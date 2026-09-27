"""The credential handoff the Qobuz app POSTs when this player is chosen.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/pibuz/src/qconnect/pairing.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

from ..auth import Credential, CredentialKind, fingerprint, unix_seconds
from .session_token import SessionToken, endpoint_host

logger = logging.getLogger(__name__.split(".")[-1])

MAX_BODY_BYTES = 64 * 1024

# A token this close to its expiry is treated as expired: clock skew plus the
# time the rest of the pairing takes.
EXPIRY_SLACK_S = 60


class HandoffError(ValueError):
    """A handoff that cannot link this player. The message goes back to the app."""


@dataclass(frozen=True, repr=False)
class Handoff:
    """What a handoff yields: the REST credential and the Connect session.

    ``api_bearer`` is the app's API token itself, kept even when ``credential``
    is something else: renewing the session token needs it.
    """

    session_id: str
    credential: Credential
    session: SessionToken
    api_bearer: Optional[Credential]
    keys: tuple[str, ...]

    def same_as(self, other: "Handoff") -> bool:
        return self.session_id == other.session_id and self.credential == other.credential

    def __repr__(self) -> str:
        return f"Handoff(session={redact_session(self.session_id)}, credential={self.credential!r})"


def redact_session(session_id: str) -> str:
    return f"{session_id[:8]}…" if session_id else "-"


def _non_empty_string(container: dict, key: str) -> str:
    value = container.get(key)
    return value if isinstance(value, str) and value.strip() else ""


def parse_handoff(body: bytes, now: float) -> Handoff:
    """Validate a ``connect-to-qconnect`` body and extract its credentials.

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
    api_bearer = (
        Credential(CredentialKind.BEARER, api["jwt"], unix_seconds(api.get("exp")))
        if isinstance(api, dict) and _non_empty_string(api, "jwt")
        else None
    )
    if user_auth_token:
        credential = Credential(CredentialKind.USER_AUTH_TOKEN, user_auth_token)
    elif api_bearer is not None:
        credential = api_bearer
    else:
        raise HandoffError("missing jwt_api")

    session_id = document.get("session_id")
    session_id = session_id if isinstance(session_id, str) else ""
    return Handoff(
        session_id=session_id,
        credential=credential,
        session=SessionToken(
            jwt=session["jwt"],
            endpoint=session["endpoint"],
            exp=session_exp,
            session_id=session_id,
        ),
        api_bearer=api_bearer,
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
        f"exp {credential.exp or 'none'}, claims {claim_names(credential.token)}, "
        f"Connect session #{fingerprint(handoff.session.jwt)} at "
        f"{endpoint_host(handoff.session.endpoint)}"
    )
