"""The Connect cloud credential: what joins this player to the app's session.

A handoff carries it as ``jwt_qconnect``, with the WebSocket endpoint it is
good for. It is renewed at the same ``qws/refreshToken`` endpoint as the API
token, as ``jwt_qws``, with a live API Bearer token as the credential.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/pibuz/src/qconnect/pairing.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import logging
from dataclasses import dataclass, replace
from typing import Optional
from urllib.parse import urlsplit

import httpx

from ..auth import Credential, fingerprint, unix_seconds
from .refresh import REFRESH_URL

logger = logging.getLogger(__name__.split(".")[-1])


@dataclass(frozen=True)
class SessionToken:
    """``exp`` is absolute Unix seconds, 0 when Qobuz gave none."""

    jwt: str
    endpoint: str
    exp: int = 0
    session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "jwt": self.jwt,
            "endpoint": self.endpoint,
            "exp": self.exp,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionToken":
        return cls(
            jwt=str(data["jwt"]),
            endpoint=str(data["endpoint"]),
            exp=int(data.get("exp", 0)),
            session_id=str(data.get("session_id", "")),
        )

    def __repr__(self) -> str:
        return (
            f"SessionToken(#{fingerprint(self.jwt)}, {endpoint_host(self.endpoint)}, "
            f"exp={self.exp})"
        )

    __str__ = __repr__


def endpoint_host(endpoint: str) -> str:
    """The endpoint without path or query, for logs."""
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.hostname}" if parts.hostname else "-"


async def renew_session_token(
    http: httpx.AsyncClient, app_id: str, bearer: Credential, current: SessionToken
) -> Optional[SessionToken]:
    """A renewed session token, or None when Qobuz would not renew it."""
    try:
        response = await http.post(
            REFRESH_URL,
            headers={"X-App-Id": app_id, **bearer.headers()},
            data={"jwt": "jwt_qws"},
        )
    except httpx.TransportError as exc:
        logger.warning("Qobuz Connect session renewal: network error (%s)", type(exc).__name__)
        return None
    if not response.is_success:
        logger.warning("Qobuz Connect session renewal refused: HTTP %d", response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        body = None
    payload = body.get("jwt_qws") if isinstance(body, dict) else None
    token = payload.get("jwt") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        logger.warning("Qobuz Connect session renewal: unusable answer")
        return None
    endpoint = payload.get("endpoint")
    renewed = replace(
        current,
        jwt=token,
        exp=unix_seconds(payload.get("exp")),
        endpoint=endpoint if isinstance(endpoint, str) and endpoint else current.endpoint,
    )
    logger.info(  # log-safe: 8-hex SHA-256 prefixes, not the tokens
        "Qobuz Connect session renewed: #%s -> #%s",
        fingerprint(current.jwt),
        fingerprint(renewed.jwt),
    )
    return renewed
