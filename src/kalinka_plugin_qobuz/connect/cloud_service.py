"""Qobuz Connect playback for the linked account.

Pairing hands this the account's Connect session whenever it has one — after a
handoff, or on start with a stored link — and it keeps the player joined to
that session so the Qobuz app can play on it. A session token that has run
out is renewed with the app's API token; when that cannot be done, the player
waits for the Qobuz app to hand over a new one, which it does whenever the
user chooses this player again.
"""

import asyncio
import logging
import time
from typing import Callable, Optional

import httpx
from kalinka_plugin_sdk.datamodel import Track
from kalinka_plugin_sdk.direct_playback import DirectPlayback
from kalinka_plugin_sdk.inputmodule import TrackSource

from ..auth import Credential
from ..qobuz import QobuzClient, metadata_from_track, qobuz_source_retriever
from .cloud_link import CloudLink, CloudState
from .cloud_queue import CloudQueue
from .cloud_renderer import LEVEL_FOR_FORMAT, ConnectRenderer
from .cloud_session import ConnectSession, DeviceIdentity
from .session_token import SessionToken, renew_session_token
from .store import LinkState

logger = logging.getLogger(__name__.split(".")[-1])

# Renew this long before expiry; a token this far past it is not tried at all.
RENEW_LEAD_S = 300
EXPIRED_GRACE_S = 300


class QobuzTracks:
    """TrackResolver over the plugin's REST client."""

    def __init__(self, client: QobuzClient):
        self._client = client

    async def resolve(self, track_id: int, format_id: int) -> tuple[TrackSource, Track]:
        meta, source = await asyncio.gather(
            self._client.get_track_meta(track_id),
            qobuz_source_retriever(self._client, track_id, format_id),
        )
        return source, metadata_from_track(meta)


class ConnectService:
    """The pairing's session sink: joins and leaves the account's Connect session.

    @param bearer The app's API token if one is live, to renew the session with.
    @param persist Stores a renewed session token with the link.
    """

    def __init__(
        self,
        *,
        direct: DirectPlayback,
        client: QobuzClient,
        format_id: int,
        device_name: str,
        software_version: str,
        bearer: Callable[[], Optional[Credential]],
        persist: Callable[[SessionToken], None],
        make_http: Callable[[], httpx.AsyncClient] = (
            lambda: httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        ),
        clock: Callable[[], float] = time.time,
    ):
        self._direct = direct
        self._client = client
        self._format_id = format_id
        self._device_name = device_name
        self._software_version = software_version
        self._bearer = bearer
        self._persist = persist
        self._make_http = make_http
        self._clock = clock
        self._token: Optional[SessionToken] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._link: Optional[CloudLink] = None
        self._session: Optional[ConnectSession] = None
        self._renderer: Optional[ConnectRenderer] = None
        self._needs_app = False
        self._tasks: set[asyncio.Task] = set()

    def session_ready(self, link: LinkState, *, handed_over: bool) -> None:
        """Join ``link``'s session; ``handed_over`` means the user just chose this player."""
        if link.session is None:
            # A link from before Connect playback: the app has to hand one over.
            self._needs_app = True
            return
        self._token = link.session
        self._needs_app = False
        if self._link is None:
            self._build(link.device_uuid)
        assert self._link is not None and self._session is not None
        if handed_over:
            self._session.join_as_active_next()
        waiting = self._link.state in (CloudState.IDLE, CloudState.RETRYING)
        if self._link.start():
            # A link started just now connects with the token set above.
            return
        # A handoff joins its session now; a link waiting for a token or a
        # retry picks the new one up at once.
        if handed_over or waiting:
            self._spawn(self._link.reconnect())

    def session_ended(self) -> None:
        """The account was unlinked or its link expired."""
        self._token = None
        self._needs_app = False
        self._spawn(self.stop())

    async def stop(self) -> None:
        renderer, link = self._renderer, self._link
        if renderer is not None:
            await renderer.shutdown()
        if link is not None:
            await link.stop()
        self._link = self._session = self._renderer = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def status_markdown(self) -> str:
        if self._needs_app:
            return (
                f"**Qobuz Connect:** choose *{self._device_name}* in the Qobuz app "
                "to play from it."
            )
        link, renderer = self._link, self._renderer
        if self._token is None or link is None or renderer is None:
            return ""
        if link.state is not CloudState.CONNECTED:
            text = "**Qobuz Connect:** connecting…"
            if link.last_error:
                text += f" Last attempt: {link.last_error}."
            return text
        track = renderer.now_playing
        if renderer.active and track is not None:
            return f"**Qobuz Connect:** playing *{track.title}* from the Qobuz app."
        if renderer.active:
            return "**Qobuz Connect:** selected in the Qobuz app."
        return "**Qobuz Connect:** available in the Qobuz app's device list."

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _build(self, device_uuid: str) -> None:
        queue = CloudQueue()
        identity = DeviceIdentity(
            device_uuid=device_uuid,
            friendly_name=self._device_name,
            software_version=self._software_version,
            max_audio_quality=LEVEL_FOR_FORMAT.get(self._format_id, 4),
        )
        self._link = CloudLink(
            token=self._current_token,
            on_connected=self._on_connected,
            on_messages=self._on_messages,
        )
        self._session = ConnectSession(
            identity, queue, send=self._link.send, on_established=self._link.established
        )
        self._renderer = ConnectRenderer(
            reporter=self._session,
            queue=queue,
            direct=self._direct,
            tracks=QobuzTracks(self._client),
            format_id=self._format_id,
        )
        self._session.attach(self._renderer)

    async def _on_connected(self) -> None:
        if self._session is not None:
            await self._session.on_connected()

    async def _on_messages(self, messages) -> None:
        if self._session is not None:
            await self._session.on_messages(messages)

    async def _current_token(self) -> Optional[SessionToken]:
        token = self._token
        if token is None or not token.exp:
            return token
        now = self._clock()
        if token.exp - RENEW_LEAD_S > now:
            return token
        renewed = await self._renew(token)
        if self._token is not token:
            # A handoff brought another session, or the link ended, meanwhile.
            return self._token
        if renewed is not None:
            return renewed
        if token.exp + EXPIRED_GRACE_S > now:
            return token
        logger.warning("Qobuz Connect session has expired; waiting for the Qobuz app")
        self._needs_app = True
        return None

    async def _renew(self, token: SessionToken) -> Optional[SessionToken]:
        bearer = self._bearer()
        if bearer is None or not self._client.id:
            return None
        if self._http is None:
            self._http = self._make_http()
        renewed = await renew_session_token(self._http, self._client.id, bearer, token)
        if renewed is None or self._token is not token:
            # Superseded while renewing: storing it would undo the newer session.
            return None
        self._token = renewed
        try:
            self._persist(renewed)
        except OSError as exc:
            logger.error(
                "Could not store the renewed Qobuz Connect session (%s)",
                exc.strerror or type(exc).__name__,
            )
        return renewed
