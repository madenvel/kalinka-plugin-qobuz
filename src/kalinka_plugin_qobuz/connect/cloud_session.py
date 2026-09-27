"""This player's part in a Qobuz Connect session: joining it, and what it hears.

On every connection it joins as a controller first — that is how the cloud
names the session — then, once the session is named, as a renderer. It learns
which renderer id is its own from the renderer list, by device uuid, and
passes renderer commands and queue changes on. Playback policy is elsewhere
(cloud_renderer); this is the protocol plumbing.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/pibuz/src/qconnect/session.rs and crates/qconnect-app/src/session.rs),
MIT License: Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Optional, Protocol

from . import frames
from .cloud_queue import CloudQueue
from .cloud_renderer import BUFFER_OK, LEVEL_MP3, PLAYING_STOPPED
from .proto import qconnect_pb2 as qc

logger = logging.getLogger(__name__.split(".")[-1])

JOIN_REASON_CONTROLLER_REQUEST = 1
JOIN_REASON_RECONNECTION = 2
# What Pibuz announces itself as; the cloud lists it among the speakers.
DEVICE_TYPE = 5
VOLUME_REMOTE_CONTROL_ALLOWED = 2


@dataclass(frozen=True)
class DeviceIdentity:
    """Who this player is to the cloud; the uuid matches the mDNS advert."""

    device_uuid: str
    friendly_name: str
    software_version: str
    max_audio_quality: int

    def message(self) -> qc.DeviceInfoMessage:
        return qc.DeviceInfoMessage(
            device_uuid=frames.uuid_bytes(self.device_uuid),
            friendly_name=self.friendly_name,
            brand="Kalinka",
            model="Kalinka",
            device_type=DEVICE_TYPE,
            capabilities=qc.DeviceCapabilitiesMessage(
                min_audio_quality=LEVEL_MP3,
                max_audio_quality=self.max_audio_quality,
                volume_remote_control=VOLUME_REMOTE_CONTROL_ALLOWED,
            ),
            software_version=self.software_version,
        )


class Playback(Protocol):
    """The playback policy the session hands renderer traffic to."""

    @property
    def active(self) -> bool: ...

    async def on_joined(self) -> None:
        """Joined as a renderer: report state, volume and quality."""
        ...

    async def on_set_state(self, message: qc.RendererSetStateMessage) -> None: ...

    async def on_set_volume(self, message: qc.RendererSetVolumeMessage) -> None: ...

    async def on_set_max_quality(self, level: int) -> None: ...

    async def on_mute(self, muted: bool) -> None: ...

    async def on_loop_mode(self, mode: int) -> None: ...

    async def on_set_active(self, active: bool) -> None: ...

    async def on_active_renderer(self, ours: bool) -> None:
        """The session named its active renderer: this player, or another."""
        ...

    async def on_shown_volume(self, percent: int) -> None:
        """The volume the Qobuz app shows for this player."""
        ...


class ConnectSession:
    """@param send Sends messages on the live connection; False when there is none."""

    def __init__(
        self,
        identity: DeviceIdentity,
        queue: CloudQueue,
        send: Callable[[Iterable[qc.QConnectMessage]], Awaitable[bool]],
        on_established: Callable[[], None],
    ):
        self._identity = identity
        self._queue = queue
        self._send = send
        self._on_established = on_established
        self._playback: Optional[Playback] = None
        self.session_uuid = ""
        self.renderer_id: Optional[int] = None
        self._joined_session = ""
        self._join_active_next = False
        self._was_joined = False

    def attach(self, playback: Playback) -> None:
        self._playback = playback

    def join_as_active_next(self) -> None:
        """The next renderer join claims playback: the user just chose this player."""
        self._join_active_next = True

    async def on_connected(self) -> None:
        self._was_joined = bool(self._joined_session)
        self._joined_session = ""
        await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.CTRL_SRVR_JOIN_SESSION,
                    ctrl_srvr_join_session=qc.JoinSessionMessage(
                        device_info=self._identity.message()
                    ),
                ),
                self._ask_for_queue(),
            ]
        )

    async def on_messages(self, messages: list[qc.QConnectMessage]) -> None:
        for message in messages:
            await self._dispatch(message)

    async def send_state(self, state: qc.RendererStateMessage) -> bool:
        return await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_STATE_UPDATED,
                    rndr_srvr_state_updated=qc.RendererStateUpdatedMessage(state=state),
                )
            ]
        )

    async def send_volume(self, percent: int) -> bool:
        return await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_VOLUME_CHANGED,
                    rndr_srvr_volume_changed=qc.RendererVolumeChangedMessage(volume=percent),
                )
            ]
        )

    async def send_muted(self, muted: bool) -> bool:
        return await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_VOLUME_MUTED,
                    rndr_srvr_volume_muted=qc.RendererVolumeMutedMessage(value=muted),
                )
            ]
        )

    async def send_max_quality(self, level: int) -> bool:
        return await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_MAX_AUDIO_QUALITY_CHANGED,
                    rndr_srvr_max_audio_quality_changed=qc.RendererMaxAudioQualityChangedMessage(
                        max_audio_quality=level
                    ),
                )
            ]
        )

    async def send_file_quality(self, quality: qc.RendererFileAudioQualityChangedMessage) -> bool:
        return await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_FILE_AUDIO_QUALITY_CHANGED,
                    rndr_srvr_file_audio_quality_changed=quality,
                )
            ]
        )

    async def send_device_quality(
        self, quality: qc.RendererDeviceAudioQualityChangedMessage
    ) -> bool:
        return await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_DEVICE_AUDIO_QUALITY_CHANGED,
                    rndr_srvr_device_audio_quality_changed=quality,
                )
            ]
        )

    async def ask_for_queue(self) -> bool:
        return await self._send([self._ask_for_queue()])

    async def _dispatch(self, message: qc.QConnectMessage) -> None:
        kind = message.message_type
        playback = self._playback
        if kind == qc.SRVR_CTRL_SESSION_STATE:
            await self._on_session_state(message.srvr_ctrl_session_state)
        elif kind in (qc.SRVR_CTRL_ADD_RENDERER, qc.SRVR_CTRL_UPDATE_RENDERER):
            body = (
                message.srvr_ctrl_add_renderer
                if kind == qc.SRVR_CTRL_ADD_RENDERER
                else message.srvr_ctrl_update_renderer
            )
            self._consider_renderer(body.renderer_id, body.device_info)
        elif kind == qc.SRVR_CTRL_REMOVE_RENDERER:
            if message.srvr_ctrl_remove_renderer.renderer_id == self.renderer_id:
                self.renderer_id = None
        elif kind == qc.SRVR_CTRL_ACTIVE_RENDERER_CHANGED:
            await self._on_active_renderer(
                message.srvr_ctrl_active_renderer_changed.active_renderer_id
            )
        elif playback is None:
            return
        elif kind == qc.SRVR_RNDR_SET_STATE:
            await playback.on_set_state(message.srvr_rndr_set_state)
        elif kind == qc.SRVR_RNDR_SET_VOLUME:
            await playback.on_set_volume(message.srvr_rndr_set_volume)
        elif kind == qc.SRVR_RNDR_SET_ACTIVE:
            # Absent is "pending", sent ahead of the real answer on a takeover.
            if message.srvr_rndr_set_active.HasField("active"):
                await playback.on_set_active(message.srvr_rndr_set_active.active)
        elif kind == qc.SRVR_RNDR_SET_MAX_AUDIO_QUALITY:
            body = message.srvr_rndr_set_max_audio_quality
            # Absent would read as 0, which clamps to MP3.
            if body.HasField("max_audio_quality"):
                await playback.on_set_max_quality(body.max_audio_quality)
        elif kind == qc.SRVR_CTRL_VOLUME_CHANGED:
            body = message.srvr_ctrl_volume_changed
            if body.renderer_id == self.renderer_id and body.HasField("volume"):
                await playback.on_shown_volume(body.volume)
        elif kind == qc.SRVR_RNDR_SET_LOOP_MODE:
            await playback.on_loop_mode(message.srvr_rndr_set_loop_mode.loop_mode)
        elif kind == qc.SRVR_RNDR_MUTE_VOLUME:
            await playback.on_mute(message.srvr_rndr_mute_volume.value)
        elif kind == qc.SRVR_CTRL_QUEUE_ERROR_MESSAGE:
            error = message.srvr_ctrl_queue_error_message.error
            logger.warning("Qobuz Connect queue error: %s", error.code or "unknown")
        elif self._queue.apply(message):
            await self.ask_for_queue()

    async def _on_session_state(self, body: qc.CtrlSessionStateMessage) -> None:
        session_uuid = frames.uuid_text(body.session_uuid)
        if session_uuid and session_uuid != self._joined_session:
            if session_uuid != self.session_uuid:
                # Renderer ids are the session's own: the last one's may be
                # another device's here.
                self.renderer_id = None
            self.session_uuid = session_uuid
            self._on_established()
            await self._join_as_renderer()
        if body.HasField("active_renderer_id"):
            await self._on_active_renderer(body.active_renderer_id)

    async def _join_as_renderer(self) -> None:
        playback = self._playback
        handed_over, self._join_active_next = self._join_active_next, False
        # A handoff is a new join even on a connection that was up before.
        reconnecting = self._was_joined and not handed_over
        is_active = handed_over or (
            reconnecting and playback is not None and playback.active
        )
        version = self._queue.version
        joined = await self._send(
            [
                qc.QConnectMessage(
                    message_type=qc.RNDR_SRVR_JOIN_SESSION,
                    rndr_srvr_join_session=qc.JoinSessionMessage(
                        session_uuid=frames.uuid_bytes(self.session_uuid),
                        device_info=self._identity.message(),
                        reason=(
                            JOIN_REASON_RECONNECTION
                            if reconnecting
                            else JOIN_REASON_CONTROLLER_REQUEST
                        ),
                        initial_state=qc.RendererStateMessage(
                            playing_state=PLAYING_STOPPED,
                            buffer_state=BUFFER_OK,
                            current_position=qc.PlaybackPositionMessage(
                                timestamp=frames.now_ms(), value=0
                            ),
                            duration=0,
                            queue_version=qc.QueueVersionRef(major=version[0], minor=version[1]),
                        ),
                        is_active=is_active,
                    ),
                )
            ]
        )
        if not joined:
            return
        self._joined_session = self.session_uuid
        logger.info(
            "Joined Qobuz Connect session %s… as %s renderer",
            self.session_uuid[:8],
            "the active" if is_active else "an available",
        )
        if is_active and playback is not None:
            await playback.on_set_active(True)
        if playback is not None:
            await playback.on_joined()
        await self.ask_for_queue()
        if self.renderer_id is not None:
            await self._send(
                [
                    qc.QConnectMessage(
                        message_type=qc.CTRL_SRVR_ASK_FOR_RENDERER_STATE,
                        ctrl_srvr_ask_for_renderer_state=qc.AskForRendererStateMessage(
                            renderer_id=self.renderer_id
                        ),
                    )
                ]
            )

    def _consider_renderer(self, renderer_id: int, info: qc.DeviceInfoMessage) -> None:
        mine = self._identity
        if info.HasField("device_uuid"):
            ours = frames.uuid_text(info.device_uuid) == mine.device_uuid
        else:
            ours = info.friendly_name == mine.friendly_name and info.brand == "Kalinka"
        if ours and self.renderer_id != renderer_id:
            self.renderer_id = renderer_id
            logger.info("Qobuz Connect lists this player as renderer %d", renderer_id)

    async def _on_active_renderer(self, active_renderer_id: int) -> None:
        playback = self._playback
        if playback is None or self.renderer_id is None or active_renderer_id < 0:
            return
        await playback.on_active_renderer(active_renderer_id == self.renderer_id)

    def _ask_for_queue(self) -> qc.QConnectMessage:
        version = self._queue.version
        return qc.QConnectMessage(
            message_type=qc.CTRL_SRVR_ASK_FOR_QUEUE_STATE,
            ctrl_srvr_ask_for_queue_state=qc.AskForQueueStateMessage(
                queue_version_ref=qc.QueueVersionRef(major=version[0], minor=version[1]),
                action_uuid=uuid.uuid4().bytes,
            ),
        )
