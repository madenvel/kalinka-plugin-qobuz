"""The WebSocket connection to the Connect cloud, against a loopback cloud."""

import asyncio
import logging

import pytest
import pytest_asyncio

from kalinka_plugin_qobuz.connect import cloud_link
from kalinka_plugin_qobuz.connect.cloud_link import CloudLink, CloudState
from kalinka_plugin_qobuz.connect.proto import qconnect_pb2 as qc
from kalinka_plugin_qobuz.connect.session_token import SessionToken

from conftest import QCONNECT_JWT, RENEWED_QCONNECT_JWT, assert_no_secrets
from fake_cloud import FakeCloud

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def quick_backoff(monkeypatch):
    monkeypatch.setattr(cloud_link, "BACKOFF_START_S", 0.01)
    monkeypatch.setattr(cloud_link, "BACKOFF_MAX_S", 0.02)


@pytest_asyncio.fixture
async def cloud():
    fake = await FakeCloud(answer_joins=False).start()
    yield fake
    await fake.stop()


class Receiver:
    def __init__(self, cloud: FakeCloud, jwt: str = QCONNECT_JWT):
        self.token = SessionToken(jwt=jwt, endpoint=cloud.url, exp=0)
        self.connections = 0
        self.heard: list[qc.QConnectMessage] = []
        self.link = CloudLink(
            token=self._token, on_connected=self._connected, on_messages=self._messages
        )

    async def _token(self):
        return self.token

    async def _connected(self):
        self.connections += 1

    async def _messages(self, messages):
        self.heard.extend(messages)


async def test_it_authenticates_with_the_session_token_and_subscribes(cloud):
    receiver = Receiver(cloud)
    receiver.link.start()

    await cloud.until(lambda: cloud.channels)

    assert cloud.tokens == [QCONNECT_JWT]
    assert cloud.channels == [[b"\x01", b"\x02", b"\x03"]]
    assert receiver.link.state is CloudState.CONNECTED
    assert receiver.connections == 1
    await receiver.link.stop()


async def test_messages_travel_both_ways(cloud):
    receiver = Receiver(cloud)
    receiver.link.start()
    await cloud.until(lambda: receiver.connections)
    volume = qc.QConnectMessage(
        message_type=qc.SRVR_RNDR_SET_VOLUME,
        srvr_rndr_set_volume=qc.RendererSetVolumeMessage(volume=20),
    )

    await cloud.push(volume)
    assert await receiver.link.send([qc.QConnectMessage(message_type=qc.CTRL_SRVR_ASK_FOR_QUEUE_STATE)])
    await cloud.until(lambda: receiver.heard and cloud.received)

    assert receiver.heard == [volume]
    assert cloud.kinds() == [qc.CTRL_SRVR_ASK_FOR_QUEUE_STATE]
    await receiver.link.stop()


async def test_nothing_is_sent_without_a_connection(cloud):
    receiver = Receiver(cloud)

    assert await receiver.link.send([qc.QConnectMessage()]) is False


async def test_a_dropped_connection_comes_back_with_the_current_token(cloud):
    receiver = Receiver(cloud)
    receiver.link.start()
    await cloud.until(lambda: receiver.connections == 1)
    receiver.token = SessionToken(jwt=RENEWED_QCONNECT_JWT, endpoint=cloud.url)

    await cloud.drop()
    await cloud.until(lambda: receiver.connections == 2)

    assert cloud.tokens == [QCONNECT_JWT, RENEWED_QCONNECT_JWT]
    await receiver.link.stop()


async def test_a_cloud_error_is_recorded_without_the_token(cloud, caplog):
    cloud.refuse_token = QCONNECT_JWT
    receiver = Receiver(cloud)

    with caplog.at_level(logging.DEBUG):
        receiver.link.start()
        await cloud.until(lambda: "expired JWT" in receiver.link.last_error)
        await receiver.link.stop()

    assert receiver.link.last_error == "cloud error 401: expired JWT"
    assert_no_secrets(caplog.text)


async def test_without_a_token_it_waits_until_told(cloud):
    receiver = Receiver(cloud)
    receiver.token = None
    receiver.link.start()
    await asyncio.sleep(0.05)
    assert cloud.tokens == []

    receiver.token = SessionToken(jwt=QCONNECT_JWT, endpoint=cloud.url)
    await receiver.link.reconnect()
    await cloud.until(lambda: cloud.tokens)

    assert cloud.tokens == [QCONNECT_JWT]
    await receiver.link.stop()


async def test_a_reconnect_connects_again_at_once_with_the_new_token(cloud, monkeypatch):
    monkeypatch.setattr(cloud_link, "BACKOFF_START_S", 30)
    receiver = Receiver(cloud)
    receiver.link.start()
    await cloud.until(lambda: receiver.connections == 1)

    receiver.token = SessionToken(jwt=RENEWED_QCONNECT_JWT, endpoint=cloud.url)
    await receiver.link.reconnect()
    await cloud.until(lambda: receiver.connections == 2, timeout=1.0)

    assert cloud.tokens == [QCONNECT_JWT, RENEWED_QCONNECT_JWT]
    await receiver.link.stop()


async def test_a_reconnect_while_connecting_uses_the_new_token(cloud):
    opened = asyncio.Event()

    def connect(*args, **kwargs):
        opening = cloud_link.ws_connect(*args, **kwargs)

        class Held:
            async def __aenter__(self):
                ws = await opening.__aenter__()
                await opened.wait()
                return ws

            async def __aexit__(self, *exc):
                return await opening.__aexit__(*exc)

        return Held()

    receiver = Receiver(cloud)
    receiver.link = CloudLink(
        token=receiver._token,
        on_connected=receiver._connected,
        on_messages=receiver._messages,
        connect=connect,
    )
    receiver.link.start()
    await asyncio.sleep(0.05)

    receiver.token = SessionToken(jwt=RENEWED_QCONNECT_JWT, endpoint=cloud.url)
    await receiver.link.reconnect()
    opened.set()
    await cloud.until(lambda: receiver.connections == 1)

    assert cloud.tokens[-1] == RENEWED_QCONNECT_JWT
    await receiver.link.stop()


async def test_an_unreachable_cloud_is_retried(cloud):
    receiver = Receiver(cloud)
    await cloud.stop()
    receiver.link.start()

    await cloud.until(lambda: receiver.link.state is CloudState.RETRYING)

    assert receiver.link.last_error
    await receiver.link.stop()
    assert receiver.link.state is CloudState.IDLE
