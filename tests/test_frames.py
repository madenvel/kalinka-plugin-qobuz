"""The Connect cloud's framing: type byte, varint length, protobuf."""

import pytest

from kalinka_plugin_qobuz.connect import frames
from kalinka_plugin_qobuz.connect.proto import qconnect_pb2 as qc
from kalinka_plugin_qobuz.connect.proto import qws_pb2 as qws

from conftest import QCONNECT_JWT

DEVICE_UUID = "8f2c1f4e-3d6b-4a57-9c1e-2b7d9e0a4c11"


def test_a_frame_round_trips():
    body = b"x" * 300  # a two-byte length prefix

    assert frames.decode_frame(frames.encode_frame(frames.PAYLOAD, body)) == (frames.PAYLOAD, body)


def test_a_frame_may_carry_trailing_bytes_it_does_not_claim():
    data = frames.encode_frame(frames.ERROR, b"abc") + b"junk"

    assert frames.decode_frame(data) == (frames.ERROR, b"abc")


@pytest.mark.parametrize(
    "data",
    [b"", bytes([frames.PAYLOAD]), bytes([frames.PAYLOAD, 0x05, 0x01]), bytes([6, 0xFF] * 12)],
)
def test_broken_frames_are_refused(data):
    with pytest.raises(frames.FrameError):
        frames.decode_frame(data)


def test_authenticate_carries_the_session_token():
    kind, body = frames.decode_frame(frames.authenticate(1, QCONNECT_JWT))

    message = qws.Authenticate.FromString(body)
    assert kind == frames.AUTHENTICATE
    assert (message.msg_id, message.jwt) == (1, QCONNECT_JWT)


def test_subscribe_names_the_receiver_channels():
    kind, body = frames.decode_frame(frames.subscribe(2))

    message = qws.Subscribe.FromString(body)
    assert kind == frames.SUBSCRIBE
    assert message.proto == 1
    assert list(message.channels) == [b"\x01", b"\x02", b"\x03"]


def test_messages_travel_batched_in_a_payload():
    sent = [
        qc.QConnectMessage(message_type=qc.CTRL_SRVR_ASK_FOR_QUEUE_STATE),
        qc.QConnectMessage(
            message_type=qc.RNDR_SRVR_VOLUME_CHANGED,
            rndr_srvr_volume_changed=qc.RendererVolumeChangedMessage(volume=40),
        ),
    ]

    kind, body = frames.decode_frame(frames.payload(3, 7, sent))

    assert kind == frames.PAYLOAD
    assert frames.messages_of(body) == sent
    batch = qc.QConnectMessages.FromString(qws.CloudPayload.FromString(body).payload)
    assert batch.messages_id == 7


def test_uuids_travel_as_sixteen_bytes():
    raw = frames.uuid_bytes(DEVICE_UUID)

    assert len(raw) == 16
    assert frames.uuid_text(raw) == DEVICE_UUID
    assert frames.uuid_text(b"short") == ""
