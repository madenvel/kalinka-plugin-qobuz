"""What the Qobuz app sees in its device picker, without touching the network."""

import socket
from types import SimpleNamespace

import pytest

from kalinka_plugin_qobuz.connect import discovery
from kalinka_plugin_qobuz.connect.discovery import (
    SERVICE_TYPE,
    Advert,
    NoAddressesError,
    ZeroconfAdvertiser,
    lan_ipv4_addresses,
    sanitize_instance_name,
)


def _text(value):
    return value.decode() if isinstance(value, bytes) else value


def _adapter(name, *ips):
    return SimpleNamespace(
        name=name,
        ips=[SimpleNamespace(ip=ip, is_IPv4=isinstance(ip, str)) for ip in ips],
    )


class _FakeZeroconf:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.fail = None
        _FakeZeroconf.instances.append(self)

    async def async_register_service(self, info, **kwargs):
        self.calls.append(("register", info, kwargs))
        if _FakeZeroconf.fail:
            raise _FakeZeroconf.fail

    async def async_unregister_service(self, info):
        self.calls.append(("unregister", info))

    async def async_close(self):
        self.calls.append(("close",))


@pytest.fixture
def lan(monkeypatch):
    adapters = [
        _adapter("lo", "127.0.0.1"),
        _adapter("eth0", "192.168.1.20", ("fe80::1", 0, 2)),
        _adapter("docker0", "172.17.0.1"),
        _adapter("wlan0", "169.254.3.4", "10.0.0.5"),
    ]
    monkeypatch.setattr(discovery.ifaddr, "get_adapters", lambda: adapters)
    _FakeZeroconf.instances = []
    _FakeZeroconf.fail = None
    monkeypatch.setattr(discovery, "AsyncZeroconf", _FakeZeroconf)
    return adapters


ADVERT = Advert(
    friendly_name="Kalinka (living room)",
    device_uuid="5b0a3c52-3a2e-4b8e-9a51-6a4d2f0e7d11",
    port=8183,
    sdk_version="kalinka-qobuz-4.0.0",
)


def test_only_reachable_lan_ipv4_addresses_are_advertised(lan):
    assert lan_ipv4_addresses() == ["192.168.1.20", "10.0.0.5"]


@pytest.mark.parametrize(
    "name, instance",
    [
        ("Kalinka (living room)", "Kalinka-living-room"),
        ("  ", "Kalinka"),
        ("Küche_1", "Küche_1"),
        ("x" * 80, "x" * 63),
    ],
)
def test_instance_names_are_mdns_safe(name, instance):
    assert sanitize_instance_name(name) == instance


@pytest.mark.asyncio
async def test_the_service_carries_the_properties_the_app_reads(lan):
    advertiser = ZeroconfAdvertiser()

    await advertiser.start(ADVERT)

    zeroconf = _FakeZeroconf.instances[0]
    kind, info, options = zeroconf.calls[0]
    assert kind == "register" and options == {"allow_name_change": True}
    assert info.type == SERVICE_TYPE
    assert info.name == f"Kalinka-living-room.{SERVICE_TYPE}"
    assert info.server == "Kalinka-living-room.local."
    assert info.port == 8183
    assert info.addresses == [socket.inet_aton("192.168.1.20"), socket.inet_aton("10.0.0.5")]
    # zeroconf hands properties back as given (str) or as encoded (bytes),
    # depending on its version.
    assert {_text(key): _text(value) for key, value in info.properties.items()} == {
        "path": "/streamcore",
        "type": "SPEAKER",
        "sdk_version": "kalinka-qobuz-4.0.0",
        "Name": "Kalinka (living room)",
        "device_uuid": ADVERT.device_uuid,
    }
    assert zeroconf.kwargs["interfaces"] == ["192.168.1.20", "10.0.0.5"]


@pytest.mark.asyncio
async def test_stop_withdraws_the_service_then_closes(lan):
    advertiser = ZeroconfAdvertiser()
    await advertiser.start(ADVERT)

    await advertiser.stop()
    await advertiser.stop()

    calls = [call[0] for call in _FakeZeroconf.instances[0].calls]
    assert calls == ["register", "unregister", "close"]


@pytest.mark.asyncio
async def test_without_an_address_nothing_is_started(monkeypatch, lan):
    monkeypatch.setattr(discovery.ifaddr, "get_adapters", lambda: [_adapter("lo", "127.0.0.1")])

    with pytest.raises(NoAddressesError):
        await ZeroconfAdvertiser().start(ADVERT)
    assert _FakeZeroconf.instances == []


@pytest.mark.asyncio
async def test_a_failed_registration_releases_zeroconf(lan):
    _FakeZeroconf.fail = OSError("no multicast")

    with pytest.raises(OSError):
        await ZeroconfAdvertiser().start(ADVERT)

    assert [call[0] for call in _FakeZeroconf.instances[0].calls] == ["register", "close"]
