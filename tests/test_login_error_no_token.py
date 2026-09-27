"""A failed login is reported without the token.

``user/login`` carries the token in its query string, and the setup failure
is logged and shown in the app, so its message must not quote the URL.
"""

import asyncio

import httpx
import pytest

from kalinka_plugin_qobuz.qobuz import AuthenticationError, QobuzClient

TOKEN = "qobuz-token-do-not-log"


def _client(status: int) -> QobuzClient:
    client = QobuzClient("123456789", [])
    client.session = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status))
    )
    client.auth(TOKEN)
    return client


@pytest.mark.parametrize("status", [400, 403, 429, 503])
def test_a_refused_login_says_why_without_the_token(status):
    with pytest.raises(AuthenticationError) as raised:
        asyncio.run(_client(status).load_user_info())

    assert str(status) in str(raised.value)
    assert TOKEN not in str(raised.value)


def test_a_rejected_token_is_still_named_as_such():
    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        asyncio.run(_client(401).load_user_info())
