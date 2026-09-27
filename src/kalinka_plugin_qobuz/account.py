"""Who the linked credential belongs to, and proof that it can do the job.

A token handed over by the Qobuz app proves nothing by itself, so before it
replaces anything the plugin checks it against the endpoints the plugin
actually relies on. Nothing here writes to the account.

The app hands over a Bearer token that lasts an hour. Asked with it,
``user/login`` also returns a user auth token, the long-lived credential the
REST client has always used. The plugin keeps that instead once it has seen
it log in by itself, the way it will after every restart.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional

import httpx

from .auth import Credential, CredentialKind, TokenHolder
from .qobuz import InvalidAppSecretError

logger = logging.getLogger(__name__.split(".")[-1])

# user/login answers a Bearer credential with the user and a user auth token;
# user/get is asked only if it does not. The credential always travels in a
# header, never in the query string, where a URL would carry it into logs.
ACCOUNT_ENDPOINTS = {
    CredentialKind.BEARER: ("user/login", "user/get"),
    CredentialKind.USER_AUTH_TOKEN: ("user/login",),
}

# Where a track this account can stream right now is looked for. A fixed test
# track can disappear from the catalogue or a region.
PROBE_FEED = "new-releases-full"
PROBE_ALBUMS = 10

VALIDATION_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class AccountInfo:
    """The account fields streaming reports and playlist ownership need."""

    user_id: Any
    credential_id: Any
    label: str
    display_name: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AccountInfo":
        return cls(
            user_id=data["user_id"],
            credential_id=data["credential_id"],
            label=str(data.get("label", "")),
            display_name=str(data.get("display_name", "")),
        )


class AccessCheckError(Exception):
    """A check of the account failed. The message names the step and the
    HTTP status, never a credential, so it can be shown to users."""

    def __init__(self, step: str, detail: str, *, status: Optional[int] = None):
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail
        self.status = status

    @property
    def unauthorized(self) -> bool:
        return self.status == 401

    @property
    def transient(self) -> bool:
        return _is_transient(self.status)


def _is_transient(status: Optional[int]) -> bool:
    """Whether an HTTP status says Qobuz is busy rather than that the answer is no."""
    return status is not None and (status == 429 or status >= 500)


class IneligibleError(AccessCheckError):
    def __init__(self):
        super().__init__("account", "free Qobuz accounts cannot stream", status=None)


@dataclass(frozen=True)
class Validated:
    """A credential proven to work, and the account it belongs to.

    @note ``credential`` is the one to keep: the user auth token Qobuz issued
        in exchange for a Bearer credential, when it issued one.
    """

    account: AccountInfo
    credential: Credential


def _json_or_none(response: httpx.Response) -> Any:
    if not response.is_success:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _user_object(body: Any) -> Optional[dict]:
    if not isinstance(body, dict):
        return None
    user = body.get("user") if isinstance(body.get("user"), dict) else body
    credential = user.get("credential")
    if "id" not in user or not isinstance(credential, dict) or "id" not in credential:
        return None
    return user


def _account_from(user: dict) -> AccountInfo:
    parameters = user["credential"].get("parameters")
    if not parameters:
        raise IneligibleError()
    return AccountInfo(
        user_id=user["id"],
        credential_id=user["credential"]["id"],
        label=str(parameters.get("short_label") or user["credential"].get("label") or ""),
        display_name=str(user.get("display_name") or user.get("login") or ""),
    )


def _summary_status(statuses: list[int]) -> int:
    if statuses and all(status == 401 for status in statuses):
        return 401
    transient = [s for s in statuses if _is_transient(s)]
    return transient[0] if transient else statuses[0]


async def probe_account(client, credential: Credential) -> tuple[AccountInfo, Optional[Credential]]:
    """Resolve the account behind ``credential``, which ``client`` sends.

    @return The account, and a user auth token when Qobuz issued one in
        exchange for a Bearer credential.
    @throw AccessCheckError when no endpoint returns a user object;
        IneligibleError for an account without a streaming subscription.
    """
    answers: list[tuple[str, int]] = []
    for endpoint in ACCOUNT_ENDPOINTS[credential.kind]:
        response = await client.session.get(client.base + endpoint)
        body = _json_or_none(response)
        logger.info(
            "Qobuz account probe %s -> HTTP %d, keys %s",
            endpoint,
            response.status_code,
            sorted(body) if isinstance(body, dict) else "-",
        )
        user = _user_object(body)
        if user is not None:
            return _account_from(user), _exchanged(credential, body)
        answers.append((endpoint, response.status_code))

    tried = ", ".join(f"{endpoint} HTTP {status}" for endpoint, status in answers)
    raise AccessCheckError(
        "account",
        f"no account details ({tried})",
        status=_summary_status([status for _, status in answers]),
    )


def _exchanged(credential: Credential, body: dict) -> Optional[Credential]:
    if credential.kind is not CredentialKind.BEARER:
        return None
    token = body.get("user_auth_token")
    if not isinstance(token, str) or not token.strip():
        return None
    return Credential(CredentialKind.USER_AUTH_TOKEN, token)


async def _check(session: httpx.AsyncClient, url: str, step: str, **params) -> Any:
    response = await session.get(url, params=params)
    if not response.is_success:
        raise AccessCheckError(step, f"HTTP {response.status_code}", status=response.status_code)
    body = _json_or_none(response)
    if not isinstance(body, dict):
        raise AccessCheckError(step, "unreadable answer")
    return body


def _streamable(items: Any) -> list[dict]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("streamable", True)]


async def _probe_track(session: httpx.AsyncClient, base: str):
    """A track this account can stream now, found through the catalogue."""
    featured = await _check(
        session, base + "album/getFeatured", "catalogue", type=PROBE_FEED, offset=0, limit=PROBE_ALBUMS
    )
    for album in _streamable(featured.get("albums", {}).get("items")):
        body = await _check(session, base + "album/get", "catalogue", album_id=album["id"], offset=0, limit=50)
        tracks = _streamable(body.get("tracks", {}).get("items"))
        if tracks:
            return tracks[0]["id"]
    raise AccessCheckError("catalogue", "no streamable track among new releases")


async def _adopt(client, holder: TokenHolder, issued: Credential, account: AccountInfo) -> AccountInfo:
    """Switch to ``issued`` if it logs in by itself; otherwise keep the credential in force.

    @note The credential kept is the one in ``holder`` now, not the one the
        validation started with: a renewal during the account probe replaced it.
    """
    kept = holder.current()
    holder.install(issued)
    try:
        confirmed, _ = await probe_account(client, issued)
    except AccessCheckError as exc:
        _reinstate(holder, issued, kept)
        if exc.transient:
            raise
        logger.warning(
            "Qobuz issued a user auth token that could not log in by itself (%s); "
            "keeping the app's token, which needs renewing every hour",
            exc,
        )
        return account
    except BaseException:
        # A network error or the validation deadline says nothing about the
        # issued token; never leave it in force unconfirmed.
        _reinstate(holder, issued, kept)
        raise
    logger.info("Qobuz issued a user auth token for this account; the plugin uses it from now on")
    return confirmed


def _reinstate(holder: TokenHolder, issued: Credential, kept: Credential) -> None:
    """Put ``kept`` back, unless something else replaced ``issued`` meanwhile."""
    if holder.credential is issued:
        holder.install(kept)


async def validate_account_access(client, holder: TokenHolder) -> Validated:
    """Check that the credential in ``holder``, which ``client`` sends, can do
    what the plugin does.

    Reads the account, its favourites and playlists, the catalogue, and a
    signed stream URL. When Qobuz issues a user auth token for a Bearer
    credential, it replaces the Bearer in ``holder`` and is what the later
    checks use. The app secret selected on the way is left on ``client.sec``.

    @throw AccessCheckError naming the failed step, httpx.TransportError, or
        asyncio.TimeoutError.
    """
    return await asyncio.wait_for(_validate(client, holder), VALIDATION_TIMEOUT_S)


async def _validate(client, holder: TokenHolder) -> Validated:
    session, base = client.session, client.base
    account, issued = await probe_account(client, holder.current())
    if issued is not None:
        account = await _adopt(client, holder, issued, account)
    await _check(session, base + "favorite/getUserFavoriteIds", "favourites", limit=1)
    await _check(session, base + "playlist/getUserPlaylists", "playlists", offset=0, limit=1)
    track_id = await _probe_track(session, base)
    try:
        await client.cfg_setup(track_id)
        stream = await client.get_track_url(track_id, fmt_id=5)
    except InvalidAppSecretError:
        raise AccessCheckError("stream", "no app secret was accepted for a stream URL")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise AccessCheckError("stream", f"HTTP {status}", status=status) from None
    if not isinstance(stream, dict) or not stream.get("url"):
        raise AccessCheckError("stream", "no stream URL in the answer")
    # What is in force now: the adopted token, and any renewal made on the way.
    return Validated(account=account, credential=holder.current())


def describe_failure(exc: BaseException) -> str:
    """A short, credential-free reason for a failed check, fit for the status page."""
    if isinstance(exc, AccessCheckError):
        return str(exc)
    if isinstance(exc, asyncio.TimeoutError):
        return "Qobuz did not answer in time"
    if isinstance(exc, httpx.TransportError):
        return f"network error reaching Qobuz ({type(exc).__name__})"
    return type(exc).__name__
