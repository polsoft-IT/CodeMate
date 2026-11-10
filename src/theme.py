# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł:   src/theme.py
# Opis:    Presety motywów (palety kolorów) interfejsu CodeMate
# Wersja:  1.0.0
# Autor:   Sebastian Januchowski
# Firma:   polsoft.ITS(TM) Group
# E-mail:  polsoft.its@mail.com
# GitHub:  https://github.com/polsoft-it
# ──────────────────────────────────────────────────────────────────────────────
"""Presety motywów interfejsu.

Każdy preset to słownik ``nazwa koloru → wartość hex``. Nazwy odpowiadają
globalnym stałym kolorów w ``baza_skryptow.py`` (``BG_*``, ``FG_*``,
``ACCENT_BLUE``, ``BORDER_CLR``, ``BTN_*``, ``TOOLTIP_*``) oraz dodatkowym
kolorom semantycznym używanym w tagach (``SUCCESS``, ``ERROR``, ``WARN`` itd.).

Motyw ``ciemny`` odwzorowuje dotychczasowy (domyślny) wygląd aplikacji 1:1.
Przełączenie motywu tylko przypisuje te wartości do globalnych stałych i
przebudowuje kolory istniejących widżetów — bez restartu aplikacji.
"""

from typing import Dict, Tuple

# Domyślny motyw (obecny wygląd aplikacji).
THEME_DEFAULT = "ciemny"

# Kolejność presetów (do prezentacji w UI).
THEME_ORDER: Tuple[str, ...] = ("ciemny", "jasny", "kontrastowy")

# Klucze kolorów wyłączone z automatycznego przemapowania widżetów
# (używane wyłącznie przez dedykowane tagi — patrz TAG_COLOR_KEYS).
CMAP_EXCLUDE: Tuple[str, ...] = ("ERRLINE_FG",)

# Tagi Treeview/Text i przypisane im klucze kolorów (do przekolorowania na żywo).
TAG_COLOR_KEYS: Dict[str, str] = {
    # tła
    "odd":           "BG_ROW_ODD",
    "even":          "BG_ROW_EVEN",
    "sel":           "BG_ROW_SEL",
    "grupa":         "BG_PANEL",
    "match":         "MATCH_BG",
    "fr_match":      "FR_MATCH_BG",
    "lint_err":      "LINT_ERR_BG",
    "lint_warn":     "LINT_WARN_BG",
    "find_hl":       "FIND_HL_BG",
    "errline":       "ERRLINE_BG",
    # kolory tekstu
    "cykl":          "ERROR",
    "osier":         "WARN",
    "high":          "ERROR",
    "medium":        "WARN",
    "low":           "INFO_BLUE",
    "fixed":         "SUCCESS",
    "A":             "SUCCESS",
    "B":             "INFO_BLUE",
    "C":             "WARN",
    "D":             "ERROR",
    "ok":            "SUCCESS",
    "warn":          "WARN",
    "err":           "ERROR",
    "error":         "ERROR",
    "add":           "SUCCESS",
    "del":           "ERROR2",
    "cmd":           "INFO_BLUE",
    "out":           "FG_TEXT",
    "info":          "FG_GRAY",
    "inf":           "WARN3",
    "tag":           "WARN2",
    "head":          "ACCENT_BLUE",
    "hdr":           "INFO_BLUE",
    "tpl":           "FG_WHITE",
    "mounted":       "SUCCESS",
    "unmounted":     "FG_GRAY",
    "hl_string_doc": "DOC",
}

# Tagi, których klucz koloru ustawiany jest jako tło (pozostałe = kolor tekstu).
TAG_BG_KEYS: Tuple[str, ...] = (
    "BG_ROW_ODD", "BG_ROW_EVEN", "BG_ROW_SEL", "BG_PANEL", "MATCH_BG",
    "FR_MATCH_BG", "LINT_ERR_BG", "LINT_WARN_BG", "FIND_HL_BG", "ERRLINE_BG",
)

# ── Presety palet ─────────────────────────────────────────────────────────────
THEME_PRESETS: Dict[str, Dict[str, str]] = {
    # ── Ciemny (obecny wygląd aplikacji) ──────────────────────────────────────
    "ciemny": {
        "BG_DARK":         "#1e2130",
        "BG_PANEL":        "#252839",
        "BG_INPUT":        "#2a2d3e",
        "BG_TAB_ACT":      "#1e2130",
        "BG_TAB_INACT":    "#2a2d3e",
        "BG_SUBTAB_ACT":   "#2e3350",
        "BG_SUBTAB_INACT": "#252839",
        "BG_ROW_ODD":      "#252839",
        "BG_ROW_EVEN":     "#2a2d3e",
        "BG_ROW_SEL":      "#2e4a7a",
        "FG_WHITE":        "#e0e4f0",
        "FG_GRAY":         "#8a8fa8",
        "FG_TEXT":         "#c8d0f0",
        "FG_HIGHLIGHT":    "#82aaff",
        "ACCENT_BLUE":     "#4a90d9",
        "BORDER_CLR":      "#3a3f58",
        "BTN_DARK":        "#2e3248",
        "BTN_HOVER":       "#3a3f5c",
        "BTN_OK":          "#2f6b3f",
        "BTN_OK_HOVER":    "#3d8a52",
        "BTN_ERR":         "#603030",
        "BTN_ERR_HOVER":   "#804040",
        "BTN_ACCENT":      "#4a90d9",
        "TOOLTIP_BG":      "#3a3f58",
        "TOOLTIP_FG":      "#c8d0f0",
        "TOOLTIP_INNER_BG": "#1e2130",
        # kolory semantyczne / nakładki
        "SUCCESS":         "#6dde84",
        "ERROR":           "#e07070",
        "ERROR2":          "#e05c5c",
        "WARN":            "#f0c050",
        "WARN2":           "#e0c040",
        "WARN3":           "#c8c040",
        "INFO_BLUE":       "#7ec8e3",
        "CHIP_BG":         "#3a4060",
        "CHIP_FG":         "#7ec8e3",
        "MATCH_BG":        "#2e4a2e",
        "FR_MATCH_BG":     "#3a5030",
        "LINT_ERR_BG":     "#4a2430",
        "LINT_WARN_BG":    "#3f3a24",
        "FIND_HL_BG":      "#5a4a1a",
        "ERRLINE_BG":      "#5a1f1f",
        "ERRLINE_FG":      "#ffffff",
        "DOC":             "#546e7a",
    },
    # ── Jasny ─────────────────────────────────────────────────────────────────
    "jasny": {
        "BG_DARK":         "#f4f5f7",
        "BG_PANEL":        "#e9ebf1",
        "BG_INPUT":        "#ffffff",
        "BG_TAB_ACT":      "#f4f5f7",
        "BG_TAB_INACT":    "#e2e5ec",
        "BG_SUBTAB_ACT":   "#d5dcf2",
        "BG_SUBTAB_INACT": "#eceef4",
        "BG_ROW_ODD":      "#ffffff",
        "BG_ROW_EVEN":     "#f1f3f8",
        "BG_ROW_SEL":      "#bcd4f6",
        "FG_WHITE":        "#1e2130",
        "FG_GRAY":         "#5b6270",
        "FG_TEXT":         "#2a2f3a",
        "FG_HIGHLIGHT":    "#1a6fd0",
        "ACCENT_BLUE":     "#2f6fd0",
        "BORDER_CLR":      "#c6cbd8",
        "BTN_DARK":        "#cfd5e2",
        "BTN_HOVER":       "#bcc4d6",
        "BTN_OK":          "#a8d4ab",
        "BTN_OK_HOVER":    "#8fc493",
        "BTN_ERR":         "#eeb3b3",
        "BTN_ERR_HOVER":   "#e09b9b",
        "BTN_ACCENT":      "#9cbdf0",
        "TOOLTIP_BG":      "#ffffff",
        "TOOLTIP_FG":      "#1e2130",
        "TOOLTIP_INNER_BG": "#f4f5f7",
        "SUCCESS":         "#0f8a4a",
        "ERROR":           "#c0392b",
        "ERROR2":          "#c0392b",
        "WARN":            "#a06a00",
        "WARN2":           "#a06a00",
        "WARN3":           "#8a6d00",
        "INFO_BLUE":       "#2f6fd0",
        "CHIP_BG":         "#dfe3ec",
        "CHIP_FG":         "#2f6fd0",
        "MATCH_BG":        "#cdeccd",
        "FR_MATCH_BG":     "#bfe3bf",
        "LINT_ERR_BG":     "#ffd6d6",
        "LINT_WARN_BG":    "#fff3cd",
        "FIND_HL_BG":      "#fff59d",
        "ERRLINE_BG":      "#ffc9c9",
        "ERRLINE_FG":      "#7a0000",
        "DOC":             "#7a828c",
    },
    # ── Kontrastowy (wysoki kontrast) ─────────────────────────────────────────
    "kontrastowy": {
        "BG_DARK":         "#000000",
        "BG_PANEL":        "#101010",
        "BG_INPUT":        "#000000",
        "BG_TAB_ACT":      "#000000",
        "BG_TAB_INACT":    "#181818",
        "BG_SUBTAB_ACT":   "#003366",
        "BG_SUBTAB_INACT": "#101010",
        "BG_ROW_ODD":      "#000000",
        "BG_ROW_EVEN":     "#101010",
        "BG_ROW_SEL":      "#0050a0",
        "FG_WHITE":        "#ffffff",
        "FG_GRAY":         "#c8c8c8",
        "FG_TEXT":         "#ffffff",
        "FG_HIGHLIGHT":    "#00b0ff",
        "ACCENT_BLUE":     "#00b0ff",
        "BORDER_CLR":      "#707070",
        "BTN_DARK":        "#202020",
        "BTN_HOVER":       "#383838",
        "BTN_OK":          "#2e7d32",
        "BTN_OK_HOVER":    "#388e3c",
        "BTN_ERR":         "#c0392b",
        "BTN_ERR_HOVER":   "#d64545",
        "BTN_ACCENT":      "#005a9e",
        "TOOLTIP_BG":      "#101010",
        "TOOLTIP_FG":      "#ffffff",
        "TOOLTIP_INNER_BG": "#000000",
        "SUCCESS":         "#00e676",
        "ERROR":           "#ff5252",
        "ERROR2":          "#ff5252",
        "WARN":            "#ffd740",
        "WARN2":           "#ffd740",
        "WARN3":           "#ffe082",
        "INFO_BLUE":       "#40c4ff",
        "CHIP_BG":         "#202020",
        "CHIP_FG":         "#00b0ff",
        "MATCH_BG":        "#005000",
        "FR_MATCH_BG":     "#006000",
        "LINT_ERR_BG":     "#400000",
        "LINT_WARN_BG":    "#3a3200",
        "FIND_HL_BG":      "#4a3c00",
        "ERRLINE_BG":      "#400000",
        "ERRLINE_FG":      "#ffffff",
        "DOC":             "#9aa0a6",
    },
}


def theme_values(name: str) -> Dict[str, str]:
    """Zwraca kopię słownika kolorów dla podanego motywu.

    Args:
        name: Nazwa motywu (klucz z :data:`THEME_PRESETS`).

    Returns:
        Dict[str, str]: Mapa ``nazwa koloru → hex``; przy nieznanej nazwie
        zwracany jest preset domyślny (:data:`THEME_DEFAULT`).
    """
    return dict(THEME_PRESETS.get(name) or THEME_PRESETS[THEME_DEFAULT])


def theme_names() -> Tuple[str, ...]:
    """Zwraca krotkę nazw dostępnych motywów w kolejności prezentacji."""
    return THEME_ORDER
