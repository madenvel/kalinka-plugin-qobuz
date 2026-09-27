"""A stream URL is signed with the app secret exactly as before, whatever
credential rides along, and an unusable link reads as an unavailable source."""

import hashlib

import pytest
from kalinka_plugin_sdk.inputmodule import DirectUrl, SourceUnavailableError

from kalinka_plugin_qobuz.auth import EXPIRED, NOT_LINKED, TokenHolder
from kalinka_plugin_qobuz.qobuz import InvalidAppSecretError, qobuz_source_retriever

from conftest import API_JWT, GOOD_SECRET, bearer


def _linked(api):
    holder = TokenHolder()
    holder.install(bearer())
    client = api.client(holder)
    client.sec = GOOD_SECRET
    return client


@pytest.mark.asyncio
async def test_the_stream_request_is_signed_and_carries_the_bearer(api):
    client = _linked(api)

    source = await qobuz_source_retriever(client, 12345, 27)

    assert source.source == DirectUrl(url="https://streaming.qobuz.test/12345")
    assert source.format == "audio/flac"
    sent = api.requests[0]
    params = sent.url.params
    signed = f"trackgetFileUrlformat_id27intentstreamtrack_id12345{params['request_ts']}{GOOD_SECRET}"
    assert params["request_sig"] == hashlib.md5(signed.encode()).hexdigest()
    assert sent.headers["Authorization"] == f"Bearer {API_JWT}"
    assert "X-User-Auth-Token" not in sent.headers


@pytest.mark.asyncio
async def test_the_signed_response_is_kept_for_streaming_reports(api):
    client = _linked(api)

    await qobuz_source_retriever(client, 12345, 6)

    assert client.track_url_response_cache["12345"]["format_id"] == 6


@pytest.mark.parametrize("reason", [NOT_LINKED, EXPIRED])
@pytest.mark.asyncio
async def test_an_unusable_link_makes_the_source_unavailable_with_its_reason(api, reason):
    holder = TokenHolder()
    holder.clear(reason)
    client = api.client(holder)
    client.sec = GOOD_SECRET

    with pytest.raises(SourceUnavailableError, match=reason[:20]):
        await qobuz_source_retriever(client, 12345, 27)
    assert api.requests == []


@pytest.mark.asyncio
async def test_a_rejected_credential_makes_the_source_unavailable(api):
    api.valid_tokens = set()
    client = _linked(api)

    with pytest.raises(SourceUnavailableError, match="did not accept"):
        await qobuz_source_retriever(client, 12345, 27)


@pytest.mark.asyncio
async def test_a_stream_before_any_secret_is_chosen_is_unavailable_not_failed(api):
    """A stored link serves requests while it is rechecked; the app secret is
    chosen by that check, so a stream asked for meanwhile is unavailable."""
    holder = TokenHolder()
    holder.install(bearer())
    client = api.client(holder)

    with pytest.raises(SourceUnavailableError, match="still connecting"):
        await qobuz_source_retriever(client, 12345, 27)
    assert api.requests == []


@pytest.mark.asyncio
async def test_a_failed_secret_search_keeps_the_secret_in_use(api):
    client = _linked(api)
    api.status["track/getFileUrl"] = 400

    with pytest.raises(InvalidAppSecretError):
        await client.cfg_setup(12345)

    assert client.sec == GOOD_SECRET
