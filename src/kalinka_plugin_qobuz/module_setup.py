import asyncio
import logging
from typing import Optional
from kalinka_plugin_sdk import (
    PlayQueueEventType,
    PlaybackStateChangedEvent,
    RequestMoreTracksEvent,
    TracksAddedEvent,
    TracksRemovedEvent,
)
from kalinka_plugin_sdk.plugin import InputPluginContext, InputModulePlugin
from kalinka_plugin_sdk.inputmodule import InputModule

from .config_model import QobuzConfig
from .qobuz_autoplay import QobuzAutoplay
from .qobuz_reporter import QobuzReporter
from .qobuz import QobuzInputModule, get_client

logger = logging.getLogger(__name__.split(".")[-1])


class KalinkaPluginQobuz(InputModulePlugin):
    REQUIRES_SDK = ">=1,<2"
    PLUGIN_ID = "qobuz"
    CONFIG_MODEL = QobuzConfig

    def __init__(self):
        self.reporter = None
        self.interface: Optional[InputModule] = None
        self._qobuz_tasks = None

    def module_name(self) -> str:
        return "Qobuz Input Module"

    def get_interface(self) -> Optional[InputModule]:
        return self.interface

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
                    if isinstance(item, RequestMoreTracksEvent):
                        await autoplay.add_recommendation(item)
                    elif isinstance(item, TracksAddedEvent):
                        autoplay.add_tracks(item)
                    elif isinstance(item, TracksRemovedEvent):
                        autoplay.remove_tracks(item)
                    elif isinstance(item, PlaybackStateChangedEvent):
                        self.reporter.on_state_changed(item)

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
        config = QobuzConfig(**context.config.model_dump())
        client = await get_client(config)
        self.interface = QobuzInputModule(config, client)
        self._qobuz_tasks = asyncio.create_task(self._setup_jobs(client, context))

    async def shutdown(self):
        if self._qobuz_tasks:
            self._qobuz_tasks.cancel()
            try:
                await self._qobuz_tasks
            except asyncio.CancelledError:
                pass

        if self.reporter:
            await self.reporter.shutdown()
