import asyncio
import logging
from typing import ClassVar, Optional
from kalinka_plugin_sdk import (
    DynamicFieldDecl,
    PlayQueueEventType,
    PlaybackStateChangedEvent,
    RequestMoreTracksEvent,
    TracksAddedEvent,
    TracksRemovedEvent,
)
from kalinka_plugin_sdk.module_health import ModuleHealthState, ModuleState
from kalinka_plugin_sdk.plugin import InputPluginContext, InputModulePlugin
from kalinka_plugin_sdk.inputmodule import InputModule

from .auth import Credential, QobuzAuth, TokenHolder
from .config_model import QobuzConfig
from .connect.pairing import PairingService, default_device_name
from .connect.store import LinkStore, default_store_path
from .qobuz_autoplay import QobuzAutoplay
from .qobuz_reporter import QobuzReporter
from .qobuz import QobuzClient, QobuzInputModule

logger = logging.getLogger(__name__.split(".")[-1])

STATUS_FIELD = "connect_status"


class KalinkaPluginQobuz(InputModulePlugin):
    REQUIRES_SDK = ">=3,<4"
    PLUGIN_ID = "qobuz"
    CONFIG_MODEL = QobuzConfig
    DYNAMIC_FIELDS: ClassVar[dict[str, DynamicFieldDecl]] = {
        STATUS_FIELD: DynamicFieldDecl(
            section_id="",
            label="Qobuz account",
            widget="rich_text",
            value_type="str",
        ),
    }

    def __init__(self):
        self.reporter = None
        self.interface: Optional[InputModule] = None
        self._qobuz_tasks = None
        self._client: Optional[QobuzClient] = None
        self._pairing: Optional[PairingService] = None

    def get_interface(self) -> Optional[InputModule]:
        return self.interface

    async def get_state(self) -> ModuleState:
        if self._pairing is None:
            return ModuleState(state=ModuleHealthState.READY)
        return self._pairing.health()

    async def resolve_dynamic_field(self, path: str):
        if path != STATUS_FIELD:
            raise KeyError(path)
        if self._pairing is None:
            return "Qobuz is not running."
        return self._pairing.status_markdown()

    async def _setup_jobs(
        self,
        client,
        context: InputPluginContext,
    ):
        if self.interface is None:
            return

        autoplay = QobuzAutoplay(
            qobuz_client=client,
            playqueue=context.playqueue,
            track_browser=self.interface,
        )
        self.reporter = QobuzReporter(client)

        try:
            async with context.listener.stream(
                [
                    PlayQueueEventType.RequestMoreTracks,
                    PlayQueueEventType.TracksAdded,
                    PlayQueueEventType.TracksRemoved,
                    PlayQueueEventType.PlaybackStateChanged,
                ]
            ) as stream:  # pyright: ignore[reportGeneralTypeIssues]
                async for item in stream:
                    try:
                        if isinstance(item, RequestMoreTracksEvent):
                            await autoplay.add_recommendation(item)
                        elif isinstance(item, TracksAddedEvent):
                            autoplay.add_tracks(item)
                        elif isinstance(item, TracksRemovedEvent):
                            autoplay.remove_tracks(item)
                        elif isinstance(item, PlaybackStateChangedEvent):
                            self.reporter.on_state_changed(item)
                    except Exception as e:
                        # One failed event (Qobuz unlinked, a network blip) must
                        # not stop autoplay and reporting for the whole session.
                        logger.warning("Qobuz could not handle %s: %s", type(item).__name__, e)

        except asyncio.CancelledError:
            logger.info("Playback state listener cancelled")
            if self.reporter:
                await self.reporter.shutdown()
            return
        except Exception as e:
            logger.error(f"Error in playback state listener: {e}")
            raise

        logger.info("Playback state listener stopped")

    async def setup(
        self,
        context: InputPluginContext,
    ) -> None:
        # No network here: an unlinked player, or one booting before its
        # network is up, must still come up and show how to link Qobuz.
        config = QobuzConfig(**context.config.model_dump())
        holder = TokenHolder()
        self._client = QobuzClient(auth=QobuzAuth(holder, on_unauthorized=self._renew_after_401))
        self._pairing = PairingService(
            client=self._client,
            holder=holder,
            store=LinkStore(default_store_path()),
            device_name=config.connect_device_name.strip() or default_device_name(),
            port=config.connect_port,
        )
        if config.unpair:
            self._pairing.forget_link()
        self.interface = QobuzInputModule(config, self._client)
        self._pairing.start()
        self._qobuz_tasks = asyncio.create_task(self._setup_jobs(self._client, context))

    async def _renew_after_401(self, credential: Credential) -> bool:
        if self._pairing is None:
            return False
        return await self._pairing.renew_after_401(credential)

    async def shutdown(self):
        if self._pairing:
            await self._pairing.stop()

        if self._qobuz_tasks:
            self._qobuz_tasks.cancel()
            try:
                await self._qobuz_tasks
            except asyncio.CancelledError:
                pass

        if self.reporter:
            await self.reporter.shutdown()

        if self._client:
            await self._client.aclose()
