"""A Qobuz Connect cloud on loopback, speaking the real frames.

It records every token it is authenticated with and every message it hears,
and answers joins the way the real cloud does: a controller join is told the
session, a renderer join is listed and, when it claims playback, made active.
"""

import asyncio
import uuid
from typing import Optional

from websockets.asyncio.server import serve

from kalinka_plugin_qobuz.connect import frames
from kalinka_plugin_qobuz.connect.proto import qconnect_pb2 as qc
from kalinka_plugin_qobuz.connect.proto import qws_pb2 as qws

SESSION_UUID = "0b0e7c9a-1111-4222-8333-944455556666"
RENDERER_ID = 7


class FakeCloud:
    def __init__(self, *, answer_joins: bool = True):
        self.answer_joins = answer_joins
        self.tokens: list[str] = []
        self.channels: list[list[bytes]] = []
        self.received: list[qc.QConnectMessage] = []
        self.refuse_token: Optional[str] = None
        self._clients: list = []
        self._server = None
        self.port = 0

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws"

    async def start(self) -> "FakeCloud":
        self._server = await serve(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def kinds(self) -> list[int]:
        return [m.message_type for m in self.received]

    def states(self) -> list[qc.RendererStateMessage]:
        return [
            m.rndr_srvr_state_updated.state
            for m in self.received
            if m.message_type == qc.RNDR_SRVR_STATE_UPDATED
        ]

    async def push(self, *messages: qc.QConnectMessage) -> None:
        await self._clients[-1].send(frames.payload(1, 1, messages))

    async def drop(self) -> None:
        await self._clients[-1].close()

    async def until(self, condition, timeout: float = 3.0) -> None:
        async def poll():
            while not condition():
                await asyncio.sleep(0.01)

        await asyncio.wait_for(poll(), timeout)

    async def _handle(self, ws) -> None:
        self._clients.append(ws)
        async for data in ws:
            kind, body = frames.decode_frame(data)
            if kind == frames.AUTHENTICATE:
                jwt = qws.Authenticate.FromString(body).jwt
                self.tokens.append(jwt)
                if jwt == self.refuse_token:
                    error = qws.ErrorMessage(code=401, descr="expired JWT")
                    await ws.send(frames.encode_frame(frames.ERROR, error.SerializeToString()))
                    await ws.close()
                    return
            elif kind == frames.SUBSCRIBE:
                self.channels.append(list(qws.Subscribe.FromString(body).channels))
            elif kind == frames.PAYLOAD:
                for message in frames.messages_of(body):
                    self.received.append(message)
                    if self.answer_joins:
                        await self._answer(ws, message)

    async def _answer(self, ws, message: qc.QConnectMessage) -> None:
        if message.message_type == qc.CTRL_SRVR_JOIN_SESSION:
            state = qc.CtrlSessionStateMessage(
                session_uuid=uuid.UUID(SESSION_UUID).bytes, active_renderer_id=-1
            )
            await ws.send(
                frames.payload(
                    1,
                    1,
                    [qc.QConnectMessage(message_type=qc.SRVR_CTRL_SESSION_STATE, srvr_ctrl_session_state=state)],
                )
            )
        elif message.message_type == qc.RNDR_SRVR_JOIN_SESSION:
            join = message.rndr_srvr_join_session
            replies = [
                qc.QConnectMessage(
                    message_type=qc.SRVR_CTRL_ADD_RENDERER,
                    srvr_ctrl_add_renderer=qc.CtrlAddRendererMessage(
                        renderer_id=RENDERER_ID, device_info=join.device_info
                    ),
                )
            ]
            if join.is_active:
                replies.append(
                    qc.QConnectMessage(
                        message_type=qc.SRVR_CTRL_ACTIVE_RENDERER_CHANGED,
                        srvr_ctrl_active_renderer_changed=qc.CtrlActiveRendererChangedMessage(
                            active_renderer_id=RENDERER_ID
                        ),
                    )
                )
            await ws.send(frames.payload(1, 1, replies))
