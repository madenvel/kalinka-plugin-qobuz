from typing import ClassVar
from pydantic import Field, ConfigDict
from kalinka_plugin_sdk.module_config import ModuleConfig
from enum import Enum


class QobuzAudioFormat(str, Enum):
    MP3 = "MP3 320kbps"
    CD = "CD 16-bit 44.1KHz"
    HIRES_96 = "Hi-Res 24-bit 96KHz"
    HIRES_192 = "Hi-Res 24-bit 192KHz"


class QobuzConfig(ModuleConfig):
    """Qobuz input module settings."""

    model_config = ConfigDict(use_enum_values=True)

    __module_icon__: ClassVar[str] = "music_note_outlined"
    __module_icon_color__: ClassVar[str] = "#C9A96A"  # gold
    __preview_fields__: ClassVar[list[str]] = ["format"]

    name: str = Field(default="qobuz", title="Qobuz", frozen=True, exclude=True)
    user_auth_token: str = Field(
        default="",
        title="User auth token",
        description=(
            "Qobuz X-User-Auth-Token. Obtain from the web app: sign in at "
            "play.qobuz.com, then copy the token from any authenticated "
            "request header in the browser devtools Network tab."
        ),
        json_schema_extra={"widget": "password", "importance": "simple"},
    )
    format: QobuzAudioFormat = Field(
        default=QobuzAudioFormat.HIRES_192,
        title="Audio quality",
        json_schema_extra={"importance": "simple"},
    )
