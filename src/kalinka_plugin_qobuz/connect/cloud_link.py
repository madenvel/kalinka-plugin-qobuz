"""The WebSocket connection to the Qobuz Connect cloud, kept up until stopped.

Each connection authenticates with the session token current at that moment,
so a renewed or newly handed-over token is used from the next reconnect on.
Backoff follows Pibuz: 2 s doubling to 30 s, ten attempts, then a minute's
rest and again; the count starts over once the cloud confirms a session.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/qconnect-transport-ws/src/transport.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import asyncio
import enum
import logging
from typing import Any, Awaitable, Callable, Iterable, Optional

from google.protobuf.message import DecodeError
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import WebSocketException

from ..auth import fingerprint
from . import frames
from .proto import qconnect_pb2 as qc
from .proto import qws_pb2 as qws
from .session_token import SessionToken, endpoint_host

logger = logging.getLogger(__name__.split(".")[-1])

# websockets logs frames at DEBUG, and AUTHENTICATE carries the session token.
_wire_logger = logging.getLogger("qobuz-connect-wire")
_wire_logger.setLevel(logging.WARNING)

BACKOFF_START_S = 2
BACKOFF_MAX_S = 30
MAX_ATTEMPTS = 10
REST_AFTER_ATTEMPTS_S = 60
PING_INTERVAL_S = 30
PING_TIMEOUT_S = 45
OPEN_TIMEOUT_S = 10
MAX_FRAME_BYTES = 4 * 1024 * 1024


class CloudState(str, enum.Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RETRYING = "retrying"


class CloudLink:
    """@param token The session token to connect with; None waits for one."""

    def __init__(
        self,
        *,
        token: Callable[[], Awaitable[Optional[SessionToken]]],
        on_connected: Callable[[], Awaitable[None]],
        on_messages: Callable[[list[qc.QConnectMessage]], Awaitable[None]],
        on_disconnected: Callable[[], Any] = lambda: None,
        connect: Callable[..., Any] = ws_connect,
    ):
        self._token = token
        self._on_connected = on_connected
        self._on_messages = on_messages
        self._on_disconnected = on_disconnected
        self._connect = connect
        self._task: Optional[asyncio.Task] = None
        self._ws: Any = None
        self._wake = asyncio.Event()
        self._attempts = 0
        self._msg_id = 0
        self._batch_id = 0
        self.state = CloudState.IDLE
        self.last_error = ""

    def start(self) -> bool:
        """True when this started the connection, which then uses the current token."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="qobuz-connect-cloud")
            return True
        return False

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.state = CloudState.IDLE

    async def reconnect(self) -> None:
        """Drop the connection and connect again now, with the current token."""
        self._attempts = 0
        self._wake.set()
        ws = self._ws
        if ws is not None:
            await ws.close()

    def established(self) -> None:
        """The cloud confirmed a session on this connection."""
        self._attempts = 0
        self.last_error = ""

    async def send(self, messages: Iterable[qc.QConnectMessage]) -> bool:
        ws = self._ws
        if ws is None:
            return False
        self._batch_id += 1
        try:
            await ws.send(frames.payload(self._next_msg_id(), self._batch_id, messages))
        except WebSocketException:
            return False
        return True

    async def _run(self) -> None:
        while True:
            # A reconnect asked for from here on, even while the token is
            # fetched or the connection opens, starts this over at once.
            self._wake.clear()
            token = await self._token()
            if token is None:
                self.state = CloudState.IDLE
                await self._wake.wait()
                continue
            self.state = CloudState.CONNECTING
            try:
                await self._session(token)
            except asyncio.CancelledError:
                raise
            except (OSError, asyncio.TimeoutError, WebSocketException) as exc:
                self.last_error = type(exc).__name__
                logger.warning(
                    "Qobuz Connect cloud at %s: %s", endpoint_host(token.endpoint), self.last_error
                )
            finally:
                self._ws = None
                self._on_disconnected()
            await self._rest()

    async def _session(self, token: SessionToken) -> None:
        self._msg_id = 0
        async with self._connect(
            token.endpoint,
            open_timeout=OPEN_TIMEOUT_S,
            ping_interval=PING_INTERVAL_S,
            ping_timeout=PING_TIMEOUT_S,
            max_size=MAX_FRAME_BYTES,
            logger=_wire_logger,
        ) as ws:
            await ws.send(frames.authenticate(self._next_msg_id(), token.jwt))
            await ws.send(frames.subscribe(self._next_msg_id()))
            if self._wake.is_set():
                # Asked to reconnect while this opened: its token may be superseded.
                return
            self._ws = ws
            self.state = CloudState.CONNECTED
            logger.info(  # log-safe: an 8-hex SHA-256 prefix, not the token
                "Connected to the Qobuz Connect cloud at %s with session #%s",
                endpoint_host(token.endpoint),
                fingerprint(token.jwt),
            )
            await self._on_connected()
            async for data in ws:
                if isinstance(data, bytes) and not await self._frame(data):
                    return

    async def _frame(self, data: bytes) -> bool:
        """Handle one frame; False when the cloud asks to disconnect."""
        try:
            kind, body = frames.decode_frame(data)
            if kind == frames.PAYLOAD:
                messages = frames.messages_of(body)
            elif kind == frames.ERROR:
                error = qws.ErrorMessage.FromString(body)
                self.last_error = f"cloud error {error.code}: {error.descr}"
                logger.warning("Qobuz Connect %s", self.last_error)
                return True
            elif kind == frames.DISCONNECT:
                logger.info("Qobuz Connect cloud asked to disconnect")
                return False
            else:
                return True
        except (frames.FrameError, DecodeError) as exc:
            logger.warning("Qobuz Connect: unreadable frame (%s)", exc)
            return True
        try:
            await self._on_messages(messages)
        except Exception:
            logger.exception("Qobuz Connect: handling a cloud message failed")
        return True

    async def _rest(self) -> None:
        self._attempts += 1
        if self._attempts > MAX_ATTEMPTS:
            self._attempts = 0
            delay = REST_AFTER_ATTEMPTS_S
        else:
            delay = min(BACKOFF_START_S * 2 ** (self._attempts - 1), BACKOFF_MAX_S)
        self.state = CloudState.RETRYING
        # Not cleared here: a reconnect asked for during the attempt skips the wait.
        try:
            await asyncio.wait_for(self._wake.wait(), delay)
        except asyncio.TimeoutError:
            pass

    def _next_msg_id(self) -> int:
        self._msg_id += 1
        return self._msg_id
