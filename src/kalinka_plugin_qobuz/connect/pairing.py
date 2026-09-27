"""Links this player to a Qobuz account through the Qobuz app, and keeps it linked.

While unlinked, the player advertises itself and accepts one handoff at a
time. A handed-over credential is checked on a separate client and only then
replaces anything. Once linked, pairing closes and stays closed, across
restarts and expiry, until the user unpairs.

Nothing here reaches the play queue or playback: a handoff only ever yields a
credential for the REST client.
"""

import asyncio
import enum
import logging
import socket
import time
from importlib import metadata
from typing import Awaitable, Callable, Optional

import httpx
from kalinka_plugin_sdk.module_health import ModuleHealthState, ModuleState

from .. import auth
from ..account import AccessCheckError, Validated, describe_failure, validate_account_access
from ..auth import Credential, CredentialKind, QobuzAuth, TokenHolder
from ..qobuz import AppBundle, QobuzClient, load_app_bundle
from .discovery import Advert, Advertiser, NoAddressesError, ZeroconfAdvertiser
from .handoff import Handoff, HandoffError, describe, parse_handoff
from .receiver import HandoffReceiver
from .refresh import TokenRefresher, renewable
from .store import LinkState, LinkStore

logger = logging.getLogger(__name__.split(".")[-1])

BUNDLE_RETRY_MAX_S = 60
RESTORE_RETRY_MAX_S = 300
WINDOW_RETRY_S = 30

_UNPAIR = "*Unpair Qobuz account on next restart*"


class _WindowUnavailable(Exception):
    """Pairing cannot be offered; the message says why, for the status page."""


class Phase(str, enum.Enum):
    STARTING = "starting"
    WAITING = "waiting"
    VALIDATING = "validating"
    LINKED = "linked"
    RECONNECTING = "reconnecting"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"


def default_device_name() -> str:
    return f"Kalinka ({socket.gethostname()})"


def _sdk_version() -> str:
    try:
        return f"kalinka-qobuz-{metadata.version('kalinka-plugin-qobuz')}"
    except metadata.PackageNotFoundError:
        return "kalinka-qobuz"


class PairingService:
    """Owns the link between this player and one Qobuz account.

    @param client The shared REST client; it only ever receives validated credentials.
    @param holder The shared client's credential source.
    @note Every change of phase or credential happens in a method that does not
        await, so on the event loop no handoff, renewal or validation result
        can interleave with it.
    """

    def __init__(
        self,
        *,
        client: QobuzClient,
        holder: TokenHolder,
        store: LinkStore,
        device_name: str,
        port: int,
        load_bundle: Callable[[], Awaitable[AppBundle]] = load_app_bundle,
        validate: Callable[[QobuzClient, TokenHolder], Awaitable[Validated]] = validate_account_access,
        make_probe_client: Callable[[TokenHolder], QobuzClient] = (
            lambda holder: QobuzClient(auth=QobuzAuth(holder))
        ),
        make_receiver: Callable[..., HandoffReceiver] = (
            lambda handlers, port: HandoffReceiver(handlers, port=port)
        ),
        advertiser: Optional[Advertiser] = None,
        make_refresher: Callable[..., TokenRefresher] = TokenRefresher,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._client = client
        self._holder = holder
        self._store = store
        self._device_name = device_name
        self._port = port
        self._load_bundle = load_bundle
        self._validate = validate
        self._make_probe_client = make_probe_client
        self._make_receiver = make_receiver
        self._advertiser = advertiser or ZeroconfAdvertiser()
        self._make_refresher = make_refresher
        self._clock = clock
        self._sleep = sleep

        # Read before anything listens, so a stored link keeps pairing closed.
        self._link: LinkState = store.load_or_create()
        self._phase = Phase.STARTING
        self._detail = ""
        self._last_failure = ""
        self._bundle: Optional[AppBundle] = None
        self._attempt = 0
        self._pending: Optional[Handoff] = None
        self._task: Optional[asyncio.Task] = None
        self._validation: Optional[asyncio.Task] = None
        self._receiver: Optional[HandoffReceiver] = None
        self._advertising = False
        self._refresher: Optional[TokenRefresher] = None
        self._refresh_http: Optional[httpx.AsyncClient] = None
        self._stopped = False

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def link(self) -> LinkState:
        return self._link

    def forget_link(self) -> None:
        """Unpair. Called before start(), when the user armed Unpair.

        @throw OSError when the unlinked state cannot be stored, so setup
            fails instead of pretending the unpair happened.
        """
        if not self._link.linked:
            logger.info("Unpair requested, but no Qobuz account is linked")
            return
        unlinked = self._link.unlinked()
        self._store.save(unlinked)
        self._link = unlinked
        logger.warning("Qobuz account unpaired; this player will wait for a new pairing")

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="qobuz-connect")

    async def stop(self) -> None:
        self._stopped = True
        tasks = [task for task in (self._task, self._validation) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._refresher is not None:
            await self._refresher.stop()
        await self._close_window()
        if self._refresh_http is not None:
            await self._refresh_http.aclose()

    async def renew_after_401(self, credential: Credential) -> bool:
        refresher = self._refresher
        if refresher is None:
            return False
        return await refresher.on_unauthorized(credential)

    def display_info(self) -> dict:
        return {
            "type": "SPEAKER",
            "friendly_name": self._device_name,
            "model_display_name": "Kalinka",
            "brand_display_name": "Kalinka",
            "serial_number": self._link.device_uuid,
            "max_audio_quality": "HIRES_L3",
        }

    def connect_info(self) -> dict:
        return {
            "current_session_id": self._pending.session_id if self._pending else "",
            "app_id": self._bundle.app_id if self._bundle else "",
        }

    async def handoff(self, body: bytes) -> tuple[int, dict]:
        try:
            handoff = parse_handoff(body, self._clock())
        except HandoffError as exc:
            logger.warning("Qobuz Connect handoff refused: %s", exc)
            return 400, {"error": str(exc)}
        logger.info("Qobuz Connect handoff: %s", describe(handoff))
        return self._accept(handoff)

    def _accept(self, handoff: Handoff) -> tuple[int, dict]:
        if self._phase is Phase.VALIDATING and self._pending is not None:
            if self._pending.same_as(handoff):
                return 200, {}
            logger.warning("Qobuz Connect handoff refused: another pairing is in progress")
            return 400, {"error": "pairing already in progress"}
        if self._phase is not Phase.WAITING or self._stopped:
            logger.warning("Qobuz Connect handoff refused in phase %s", self._phase.value)
            return 400, {"error": "device is not accepting pairing"}
        self._attempt += 1
        self._pending = handoff
        self._set(Phase.VALIDATING)
        self._validation = asyncio.create_task(
            self._validate_handoff(self._attempt, handoff), name="qobuz-connect-validate"
        )
        # Acknowledged at once, as other receivers do; the outcome shows in the status.
        return 200, {}

    def status_markdown(self) -> str:
        phase, name = self._phase, self._device_name
        if phase is Phase.STARTING:
            return f"**Starting…** {self._detail or 'Loading Qobuz app information.'}"
        if phase is Phase.WAITING:
            text = (
                "**Not linked.** On this network, open the Qobuz app, open its "
                f"device picker and choose *{name}*."
            )
            if self._last_failure:
                text += f" Last attempt failed: {self._last_failure}."
            return text
        if phase is Phase.VALIDATING:
            return "**Pairing…** Checking the Qobuz account the app handed over."
        if phase is Phase.UNAVAILABLE:
            return f"**Pairing unavailable:** {self._detail}. Retrying."
        who = self._account_text()
        if phase is Phase.LINKED:
            return (
                f"**Linked** as {who}. {self._renewal_text()}"
                f"To link another account, turn on {_UNPAIR} and apply."
            )
        if phase is Phase.RECONNECTING:
            text = f"**Reconnecting** to Qobuz as {who}…"
            if self._detail:
                text += f" Last check failed: {self._detail}."
            return text
        return (
            f"**Link expired** ({self._detail}). Turn on {_UNPAIR} and apply, "
            f"then choose *{name}* in the Qobuz app again."
        )

    def health(self) -> ModuleState:
        phase = self._phase
        if phase is Phase.LINKED:
            return ModuleState(state=ModuleHealthState.READY)
        waiting = f"Not linked: choose {self._device_name} in the Qobuz app."
        if self._last_failure:
            waiting += f" Last attempt failed: {self._last_failure}."
        messages = {
            Phase.STARTING: "Starting." if self._link.linked else "Not linked yet: starting pairing.",
            Phase.WAITING: waiting,
            Phase.VALIDATING: "Pairing with the Qobuz app.",
            Phase.RECONNECTING: "Reconnecting to Qobuz.",
            Phase.EXPIRED: "The Qobuz link has expired: unpair, then pair again.",
            Phase.UNAVAILABLE: f"Pairing unavailable: {self._detail}.",
        }
        # Without an account Qobuz has nothing to offer, so it reports itself
        # unavailable; a stored link that is starting or reconnecting is on its way.
        on_its_way = self._link.linked and phase in (Phase.STARTING, Phase.RECONNECTING)
        return ModuleState(
            state=ModuleHealthState.WARNING if on_its_way else ModuleHealthState.ERROR,
            message=messages[phase],
        )

    def _account_text(self) -> str:
        account = self._link.account
        if account is None:
            return "an unknown account"
        who = account.display_name or f"user {account.user_id}"
        return f"{who} ({account.label})" if account.label else who

    def _renewal_text(self) -> str:
        credential = self._link.credential
        if credential is None or credential.kind is not CredentialKind.BEARER:
            return ""
        if not credential.exp:
            return "Qobuz gave no expiry for this link. "
        at = self._refresher.next_refresh_at if self._refresher else None
        if at is None:
            return ""
        return f"Renews itself around {time.strftime('%d %b %H:%M', time.localtime(at))}. "

    async def _run(self) -> None:
        self._bundle = await self._load_bundle_until_ready()
        self._client.configure_app(self._bundle.app_id, self._bundle.secrets)
        if self._link.linked:
            await self._restore()
        else:
            await self._open_window_until_ready()

    async def _load_bundle_until_ready(self) -> AppBundle:
        failures = 0
        while True:
            try:
                return await self._load_bundle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failures += 1
                delay = min(2 * failures, BUNDLE_RETRY_MAX_S)
                self._detail = "Waiting for the network to reach Qobuz."
                logger.warning(
                    "Qobuz web bundle load failed (%s); retrying in %ds",
                    type(exc).__name__,
                    delay,
                )
                await self._sleep(delay)

    async def _restore(self) -> None:
        link = self._link
        if link.credential is None or link.account is None:
            self._expire("the stored link is incomplete")
            return
        self._holder.install(link.credential)
        self._client.install_account(link.account)
        self._set(Phase.RECONNECTING)
        self._start_refresher()
        failures = 0
        while True:
            try:
                validated = await self._validate(self._client, self._holder)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._phase is not Phase.RECONNECTING:
                    return
                reason = describe_failure(exc)
                if (
                    isinstance(exc, AccessCheckError)
                    and exc.unauthorized
                    and not renewable(self._holder.credential)
                ):
                    self._expire(reason)
                    return
                failures += 1
                delay = min(2**failures, RESTORE_RETRY_MAX_S)
                self._detail = reason
                logger.warning("Qobuz link check failed (%s); retrying in %ds", reason, delay)
                await self._sleep(delay)
                continue
            self._confirm_restored(validated)
            return

    def _confirm_restored(self, validated: Validated) -> None:
        if self._phase is not Phase.RECONNECTING:
            return
        self._client.install_account(validated.account)
        current = self._link
        if validated.account != current.account or validated.credential != current.credential:
            updated = LinkState(
                device_uuid=current.device_uuid,
                linked=True,
                linked_at=current.linked_at,
                credential=validated.credential,
                account=validated.account,
            )
            try:
                self._store.save(updated)
                self._link = updated
            except OSError as exc:
                logger.error(
                    "Could not store the updated Qobuz link (%s)",
                    exc.strerror or type(exc).__name__,
                )
        self._set(Phase.LINKED)
        # The check may have swapped credentials under a running refresher,
        # which stops for good once it sees one it cannot renew.
        self._start_refresher()
        logger.info("Qobuz link restored for user %s", validated.account.user_id)

    async def _open_window_until_ready(self) -> None:
        while True:
            try:
                await self._open_window()
                return
            except asyncio.CancelledError:
                await self._close_window()
                raise
            except _WindowUnavailable as exc:
                await self._close_window()
                self._set(Phase.UNAVAILABLE, detail=str(exc))
                logger.warning(
                    "Qobuz Connect pairing unavailable (%s); retrying in %ds",
                    self._detail,
                    WINDOW_RETRY_S,
                )
                await self._sleep(WINDOW_RETRY_S)

    async def _open_window(self) -> None:
        self._receiver = self._make_receiver(self, self._port)
        try:
            await self._receiver.start()
        except OSError as exc:
            raise _WindowUnavailable(
                f"cannot listen on port {self._port} ({exc.strerror or type(exc).__name__})"
            ) from None
        advert = Advert(
            friendly_name=self._device_name,
            device_uuid=self._link.device_uuid,
            port=self._receiver.port,
            sdk_version=_sdk_version(),
        )
        try:
            await self._advertiser.start(advert)
        except NoAddressesError:
            raise _WindowUnavailable("no network address to advertise on") from None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise _WindowUnavailable(
                f"cannot advertise on the network ({type(exc).__name__})"
            ) from None
        self._advertising = True
        self._holder.clear(auth.NOT_LINKED)
        self._set(Phase.WAITING)

    async def _close_window(self) -> None:
        receiver, self._receiver = self._receiver, None
        try:
            if self._advertising:
                self._advertising = False
                try:
                    await self._advertiser.stop()
                except Exception as exc:
                    logger.warning("Stopping the Qobuz Connect advert failed: %s", type(exc).__name__)
        finally:
            # Detached above, so no later call would release the port.
            if receiver is not None:
                await receiver.stop()

    async def _validate_handoff(self, attempt: int, handoff: Handoff) -> None:
        probe_holder = TokenHolder()
        probe_holder.install(handoff.credential)
        probe: Optional[QobuzClient] = None
        try:
            # Inside the try: a failure here must still end VALIDATING, or
            # every later handoff would be refused as a pairing in progress.
            probe = self._make_probe_client(probe_holder)
            probe.configure_app(self._bundle.app_id, self._bundle.secrets)
            validated = await self._validate(probe, probe_holder)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._reject(attempt, describe_failure(exc))
            return
        finally:
            if probe is not None:
                await probe.aclose()
        if self._commit(attempt, validated, probe.sec):
            await self._close_window()

    def _reject(self, attempt: int, reason: str) -> None:
        if attempt != self._attempt or self._phase is not Phase.VALIDATING:
            return
        self._pending = None
        self._last_failure = reason
        self._set(Phase.WAITING)
        logger.warning("Qobuz Connect pairing failed: %s", reason)

    def _commit(self, attempt: int, validated: Validated, sec) -> bool:
        if attempt != self._attempt or self._phase is not Phase.VALIDATING or self._stopped:
            logger.info("Discarded a Qobuz Connect pairing that finished after it was superseded")
            return False
        link = LinkState(
            device_uuid=self._link.device_uuid,
            linked=True,
            linked_at=int(self._clock()),
            credential=validated.credential,
            account=validated.account,
        )
        try:
            self._store.save(link)
        except OSError as exc:
            self._reject(attempt, f"could not save the link ({exc.strerror or type(exc).__name__})")
            return False
        self._link = link
        self._pending = None
        self._last_failure = ""
        self._client.reset_caches()
        self._holder.install(validated.credential)
        self._client.install_account(validated.account)
        self._client.sec = sec
        self._set(Phase.LINKED)
        self._start_refresher()
        logger.info(
            "Qobuz account linked: user %s, %s, %s credential",
            validated.account.user_id,
            validated.account.label or "no subscription label",
            validated.credential.kind.value,
        )
        return True

    def _start_refresher(self) -> None:
        """Start renewal for a Bearer credential in force; restart it if it stopped."""
        credential = self._holder.credential
        if credential is None or credential.kind is not CredentialKind.BEARER:
            return
        if self._refresher is None:
            if self._refresh_http is None:
                self._refresh_http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
            self._refresher = self._make_refresher(
                holder=self._holder,
                http=self._refresh_http,
                app_id=self._bundle.app_id,
                persist=self._persist_renewed,
                on_expired=self._expire,
                clock=self._clock,
            )
        self._refresher.start()

    def _persist_renewed(self, credential: Credential) -> None:
        renewed = self._link.with_credential(credential)
        self._store.save(renewed)
        self._link = renewed

    def _expire(self, reason: str) -> None:
        if not self._link.linked or self._phase is Phase.EXPIRED:
            return
        self._holder.clear(auth.EXPIRED)
        self._set(Phase.EXPIRED, detail=reason)
        logger.warning("Qobuz link expired: %s. Unpair to pair again.", reason)

    def _set(self, phase: Phase, *, detail: str = "") -> None:
        self._detail = detail
        if phase is not self._phase:
            logger.info("Qobuz Connect: %s -> %s", self._phase.value, phase.value)
        self._phase = phase
