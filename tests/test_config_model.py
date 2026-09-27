"""The settings page: no token to paste, a one-shot Unpair, and a status card."""

from kalinka_plugin_qobuz.config_model import QobuzConfig
from kalinka_plugin_qobuz.module_setup import STATUS_FIELD, KalinkaPluginQobuz


def _extra(field: str) -> dict:
    return QobuzConfig.model_fields[field].json_schema_extra or {}


def test_there_is_no_token_to_paste():
    assert "user_auth_token" not in QobuzConfig.model_fields
    assert all(_extra(name).get("widget") != "password" for name in QobuzConfig.model_fields)
    assert all(_extra(name).get("setup") != "required" for name in QobuzConfig.model_fields)


def test_unpair_is_a_one_shot_switch_that_starts_off():
    assert _extra("unpair")["one_shot"] is True
    assert _extra("unpair")["importance"] == "simple"
    assert QobuzConfig().unpair is False


def test_the_device_name_is_a_regular_setting_and_the_port_an_expert_one():
    assert _extra("connect_device_name")["importance"] == "simple"
    assert "importance" not in _extra("connect_port")


def test_pairing_defaults():
    config = QobuzConfig()

    assert config.connect_port == 8183
    assert config.connect_device_name == ""


def test_an_old_saved_token_is_ignored_rather_than_fatal():
    config = QobuzConfig(user_auth_token="left-over-from-3.x")

    assert not hasattr(config, "user_auth_token")


def test_the_status_card_sits_at_the_module_root():
    field = KalinkaPluginQobuz.DYNAMIC_FIELDS[STATUS_FIELD]

    assert field.section_id == ""
    assert field.widget == "rich_text"
