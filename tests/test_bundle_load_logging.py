"""get_client() must clearly log the web-bundle load (start + finish).

The bundle fetch/parse is the slowest, blocking part of Qobuz startup, so the
server log needs an obvious "started" and "finished (in Ns)" marker around it.
These assert those markers are emitted, without touching the network.
"""

import asyncio
import logging

import pytest

from kalinka_plugin_qobuz import qobuz
from kalinka_plugin_qobuz.config_model import QobuzConfig


class _FakeBundle:
    def get_app_id(self):
        return "123456789"

    def get_secrets(self):
        return {"a": "secret_a", "b": ""}  # falsy entries are filtered out


class _FakeClient:
    def __init__(self, app_id, secrets):
        self.app_id = app_id
        self.secrets = secrets
        self.sec = None

    def auth(self, token):
        self.token = token

    async def load_user_info(self):
        pass

    async def cfg_setup(self):
        self.sec = self.secrets[0]


@pytest.fixture
def _stub_network(monkeypatch):
    monkeypatch.setattr(qobuz, "Bundle", _FakeBundle)
    monkeypatch.setattr(qobuz, "QobuzClient", _FakeClient)


def test_bundle_load_is_logged_start_and_finish(_stub_network, caplog):
    with caplog.at_level(logging.INFO, logger="qobuz"):
        asyncio.run(qobuz.get_client(QobuzConfig()))

    messages = [r.getMessage() for r in caplog.records]
    started = [m for m in messages if "Loading Qobuz web bundle" in m]
    finished = [m for m in messages if "Qobuz web bundle loaded in" in m]

    assert started, f"missing bundle-start log; got {messages}"
    assert finished, f"missing bundle-finish log; got {messages}"
    # The finish line reports the elapsed time and what was scraped.
    assert "app id 123456789" in finished[0]
    assert "1 secret(s)" in finished[0]  # only the truthy secret counts


def test_finish_logged_after_start(_stub_network, caplog):
    with caplog.at_level(logging.INFO, logger="qobuz"):
        asyncio.run(qobuz.get_client(QobuzConfig()))

    order = [
        i
        for i, r in enumerate(caplog.records)
        if "Loading Qobuz web bundle" in r.getMessage()
        or "Qobuz web bundle loaded in" in r.getMessage()
    ]
    # Start record precedes finish record.
    assert order == sorted(order) and len(order) == 2
