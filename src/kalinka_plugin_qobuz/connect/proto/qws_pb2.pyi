from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Authenticate(_message.Message):
    __slots__ = ("msg_id", "msg_date", "jwt")
    MSG_ID_FIELD_NUMBER: _ClassVar[int]
    MSG_DATE_FIELD_NUMBER: _ClassVar[int]
    JWT_FIELD_NUMBER: _ClassVar[int]
    msg_id: int
    msg_date: int
    jwt: str
    def __init__(self, msg_id: _Optional[int] = ..., msg_date: _Optional[int] = ..., jwt: _Optional[str] = ...) -> None: ...

class Subscribe(_message.Message):
    __slots__ = ("msg_id", "msg_date", "proto", "channels")
    MSG_ID_FIELD_NUMBER: _ClassVar[int]
    MSG_DATE_FIELD_NUMBER: _ClassVar[int]
    PROTO_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    msg_id: int
    msg_date: int
    proto: int
    channels: _containers.RepeatedScalarFieldContainer[bytes]
    def __init__(self, msg_id: _Optional[int] = ..., msg_date: _Optional[int] = ..., proto: _Optional[int] = ..., channels: _Optional[_Iterable[bytes]] = ...) -> None: ...

class CloudPayload(_message.Message):
    __slots__ = ("msg_id", "msg_date", "proto", "src", "dests", "payload")
    MSG_ID_FIELD_NUMBER: _ClassVar[int]
    MSG_DATE_FIELD_NUMBER: _ClassVar[int]
    PROTO_FIELD_NUMBER: _ClassVar[int]
    SRC_FIELD_NUMBER: _ClassVar[int]
    DESTS_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    msg_id: int
    msg_date: int
    proto: int
    src: bytes
    dests: _containers.RepeatedScalarFieldContainer[bytes]
    payload: bytes
    def __init__(self, msg_id: _Optional[int] = ..., msg_date: _Optional[int] = ..., proto: _Optional[int] = ..., src: _Optional[bytes] = ..., dests: _Optional[_Iterable[bytes]] = ..., payload: _Optional[bytes] = ...) -> None: ...

class ErrorMessage(_message.Message):
    __slots__ = ("msg_id", "msg_date", "code", "descr")
    MSG_ID_FIELD_NUMBER: _ClassVar[int]
    MSG_DATE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DESCR_FIELD_NUMBER: _ClassVar[int]
    msg_id: int
    msg_date: int
    code: int
    descr: str
    def __init__(self, msg_id: _Optional[int] = ..., msg_date: _Optional[int] = ..., code: _Optional[int] = ..., descr: _Optional[str] = ...) -> None: ...
