"""
Testy motywów interfejsu (poz. 10 planu działania).

Sprawdzają spójność presetów palety, mapowanie kluczy kolorów, wiązanie
globalnych stałych oraz model konfiguracji (pole ``theme``).
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from src.config import AppConfig
from src.theme import (
    TAG_BG_KEYS,
    TAG_COLOR_KEYS,
    THEME_DEFAULT,
    THEME_ORDER,
    THEME_PRESETS,
    theme_names,
    theme_values,
)

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TestPresets:
    """Spójność presetów palety kolorów."""

    def test_default_in_order(self):
        assert THEME_DEFAULT in THEME_ORDER

    def test_order_values(self):
        assert THEME_ORDER == ("ciemny", "jasny", "kontrastowy")

    def test_names_helper(self):
        assert theme_names() == THEME_ORDER

    def test_presets_cover_order(self):
        assert set(THEME_PRESETS) == set(THEME_ORDER)

    def test_same_key_set(self):
        keys = [set(p) for p in THEME_PRESETS.values()]
        assert all(k == keys[0] for k in keys)

    def test_all_hex(self):
        for name, preset in THEME_PRESETS.items():
            for key, val in preset.items():
                assert _HEX_RE.match(val), f"{name}.{key} = {val!r}"

    def test_required_globals_present(self):
        for key in (
            "BG_DARK", "BG_PANEL", "BG_INPUT", "BG_TAB_ACT", "BG_TAB_INACT",
            "BG_SUBTAB_ACT", "BG_SUBTAB_INACT", "BG_ROW_ODD", "BG_ROW_EVEN",
            "BG_ROW_SEL", "FG_WHITE", "FG_GRAY", "FG_TEXT", "ACCENT_BLUE",
            "BORDER_CLR", "BTN_DARK", "BTN_HOVER",
        ):
            assert key in THEME_PRESETS[THEME_DEFAULT]

    def test_dark_matches_module_constants(self):
        dark = THEME_PRESETS["ciemny"]
        # Motyw ciemny odwzorowuje dotychczasowy wygląd (stałe z modułu głównego).
        assert dark["BG_DARK"] == "#1e2130"
        assert dark["FG_WHITE"] == "#e0e4f0"
        assert dark["ACCENT_BLUE"] == "#4a90d9"

    def test_theme_values_fallback(self):
        assert theme_values("nope") == THEME_PRESETS[THEME_DEFAULT]

    def test_theme_values_copy(self):
        first = theme_values("ciemny")
        first["BG_DARK"] = "#000000"
        assert THEME_PRESETS["ciemny"]["BG_DARK"] != "#000000"


class TestTagMapping:
    """Mapowanie tagów Treeview/Text na klucze kolorów."""

    def test_tag_keys_exist_in_presets(self):
        palette_keys = set(THEME_PRESETS[THEME_DEFAULT])
        for tag, key in TAG_COLOR_KEYS.items():
            assert key in palette_keys, f"{tag} → {key}"

    def test_bg_keys_are_palette_keys(self):
        palette_keys = set(THEME_PRESETS[THEME_DEFAULT])
        for key in TAG_BG_KEYS:
            assert key in palette_keys

    def test_core_tags_present(self):
        for tag in ("odd", "even", "sel", "ok", "err", "warn", "cykl", "osier"):
            assert tag in TAG_COLOR_KEYS


class TestBindGlobals:
    """Wiązanie globalnych stałych kolorów wg motywu."""

    @pytest.fixture(autouse=True)
    def _restore(self):
        keys = tuple(THEME_PRESETS[THEME_DEFAULT])
        saved = {k: getattr(bs, k) for k in keys if hasattr(bs, k)}
        missing = [k for k in keys if not hasattr(bs, k)]
        yield
        for k, v in saved.items():
            setattr(bs, k, v)
        for k in missing:
            if hasattr(bs, k):
                delattr(bs, k)

    def test_bind_light(self):
        bs._bind_theme_globals("jasny")
        assert bs.BG_DARK == THEME_PRESETS["jasny"]["BG_DARK"]
        assert bs.FG_WHITE == THEME_PRESETS["jasny"]["FG_WHITE"]

    def test_bind_returns_palette(self):
        vals = bs._bind_theme_globals("kontrastowy")
        assert vals["BG_DARK"] == THEME_PRESETS["kontrastowy"]["BG_DARK"]
        assert bs.BG_DARK == vals["BG_DARK"]

    def test_apply_hl_palette_light(self):
        saved = bs._HL_COLORS
        try:
            bs._apply_hl_palette("jasny")
            assert bs._HL_COLORS
            bs._apply_hl_palette("ciemny")
            assert bs._HL_COLORS
        finally:
            bs._HL_COLORS = saved


class TestConfigTheme:
    """Pole ``theme`` w modelu konfiguracji i CFG_KEYS."""

    def test_cfg_keys_has_theme(self):
        assert bs.CFG_KEYS.get("theme") == "ciemny"

    def test_default_theme(self):
        assert AppConfig().theme == "ciemny"

    def test_theme_roundtrip(self):
        cfg = AppConfig.from_dict({"theme": "jasny"})
        assert cfg.theme == "jasny"
        assert cfg.to_dict()["theme"] == "jasny"

    def test_theme_validation(self):
        assert AppConfig.from_dict({"theme": "bogus"}).theme == "ciemny"

    def test_theme_labels_complete(self):
        for name in THEME_ORDER:
            assert name in bs._THEME_PL_LABELS
        for name in THEME_ORDER:
            assert _t_theme(name)

    def test_custom_colors_override_theme_palette(self):
        values = bs._theme_values_with_custom("jasny", {
            "bg_tab_act": "#123456",
            "bg_tab_inact": "#abcdef",
            "fg_text": "#fedcba",
        })

        assert values["BG_TAB_ACT"] == "#123456"
        assert values["BG_TAB_INACT"] == "#abcdef"
        assert values["FG_TEXT"] == "#fedcba"
        assert values["BG_DARK"] == THEME_PRESETS["jasny"]["BG_DARK"]

    def test_invalid_custom_colors_are_ignored(self):
        values = bs._theme_values_with_custom("ciemny", {
            "bg_tab_act": "red",
            "fg_text": "#12xx56",
        })

        assert values["BG_TAB_ACT"] == THEME_PRESETS["ciemny"]["BG_TAB_ACT"]
        assert values["FG_TEXT"] == THEME_PRESETS["ciemny"]["FG_TEXT"]

    def test_apply_saved_appearance_updates_fonts_and_main_tabs(self, monkeypatch):
        class FakeButton:
            def __init__(self):
                self.options = {}

            def configure(self, **options):
                self.options.update(options)

        class FakeMouse:
            def _apply_zoom(self):
                self.zoom_applied = True

        class FakeApp:
            _apply_main_tab_colors = bs.CodeMate._apply_main_tab_colors

            def __init__(self):
                self._theme = "ciemny"
                self._theme_vals = theme_values("ciemny")
                self._cfg = {
                    "font_family": "Fira Code",
                    "font_size": "13",
                    "bg_tab_act": "#123456",
                    "bg_tab_inact": "#abcdef",
                }
                self._main_active_idx = 1
                self._main_btns = [FakeButton(), FakeButton()]
                self._mouse = FakeMouse()

            def _recolor_widgets(self, _widget, cmap):
                self.color_map = cmap

            def _style_ttk_theme(self):
                pass

            def _reapply_highlight_tags(self):
                pass

            def _apply_widget_font_family(self, _widget, family):
                self.applied_font_family = family

            def _apply_list_appearance(self, _config=None):
                pass

        for name in ("FONT_FAMILY", "FONT_UI", "FONT_BOLD", "FONT_MONO", "FONT_TITLE"):
            monkeypatch.setattr(bs, name, getattr(bs, name))

        app = FakeApp()
        bs.CodeMate._apply_appearance_settings(app)

        assert bs.FONT_FAMILY == "Fira Code"
        assert bs.FONT_MONO == ("Fira Code", 10)
        assert app._mouse.FONT_FAMILY == "Fira Code"
        assert app._mouse._editor_font_size == 13
        assert app._mouse.zoom_applied
        assert app._main_btns[0].options["bg"] == "#abcdef"
        assert app._main_btns[1].options["bg"] == "#123456"

    def test_settings_preview_does_not_save_form_values(self):
        class FakeField:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class FakeApp:
            def __init__(self):
                self._cfg = {"font_family": "Consolas", "font_size": "10"}
                self._ust_appearance_fields = (
                    FakeField("Fira Code"), FakeField("14"),
                    FakeField("#123456"), FakeField("#abcdef"), FakeField("#fedcba"))

            def _apply_appearance_settings(self, config):
                self.applied_preview = config

            def _apply_list_appearance(self, _config=None):
                pass

        app = FakeApp()
        bs.CodeMate._ust_preview_appearance(app)

        assert app._cfg == {"font_family": "Consolas", "font_size": "10"}
        assert app.applied_preview["font_family"] == "Fira Code"
        assert app.applied_preview["font_size"] == "14"
        assert app._appearance_preview["bg_tab_act"] == "#123456"


def _t_theme(name: str) -> str:
    """Pomocniczo: pobiera etykietę motywu z warstwy i18n."""
    return bs._t("theme_" + name)
