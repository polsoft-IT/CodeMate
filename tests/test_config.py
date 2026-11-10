from pathlib import Path

import pytest

from src.config import AppConfig


def test_legacy_config_file_roundtrip(tmp_path):
    path = tmp_path / "baza_skryptow.cfg"
    config = AppConfig.from_dict({
        "db_path": "scripts.json",
        "timeout": "120",
        "git_auto_push": "1",
        "language": "en",
    })

    config.save_to_file(path)
    restored = AppConfig.load_from_file(path)

    assert restored.db_path == "scripts.json"
    assert restored.timeout == 120
    assert restored.git_auto_push is True
    assert restored.language == "en"


def test_settings_environment_prefix_and_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "CODEMATE_TIMEOUT=135\nCODEMATE_GIT_AUTO_PUSH=1\n",
        encoding="utf-8",
    )

    config = AppConfig()

    assert config.timeout == 135
    assert config.git_auto_push is True


@pytest.mark.parametrize("call", [
    lambda: AppConfig.validate_backup_count(-1),
    lambda: AppConfig.validate_backup_count(11),
    lambda: AppConfig.validate_timeout(0),
    lambda: AppConfig.validate_timeout(3601),
    lambda: AppConfig.validate_font_size(6),
    lambda: AppConfig.validate_font_size(29),
])
def test_numeric_field_validators_reject_out_of_range_values(call):
    # Ograniczenia Field(ge/le) przechwytują błędy wcześniej — wołamy
    # walidatory wprost, aby pokryć ich gałęzie raise.
    with pytest.raises(ValueError):
        call()


def test_load_from_file_returns_defaults_when_read_fails(tmp_path, monkeypatch):
    import configparser

    def broken_read(self, *args, **kwargs):
        raise OSError("unreadable")

    monkeypatch.setattr(configparser.ConfigParser, "read", broken_read)
    config = AppConfig.load_from_file(tmp_path / "baza_skryptow.cfg")
    assert isinstance(config, AppConfig)
