"""The linked account survives restarts, privately."""

import json
import os
import stat
import uuid

import pytest

from kalinka_plugin_qobuz.connect.store import LinkState, LinkStore, default_store_path

from conftest import ACCOUNT, API_JWT, assert_no_secrets, bearer


def _linked(device_uuid: str) -> LinkState:
    return LinkState(
        device_uuid=device_uuid,
        linked=True,
        linked_at=1_700_000_000,
        credential=bearer(API_JWT, exp=4102444800),
        account=ACCOUNT,
    )


def test_a_new_store_creates_and_keeps_a_device_identity(tmp_path):
    store = LinkStore(str(tmp_path / "qobuz" / "connect.json"))

    first = store.load_or_create()
    again = store.load_or_create()

    assert uuid.UUID(first.device_uuid)
    assert again.device_uuid == first.device_uuid
    assert not first.linked


def test_a_link_round_trips(tmp_path):
    store = LinkStore(str(tmp_path / "qobuz" / "connect.json"))
    state = _linked(store.load_or_create().device_uuid)

    store.save(state)

    assert store.load_or_create() == state


def test_the_file_is_owner_only_and_written_whole(tmp_path):
    path = tmp_path / "qobuz" / "connect.json"
    store = LinkStore(str(path))
    store.save(_linked(str(uuid.uuid4())))

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700
    assert os.listdir(path.parent) == ["connect.json"]


@pytest.mark.parametrize("content", ["{ not json", "null", "[]", '"linked"'])
def test_an_unreadable_file_is_set_aside_and_starts_unlinked(tmp_path, content):
    path = tmp_path / "qobuz" / "connect.json"
    path.parent.mkdir()
    path.write_text(content)

    state = LinkStore(str(path)).load_or_create()

    assert not state.linked
    assert any(name.startswith("connect.json.corrupt-") for name in os.listdir(path.parent))
    assert json.loads(path.read_text())["device_uuid"] == state.device_uuid


def test_unlinking_keeps_the_device_identity():
    state = _linked(str(uuid.uuid4()))

    unlinked = state.unlinked()

    assert unlinked == LinkState(device_uuid=state.device_uuid)


def test_a_state_never_shows_its_token():
    assert_no_secrets(repr(_linked(str(uuid.uuid4()))))


def test_the_default_path_follows_the_install_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("KALINKA_PREFIX", str(tmp_path))

    assert default_store_path() == str(tmp_path / "var/lib/kalinka/qobuz/connect.json")
