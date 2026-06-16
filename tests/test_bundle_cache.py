"""Tests for the Qobuz web-bundle credential cache.

Covers the on-disk cache roundtrip/robustness and the get_client() fast path:
a cache hit must skip the (slow) Bundle download, a cache miss must fetch and
persist, and a stale cache (API rejects the cached secret) must invalidate and
re-fetch exactly once.
"""

import asyncio
import json
from pathlib import Path

import pytest

from kalinka_plugin_qobuz import bundle_cache
from kalinka_plugin_qobuz import qobuz
from kalinka_plugin_qobuz.config_model import QobuzConfig
from kalinka_plugin_qobuz.qobuz import InvalidAppSecretError


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Point the cache at a throwaway dir so tests never touch the real one.

    ``CACHE_DIRECTORY`` takes precedence over ``XDG_CACHE_HOME`` in the resolver
    (it's what systemd sets in production), so clear it to make the XDG path
    deterministic under any environment."""
    monkeypatch.delenv("CACHE_DIRECTORY", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    return tmp_path


# --------------------------------------------------------------------------
# Cache module
# --------------------------------------------------------------------------


def test_cache_dir_precedence_and_no_home_expansion(monkeypatch):
    # 1. CACHE_DIRECTORY (set by systemd) wins, first entry of a :-list.
    monkeypatch.setenv("CACHE_DIRECTORY", "/var/cache/kalinka:/other")
    monkeypatch.setenv("XDG_CACHE_HOME", "/xdg")
    assert bundle_cache._cache_dir() == Path("/var/cache/kalinka")

    # 2. else XDG_CACHE_HOME/kalinka.
    monkeypatch.delenv("CACHE_DIRECTORY", raising=False)
    assert bundle_cache._cache_dir() == Path("/xdg/kalinka")

    # 3. else the packaged default — never anything derived from "~".
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/someone")  # must be ignored
    resolved = bundle_cache._cache_dir()
    assert resolved == Path("/var/cache/kalinka")
    assert "~" not in str(resolved)
    assert "/home/someone" not in str(resolved)


def test_roundtrip_save_load():
    assert bundle_cache.load_cached_bundle() is None
    bundle_cache.save_cached_bundle("123456789", "deadbeef")
    assert bundle_cache.load_cached_bundle() == ("123456789", "deadbeef")


def test_clear_removes_cache():
    bundle_cache.save_cached_bundle("123456789", "deadbeef")
    bundle_cache.clear_cached_bundle()
    assert bundle_cache.load_cached_bundle() is None
    # Idempotent: clearing a missing cache is a no-op, not an error.
    bundle_cache.clear_cached_bundle()


def test_empty_values_are_not_persisted():
    bundle_cache.save_cached_bundle("", "secret")
    bundle_cache.save_cached_bundle("app", "")
    assert bundle_cache.load_cached_bundle() is None


def test_malformed_file_is_ignored(tmp_path):
    path = bundle_cache._cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{", encoding="utf-8")
    assert bundle_cache.load_cached_bundle() is None


def test_wrong_version_is_ignored():
    path = bundle_cache._cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 999, "app_id": "x", "secret": "y"}), encoding="utf-8"
    )
    assert bundle_cache.load_cached_bundle() is None


# --------------------------------------------------------------------------
# get_client() fast path
# --------------------------------------------------------------------------


class _FakeBundle:
    """Stand-in for the network Bundle download."""

    instances = 0

    def __init__(self):
        type(self).instances += 1

    def get_app_id(self):
        return "999999999"

    def get_secrets(self):
        return {"a": "fresh_secret", "b": ""}


class _FakeClient:
    def __init__(self, sec):
        self.sec = sec


def _patch(monkeypatch, *, init_results):
    """Patch Bundle + _init_client. ``init_results`` is a list of either a
    secret string (success → client with that .sec) or an Exception to raise,
    consumed one per _init_client call."""
    _FakeBundle.instances = 0
    monkeypatch.setattr(qobuz, "Bundle", _FakeBundle)

    calls = []

    async def fake_init(config, app_id, secrets):
        calls.append((app_id, list(secrets)))
        outcome = init_results[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeClient(sec=outcome)

    monkeypatch.setattr(qobuz, "_init_client", fake_init)
    return calls


def test_cache_miss_fetches_bundle_and_persists(monkeypatch):
    calls = _patch(monkeypatch, init_results=["fresh_secret"])

    client = asyncio.run(qobuz.get_client(QobuzConfig()))

    assert _FakeBundle.instances == 1  # bundle was downloaded
    assert client.sec == "fresh_secret"
    # The validated app id + secret are now cached.
    assert bundle_cache.load_cached_bundle() == ("999999999", "fresh_secret")
    # Fresh fetch passes the full (truthy) secret list.
    assert calls == [("999999999", ["fresh_secret"])]


def test_cache_hit_skips_bundle(monkeypatch):
    bundle_cache.save_cached_bundle("111111111", "cached_secret")
    calls = _patch(monkeypatch, init_results=["cached_secret"])

    client = asyncio.run(qobuz.get_client(QobuzConfig()))

    assert _FakeBundle.instances == 0  # no download on a cache hit
    assert client.sec == "cached_secret"
    assert calls == [("111111111", ["cached_secret"])]


def test_stale_cache_invalidates_and_refetches(monkeypatch):
    bundle_cache.save_cached_bundle("111111111", "stale_secret")
    calls = _patch(
        monkeypatch,
        init_results=[InvalidAppSecretError("stale"), "fresh_secret"],
    )

    client = asyncio.run(qobuz.get_client(QobuzConfig()))

    assert _FakeBundle.instances == 1  # refetched after rejection
    assert client.sec == "fresh_secret"
    # Cache now holds the freshly-validated value.
    assert bundle_cache.load_cached_bundle() == ("999999999", "fresh_secret")
    # First attempt used the cached secret, second the fresh bundle secrets.
    assert calls == [
        ("111111111", ["stale_secret"]),
        ("999999999", ["fresh_secret"]),
    ]
