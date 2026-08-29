"""load_bundle: the fetch must not block the event loop, must observe a
deadline (getaddrinfo has no timeout of its own), and on deadline must abort
the worker by closing its session rather than abandoning it."""

import asyncio
import time

import pytest

from kalinka_plugin_qobuz import bundle as bundle_mod
from kalinka_plugin_qobuz.bundle import Bundle, load_bundle


def test_fetch_runs_off_the_event_loop(monkeypatch):
    seen = {}

    def fake_fetch(session):
        try:
            asyncio.get_running_loop()
            seen["on_loop"] = True
        except RuntimeError:
            seen["on_loop"] = False
        return Bundle("x")

    monkeypatch.setattr(bundle_mod, "fetch_bundle", fake_fetch)

    result = asyncio.run(load_bundle())

    assert isinstance(result, Bundle)
    assert seen == {"on_loop": False}


def test_deadline_trips_on_a_hung_fetch(monkeypatch):
    def hanging_fetch(session):
        # A worker ignoring its session simulates the one uninterruptible
        # phase (a hung resolver); the grace await reaps it when it returns.
        time.sleep(1)
        return Bundle("x")

    monkeypatch.setattr(bundle_mod, "fetch_bundle", hanging_fetch)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(load_bundle(deadline_s=0.1))


def test_deadline_aborts_the_worker_via_its_session(monkeypatch):
    def cooperative_fetch(session):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if session.is_closed:
                raise RuntimeError("aborted")
            time.sleep(0.02)
        return Bundle("never")

    monkeypatch.setattr(bundle_mod, "fetch_bundle", cooperative_fetch)

    start = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(load_bundle(deadline_s=0.1))
    elapsed = time.monotonic() - start

    # Closing the session stopped the worker: well under its 10s runtime,
    # and under the abort grace — the worker exited, it wasn't abandoned.
    assert elapsed < 3


def test_session_is_closed_when_the_fetch_fails(monkeypatch):
    sessions = []

    def failing_fetch(session):
        sessions.append(session)
        raise ConnectionError("no route")

    monkeypatch.setattr(bundle_mod, "fetch_bundle", failing_fetch)

    with pytest.raises(ConnectionError):
        asyncio.run(load_bundle())

    assert sessions[0].is_closed
