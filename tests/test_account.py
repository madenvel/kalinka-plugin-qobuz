"""The account behind a linked credential, and proof it can do the plugin's job.

A failed check says why, by step and HTTP status, and never quotes a
credential.
"""

import asyncio
import logging

import httpx
import pytest

from kalinka_plugin_qobuz.account import (
    AccessCheckError,
    IneligibleError,
    describe_failure,
    probe_account,
    validate_account_access,
)
from kalinka_plugin_qobuz.auth import TokenHolder

from conftest import (
    ACCOUNT,
    API_JWT,
    APP_ID,
    GOOD_SECRET,
    ISSUED_UAT,
    RENEWED_JWT,
    assert_no_secrets,
    bearer,
    uat,
)


def _linked(api, credential=None):
    holder = TokenHolder()
    holder.install(credential or bearer())
    return api.client(holder), holder


@pytest.mark.asyncio
async def test_a_bearer_login_yields_the_account_and_a_user_auth_token(api):
    client, _ = _linked(api)

    account, exchanged = await probe_account(client, bearer())

    assert account == ACCOUNT
    assert exchanged == uat()
    assert api.endpoint_calls() == ["user/login"]
    assert not api.requests[0].url.params


@pytest.mark.asyncio
async def test_no_exchange_when_qobuz_issues_no_user_auth_token(api):
    api.issue_uat = False
    client, _ = _linked(api)

    account, exchanged = await probe_account(client, bearer())

    assert account == ACCOUNT and exchanged is None


@pytest.mark.asyncio
async def test_user_get_is_asked_when_user_login_does_not_answer(api):
    api.account_endpoint = "user/get"
    client, _ = _linked(api)

    account, exchanged = await probe_account(client, bearer())

    assert account == ACCOUNT and exchanged is None
    assert api.endpoint_calls() == ["user/login", "user/get"]


@pytest.mark.asyncio
async def test_a_user_auth_token_logs_in_by_header_and_never_in_the_url(api):
    client, _ = _linked(api, uat())

    account, exchanged = await probe_account(client, uat())

    assert account == ACCOUNT and exchanged is None
    sent = api.requests[0]
    assert ISSUED_UAT not in str(sent.url)
    assert sent.headers["X-User-Auth-Token"] == ISSUED_UAT
    assert "Authorization" not in sent.headers


@pytest.mark.asyncio
async def test_a_free_account_is_ineligible(api):
    api.user["credential"] = {"id": 1, "parameters": None}
    client, _ = _linked(api)

    with pytest.raises(IneligibleError, match="free Qobuz accounts"):
        await probe_account(client, bearer())


@pytest.mark.parametrize("credential", [bearer(), uat()], ids=["bearer", "user_auth_token"])
@pytest.mark.parametrize("status", [400, 403, 429, 503])
@pytest.mark.asyncio
async def test_a_refused_probe_names_the_status_without_the_token(api, status, credential, caplog):
    api.status = {"user/login": status, "user/get": status}
    client, _ = _linked(api, credential)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(AccessCheckError) as raised:
            await probe_account(client, credential)

    assert f"HTTP {status}" in str(raised.value)
    assert raised.value.transient == (status in (429, 503))
    assert_no_secrets(str(raised.value), caplog.text)


@pytest.mark.asyncio
async def test_a_rejected_token_is_named_as_unauthorized(api):
    api.valid_tokens = set()
    client, _ = _linked(api)

    with pytest.raises(AccessCheckError) as raised:
        await probe_account(client, bearer())

    assert raised.value.unauthorized


@pytest.mark.asyncio
async def test_validation_switches_to_the_issued_token_for_everything_after_login(api):
    client, holder = _linked(api)

    validated = await validate_account_access(client, holder)

    assert validated.account == ACCOUNT
    assert validated.credential == uat()
    assert holder.current() == uat()
    assert client.sec == GOOD_SECRET
    calls = api.endpoint_calls()
    assert calls[:6] == [
        "user/login",
        "user/login",
        "favorite/getUserFavoriteIds",
        "playlist/getUserPlaylists",
        "album/getFeatured",
        "album/get",
    ]
    assert set(calls[6:]) == {"track/getFileUrl"}
    assert api.requests[0].headers["Authorization"] == f"Bearer {API_JWT}"
    for request in api.requests[1:]:
        assert request.headers["X-User-Auth-Token"] == ISSUED_UAT
        assert "Authorization" not in request.headers
        assert ISSUED_UAT not in str(request.url)
    assert all(request.method == "GET" for request in api.requests)


@pytest.mark.parametrize("status", [400, 401])
@pytest.mark.asyncio
async def test_an_issued_token_that_cannot_log_in_alone_is_not_adopted(api, status, caplog):
    api.uat_login_status = status
    client, holder = _linked(api)

    with caplog.at_level(logging.INFO):
        validated = await validate_account_access(client, holder)

    assert validated.credential == bearer()
    assert holder.current() == bearer()
    assert api.requests[-1].headers["Authorization"] == f"Bearer {API_JWT}"
    assert "keeping the app's token" in caplog.text
    assert_no_secrets(caplog.text)


@pytest.mark.asyncio
async def test_a_busy_qobuz_while_confirming_the_issued_token_fails_this_attempt(api):
    api.uat_login_status = 503
    client, holder = _linked(api)

    with pytest.raises(AccessCheckError) as raised:
        await validate_account_access(client, holder)

    assert raised.value.transient
    # The next attempt starts from the app's token, not the unconfirmed one.
    assert holder.current() == bearer()


@pytest.mark.asyncio
async def test_a_network_error_while_confirming_the_issued_token_restores_the_app_token(api):
    serve = api.handle

    def handle(request):
        if request.headers.get("X-User-Auth-Token") == ISSUED_UAT:
            raise httpx.ConnectError("down")
        return serve(request)

    api.handle = handle
    client, holder = _linked(api)

    with pytest.raises(httpx.ConnectError):
        await validate_account_access(client, holder)

    assert holder.current() == bearer()


@pytest.mark.parametrize("issue_uat", [True, False], ids=["uat-refused", "no-uat"])
@pytest.mark.asyncio
async def test_a_renewal_made_during_the_check_is_what_it_keeps(api, issue_uat):
    api.valid_tokens = {RENEWED_JWT}
    api.issue_uat = issue_uat
    api.uat_login_status = 401
    renewed = bearer(RENEWED_JWT, 4102448400)
    holder = TokenHolder()
    holder.install(bearer(API_JWT, 4102444800))

    async def renew_once(rejected):
        if holder.credential != rejected:
            return True
        if holder.credential == renewed:
            return False
        holder.install(renewed)
        return True

    client = api.client(holder, on_unauthorized=renew_once)

    validated = await validate_account_access(client, holder)

    assert validated.credential == renewed
    assert holder.current() == renewed


@pytest.mark.asyncio
async def test_without_an_issued_token_the_bearer_is_kept(api):
    api.issue_uat = False
    client, holder = _linked(api)

    validated = await validate_account_access(client, holder)

    assert validated.credential == bearer()
    assert holder.current() == bearer()


@pytest.mark.asyncio
async def test_a_stored_user_auth_token_validates_as_itself(api):
    client, holder = _linked(api, uat())

    validated = await validate_account_access(client, holder)

    assert validated.credential == uat()


@pytest.mark.asyncio
async def test_the_probe_track_is_one_the_account_can_stream_now(api):
    client, holder = _linked(api)

    await validate_account_access(client, holder)

    albums = [r.url.params["album_id"] for r in api.requests if r.url.path.endswith("album/get")]
    tracks = {r.url.params["track_id"] for r in api.requests if r.url.path.endswith("getFileUrl")}
    assert albums == ["alb1"]
    assert tracks == {"222"}


@pytest.mark.asyncio
async def test_no_streamable_new_release_fails_the_catalogue_step(api):
    api.album_tracks = [{"id": 111, "streamable": False}]
    client, holder = _linked(api)

    with pytest.raises(AccessCheckError) as raised:
        await validate_account_access(client, holder)

    assert raised.value.step == "catalogue"


@pytest.mark.parametrize(
    "endpoint, step",
    [
        ("favorite/getUserFavoriteIds", "favourites"),
        ("playlist/getUserPlaylists", "playlists"),
        ("album/getFeatured", "catalogue"),
        ("album/get", "catalogue"),
    ],
)
@pytest.mark.asyncio
async def test_validation_names_the_step_that_failed(api, endpoint, step):
    api.status = {endpoint: 403}
    client, holder = _linked(api)

    with pytest.raises(AccessCheckError) as raised:
        await validate_account_access(client, holder)

    assert raised.value.step == step
    assert raised.value.status == 403


@pytest.mark.asyncio
async def test_a_missing_track_does_not_disqualify_a_secret(api):
    api.missing_tracks = {5966783}
    client, _ = _linked(api)

    await client.cfg_setup(5966783)

    assert client.sec == GOOD_SECRET


@pytest.mark.asyncio
async def test_a_track_that_will_not_stream_fails_the_stream_step(api):
    api.missing_tracks = {222}
    client, holder = _linked(api)

    with pytest.raises(AccessCheckError) as raised:
        await validate_account_access(client, holder)

    assert (raised.value.step, raised.value.status) == ("stream", 404)


@pytest.mark.asyncio
async def test_a_stream_url_refused_for_every_secret_fails_the_stream_step(api):
    client, holder = _linked(api)
    client.configure_app(APP_ID, ["wrong-secret", "also-wrong"])

    with pytest.raises(AccessCheckError) as raised:
        await validate_account_access(client, holder)

    assert raised.value.step == "stream"


def test_failures_are_described_without_detail_that_could_carry_a_token():
    assert describe_failure(asyncio.TimeoutError()) == "Qobuz did not answer in time"
    assert "ConnectError" in describe_failure(httpx.ConnectError("boom"))
    assert describe_failure(AccessCheckError("account", "HTTP 401", status=401)) == "account: HTTP 401"
