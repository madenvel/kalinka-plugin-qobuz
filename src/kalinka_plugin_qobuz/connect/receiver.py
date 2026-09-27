"""The ``/streamcore`` HTTP endpoints the Qobuz app calls while pairing.

Unauthenticated by necessity: the app is an anonymous client on the LAN. The
listener therefore bounds every request in size and time, answers one request
per connection, and serves nothing but these three routes.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/pibuz/src/qconnect/pairing.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import asyncio
import contextlib
import json
import logging
from typing import Optional, Protocol

import h11

from .handoff import MAX_BODY_BYTES

logger = logging.getLogger(__name__.split(".")[-1])

DISPLAY_INFO = "/streamcore/get-display-info"
CONNECT_INFO = "/streamcore/get-connect-info"
HANDOFF = "/streamcore/connect-to-qconnect"

REQUEST_DEADLINE_S = 10.0
MAX_HEADER_BYTES = 16 * 1024
MAX_CONNECTIONS = 8
_READ_CHUNK = 16 * 1024


class ReceiverHandlers(Protocol):
    def display_info(self) -> dict: ...

    def connect_info(self) -> dict: ...

    async def handoff(self, body: bytes) -> tuple[int, dict]: ...


class _TooLarge(Exception):
    pass


class HandoffReceiver:
    """Serves the pairing endpoints on ``host:port`` until stopped."""

    def __init__(self, handlers: ReceiverHandlers, host: str = "0.0.0.0", port: int = 8183):
        self._handlers = handlers
        self._host = host
        self._port = port
        self._server: Optional[asyncio.AbstractServer] = None
        self._writers: set[asyncio.StreamWriter] = set()

    @property
    def port(self) -> int:
        """The bound port, which differs from the requested one when that was 0."""
        if self._server is None:
            return self._port
        return self._server.sockets[0].getsockname()[1]

    async def start(self) -> None:
        """@throw OSError when the port cannot be bound."""
        self._server = await asyncio.start_server(self._serve, self._host, self._port)
        logger.info("Qobuz Connect pairing endpoint listening on %s:%d", self._host, self.port)

    async def stop(self) -> None:
        server, self._server = self._server, None
        if server is None:
            return
        server.close()
        for writer in list(self._writers):
            writer.close()
        await server.wait_closed()
        logger.info("Qobuz Connect pairing endpoint closed")

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if len(self._writers) >= MAX_CONNECTIONS:
            writer.close()
            return
        self._writers.add(writer)
        peer = writer.get_extra_info("peername")
        try:
            connection = h11.Connection(h11.SERVER, max_incomplete_event_size=MAX_HEADER_BYTES)
            route = "-"
            try:
                route, status, payload = await asyncio.wait_for(
                    self._exchange(connection, reader), REQUEST_DEADLINE_S
                )
            except asyncio.TimeoutError:
                status, payload = 408, {"error": "request timeout"}
            except _TooLarge:
                status, payload = 413, {"error": "request too large"}
            except h11.RemoteProtocolError as exc:
                status, payload = exc.error_status_hint, {"error": "bad request"}
            except Exception as exc:
                logger.error("Qobuz Connect %s failed: %s", route, type(exc).__name__)
                status, payload = 500, {"error": "internal error"}
            if status is None:
                return
            logger.info("Qobuz Connect %s from %s -> %d", route, peer[0] if peer else "?", status)
            writer.write(_response(connection, status, payload))
            await writer.drain()
        except (ConnectionError, OSError, h11.LocalProtocolError):
            pass
        finally:
            self._writers.discard(writer)
            writer.close()
            with contextlib.suppress(ConnectionError, OSError):
                await writer.wait_closed()

    async def _exchange(self, connection: h11.Connection, reader: asyncio.StreamReader):
        request, body = await _read_request(connection, reader)
        if request is None:
            return "-", None, None
        method = request.method.decode("ascii", "replace")
        path = request.target.split(b"?", 1)[0].decode("ascii", "replace")
        route = f"{method} {path}"
        if (method, path) == ("GET", DISPLAY_INFO):
            return route, 200, self._handlers.display_info()
        if (method, path) == ("GET", CONNECT_INFO):
            return route, 200, self._handlers.connect_info()
        if (method, path) == ("POST", HANDOFF):
            status, payload = await self._handlers.handoff(body)
            return route, status, payload
        return route, 404, {"error": "not found"}


async def _read_request(connection: h11.Connection, reader: asyncio.StreamReader):
    request = None
    body = bytearray()
    while True:
        event = connection.next_event()
        if event is h11.NEED_DATA:
            connection.receive_data(await reader.read(_READ_CHUNK))
        elif isinstance(event, h11.Request):
            request = event
            if _content_length(event) > MAX_BODY_BYTES:
                raise _TooLarge()
        elif isinstance(event, h11.Data):
            body += event.data
            if len(body) > MAX_BODY_BYTES:
                raise _TooLarge()
        elif isinstance(event, h11.EndOfMessage):
            return request, bytes(body)
        elif isinstance(event, h11.ConnectionClosed):
            return None, b""


def _content_length(request: h11.Request) -> int:
    for name, value in request.headers:
        if name == b"content-length":
            return int(value)
    return 0


def _response(connection: h11.Connection, status: int, payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"connection", b"close"),
    ]
    return (
        connection.send(h11.Response(status_code=status, headers=headers))
        + connection.send(h11.Data(data=body))
        + connection.send(h11.EndOfMessage())
    )
