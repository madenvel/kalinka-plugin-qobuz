"""What the Qobuz app POSTs, and what the plugin takes from it."""

import json

import pytest

from kalinka_plugin_qobuz.auth import CredentialKind
from kalinka_plugin_qobuz.connect.handoff import (
    HandoffError,
    claim_names,
    describe,
    parse_handoff,
)

from conftest import API_JWT, QCONNECT_JWT, assert_no_secrets, handoff_body

NOW = 1_700_000_000


def _body(**changes) -> bytes:
    document = json.loads(handoff_body())
    for path, value in changes.items():
        target = document
        *parents, leaf = path.split("__")
        for key in parents:
            target = target[key]
        if value is None:
            target.pop(leaf, None)
        else:
            target[leaf] = value
    return json.dumps(document).encode()


def test_a_complete_handoff_yields_the_api_bearer_credential():
    handoff = parse_handoff(handoff_body(), NOW)

    assert handoff.credential.kind is CredentialKind.BEARER
    assert handoff.credential.token == API_JWT
    assert handoff.credential.exp == 4102444800
    assert handoff.session_id == "sess-1234-abcd"
    assert handoff.keys == ("jwt_api", "jwt_qconnect", "session_id")


def test_a_plain_user_auth_token_is_preferred_when_present():
    handoff = parse_handoff(handoff_body(user_auth_token="uat-synthetic"), NOW)

    assert handoff.credential.kind is CredentialKind.USER_AUTH_TOKEN
    assert handoff.credential.token == "uat-synthetic"


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"jwt_qconnect": None}, "missing jwt_qconnect"),
        ({"jwt_qconnect__jwt": ""}, "missing jwt_qconnect.jwt"),
        ({"jwt_qconnect__endpoint": None}, "missing jwt_qconnect.endpoint"),
        ({"jwt_qconnect__exp": NOW + 30}, "jwt_qconnect is already expired"),
        ({"jwt_api": None}, "missing jwt_api"),
        ({"jwt_api__jwt": " "}, "missing jwt_api"),
    ],
)
def test_an_incomplete_handoff_is_refused_with_pibuz_wording(changes, message):
    with pytest.raises(HandoffError) as raised:
        parse_handoff(_body(**changes), NOW)

    assert str(raised.value) == message


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b"\xff\xfe"])
def test_a_body_that_is_not_a_json_object_is_refused(body):
    with pytest.raises(HandoffError):
        parse_handoff(body, NOW)


@pytest.mark.parametrize(
    "exp, seconds",
    [
        (None, 0),
        ("4102444800", 0),
        (True, 0),
        (-5, 0),
        (float("nan"), 0),
        (float("inf"), 0),
        (4102444800.7, 4102444800),
        (4102444800000, 4102444800),
    ],
)
def test_expiry_is_read_as_unix_seconds(exp, seconds):
    handoff = parse_handoff(_body(jwt_api__exp=exp), NOW)

    assert handoff.credential.exp == seconds


def test_a_missing_session_id_is_empty():
    assert parse_handoff(_body(session_id=None), NOW).session_id == ""


def test_same_handoff_is_recognised():
    first = parse_handoff(handoff_body(), NOW)

    assert first.same_as(parse_handoff(handoff_body(), NOW))
    assert not first.same_as(parse_handoff(handoff_body(session_id="other"), NOW))


def test_describing_a_handoff_reveals_no_credential():
    handoff = parse_handoff(handoff_body(), NOW)

    text = describe(handoff) + repr(handoff)

    assert_no_secrets(text)
    assert "sess-123…" in text
    assert "claims ['exp', 'scope', 'sub']" in text


def test_claim_names_survive_garbage():
    assert claim_names("not-a-jwt") == []
    assert claim_names("a.@@@.c") == []
    assert claim_names(QCONNECT_JWT) == ["aud", "sub"]
