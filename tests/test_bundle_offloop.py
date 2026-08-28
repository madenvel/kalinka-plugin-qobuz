"""The web-bundle fetch must not block the event loop, and must have a deadline.

Bundle() is synchronous httpx; run inline it froze the whole server during
setup, and its DNS lookup (getaddrinfo) has no timeout at all, so a blackholed
resolver stalled startup indefinitely.
"""

import asyncio
import time

import pytest

from kalinka_plugin_qobuz import qobuz
from kalinka_plugin_qobuz.config_model import QobuzConfig


class _RecordingBundle:
    on_loop = None

    def __init__(self):
        try:
            asyncio.get_running_loop()
            _RecordingBundle.on_loop = True
        except RuntimeError:
            _RecordingBundle.on_loop = False

    def get_app_id(self):
        return "123456789"

    def get_secrets(self):
        return {"a": "secret_a"}


class _FakeClient:
    def __init__(self, app_id, secrets):
        self.secrets = secrets

    def auth(self, token):
        pass

    async def load_user_info(self):
        pass

    async def cfg_setup(self):
        pass


def test_bundle_is_built_off_the_event_loop(monkeypatch):
    monkeypatch.setattr(qobuz, "Bundle", _RecordingBundle)
    monkeypatch.setattr(qobuz, "QobuzClient", _FakeClient)

    asyncio.run(qobuz.get_client(QobuzConfig()))

    assert _RecordingBundle.on_loop is False


def test_bundle_load_has_a_deadline(monkeypatch):
    class _HangingBundle:
        def __init__(self):
            # asyncio.run joins the leaked worker thread on shutdown, so keep
            # the hang just long enough to trip the shrunken deadline.
            time.sleep(1)

    monkeypatch.setattr(qobuz, "Bundle", _HangingBundle)
    monkeypatch.setattr(qobuz, "QobuzClient", _FakeClient)
    monkeypatch.setattr(qobuz, "_BUNDLE_DEADLINE_S", 0.1)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(qobuz.get_client(QobuzConfig()))
