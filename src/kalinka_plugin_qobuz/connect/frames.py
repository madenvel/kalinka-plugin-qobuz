"""The Qobuz Connect cloud's framing: one message per WebSocket binary frame.

A frame is ``[type byte][varint length][protobuf]``. Connect messages travel
in PAYLOAD frames, batched in a ``QConnectMessages``.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/qconnect-transport-ws/src/transport.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import time
import uuid
from typing import Iterable

from .proto import qconnect_pb2 as qc
from .proto import qws_pb2 as qws

AUTHENTICATE = 1
SUBSCRIBE = 2
PAYLOAD = 6
ERROR = 9
DISCONNECT = 10

# The cloud's transport protocol version, and the channels a receiver listens
# on: connection, backend, controllers.
CLOUD_PROTO = 1
CHANNELS = (b"\x01", b"\x02", b"\x03")


class FrameError(ValueError):
    """A frame that does not parse."""


def now_ms() -> int:
    return int(time.time() * 1000)


def encode_frame(kind: int, payload: bytes) -> bytes:
    return bytes([kind]) + _varint(len(payload)) + payload


def decode_frame(data: bytes) -> tuple[int, bytes]:
    if not data:
        raise FrameError("empty frame")
    length, offset = _read_varint(data, 1)
    end = offset + length
    if end > len(data):
        raise FrameError(f"truncated frame: {len(data)} of {end} bytes")
    return data[0], data[offset:end]


def authenticate(msg_id: int, jwt: str) -> bytes:
    message = qws.Authenticate(msg_id=msg_id, msg_date=now_ms(), jwt=jwt)
    return encode_frame(AUTHENTICATE, message.SerializeToString())


def subscribe(msg_id: int) -> bytes:
    message = qws.Subscribe(
        msg_id=msg_id, msg_date=now_ms(), proto=CLOUD_PROTO, channels=list(CHANNELS)
    )
    return encode_frame(SUBSCRIBE, message.SerializeToString())


def payload(msg_id: int, batch_id: int, messages: Iterable[qc.QConnectMessage]) -> bytes:
    batch = qc.QConnectMessages(
        messages_time=now_ms(), messages_id=batch_id, messages=list(messages)
    )
    envelope = qws.CloudPayload(
        msg_id=msg_id,
        msg_date=now_ms(),
        proto=CLOUD_PROTO,
        payload=batch.SerializeToString(),
    )
    return encode_frame(PAYLOAD, envelope.SerializeToString())


def messages_of(body: bytes) -> list[qc.QConnectMessage]:
    """The Connect messages in a PAYLOAD frame's body."""
    envelope = qws.CloudPayload.FromString(body)
    if not envelope.HasField("payload"):
        return []
    return list(qc.QConnectMessages.FromString(envelope.payload).messages)


def uuid_bytes(value: str) -> bytes:
    return uuid.UUID(value).bytes


def uuid_text(value: bytes) -> str:
    return str(uuid.UUID(bytes=value)) if len(value) == 16 else ""


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            break
    raise FrameError("bad length prefix")
