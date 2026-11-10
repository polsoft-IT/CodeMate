"""
Testy powiadomień systemowych (poz. 11 planu działania).

Sprawdzają bezpieczną degradację backendu ``plyer`` oraz pole
``notify_enabled`` w modelu konfiguracji i CFG_KEYS.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from src import notify
from src.config import AppConfig


class TestNotifyBackend:
    """Warstwa natywnych powiadomień (plyer) z degradacją."""

    def test_available_returns_bool(self):
        assert isinstance(notify.notify_available(), bool)

    def test_send_without_backend(self, monkeypatch):
        monkeypatch.setattr(notify, "_PLYER_OK", False)
        monkeypatch.setattr(notify, "_notification", None)
        assert notify.send_native("t", "m") is False

    def test_send_backend_error(self, monkeypatch):
        class _Boom:
            @staticmethod
            def notify(**_kwargs):
                raise RuntimeError("brak backendu")

        monkeypatch.setattr(notify, "_PLYER_OK", True)
        monkeypatch.setattr(notify, "_notification", _Boom)
        assert notify.send_native("t", "m") is False

    def test_send_success(self, monkeypatch):
        calls = {}

        class _Fake:
            @staticmethod
            def notify(**kwargs):
                calls.update(kwargs)

        monkeypatch.setattr(notify, "_PLYER_OK", True)
        monkeypatch.setattr(notify, "_notification", _Fake)
        assert notify.send_native("Tytuł", "Treść", timeout=5, app_name="App") is True
        assert calls["title"] == "Tytuł"
        assert calls["message"] == "Treść"
        assert calls["timeout"] == 5
        assert calls["app_name"] == "App"

    def test_module_defaults(self):
        assert notify.NOTIFY_TIMEOUT > 0
        assert notify.NOTIFY_APP_NAME


class TestConfigNotify:
    """Pole ``notify_enabled`` w CFG_KEYS i modelu konfiguracji."""

    def test_cfg_keys_has_notify(self):
        assert bs.CFG_KEYS.get("notify_enabled") == "1"

    def test_default_enabled(self):
        assert AppConfig().notify_enabled is True

    def test_roundtrip_off(self):
        cfg = AppConfig.from_dict({"notify_enabled": "0"})
        assert cfg.notify_enabled is False
        assert cfg.to_dict()["notify_enabled"] == "0"

    def test_roundtrip_on(self):
        cfg = AppConfig.from_dict({"notify_enabled": "1"})
        assert cfg.notify_enabled is True
        assert cfg.to_dict()["notify_enabled"] == "1"


class TestNotifyI18n:
    """Klucze i18n powiadomień dostępne w obu językach."""

    @pytest.mark.parametrize("key", [
        "ust_sec_notify", "ust_notify_enabled",
        "notify_title", "notify_done_ok", "notify_done_err",
    ])
    def test_key_present(self, key):
        assert key in bs._UI_PL
        assert key in bs.TRANSLATIONS

    def test_message_format_ok(self):
        txt = bs._t("notify_done_ok", nazwa="demo", czas="1.2")
        assert "demo" in txt and "1.2" in txt

    def test_error_format_ok(self):
        txt = bs._t("notify_done_err", nazwa="demo", rc=3, czas="0.5")
        assert "demo" in txt and "3" in txt
