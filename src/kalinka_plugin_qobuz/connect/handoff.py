"""The credential handoff the Qobuz app POSTs when this player is chosen.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/pibuz/src/qconnect/pairing.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import base64
import json
import logging
import math
from dataclasses import dataclass
from typing import Any

from ..auth import Credential, CredentialKind, fingerprint

logger = logging.getLogger(__name__.split(".")[-1])

MAX_BODY_BYTES = 64 * 1024

# A token this close to its expiry is treated as expired: clock skew plus the
# time the rest of the pairing takes.
EXPIRY_SLACK_S = 60

# Unix seconds pass 10**11 in the year 5138, so a larger `exp` is milliseconds.
_MILLISECONDS_THRESHOLD = 10**11


class HandoffError(ValueError):
    """A handoff that cannot link this player. The message goes back to the app."""


@dataclass(frozen=True, repr=False)
class Handoff:
    """The part of a handoff the plugin keeps: the REST credential.

    The Connect session token in the same body is checked, not kept; this
    plugin never joins the Connect session.
    """

    session_id: str
    credential: Credential
    keys: tuple[str, ...]

    def same_as(self, other: "Handoff") -> bool:
        return self.session_id == other.session_id and self.credential == other.credential

    def __repr__(self) -> str:
        return f"Handoff(session={redact_session(self.session_id)}, credential={self.credential!r})"


def redact_session(session_id: str) -> str:
    return f"{session_id[:8]}…" if session_id else "-"


def unix_seconds(value: Any) -> int:
    """A Qobuz ``exp`` as absolute Unix seconds, 0 when it is not a usable time."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return 0
    # JSON parsing admits NaN and Infinity, which no integer can hold.
    if isinstance(value, float) and not math.isfinite(value):
        return 0
    if value > _MILLISECONDS_THRESHOLD:
        logger.info("Qobuz gave an expiry in milliseconds; converted")
        return int(value // 1000)
    return int(value)


def _non_empty_string(container: dict, key: str) -> str:
    value = container.get(key)
    return value if isinstance(value, str) and value.strip() else ""


def parse_handoff(body: bytes, now: float) -> Handoff:
    """Validate a ``connect-to-qconnect`` body and extract the REST credential.

    A plain ``user_auth_token``, if the app ever sends one, is preferred: it
    is the credential the REST client has always used. Otherwise ``jwt_api``
    is used as a Bearer credential.
    """
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HandoffError("body is not JSON") from None
    if not isinstance(document, dict):
        raise HandoffError("body is not a JSON object")

    session = document.get("jwt_qconnect")
    if not isinstance(session, dict):
        raise HandoffError("missing jwt_qconnect")
    if not _non_empty_string(session, "jwt"):
        raise HandoffError("missing jwt_qconnect.jwt")
    if not _non_empty_string(session, "endpoint"):
        raise HandoffError("missing jwt_qconnect.endpoint")
    session_exp = unix_seconds(session.get("exp"))
    if session_exp and session_exp <= now + EXPIRY_SLACK_S:
        raise HandoffError("jwt_qconnect is already expired")

    user_auth_token = _non_empty_string(document, "user_auth_token")
    api = document.get("jwt_api")
    if user_auth_token:
        credential = Credential(CredentialKind.USER_AUTH_TOKEN, user_auth_token)
    elif isinstance(api, dict) and _non_empty_string(api, "jwt"):
        credential = Credential(
            CredentialKind.BEARER, api["jwt"], unix_seconds(api.get("exp"))
        )
    else:
        raise HandoffError("missing jwt_api")

    session_id = document.get("session_id")
    return Handoff(
        session_id=session_id if isinstance(session_id, str) else "",
        credential=credential,
        keys=tuple(sorted(document)),
    )


def claim_names(jwt: str) -> list[str]:
    """The names of a JWT's claims, for diagnostics. Values are never read out."""
    try:
        payload = jwt.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        return []
    return sorted(claims) if isinstance(claims, dict) else []


def describe(handoff: Handoff) -> str:
    """One log line about a handoff that reveals no credential."""
    credential = handoff.credential
    return (
        f"session {redact_session(handoff.session_id)}, keys {list(handoff.keys)}, "
        f"{credential.kind.value} credential #{fingerprint(credential.token)}, "
        f"exp {credential.exp or 'none'}, claims {claim_names(credential.token)}"
    )
