"""Announces this player to the Qobuz app's device picker over mDNS.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/pibuz/src/qconnect/pairing.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import logging
import socket
from dataclasses import dataclass
from typing import Optional, Protocol

import ifaddr
from zeroconf import IPVersion, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

logger = logging.getLogger(__name__.split(".")[-1])

SERVICE_TYPE = "_qobuz-connect._tcp.local."

# Container and VM bridges: advertising them hands the app an address it
# usually cannot reach.
_VIRTUAL_ADAPTERS = ("docker", "br-", "virbr", "veth")

_MAX_LABEL_BYTES = 63


class NoAddressesError(OSError):
    """No LAN IPv4 address to advertise."""


@dataclass(frozen=True)
class Advert:
    friendly_name: str
    device_uuid: str
    port: int
    sdk_version: str

    @property
    def instance(self) -> str:
        return sanitize_instance_name(self.friendly_name)

    def properties(self) -> dict[str, str]:
        return {
            "path": "/streamcore",
            "type": "SPEAKER",
            "sdk_version": self.sdk_version,
            "Name": self.friendly_name,
            "device_uuid": self.device_uuid,
        }


class Advertiser(Protocol):
    async def start(self, advert: Advert) -> None: ...

    async def stop(self) -> None: ...


def sanitize_instance_name(name: str) -> str:
    """An mDNS-safe instance label; the display name travels in the TXT ``Name``."""
    out = []
    for char in name:
        if char.isalnum() or char == "_":
            out.append(char)
        elif not out or out[-1] != "-":
            out.append("-")
    label = "".join(out).strip("-") or "Kalinka"
    return label.encode("utf-8")[:_MAX_LABEL_BYTES].decode("utf-8", "ignore")


def lan_ipv4_addresses() -> list[str]:
    addresses = []
    for adapter in ifaddr.get_adapters():
        if str(adapter.name).startswith(_VIRTUAL_ADAPTERS):
            continue
        for ip in adapter.ips:
            if not ip.is_IPv4 or ip.ip.startswith(("127.", "169.254.")):
                continue
            if ip.ip not in addresses:
                addresses.append(ip.ip)
    return addresses


class ZeroconfAdvertiser:
    """Registers one ``_qobuz-connect._tcp`` service while started."""

    def __init__(self):
        self._zeroconf: Optional[AsyncZeroconf] = None
        self._info: Optional[ServiceInfo] = None

    async def start(self, advert: Advert) -> None:
        """@throw NoAddressesError without a LAN address; zeroconf errors as raised."""
        addresses = lan_ipv4_addresses()
        if not addresses:
            raise NoAddressesError("no LAN IPv4 address")
        instance = advert.instance
        info = ServiceInfo(
            SERVICE_TYPE,
            f"{instance}.{SERVICE_TYPE}",
            port=advert.port,
            properties=advert.properties(),
            # Named after the instance, not the machine, so it never contends
            # with the system's own mDNS responder for the host's A record.
            server=f"{instance}.local.",
            addresses=[socket.inet_aton(address) for address in addresses],
        )
        self._zeroconf = AsyncZeroconf(ip_version=IPVersion.V4Only, interfaces=addresses)
        try:
            await self._zeroconf.async_register_service(info, allow_name_change=True)
        except BaseException:
            await self.stop()
            raise
        self._info = info
        logger.info(
            "Advertising Qobuz Connect device %r on %s port %d",
            info.name,
            ", ".join(addresses),
            advert.port,
        )

    async def stop(self) -> None:
        zeroconf, info = self._zeroconf, self._info
        self._zeroconf = self._info = None
        if zeroconf is None:
            return
        try:
            if info is not None:
                await zeroconf.async_unregister_service(info)
        finally:
            await zeroconf.async_close()
        logger.info("Stopped advertising Qobuz Connect")
