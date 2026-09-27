from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MESSAGE_TYPE_UNKNOWN: _ClassVar[MessageType]
    RNDR_SRVR_JOIN_SESSION: _ClassVar[MessageType]
    RNDR_SRVR_STATE_UPDATED: _ClassVar[MessageType]
    RNDR_SRVR_VOLUME_CHANGED: _ClassVar[MessageType]
    RNDR_SRVR_FILE_AUDIO_QUALITY_CHANGED: _ClassVar[MessageType]
    RNDR_SRVR_DEVICE_AUDIO_QUALITY_CHANGED: _ClassVar[MessageType]
    RNDR_SRVR_MAX_AUDIO_QUALITY_CHANGED: _ClassVar[MessageType]
    RNDR_SRVR_VOLUME_MUTED: _ClassVar[MessageType]
    SRVR_RNDR_SET_STATE: _ClassVar[MessageType]
    SRVR_RNDR_SET_VOLUME: _ClassVar[MessageType]
    SRVR_RNDR_SET_ACTIVE: _ClassVar[MessageType]
    SRVR_RNDR_SET_MAX_AUDIO_QUALITY: _ClassVar[MessageType]
    SRVR_RNDR_SET_LOOP_MODE: _ClassVar[MessageType]
    SRVR_RNDR_SET_SHUFFLE_MODE: _ClassVar[MessageType]
    SRVR_RNDR_MUTE_VOLUME: _ClassVar[MessageType]
    CTRL_SRVR_JOIN_SESSION: _ClassVar[MessageType]
    CTRL_SRVR_ASK_FOR_QUEUE_STATE: _ClassVar[MessageType]
    CTRL_SRVR_ASK_FOR_RENDERER_STATE: _ClassVar[MessageType]
    SRVR_CTRL_SESSION_STATE: _ClassVar[MessageType]
    SRVR_CTRL_RENDERER_STATE_UPDATED: _ClassVar[MessageType]
    SRVR_CTRL_ADD_RENDERER: _ClassVar[MessageType]
    SRVR_CTRL_UPDATE_RENDERER: _ClassVar[MessageType]
    SRVR_CTRL_REMOVE_RENDERER: _ClassVar[MessageType]
    SRVR_CTRL_ACTIVE_RENDERER_CHANGED: _ClassVar[MessageType]
    SRVR_CTRL_VOLUME_CHANGED: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_ERROR_MESSAGE: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_CLEARED: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_STATE: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_TRACKS_LOADED: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_TRACKS_INSERTED: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_TRACKS_ADDED: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_TRACKS_REMOVED: _ClassVar[MessageType]
    SRVR_CTRL_QUEUE_TRACKS_REORDERED: _ClassVar[MessageType]
    SRVR_CTRL_SHUFFLE_MODE_SET: _ClassVar[MessageType]
MESSAGE_TYPE_UNKNOWN: MessageType
RNDR_SRVR_JOIN_SESSION: MessageType
RNDR_SRVR_STATE_UPDATED: MessageType
RNDR_SRVR_VOLUME_CHANGED: MessageType
RNDR_SRVR_FILE_AUDIO_QUALITY_CHANGED: MessageType
RNDR_SRVR_DEVICE_AUDIO_QUALITY_CHANGED: MessageType
RNDR_SRVR_MAX_AUDIO_QUALITY_CHANGED: MessageType
RNDR_SRVR_VOLUME_MUTED: MessageType
SRVR_RNDR_SET_STATE: MessageType
SRVR_RNDR_SET_VOLUME: MessageType
SRVR_RNDR_SET_ACTIVE: MessageType
SRVR_RNDR_SET_MAX_AUDIO_QUALITY: MessageType
SRVR_RNDR_SET_LOOP_MODE: MessageType
SRVR_RNDR_SET_SHUFFLE_MODE: MessageType
SRVR_RNDR_MUTE_VOLUME: MessageType
CTRL_SRVR_JOIN_SESSION: MessageType
CTRL_SRVR_ASK_FOR_QUEUE_STATE: MessageType
CTRL_SRVR_ASK_FOR_RENDERER_STATE: MessageType
SRVR_CTRL_SESSION_STATE: MessageType
SRVR_CTRL_RENDERER_STATE_UPDATED: MessageType
SRVR_CTRL_ADD_RENDERER: MessageType
SRVR_CTRL_UPDATE_RENDERER: MessageType
SRVR_CTRL_REMOVE_RENDERER: MessageType
SRVR_CTRL_ACTIVE_RENDERER_CHANGED: MessageType
SRVR_CTRL_VOLUME_CHANGED: MessageType
SRVR_CTRL_QUEUE_ERROR_MESSAGE: MessageType
SRVR_CTRL_QUEUE_CLEARED: MessageType
SRVR_CTRL_QUEUE_STATE: MessageType
SRVR_CTRL_QUEUE_TRACKS_LOADED: MessageType
SRVR_CTRL_QUEUE_TRACKS_INSERTED: MessageType
SRVR_CTRL_QUEUE_TRACKS_ADDED: MessageType
SRVR_CTRL_QUEUE_TRACKS_REMOVED: MessageType
SRVR_CTRL_QUEUE_TRACKS_REORDERED: MessageType
SRVR_CTRL_SHUFFLE_MODE_SET: MessageType

class QueueVersionRef(_message.Message):
    __slots__ = ("major", "minor")
    MAJOR_FIELD_NUMBER: _ClassVar[int]
    MINOR_FIELD_NUMBER: _ClassVar[int]
    major: int
    minor: int
    def __init__(self, major: _Optional[int] = ..., minor: _Optional[int] = ...) -> None: ...

class ErrorMessage(_message.Message):
    __slots__ = ("code", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class QueueTrack(_message.Message):
    __slots__ = ("queue_item_id", "track_id")
    QUEUE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    queue_item_id: int
    track_id: int
    def __init__(self, queue_item_id: _Optional[int] = ..., track_id: _Optional[int] = ...) -> None: ...

class QueueTrackWithContext(_message.Message):
    __slots__ = ("queue_item_id", "track_id", "context_uuid")
    QUEUE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_UUID_FIELD_NUMBER: _ClassVar[int]
    queue_item_id: int
    track_id: int
    context_uuid: bytes
    def __init__(self, queue_item_id: _Optional[int] = ..., track_id: _Optional[int] = ..., context_uuid: _Optional[bytes] = ...) -> None: ...

class DeviceCapabilitiesMessage(_message.Message):
    __slots__ = ("min_audio_quality", "max_audio_quality", "volume_remote_control")
    MIN_AUDIO_QUALITY_FIELD_NUMBER: _ClassVar[int]
    MAX_AUDIO_QUALITY_FIELD_NUMBER: _ClassVar[int]
    VOLUME_REMOTE_CONTROL_FIELD_NUMBER: _ClassVar[int]
    min_audio_quality: int
    max_audio_quality: int
    volume_remote_control: int
    def __init__(self, min_audio_quality: _Optional[int] = ..., max_audio_quality: _Optional[int] = ..., volume_remote_control: _Optional[int] = ...) -> None: ...

class DeviceInfoMessage(_message.Message):
    __slots__ = ("device_uuid", "friendly_name", "brand", "model", "serial_number", "device_type", "capabilities", "software_version")
    DEVICE_UUID_FIELD_NUMBER: _ClassVar[int]
    FRIENDLY_NAME_FIELD_NUMBER: _ClassVar[int]
    BRAND_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    SERIAL_NUMBER_FIELD_NUMBER: _ClassVar[int]
    DEVICE_TYPE_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    SOFTWARE_VERSION_FIELD_NUMBER: _ClassVar[int]
    device_uuid: bytes
    friendly_name: str
    brand: str
    model: str
    serial_number: str
    device_type: int
    capabilities: DeviceCapabilitiesMessage
    software_version: str
    def __init__(self, device_uuid: _Optional[bytes] = ..., friendly_name: _Optional[str] = ..., brand: _Optional[str] = ..., model: _Optional[str] = ..., serial_number: _Optional[str] = ..., device_type: _Optional[int] = ..., capabilities: _Optional[_Union[DeviceCapabilitiesMessage, _Mapping]] = ..., software_version: _Optional[str] = ...) -> None: ...

class PlaybackPositionMessage(_message.Message):
    __slots__ = ("timestamp", "value")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    value: int
    def __init__(self, timestamp: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...

class RendererStateMessage(_message.Message):
    __slots__ = ("playing_state", "buffer_state", "current_position", "duration", "queue_version", "current_queue_item_id", "next_queue_item_id")
    PLAYING_STATE_FIELD_NUMBER: _ClassVar[int]
    BUFFER_STATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_POSITION_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CURRENT_QUEUE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    NEXT_QUEUE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    playing_state: int
    buffer_state: int
    current_position: PlaybackPositionMessage
    duration: int
    queue_version: QueueVersionRef
    current_queue_item_id: int
    next_queue_item_id: int
    def __init__(self, playing_state: _Optional[int] = ..., buffer_state: _Optional[int] = ..., current_position: _Optional[_Union[PlaybackPositionMessage, _Mapping]] = ..., duration: _Optional[int] = ..., queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., current_queue_item_id: _Optional[int] = ..., next_queue_item_id: _Optional[int] = ...) -> None: ...

class JoinSessionMessage(_message.Message):
    __slots__ = ("session_uuid", "device_info", "reason", "initial_state", "is_active")
    SESSION_UUID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_INFO_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    INITIAL_STATE_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    session_uuid: bytes
    device_info: DeviceInfoMessage
    reason: int
    initial_state: RendererStateMessage
    is_active: bool
    def __init__(self, session_uuid: _Optional[bytes] = ..., device_info: _Optional[_Union[DeviceInfoMessage, _Mapping]] = ..., reason: _Optional[int] = ..., initial_state: _Optional[_Union[RendererStateMessage, _Mapping]] = ..., is_active: _Optional[bool] = ...) -> None: ...

class RendererStateUpdatedMessage(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: RendererStateMessage
    def __init__(self, state: _Optional[_Union[RendererStateMessage, _Mapping]] = ...) -> None: ...

class RendererVolumeChangedMessage(_message.Message):
    __slots__ = ("volume",)
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    volume: int
    def __init__(self, volume: _Optional[int] = ...) -> None: ...

class RendererFileAudioQualityChangedMessage(_message.Message):
    __slots__ = ("sampling_rate", "bit_depth", "nb_channels", "audio_quality")
    SAMPLING_RATE_FIELD_NUMBER: _ClassVar[int]
    BIT_DEPTH_FIELD_NUMBER: _ClassVar[int]
    NB_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    AUDIO_QUALITY_FIELD_NUMBER: _ClassVar[int]
    sampling_rate: int
    bit_depth: int
    nb_channels: int
    audio_quality: int
    def __init__(self, sampling_rate: _Optional[int] = ..., bit_depth: _Optional[int] = ..., nb_channels: _Optional[int] = ..., audio_quality: _Optional[int] = ...) -> None: ...

class RendererDeviceAudioQualityChangedMessage(_message.Message):
    __slots__ = ("sampling_rate", "bit_depth", "nb_channels")
    SAMPLING_RATE_FIELD_NUMBER: _ClassVar[int]
    BIT_DEPTH_FIELD_NUMBER: _ClassVar[int]
    NB_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    sampling_rate: int
    bit_depth: int
    nb_channels: int
    def __init__(self, sampling_rate: _Optional[int] = ..., bit_depth: _Optional[int] = ..., nb_channels: _Optional[int] = ...) -> None: ...

class RendererVolumeMutedMessage(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: bool
    def __init__(self, value: _Optional[bool] = ...) -> None: ...

class RendererMaxAudioQualityChangedMessage(_message.Message):
    __slots__ = ("max_audio_quality", "network_type")
    MAX_AUDIO_QUALITY_FIELD_NUMBER: _ClassVar[int]
    NETWORK_TYPE_FIELD_NUMBER: _ClassVar[int]
    max_audio_quality: int
    network_type: int
    def __init__(self, max_audio_quality: _Optional[int] = ..., network_type: _Optional[int] = ...) -> None: ...

class RendererSetStateMessage(_message.Message):
    __slots__ = ("playing_state", "current_position", "queue_version", "current_track", "next_track")
    PLAYING_STATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_POSITION_FIELD_NUMBER: _ClassVar[int]
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CURRENT_TRACK_FIELD_NUMBER: _ClassVar[int]
    NEXT_TRACK_FIELD_NUMBER: _ClassVar[int]
    playing_state: int
    current_position: int
    queue_version: QueueVersionRef
    current_track: QueueTrackWithContext
    next_track: QueueTrackWithContext
    def __init__(self, playing_state: _Optional[int] = ..., current_position: _Optional[int] = ..., queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., current_track: _Optional[_Union[QueueTrackWithContext, _Mapping]] = ..., next_track: _Optional[_Union[QueueTrackWithContext, _Mapping]] = ...) -> None: ...

class RendererSetVolumeMessage(_message.Message):
    __slots__ = ("volume", "volume_delta")
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    VOLUME_DELTA_FIELD_NUMBER: _ClassVar[int]
    volume: int
    volume_delta: int
    def __init__(self, volume: _Optional[int] = ..., volume_delta: _Optional[int] = ...) -> None: ...

class RendererSetActiveMessage(_message.Message):
    __slots__ = ("active",)
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    active: bool
    def __init__(self, active: _Optional[bool] = ...) -> None: ...

class RendererSetMaxAudioQualityMessage(_message.Message):
    __slots__ = ("max_audio_quality",)
    MAX_AUDIO_QUALITY_FIELD_NUMBER: _ClassVar[int]
    max_audio_quality: int
    def __init__(self, max_audio_quality: _Optional[int] = ...) -> None: ...

class RendererSetLoopModeMessage(_message.Message):
    __slots__ = ("loop_mode",)
    LOOP_MODE_FIELD_NUMBER: _ClassVar[int]
    loop_mode: int
    def __init__(self, loop_mode: _Optional[int] = ...) -> None: ...

class RendererSetShuffleModeMessage(_message.Message):
    __slots__ = ("shuffle_mode",)
    SHUFFLE_MODE_FIELD_NUMBER: _ClassVar[int]
    shuffle_mode: bool
    def __init__(self, shuffle_mode: _Optional[bool] = ...) -> None: ...

class RendererMuteVolumeMessage(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: bool
    def __init__(self, value: _Optional[bool] = ...) -> None: ...

class AskForQueueStateMessage(_message.Message):
    __slots__ = ("queue_version_ref", "action_uuid")
    QUEUE_VERSION_REF_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    queue_version_ref: QueueVersionRef
    action_uuid: bytes
    def __init__(self, queue_version_ref: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ...) -> None: ...

class AskForRendererStateMessage(_message.Message):
    __slots__ = ("renderer_id",)
    RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    renderer_id: int
    def __init__(self, renderer_id: _Optional[int] = ...) -> None: ...

class CtrlSessionStateMessage(_message.Message):
    __slots__ = ("session_uuid", "active_renderer_id", "queue_version", "playing_state", "loop_mode")
    SESSION_UUID_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    PLAYING_STATE_FIELD_NUMBER: _ClassVar[int]
    LOOP_MODE_FIELD_NUMBER: _ClassVar[int]
    session_uuid: bytes
    active_renderer_id: int
    queue_version: QueueVersionRef
    playing_state: int
    loop_mode: int
    def __init__(self, session_uuid: _Optional[bytes] = ..., active_renderer_id: _Optional[int] = ..., queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., playing_state: _Optional[int] = ..., loop_mode: _Optional[int] = ...) -> None: ...

class CtrlAddRendererMessage(_message.Message):
    __slots__ = ("renderer_id", "device_info")
    RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_INFO_FIELD_NUMBER: _ClassVar[int]
    renderer_id: int
    device_info: DeviceInfoMessage
    def __init__(self, renderer_id: _Optional[int] = ..., device_info: _Optional[_Union[DeviceInfoMessage, _Mapping]] = ...) -> None: ...

class CtrlUpdateRendererMessage(_message.Message):
    __slots__ = ("renderer_id", "device_info")
    RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_INFO_FIELD_NUMBER: _ClassVar[int]
    renderer_id: int
    device_info: DeviceInfoMessage
    def __init__(self, renderer_id: _Optional[int] = ..., device_info: _Optional[_Union[DeviceInfoMessage, _Mapping]] = ...) -> None: ...

class CtrlRemoveRendererMessage(_message.Message):
    __slots__ = ("renderer_id",)
    RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    renderer_id: int
    def __init__(self, renderer_id: _Optional[int] = ...) -> None: ...

class CtrlActiveRendererChangedMessage(_message.Message):
    __slots__ = ("active_renderer_id",)
    ACTIVE_RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    active_renderer_id: int
    def __init__(self, active_renderer_id: _Optional[int] = ...) -> None: ...

class CtrlVolumeChangedMessage(_message.Message):
    __slots__ = ("renderer_id", "volume")
    RENDERER_ID_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    renderer_id: int
    volume: int
    def __init__(self, renderer_id: _Optional[int] = ..., volume: _Optional[int] = ...) -> None: ...

class QueueErrorMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "error")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    error: ErrorMessage
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., error: _Optional[_Union[ErrorMessage, _Mapping]] = ...) -> None: ...

class QueueClearedMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ...) -> None: ...

class QueueStateMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "tracks", "shuffle_mode", "shuffled_track_indexes", "autoplay_mode", "autoplay_loading", "autoplay_tracks", "queue_hash")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    TRACKS_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_MODE_FIELD_NUMBER: _ClassVar[int]
    SHUFFLED_TRACK_INDEXES_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_MODE_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_LOADING_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_TRACKS_FIELD_NUMBER: _ClassVar[int]
    QUEUE_HASH_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    tracks: _containers.RepeatedCompositeFieldContainer[QueueTrackWithContext]
    shuffle_mode: bool
    shuffled_track_indexes: _containers.RepeatedScalarFieldContainer[int]
    autoplay_mode: bool
    autoplay_loading: bool
    autoplay_tracks: _containers.RepeatedCompositeFieldContainer[QueueTrackWithContext]
    queue_hash: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., tracks: _Optional[_Iterable[_Union[QueueTrackWithContext, _Mapping]]] = ..., shuffle_mode: _Optional[bool] = ..., shuffled_track_indexes: _Optional[_Iterable[int]] = ..., autoplay_mode: _Optional[bool] = ..., autoplay_loading: _Optional[bool] = ..., autoplay_tracks: _Optional[_Iterable[_Union[QueueTrackWithContext, _Mapping]]] = ..., queue_hash: _Optional[bytes] = ...) -> None: ...

class QueueTracksLoadedMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "tracks", "queue_position", "shuffle_seed", "shuffle_pivot_queue_item_id", "shuffle_mode", "context_uuid", "autoplay_reset", "autoplay_loading", "queue_hash")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    TRACKS_FIELD_NUMBER: _ClassVar[int]
    QUEUE_POSITION_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_SEED_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_PIVOT_QUEUE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_MODE_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_UUID_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_RESET_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_LOADING_FIELD_NUMBER: _ClassVar[int]
    QUEUE_HASH_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    tracks: _containers.RepeatedCompositeFieldContainer[QueueTrack]
    queue_position: int
    shuffle_seed: int
    shuffle_pivot_queue_item_id: int
    shuffle_mode: bool
    context_uuid: bytes
    autoplay_reset: bool
    autoplay_loading: bool
    queue_hash: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., tracks: _Optional[_Iterable[_Union[QueueTrack, _Mapping]]] = ..., queue_position: _Optional[int] = ..., shuffle_seed: _Optional[int] = ..., shuffle_pivot_queue_item_id: _Optional[int] = ..., shuffle_mode: _Optional[bool] = ..., context_uuid: _Optional[bytes] = ..., autoplay_reset: _Optional[bool] = ..., autoplay_loading: _Optional[bool] = ..., queue_hash: _Optional[bytes] = ...) -> None: ...

class QueueTracksInsertedMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "tracks", "insert_after", "shuffle_seed", "context_uuid", "autoplay_reset", "autoplay_loading", "queue_hash")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    TRACKS_FIELD_NUMBER: _ClassVar[int]
    INSERT_AFTER_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_SEED_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_UUID_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_RESET_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_LOADING_FIELD_NUMBER: _ClassVar[int]
    QUEUE_HASH_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    tracks: _containers.RepeatedCompositeFieldContainer[QueueTrack]
    insert_after: int
    shuffle_seed: int
    context_uuid: bytes
    autoplay_reset: bool
    autoplay_loading: bool
    queue_hash: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., tracks: _Optional[_Iterable[_Union[QueueTrack, _Mapping]]] = ..., insert_after: _Optional[int] = ..., shuffle_seed: _Optional[int] = ..., context_uuid: _Optional[bytes] = ..., autoplay_reset: _Optional[bool] = ..., autoplay_loading: _Optional[bool] = ..., queue_hash: _Optional[bytes] = ...) -> None: ...

class QueueTracksAddedMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "tracks", "shuffle_seed", "context_uuid", "autoplay_reset", "autoplay_loading", "queue_hash")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    TRACKS_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_SEED_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_UUID_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_RESET_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_LOADING_FIELD_NUMBER: _ClassVar[int]
    QUEUE_HASH_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    tracks: _containers.RepeatedCompositeFieldContainer[QueueTrack]
    shuffle_seed: int
    context_uuid: bytes
    autoplay_reset: bool
    autoplay_loading: bool
    queue_hash: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., tracks: _Optional[_Iterable[_Union[QueueTrack, _Mapping]]] = ..., shuffle_seed: _Optional[int] = ..., context_uuid: _Optional[bytes] = ..., autoplay_reset: _Optional[bool] = ..., autoplay_loading: _Optional[bool] = ..., queue_hash: _Optional[bytes] = ...) -> None: ...

class QueueTracksRemovedMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "queue_item_ids", "autoplay_reset", "autoplay_loading", "queue_hash")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    QUEUE_ITEM_IDS_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_RESET_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_LOADING_FIELD_NUMBER: _ClassVar[int]
    QUEUE_HASH_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    queue_item_ids: _containers.RepeatedScalarFieldContainer[int]
    autoplay_reset: bool
    autoplay_loading: bool
    queue_hash: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., queue_item_ids: _Optional[_Iterable[int]] = ..., autoplay_reset: _Optional[bool] = ..., autoplay_loading: _Optional[bool] = ..., queue_hash: _Optional[bytes] = ...) -> None: ...

class QueueTracksReorderedMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "queue_item_ids", "insert_after", "autoplay_reset", "autoplay_loading", "queue_hash")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    QUEUE_ITEM_IDS_FIELD_NUMBER: _ClassVar[int]
    INSERT_AFTER_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_RESET_FIELD_NUMBER: _ClassVar[int]
    AUTOPLAY_LOADING_FIELD_NUMBER: _ClassVar[int]
    QUEUE_HASH_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    queue_item_ids: _containers.RepeatedScalarFieldContainer[int]
    insert_after: int
    autoplay_reset: bool
    autoplay_loading: bool
    queue_hash: bytes
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., queue_item_ids: _Optional[_Iterable[int]] = ..., insert_after: _Optional[int] = ..., autoplay_reset: _Optional[bool] = ..., autoplay_loading: _Optional[bool] = ..., queue_hash: _Optional[bytes] = ...) -> None: ...

class ShuffleModeSetMessage(_message.Message):
    __slots__ = ("queue_version", "action_uuid", "shuffle_mode")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ACTION_UUID_FIELD_NUMBER: _ClassVar[int]
    SHUFFLE_MODE_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    action_uuid: bytes
    shuffle_mode: bool
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., action_uuid: _Optional[bytes] = ..., shuffle_mode: _Optional[bool] = ...) -> None: ...

class PlaybackErrorMessage(_message.Message):
    __slots__ = ("queue_version", "queue_item_id", "error_type")
    QUEUE_VERSION_FIELD_NUMBER: _ClassVar[int]
    QUEUE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_TYPE_FIELD_NUMBER: _ClassVar[int]
    queue_version: QueueVersionRef
    queue_item_id: int
    error_type: int
    def __init__(self, queue_version: _Optional[_Union[QueueVersionRef, _Mapping]] = ..., queue_item_id: _Optional[int] = ..., error_type: _Optional[int] = ...) -> None: ...

class QConnectMessage(_message.Message):
    __slots__ = ("message_type", "playback_error", "rndr_srvr_join_session", "rndr_srvr_state_updated", "rndr_srvr_volume_changed", "rndr_srvr_file_audio_quality_changed", "rndr_srvr_device_audio_quality_changed", "rndr_srvr_max_audio_quality_changed", "rndr_srvr_volume_muted", "srvr_rndr_set_state", "srvr_rndr_set_volume", "srvr_rndr_set_active", "srvr_rndr_set_max_audio_quality", "srvr_rndr_set_loop_mode", "srvr_rndr_set_shuffle_mode", "srvr_rndr_mute_volume", "ctrl_srvr_join_session", "ctrl_srvr_ask_for_queue_state", "ctrl_srvr_ask_for_renderer_state", "srvr_ctrl_session_state", "srvr_ctrl_add_renderer", "srvr_ctrl_update_renderer", "srvr_ctrl_remove_renderer", "srvr_ctrl_active_renderer_changed", "srvr_ctrl_volume_changed", "srvr_ctrl_queue_error_message", "srvr_ctrl_queue_cleared", "srvr_ctrl_queue_state", "srvr_ctrl_queue_tracks_loaded", "srvr_ctrl_queue_tracks_inserted", "srvr_ctrl_queue_tracks_added", "srvr_ctrl_queue_tracks_removed", "srvr_ctrl_queue_tracks_reordered", "srvr_ctrl_shuffle_mode_set")
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    PLAYBACK_ERROR_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_JOIN_SESSION_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_STATE_UPDATED_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_VOLUME_CHANGED_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_FILE_AUDIO_QUALITY_CHANGED_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_DEVICE_AUDIO_QUALITY_CHANGED_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_MAX_AUDIO_QUALITY_CHANGED_FIELD_NUMBER: _ClassVar[int]
    RNDR_SRVR_VOLUME_MUTED_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_SET_STATE_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_SET_VOLUME_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_SET_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_SET_MAX_AUDIO_QUALITY_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_SET_LOOP_MODE_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_SET_SHUFFLE_MODE_FIELD_NUMBER: _ClassVar[int]
    SRVR_RNDR_MUTE_VOLUME_FIELD_NUMBER: _ClassVar[int]
    CTRL_SRVR_JOIN_SESSION_FIELD_NUMBER: _ClassVar[int]
    CTRL_SRVR_ASK_FOR_QUEUE_STATE_FIELD_NUMBER: _ClassVar[int]
    CTRL_SRVR_ASK_FOR_RENDERER_STATE_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_SESSION_STATE_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_ADD_RENDERER_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_UPDATE_RENDERER_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_REMOVE_RENDERER_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_ACTIVE_RENDERER_CHANGED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_VOLUME_CHANGED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_CLEARED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_STATE_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_TRACKS_LOADED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_TRACKS_INSERTED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_TRACKS_ADDED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_TRACKS_REMOVED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_QUEUE_TRACKS_REORDERED_FIELD_NUMBER: _ClassVar[int]
    SRVR_CTRL_SHUFFLE_MODE_SET_FIELD_NUMBER: _ClassVar[int]
    message_type: int
    playback_error: PlaybackErrorMessage
    rndr_srvr_join_session: JoinSessionMessage
    rndr_srvr_state_updated: RendererStateUpdatedMessage
    rndr_srvr_volume_changed: RendererVolumeChangedMessage
    rndr_srvr_file_audio_quality_changed: RendererFileAudioQualityChangedMessage
    rndr_srvr_device_audio_quality_changed: RendererDeviceAudioQualityChangedMessage
    rndr_srvr_max_audio_quality_changed: RendererMaxAudioQualityChangedMessage
    rndr_srvr_volume_muted: RendererVolumeMutedMessage
    srvr_rndr_set_state: RendererSetStateMessage
    srvr_rndr_set_volume: RendererSetVolumeMessage
    srvr_rndr_set_active: RendererSetActiveMessage
    srvr_rndr_set_max_audio_quality: RendererSetMaxAudioQualityMessage
    srvr_rndr_set_loop_mode: RendererSetLoopModeMessage
    srvr_rndr_set_shuffle_mode: RendererSetShuffleModeMessage
    srvr_rndr_mute_volume: RendererMuteVolumeMessage
    ctrl_srvr_join_session: JoinSessionMessage
    ctrl_srvr_ask_for_queue_state: AskForQueueStateMessage
    ctrl_srvr_ask_for_renderer_state: AskForRendererStateMessage
    srvr_ctrl_session_state: CtrlSessionStateMessage
    srvr_ctrl_add_renderer: CtrlAddRendererMessage
    srvr_ctrl_update_renderer: CtrlUpdateRendererMessage
    srvr_ctrl_remove_renderer: CtrlRemoveRendererMessage
    srvr_ctrl_active_renderer_changed: CtrlActiveRendererChangedMessage
    srvr_ctrl_volume_changed: CtrlVolumeChangedMessage
    srvr_ctrl_queue_error_message: QueueErrorMessage
    srvr_ctrl_queue_cleared: QueueClearedMessage
    srvr_ctrl_queue_state: QueueStateMessage
    srvr_ctrl_queue_tracks_loaded: QueueTracksLoadedMessage
    srvr_ctrl_queue_tracks_inserted: QueueTracksInsertedMessage
    srvr_ctrl_queue_tracks_added: QueueTracksAddedMessage
    srvr_ctrl_queue_tracks_removed: QueueTracksRemovedMessage
    srvr_ctrl_queue_tracks_reordered: QueueTracksReorderedMessage
    srvr_ctrl_shuffle_mode_set: ShuffleModeSetMessage
    def __init__(self, message_type: _Optional[int] = ..., playback_error: _Optional[_Union[PlaybackErrorMessage, _Mapping]] = ..., rndr_srvr_join_session: _Optional[_Union[JoinSessionMessage, _Mapping]] = ..., rndr_srvr_state_updated: _Optional[_Union[RendererStateUpdatedMessage, _Mapping]] = ..., rndr_srvr_volume_changed: _Optional[_Union[RendererVolumeChangedMessage, _Mapping]] = ..., rndr_srvr_file_audio_quality_changed: _Optional[_Union[RendererFileAudioQualityChangedMessage, _Mapping]] = ..., rndr_srvr_device_audio_quality_changed: _Optional[_Union[RendererDeviceAudioQualityChangedMessage, _Mapping]] = ..., rndr_srvr_max_audio_quality_changed: _Optional[_Union[RendererMaxAudioQualityChangedMessage, _Mapping]] = ..., rndr_srvr_volume_muted: _Optional[_Union[RendererVolumeMutedMessage, _Mapping]] = ..., srvr_rndr_set_state: _Optional[_Union[RendererSetStateMessage, _Mapping]] = ..., srvr_rndr_set_volume: _Optional[_Union[RendererSetVolumeMessage, _Mapping]] = ..., srvr_rndr_set_active: _Optional[_Union[RendererSetActiveMessage, _Mapping]] = ..., srvr_rndr_set_max_audio_quality: _Optional[_Union[RendererSetMaxAudioQualityMessage, _Mapping]] = ..., srvr_rndr_set_loop_mode: _Optional[_Union[RendererSetLoopModeMessage, _Mapping]] = ..., srvr_rndr_set_shuffle_mode: _Optional[_Union[RendererSetShuffleModeMessage, _Mapping]] = ..., srvr_rndr_mute_volume: _Optional[_Union[RendererMuteVolumeMessage, _Mapping]] = ..., ctrl_srvr_join_session: _Optional[_Union[JoinSessionMessage, _Mapping]] = ..., ctrl_srvr_ask_for_queue_state: _Optional[_Union[AskForQueueStateMessage, _Mapping]] = ..., ctrl_srvr_ask_for_renderer_state: _Optional[_Union[AskForRendererStateMessage, _Mapping]] = ..., srvr_ctrl_session_state: _Optional[_Union[CtrlSessionStateMessage, _Mapping]] = ..., srvr_ctrl_add_renderer: _Optional[_Union[CtrlAddRendererMessage, _Mapping]] = ..., srvr_ctrl_update_renderer: _Optional[_Union[CtrlUpdateRendererMessage, _Mapping]] = ..., srvr_ctrl_remove_renderer: _Optional[_Union[CtrlRemoveRendererMessage, _Mapping]] = ..., srvr_ctrl_active_renderer_changed: _Optional[_Union[CtrlActiveRendererChangedMessage, _Mapping]] = ..., srvr_ctrl_volume_changed: _Optional[_Union[CtrlVolumeChangedMessage, _Mapping]] = ..., srvr_ctrl_queue_error_message: _Optional[_Union[QueueErrorMessage, _Mapping]] = ..., srvr_ctrl_queue_cleared: _Optional[_Union[QueueClearedMessage, _Mapping]] = ..., srvr_ctrl_queue_state: _Optional[_Union[QueueStateMessage, _Mapping]] = ..., srvr_ctrl_queue_tracks_loaded: _Optional[_Union[QueueTracksLoadedMessage, _Mapping]] = ..., srvr_ctrl_queue_tracks_inserted: _Optional[_Union[QueueTracksInsertedMessage, _Mapping]] = ..., srvr_ctrl_queue_tracks_added: _Optional[_Union[QueueTracksAddedMessage, _Mapping]] = ..., srvr_ctrl_queue_tracks_removed: _Optional[_Union[QueueTracksRemovedMessage, _Mapping]] = ..., srvr_ctrl_queue_tracks_reordered: _Optional[_Union[QueueTracksReorderedMessage, _Mapping]] = ..., srvr_ctrl_shuffle_mode_set: _Optional[_Union[ShuffleModeSetMessage, _Mapping]] = ...) -> None: ...

class QConnectMessages(_message.Message):
    __slots__ = ("messages_time", "messages_id", "messages")
    MESSAGES_TIME_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages_time: int
    messages_id: int
    messages: _containers.RepeatedCompositeFieldContainer[QConnectMessage]
    def __init__(self, messages_time: _Optional[int] = ..., messages_id: _Optional[int] = ..., messages: _Optional[_Iterable[_Union[QConnectMessage, _Mapping]]] = ...) -> None: ...
