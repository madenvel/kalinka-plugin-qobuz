"""The linked account, kept private on disk across restarts.

The file holds a live credential, so it is written owner-only and replaced
atomically; a reader never sees a half-written link.
"""

import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, replace
from typing import Optional

from kalinka_plugin_sdk import paths

from ..account import AccountInfo
from ..auth import Credential, CredentialKind
from .session_token import SessionToken

logger = logging.getLogger(__name__.split(".")[-1])

# 2 adds the Connect session and the app's API token; 1 is still read.
_VERSION = 2


def default_store_path() -> str:
    return os.path.join(paths.state_dir(), "qobuz", "connect.json")


@dataclass(frozen=True)
class LinkState:
    """This player's Connect identity and the account linked to it, if any.

    @note ``linked`` is the paired lock: it stays set when the credential
        expires, and only an explicit unpair clears it.
    """

    device_uuid: str
    linked: bool = False
    linked_at: int = 0
    credential: Optional[Credential] = None
    account: Optional[AccountInfo] = None
    # The Connect session to join, and the API token that renews it.
    session: Optional[SessionToken] = None
    api_bearer: Optional[Credential] = None

    def unlinked(self) -> "LinkState":
        return LinkState(device_uuid=self.device_uuid)

    def with_credential(self, credential: Credential) -> "LinkState":
        return replace(self, credential=credential)

    def with_session(
        self, session: Optional[SessionToken], api_bearer: Optional[Credential]
    ) -> "LinkState":
        return replace(self, session=session, api_bearer=api_bearer)

    def to_dict(self) -> dict:
        return {
            "version": _VERSION,
            "device_uuid": self.device_uuid,
            "linked": self.linked,
            "linked_at": self.linked_at,
            "credential": _credential_dict(self.credential),
            "account": self.account.to_dict() if self.account else None,
            "session": self.session.to_dict() if self.session else None,
            "api_bearer": _credential_dict(self.api_bearer),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LinkState":
        account = data.get("account")
        session = data.get("session")
        return cls(
            device_uuid=str(uuid.UUID(data["device_uuid"])),
            linked=bool(data.get("linked", False)),
            linked_at=int(data.get("linked_at", 0)),
            credential=_credential(data.get("credential")),
            account=AccountInfo.from_dict(account) if account else None,
            session=SessionToken.from_dict(session) if session else None,
            api_bearer=_credential(data.get("api_bearer")),
        )

    def __repr__(self) -> str:
        return (
            f"LinkState(device={self.device_uuid}, linked={self.linked}, "
            f"credential={self.credential!r}, account={self.account!r}, "
            f"session={self.session!r}, api_bearer={self.api_bearer!r})"
        )


def _credential_dict(credential: Optional[Credential]) -> Optional[dict]:
    if credential is None:
        return None
    return {"kind": credential.kind.value, "token": credential.token, "exp": credential.exp}


def _credential(data: Optional[dict]) -> Optional[Credential]:
    if not data:
        return None
    return Credential(
        kind=CredentialKind(data["kind"]),
        token=str(data["token"]),
        exp=int(data.get("exp", 0)),
    )


class LinkStore:
    """Reads and writes the LinkState file."""

    def __init__(self, path: str):
        self.path = path

    def load_or_create(self) -> LinkState:
        """The stored state, or a new unlinked identity saved for next time.

        A file that cannot be parsed is set aside, and a new identity starts
        unlinked: its lock cannot be honoured without knowing what it held.

        @throw OSError when the file exists but cannot be read.
        """
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                return LinkState.from_dict(json.load(file))
        except FileNotFoundError:
            pass
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            # AttributeError: well-formed JSON that is not an object, e.g. null.
            self._set_aside(type(exc).__name__)

        state = LinkState(device_uuid=str(uuid.uuid4()))
        try:
            self.save(state)
        except OSError as exc:
            logger.warning(
                "Cannot save the Qobuz Connect identity to %s (%s); "
                "this player's device id will change on restart",
                self.path,
                exc.strerror or type(exc).__name__,
            )
        return state

    def save(self, state: LinkState) -> None:
        directory = os.path.dirname(self.path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
        fd, temp_path = tempfile.mkstemp(dir=directory, prefix=".connect-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                os.fchmod(file.fileno(), 0o600)
                json.dump(state.to_dict(), file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, self.path)
        except BaseException:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _set_aside(self, reason: str) -> None:
        aside = f"{self.path}.corrupt-{int(time.time())}"
        try:
            os.replace(self.path, aside)
            logger.warning(
                "Qobuz Connect state was unreadable (%s); moved it to %s and started unlinked",
                reason,
                aside,
            )
        except OSError as exc:
            logger.warning(
                "Qobuz Connect state was unreadable (%s) and could not be moved aside (%s)",
                reason,
                exc.strerror or type(exc).__name__,
            )
