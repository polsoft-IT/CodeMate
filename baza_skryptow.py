# ── Metadane ──────────────────────────────────────────────────────────────────
# autor:   Sebastian Januchowski
# company: polsoft.ITS(TM) Group
# github:  https://github.com/polsoft-IT
# email:   polsoft.its@mail.com
# wersja:  4.0
# ──────────────────────────────────────────────────────────────────────────────
# OPIS
# ─────
# CodeMate v4.0 - aplikacja do zarządzania skryptami Python/Bash/PowerShell/JS/SQL.
# Funkcje: edytor z podświetlaniem składni, harmonogram uruchomień, kosz, szablony,
# statystyki, wyszukiwanie, eksport/import, virtualenv, VDrive, terminal.
#
# SPIS TREŚCI (odśwież przez: python baza_skryptow.py --toc)
# ──────────────────────────────────────────────────────────────────────────────
#   Sekcja 1: Importy i konfiguracja logging .............. linia   28
#   Sekcja 2: Stałe konfiguracyjne .......................... linia   62
#   Sekcja 3: Funkcje konfiguracji (cfg_load, cfg_save) ... linia   90
#   Sekcja 4: Funkcje bazy danych (db_read, db_write) ...... linia  247
#   Sekcja 5: SyntaxHighlighter — podświetlanie składni .... linia  430
#   Sekcja 6: MouseManager — menu kontekstowe / tooltipy .. linia  630
#   Sekcja 7: class CodeMate(tk.Tk) — aplikacja ....... linia 1800
#       ↳ __init__ / infrastruktura (cfg, indeksy, after)
#       ↳ BAZA DANYCH: _autoload_db / save_db / _on_close
#       ↳ RUNNER: _runner_* (proces, wyjście, historia, drift)
#       ↳ HARMONOGRAM: _sched_*
#       ↳ KOSZ: _trash_*
#       ↳ UI: menu · nagłówek · zakładki główne
#       ↳ Skrypty: Nowy / Lista / Edytor / Szablony / Statystyki /
#         Zaawansowane / Runner / Kosz
#       ↳ Szukaj · Moduły · Baza Danych · VirtualEnv · VDrive ·
#         Narzędzia · Terminal · Runner
#   Sekcja 8: main() — CLI: --list --run --export --import
#                 --verify --self-check --toc --gui-runner
# ──────────────────────────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import sys

# Autoprawka sys.path — umożliwia uruchomienie "python baza_skryptow.py"
# z dowolnego katalogu oraz pozwala mypy/IDE rozwiązywać pakiet src.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import json
import uuid
import hashlib
import base64
import shutil
import subprocess
import tempfile
import datetime
import logging
import threading
import gzip
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import integracji Git
try:
    from src.git_integration import GitIntegration
    _GIT_AVAILABLE = True
except ImportError:
    _GIT_AVAILABLE = False

# Import systemu pluginów
try:
    from src.plugin_system import PluginManager
    _PLUGINS_AVAILABLE = True
except ImportError:
    _PLUGINS_AVAILABLE = False

# Import kreatora pluginów (moduł rozszerzający — src/modules/plugin_creator.py)
try:
    from src.modules.plugin_creator import (
        FILE_COMMANDS as _CREATOR_FILE_COMMANDS,
        NAV_COMMANDS as _CREATOR_NAV_COMMANDS,
        plugin_source as _creator_plugin_source,
        valid_alias as _creator_valid_alias,
        valid_plugin_filename as _creator_valid_filename,
    )
    _CREATOR_AVAILABLE = True
except ImportError:
    _CREATOR_AVAILABLE = False
    _CREATOR_FILE_COMMANDS = ()
    _CREATOR_NAV_COMMANDS = ()
    _creator_plugin_source = None
    _creator_valid_alias = None
    _creator_valid_filename = None

# Import nowego modelu konfiguracji
try:
    from src.config import AppConfig
    _PYDANTIC_CONFIG_AVAILABLE = True
except ImportError:
    _PYDANTIC_CONFIG_AVAILABLE = False

# Import tłumaczeń interfejsu (i18n) — język angielski wydzielony do src/lang/en.py
try:
    from src.lang.en import KEYED as _EN_KEYED, MENU as _EN_MENU
except ImportError:
    _EN_KEYED, _EN_MENU = {}, {}

# Import menedżera sekretów (szyfrowanie Fernet + magazyn klucza keyring)
try:
    from src.secrets import SecretsStore, env_name_valid
    _SECRETS_AVAILABLE = True
except ImportError:
    _SECRETS_AVAILABLE = False

# Import presetów motywów (palety kolorów interfejsu)
try:
    from src.theme import (
        CMAP_EXCLUDE, TAG_BG_KEYS, TAG_COLOR_KEYS, THEME_DEFAULT, THEME_ORDER,
        THEME_PRESETS, theme_values,
    )
    _THEME_AVAILABLE = True
except ImportError:
    _THEME_AVAILABLE = False
    THEME_DEFAULT = "ciemny"
    THEME_ORDER = ("ciemny",)
    THEME_PRESETS: Dict[str, Dict[str, str]] = {"ciemny": {}}
    TAG_COLOR_KEYS: Dict[str, str] = {}
    TAG_BG_KEYS: Tuple[str, ...] = ()
    CMAP_EXCLUDE: Tuple[str, ...] = ()

    def theme_values(name: str) -> Dict[str, str]:
        """Fallback: brak modułu motywów — zwraca pustą paletę."""
        return {}

# Import powiadomień systemowych (toast przez plyer; opcjonalny)
try:
    from src.notify import notify_available as _notify_available
    from src.notify import send_native as _notify_send_native
    _NOTIFY_AVAILABLE = True
except ImportError:
    _NOTIFY_AVAILABLE = False

    def _notify_available() -> bool:
        """Fallback: brak modułu powiadomień."""
        return False

    def _notify_send_native(title: str, message: str, timeout: int = 8,
                            app_name: str = "") -> bool:
        """Fallback: brak modułu powiadomień — nigdy nie wysyła."""
        return False

from src.vdrive import load_vdrive_state, save_vdrive_state

# ── Konfiguracja logging (rotacyjny, max 3 × 1 MB) ─────────────────────────────
from logging.handlers import RotatingFileHandler
_log_handler = RotatingFileHandler(
    'baza_skryptow.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')
_log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'))
logging.basicConfig(
    handlers=[_log_handler],
    level=logging.WARNING,
)

# ── Globalny handler nieobsłużonych wyjątków Tk (zapis do loga + informacja) ──
def _report_callback_exception(exc_type, exc_value, exc_tb):
    """Zastępuje domyślny Tk report_callback_exception.

    Tk callbacki (bind, command, after) połykają wyjątki — bez tego handlera
    błąd GUI ginie po cichu. Teraz trafia do baza_skryptow.log.
    """
    import traceback
    logging.error(
        "Nieobsłużony wyjątek w GUI:\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


tk.Tk.report_callback_exception = _report_callback_exception

# ── Kodowanie konsoli: UTF-8 (polskie znaki w --list / --run) ────────────────
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:
        logging.warning(f"Nie udało się skonfigurować stdout UTF-8: {e}")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:
        logging.warning(f"Nie udało się skonfigurować stderr UTF-8: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURACJA — baza w jednym pliku JSON obok skryptu (+ plik .cfg)
# ══════════════════════════════════════════════════════════════════════════════
DB_SCHEMA = 2              # wersja formatu pliku bazy — podnoś przy zmianie struktury
APP_VER   = "4.0"        # wersja aplikacji (metadane / --version)

APP_DIR  = Path(_APP_DIR)
DB_FILE  = APP_DIR / "baza_skryptow.json"
CFG_FILE = APP_DIR / "baza_skryptow.cfg"
SNIPPETS_FILE = APP_DIR / "baza_skryptow.snippety.json"
VDRIVE_STATE_FILE = APP_DIR / "vdrive_state.json"
SECRETS_FILE = APP_DIR / "baza_skryptow.sekrety.json"


def _popup(parent: tk.Misc) -> tk.Toplevel:
    """Tworzy okno dialogowe (Toplevel) z ikoną aplikacji w pasku tytułu."""
    win = tk.Toplevel(parent)
    try:
        win.iconbitmap(str(APP_DIR / "codemate.ico"))
    except Exception:
        pass
    return win


CFG_KEYS = {
    "db_path":        "",          # puste = DB_FILE
    "autosave":       "1",         # 1 = autosave po zapisie/usunięciu
    "backup_count":   "3",         # ile kopii .bak trzymać
    "backup_days":    "7",         # ile dziennych kopii w backups/ trzymać
    "interpreter":    "",          # puste = sys.executable
    "timeout":        "60",        # sekundy dla runnera
    "runner_args":    "",
    "runner_console": "0",         # 1 = uruchamiaj w nowej konsoli
    # UI - kolory (nadpisują stałe)
    "bg_tab_act":     "",          # puste = użyj stałej BG_TAB_ACT
    "bg_tab_inact":   "",          # puste = użyj stałej BG_TAB_INACT
    "fg_text":        "",          # puste = użyj stałej FG_TEXT
    "font_family":    "",          # puste = Consolas
    "font_size":      "10",        # domyślny rozmiar czcionki
    "theme":          "ciemny",    # motyw UI: ciemny / jasny / kontrastowy
    "language":       "en",        # język interfejsu: "pl" lub "en"
    # Integracja Git
    "git_enabled":     "1",        # 1 = integracja Git aktywna
    "git_auto_commit": "1",        # 1 = auto-commit po zapisie bazy
    "git_auto_push":   "0",        # 1 = push po lokalnym commicie bazy
    # System pluginów
    "plugins_enabled": "1",        # 1 = ładowanie pluginów przy starcie
    "plugins_disabled": "",        # lista nazw pluginów wyłączonych (CSV)
    # Kosz
    "trash_days":      "0",        # 0 = bez auto-czyszczenia; N = usuń trwale po N dniach
    # Powiadomienia
    "notify_enabled":  "1",        # 1 = powiadomienie po zadaniu harmonogramu
    # Wygląd listy skryptów
    "list_alt_rows":   "1",        # 1 = naprzemienne kolory wierszy
    "list_bg_odd":     "",         # puste = kolor z motywu (BG_ROW_ODD)
    "list_bg_even":    "",         # puste = kolor z motywu (BG_ROW_EVEN)
    "list_sel_bg":     "",         # puste = kolor z motywu (BG_ROW_SEL)
    "list_row_height": "24",       # wysokość wiersza [px]
    "list_font_size":  "10",       # rozmiar czcionki listy
}

# Stałe konfiguracyjne
DEFAULT_BACKUP_COUNT = 3      # domyślna liczba kopii zapasowych
DEFAULT_TIMEOUT = 60          # domyślny timeout dla runnera (sekundy)
MAX_VERSIONS_STORED = 20      # ile poprzednich wersji kodu trzymać w rekordzie
BIG_DB_THRESHOLD = 1_000_000  # znaków - powyżej tego nie wstawiaj wcięć w JSON
DAILY_BACKUP_DIR = "backups"  # katalog dziennych kopii zapasowych bazy
DAILY_BACKUP_KEEP = 7         # ile dziennych kopii trzymać (rotacja)

# Stałe UI
TOOLTIP_DELAY_MS = 600        # opóźnienie tooltipa
TOOLTIP_GRACE_MS = 300        # grace na powrót do widgetu z tooltipem (anty-mruganie)
GESTURE_THRESHOLD = 40        # piksele - próg gestu myszy
FONT_SIZE_MIN = 7             # minimalny rozmiar czcionki
FONT_SIZE_MAX = 28            # maksymalny rozmiar czcionki
FONT_FAMILY = "Consolas"      # rodzina czcionki edytorów
HIGHLIGHT_DEBOUNCE_MS = 120   # opóźnienie podświetlania składni
TOOLTIP_BG = "#3a3f58"        # kolor tła tooltipa
TOOLTIP_FG = "#c8d0f0"        # kolor tekstu tooltipa
TOOLTIP_INNER_BG = "#1e2130"  # kolor wewnętrznego tła tooltipa

# Stałe kolorów UI
BG_TAB_ACT = "#4a90d9"        # aktywna zakładka
BG_TAB_INACT = "#252840"      # nieaktywna zakładka
FG_TEXT = "#c8d0f0"           # kolor tekstu
FG_HIGHLIGHT = "#82aaff"      # kolor podświetlenia

# Skróty klawiszowe (centralna konfiguracja)
KEYBOARD_SHORTCUTS = {
    "Ctrl+S": "save_script",
    "Ctrl+N": "new_script",
    "Ctrl+F": "find",
    "Ctrl+H": "replace",
    "Ctrl+O": "open_script",
    "Ctrl+E": "export_db",
    "Ctrl+I": "import_db",
    "Ctrl+R": "run_script",
    "Ctrl+T": "show_stats",
    "F5": "refresh",
    "Ctrl+Q": "quit",
    "Ctrl+L": "show_list",
    "Ctrl+D": "delete_line",
    "Ctrl+/": "toggle_comment",
    "Ctrl+A": "select_all",
}

# Metryki instrumentacji
class AppMetrics:
    """Prosta klasa do zbierania metryk aplikacji."""
    def __init__(self):
        self.scripts_loaded = 0
        self.runs_today = 0
        self.saves_today = 0
        self.start_time = datetime.datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Zwraca metryki jako słownik."""
        uptime = (datetime.datetime.now() - self.start_time).total_seconds()
        return {
            "scripts_loaded": self.scripts_loaded,
            "runs_today": self.runs_today,
            "saves_today": self.saves_today,
            "uptime_seconds": uptime,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
        }

CATEGORIES = ["Python", "Bash", "PowerShell", "JavaScript", "Batch",
              "VBScript", "Java", "JAR", "C", "C++", "Ruby", "Perl", "PHP",
              "WSF", "HTA", "HTML", "CSS", "JSON", "Markdown", "SQL", "Other"]
_CAT_FILTER_CHOICES = ("Wszystkie",) + tuple(CATEGORIES)

# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 2b: i18n — tłumaczenia PL/EN
# ══════════════════════════════════════════════════════════════════════════════
# Polski ("pl") jest językiem źródłowym (teksty bazowe poniżej). Pozostałe języki
# (obecnie tylko "en") są wydzielone do modułów w src/lang/.
# W kodzie UI używaj _t("klucz") (opcjonalnie z parametrami: _t("k", n=3)).
UI_LANGS = ("pl", "en")
_UI_LANG = "en"   # aktualny język interfejsu (domyślnie angielski)

# Teksty źródłowe (PL) — klucz i18n → tekst polski.
_UI_PL: Dict[str, str] = {
    # Okno / nagłówek
    "app_title":        "CodeMate v{ver}",
    "header_title":     "CodeMate  v{ver}",
    "header_platform":  "Windows 11",
    "header_count":     "Skryptów: {n}",
    "lang_button":      "● EN",
    # Nawigacja główna
    "tab_skrypty":      "Skrypty",
    "tab_szukaj":       "Szukaj",
    "tab_moduly":       "Moduły",
    "tab_baza":         "Baza Danych",
    "tab_venv":         "VirtualEnv",
    "tab_vdrive":       "💾 VDrive",
    "tab_narzedzia":    "Narzędzia",
    "tab_terminal":     "🖥 Terminal",
    "tab_runner":       "▶ Runner",
    "tab_git":          "📚 Git",
    "tab_plugins":      "🔌 Plugins",
    "tab_ustawienia":   "Ustawienia",
    # Zakładka: Ustawienia
    "ust_header":           "⚙ Ustawienia",
    "ust_status_saved":     "Zapisano ustawienia",
    "ust_status_reset":     "Przywrócono wartości domyślne",
    "ust_status_err":       "Błąd: wartości liczbowe nieprawidłowe",
    "ust_sec_db":           "Baza danych",
    "ust_db_file":          "Plik bazy:",
    "ust_btn_open_folder":  "Otwórz folder",
    "ust_db_backups":       "Kopie zapasowe (.bak):",
    "ust_db_autosave":      "Autosave po zmianach:",
    "ust_sec_runner":       "Runner",
    "ust_run_interp":       "Interpreter (pusty = domyślny):",
    "ust_btn_browse":       "Przeglądaj…",
    "ust_run_timeout":      "Timeout [s]:",
    "ust_run_args":         "Dodatkowe argumenty:",
    "ust_run_console":      "Domyślnie w nowej konsoli:",
    "ust_sec_look":         "Wygląd",
    "ust_look_theme":       "Motyw:",
    "theme_ciemny":         "Ciemny",
    "theme_jasny":          "Jasny",
    "theme_kontrastowy":    "Kontrastowy",
    "ust_look_font":        "Czcionka:",
    "ust_look_fontsize":    "Rozmiar czcionki:",
    "ust_look_bgact":       "Kolor aktywnej zakładki:",
    "ust_look_bginact":     "Kolor nieaktywnej zakładki:",
    "ust_look_fg":          "Kolor czcionki (tekst, listy, edytory):",
    "ust_sec_lang":         "Język interfejsu",
    "ust_lang_label":       "Język:",
    "ust_sec_git":          "Git",
    "ust_git_enabled":      "Integracja Git:",
    "ust_git_auto_commit":  "Automatyczny commit bazy:",
    "ust_sec_plugins":      "Pluginy",
    "ust_plugins_enabled":  "Ładowanie pluginów przy starcie:",
    "ust_sec_trash":        "Kosz",
    "ust_trash_days":       "Trwale usuń po [dni, 0 = nigdy]:",
    "ust_sec_notify":       "Powiadomienia",
    "ust_notify_enabled":   "Powiadomienie po zadaniu harmonogramu:",
    "toast_font_size":      "Czcionka: {size} pt",
    "notify_title":         "Harmonogram",
    "notify_done_ok":       "{nazwa} — zakończono OK ({czas} s)",
    "notify_done_err":      "{nazwa} — BŁĄD (kod {rc}, {czas} s)",
    "ust_btn_save":         "💾 Zapisz ustawienia",
    "ust_btn_reset":        "Przywróć domyślne",
    "ust_cfg_file":         "Plik konfiguracji: {file}",
    "ust_status_purged":    "Zapisano ustawienia · usunięto trwale {n} z kosza",
    "stat_trash_info":      "Elementów: {n} · rozmiar kodu: {size} znaków",
    "ust_dlg_interp_title": "Wybierz interpreter Python",
    "ust_dlg_all_files":    "Wszystkie pliki",
    # Zakładka Ustawienia — pod-zakładki
    "ust_sub_ogolne":           "⚙ Ogólne",
    "ust_sub_personalizacja":   "🎨 Personalizacja",
    "ust_sec_list":             "Wygląd listy skryptów",
    "ust_list_alt":             "Naprzemienne kolory wierszy:",
    "ust_list_bgodd":           "Kolor wiersza nieparzystego (puste = motyw):",
    "ust_list_bgeven":          "Kolor wiersza parzystego (puste = motyw):",
    "ust_list_sel":             "Kolor zaznaczonego wiersza (puste = motyw):",
    "ust_list_rowheight":       "Wysokość wiersza [px]:",
    "ust_list_fontsize":        "Rozmiar czcionki listy:",
    # Zakładka: Snippety
    "sn_status_saved":      "Zapisano snippet",
    "sn_status_deleted":    "Usunięto snippet",
    "sn_status_inserted":   "Wstawiono do edytora",
    "sn_status_copied":     "Skopiowano do schowka",
}

# Pełna tabela tłumaczeń: klucz → {język: tekst}. Angielski z src/lang/en.py.
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    key: {"pl": pl, "en": _EN_KEYED.get(key, pl)} for key, pl in _UI_PL.items()
}


def _t(key: str, **kwargs: Any) -> str:
    """Zwraca przetłumaczony tekst dla klucza w aktualnym języku (_UI_LANG).

    Brak klucza = zwraca sam klucz (bezpieczny fallback). Parametry nazwane
    podstawiane są przez str.format (błędne podstawienie nie przerywa działania).
    """
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    txt = entry.get(_UI_LANG) or entry.get("pl") or key
    if kwargs:
        try:
            txt = txt.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return txt


def _set_lang(lang: str) -> str:
    """Ustawia aktualny język interfejsu; zwraca obowiązujący kod języka."""
    global _UI_LANG
    _UI_LANG = lang if lang in UI_LANGS else "en"
    return _UI_LANG


# Tłumaczenia tekstowe menu (klucz = tekst polski z UI). Angielski: src/lang/en.py.
# Używane przez _tr() przy etykietach menu, gdzie wygodniej mapować cały tekst
# niż wprowadzać osobne klucze.
MENU_EN: Dict[str, str] = dict(_EN_MENU)


def _tr(text: str) -> str:
    """Tłumaczy pojedynczy tekst UI (klucz = tekst polski) na aktualny język."""
    if _UI_LANG == "pl":
        return text
    return MENU_EN.get(text, text)



# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 3: FUNKCJE KONFIGURACJI
# ══════════════════════════════════════════════════════════════════════════════


def cfg_load() -> Dict[str, str]:
    """
    Wczytuje konfigurację z pliku .cfg; brak pliku = wartości domyślne.
    Używa pydantic jeśli dostępny, w przeciwnym razie configparser.

    Returns:
        Dict[str, str]: Słownik z wartościami konfiguracyjnymi.
    """
    if _PYDANTIC_CONFIG_AVAILABLE and CFG_FILE.exists():
        try:
            config = AppConfig.load_from_file(CFG_FILE)
            return config.to_dict()
        except Exception as e:
            logging.warning(f"Błąd wczytywania konfiguracji (pydantic): {e}")
            # Fallback do starej metody

    import configparser
    cp = configparser.ConfigParser()
    try:
        cp.read(str(CFG_FILE), encoding="utf-8")
    except Exception as e:
        logging.warning(f"Błąd wczytywania konfiguracji: {e}")
        return dict(CFG_KEYS)
    out = dict(CFG_KEYS)
    if cp.has_section("baza"):
        for k in CFG_KEYS:
            if cp.has_option("baza", k):
                out[k] = cp.get("baza", k)
    if not out.get("db_path"):
        out["db_path"] = str(DB_FILE)
    return out


def cfg_save(values: Dict[str, str]) -> None:
    """
    Zapisuje konfigurację do pliku .cfg (atomowo).
    Używa pydantic jeśli dostępny, w przeciwnym razie configparser.

    Args:
        values: Słownik z wartościami konfiguracyjnymi do zapisania.
    """
    if _PYDANTIC_CONFIG_AVAILABLE:
        try:
            config = AppConfig.from_dict(values)
            config.save_to_file(CFG_FILE)
            return
        except Exception as e:
            logging.warning(f"Błąd zapisu konfiguracji (pydantic): {e}")
            # Fallback do starej metody

    import configparser
    cp = configparser.ConfigParser()
    cp.add_section("baza")
    for k in CFG_KEYS:
        cp.set("baza", k, str(values.get(k, CFG_KEYS[k])))
    tmp = CFG_FILE.with_suffix(".cfg.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            cp.write(fh)
        Path(tmp).replace(CFG_FILE)
    except OSError as e:
        logging.error(f"Błąd zapisu konfiguracji: {e}")


def kod_checksum(kod: Optional[str]) -> str:
    """
    Skrót SHA-256 kodu — do wykrywania duplikatów treści.

    Args:
        kod: Kod do zahaszowania (może być None).

    Returns:
        str: Hex string SHA-256.
    """
    return hashlib.sha256((kod or "").encode("utf-8", "replace")).hexdigest()


def now_str() -> str:
    """
    Zwraca aktualny timestamp w formacie YYYY-MM-DD HH:MM:SS.

    Returns:
        str: Sformatowany timestamp.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 3b: BIBLIOTEKA SNIPPETÓW (własne fragmenty kodu)
# ══════════════════════════════════════════════════════════════════════════════

PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z0-9_\- ]+)\}")


def snippet_normalize(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sprowadza snippet do jednolitego słownika i uzupełnia brakujące pola."""
    it = dict(item or {})
    it["id"] = it.get("id") or uuid.uuid4().hex
    it["nazwa"] = str(it.get("nazwa") or "snippet").strip() or "snippet"
    it["kategoria"] = it.get("kategoria") if it.get("kategoria") in CATEGORIES else "Python"
    it["tagi"] = str(it.get("tagi") or "").strip()
    it["tresc"] = str(it.get("tresc") or "")
    it["zmieniony"] = it.get("zmieniony") or now_str()
    return it


def snippets_load() -> List[Dict[str, Any]]:
    """Wczytuje bibliotekę snippetów z pliku JSON.

    Brak pliku = zapis zestawu startowego (src.starter_snippets) i zwrot
    jego treści, dzięki czemu nowa instalacja ma gotowy zestaw snippetów.
    Uszkodzony plik = pusta lista (bez nadpisywania danych użytkownika).
    """
    try:
        if not SNIPPETS_FILE.exists():
            from src.starter_snippets import starter_items
            items = [snippet_normalize(it) for it in starter_items()]
            snippets_save(items)
            return items
        data = json.loads(SNIPPETS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"Błąd wczytywania snippetów: {e}")
        return []
    if isinstance(data, dict):
        data = data.get("snippety", [])
    if not isinstance(data, list):
        return []
    return [snippet_normalize(it) for it in data]


def snippets_save(items: List[Dict[str, Any]]) -> None:
    """Zapisuje bibliotekę snippetów do pliku JSON (atomowo)."""
    tmp = SNIPPETS_FILE.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps({"schema": 1, "snippety": items},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        Path(tmp).replace(SNIPPETS_FILE)
    except OSError as e:
        logging.error(f"Błąd zapisu snippetów: {e}")


def sc_normalize(sc: Optional[Dict[str, Any]], kat_default: str = "Other") -> Dict[str, Any]:
    """
    Sprowadza rekord do jednolitego słownika i uzupełnia brakujące pola.

    Args:
        sc: Słownik z danymi skryptu (może być None).
        kat_default: Domyślna kategoria jeśli brak lub nieprawidłowa.

    Returns:
        Dict[str, Any]: Znormalizowany słownik skryptu.
    """
    sc = dict(sc or {})
    sc["id"] = sc.get("id") or uuid.uuid4().hex
    sc["nazwa"] = str(sc.get("nazwa") or "bez-nazwy").strip() or "bez-nazwy"
    sc["kategoria"] = sc.get("kategoria") if sc.get("kategoria") in CATEGORIES else kat_default
    sc["tagi"] = sc.get("tagi") or ""
    if isinstance(sc["tagi"], (list, tuple)):
        sc["tagi"] = ", ".join(str(t) for t in sc["tagi"])
    sc["opis"] = sc.get("opis") or ""
    sc["kod"] = sc.get("kod") or ""
    sc["utworzony"] = sc.get("utworzony") or now_str()
    sc["zmieniony"] = sc.get("zmieniony") or sc["utworzony"]
    try:
        sc["uruchomien"] = int(sc.get("uruchomien") or 0)
    except (TypeError, ValueError):
        sc["uruchomien"] = 0
    sc["ostatni_run"] = sc.get("ostatni_run")
    sc["ostatni_wynik"] = sc.get("ostatni_wynik")
    sc["ostatni_czas_ms"] = sc.get("ostatni_czas_ms")
    sc["zaufany"] = bool(sc.get("zaufany", False))
    sc["checksum"] = sc.get("checksum") or kod_checksum(sc["kod"])
    # historia uruchomień / ostatni udany przebieg / argumenty runnera
    hist = sc.get("historia")
    sc["historia"] = hist if isinstance(hist, list) else []
    sc["ok_checksum"] = sc.get("ok_checksum")
    sc["ok_run"] = sc.get("ok_run")
    sc["ok_kod"] = sc.get("ok_kod")
    sc["runner_args"] = sc.get("runner_args") or ""
    # plan harmonogramu (aktywny, co_min, o_godzinie, args) — może być None
    hm = sc.get("harmonogram")
    sc["harmonogram"] = hm if isinstance(hm, dict) else None
    # kosz (data przeniesienia) i wersje kodu
    sc["usuniety"] = sc.get("usuniety") or None
    ver = sc.get("wersje")
    sc["wersje"] = ver if isinstance(ver, list) else []
    # załączniki skryptu (pliki pomocnicze pakowane w .bsdb)
    fl = sc.get("pliki")
    sc["pliki"] = fl if isinstance(fl, dict) else {}
    return sc


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 4: FUNKCJE BAZY DANYCH
# ══════════════════════════════════════════════════════════════════════════════


def sc_add_version(sc: Dict[str, Any], autor: str = "zapis") -> None:
    """
    Dopisuje poprzednią wersję kodu do historii wersji (max MAX_VERSIONS_STORED).

    Args:
        sc: Słownik skryptu do zaktualizowania.
        autor: Autor zmiany (domyślnie "zapis").
    """
    if not isinstance(sc, dict) or not sc.get("kod"):
        return
    ver = sc.setdefault("wersje", [])
    cs = kod_checksum(sc.get("kod", ""))
    if ver and ver[-1].get("checksum") == cs:
        return
    ver.append({"ts": sc.get("zmieniony") or now_str(),
                "autor": autor, "checksum": cs, "kod": sc.get("kod", "")})
    if len(ver) > MAX_VERSIONS_STORED:
        del ver[:-MAX_VERSIONS_STORED]


def db_wrap(skrypty: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Opakowuje listę rekordów w strukturę pliku (schema + metadane).

    Args:
        skrypty: Lista słowników skryptów.

    Returns:
        Dict[str, Any]: Struktura bazy gotowa do zapisu.
    """
    return {
        "schema":   DB_SCHEMA,
        "app":      f"CodeMate v{APP_VER}",
        "exported": now_str(),
        "skrypty":  list(skrypty),
    }


def db_to_list(data: Any) -> Tuple[List[Dict[str, Any]], int]:
    """
    Migracja danych dowolnej wersji do listy rekordów. Toleruje:
      v2: {"schema": 2, "skrypty": [...]}   — nowy format
      v1: [ {"nazwa": ...}, ... ]           — stary eksport (lista)
      v0: {"skrypty": [...]}                — dict bez schema

    Args:
        data: Dane z pliku JSON (dict lub list).

    Returns:
        Tuple[List[Dict[str, Any]], int]: (lista skryptów, liczba znormalizowanych rekordów).

    Raises:
        ValueError: Jeśli format jest nieobsługiwany.
    """
    if isinstance(data, dict):
        data = data.get("skrypty", [data]) if "skrypty" in data else [data]
    if not isinstance(data, list):
        raise ValueError("Plik bazy ma nieobsługiwany format (oczekiwano listy skryptów).")
    out, normalized, seen = [], 0, set()
    for raw in data:
        if not isinstance(raw, dict):
            continue
        before = set(raw.keys())
        sc = sc_normalize(raw)
        if set(sc.keys()) - before:
            normalized += 1
        if sc["id"] in seen:
            sc["id"] = uuid.uuid4().hex
        seen.add(sc["id"])
        out.append(sc)
    return out, normalized


def db_read(path: Union[str, Path]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Czyta plik bazy z migracją.

    Args:
        path: Ścieżka do pliku bazy.

    Returns:
        Tuple[List[Dict[str, Any]], List[str]]: (lista skryptów, lista ostrzeżeń).
    """
    path = Path(path)
    # Bazy większe od progu zapisywane są gzipem mimo rozszerzenia .json.
    # Rozpoznaj kompresję po sygnaturze, zachowując zgodność ze zwykłym JSON.
    with open(path, "rb") as fh:
        is_gzip = fh.read(2) == b"\x1f\x8b"
    opener = gzip.open if is_gzip else open
    with opener(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    schema = data.get("schema") if isinstance(data, dict) else 1
    lista, normalized = db_to_list(data)
    notes = []
    if schema != DB_SCHEMA:
        notes.append(f"Migracja formatu v{schema or 1} → v{DB_SCHEMA}.")
    if normalized:
        notes.append(f"Uzupełniono metadane w {normalized} rekordzie/-ach.")
    return lista, notes


def db_write(path: Union[str, Path], skrypty: List[Dict[str, Any]], backup_count: int = 3) -> Path:
    """
    Atomowy zapis bazy: .tmp → fsync → rotacja .bak → os.replace.
    Przy crashu zostaje poprzednia dobra wersja, nigdy plik pusty/ucięty.
    Obsługuje kompresję gzip dla dużych baz.

    Args:
        path: Ścieżka do pliku bazy.
        skrypty: Lista słowników skryptów.
        backup_count: Liczba kopii zapasowych do zachowania.

    Returns:
        Path: Ścieżka do zapisanego pliku.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = db_wrap(skrypty)
    big = sum(len(str(sc.get("kod", ""))) for sc in skrypty) > BIG_DB_THRESHOLD

    try:
        # Kompresuj do osobnego pliku tymczasowego, a potem atomowo podmień bazę.
        if big:
            tmp_gz = tmp.with_suffix(tmp.suffix + ".gz")
            with gzip.open(tmp_gz, "wt", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=None)
            tmp_gz.replace(tmp)
        else:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())

        try:
            n = max(0, int(backup_count))
        except (TypeError, ValueError):
            n = DEFAULT_BACKUP_COUNT
        if path.exists() and n > 0:
            oldest = path.with_suffix(f"{path.suffix}.bak.{n}")
            if oldest.exists():
                oldest.unlink()
            for i in range(n - 1, 0, -1):
                older = path.with_suffix(f"{path.suffix}.bak.{i}")
                if older.exists():
                    older.replace(path.with_suffix(f"{path.suffix}.bak.{i + 1}"))
            path.replace(path.with_suffix(f"{path.suffix}.bak"))

        tmp.replace(path)
        return path
    finally:
        for stale in (tmp, tmp.with_suffix(tmp.suffix + ".gz")):
            try:
                if stale.exists():
                    stale.unlink()
            except OSError:
                logging.warning("Nie udało się usunąć pliku tymczasowego: %s", stale)


def daily_backup(path: Union[str, Path], keep: int = DAILY_BACKUP_KEEP) -> Optional[Path]:
    """Tworzy dzienną kopię zapasową bazy (raz na dzień, rotacja ``keep`` dni).

    Kopia powstaje tylko, gdy dzisiejsza jeszcze nie istnieje — dzięki temu
    codzienne uruchomienia nie zaśmiecają katalogu. Kopie trafiają do
    ``backups/`` obok bazy (nazwa: ``<baza>.YYYY-MM-DD.json``).

    Args:
        path: Ścieżka pliku bazy.
        keep: Ile najnowszych kopii dziennych trzymać.

    Returns:
        Optional[Path]: Ścieżka nowej kopii albo None (już jest dzisiejsza /
        baza nie istnieje / błąd zapisu).
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        backup_dir = path.parent / DAILY_BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.date.today().isoformat()
        target = backup_dir / f"{path.stem}.{stamp}{path.suffix}"
        if target.exists():
            return None  # dzisiejsza kopia już istnieje
        shutil.copy2(path, target)
        # rotacja: usuń najstarsze ponad `keep` (keep=0 → tylko dzisiejsza)
        backups = sorted(backup_dir.glob(f"{path.stem}.*{path.suffix}"))
        for stale in (backups[:-keep] if keep > 0 else backups[:-1]):
            try:
                stale.unlink()
            except OSError:
                logging.warning("Nie udało się usunąć starej kopii: %s", stale)
        return target
    except OSError as e:
        logging.warning("Dzienny backup nieudany: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 5: SYNTAX HIGHLIGHTER
# ══════════════════════════════════════════════════════════════════════════════
# Syntax highlighting (opcjonalne — działa gdy zainstalowany Pygments)
try:
    from pygments import lex
    from pygments.lexers import (PythonLexer, BashLexer, PowerShellLexer,
                                  JavascriptLexer, SqlLexer, TextLexer, get_lexer_by_name)
    from pygments.token import Token
    _PYGMENTS_OK = True
except ImportError:
    _PYGMENTS_OK = False


# ══════════════════════════════════════════════════════════════════════════════
# SYNTAX HIGHLIGHTER — podświetlanie składni kodu (Pygments)
# ══════════════════════════════════════════════════════════════════════════════
# Paleta kolorów dopasowana do ciemnego motywu aplikacji
_HL_COLORS_DARK = {
    # Słowa kluczowe
    Token.Keyword:              "#c792ea",
    Token.Keyword.Constant:     "#c792ea",
    Token.Keyword.Declaration:  "#c792ea",
    Token.Keyword.Namespace:    "#c792ea",
    Token.Keyword.Type:         "#c792ea",
    # Wbudowane
    Token.Name.Builtin:         "#82aaff",
    Token.Name.Builtin.Pseudo:  "#82aaff",
    Token.Name.Exception:       "#f07178",
    Token.Name.Decorator:       "#ffcb6b",
    Token.Name.Class:           "#ffcb6b",
    Token.Name.Function:        "#82aaff",
    # Stringi
    Token.Literal.String:       "#c3e88d",
    Token.Literal.String.Doc:   "#546e7a",
    Token.Literal.String.Interpol: "#f07178",
    # Liczby
    Token.Literal.Number:       "#f78c6c",
    Token.Literal.Number.Integer: "#f78c6c",
    Token.Literal.Number.Float: "#f78c6c",
    Token.Literal.Number.Hex:   "#f78c6c",
    # Komentarze
    Token.Comment:              "#546e7a",
    Token.Comment.Single:       "#546e7a",
    Token.Comment.Multiline:    "#546e7a",
    # Operatory i interpunkcja
    Token.Operator:             "#89ddff",
    Token.Operator.Word:        "#c792ea",
    Token.Punctuation:          "#89ddff",
    # Domyślny tekst
    Token.Text:                 "#c8d0f0",
    Token.Name:                 "#c8d0f0",
} if _PYGMENTS_OK else {}

# Paleta kolorów podświetlania składni dla motywu jasnego (wyższy kontrast
# na jasnym tle). Motyw kontrastowy korzysta z palety ciemnej.
_HL_COLORS_LIGHT = {
    Token.Keyword:              "#7c4dff",
    Token.Keyword.Constant:     "#7c4dff",
    Token.Keyword.Declaration:  "#7c4dff",
    Token.Keyword.Namespace:    "#7c4dff",
    Token.Keyword.Type:         "#7c4dff",
    Token.Name.Builtin:         "#1565c0",
    Token.Name.Builtin.Pseudo:  "#1565c0",
    Token.Name.Exception:       "#c62828",
    Token.Name.Decorator:       "#ef6c00",
    Token.Name.Class:           "#ef6c00",
    Token.Name.Function:        "#1565c0",
    Token.Literal.String:       "#2e7d32",
    Token.Literal.String.Doc:   "#607d8b",
    Token.Literal.String.Interpol: "#c62828",
    Token.Literal.Number:       "#d84315",
    Token.Literal.Number.Integer: "#d84315",
    Token.Literal.Number.Float: "#d84315",
    Token.Literal.Number.Hex:   "#d84315",
    Token.Comment:              "#607d8b",
    Token.Comment.Single:       "#607d8b",
    Token.Comment.Multiline:    "#607d8b",
    Token.Operator:             "#00838f",
    Token.Operator.Word:        "#7c4dff",
    Token.Punctuation:          "#00838f",
    Token.Text:                 "#2a2f3a",
    Token.Name:                 "#2a2f3a",
} if _PYGMENTS_OK else {}

# Aktywna paleta podświetlania (przełączana wg motywu: _apply_hl_palette).
_HL_COLORS = dict(_HL_COLORS_DARK)


def _apply_hl_palette(name: str) -> None:
    """Ustawia aktywną paletę podświetlania składni wg motywu.

    Motyw ``jasny`` korzysta z jaśniejszej palety; pozostałe z ciemnej.
    """
    global _HL_COLORS
    _HL_COLORS = dict(_HL_COLORS_LIGHT if name == "jasny" else _HL_COLORS_DARK)


_CATEGORY_LEXER = {
    "Python":     "python",
    "Bash":       "bash",
    "PowerShell": "powershell",
    "JavaScript": "javascript",
    "Batch":      "batch",
    "VBScript":   "vbscript",
    "Java":       "java",
    "JAR":        "text",
    "C":          "c",
    "C++":        "cpp",
    "Ruby":       "ruby",
    "Perl":       "perl",
    "PHP":        "php",
    "WSF":        "xml",
    "HTA":        "html",
    "HTML":       "html",
    "CSS":        "css",
    "JSON":       "json",
    "Markdown":   "markdown",
    "SQL":        "sql",
    "Other":      "text",
}

# Ikona (emoji) i akcent kolorystyczny przypisane do kategorii skryptu.
KAT_ICON = {
    "Python":     "🐍",
    "Bash":       "🐚",
    "PowerShell": "💠",
    "JavaScript": "🟨",
    "Batch":      "🖥️",
    "VBScript":   "📜",
    "Java":       "☕",
    "JAR":        "📦",
    "C":          "⚙️",
    "C++":        "🧰",
    "Ruby":       "💎",
    "Perl":       "🐪",
    "PHP":        "🐘",
    "WSF":        "🧩",
    "HTA":        "🪟",
    "HTML":       "🌐",
    "CSS":        "🎨",
    "JSON":       "🔧",
    "Markdown":   "📝",
    "SQL":        "🗃️",
    "Other":      "📄",
}

KAT_COLOR = {
    "Python":     "#4a90d9",
    "Bash":       "#7ec27e",
    "PowerShell": "#5fa8e0",
    "JavaScript": "#e0c04a",
    "Batch":      "#9aa4b8",
    "VBScript":   "#c08ae0",
    "Java":       "#e08a5a",
    "JAR":        "#d0a15a",
    "C":          "#6aa8d9",
    "C++":        "#4aa8c9",
    "Ruby":       "#e06a6a",
    "Perl":       "#6ac0c0",
    "PHP":        "#8a8ae0",
    "WSF":        "#b0b0d0",
    "HTA":        "#7db8e0",
    "HTML":       "#e08a4a",
    "CSS":        "#4ab0d9",
    "JSON":       "#c0c0a0",
    "Markdown":   "#a0d0a0",
    "SQL":        "#d9a04a",
    "Other":      "#8890a4",
}


def kat_label(kategoria: str) -> str:
    """Zwraca etykietę kategorii z ikoną, np. ``🐍 Python`` (bez ikony gdy brak)."""
    icon = KAT_ICON.get(kategoria)
    return f"{icon} {kategoria}" if icon else (kategoria or "")


def discover_venv_tools(which=shutil.which) -> Dict[str, str]:
    """Locate optional environment managers without coupling detection to UI setup."""
    tools = {}
    for tool in ("venv", "virtualenv", "pipenv", "poetry", "conda"):
        found = which(tool)
        if found:
            tools[tool] = found
        elif tool == "venv":
            tools[tool] = "built-in"
        else:
            tools[tool] = ""
    return tools

# Słowa kluczowe i wbudowane funkcje Pythona — źródło podpowiedzi edytora.
PY_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "match", "case", "self",
}

PY_BUILTINS = {
    "abs", "all", "any", "bool", "bytes", "callable", "chr", "classmethod",
    "dict", "dir", "divmod", "enumerate", "eval", "filter", "float", "format",
    "frozenset", "getattr", "globals", "hasattr", "hash", "hex", "id", "input",
    "int", "isinstance", "issubclass", "iter", "len", "list", "locals", "map",
    "max", "min", "next", "object", "oct", "open", "ord", "pow", "print",
    "property", "range", "repr", "reversed", "round", "set", "setattr",
    "slice", "sorted", "staticmethod", "str", "sum", "super", "tuple", "type",
    "vars", "zip", "Exception", "ValueError", "TypeError", "KeyError",
}

# Znane symbole modułów standardowych — podpowiedzi po kropce dla importów.
PY_MODULE_ATTRS: Dict[str, Tuple[str, ...]] = {
    "os":      ("path", "getcwd", "listdir", "mkdir", "makedirs", "remove",
                "rename", "environ", "sep", "walk", "stat", "system"),
    "os.path": ("join", "exists", "isfile", "isdir", "basename", "dirname",
                "abspath", "splitext", "expanduser", "getsize"),
    "sys":     ("argv", "exit", "path", "version", "platform", "stderr",
                "stdout", "stdin", "modules"),
    "json":    ("dump", "dumps", "load", "loads", "JSONDecodeError"),
    "re":      ("match", "search", "findall", "sub", "split", "compile",
                "fullmatch", "escape", "IGNORECASE", "MULTILINE"),
    "math":    ("sqrt", "floor", "ceil", "pi", "e", "sin", "cos", "tan",
                "log", "log2", "log10", "exp", "factorial", "gcd"),
    "random":  ("random", "randint", "choice", "shuffle", "sample", "seed",
                "uniform", "randrange"),
    "time":    ("time", "sleep", "strftime", "strptime", "ctime", "time_ns"),
    "datetime": ("datetime", "date", "time", "timedelta", "timezone"),
    "pathlib": ("Path", "PurePath", "PosixPath", "WindowsPath"),
    "subprocess": ("run", "Popen", "call", "check_output", "check_call",
                   "CompletedProcess", "PIPE", "DEVNULL"),
    "tkinter": ("Tk", "Toplevel", "Frame", "Label", "Button", "Entry",
                "Text", "Listbox", "Menu", "Canvas", "Scrollbar", "StringVar"),
    "sqlite3": ("connect", "Connection", "Cursor", "Error", "paramstyle"),
    "shutil":  ("copy", "copy2", "copytree", "move", "rmtree", "which",
                "disk_usage", "make_archive", "unpack_archive"),
    "typing":  ("List", "Dict", "Set", "Tuple", "Optional", "Any", "Callable",
                "Union", "Iterable", "Iterator"),
}

# Słowa kluczowe / znaczniki dla pozostałych kategorii — źródło podpowiedzi edytora.
AUTO_KEYWORDS: Dict[str, set] = {
    "Ruby": {
        "begin", "break", "case", "class", "def", "defined?", "do", "else",
        "elsif", "end", "ensure", "false", "for", "if", "in", "module", "next",
        "nil", "not", "or", "and", "redo", "rescue", "retry", "return", "self",
        "super", "then", "true", "unless", "until", "when", "while", "yield",
        "attr_accessor", "attr_reader", "attr_writer", "require", "require_relative",
        "puts", "print", "p", "gets", "lambda", "proc", "raise", "loop", "each",
        "map", "select", "reject", "reduce", "freeze", "new", "to_s", "to_i",
        "to_f", "to_a", "to_h", "length", "size", "push", "pop", "shift",
    },
    "Perl": {
        "my", "our", "local", "sub", "return", "if", "elsif", "else", "unless",
        "while", "until", "for", "foreach", "do", "last", "next", "redo", "use",
        "no", "package", "require", "strict", "warnings", "print", "printf",
        "say", "chomp", "chop", "split", "join", "map", "grep", "sort", "keys",
        "values", "each", "push", "pop", "shift", "unshift", "defined", "undef",
        "die", "warn", "eval", "open", "close", "read", "write", "scalar",
        "ref", "bless", "wantarray", "qw", "qq", "q", "tr", "s", "m",
    },
    "PHP": {
        "<?php", "?>", "declare", "strict_types", "namespace", "use", "class",
        "interface", "trait", "extends", "implements", "public", "private",
        "protected", "static", "final", "abstract", "const", "function", "fn",
        "return", "echo", "print", "if", "else", "elseif", "endif", "while",
        "endwhile", "for", "foreach", "endforeach", "as", "break", "continue",
        "switch", "case", "default", "match", "try", "catch", "finally", "throw",
        "new", "clone", "instanceof", "null", "true", "false", "array", "list",
        "isset", "unset", "empty", "die", "exit", "require", "require_once",
        "include", "include_once", "global", "yield", "readonly", "enum",
        "strlen", "count", "implode", "explode", "array_map", "array_filter",
        "sprintf", "printf", "var_dump", "file_get_contents", "file_put_contents",
    },
    "HTML": {
        "!DOCTYPE", "html", "head", "meta", "title", "link", "style", "script",
        "body", "header", "nav", "main", "section", "article", "aside", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "img", "ul", "ol", "li",
        "table", "thead", "tbody", "tr", "th", "td", "form", "input", "button",
        "select", "option", "textarea", "label", "div", "span", "br", "hr",
        "class", "id", "href", "src", "alt", "type", "name", "value", "placeholder",
    },
    "CSS": {
        "color", "background", "background-color", "font", "font-family",
        "font-size", "font-weight", "margin", "padding", "border", "border-radius",
        "width", "height", "max-width", "min-width", "display", "flex", "grid",
        "position", "top", "right", "bottom", "left", "z-index", "overflow",
        "box-shadow", "transition", "transform", "animation", "opacity", "cursor",
        "text-align", "line-height", "letter-spacing", "gap", "justify-content",
        "align-items", "grid-template-columns", "var", "calc", "!important",
        ":root", "hover", "focus",
    },
    "JSON": {"true", "false", "null"},
    "C": {
        "auto", "break", "case", "char", "const", "continue", "default",
        "do", "double", "else", "enum", "extern", "float", "for", "goto",
        "if", "inline", "int", "long", "register", "restrict", "return",
        "short", "signed", "sizeof", "static", "struct", "switch", "typedef",
        "union", "unsigned", "void", "volatile", "while", "bool", "true",
        "false", "NULL", "printf", "scanf", "sprintf", "snprintf", "fprintf",
        "fopen", "fclose", "fread", "fwrite", "malloc", "calloc", "realloc",
        "free", "exit", "abs", "atoi", "atof", "strlen", "strcpy", "strncpy",
        "strcmp", "strncmp", "strcat", "strstr", "memcpy", "memset", "memmove",
        "puts", "putchar", "getchar", "gets", "main", "sizeof", "offsetof",
        "assert", "errno", "size_t", "FILE", "stdin", "stdout", "stderr",
        "#include", "#define", "#ifdef", "#ifndef", "#endif", "#else", "#elif",
    },
    "C++": {
        "alignas", "alignof", "auto", "bool", "break", "case", "catch",
        "char", "char8_t", "char16_t", "char32_t", "class", "const",
        "constexpr", "const_cast", "continue", "decltype", "default",
        "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit",
        "export", "extern", "false", "float", "for", "friend", "goto",
        "if", "inline", "int", "long", "mutable", "namespace", "new",
        "noexcept", "nullptr", "operator", "private", "protected", "public",
        "register", "reinterpret_cast", "requires", "return", "short",
        "signed", "sizeof", "static", "static_assert", "static_cast",
        "struct", "switch", "template", "this", "thread_local", "throw",
        "true", "try", "typedef", "typeid", "typename", "union", "unsigned",
        "using", "virtual", "void", "volatile", "wchar_t", "while",
        "std", "cout", "cin", "cerr", "endl", "string", "vector", "map",
        "set", "unordered_map", "algorithm", "iostream", "vector", "memory",
        "make_unique", "make_shared", "printf", "malloc", "free", "main",
        "#include", "#define", "#ifdef", "#ifndef", "#endif", "#else", "#elif",
        "#pragma", "#error",
    },
    "Markdown": {
        "#", "##", "###", "####", "#####", "######", "-", "*", "+", "1.",
        ">", "**", "__", "`", "```", "---", "***", "[]", "()", "![", "|",
    },
}

# HTA oraz WSF łączą znaczniki HTML/XML z kodem skryptowym Windows.
AUTO_KEYWORDS["HTA"] = set(AUTO_KEYWORDS["HTML"]) | {
    "HTA:APPLICATION", "WScript", "MsgBox", "window", "onclick", "language",
    "Sub", "End Sub", "Function", "End Function", "Dim", "VBScript", "JScript",
}
AUTO_KEYWORDS["WSF"] = {
    "job", "script", "language", "runtime", "reference", "object", "resource",
    "description", "author", "example", "package", "VBScript", "JScript",
    "WScript", "Echo", "CreateObject",
}


def collect_py_symbols(code: str) -> List[str]:
    """Zbiera nazwy z kodu Python: importy, funkcje, klasy, zmienne, argumenty.

    Przy błędzie składni zwraca pustą listę (podpowiedzi bazują wtedy na
    słowach kluczowych i wbudowanych funkcjach).
    """
    import ast
    names = set()
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    names.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return sorted(n for n in names if n.isidentifier())


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA: graf zależności skryptów (poz. 8 planu działania)
# ══════════════════════════════════════════════════════════════════════════════

_NOT_IDENT_RE = re.compile(r"[^0-9a-zA-Z_]+")


def module_key(nazwa: str) -> str:
    """Zamienia nazwę skryptu na klucz modułu (małe litery, ``_`` zamiast spacji).

    Przykłady: ``"Moja Biblio.py"`` → ``"moja_biblio"``, ``"Util-2"`` → ``"util_2"``.
    Pusty lub bezsensowny wynik zastępowany jest przez ``"bez_nazwy"``.
    """
    base = str(nazwa or "").strip()
    if base.lower().endswith((".py", ".pyw")):
        base = base.rsplit(".", 1)[0]
    base = _NOT_IDENT_RE.sub("_", base).strip("_").lower()
    return base or "bez_nazwy"


def collect_py_imports(code: str) -> List[str]:
    """Zwraca posortowane, unikalne nazwy importowanych modułów najwyższego poziomu.

    Uwzględnia ``import a.b`` oraz ``from a.b import c`` (poziom 0). Przy błędzie
    składni zwraca pustą listę.
    """
    import ast
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return sorted(m for m in mods if m)


def build_dep_graph(skrypty: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Buduje graf zależności między skryptami Python na podstawie importów.

    Węzłami są skrypty kategorii ``Python`` (identyfikowane przez :func:`module_key`).
    Krawędź ``(A, B)`` oznacza, że skrypt A importuje moduł odpowiadający nazwie
    skryptu B. Importy nierozwiązane do żadnego skryptu trafiają do ``external``.

    Returns:
        Dict z kluczami: ``nodes`` ({klucz: {"nazwa", "kategoria", "id"}}),
        ``edges`` (zbiór krotek ``(src, dst)``), ``external``
        ({klucz: [nazwy modułów spoza bazy]}).
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    py_scripts = []
    for s in skrypty or []:
        if not isinstance(s, dict) or s.get("usuniety"):
            continue
        if (s.get("kategoria") or "") != "Python":
            continue
        key = module_key(s.get("nazwa", ""))
        if key in nodes:
            continue
        nodes[key] = {"nazwa": str(s.get("nazwa") or ""),
                      "kategoria": "Python",
                      "id": s.get("id") or ""}
        py_scripts.append((key, s))

    edges = set()
    external: Dict[str, List[str]] = {}
    for key, s in py_scripts:
        ext = []
        for mod in collect_py_imports(s.get("kod") or ""):
            tgt = module_key(mod)
            if tgt != key and tgt in nodes:
                edges.add((key, tgt))
            else:
                ext.append(mod)
        if ext:
            external[key] = ext
    return {"nodes": nodes, "edges": edges, "external": external}


def find_cycles(nodes: Dict[str, Any], edges) -> List[List[str]]:
    """Zwraca cykle w grafie skierowanym (silnie spójne składowe > 1 lub pętle własne).

    Implementacja iteracyjna algorytmu Tarjana (bez rekurencji). Każdy cykl to
    posortowana lista kluczy modułów.
    """
    adj: Dict[str, List[str]] = {n: [] for n in nodes}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, [])
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    result: List[List[str]] = []
    counter = 0
    for root in list(adj):
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, pi = work[-1]
            if pi == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                on_stack[v] = True
            neigh = adj.get(v, [])
            descended = False
            for i in range(pi, len(neigh)):
                w = neigh[i]
                if w not in index:
                    work[-1] = (v, i + 1)
                    work.append((w, 0))
                    descended = True
                    break
                if on_stack.get(w):
                    low[v] = min(low[v], index[w])
            if descended:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in adj.get(v, []):
                    result.append(sorted(comp))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    return result


def find_isolated(nodes: Dict[str, Any], edges) -> List[str]:
    """Zwraca klucze modułów bez żadnych połączeń (ani nie importują, ani nie są importowane)."""
    connected = set()
    for a, b in edges:
        connected.add(a)
        connected.add(b)
    return sorted(n for n in nodes if n not in connected)


class SyntaxHighlighter:
    """
    Podświetla składnię kodu w widżecie tk.Text.
    Używa Pygments – jeśli niedostępny, jest transparentny (brak efektu).
    Wywołaj highlight(widget, kategoria) po każdej zmianie kodu.
    Debounce 120 ms – nie spowalnia pisania.
    Buforowanie wyników dla dużych plików.

    Attributes:
        _cache: Dict[(checksum, category): highlighted_tokens] - bufor podświetlania
    """

    DEBOUNCE_MS = HIGHLIGHT_DEBOUNCE_MS
    CACHE_MAX_SIZE = 50  # maksymalna liczba wpisów w buforze

    def __init__(self, app):
        """
        Inicjalizuje highlighter.

        Args:
            app: Główna instancja aplikacji tkinter.
        """
        self.app = app
        self._after_id = None
        self._active_widget = None
        self._active_category = "Python"
        self._cache: Dict[Tuple[str, str], Any] = {}

    def attach(self, widget, get_category_fn):
        """
        Podłącz highlighter do widżetu Text.
        get_category_fn() → string z aktualną kategorią skryptu.
        """
        if not _PYGMENTS_OK:
            return
        widget.bind("<KeyRelease>",
                    lambda e: self._schedule(widget, get_category_fn()), add="+")
        # Skonfiguruj tagi kolorów (raz)
        for token, color in _HL_COLORS.items():
            tag = self._tag(token)
            widget.tag_configure(tag, foreground=color)
        # Dodatkowe tagi semantyczne
        widget.tag_configure("hl_string_doc", foreground="#546e7a", font=("Consolas", 10, "italic"))

    def _tag(self, token):
        return "hl_" + str(token).replace(".", "_").replace(" ", "")

    def _schedule(self, widget, category):
        if self._after_id:
            self.app.after_cancel(self._after_id)
        self._active_widget   = widget
        self._active_category = category
        self._after_id = self.app.after(self.DEBOUNCE_MS, self._run)

    def _run(self):
        self._after_id = None
        widget   = self._active_widget
        category = self._active_category
        if not widget or not widget.winfo_exists():
            return
        self.highlight(widget, category)

    def highlight(self, widget, category: str) -> None:
        """
        Pełne podświetlenie zawartości widżetu z buforowaniem.

        Args:
            widget: Widżet tk.Text do podświetlenia.
            category: Kategoria języka (Python, Bash, itp.).
        """
        if not _PYGMENTS_OK:
            return
        code = widget.get("1.0", "end-1c")
        if not code.strip():
            return

        # Sprawdź bufor
        checksum = kod_checksum(code)
        cache_key = (checksum, category)
        if cache_key in self._cache:
            self._apply_cached(widget, self._cache[cache_key])
            return

        # Usuń stare tagi
        for tag in widget.tag_names():
            if tag.startswith("hl_"):
                widget.tag_remove(tag, "1.0", "end")

        # Wybierz lexer
        lex_name = _CATEGORY_LEXER.get(category, "text")
        try:
            lexer = get_lexer_by_name(lex_name, stripall=False)
        except Exception as e:
            logging.warning(f"Błąd lexer dla {category}: {e}")
            return

        # Zastosuj tokeny i zapisz w buforze
        tokens_to_apply = []
        row, col = 1, 0
        defined_tags = set(widget.tag_names())
        for token_type, value in lex(code, lexer):
            # Znajdź kolor (szukaj ogólniejszego tokenu jeśli brak dokładnego)
            color_tag = None
            t = token_type
            while t:
                if t in _HL_COLORS:
                    color_tag = self._tag(t)
                    break
                t = t.parent
            if not color_tag:
                t = token_type
                while t:
                    tag = self._tag(t)
                    if tag in defined_tags and widget.tag_cget(tag, "foreground"):
                        color_tag = tag
                        break
                    t = t.parent if hasattr(t, 'parent') else None

            lines = value.split("\n")
            for li, line in enumerate(lines):
                if li > 0:
                    row += 1
                    col  = 0
                end_col = col + len(line)
                if color_tag and line:
                    start = f"{row}.{col}"
                    end   = f"{row}.{end_col}"
                    widget.tag_add(color_tag, start, end)
                    tokens_to_apply.append((color_tag, start, end))
                col = end_col

        # Zapisz w buforze z limitem rozmiaru
        if len(self._cache) >= self.CACHE_MAX_SIZE:
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = tokens_to_apply

    def _apply_cached(self, widget, tokens: List[Tuple[str, str, str]]) -> None:
        """
        Aplikuje zbuforowane tokeny do widżetu.

        Args:
            widget: Widżet tk.Text.
            tokens: Lista (tag, start, end) do zastosowania.
        """
        # Usuń stare tagi
        for tag in widget.tag_names():
            if tag.startswith("hl_"):
                widget.tag_remove(tag, "1.0", "end")
        # Aplikuj zbuforowane
        for tag, start, end in tokens:
            widget.tag_add(tag, start, end)


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 5b: AUTOCOMPLETER — podpowiedzi w edytorze kodu
# ══════════════════════════════════════════════════════════════════════════════
class AutoCompleter:
    """Autouzupełnianie kodu: okno podpowiedzi wywoływane skrótem Ctrl+Space.

    Źródłem podpowiedzi są słowa kluczowe Pythona, wbudowane funkcje oraz
    symbole wyłuskane z aktualnego kodu (importy, funkcje, klasy, zmienne,
    argumenty). Okno pozostaje bez fokusu — nawigacja odbywa się klawiszami
    obsługiwanymi na widżecie edytora.

    Dodatkowo:
    * dopasowanie substring — gdy nic nie zaczyna się od prefiksu, szukamy
      podpowiedzi zawierających prefiks w środku nazwy,
    * podpowiedzi metod/atrybutów po kropce (``obj.``) na podstawie wywnioskowanego
      typu (str/list/dict/set/tuple), ``self.`` oraz modułów z importów,
    * automatyczne otwieranie okna po wpisaniu co najmniej AUTO_OPEN_LEN znaków
      (bez Ctrl+Space).
    """

    MAX_ITEMS = 12
    POPUP_W   = 240
    POPUP_H   = 220
    AUTO_OPEN_LEN = 3

    # Metody/atrybuty popularnych typów wbudowanych — dla podpowiedzi po kropce.
    ATTRS: Dict[str, Tuple[str, ...]] = {
        "str":   ("upper", "lower", "title", "strip", "lstrip", "rstrip",
                  "split", "rsplit", "splitlines", "join", "replace",
                  "startswith", "endswith", "find", "rfind", "count",
                  "format", "encode", "decode", "isdigit", "isalpha",
                  "capitalize", "center", "zfill", "partition"),
        "list":  ("append", "extend", "insert", "remove", "pop", "clear",
                  "index", "count", "sort", "reverse", "copy"),
        "dict":  ("keys", "values", "items", "get", "pop", "popitem",
                  "update", "setdefault", "clear", "copy"),
        "set":   ("add", "remove", "discard", "pop", "clear", "union",
                  "intersection", "difference", "issubset", "issuperset",
                  "copy"),
        "tuple": ("count", "index"),
    }

    def __init__(self, app):
        self.app = app
        self._win: Optional[tk.Toplevel] = None
        self._list: Optional[tk.Listbox] = None
        self._text: Optional[tk.Text] = None
        self._start_idx: Optional[str] = None
        self._items: List[str] = []

    # ── podłączanie ──────────────────────────────────────────────────────────
    def attach(self, widget, get_category_fn) -> None:
        """Podłącza obsługę podpowiedzi do widżetu Text."""
        widget.bind("<Control-space>",
                    lambda e, w=widget, g=get_category_fn: self.popup(w, g()), add="+")
        widget.bind("<Escape>", lambda e: self.hide(), add="+")
        widget.bind("<Up>", lambda e: self._nav(-1), add="+")
        widget.bind("<Down>", lambda e: self._nav(1), add="+")
        widget.bind("<Return>", lambda e: self._accept(), add="+")
        widget.bind("<Tab>", lambda e: self._accept(), add="+")
        widget.bind("<Button-1>", lambda e: self.hide(), add="+")
        widget.bind("<FocusOut>", lambda e: self.hide(), add="+")
        widget.bind("<KeyRelease>",
                    lambda e, w=widget, g=get_category_fn: self._on_key(w, g(), e), add="+")

    # ── logika ───────────────────────────────────────────────────────────────
    def _prefix(self, widget: tk.Text) -> Tuple[str, Optional[str]]:
        """Zwraca (prefiks, indeks początku) na podstawie tekstu przed kursorem."""
        try:
            line = widget.get("insert linestart", "insert")
        except Exception:
            return "", None
        m = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", line)
        if not m:
            return "", None
        prefix = m.group(0)
        return prefix, f"insert-{len(prefix)}c"

    def _dot_context(self, widget: tk.Text) -> Optional[str]:
        """Jeśli przed kursorem jest ``nazwa.``, zwraca nazwę obiektu."""
        try:
            line = widget.get("insert linestart", "insert")
        except Exception:
            return None
        m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\.$", line)
        return m.group(1) if m else None

    def _dot_candidates(self, obj: str, code: str) -> List[str]:
        """Kandydaci po kropce: metody wywnioskowanego typu, ``self.*``, moduły."""
        names: set = set()
        inferred = self._infer_types(code)
        if obj in inferred:
            names |= set(self.ATTRS.get(inferred[obj], ()))
        if obj == "self":
            names |= set(self._collect_self_attrs(code))
        imported = set(collect_py_symbols(code))
        if obj in imported:
            names |= set(PY_MODULE_ATTRS.get(obj, ()))
        return sorted(n for n in names if n)

    @staticmethod
    def _infer_types(code: str) -> Dict[str, str]:
        """Wniosek o typie zmiennych z przypisań literałów: x = "s", x = []..."""
        import ast
        out: Dict[str, str] = {}
        try:
            tree = ast.parse(code or "")
        except SyntaxError:
            return out
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                v = node.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out[name] = "str"
                elif isinstance(v, ast.List):
                    out[name] = "list"
                elif isinstance(v, ast.Dict):
                    out[name] = "dict"
                elif isinstance(v, ast.Set):
                    out[name] = "set"
                elif isinstance(v, ast.Tuple):
                    out[name] = "tuple"
        return out

    @staticmethod
    def _collect_self_attrs(code: str) -> List[str]:
        """Zbiera nazwy atrybutów przypisywanych do ``self.`` w kodzie."""
        import ast
        try:
            tree = ast.parse(code or "")
        except SyntaxError:
            return []
        names = {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and isinstance(node.ctx, ast.Store)
        }
        return sorted(names)

    def _candidates(self, category: str, code: str) -> List[str]:
        """Zwraca kandydatów podpowiedzi dopasowanych do kategorii.

        Dla Pythona dołączane są także symbole wyłuskane z aktualnego kodu;
        dla pozostałych kategorii — zestaw słów kluczowych/znaczników.
        """
        if not category or category == "Python":
            names = set(PY_KEYWORDS) | set(PY_BUILTINS)
            names |= set(collect_py_symbols(code))
        else:
            names = set(AUTO_KEYWORDS.get(category, ()))
        return sorted(names, key=str.lower)

    def popup(self, widget: tk.Text, category: str) -> str:
        """Pokazuje okno podpowiedzi dopasowane do prefiksu przed kursorem."""
        try:
            code = widget.get("1.0", "end-1c")
        except Exception:
            return "break"
        # Kropka: podpowiedź metod/atrybutów obiektu przed kursorem.
        dot_obj = self._dot_context(widget)
        start = None
        prefix = ""
        if dot_obj:
            cands = self._dot_candidates(dot_obj, code)
        else:
            prefix, start = self._prefix(widget)
            cands = self._candidates(category, code)
        if prefix:
            low = prefix.casefold()
            items = [c for c in cands if c.casefold().startswith(low) and c != prefix]
            # Fallback substring: gdy nic nie zaczyna się od prefiksu,
            # szukamy nazw zawierających prefiks w środku.
            if not items:
                items = [c for c in cands if low in c.casefold() and c != prefix]
        else:
            items = cands
        if not items:
            self.hide()
            return "break"
        self._text = widget
        self._start_idx = start  # None przy podpowiedzi po kropce — nic nie usuwamy
        self._items = items[:self.MAX_ITEMS]
        self._render(widget)
        return "break"

    def _render(self, widget: tk.Text) -> None:
        if self._win is None:
            self._win = _popup(self.app)
            self._win.wm_overrideredirect(True)
            try:
                self._win.attributes("-topmost", True)
            except Exception:
                pass
            frame = tk.Frame(self._win, bg=BORDER_CLR, bd=0,
                             highlightthickness=1, highlightbackground=ACCENT_BLUE)
            frame.pack(fill="both", expand=True)
            self._list = tk.Listbox(frame, font=FONT_MONO, bg="#252840", fg="#c8d0f0",
                                    selectbackground=ACCENT_BLUE, selectforeground="#ffffff",
                                    relief="flat", highlightthickness=0, activestyle="none",
                                    exportselection=False)
            self._list.pack(fill="both", expand=True, padx=1, pady=1)
        self._list.delete(0, "end")
        for it in self._items:
            self._list.insert("end", it)
        self._list.selection_clear(0, "end")
        self._list.selection_set(0)
        self._list.activate(0)
        h = min(self.POPUP_H, max(20, len(self._items) * 18 + 6))
        try:
            bbox = widget.bbox("insert")
        except Exception:
            bbox = None
        if bbox:
            x = widget.winfo_rootx() + bbox[0]
            y = widget.winfo_rooty() + bbox[1] + bbox[3]
        else:
            x = widget.winfo_rootx() + 40
            y = widget.winfo_rooty() + 40
        self._win.geometry(f"{self.POPUP_W}x{h}+{x}+{y}")
        self._win.lift()

    def _on_key(self, widget: tk.Text, category: str, event) -> None:
        """Po wpisaniu znaku zawęża listę, po innym znaku zamyka okno.

        Kropka otwiera podpowiedzi metod/atrybutów; prefiks o długości co
        najmniej AUTO_OPEN_LEN otwiera okno automatycznie (bez Ctrl+Space).
        """
        # Ctrl+Space (wywołanie okna) ani klawisze nawigacji nie zmieniają listy.
        if event.state & 0x0004:  # modyfikator Ctrl
            return
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape",
                            "Control_L", "Control_R"):
            return
        ch = event.char
        if ch == ".":
            # Po kropce pokazujemy metody/atrybuty obiektu przed kursorem.
            widget.after_idle(lambda: self.popup(widget, category))
            return
        if ch and (ch.isalnum() or ch == "_"):
            if self._win is not None:
                self.popup(widget, category)
            else:
                # Auto-popup: wystarczająco długi prefiks słowa otwiera okno.
                prefix, _ = self._prefix(widget)
                if len(prefix) >= self.AUTO_OPEN_LEN:
                    self.popup(widget, category)
        else:
            self.hide()

    def is_open(self) -> bool:
        """Czy okno podpowiedzi jest aktualnie otwarte."""
        return self._win is not None

    def _nav(self, delta: int) -> Optional[str]:
        """Przesuwa zaznaczenie w oknie podpowiedzi."""
        if self._win is None or self._list is None:
            return None
        sel = self._list.curselection()
        cur = sel[0] if sel else 0
        nxt = max(0, min(len(self._items) - 1, cur + delta))
        self._list.selection_clear(0, "end")
        self._list.selection_set(nxt)
        self._list.activate(nxt)
        self._list.see(nxt)
        return "break"

    def _accept(self) -> Optional[str]:
        """Wstawia zaznaczoną podpowiedź w miejscu kursora."""
        if self._win is None or self._list is None:
            return None
        sel = self._list.curselection()
        if not sel:
            self.hide()
            return "break"
        value = self._list.get(sel[0])
        widget = self._text
        if widget is not None:
            if self._start_idx:
                widget.delete(self._start_idx, "insert")
            widget.insert("insert", value)
        self.hide()
        return "break"

    def hide(self) -> None:
        """Zamyka okno podpowiedzi."""
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
            self._list = None


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 6: MOUSE MANAGER — pełna obsługa myszy
# ══════════════════════════════════════════════════════════════════════════════
class MouseManager:
    """
    Kompleksowa obsługa myszy dla całej aplikacji.

    SCROLL
    ──────
    Kółko myszy        → pionowy scroll łańcuchem hierarchii (widget → przodek,
                         z propagacją na granicy zakresu; duck-typing, nie isinstance)
    Shift/Alt + kółko  → poziomy scroll; fallback na pionowy, gdy brak przewijanego
    Ctrl + kółko       → zoom czcionki edytorów (7-28 pt)
    Środkowy przycisk  → pan dla każdego przewijanego widżetu (obie osie)

    MENU KONTEKSTOWE (prawy klik bez gestu)
    ──────────────────────────────────────
    tk.Text (edytor kodu)   → clipboard, transformacje, kod (komentuj/wcinaj),
                               sortuj linie, usuń duplikaty, Znajdź/Zastąp, zoom
    tk.Text (opis/log)      → uproszczone clipboard + transformacje + zoom
    ttk.Treeview            → CRUD, duplikuj, eksport zaznaczenia, sortowanie,
                               filtr kategorii, statystyki
    tk.Listbox              → kopiuj, usuń, eksportuj
    ttk.Entry / ttk.Combobox→ clipboard, wyczyść, historia, lista wartości
    tk.Canvas               → zoom, reset widoku, eksport PS
    ogólne (Frame/inne)     → skróty, gesty-ściągawka, o programie

    GESTY (prawy przycisk + przeciągnięcie >= 40px)
    ───────────────────────────────────────────────
    L → R   → następna zakładka
    R → L   → poprzednia zakładka
    ↓       → odśwież
    ↑       → nowy skrypt
    ↗       → eksport bazy
    ↖       → import bazy
    ↘       → szukaj
    ↙       → lista skryptów

    Attributes:
        app: Główna instancja aplikacji tkinter.
    """

    TOOLTIP_DELAY_MS  = TOOLTIP_DELAY_MS
    TOOLTIP_GRACE_MS  = TOOLTIP_GRACE_MS
    GESTURE_THRESHOLD = GESTURE_THRESHOLD
    FONT_SIZE_MIN     = FONT_SIZE_MIN
    FONT_SIZE_MAX     = FONT_SIZE_MAX
    FONT_FAMILY       = FONT_FAMILY

    _EDITOR_ATTRS = [
        "text_kod", "text_opis", "text_preview",
        "edytor_text", "diag_text", "adv_preview",
        "venv_log_text", "venv_req_text",
        "db_result_text", "tools_text",
    ]

    def __init__(self, app):
        """
        Inicjalizuje menedżer myszy.

        Args:
            app: Główna instancja aplikacji tkinter.
        """
        self.app = app

        self._pan_active   = False
        self._pan_widget   = None
        self._pan_start_x  = 0
        self._pan_start_y  = 0
        self._pan_acc_x    = 0.0
        self._pan_acc_y    = 0.0

        self._gesture_start_x = 0
        self._gesture_start_y = 0
        self._gesture_active  = False
        self._gesture_widget  = None
        self._gesture_moved   = False

        self._tooltip_win        = None
        self._tooltip_win_widget = None
        self._tooltip_after      = None
        self._tooltip_hide       = None
        self._tooltip_dismiss    = None
        self._tooltip_widget     = None

        self._editor_font_size = 10
        self._zoom_toast       = None
        self._ctx_menu         = None
        self._entry_history    = {}

        app.bind_all("<Button-2>",        self._on_middle_press)
        app.bind_all("<B2-Motion>",       self._on_middle_drag)
        app.bind_all("<ButtonRelease-2>", self._on_middle_release)
        app.bind_all("<MouseWheel>",      self._on_mousewheel_global)
        app.bind_all("<Button-4>",        self._on_mousewheel_global)
        app.bind_all("<Button-5>",        self._on_mousewheel_global)
        app.bind_all("<Shift-Button-4>",  self._on_mousewheel_global)
        app.bind_all("<Shift-Button-5>",  self._on_mousewheel_global)
        app.bind_all("<Button-3>",        self._on_right_press)
        app.bind_all("<B3-Motion>",       self._on_gesture_motion)
        app.bind_all("<ButtonRelease-3>", self._on_right_release)
        app.bind_all("<Control-a>",       self._on_ctrl_a)

    # ── TOOLTIPS ──────────────────────────────────────────────────────────────
    def attach_tooltip(self, widget, text):
        # Tooltipy (chmurki z opisami) wyłączone — ich okienka mrugały
        # przy najechaniu na zakładki. Metoda zostaje jako no-op, żeby
        # istniejące wywołania nie wymagały zmian.
        return

    def _tooltip_schedule(self, widget, text):
        # Powrót na widget z widocznym tooltipem (drganie kursora przy
        # krawędzi albo skrzyżowanie z innym widgetem i powrót) — zostaw
        # go, nie pokazuj ponownie. Zapobiega pętli show/hide = mruganiu.
        if self._tooltip_win is not None and widget is self._tooltip_win_widget:
            self._cancel_tooltip_timers()
            self._tooltip_widget = widget
            return
        # Ten sam widget ma jeszcze oczekujący pokaz — nie resetuj timera.
        if self._tooltip_widget is widget and self._tooltip_after is not None:
            self._cancel_tooltip_hide()
            return
        # Inny widget: widoczny tooltip NIE jest niszczony od razu — dostaje
        # krótki grace period, więc szybki powrót nie powoduje mrugania.
        self._cancel_tooltip_timers()
        if self._tooltip_win is not None:
            self._tooltip_dismiss = self.app.after(
                self.TOOLTIP_GRACE_MS, self._tooltip_dismiss_win)
        self._tooltip_widget = widget
        self._tooltip_after  = self.app.after(
            self.TOOLTIP_DELAY_MS,
            lambda: self._tooltip_show(widget, text))

    def _tooltip_leave(self):
        """Opuścenie widgetu — ukryj tooltip z małym opóźnieniem.

        Bez opóźnienia tooltip pojawiający się pod kursorem powoduje
        natychmiastowy <Leave> → destroy → <Enter> → pokazanie — mruganie.
        """
        if (self._tooltip_win is None and self._tooltip_after is None
                and self._tooltip_dismiss is None):
            return
        if self._tooltip_hide:
            try:
                self.app.after_cancel(self._tooltip_hide)
            except Exception:
                pass
        self._tooltip_hide = self.app.after(250, self._tooltip_cancel)

    def _cancel_tooltip_timers(self):
        for attr in ("_tooltip_after", "_tooltip_hide", "_tooltip_dismiss"):
            tid = getattr(self, attr, None)
            if tid:
                try:
                    self.app.after_cancel(tid)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _tooltip_dismiss_win(self):
        """Zniszcz samą ramkę tooltipa po grace period — timery (np.
        oczekujący pokaz nowego widgetu) zostają nietknięte."""
        self._tooltip_dismiss = None
        if self._tooltip_win is not None:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None
            self._tooltip_win_widget = None

    def _tooltip_cancel(self):
        self._cancel_tooltip_timers()
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None
            self._tooltip_win_widget = None
        self._tooltip_widget = None

    def _tooltip_show(self, widget, text):
        self._tooltip_after = None  # timer już się wyzwolił
        if not widget.winfo_exists():
            return
        # Nie pokazuj, gdy wskaźnik już opuścił widget (np. szybkie
        # przeciągnięcie kursora między elementami).
        try:
            px, py = self.app.winfo_pointerxy()
            cont = self.app.winfo_containing(px, py)
            w = cont
            over = False
            while w is not None:
                if str(w) == str(widget):
                    over = True
                    break
                try:
                    w = w.nametowidget(w.winfo_parent())
                except Exception:
                    break
            if not over:
                return
        except Exception:
            pass
        try:
            x = widget.winfo_rootx() + 12
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            sw = self.app.winfo_screenwidth()
            if x + 220 > sw:
                x = sw - 224
            # Przytnij Y do ekranu — Windows może przenieść okno nad widget.
            sh = self.app.winfo_screenheight()
            if y + 60 > sh:
                y = max(8, widget.winfo_rooty() - 66)
        except Exception:
            return
        # Stary tooltip (np. w grace period) ustępuje nowemu.
        if self._tooltip_win is not None:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
        self._tooltip_win = None
        self._tooltip_win_widget = None
        self._tooltip_after = None
        win = _popup(self.app)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        win.attributes("-topmost", True)
        # Można najechać na tooltip — wtedy nie ukrywaj go od razu.
        win.bind("<Enter>", lambda e: self._cancel_tooltip_hide())
        win.bind("<Leave>", lambda e: self._tooltip_cancel())
        outer = tk.Frame(win, bg="#3a3f58", bd=1)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text=_tr(text), font=("Consolas", 8),
                 bg="#1e2130", fg="#c8d0f0",
                 padx=10, pady=5, justify="left").pack()
        self._tooltip_win = win
        self._tooltip_win_widget = widget

    def _cancel_tooltip_hide(self):
        for attr in ("_tooltip_hide", "_tooltip_dismiss"):
            tid = getattr(self, attr, None)
            if tid:
                try:
                    self.app.after_cancel(tid)
                except Exception:
                    pass
                setattr(self, attr, None)

    # ── ŚRODKOWY PRZYCISK — PAN ────────────────────────────────────────────────
    def _on_middle_press(self, event):
        w = event.widget
        self._pan_active  = True
        self._pan_widget  = w
        self._pan_start_x = event.x_root
        self._pan_start_y = event.y_root
        self._pan_acc_x   = 0.0
        self._pan_acc_y   = 0.0
        try:
            w.config(cursor="fleur")
        except Exception:
            pass

    def _on_middle_drag(self, event):
        if not self._pan_active or not self._pan_widget:
            return
        w  = self._pan_widget
        dx = self._pan_start_x - event.x_root
        dy = self._pan_start_y - event.y_root
        self._pan_start_x = event.x_root
        self._pan_start_y = event.y_root
        self._pan_acc_x += dx / 4.0
        self._pan_acc_y += dy / 3.0
        ix = int(self._pan_acc_x)
        iy = int(self._pan_acc_y)
        if ix: self._pan_acc_x -= ix
        if iy: self._pan_acc_y -= iy
        try:
            self._pan_scroll(w, ix, iy)
        except Exception:
            pass

    def _on_middle_release(self, event):
        if self._pan_widget:
            try:
                self._pan_widget.config(cursor="")
            except Exception:
                pass
        self._pan_active = False
        self._pan_widget = None

    # ── KÓŁKO MYSZY ────────────────────────────────────────────────────────────
    def _on_mousewheel_global(self, event):
        state = event.state
        ctrl  = bool(state & 0x4)
        shift = bool(state & 0x1)
        alt   = bool(state & 0x8)
        if ctrl:
            self._zoom_font(event)
            return "break"
        delta = self._get_delta(event)
        if delta == 0:
            return "break"
        if shift or alt:
            # Shift/Alt + kółko = przewijanie poziome; gdy w łańcuchu nie ma
            # przewijanego w poziomie — fallback na pionowe.
            if not self._scroll_axis(event.widget, "x", delta):
                self._scroll_axis(event.widget, "y", -delta)
            return "break"
        if not self._scroll_axis(event.widget, "y", -delta):
            # Gdy pionowe przewijanie nigdzie nie prowadzi (brak przewijanego
            # widgetu albo osiągnięty kres zakresu) — spróbuj poziomo.
            # Dzięki temu kółko działa też nad szerokimi Entry/Treeview/Canvas.
            self._scroll_axis(event.widget, "x", -delta)
        return "break"

    def _get_delta(self, event):
        if event.num == 4: return  3
        if event.num == 5: return -3
        d = getattr(event, "delta", 0)
        if d == 0:         return  0
        return max(-5, min(5, d // 40)) or (1 if d > 0 else -1)

    @staticmethod
    def _scrollable(w, axis):
        """Czy widget obsługuje przewijanie wzdłuż danej osi (duck-typing)."""
        return (hasattr(w, f"{axis}view") and hasattr(w, f"{axis}view_scroll"))

    def _scroll_axis(self, widget, axis, units):
        """Przewija najbliższy przewijany widget w łańcuchu hierarchii.

        Zaczyna od samego widgetu i idzie w górę przez przodków — dzięki temu
        kółko działa także nad dziećmi przewijanych kontenerów (np. elementy
        wewnątrz Canvas). Gdy widget jest na krańcu zakresu (pozycja się nie
        zmienia), przewijanie propaguje się do najbliższego przewijanego
        przodka.

        Args:
            widget: widget, od którego zaczyna się szukanie.
            axis: "x" (poziomo) lub "y" (pionowo).
            units: liczba jednostek przewinięcia (znak = kierunek).

        Returns:
            bool: True, gdy faktycznie doszło do przewinięcia.
        """
        view = f"{axis}view"
        scroll = f"{axis}view_scroll"
        for w in self._widget_chain(widget):
            if not self._scrollable(w, axis):
                continue
            try:
                before = getattr(w, view)()
                getattr(w, scroll)(units, "units")
                if getattr(w, view)() != before:
                    return True
            except Exception:
                continue
        return False

    def _pan_scroll(self, widget, ix, iy):
        """Przewija widget (lub najbliższego przewijanego przodka) podczas panoru
        środkowym przyciskiem myszy. Działa dla obu osi jednocześnie."""
        if not (ix or iy):
            return
        for w in self._widget_chain(widget):
            moved = False
            for axis, amount in (("y", iy), ("x", ix)):
                if not amount or not self._scrollable(w, axis):
                    continue
                view = f"{axis}view"
                scroll = f"{axis}view_scroll"
                try:
                    before = getattr(w, view)()
                    getattr(w, scroll)(amount, "units")
                    if getattr(w, view)() != before:
                        moved = True
                except Exception:
                    pass
            if moved:
                return

    def _widget_chain(self, widget):
        w = widget
        visited = set()
        while w and str(w) not in visited:
            visited.add(str(w))
            yield w
            try:
                w = w.nametowidget(w.winfo_parent())
            except Exception:
                break

    # ── ZOOM ───────────────────────────────────────────────────────────────────
    def _zoom_font(self, event):
        delta = self._get_delta(event)
        new_size = max(self.FONT_SIZE_MIN,
                       min(self.FONT_SIZE_MAX,
                           self._editor_font_size + (1 if delta > 0 else -1)))
        if new_size == self._editor_font_size:
            return
        self._editor_font_size = new_size
        self._apply_zoom()
        self._show_zoom_toast(new_size)

    def _zoom_step(self, step):
        new_size = max(self.FONT_SIZE_MIN,
                       min(self.FONT_SIZE_MAX, self._editor_font_size + step))
        self._editor_font_size = new_size
        self._apply_zoom()
        self._show_zoom_toast(new_size)

    def _zoom_reset(self):
        self._editor_font_size = 10
        self._apply_zoom()
        self._show_zoom_toast(10)

    def _apply_zoom(self):
        font = (self.FONT_FAMILY, self._editor_font_size)
        for attr in self._EDITOR_ATTRS:
            try:
                w = getattr(self.app, attr, None)
                if w and w.winfo_exists():
                    w.config(font=font)
            except Exception:
                pass

    def _show_zoom_toast(self, size):
        if self._zoom_toast:
            try:
                self._zoom_toast.destroy()
            except Exception:
                pass
        win = _popup(self.app)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        rx = self.app.winfo_rootx() + self.app.winfo_width() - 170
        ry = self.app.winfo_rooty() + 55
        win.wm_geometry(f"+{rx}+{ry}")
        bar = tk.Frame(win, bg="#2a304a", bd=0)
        bar.pack(fill="both", expand=True)
        bar2 = tk.Frame(bar, bg="#4a90d9", width=3)
        bar2.pack(side="left", fill="y")
        tk.Label(bar, text=f"  {_t('toast_font_size', size=size)}  ",
                 font=("Consolas", 10, "bold"),
                 bg="#2a304a", fg="#82aaff",
                 padx=6, pady=8).pack(side="left")
        self._zoom_toast = win
        self.app.after(1400, lambda: self._safe_destroy(win))

    def _safe_destroy(self, win):
        """Bezpiecznie niszczy okno jeśli istnieje."""
        if win.winfo_exists():
            win.destroy()

    # ── PRAWY PRZYCISK — GESTY ─────────────────────────────────────────────────
    def _on_right_press(self, event):
        self._gesture_start_x = event.x_root
        self._gesture_start_y = event.y_root
        self._gesture_active  = True
        self._gesture_widget  = event.widget
        self._gesture_moved   = False

    def _on_gesture_motion(self, event):
        if not self._gesture_active:
            return
        dx = event.x_root - self._gesture_start_x
        dy = event.y_root - self._gesture_start_y
        if abs(dx) > 6 or abs(dy) > 6:
            self._gesture_moved = True

    def _on_right_release(self, event):
        if not self._gesture_active:
            return
        dx   = event.x_root - self._gesture_start_x
        dy   = event.y_root - self._gesture_start_y
        dist = (dx**2 + dy**2) ** 0.5
        self._gesture_active = False
        if dist >= self.GESTURE_THRESHOLD and self._gesture_moved:
            self._handle_gesture(dx, dy, event)
        else:
            self._tooltip_cancel()
            self._show_context_menu(event)

    def _handle_gesture(self, dx, dy, event):
        adx, ady = abs(dx), abs(dy)
        ratio = adx / (ady + 0.001)
        if 0.4 < ratio < 2.5:
            if dx > 0 and dy < 0:
                try: self.app._lista_eksportuj()
                except Exception: pass
                self._show_gesture_toast("Eksport bazy")
                return
            if dx < 0 and dy < 0:
                try: self.app._lista_importuj()
                except Exception: pass
                self._show_gesture_toast("Import bazy")
                return
            if dx > 0 and dy > 0:
                try: self.app._menu_pokaz_szukaj()
                except Exception: pass
                self._show_gesture_toast("Szukaj")
                return
            if dx < 0 and dy > 0:
                try: self.app._menu_pokaz_liste()
                except Exception: pass
                self._show_gesture_toast("Lista skryptow")
                return
        if adx > ady:
            if dx > 0:
                self._gesture_next_tab(1)
                self._show_gesture_toast("Nastepna zakladka")
            else:
                self._gesture_next_tab(-1)
                self._show_gesture_toast("Poprzednia zakladka")
        else:
            if dy > 0:
                try: self.app._menu_odswiez()
                except Exception: pass
                self._show_gesture_toast("Odswiezone")
            else:
                try: self.app._menu_nowy_skrypt()
                except Exception: pass
                self._show_gesture_toast("Nowy skrypt")

    def _gesture_next_tab(self, direction):
        btns = getattr(self.app, "_main_btns", [])
        if not btns:
            return
        active = 0
        for i, b in enumerate(btns):
            try:
                if b.cget("bg") == BG_TAB_ACT:
                    active = i
                    break
            except Exception:
                pass
        nxt = (active + direction) % len(btns)
        try:
            btns[nxt].invoke()
        except Exception:
            pass

    def _show_gesture_toast(self, text):
        if hasattr(self, "_gesture_toast") and self._gesture_toast:
            try:
                self._gesture_toast.destroy()
            except Exception:
                pass
        win = _popup(self.app)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        rx = self.app.winfo_rootx() + self.app.winfo_width()  // 2 - 110
        ry = self.app.winfo_rooty() + self.app.winfo_height() // 2 - 28
        win.wm_geometry(f"+{rx}+{ry}")
        frm = tk.Frame(win, bg="#1a2040", highlightthickness=1,
                       highlightbackground="#4a90d9")
        frm.pack(fill="both", expand=True)
        tk.Label(frm, text=_tr(text),
                 font=("Consolas", 12, "bold"),
                 bg="#1a2040", fg="#6dde84",
                 padx=22, pady=14).pack()
        self._gesture_toast = win
        self.app.after(900, lambda: self._safe_destroy(win))

    # ── MENU KONTEKSTOWE ───────────────────────────────────────────────────────
    def _make_menu(self):
        return tk.Menu(self.app, tearoff=0,
                       bg="#252840", fg="#c8d0f0",
                       activebackground="#4a90d9",
                       activeforeground="#ffffff",
                       relief="flat", bd=1, font=("Consolas", 9))

    def _has_sel(self, w):
        try:
            w.get("sel.first", "sel.last")
            return True
        except Exception:
            return False

    def _show_context_menu(self, event):
        """
        Główna metoda pokazująca menu kontekstowe.
        Deleguje do wyspecjalizowanych metod dla każdego typu widżetu.
        """
        if self._ctx_menu:
            try:
                self._ctx_menu.destroy()
            except Exception as e:
                logging.warning(f"Błąd usuwania starego menu: {e}")

        w = event.widget
        app = self.app
        menu = self._make_menu()

        # Deleguj do odpowiedniej metody
        if isinstance(w, tk.Text) and str(w.cget("state")) != "disabled":
            self._build_text_menu(menu, w, app)
        elif isinstance(w, ttk.Treeview):
            self._build_treeview_menu(menu, w, app)
        elif isinstance(w, tk.Listbox):
            self._build_listbox_menu(menu, w, app)
        elif isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox)):
            self._build_entry_menu(menu, w, app)
        elif isinstance(w, tk.Canvas):
            self._build_canvas_menu(menu, w, app)
        else:
            self._build_general_menu(menu, app)

        self._ctx_menu = menu
        menu.tk_popup(event.x_root, event.y_root)

    def _add_zoom_submenu(self, menu):
        """Dodaje podmenu zoom do menu."""
        zoom_m = self._make_menu()
        zoom_m.add_command(label="Powieksz  (Ctrl+scroll)",
                           command=lambda: self._zoom_step(+1))
        zoom_m.add_command(label="Pomniejsz (Ctrl+scroll)",
                           command=lambda: self._zoom_step(-1))
        zoom_m.add_separator()
        for sz in [8, 9, 10, 11, 12, 14, 16, 18, 20, 24]:
            zoom_m.add_command(
                label=f"  {sz} pt" + ("  +" if sz == self._editor_font_size else ""),
                command=lambda s=sz: (
                    setattr(self, "_editor_font_size", s),
                    self._apply_zoom(),
                    self._show_zoom_toast(s)))
        zoom_m.add_separator()
        zoom_m.add_command(label="Reset (10 pt)", command=self._zoom_reset)
        menu.add_cascade(label="Zoom czcionki", menu=zoom_m)

    def _build_text_menu(self, menu, w, app):
        """Buduje menu kontekstowe dla tk.Text."""
        is_code = (w is getattr(app, "text_kod", None) or
                   w is getattr(app, "edytor_text", None))

        menu.add_command(label="Wytnij         Ctrl+X",
                         command=lambda: w.event_generate("<<Cut>>"))
        menu.add_command(label="Kopiuj         Ctrl+C",
                         command=lambda: w.event_generate("<<Copy>>"))
        menu.add_command(label="Wklej           Ctrl+V",
                         command=lambda: w.event_generate("<<Paste>>"))
        menu.add_command(label="Cofnij          Ctrl+Z",
                         command=lambda: w.event_generate("<<Undo>>"))
        menu.add_command(label="Ponow           Ctrl+Y",
                         command=lambda: w.event_generate("<<Redo>>"))
        menu.add_separator()
        menu.add_command(label="Zaznacz wszystko  Ctrl+A",
                         command=lambda: (w.tag_add("sel", "1.0", "end"),
                                         w.mark_set("insert", "end")))
        menu.add_separator()

        has_sel = self._has_sel(w)
        if has_sel:
            sel_m = self._make_menu()
            sel_m.add_command(label="Na male litery",
                              command=lambda: self._transform_sel(w, str.lower))
            sel_m.add_command(label="Na WIELKIE litery",
                              command=lambda: self._transform_sel(w, str.upper))
            sel_m.add_command(label="Title Case",
                              command=lambda: self._transform_sel(w, str.title))
            sel_m.add_command(label="Odwroc tekst",
                              command=lambda: self._transform_sel(w, lambda s: s[::-1]))
            sel_m.add_separator()
            sel_m.add_command(label="Statystyki zaznaczenia",
                              command=lambda: self._count_sel(w))
            sel_m.add_command(label="Policz wystapienia",
                              command=lambda: self._count_occurrences(w))
            menu.add_cascade(label="Zaznaczenie", menu=sel_m)

        line_m = self._make_menu()
        line_m.add_command(label="Usun biezaca linie  Ctrl+D",
                           command=lambda: self._delete_line(w))
        line_m.add_command(label="Przesun linie w gore",
                           command=lambda: self._move_line(w, -1))
        line_m.add_command(label="Przesun linie w dol",
                           command=lambda: self._move_line(w, +1))
        line_m.add_separator()
        line_m.add_command(label="Kopiuj biezaca linie",
                           command=lambda: self._copy_line(w))
        line_m.add_command(label="Duplikuj linie",
                           command=lambda: self._duplicate_line(w))
        menu.add_cascade(label="Linia", menu=line_m)

        if is_code:
            code_m = self._make_menu()
            code_m.add_command(label="Komentuj / odkomentuj  Ctrl+/",
                               command=lambda: self._toggle_comment(w))
            code_m.add_command(label="Wciecie (+4 spacje)     Tab",
                               command=lambda: self._indent_sel(w, +1))
            code_m.add_command(label="Wciecie (-4 spacje)  Shift+Tab",
                               command=lambda: self._indent_sel(w, -1))
            code_m.add_separator()
            code_m.add_command(label="Usun trailing spaces",
                               command=lambda: self._strip_trailing(w))
            code_m.add_command(label="Dodaj numery linii (tekst)",
                               command=lambda: self._add_line_numbers(w))
            code_m.add_command(label="Sortuj linie A-Z",
                               command=lambda: self._sort_lines(w, reverse=False))
            code_m.add_command(label="Sortuj linie Z-A",
                               command=lambda: self._sort_lines(w, reverse=True))
            code_m.add_command(label="Usun duplikaty linii",
                               command=lambda: self._remove_dup_lines(w))
            menu.add_cascade(label="Kod", menu=code_m)
            menu.add_command(label="Znajdz / Zastap  Ctrl+H",
                             command=lambda: self._open_find_replace(w))

        menu.add_separator()
        menu.add_command(label="Wyczysc edytor",
                         command=lambda: w.delete("1.0", "end"))
        menu.add_separator()
        self._add_zoom_submenu(menu)

    def _build_treeview_menu(self, menu, w, app):
        """Buduje menu kontekstowe dla ttk.Treeview."""
        sel = w.selection()
        n = len(sel)

        if sel:
            if n == 1:
                menu.add_command(label="Otworz w edytorze",
                                 command=lambda: app._otworz_skrypt())
                menu.add_command(label="Edytuj skrypt",
                                 command=lambda: app._edytuj_skrypt())
                menu.add_command(label="Kopiuj kod",
                                 command=lambda: self._tree_copy_kod(w))
                menu.add_command(label="Kopiuj nazwe",
                                 command=lambda: self._tree_copy_field(w, 0))
                menu.add_command(label="Duplikuj skrypt",
                                 command=lambda: self._tree_duplicate(w))
                menu.add_separator()
            lbl_usun = f"Usun  ({n} skrypt" + ("y" if 1<n<5 else "ow" if n>=5 else "") + ")"
            menu.add_command(label=lbl_usun,
                             command=lambda: app._usun_skrypt())
            exp_m = self._make_menu()
            exp_m.add_command(label="Eksportuj jako .py",
                              command=lambda: self._tree_export_sel(w, "py"))
            exp_m.add_command(label="Eksportuj jako .txt",
                              command=lambda: self._tree_export_sel(w, "txt"))
            exp_m.add_command(label="Eksportuj jako .json",
                              command=lambda: self._tree_export_sel(w, "json"))
            menu.add_cascade(label="Eksportuj zaznaczone", menu=exp_m)
            menu.add_separator()

        menu.add_command(label="Nowy skrypt",
                         command=lambda: app._menu_nowy_skrypt())
        menu.add_command(label="Odswiez liste",
                         command=lambda: app._refresh_lista())
        menu.add_command(label="Zaznacz wszystko  Ctrl+A",
                         command=lambda: self._tree_select_all(w))
        menu.add_separator()

        sort_m = self._make_menu()
        for lbl, field, order in [
            ("A-Z  Nazwa rosnaco",    "nazwa",     "ASC"),
            ("Z-A  Nazwa malejaco",   "nazwa",     "DESC"),
            ("Kategoria A-Z",         "kategoria", "ASC"),
            ("Kategoria Z-A",         "kategoria", "DESC"),
            ("Tagi A-Z",              "tagi",      "ASC"),
        ]:
            sort_m.add_command(label=lbl,
                               command=lambda f=field, o=order: app._menu_sortuj(f, o))
        menu.add_cascade(label="Sortuj", menu=sort_m)

        fil_m = self._make_menu()
        kats  = sorted({s.get("kategoria","") for s in app.skrypty if s.get("kategoria")})
        fil_m.add_command(label="Wszystkie kategorie",
                          command=lambda: app._menu_sortuj("nazwa", "ASC"))
        fil_m.add_separator()
        for kat in kats:
            fil_m.add_command(label=f"  {kat}",
                              command=lambda k=kat: self._tree_filter_kat(w, k))
        menu.add_cascade(label="Filtruj wg kategorii", menu=fil_m)
        menu.add_separator()
        menu.add_command(label="Eksportuj cala baze...",
                         command=lambda: app._lista_eksportuj())
        menu.add_command(label="Importuj baze...",
                         command=lambda: app._lista_importuj())
        menu.add_separator()
        total    = len(app.skrypty)
        kats_cnt = len({s.get("kategoria","") for s in app.skrypty})
        menu.add_command(label=f"  {total} skryptow  /  {kats_cnt} kategorii",
                         state="disabled")

    def _build_listbox_menu(self, menu, w, app):
        """Buduje menu kontekstowe dla tk.Listbox."""
        sel = w.curselection()
        if sel:
            items = [w.get(i) for i in sel]
            val   = items[0]
            menu.add_command(
                label=f"Kopiuj: {val[:30]}{'...' if len(val)>30 else ''}",
                command=lambda v=val: (app.clipboard_clear(),
                                      app.clipboard_append(v)))
            if len(items) > 1:
                menu.add_command(
                    label=f"Kopiuj wszystkie ({len(items)})",
                    command=lambda vs=items: (app.clipboard_clear(),
                                              app.clipboard_append("\n".join(vs))))
            menu.add_separator()
            menu.add_command(label="Usun zaznaczone",
                             command=lambda: self._listbox_delete_sel(w))
            menu.add_separator()
        menu.add_command(label="Odswiez",
                         command=lambda: self._try_refresh(w))
        menu.add_command(label="Eksportuj jako TXT",
                         command=lambda: self._listbox_export(w))
        menu.add_separator()
        menu.add_command(label=f"  {w.size()} elementow", state="disabled")

    def _build_entry_menu(self, menu, w, app):
        """Buduje menu kontekstowe dla Entry/Combobox."""
        val = ""
        try:
            val = w.get()
        except Exception as e:
            logging.warning(f"Błąd odczytu Entry: {e}")
        menu.add_command(label="Wytnij",
                         command=lambda: w.event_generate("<<Cut>>"))
        menu.add_command(label="Kopiuj",
                         command=lambda: w.event_generate("<<Copy>>"))
        menu.add_command(label="Wklej",
                         command=lambda: w.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Zaznacz wszystko",
                         command=lambda: (w.select_range(0, "end"),
                                         w.icursor("end")))
        menu.add_command(label="Wyczysc pole",
                         command=lambda: w.delete(0, "end"))
        menu.add_separator()
        if val.strip():
            menu.add_command(label="Na male litery",
                             command=lambda v=val: (w.delete(0, "end"),
                                                    w.insert(0, v.lower())))
            menu.add_command(label="Na WIELKIE litery",
                             command=lambda v=val: (w.delete(0, "end"),
                                                    w.insert(0, v.upper())))
            menu.add_separator()
        wid  = str(w)
        hist = self._entry_history.get(wid, [])
        if hist:
            hist_m = self._make_menu()
            for h in reversed(hist[-15:]):
                hist_m.add_command(
                    label=f"  {h[:40]}{'...' if len(h)>40 else ''}",
                    command=lambda v=h: (w.delete(0, "end"), w.insert(0, v)))
            hist_m.add_separator()
            hist_m.add_command(label="Wyczysc historie",
                               command=lambda: self._entry_history.update({wid: []}))
            menu.add_cascade(label="Historia wpisow", menu=hist_m)
        if isinstance(w, ttk.Combobox):
            vals = list(w.cget("values") or [])
            if vals:
                val_m = self._make_menu()
                for v in vals:
                    val_m.add_command(label=f"  {v}",
                                      command=lambda vv=v: w.set(vv))
                menu.add_cascade(label="Dostepne wartosci", menu=val_m)

    def _build_canvas_menu(self, menu, w, app):
        """Buduje menu kontekstowe dla tk.Canvas."""
        menu.add_command(label="Powieksz", command=lambda: self._zoom_step(+1))
        menu.add_command(label="Pomniejsz", command=lambda: self._zoom_step(-1))
        menu.add_command(label="Reset widoku",
                         command=lambda: (w.xview_moveto(0), w.yview_moveto(0)))
        menu.add_separator()
        menu.add_command(label="Eksportuj jako PS",
                         command=lambda: self._canvas_export_ps(w))
        menu.add_separator()
        menu.add_command(label="Odswiez", command=lambda: self._try_refresh(w))

    def _build_general_menu(self, menu, app):
        """Buduje ogólne menu kontekstowe."""
        menu.add_command(label="Nowy skrypt      Ctrl+N",
                         command=app._menu_nowy_skrypt)
        menu.add_command(label="Lista skryptow   Ctrl+L",
                         command=app._menu_pokaz_liste)
        menu.add_command(label="Szukaj           Ctrl+F",
                         command=app._menu_pokaz_szukaj)
        menu.add_command(label="Zapisz           Ctrl+S",
                         command=app._zapisz)
        menu.add_separator()
        menu.add_command(label="Odswiez          F5",
                         command=app._menu_odswiez)
        menu.add_separator()
        self._add_zoom_submenu(menu)
        menu.add_separator()
        gest_m = self._make_menu()
        for lbl in [
            "prawo      -> nastepna zakladka",
            "lewo       -> poprzednia zakladka",
            "dol        -> odswiez",
            "gora       -> nowy skrypt",
            "prawo-gora -> eksport bazy",
            "lewo-gora  -> import bazy",
            "prawo-dol  -> szukaj",
            "lewo-dol   -> lista skryptow",
        ]:
            gest_m.add_command(label=lbl, state="disabled")
        menu.add_cascade(label="Gesty myszy (sciagatka)", menu=gest_m)
        menu.add_separator()
        menu.add_command(label="O programie",      command=app._menu_o_programie)

    # ── Operacje na tekście ────────────────────────────────────────────────────
    def _transform_sel(self, widget, func):
        try:
            sel = widget.get("sel.first", "sel.last")
            widget.delete("sel.first", "sel.last")
            widget.insert("insert", func(sel))
        except Exception:
            pass

    def _count_sel(self, widget):
        try:
            sel   = widget.get("sel.first", "sel.last")
            lines = sel.count("\n") + 1
            words = len(sel.split())
            messagebox.showinfo(_tr("Statystyki zaznaczenia"),
                f"Znaki:  {len(sel):,}\n"
                f"Slowa:  {words:,}\n"
                f"Linie:  {lines:,}\n"
                f"Linii z kodem: {sum(1 for l in sel.splitlines() if l.strip()):,}")
        except Exception:
            pass

    def _count_occurrences(self, widget):
        try:
            sel = widget.get("sel.first", "sel.last").strip()
            if not sel:
                return
            cnt = widget.get("1.0", "end-1c").count(sel)
            messagebox.showinfo(_tr("Wystapienia"),
                f"'{sel[:40]}'\nWystepuje: {cnt} razy")
        except Exception:
            pass

    def _delete_line(self, widget):
        try:
            ln = widget.index("insert").split(".")[0]
            widget.delete(f"{ln}.0", f"{ln}.0 lineend+1c")
        except Exception:
            pass

    def _copy_line(self, widget):
        try:
            ln  = widget.index("insert").split(".")[0]
            txt = widget.get(f"{ln}.0", f"{ln}.0 lineend")
            self.app.clipboard_clear()
            self.app.clipboard_append(txt)
        except Exception:
            pass

    def _duplicate_line(self, widget):
        try:
            ln  = widget.index("insert").split(".")[0]
            txt = widget.get(f"{ln}.0", f"{ln}.0 lineend")
            widget.insert(f"{ln}.0 lineend", "\n" + txt)
        except Exception:
            pass

    def _move_line(self, widget, direction):
        try:
            ln   = int(widget.index("insert").split(".")[0])
            col  = widget.index("insert").split(".")[1]
            txt  = widget.get(f"{ln}.0", f"{ln}.0 lineend")
            widget.delete(f"{ln}.0", f"{ln}.0 lineend+1c")
            new_ln = ln + direction
            if direction < 0:
                widget.insert(f"{new_ln}.0", txt + "\n")
            else:
                widget.insert(f"{new_ln}.0 lineend", "\n" + txt)
            widget.mark_set("insert", f"{new_ln}.{col}")
        except Exception:
            pass

    def _toggle_comment(self, widget):
        try:
            try:
                start = widget.index("sel.first linestart")
                end   = widget.index("sel.last lineend")
            except Exception:
                ln    = widget.index("insert").split(".")[0]
                start = f"{ln}.0"
                end   = f"{ln}.0 lineend"
            lines = widget.get(start, end).split("\n")
            all_commented = all(l.lstrip().startswith("#") for l in lines if l.strip())
            new_lines = []
            for line in lines:
                if all_commented:
                    new_lines.append(re.sub(r"^(\s*)# ?", r"\1", line))
                else:
                    stripped = line.lstrip()
                    indent   = line[: len(line) - len(stripped)]
                    new_lines.append(indent + "# " + stripped)
            widget.delete(start, end)
            widget.insert(start, "\n".join(new_lines))
        except Exception:
            pass

    def _indent_sel(self, widget, direction):
        INDENT = "    "
        try:
            try:
                start = widget.index("sel.first linestart")
                end   = widget.index("sel.last lineend")
            except Exception:
                ln    = widget.index("insert").split(".")[0]
                start = f"{ln}.0"
                end   = f"{ln}.0 lineend"
            lines = widget.get(start, end).split("\n")
            new_lines = []
            for line in lines:
                if direction > 0:
                    new_lines.append(INDENT + line)
                else:
                    if line.startswith(INDENT):
                        new_lines.append(line[4:])
                    else:
                        new_lines.append(line.lstrip(" ")[:max(0, len(line)-4)] or line)
            widget.delete(start, end)
            widget.insert(start, "\n".join(new_lines))
        except Exception:
            pass

    def _strip_trailing(self, widget):
        try:
            lines = widget.get("1.0", "end-1c").split("\n")
            widget.delete("1.0", "end")
            widget.insert("1.0", "\n".join(l.rstrip() for l in lines))
        except Exception:
            pass

    def _add_line_numbers(self, widget):
        try:
            lines = widget.get("1.0", "end-1c").split("\n")
            w     = len(str(len(lines)))
            widget.delete("1.0", "end")
            widget.insert("1.0", "\n".join(f"{str(i+1).rjust(w)}  {l}"
                                           for i, l in enumerate(lines)))
        except Exception:
            pass

    def _sort_lines(self, widget, reverse=False):
        try:
            lines = widget.get("1.0", "end-1c").split("\n")
            lines.sort(key=str.lower, reverse=reverse)
            widget.delete("1.0", "end")
            widget.insert("1.0", "\n".join(lines))
        except Exception:
            pass

    def _remove_dup_lines(self, widget):
        try:
            lines = widget.get("1.0", "end-1c").split("\n")
            seen  = []
            for l in lines:
                if l not in seen:
                    seen.append(l)
            widget.delete("1.0", "end")
            widget.insert("1.0", "\n".join(seen))
        except Exception:
            pass

    def _open_find_replace(self, widget):
        win = _popup(self.app)
        win.title(_tr("Znajdz / Zastap"))
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg="#1e2130")
        try:
            win.wm_geometry(f"+{widget.winfo_rootx()+20}+{widget.winfo_rooty()+40}")
        except Exception:
            pass

        pad = dict(padx=10, pady=4)
        self.app._trw(tk.Label(win, text=_tr("Znajdz:"), font=("Consolas", 9),
                 bg="#1e2130", fg="#c8d0f0"), "Znajdz:").grid(row=0, column=0, sticky="w", **pad)
        e_find = tk.Entry(win, font=("Consolas", 9), bg="#252840", fg="#c8d0f0",
                          insertbackground="#c8d0f0", width=32, relief="flat")
        e_find.grid(row=0, column=1, columnspan=2, **pad)
        e_find.focus_set()

        self.app._trw(tk.Label(win, text=_tr("Zastap:"), font=("Consolas", 9),
                 bg="#1e2130", fg="#c8d0f0"), "Zastap:").grid(row=1, column=0, sticky="w", **pad)
        e_repl = tk.Entry(win, font=("Consolas", 9), bg="#252840", fg="#c8d0f0",
                          insertbackground="#c8d0f0", width=32, relief="flat")
        e_repl.grid(row=1, column=1, columnspan=2, **pad)

        var_case  = tk.BooleanVar(value=False)
        var_regex = tk.BooleanVar(value=False)
        self.app._trw(tk.Checkbutton(win, text=_tr("Aa wielk."), variable=var_case,
                       bg="#1e2130", fg="#c8d0f0", selectcolor="#252840",
                       font=("Consolas", 8), activebackground="#1e2130",
                       activeforeground="#c8d0f0"), "Aa wielk.").grid(row=2, column=0, **pad)
        self.app._trw(tk.Checkbutton(win, text=_tr("Regex"), variable=var_regex,
                       bg="#1e2130", fg="#c8d0f0", selectcolor="#252840",
                       font=("Consolas", 8), activebackground="#1e2130",
                       activeforeground="#c8d0f0"), "Regex").grid(row=2, column=1, **pad)

        lbl_res = tk.Label(win, text="", font=("Consolas", 8),
                           bg="#1e2130", fg="#6dde84")
        lbl_res.grid(row=3, column=0, columnspan=3, **pad)

        def _highlight_all():
            widget.tag_remove("fr_match", "1.0", "end")
            term = e_find.get()
            if not term:
                return 0
            flags   = 0 if var_case.get() else re.IGNORECASE
            content = widget.get("1.0", "end-1c")
            try:
                pat  = term if var_regex.get() else re.escape(term)
                hits = list(re.finditer(pat, content, flags))
            except re.error:
                hits = []
            lines   = content.split("\n")
            offsets = [0]
            for l in lines:
                offsets.append(offsets[-1] + len(l) + 1)
            widget.tag_configure("fr_match", background="#3a5030", foreground="#c3e88d")
            for m in hits:
                def _pos(off):
                    for ri, o in enumerate(offsets):
                        if o > off:
                            return ri, off - offsets[ri-1]
                    return len(lines), 0
                sr, sc = _pos(m.start())
                er, ec = _pos(m.end())
                widget.tag_add("fr_match", f"{sr}.{sc}", f"{er}.{ec}")
            return len(hits)

        def _find_next():
            cnt = _highlight_all()
            lbl_res.config(text=f"Znaleziono: {cnt}" if cnt else _tr("Nie znaleziono"))
            ranges = widget.tag_ranges("fr_match")
            if not ranges:
                return
            pairs = list(zip(ranges[0::2], ranges[1::2]))
            cur   = widget.index("insert")
            for s, e in pairs:
                if widget.compare(str(s), ">", cur):
                    widget.mark_set("insert", str(s))
                    widget.see(str(s))
                    return
            widget.mark_set("insert", str(pairs[0][0]))
            widget.see(str(pairs[0][0]))

        def _replace_one():
            term = e_find.get()
            repl = e_repl.get()
            if not term:
                return
            try:
                sel_s = widget.index("sel.first")
                sel_e = widget.index("sel.last")
                txt   = widget.get(sel_s, sel_e)
                flags = 0 if var_case.get() else re.IGNORECASE
                pat   = term if var_regex.get() else re.escape(term)
                new   = re.sub(pat, repl, txt, count=1, flags=flags)
                widget.delete(sel_s, sel_e)
                widget.insert(sel_s, new)
            except Exception:
                pass
            _find_next()

        def _replace_all():
            term = e_find.get()
            repl = e_repl.get()
            if not term:
                return
            content = widget.get("1.0", "end-1c")
            flags   = 0 if var_case.get() else re.IGNORECASE
            try:
                pat = term if var_regex.get() else re.escape(term)
                new_content, n = re.subn(pat, repl, content, flags=flags)
            except re.error as exc:
                messagebox.showerror(_tr("Regex blad"), str(exc))
                return
            widget.delete("1.0", "end")
            widget.insert("1.0", new_content)
            lbl_res.config(text=f"Zastapiono: {n}")

        btn_cfg = dict(font=("Consolas", 9), bg="#2e3350", fg="#c8d0f0",
                       relief="flat", padx=8, pady=3,
                       activebackground="#4a90d9", activeforeground="#fff",
                       cursor="hand2")
        self.app._trw(tk.Button(win, text=_tr("Szukaj dalej"),    **btn_cfg,
                  command=_find_next), "Szukaj dalej").grid(row=4, column=0, **pad)
        self.app._trw(tk.Button(win, text=_tr("Zastap"),          **btn_cfg,
                  command=_replace_one), "Zastap").grid(row=4, column=1, **pad)
        self.app._trw(tk.Button(win, text=_tr("Zastap wszystko"), **btn_cfg,
                  command=_replace_all), "Zastap wszystko").grid(row=4, column=2, **pad)
        self.app._trw(tk.Button(win, text=_tr("Zamknij"),         **btn_cfg,
                  command=win.destroy), "Zamknij").grid(row=5, column=0, columnspan=3, pady=6)

        e_find.bind("<Return>",    lambda e: _find_next())
        e_find.bind("<KeyRelease>",lambda e: _highlight_all())

    # ── Operacje na Treeview ───────────────────────────────────────────────────
    def _tree_copy_kod(self, tree):
        sel = tree.selection()
        if not sel:
            return
        try:
            kod = self.app.skrypty[int(sel[0])].get("kod", "")
            self.app.clipboard_clear()
            self.app.clipboard_append(kod)
        except Exception:
            pass

    def _tree_copy_field(self, tree, col):
        sel = tree.selection()
        if not sel:
            return
        try:
            vals = tree.item(sel[0], "values")
            self.app.clipboard_clear()
            self.app.clipboard_append(vals[col] if col < len(vals) else "")
        except Exception:
            pass

    def _tree_duplicate(self, tree):
        sel = tree.selection()
        if not sel:
            return
        import copy
        try:
            idx = int(sel[0])
            s   = copy.deepcopy(self.app.skrypty[idx])
            s["nazwa"] = s["nazwa"] + " (kopia)"
            s.pop("id", None)
            s["checksum"] = None
            s["uruchomien"] = 0
            self.app.skrypty.append(sc_normalize(s))
            self.app._rebuild_index()
            self.app._refresh_lista()
            self.app._update_count()
            self.app._after_db_change()
        except Exception as e:
            messagebox.showerror(_tr("Blad"), str(e))

    def _tree_export_sel(self, tree, fmt):
        sel   = tree.selection()
        items = []
        for iid in sel:
            try:
                items.append(self.app.skrypty[int(iid)])
            except Exception:
                pass
        if not items:
            return
        if fmt == "json":
            import json
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                title=_tr("Eksportuj zaznaczone jako JSON"))
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                messagebox.showinfo(_tr("Eksport"), f"Wyeksportowano {len(items)} skryptow.")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=f".{fmt}",
                filetypes=[(fmt.upper(), f"*.{fmt}")],
                title=f"Eksportuj zaznaczone jako .{fmt}")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    for s in items:
                        f.write(f"# -- {s.get('nazwa','')} [{s.get('kategoria','')}] --\n")
                        f.write(s.get("kod", "") + "\n\n")
                messagebox.showinfo(_tr("Eksport"), f"Wyeksportowano {len(items)} skryptow.")

    def _tree_filter_kat(self, tree, kat):
        try:
            self.app._refresh_lista(filter_kat=kat)
        except Exception:
            try:
                self.app._refresh_lista()
            except Exception:
                pass

    def _tree_select_all(self, tree):
        tree.selection_set(tree.get_children())

    # ── Operacje na Listbox ────────────────────────────────────────────────────
    def _listbox_delete_sel(self, widget):
        for i in reversed(widget.curselection()):
            widget.delete(i)

    def _listbox_export(self, widget):
        items = list(widget.get(0, "end"))
        if not items:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Plik tekstowy", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(items))
            messagebox.showinfo(_tr("Eksport"), f"Zapisano {len(items)} elementow.")

    # ── Canvas ─────────────────────────────────────────────────────────────────
    def _canvas_export_ps(self, canvas):
        path = filedialog.asksaveasfilename(
            defaultextension=".ps",
            filetypes=[("PostScript", "*.ps")])
        if path:
            try:
                canvas.postscript(file=path)
                messagebox.showinfo(_tr("Eksport"), f"Zapisano: {path}")
            except Exception as e:
                messagebox.showerror(_tr("Blad eksportu"), str(e))

    # ── Rozne ──────────────────────────────────────────────────────────────────
    def _try_refresh(self, widget):
        for method in ["_venv_refresh_list", "_refresh_lista",
                       "_menu_odswiez", "_stat_refresh"]:
            fn = getattr(self.app, method, None)
            if fn:
                try:
                    fn()
                    return
                except Exception:
                    pass

    def _on_ctrl_a(self, event):
        w = event.widget
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end")
            w.mark_set("insert", "end")
            return "break"
        if isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox)):
            try:
                w.select_range(0, "end")
                w.icursor("end")
            except Exception:
                pass
            return "break"
        if isinstance(w, ttk.Treeview):
            self._tree_select_all(w)
            return "break"

    def track_entry(self, widget):
        val = ""
        try:
            val = widget.get().strip()
        except Exception:
            return
        if not val:
            return
        wid  = str(widget)
        hist = self._entry_history.setdefault(wid, [])
        if val not in hist:
            hist.append(val)
            if len(hist) > 50:
                hist.pop(0)

    def setup_tree_enhanced(self, tree):
        tree.bind("<Triple-1>",  lambda e: self._tree_select_all(tree))
        tree.bind("<Control-a>", lambda e: self._tree_select_all(tree))
        tree.bind("<Enter>",     lambda e: tree.focus_set())

    def register_app_tooltips(self):
        app = self.app
        tip = self.attach_tooltip
        for i, b in enumerate(getattr(app, "_main_btns", [])):
            labels = [
                "Skrypty - dodawaj, edytuj, przegladaj",
                "Wyszukiwarka - live search",
                "Moduly systemowe - diagnostyka",
                "Baza danych - SQLite",
                "Srodowiska wirtualne - venv + pip",
                "Narzedzia",
            ]
            if i < len(labels):
                tip(b, labels[i])
        for attr, text in [
            ("entry_nazwa",  "Nazwa skryptu - wymagane\nRamka: zielona=nowy  pomaranczowa=aktualizacja  czerwona=puste"),
            ("entry_tagi",   "Tagi oddzielone przecinkami\nnp: python, petla, plik"),
            ("entry_search", "Live search - nazwa / kategoria / tagi / kod\nEnter = potwierdz"),
            ("text_opis",    "Krotki opis skryptu"),
            ("text_kod",     "Edytor kodu\nCtrl+Scroll=zoom  Srodkowy=pan\nPrawy klik=menu (komentuj, wcinaj, znajdz...)"),
        ]:
            w = getattr(app, attr, None)
            if w:
                tip(w, text)
        for attr, text in [
            ("tree",      "Lista skryptow\nPrawy klik=menu  Ctrl+A=zaznacz wszystko\nSrodkowy=pan  Ctrl+scroll=zoom"),
            ("adv_tree",  "Wyniki wyszukiwania - dwuklik=edytuj"),
            ("hist_tree", "Historia wyszukiwan - dwuklik=przywroc"),
        ]:
            w = getattr(app, attr, None)
            if w:
                tip(w, text)


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER — przygotowanie i uruchamianie skryptów (bez zależności od GUI)
# ══════════════════════════════════════════════════════════════════════════════
RUNNER_EXT = {
    "Python":     ".py",
    "Bash":       ".sh",
    "PowerShell": ".ps1",
    "JavaScript": ".js",
    "Batch":      ".bat",
    "VBScript":   ".vbs",
    "Java":       ".java",
    "JAR":        ".jar",
    "C":          ".c",
    "C++":        ".cpp",
    "Ruby":       ".rb",
    "Perl":       ".pl",
    "PHP":        ".php",
    "WSF":        ".wsf",
    "HTA":        ".hta",
    "HTML":       ".html",
    "CSS":        ".css",
    "JSON":       ".json",
    "Markdown":   ".md",
    "SQL":        ".sql",
    "Other":      ".txt",
}

# Rozszerzenie pliku → kategoria (import / wczytywanie z dysku)
EXT_KAT = {
    ".py": "Python", ".sh": "Bash", ".ps1": "PowerShell",
    ".js": "JavaScript", ".bat": "Batch", ".cmd": "Batch",
    ".vbs": "VBScript", ".java": "Java", ".jar": "JAR", ".sql": "SQL",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".c++": "C++",
    ".hpp": "C++", ".hh": "C++", ".hxx": "C++",
    ".rb": "Ruby", ".pl": "Perl", ".php": "PHP",
    ".wsf": "WSF", ".hta": "HTA",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".json": "JSON",
    ".md": "Markdown", ".markdown": "Markdown",
}

# Rozszerzenia plików binarnych przechowywanych w bazie jako base64
BIN_EXT = (".jar",)

# Grupowanie obsługiwanych skryptów/plików dla okna „Obsługiwane skrypty i pliki"
# (menu Pomoc). Wpis: (rozszerzenia, kategoria, opis runnera/interpretera).
OBSL_GRUPY = [
    ("Skrypty systemowe Windows", [
        (".bat, .cmd", "Batch",      "cmd.exe /c"),
        (".vbs",       "VBScript",   "cscript.exe //nologo"),
        (".ps1",       "PowerShell", "powershell -NoProfile -ExecutionPolicy Bypass"),
        (".wsf",       "WSF",        "cscript.exe //nologo"),
        (".hta",       "HTA",        "mshta.exe"),
    ]),
    ("Skrypty języków programowania", [
        (".py",   "Python",     "python -u"),
        (".sh",   "Bash",       "bash (Git Bash)"),
        (".js",   "JavaScript", "node"),
        (".java", "Java",       "javac → java -cp"),
        (".jar",  "JAR",        "java -jar"),
        (".c, .h",         "C",   "gcc/clang → program.exe"),
        (".cpp, .cc, .cxx, .c++, .hpp, .hh, .hxx", "C++", "g++/clang++ → program.exe"),
        (".rb",   "Ruby",       "ruby"),
        (".pl",   "Perl",       "perl"),
        (".php",  "PHP",        "php"),
    ]),
    ("Pliki danych i znaczników", [
        (".html, .htm",    "HTML",     "cmd /c start"),
        (".css",           "CSS",      "—"),
        (".json",          "JSON",     "—"),
        (".md, .markdown", "Markdown", "—"),
        (".sql",           "SQL",      "SQLite (Baza Danych)"),
        (".txt",           "Other",    "—"),
    ]),
]


def jar_bytes(kod: str) -> bytes:
    """Dekoduje zawartość archiwum JAR (zapisaną jako base64) do bajtów."""
    try:
        return base64.b64decode((kod or "").strip(), validate=False)
    except Exception:
        return b""


def jar_base64(path: str) -> str:
    """Wczytuje plik binarny (np. .jar) i zwraca jego treść jako base64."""
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def runner_java_class(kod: str) -> str:
    """Nazwa głównej klasy źródła Java (public, w przeciwnym razie pierwsza)."""
    src = kod or ""
    m = re.search(r'\bpublic\s+(?:final\s+|abstract\s+)?(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)', src)
    if not m:
        m = re.search(r'\b(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)', src)
    return m.group(1) if m else "Main"


def runner_java_package(kod: str) -> str:
    """Deklaracja pakietu ze źródła Java (lub pusty string)."""
    m = re.search(r'^\s*package\s+([\w.]+)\s*;', kod or "", re.M)
    return m.group(1) if m else ""


def _java_tool(name: str, interpreter: str = "") -> str:
    """Zwraca ścieżkę do narzędzia JDK (``java``/``javac``).

    Kolejność: wskazany interpreter (gdy to samo narzędzie), jego sąsiad w tym
    samym ``bin``, ``JAVA_HOME\\bin``, na końcu PATH. Gdy nic nie znajdzie,
    zwraca samą nazwę (uruchomienie z PATH).
    """
    exe = name + (".exe" if os.name == "nt" else "")
    if interpreter:
        if os.path.basename(interpreter).lower() in (name, exe.lower()):
            return interpreter
        cand = os.path.join(os.path.dirname(os.path.abspath(interpreter)), exe)
        if os.path.exists(cand):
            return cand
    jh = os.environ.get("JAVA_HOME")
    if jh:
        cand = os.path.join(jh, "bin", exe)
        if os.path.exists(cand):
            return cand
    return shutil.which(name) or name


def _java_available(name: str, interpreter: str = "") -> bool:
    """Czy narzędzie JDK (``java``/``javac``) jest osiągalne.

    Sprawdza wskazany interpreter, jego sąsiedztwo w ``bin``, ``JAVA_HOME``
    oraz PATH. Służy do ostrzegania przed uruchomieniem, gdy brakuje JDK.
    """
    tool = _java_tool(name, interpreter)
    if os.path.isabs(tool):
        return os.path.exists(tool)
    return shutil.which(tool) is not None


def _interp_tool(name: str, interpreter: str = "") -> str:
    """Zwraca ścieżkę do interpretera (``ruby``/``perl``/``php``/``cscript``/…).

    Kolejność: wskazany interpreter (gdy to samo narzędzie), jego sąsiad w tym
    samym katalogu, na końcu PATH. Gdy nic nie znajdzie, zwraca samą nazwę
    (uruchomienie z PATH).
    """
    exe = name + (".exe" if os.name == "nt" else "")
    if interpreter:
        base = os.path.basename(interpreter).lower()
        if base in (name.lower(), exe.lower()):
            return interpreter
        cand = os.path.join(os.path.dirname(os.path.abspath(interpreter)), exe)
        if os.path.exists(cand):
            return cand
    return shutil.which(name) or name


def _tool_available(name: str, interpreter: str = "") -> bool:
    """Czy interpreter (``ruby``/``perl``/``php``/``cscript``/``mshta``) jest osiągalny."""
    tool = _interp_tool(name, interpreter)
    if os.path.isabs(tool):
        return os.path.exists(tool)
    return shutil.which(tool) is not None


def _interp_warning(name: str, interpreter: str = "") -> str:
    """Zwraca ostrzeżenie o braku interpretera albo pusty łańcuch."""
    if _tool_available(name, interpreter):
        return ""
    return f" — uwaga: nie znaleziono {name} w PATH"


def runner_jar_main_class(data: bytes) -> str:
    """Odczytuje ``Main-Class`` z ``META-INF/MANIFEST.MF`` archiwum JAR/ZIP."""
    if not data or data[:2] != b"PK":
        return ""
    try:
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            raw = zf.read("META-INF/MANIFEST.MF")
    except Exception:
        return ""
    for line in raw.decode("utf-8", "replace").splitlines():
        if line.lower().startswith("main-class:"):
            return line.split(":", 1)[1].strip()
    return ""


def runner_java_launcher_lines(src_name: str, fq: str, javac: str = "javac",
                               java: str = "java") -> List[str]:
    """Wiersze launchera .bat: kompilacja ``javac`` → uruchomienie ``java``."""
    return [
        "@echo off",
        "chcp 65001 >nul",
        'cd /d "%~dp0"',
        f'"{javac}" -encoding UTF-8 -d "%~dp0." "{src_name}" || exit /b 1',
        f'"{java}" -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 '
        f'-Dstderr.encoding=UTF-8 -cp "%~dp0." {fq} %*',
        "exit /b %errorlevel%",
    ]


def runner_java_launcher(src_path: str, workdir: str, kod: str = "",
                         interpreter: str = "") -> str:
    """Tworzy skrypt .bat kompilujący (javac) i uruchamiający (java) źródło Java."""
    main = runner_java_class(kod)
    pkg = runner_java_package(kod)
    fq = f"{pkg}.{main}" if pkg else main
    lines = runner_java_launcher_lines(
        os.path.basename(src_path), fq,
        _java_tool("javac", interpreter), _java_tool("java", interpreter))
    bat = os.path.join(workdir, "run_java.bat")
    with open(bat, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\r\n".join(lines) + "\r\n")
    return bat


def runner_path(path):
    """Ścieżka zdatna do przekazania interpreterowi na Windows.
    Git-Bash/Node lubią zjadać backslashe i mylić "C:" z opcją — używamy 'C:/...'.
    """
    path = os.path.abspath(path)
    return path.replace("\\", "/") if os.name == "nt" else path


def _c_tool(kategoria: str, interpreter: str = "") -> str:
    """Zwraca kompilator C/C++ (``gcc``/``g++``, fallback ``clang``/``clang++``).

    Kolejność: wskazany interpreter (gdy to samo narzędzie), kompilator z PATH,
    na końcu clang. Gdy nic nie znajdzie, zwraca nazwę primary do uruchomienia
    z PATH (błąd zgłosi runner/analyze).
    """
    primary = "gcc" if kategoria == "C" else "g++"
    fallback = "clang" if kategoria == "C" else "clang++"
    if _tool_available(primary, interpreter):
        return _interp_tool(primary, interpreter)
    if _tool_available(fallback, interpreter):
        return _interp_tool(fallback, interpreter)
    return _interp_tool(primary, interpreter)


def runner_c_launcher_lines(src_name: str, compiler: str,
                            std_flag: str, exe_name: str = "skrypt") -> List[str]:
    """Wiersze launchera .bat: kompilacja (gcc/g++) → uruchomienie programu."""
    return [
        "@echo off",
        "chcp 65001 >nul",
        'cd /d "%~dp0"',
        f'"{compiler}" -O2 {std_flag} -o "%~dp0{exe_name}.exe" '
        f'"{src_name}" || exit /b 1',
        f'"%~dp0{exe_name}.exe" %*',
        "exit /b %errorlevel%",
    ]


def runner_c_sh_lines(src_name: str, compiler: str,
                      std_flag: str, exe_name: str = "skrypt") -> List[str]:
    """Wiersze launchera .sh (POSIX): kompilacja → uruchomienie programu."""
    return [
        "#!/bin/sh",
        'cd "$(dirname "$0")"',
        f'"{compiler}" -O2 {std_flag} -o {exe_name} "{src_name}" || exit 1',
        f'./{exe_name} "$@"',
        "exit $?",
    ]


def runner_c_launcher(src_path: str, workdir: str, kategoria: str,
                      interpreter: str = "") -> str:
    """Tworzy launcher kompilujący i uruchamiający źródło C/C++ (.bat/.sh)."""
    std_flag = "-std=c11" if kategoria == "C" else "-std=c++17"
    compiler = _c_tool(kategoria, interpreter)
    src_name = os.path.basename(src_path)
    if os.name == "nt":
        lines = runner_c_launcher_lines(src_name, compiler, std_flag)
        bat = os.path.join(workdir, "run_c.bat")
        with open(bat, "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("\r\n".join(lines) + "\r\n")
        return bat
    lines = runner_c_sh_lines(src_name, compiler, std_flag)
    sh = os.path.join(workdir, "run_c.sh")
    with open(sh, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return sh


def runner_cmd(kategoria: str, path: str,
               args: Optional[List[str]] = None,
               interpreter: str = "") -> Optional[List[str]]:
    """Buduje listę argumentów polecenia dla danego języka. None = brak runnera."""
    args = list(args or [])
    if kategoria == "Python":
        exe = interpreter or sys.executable
        return [exe, "-u", path] + args
    if kategoria == "PowerShell":
        exe = interpreter or "powershell"
        p = runner_path(path)
        if os.path.basename(exe).lower() in ("pwsh", "pwsh.exe"):
            return [exe, "-NoProfile", "-File", p] + args
        return [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", p] + args
    if kategoria == "Bash":
        # WSH (C:\Windows\System32\bash.exe) to nie bash — szukamy prawdziwego (Git Bash)
        exe = interpreter
        if not exe:
            for cand in (os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Git", "bin", "bash.exe"),
                         os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Git", "bin", "bash.exe"),
                         os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "bin", "bash.exe")):
                if os.path.exists(cand):
                    exe = cand
                    break
        return [exe or "bash", runner_path(path)] + args
    if kategoria == "JavaScript":
        return [interpreter or "node", runner_path(path)] + args
    if kategoria == "Batch":
        shell = interpreter or ("cmd.exe" if os.name == "nt" else "cmd")
        # launcher z runner_save_temp: chcp 65001 + call skryptu + kod wyjścia
        wrapper = os.path.join(os.path.dirname(os.path.abspath(path)), "run_batch.bat")
        target = wrapper if os.path.exists(wrapper) else os.path.abspath(path)
        return [shell, "/c", target] + args
    if kategoria == "VBScript":
        return [_interp_tool("cscript", interpreter), "//nologo",
                os.path.abspath(path)] + args
    if kategoria == "WSF":
        return [_interp_tool("cscript", interpreter), "//nologo",
                os.path.abspath(path)] + args
    if kategoria == "HTA":
        return [_interp_tool("mshta", interpreter), os.path.abspath(path)] + args
    if kategoria == "HTML":
        # Otwarcie dokumentu w domyślnej przeglądarce (Windows: cmd /c start).
        if os.name == "nt":
            return ["cmd", "/c", "start", "", os.path.abspath(path)] + args
        return None
    if kategoria == "Ruby":
        return [_interp_tool("ruby", interpreter), runner_path(path)] + args
    if kategoria == "Perl":
        return [_interp_tool("perl", interpreter), runner_path(path)] + args
    if kategoria == "PHP":
        return [_interp_tool("php", interpreter), runner_path(path)] + args
    if kategoria == "Java":
        # uruchamiamy przez launcher .bat: javac → java (utworzony w runner_save_temp)
        shell = "cmd.exe" if os.name == "nt" else "cmd"
        launcher = os.path.join(os.path.dirname(os.path.abspath(path)), "run_java.bat")
        return [shell, "/c", launcher] + args
    if kategoria == "JAR":
        return [_java_tool("java", interpreter), "-Dfile.encoding=UTF-8",
                "-Dstdout.encoding=UTF-8", "-jar", runner_path(path)] + args
    if kategoria in ("C", "C++"):
        # launcher tworzony w runner_save_temp: kompilacja → program.exe
        d = os.path.dirname(os.path.abspath(path))
        if os.name == "nt":
            launcher = os.path.join(d, "run_c.bat")
            return ["cmd.exe", "/c", launcher] + args
        launcher = os.path.join(d, "run_c.sh")
        return ["sh", launcher] + args
    return None


def runner_shell_cmd(categoria, path, args=None, interpreter=""):
    """Jak runner_cmd(), ale jako pojedynczy string dla nowej konsoli Windows."""
    import subprocess
    cmd = runner_cmd(categoria, path, args, interpreter)
    return subprocess.list2cmdline(cmd) if cmd else None


def runner_parse_error(output, kategoria="Python"):
    """Wyciąga z wyjścia procesu informację o błędzie i linii kodu.
    Zwraca dict {linia, plik, typ, komunikat} albo None."""
    if not output:
        return None
    out = output.replace("\r\n", "\n")
    if kategoria == "Python":
        # File "…/skrypt.py", line 12, in <module>
        matches = re.findall(r'File "([^"]*)", line (\d+), in ([^\n]*)', out)
        typ = re.search(r'^([A-Za-z_][\w.]*(?:Error|Exception|Interrupt|Exit)):? ?(.*)$',
                        out, re.MULTILINE)
        if matches:
            plik, linia, funkcja = matches[-1]
        else:
            m2 = re.search(r'line (\d+)', out)
            plik, linia, funkcja = ("", m2.group(1), "") if m2 else ("", 0, "")
        return {"plik": plik, "linia": int(linia or 0), "funkcja": funkcja,
                "typ": typ.group(1) if typ else "",
                "komunikat": (typ.group(2) if typ else "").strip()[:200]}
    if kategoria == "PowerShell":
        # warianty: 'At C:\\x.ps1:5 char:1' albo 'At line:5 char:1'
        m = re.search(r'At\s+(?:(?P<plik>.+?):(?P<l1>\d+)|line:(?P<l2>\d+))\s+char:', out)
        linia = 0
        plik = ""
        if m:
            plik = (m.group("plik") or "").strip()
            if plik.lower() == "line":
                plik = ""
            linia = int(m.group("l1") or m.group("l2") or 0)
        t = re.search(r'^\s*([A-Za-z][\w.]*(?:Exception|Error)[^:\n]*):?\s*(.*)$', out, re.MULTILINE)
        typ = "PowerShell"
        kom = ""
        if t:
            typ = (t.group(1) or "PowerShell").strip()[:60]
            kom = (t.group(2) or "").strip()[:200]
            if not kom:
                # linia błędu bywa dalej po „+ $x = …” — bierzemy najdłuższy opis
                part = out[t.end():].strip().splitlines()
                kom = (part[0] if part else "").strip()[:200]
        if not kom:
            kom = (out.strip().splitlines() or [""])[-1][:200]
        return {"plik": plik, "linia": linia, "funkcja": "",
                "typ": typ, "komunikat": kom}
    if kategoria == "JavaScript":
        m = re.search(r'(?:file://)?[^\s:]+\.(?:js|mjs):(\d+):(\d+)', out)
        t = re.search(r'^(\w*Error):? ?(.*)$', out, re.MULTILINE)
        return {"plik": "", "linia": int(m.group(1)) if m else 0, "funkcja": "",
                "typ": t.group(1) if t else "",
                "komunikat": (t.group(2) if t else "").strip()[:200]}
    if kategoria == "Bash":
        m = re.search(r'line (\d+):', out)
        return {"plik": "", "linia": int(m.group(1)) if m else 0, "funkcja": "",
                "typ": "Bash", "komunikat": (out.strip().splitlines() or [""])[-1][:200]}
    if kategoria == "Java":
        # javac: Plik.java:12: error: wiadomość
        m = re.search(r'[^\s:]+\.java:(\d+):\s*(?:error|warning):\s*(.*)', out)
        if m:
            return {"plik": "", "linia": int(m.group(1)), "funkcja": "",
                    "typ": "Java", "komunikat": m.group(2).strip()[:200]}
        m2 = re.search(r'Exception in thread "[^"]*"\s+([\w.$]+):?\s*(.*)', out)
        if m2:
            return {"plik": "", "linia": 0, "funkcja": "",
                    "typ": m2.group(1).split(".")[-1], "komunikat": m2.group(2).strip()[:200]}
        return None
    if kategoria == "VBScript" or kategoria == "WSF":
        # C:\x\skrypt.vbs(12, 3) Microsoft VBScript runtime error: …
        m = re.search(r'\((\d+),\s*(\d+)\)\s*([^\n]*)', out)
        if not m:
            return None
        msg = m.group(3).strip()
        t = re.search(r'(Microsoft VBScript \w+ error)', msg)
        return {"plik": "", "linia": int(m.group(1)), "funkcja": "",
                "typ": t.group(1) if t else kategoria,
                "komunikat": msg[:200]}
    if kategoria == "Ruby":
        # skrypt.rb:12: syntax error / skrypt.rb:12:in 'x': msg (RuntimeError)
        m = re.search(r'([^\s:]+\.rb):(\d+):\s*([^\n]*)', out)
        if not m:
            return None
        msg = m.group(3).strip()
        t = re.search(r'\(([\w:]+)\)\s*$', msg)
        return {"plik": m.group(1), "linia": int(m.group(2)), "funkcja": "",
                "typ": t.group(1) if t else "Ruby", "komunikat": msg[:200]}
    if kategoria == "Perl":
        # syntax error at skrypt.pl line 12, near "…"
        m = re.search(r'([^\s:]+\.pl)\s+line\s+(\d+)[.,]?\s*(.*)', out)
        if not m:
            return None
        return {"plik": m.group(1), "linia": int(m.group(2)), "funkcja": "",
                "typ": "Perl", "komunikat": m.group(3).strip()[:200]}
    if kategoria == "PHP":
        # PHP Parse error: … in C:\x\skrypt.php on line 12
        m = re.search(r'PHP\s+([\w ]*error):\s*(.*?)\s+in\s+[^\s]+\s+on line\s+(\d+)',
                      out, re.IGNORECASE)
        if m:
            return {"plik": "", "linia": int(m.group(3)), "funkcja": "",
                    "typ": m.group(1).strip().title(), "komunikat": m.group(2).strip()[:200]}
        t = re.search(r'^\s*(Fatal error|Parse error|Warning)\s*:\s*(.*)$',
                      out, re.MULTILINE | re.IGNORECASE)
        if t:
            return {"plik": "", "linia": 0, "funkcja": "",
                    "typ": t.group(1).strip().title(), "komunikat": t.group(2).strip()[:200]}
        return None
    if kategoria in ("C", "C++"):
        # gcc/clang: skrypt.c:12:5: error: wiadomość  /  :12: error: wiadomość
        m = re.search(r'[^\s:]+\.(?:c|h|cpp|cc|cxx|c\+\+|hpp|hh|hxx):(\d+)'
                      r'(?::\d+)?:\s*(?:fatal\s+)?error:\s*(.*)', out)
        if m:
            return {"plik": "", "linia": int(m.group(1)), "funkcja": "",
                    "typ": kategoria, "komunikat": m.group(2).strip()[:200]}
        return None
    if kategoria == "Batch":
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        kom = ""
        for ln in reversed(lines):
            if re.search(r'(?i)(not recognized|nie jest rozpoznawane|nie można znaleźć|'
                         r'cannot find|the system cannot|syntax error|błąd składni|'
                         r'nieoczekiwany|unexpected)', ln):
                kom = ln
                break
        if not kom and lines:
            kom = lines[-1]
        if not kom:
            return None
        return {"plik": "", "linia": 0, "funkcja": "",
                "typ": "Batch", "komunikat": kom[:200]}
    return None


def runner_analyze(kod, kategoria, path, interpreter=""):
    """Statyczna kontrola przed uruchomieniem: składnia + ostrzeżenia.
    Zwraca (ok, komunikat). ``interpreter`` pozwala wykryć brak JDK dla
    kategorii Java/JAR jeszcze przed uruchomieniem."""
    if kategoria == "Python":
        import ast
        try:
            tree = ast.parse(kod or "", filename=path)
        except SyntaxError as e:
            return False, f"Błąd składni Python, linia {e.lineno}: {e.msg}"
        warnings = []
        risky = {"subprocess", "shutil", "os", "socket", "ctypes", "winreg"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                name = (node.module if isinstance(node, ast.ImportFrom) else node.names[0].name) or ""
                if name.split(".")[0] in risky:
                    warnings.append(name)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("eval", "exec", "__import__"):
                warnings.append(node.func.id)
        return True, ("OK" if not warnings else "OK — uwaga: " + ", ".join(sorted(set(warnings))))
    if kategoria == "JavaScript":
        return True, "OK (Node.js)" if not re.search(r"while\s*\(\s*true\s*\)", kod or "") else "OK — uwaga: pętla while(true)"
    if kategoria == "SQL":
        if not re.search(r"\b(select|insert|update|delete|create|drop|alter)\b", (kod or "").lower()):
            return False, "Nie rozpoznano polecenia SQL."
        return True, "OK (SQL)"
    if kategoria == "Java":
        if not re.search(r'\b(?:class|interface|enum)\s+\w+', kod or ""):
            return False, "Nie znaleziono definicji klasy w kodzie Java."
        main = runner_java_class(kod)
        pkg = runner_java_package(kod)
        fq = f"{pkg}.{main}" if pkg else main
        brak = [n for n in ("javac", "java") if not _java_available(n, interpreter)]
        ostrz = (" — uwaga: nie znaleziono " + ", ".join(brak) +
                 " (wymagany JDK w PATH)") if brak else ""
        if not re.search(r'\bstatic\s+void\s+main\s*\(', kod or ""):
            return True, f"OK (Java) — klasa {fq}, brak metody main(){ostrz}"
        return True, f"OK (Java) — klasa główna: {fq}{ostrz}"
    if kategoria == "JAR":
        data = jar_bytes(kod)
        if not data:
            return False, "Brak danych archiwum JAR (base64)."
        if data[:2] != b"PK":
            return False, "Zawartość nie jest archiwum JAR/ZIP."
        ostrz = "" if _java_available("java", interpreter) else \
            " — uwaga: nie znaleziono java w PATH"
        main = runner_jar_main_class(data)
        if not main:
            return True, ("OK (JAR) — brak Main-Class w MANIFEST; "
                          "uruchomienie java -jar może się nie powieść" + ostrz)
        return True, f"OK (JAR) — klasa główna: {main}{ostrz}"
    if kategoria in ("C", "C++"):
        if not re.search(r'\bint\s+main\s*\(', kod or ""):
            return True, f"OK ({kategoria}) — brak funkcji main()"
        comp = _c_tool(kategoria, interpreter)
        tool_name = "gcc" if kategoria == "C" else "g++"
        ostrz = "" if _tool_available(tool_name, interpreter) or \
            _tool_available("clang" if kategoria == "C" else "clang++", interpreter) \
            else f" — uwaga: nie znaleziono kompilatora ({tool_name}/clang) w PATH"
        return True, f"OK ({kategoria}) — kompilator: {comp}{ostrz}"
    if kategoria == "Batch":
        risky = re.search(r'(?i)\b(format|diskpart|shutdown|del\s+/[fq]|rd\s+/s|rmdir\s+/s|reg\s+delete)\b',
                          kod or "")
        return True, ("OK — uwaga: potencjalnie niebezpieczna komenda" if risky else "OK (Batch)")
    if kategoria == "VBScript":
        return True, "OK (VBScript)" + _interp_warning("cscript", interpreter)
    if kategoria == "WSF":
        if not re.search(r'<\s*job\b', kod or "", re.IGNORECASE):
            return False, "Nie znaleziono elementu <job> w pliku WSF."
        return True, "OK (WSF — Windows Script File)" + _interp_warning("cscript", interpreter)
    if kategoria == "HTA":
        ostrz = _interp_warning("mshta", interpreter)
        if not re.search(r'<\s*html\b|<\s*hta:application\b', kod or "", re.IGNORECASE):
            return True, "OK (HTA) — brak <html>/<HTA:APPLICATION> (może nie działać)" + ostrz
        return True, "OK (HTA)" + ostrz
    if kategoria == "HTML":
        if not re.search(r'<[a-zA-Z!/]', kod or ""):
            return True, "OK (HTML) — brak znaczników"
        return True, "OK (HTML)"
    if kategoria == "CSS":
        return True, "OK (CSS)"
    if kategoria == "JSON":
        try:
            json.loads(kod or "")
        except json.JSONDecodeError as e:
            return False, f"Błąd składni JSON, linia {e.lineno}: {e.msg}"
        return True, "OK (JSON)"
    if kategoria == "Markdown":
        return True, "OK (Markdown)"
    if kategoria == "Ruby":
        return True, "OK (Ruby)" + _interp_warning("ruby", interpreter)
    if kategoria == "Perl":
        return True, "OK (Perl)" + _interp_warning("perl", interpreter)
    if kategoria == "PHP":
        ostrz = _interp_warning("php", interpreter)
        if not re.search(r'<\?php|<\?=', kod or ""):
            return True, "OK (PHP) — brak <?php na początku pliku" + ostrz
        return True, "OK (PHP)" + ostrz
    return True, "OK"


# ── Linter: analiza statyczna kodu Python przed uruchomieniem ────────────────
LINT_ERROR = "error"      # problem blokujący (błąd składni)
LINT_WARNING = "warning"  # ostrzeżenie (np. nieużywany import)


def _lint_ruff_cmd() -> Optional[List[str]]:
    """Zwraca polecenie wywołania ruff lub None, gdy ruff jest niedostępny."""
    exe = shutil.which("ruff")
    if exe:
        return [exe]
    try:
        import importlib.util
        if importlib.util.find_spec("ruff") is not None:
            return [sys.executable, "-m", "ruff"]
    except (ImportError, ValueError):
        pass
    return None


def _lint_with_ruff(code: str, path: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """Analiza kodem ruff. Zwraca None, gdy ruff niedostępny lub zawiedzie."""
    if not code.strip():
        return []
    base = _lint_ruff_cmd()
    if not base:
        return None
    cmd = base + ["check", "--output-format=json", "--no-cache",
                  "--stdin-filename", os.path.basename(path) if path else "skrypt.py", "-"]
    try:
        proc = subprocess.run(cmd, input=code, capture_output=True, text=True,
                              encoding="utf-8", timeout=20,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode not in (0, 1):
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    issues = []
    seen = set()
    for item in data:
        loc = item.get("location") or {}
        code_id = str(item.get("code") or "")
        line = int(loc.get("row") or 1)
        if (line, code_id) in seen:
            continue
        seen.add((line, code_id))
        issues.append({
            "line": line,
            "col": int(loc.get("column") or 1),
            "code": code_id or "?",
            "message": str(item.get("message") or "").strip(),
            "severity": (LINT_ERROR if code_id.startswith("E9")
                         or code_id in ("invalid-syntax", "syntax-error")
                         else LINT_WARNING),
        })
    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


def _lint_with_pyflakes(code: str, path: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """Analiza modułem pyflakes. Zwraca None, gdy pyflakes niedostępny lub zawiedzie."""
    if not code.strip():
        return []
    try:
        import importlib.util
        if importlib.util.find_spec("pyflakes") is None:
            return None
    except (ImportError, ValueError):
        return None
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".py", prefix="lint_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(code)
        proc = subprocess.run([sys.executable, "-m", "pyflakes", tmp],
                              capture_output=True, text=True, encoding="utf-8", timeout=20,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    if proc.returncode not in (0, 1):
        return None
    issues = []
    for line in (proc.stdout or "").splitlines():
        m = re.match(r"^.+?:(\d+):(\d+):\s*(.+)$", line)
        if not m:
            continue
        issues.append({"line": int(m.group(1)), "col": int(m.group(2)),
                       "code": "F", "message": m.group(3).strip(),
                       "severity": LINT_WARNING})
    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


def _lint_builtin(code: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Wbudowany, lekki analizator AST (fallback bez ruff/pyflakes).

    Wykrywa: błąd składni, nieużywane importy, puste ``except:`` oraz użycie
    ``eval()``/``exec()``.
    """
    import ast
    try:
        tree = ast.parse(code or "", filename=path or "<skrypt>")
    except SyntaxError as e:
        return [{"line": e.lineno or 1, "col": e.offset or 1, "code": "E999",
                 "message": e.msg or "Błąd składni", "severity": LINT_ERROR}]
    issues: List[Dict[str, Any]] = []
    imported: Dict[str, int] = {}
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    imported[alias.asname or alias.name] = node.lineno
        elif isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append({"line": node.lineno, "col": 1, "code": "E722",
                           "message": "Puste 'except:' — użyj konkretnego wyjątku",
                           "severity": LINT_WARNING})
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("eval", "exec")):
            issues.append({"line": node.lineno, "col": 1, "code": "S307",
                           "message": f"Użycie '{node.func.id}()' może być niebezpieczne",
                           "severity": LINT_WARNING})
    for name, line in imported.items():
        if name not in used:
            issues.append({"line": line, "col": 1, "code": "F401",
                           "message": f"Zaimportowano '{name}', ale nie użyto",
                           "severity": LINT_WARNING})
    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


def lint_python(code: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Analiza statyczna kodu Python: ruff → pyflakes → wbudowany AST.

    Args:
        code: Treść skryptu do sprawdzenia.
        path: Opcjonalna nazwa/ścieżka pliku (dla czytelnych komunikatów).

    Returns:
        List[Dict[str, Any]]: Posortowana lista problemów; każdy ze kluczami
        ``line``, ``col``, ``code``, ``message`` i ``severity``
        (``LINT_ERROR`` lub ``LINT_WARNING``).
    """
    code = code or ""
    for engine in (_lint_with_ruff, _lint_with_pyflakes):
        issues = engine(code, path)
        if issues is not None:
            return issues
    return _lint_builtin(code, path)


# ── Linter: analiza statyczna pozostałych kategorii ──────────────────────────
# Kategorie obsługiwane przez lint_code() (Python + nowe języki).
LINT_CATEGORIES = {"Python", "JSON", "HTML", "HTA", "CSS", "PHP", "Ruby", "Perl"}


def lint_supported(kategoria: str) -> bool:
    """Czy dla danej kategorii dostępna jest analiza statyczna."""
    return (kategoria or "") in LINT_CATEGORIES


def _lint_blank_newlines(text: str, pattern: str) -> str:
    """Zastępuje dopasowania pustymi liniami — zachowuje numerację wierszy."""
    return re.sub(pattern, lambda m: "\n" * m.group(0).count("\n"), text or "",
                  flags=re.DOTALL | re.IGNORECASE)


def _lint_json(code: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Walidacja składni JSON (pełna, przez ``json.loads``)."""
    if not (code or "").strip():
        return []
    try:
        json.loads(code)
    except json.JSONDecodeError as e:
        return [{"line": e.lineno or 1, "col": e.colno or 1, "code": "JSON",
                 "message": f"Błąd składni JSON: {e.msg}", "severity": LINT_ERROR}]
    return []


# Znaczniki HTML bez treści (samozamykające się) — nie wymagają domknięcia.
_HTML_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
              "link", "meta", "param", "source", "track", "wbr"}


def _lint_html(code: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Heurystyczna walidacja HTML: niedomknięte komentarze i znaczniki."""
    code = code or ""
    if not code.strip():
        return []
    issues: List[Dict[str, Any]] = []
    if code.count("<!--") != code.count("-->"):
        issues.append({"line": 1, "col": 1, "code": "HTML",
                       "message": "Niezamknięty komentarz <!-- … -->",
                       "severity": LINT_WARNING})
    # pomijamy zawartość <script>/<style> zachowując numery linii
    body = _lint_blank_newlines(code, r"<!--.*?-->")
    body = _lint_blank_newlines(body, r"<(script|style)\b.*?</\1\s*>")
    stack: List[Any] = []
    for m in re.finditer(r"<\s*(/?)\s*([a-zA-Z][\w:-]*)([^>]*)>", body):
        closing, tag, rest = m.group(1), m.group(2).lower(), m.group(3)
        if tag in _HTML_VOID or rest.rstrip().endswith("/"):
            continue
        if closing:
            if any(t == tag for t, _ in stack):
                while stack and stack[-1][0] != tag:
                    stack.pop()
                if stack:
                    stack.pop()
        else:
            stack.append((tag, m.start()))
    for tag, pos in stack:
        ln = body[:pos].count("\n") + 1
        issues.append({"line": ln, "col": 1, "code": "HTML",
                       "message": f"Nie domknięto znacznika <{tag}>",
                       "severity": LINT_WARNING})
    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


def _lint_css(code: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Heurystyczna walidacja CSS: zbalansowanie nawiasów i komentarzy."""
    code = code or ""
    if not code.strip():
        return []
    issues: List[Dict[str, Any]] = []
    if code.count("/*") != code.count("*/"):
        issues.append({"line": 1, "col": 1, "code": "CSS",
                       "message": "Niezamknięty komentarz /* … */",
                       "severity": LINT_WARNING})
    body = _lint_blank_newlines(code, r"/\*.*?\*/")
    depth, open_line, line = 0, 1, 1
    for ch in body:
        if ch == "\n":
            line += 1
        elif ch == "{":
            if depth == 0:
                open_line = line
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                issues.append({"line": line, "col": 1, "code": "CSS",
                               "message": "Nadmiarowy znak '}'",
                               "severity": LINT_WARNING})
                depth = 0
    if depth > 0:
        issues.append({"line": open_line, "col": 1, "code": "CSS",
                       "message": f"Nie domknięto bloku '{{' (brak {depth} × '}}')",
                       "severity": LINT_WARNING})
    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


def _lint_with_interpreter(code: str, kategoria: str, tool: str, args: List[str],
                           path: Optional[str] = None, interpreter: str = ""
                           ) -> List[Dict[str, Any]]:
    """Sprawdzenie składni przez interpreter (``php -l`` / ``ruby -c`` / ``perl -c``).

    Gdy interpretera brakuje, zwraca pustą listę (brak fałszywych blokad).
    """
    if not (code or "").strip() or not _tool_available(tool, interpreter):
        return []
    ext = RUNNER_EXT.get(kategoria, ".txt")
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=ext, prefix="lint_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(code)
        proc = subprocess.run([_interp_tool(tool, interpreter)] + list(args) + [tmp],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=20,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return []
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    if proc.returncode == 0:
        return []
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    info = runner_parse_error(out, kategoria)
    line = int(info["linia"]) if info and info.get("linia") else 1
    msg = (info.get("komunikat") if info else "") or ""
    if not msg:
        msg = (out.splitlines() or [""])[-1][:200] or "Błąd składni"
    return [{"line": max(1, line), "col": 1, "code": kategoria.upper()[:4],
             "message": msg, "severity": LINT_ERROR}]


def lint_code(code: str, kategoria: str, path: Optional[str] = None,
              interpreter: str = "") -> List[Dict[str, Any]]:
    """Analiza statyczna kodu dowolnej obsługiwanej kategorii.

    Python → ruff/pyflakes/AST, JSON → ``json.loads``, HTML/HTA oraz CSS →
    heurystyka, PHP/Ruby/Perl → interpreter (``php -l`` / ``ruby -c`` /
    ``perl -c``) gdy jest dostępny. Dla pozostałych kategorii zwraca pustą listę.

    Returns:
        List[Dict[str, Any]]: problemy ze kluczami ``line``, ``col``, ``code``,
        ``message``, ``severity``.
    """
    kategoria = kategoria or ""
    if kategoria == "Python":
        return lint_python(code, path)
    if kategoria == "JSON":
        return _lint_json(code, path)
    if kategoria in ("HTML", "HTA"):
        return _lint_html(code, path)
    if kategoria == "CSS":
        return _lint_css(code, path)
    if kategoria == "PHP":
        return _lint_with_interpreter(code, kategoria, "php", ["-l"],
                                      path, interpreter)
    if kategoria == "Ruby":
        return _lint_with_interpreter(code, kategoria, "ruby", ["-c"],
                                      path, interpreter)
    if kategoria == "Perl":
        return _lint_with_interpreter(code, kategoria, "perl", ["-c"],
                                      path, interpreter)
    return []


def runner_kill_tree(proc: Any) -> None:
    """Ubija proces razem z dziećmi (PowerShell/cmd zostawia potomstwo po kill())."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            import subprocess as _sp
            _sp.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def runner_save_temp(kod: str, kategoria: str, workdir: Optional[str] = None,
                     interpreter: str = "") -> str:
    """Zapisuje kod do pliku tymczasowego (ASCII-safe nazwa) i zwraca ścieżkę.

    Dla Java plik nazywany jest nazwą klasy głównej (wymóg ``javac``), a obok
    tworzony jest launcher ``run_java.bat``. Dla C/C++ obok ``skrypt.c``/
    ``skrypt.cpp`` powstaje launcher ``run_c.bat``/``run_c.sh`` kompilujący
    (``gcc``/``g++``, fallback ``clang``/``clang++``) i uruchamiający program. Dla JAR zawartość (base64) jest
    dekodowana i zapisywana jako plik binarny. Dla Batch powstaje launcher
    ``run_batch.bat`` (UTF-8 + przekazanie kodu wyjścia). Dla VBScript plik ze
    znakami spoza ASCII zapisywany jest w UTF-16 z BOM (Windows Script Host).
    """
    d = workdir or tempfile.mkdtemp(prefix="runner_")
    kod = kod or ""
    if kategoria == "Java":
        path = os.path.join(d, runner_java_class(kod) + ".java")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(kod)
        runner_java_launcher(path, d, kod, interpreter)
        return path
    if kategoria in ("C", "C++"):
        ext = RUNNER_EXT[kategoria]
        path = os.path.join(d, "skrypt" + ext)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(kod or "")
        runner_c_launcher(path, d, kategoria, interpreter)
        return path
    if kategoria == "JAR":
        path = os.path.join(d, "skrypt.jar")
        with open(path, "wb") as fh:
            fh.write(jar_bytes(kod))
        return path
    if kategoria == "VBScript":
        path = os.path.join(d, "skrypt.vbs")
        if any(ord(ch) > 127 for ch in kod):
            with open(path, "wb") as fh:            # UTF-16 LE + BOM
                fh.write(kod.encode("utf-16"))
        else:
            with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
                fh.write(kod)
        return path
    if kategoria == "Batch":
        path = os.path.join(d, "skrypt.bat")
        with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write(kod)
        wrapper = os.path.join(d, "run_batch.bat")
        with open(wrapper, "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("@echo off\r\n"
                     "chcp 65001 >nul\r\n"
                     'cd /d "%~dp0"\r\n'
                     'call "%~dp0skrypt.bat" %*\r\n'
                     "exit /b %errorlevel%\r\n")
        return path
    ext = RUNNER_EXT.get(kategoria, ".txt")
    path = os.path.join(d, "skrypt" + ext)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(kod or "")
    return path


# ── Kolory ───────────────────────────────────────────────────────────────────
BG_DARK         = "#1e2130"
BG_PANEL        = "#252839"
BG_INPUT        = "#2a2d3e"
BG_TAB_ACT      = "#1e2130"
BG_TAB_INACT    = "#2a2d3e"
BG_SUBTAB_ACT   = "#2e3350"
BG_SUBTAB_INACT = "#252839"
BG_ROW_ODD      = "#252839"
BG_ROW_EVEN     = "#2a2d3e"
BG_ROW_SEL      = "#2e4a7a"
FG_WHITE        = "#e0e4f0"
FG_GRAY         = "#8a8fa8"
ACCENT_BLUE     = "#4a90d9"
BORDER_CLR      = "#3a3f58"
BTN_DARK        = "#2e3248"
BTN_HOVER       = "#3a3f5c"
BTN_OK          = "#2f6b3f"
BTN_OK_HOVER    = "#3d8a52"
BTN_ERR         = "#603030"
BTN_ERR_HOVER   = "#804040"
BTN_ACCENT      = "#4a90d9"

FONT_UI    = ("Consolas", 9)
FONT_BOLD  = ("Consolas", 9, "bold")
FONT_MONO  = ("Consolas", 10)
FONT_TITLE = ("Consolas", 16, "bold")

# Opcje kolorystyczne widżetów Tk poddawane przemapowaniu przy zmianie motywu.
_WIDGET_COLOR_OPTS = (
    "background", "foreground", "activebackground", "activeforeground",
    "highlightbackground", "highlightcolor", "selectbackground",
    "selectforeground", "insertbackground", "selectcolor", "buttonbackground",
    "troughcolor", "disabledforeground", "readonlybackground",
    "inactiveselectbackground",
)


def _bind_theme_globals(name: str) -> Dict[str, str]:
    """Przypisuje globalne stałe kolorów (``BG_*``, ``FG_*`` …) wg presetu motywu.

    Args:
        name: Nazwa motywu (klucz z ``THEME_PRESETS``).

    Returns:
        Dict[str, str]: Zastosowana paleta kolorów.
    """
    vals = theme_values(name)
    for key, val in vals.items():
        globals()[key] = val
    return vals


def _is_hex_color(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def _theme_values_with_custom(name: str, config: Dict[str, str]) -> Dict[str, str]:
    values = theme_values(name)
    for config_key, palette_keys in (
            ("bg_tab_act", ("BG_TAB_ACT",)),
            ("bg_tab_inact", ("BG_TAB_INACT",)),
            ("fg_text", ("FG_TEXT", "FG_WHITE"))):
        color = str(config.get(config_key, "")).strip()
        if color and _is_hex_color(color):
            for palette_key in palette_keys:
                values[palette_key] = color
    return values


# Polskie etykiety motywów (klucz presetu → tekst PL; tłumaczone przez _tr/_t).
_THEME_PL_LABELS = {
    "ciemny":      "Ciemny",
    "jasny":       "Jasny",
    "kontrastowy": "Kontrastowy",
}


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 7: CLASS CODEMATE — główna aplikacja
# ══════════════════════════════════════════════════════════════════════════════


class CodeMate(tk.Tk):
    def __init__(self, start_runner: bool = False) -> None:
        super().__init__()
        self.geometry("1024x700")
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        # lista zapisanych skryptów: [{id, nazwa, kategoria, tagi, opis, kod, ...}, ...]
        self.skrypty: List[Dict[str, Any]] = []
        # biblioteka snippetów: [{id, nazwa, kategoria, tagi, tresc, zmieniony}, ...]
        self.snippety: List[Dict[str, Any]] = snippets_load()
        # menedżer sekretów (zaszyfrowane tokeny/hasła wstrzykiwane do Runnera)
        self._secrets: Optional[Any] = None
        if _SECRETS_AVAILABLE:
            try:
                self._secrets = SecretsStore(SECRETS_FILE)
            except Exception as e:
                logging.warning(f"Nie udało się zainicjować menedżera sekretów: {e}")
        # historia wyszukiwań
        self.search_history: List[str] = []

        # ── Konfiguracja + ścieżka bazy (stała, jednoplikowa baza) ──────────
        self._cfg: Dict[str, str] = cfg_load()
        # Motyw interfejsu z konfiguracji — ustaw stałe kolorów przed budową UI.
        self._theme: str = self._cfg.get("theme", THEME_DEFAULT)
        if self._theme not in THEME_PRESETS:
            self._theme = THEME_DEFAULT
        self._theme_vals: Dict[str, str] = _bind_theme_globals(self._theme)
        _apply_hl_palette(self._theme)
        self.configure(bg=BG_DARK)
        # Język interfejsu z konfiguracji (domyślnie PL)
        _set_lang(self._cfg.get("language", "en"))
        self.title(_t("app_title", ver=APP_VER))
        # Ikona okna (pasek tytułu / pasek zadań) — plik .ico obok aplikacji.
        _icon = APP_DIR / "codemate.ico"
        if _icon.exists():
            try:
                self.iconbitmap(str(_icon))
            except Exception:
                pass
        self.db_path: Path = Path(self._cfg.get("db_path") or DB_FILE)
        self._last_save: Optional[str] = None
        self._autosave_pending: Optional[int] = None

        # ── Integracja Git ────────────────────────────────────────────────────
        # Sterowana konfiguracją: git_enabled (inicjalizacja) i git_auto_commit.
        self._git: Optional[GitIntegration] = None
        self._git_enabled = (
            _GIT_AVAILABLE and str(self._cfg.get("git_enabled", "1")) == "1")
        self._git_auto_commit: bool = str(self._cfg.get("git_auto_commit", "1")) == "1"
        self._git_auto_push: bool = str(self._cfg.get("git_auto_push", "0")) == "1"

        # ── System pluginów ────────────────────────────────────────────────────
        self._plugin_manager: Optional[PluginManager] = None
        if _PLUGINS_AVAILABLE and str(self._cfg.get("plugins_enabled", "1")) == "1":
            self._plugin_manager = PluginManager(self)
            loaded = self._plugin_manager.load_plugins()
            self._plugins_apply_disabled()
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("on_app_start")
            logging.info(f"Plugin system: {loaded} plugins loaded")

        self._build_menu()
        self._build_header()
        self._build_main_tabs()
        self._bind_shortcuts()
        self._mouse = MouseManager(self)
        # Syntax highlighter + walidacja nazwy
        self._highlighter = SyntaxHighlighter(self)
        self._autocomplete = AutoCompleter(self)
        self._apply_appearance_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._gui_ready = False
        # Jednorazowy pomiar minsize po polsku (niewidoczny — okno jeszcze
        # nie jest pokazane). Daje obu językom ten sam minimalny rozmiar.
        try:
            self._update_minsize_boot_pl()
        except Exception:
            pass
        # harmonogram — pętla planów działa od startu aplikacji (jeśli jest aktywny)
        self._sched_init()
        self._after_ids: List[int] = [
            self.after(100, self._autoload_db),
            self.after(200, self._mouse.register_app_tooltips),
            self.after(200, lambda: self._mouse.setup_tree_enhanced(self.tree)),
            self.after(300, self._attach_highlighter),
            self.after(300, self._attach_nazwa_validation),
            self.after(400, self._sched_sync_ui),
            self.after(150, self._update_minsize),
        ]
        if start_runner:
            self._after_ids.append(self.after(250, self._menu_pokaz_runner))

    def _safe_after(self, ms: int, func, *args):
        """After odporne na zamykanie — używane przez wątki tła.

        Gdy aplikacja się zamyka (``_shutting_down``) albo okno już nie żyje,
        callback jest po prostu pomijany zamiast wywołać TclError w wątku.
        Zwraca identyfikator after() albo None.
        """
        if getattr(self, "_shutting_down", False):
            return None
        try:
            return self.after(ms, lambda: func(*args))
        except tk.TclError:
            return None

    def __getattr__(self, name: str) -> Any:
        """Odporny dostęp do bazy — modułowe funkcje mogą ominąć __init__.
        Zapewnia sensowną wartość zamiast AttributeError dla pól infrastruktury.
        """
        if name.startswith("__") or not name.startswith("_"):
            raise AttributeError(name)
        defaults: Dict[str, Any] = {
            "_cfg": None, "db_path": "", "_last_save": None,
            "_autosave_pending": None, "_sc_index": None,
            "_runner_current_idx": None, "_runner_mode_edit": False,
            "_runner_proc": None, "_runner_busy": False,
            "_runner_force_new_console": False, "_runner_current": None,
            "_runner_finished": True, "_runner_busy": False,
            "_runner_tick_id": None, "_runner_follow": True,
            "_runner_list_sig": None, "_runner_after_id": None,
            "_sched_running": False, "_sched_after_id": None, "_sched_last": None,
            "_edytor_spec": None, "_runner_out": None, "_runner_out_sub": None,
            "snippety": [],
        }
        if name in defaults:
            return defaults[name]
        raise AttributeError(name)

    def _ensure_git(self) -> Optional[GitIntegration]:
        """Inicjalizuje Git przy pierwszym użyciu, a nie podczas budowy okna."""
        if not getattr(self, "_git_enabled", False):
            return None
        if self._git is None:
            try:
                self._git = GitIntegration(APP_DIR, auto_commit=True)
                if not self._git.is_available():
                    self._git.init_repo()
                logging.info(
                    "Git integration: %s",
                    "enabled" if self._git.is_available() else "disabled")
            except Exception as e:
                logging.warning(f"Nie udało się zainicjować integracji Git: {e}")
                self._git = None
        return self._git

    def _attach_highlighter(self) -> None:
        """Podłącz highlighter + autouzupełnianie do obu edytorów kodu."""
        if hasattr(self, "text_kod"):
            self._highlighter.attach(self.text_kod, lambda: self.var_kat.get())
            self._autocomplete.attach(self.text_kod, lambda: self.var_kat.get())
        if hasattr(self, "edytor_text"):
            self._attach_editor_highlighter()

    def _attach_editor_highlighter(self) -> None:
        """Podłącza highlighter i autouzupełnianie do edytora listy."""
        if not hasattr(self, "edytor_text"):
            return

        def _get_kat_edytor() -> str:
            idx = getattr(self, "_edytor_current_idx", None)
            if idx is not None and idx < len(self.skrypty):
                return self.skrypty[idx].get("kategoria", "Python")
            return "Python"

        self._highlighter.attach(self.edytor_text, _get_kat_edytor)
        self._autocomplete.attach(self.edytor_text, _get_kat_edytor)

    def _attach_nazwa_validation(self) -> None:
        """Podłącz walidację pola Nazwa na żywo."""
        if hasattr(self, "entry_nazwa"):
            self.entry_nazwa.bind("<KeyRelease>", self._validate_nazwa, add="+")

    def _validate_nazwa(self, event: Optional[tk.Event] = None) -> None:
        """Koloruje ramkę entry_nazwa: zielona=OK, czerwona=puste/duplikat."""
        nazwa = self.entry_nazwa.get().strip()
        if not nazwa:
            self.entry_nazwa.config(highlightbackground="#e05c5c",
                                    highlightcolor="#e05c5c")
            return
        # Sprawdź duplikat (ale pozwól na edycję istniejącego o tej samej nazwie)
        existing = [s["nazwa"] for s in self.skrypty]
        current_editing = getattr(self, "_editing_nazwa", None)
        if nazwa in existing and nazwa != current_editing:
            # Pomarańczowy = istnieje (aktualizacja)
            self.entry_nazwa.config(highlightbackground="#e0a020",
                                    highlightcolor="#e0a020")
        else:
            # Zielony = nowa lub ta sama nazwa (OK)
            self.entry_nazwa.config(highlightbackground="#4caf50",
                                    highlightcolor="#4caf50")

    def _bind_shortcuts(self):
        self.bind_all("<Control-n>",       lambda e: self._menu_nowy_skrypt())
        self.bind_all("<Control-s>",       lambda e: self._zapisz())
        self.bind_all("<Control-o>",       lambda e: self._wczytaj_plik())
        self.bind_all("<Control-w>",       lambda e: self._wyczysc())
        self.bind_all("<Control-f>",       lambda e: self._menu_pokaz_szukaj())
        self.bind_all("<Control-C>",       lambda e: self._kopiuj_kod())   # Ctrl+Shift+C
        self.bind_all("<F5>",              lambda e: self._menu_odswiez())
        # ── Runner ──────────────────────────────────────────────────────────
        self.bind_all("<F9>",              lambda e: self._runner_run_form())
        self.bind_all("<Shift-F9>",        lambda e: self._runner_run_form(save_first=False))
        self.bind_all("<Control-F9>",      lambda e: self._runner_run_form(new_console=True))
        # pozostaje aktywne także gdy trwa przebieg (zatrzymanie przez użytkownika)
        self.bind_all("<Control-F5>",      lambda e: self._runner_stop())
        self.bind_all("<Control-r>",       lambda e: self._menu_pokaz_runner())
        self.bind_all("<Control-R>",       lambda e: self._runner_run_form(save_first=False))
        self.bind_all("<Control-l>",       lambda e: self._runner_show_error_line())
        # ── Baza jednoplikowa ────────────────────────────────────────────────
        self.bind_all("<Control-Shift-S>", lambda e: self._save_db(save_as=True))
        self.bind_all("<Control-b>",       lambda e: self._manual_backup())
        # ── Panel wyjścia runnera ───────────────────────────────────────────
        self.bind_all("<Control-Shift-F>", lambda e: self._runner_find_focus())

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        # Przy zmianie języka menu jest przebudowywane — usuń poprzedni pasek.
        if getattr(self, "_menubar", None) is not None:
            try:
                self._menubar.destroy()
            except Exception:
                pass
        menubar = tk.Menu(self, bg=BG_PANEL, fg=FG_WHITE,
                          activebackground=BTN_ACCENT, activeforeground=FG_WHITE,
                          relief="flat", bd=0)
        self._menubar = menubar

        def menu(label):
            m = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=FG_WHITE,
                        activebackground=BTN_ACCENT, activeforeground=FG_WHITE)
            menubar.add_cascade(label=_tr(label), menu=m)
            return m

        def sep(m):
            m.add_separator()

        def item(m, label, cmd=None, shortcut=None):
            kw = {}
            if shortcut:
                kw["accelerator"] = shortcut
            m.add_command(label=_tr(label), command=cmd or (lambda: None), **kw)

        # ── Plik ──────────────────────────────────────────────────────────────
        m_plik = menu("Plik")
        item(m_plik, "Nowy skrypt",            self._menu_nowy_skrypt,       "Ctrl+N")
        item(m_plik, "Otwórz plik…",           self._wczytaj_plik,           "Ctrl+O")
        item(m_plik, "Importuj katalog…",       self._importuj_katalog)
        sep(m_plik)
        item(m_plik, "Zapisz skrypt",           self._zapisz,                 "Ctrl+S")
        item(m_plik, "Zapisz bazę do pliku",    self._save_db,                "Ctrl+Shift+S")
        item(m_plik, "Otwórz bazę z pliku…",    self._open_db)
        sep(m_plik)
        item(m_plik, "Eksportuj jako .py…",     lambda: self._eksportuj("py"))
        item(m_plik, "Eksportuj jako .txt…",    lambda: self._eksportuj("txt"))
        item(m_plik, "Eksportuj całą bazę…",    self._lista_eksportuj)
        item(m_plik, "Eksportuj bazę .bsdb…",   self._lista_eksport_bsdb)
        sep(m_plik)
        item(m_plik, "Importuj bazę (JSON)…",   self._lista_importuj)
        item(m_plik, "Importuj bazę .bsdb…",    self._lista_import_bsdb)
        item(m_plik, "Scal bazę (merge)…",      self._lista_importuj)
        sep(m_plik)
        item(m_plik, "Wyczyść formularz",       self._wyczysc,                "Ctrl+W")
        sep(m_plik)
        item(m_plik, "Zamknij aplikację",       self.destroy,                 "Alt+F4")

        # ── Skrypty ───────────────────────────────────────────────────────────
        m_skr = menu("Skrypty")
        item(m_skr, "Dodaj nowy skrypt",        self._menu_nowy_skrypt,       "Ctrl+N")
        item(m_skr, "Zapisz skrypt",            self._zapisz,                 "Ctrl+S")
        item(m_skr, "Wyczyść formularz",        self._wyczysc)
        sep(m_skr)
        item(m_skr, "Uruchom skrypt (runner)",   self._runner_run_form,        "F9")
        item(m_skr, "Uruchom w nowej konsoli",   lambda: self._runner_run_form(new_console=True), "Ctrl+F9")
        item(m_skr, "Uruchom zaznaczony z listy",self._runner_run_selected)
        item(m_skr, "Zatrzymaj proces",          self._runner_stop,            "Ctrl+F5")
        item(m_skr, "Pokaż panel Runner",        self._menu_pokaz_runner)
        sep(m_skr)
        item(m_skr, "Kopiuj kod do schowka",    self._kopiuj_kod,             "Ctrl+Shift+C")
        item(m_skr, "Wczytaj plik do edytora",  self._wczytaj_plik)
        sep(m_skr)
        item(m_skr, "Pokaż listę skryptów",     self._menu_pokaz_liste)
        item(m_skr, "Edytuj zaznaczony",        self._edytuj_skrypt)
        item(m_skr, "Usuń zaznaczony",          self._usun_skrypt,            "Delete")
        sep(m_skr)
        item(m_skr, "🗑 Kosz — przywróć/opróżnij", self._menu_pokaz_kosz)
        sep(m_skr)
        item(m_skr, "Importuj skrypty (JSON)…", self._lista_importuj)
        item(m_skr, "Eksportuj skrypty (JSON)…",self._lista_eksportuj)

        # ── Run (runner) ──────────────────────────────────────────────────────
        m_run = menu("Run")
        item(m_run, "Pokaż panel Runner",        self._menu_pokaz_runner,     "Ctrl+R")
        sep(m_run)
        item(m_run, "Uruchom (zapisuje najpierw)", self._runner_run_form,      "F9")
        item(m_run, "Uruchom bez zapisu",         lambda: self._runner_run_form(save_first=False), "Shift+F9")
        item(m_run, "Uruchom w nowej konsoli",    lambda: self._runner_run_form(new_console=True), "Ctrl+F9")
        item(m_run, "Zatrzymaj",                  self._runner_stop,          "Ctrl+F5")
        sep(m_run)
        item(m_run, "Szukaj w wyjściu",           self._runner_find_focus,    "Ctrl+Shift+F")
        item(m_run, "Przejdź do linii błędu",     self._runner_show_error_line, "Ctrl+L")
        sep(m_run)
        item(m_run, "Harmonogram — plany…",       lambda: self._runner_open_pane("plan"))
        item(m_run, "Harmonogram — włącz/zatrzymaj", self._sched_toggle)
        sep(m_run)
        item(m_run, "Wyczyść panel wyjścia",      self._runner_clear)
        item(m_run, "Eksportuj wyjście…",         self._runner_export_out)
        item(m_run, "Eksportuj skrypt jako .bat", self._runner_export_bat)

        # ── Biblioteka ────────────────────────────────────────────────────────
        m_bib = menu("Biblioteka")
        item(m_bib, "Pokaż wszystkie skrypty",  self._menu_pokaz_liste)
        item(m_bib, "Filtruj wg kategorii…",    self._menu_filtr_kategoria)
        item(m_bib, "Filtruj wg tagów…",        self._menu_filtr_tagi)
        sep(m_bib)
        item(m_bib, "Zaawansowane wyszukiwanie",self._menu_pokaz_szukaj,      "Ctrl+F")
        sep(m_bib)
        item(m_bib, "Sortuj A→Z",               lambda: self._menu_sortuj("nazwa", "ASC"))
        item(m_bib, "Sortuj Z→A",               lambda: self._menu_sortuj("nazwa", "DESC"))
        item(m_bib, "Sortuj wg kategorii",       lambda: self._menu_sortuj("kategoria", "ASC"))
        sep(m_bib)
        item(m_bib, "Eksportuj listę (.txt)…",  self._adv_export)
        item(m_bib, "Kopiuj wyniki wyszukiwania",self._adv_copy_results)

        # ── Baza danych ───────────────────────────────────────────────────────
        m_db = menu("Baza danych")
        item(m_db, "Importuj bazę (JSON)…",     self._lista_importuj)
        item(m_db, "Eksportuj bazę (JSON)…",    self._lista_eksportuj)
        item(m_db, "Scal bazę (merge)…",        self._lista_importuj)
        sep(m_db)
        item(m_db, "Wyczyść całą bazę…",        self._menu_wyczysc_baze)
        sep(m_db)
        item(m_db, "Statystyki bazy",           self._menu_statystyki)
        item(m_db, "Odśwież widok",             self._menu_odswiez)
        sep(m_db)
        item(m_db, "Kopia zapasowa bazy…",      lambda: self._save_db(save_as=True))
        item(m_db, "Diagnostyka bazy",          self._run_diag)
        item(m_db, "Naprawa bazy",              self._naprawa_scan)

        # ── Narzędzia ─────────────────────────────────────────────────────────
        m_nar = menu("Narzędzia")
        item(m_nar, "Uruchom diagnostykę",      self._run_diag)
        item(m_nar, "Testy osiągów",            self._run_testy)
        item(m_nar, "Naprawa błędów",           self._naprawa_scan)
        sep(m_nar)
        item(m_nar, "Kreator Pluginów",         self._menu_pokaz_plugin)
        item(m_nar, "Łączenie modułów",         self._menu_pokaz_laczen)
        sep(m_nar)
        item(m_nar, "🔑 Menedżer sekretów…",    self._menu_sekrety)
        sep(m_nar)
        item(m_nar, "Kopiuj kod",               self._kopiuj_kod,             "Ctrl+Shift+C")
        item(m_nar, "Wczytaj plik…",            self._wczytaj_plik)
        item(m_nar, "Importuj katalog…",         self._importuj_katalog)
        sep(m_nar)
        item(m_nar, "Odśwież info o modułach",  self._mod_refresh_info)

        # ── Widok ─────────────────────────────────────────────────────────────
        m_wid = menu("Widok")
        item(m_wid, "Skrypty — Nowy skrypt",    self._menu_nowy_skrypt)
        item(m_wid, "Skrypty — Lista",          self._menu_pokaz_liste)
        item(m_wid, "Skrypty — Edytor",         self._menu_pokaz_edytor)
        sep(m_wid)
        item(m_wid, "Szukaj",                   self._menu_pokaz_szukaj,      "Ctrl+F")
        sep(m_wid)
        item(m_wid, "Moduły — Info",            lambda: self._menu_pokaz_mod("info"))
        item(m_wid, "Moduły — Diagnostyka",     lambda: self._menu_pokaz_mod("diag"))
        item(m_wid, "Moduły — Łączenie",        lambda: self._menu_pokaz_mod("laczen"))
        item(m_wid, "Moduły — Graf zależności", lambda: self._menu_pokaz_mod("graf"))
        item(m_wid, "Moduły — Testy osiągów",   lambda: self._menu_pokaz_mod("testy"))
        item(m_wid, "Moduły — Naprawa",         lambda: self._menu_pokaz_mod("naprawa"))
        item(m_wid, "Moduły — Kreator Pluginów",lambda: self._menu_pokaz_mod("plugin"))
        sep(m_wid)
        # Podmenu: przełączanie motywu (na żywo, bez restartu).
        m_motyw = tk.Menu(m_wid, tearoff=0, bg=BG_PANEL, fg=FG_WHITE,
                          activebackground=BTN_ACCENT, activeforeground=FG_WHITE)
        m_wid.add_cascade(label=_tr("Motyw"), menu=m_motyw)
        for _tm in THEME_ORDER:
            m_motyw.add_command(label=_tr(_THEME_PL_LABELS.get(_tm, _tm)),
                                command=lambda n=_tm: self._apply_theme(n))

        # ── Narzędzia dodatkowe ───────────────────────────────────────────────
        m_nd = menu("Narzędzia dodatkowe")
        item(m_nd, "Załaduj moduł z pliku…",    lambda: self._mod_zaladuj("info"))
        item(m_nd, "Eksportuj raport info…",     self._mod_export_info)
        item(m_nd, "Kopiuj raport info",         self._mod_copy_info)
        sep(m_nd)
        item(m_nd, "Zapisz log diagnostyki…",    self._diag_save_log)
        item(m_nd, "Eksportuj wyniki testów…",   self._testy_export)
        item(m_nd, "Zapisz raport naprawy…",     self._naprawa_save)
        sep(m_nd)
        item(m_nd, "Generuj plugin",             self._plugin_generuj)
        item(m_nd, "Eksportuj plugin (.py)…",    self._plugin_eksportuj)
        item(m_nd, "Zapisz plugin w bazie",      self._plugin_zapisz_w_bazie)
        sep(m_nd)
        item(m_nd, "Wyczyść historię wyszukiwań",self._adv_clear_history)
        item(m_nd, "Kopiuj wyniki wyszukiwania", self._adv_copy_results)

        # ── Ustawienia ────────────────────────────────────────────────────────
        m_ust = menu("Ustawienia")
        item(m_ust, "Kategorie skryptów…",       self._menu_ustawienia_kategorie)
        item(m_ust, "Interpreter i timeout…",    self._menu_ustawienia_runner)
        sep(m_ust)
        item(m_ust, "Ścieżka pliku bazy…",       lambda: self._save_db(save_as=True))
        item(m_ust, "Otwórz plik bazy w folderze", self._open_db_folder)
        sep(m_ust)
        item(m_ust, "Odśwież wszystkie widoki",  self._menu_odswiez)
        item(m_ust, "Informacje o środowisku",   self._mod_refresh_info)

        # ── Pomoc ─────────────────────────────────────────────────────────────
        m_pom = menu("Pomoc")
        item(m_pom, "Skróty klawiszowe",         self._menu_skroty)
        item(m_pom, "Obsługiwane skrypty i pliki", self._menu_obslugiwane)
        sep(m_pom)
        item(m_pom, "Diagnostyka: sprawdź kod",   self._menu_self_check)
        item(m_pom, "Diagnostyka: sprawdź bazę",  self._menu_verify_db)
        sep(m_pom)
        item(m_pom, "O programie",               self._menu_o_programie)

        self.config(menu=menubar)

    # ── Akcje menu ────────────────────────────────────────────────────────────

    def _menu_nowy_skrypt(self):
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(0, self._show_sub_dodaj)
        self._wyczysc()

    def _menu_pokaz_runner(self):
        self._sel_main(8, self._show_runner)

    def _show_runner(self):
        self.main_frames["runner"].pack(fill="both", expand=True)
        self._runner_fill_list()

    def _menu_pokaz_liste(self):
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(1, self._show_sub_lista)

    def _menu_pokaz_kosz(self):
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(8, self._show_sub_kosz)

    def _menu_pokaz_edytor(self):
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(2, self._show_sub_edytor)

    def _menu_pokaz_szukaj(self):
        self._sel_main(1, self._show_szukaj)

    def _menu_pokaz_mod(self, key):
        self._sel_main(2, self._show_moduly)
        idx = ["info", "diag", "laczen", "graf", "testy", "naprawa", "plugin"].index(key)
        for j, b in enumerate(self._mod_btns):
            b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                        fg=FG_WHITE       if j == idx else FG_GRAY)
        for f in self._mod_frames.values():
            f.pack_forget()
        self._mod_frames[key].pack(fill="both", expand=True)
        self._update_minsize()

    def _menu_pokaz_plugin(self):
        self._menu_pokaz_mod("plugin")

    def _menu_pokaz_laczen(self):
        self._menu_pokaz_mod("laczen")

    def _menu_filtr_kategoria(self):
        dlg = _popup(self)
        dlg.title(_tr("Filtruj wg kategorii"))
        dlg.configure(bg=BG_DARK)
        dlg.geometry("300x280")
        dlg.resizable(False, False)
        dlg.grab_set()
        self._trw(tk.Label(dlg, text=_tr("Wybierz kategorię:"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), "Wybierz kategorię:").pack(anchor="w", padx=14, pady=(12, 4))
        var = tk.StringVar(value="Wszystkie")
        for cat in ["Wszystkie"] + CATEGORIES:
            self._trw(tk.Radiobutton(dlg, text=_tr(cat), variable=var, value=cat,
                           font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                           activebackground=BG_DARK, selectcolor=BG_INPUT), cat).pack(anchor="w", padx=22)
        def apply_filter():
            chosen = var.get()
            self._menu_pokaz_liste()
            query = "" if chosen == "Wszystkie" else chosen
            for row in self.tree.get_children():
                self.tree.delete(row)
            for i, s in enumerate(self.skrypty):
                if query and s.get("kategoria", "") != query:
                    continue
                opis_skrot = s["opis"][:80] + ("…" if len(s["opis"]) > 80 else "")
                self.tree.insert("", "end", iid=str(i),
                                 values=(s["nazwa"], kat_label(s["kategoria"]),
                                         s["tagi"], opis_skrot),
                                 tags=("odd" if i % 2 == 0 else "even",))
            dlg.destroy()
        self._trw(tk.Button(dlg, text=_tr("Zastosuj filtr"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", command=apply_filter), "Zastosuj filtr").pack(pady=14)

    def _menu_filtr_tagi(self):
        dlg = _popup(self)
        dlg.title(_tr("Filtruj wg tagów"))
        dlg.configure(bg=BG_DARK)
        dlg.geometry("320x180")
        dlg.resizable(False, False)
        dlg.grab_set()
        self._trw(tk.Label(dlg, text=_tr("Wpisz tag (częściowe dopasowanie):"),
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE), "Wpisz tag (częściowe dopasowanie):").pack(anchor="w", padx=14, pady=(12, 4))
        e = tk.Entry(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                     insertbackground=FG_WHITE, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER_CLR,
                     highlightcolor=ACCENT_BLUE)
        e.pack(fill="x", padx=14, pady=4)
        e.focus_set()
        def apply():
            tag = e.get().strip().lower()
            self._menu_pokaz_liste()
            for row in self.tree.get_children():
                self.tree.delete(row)
            for i, s in enumerate(self.skrypty):
                if tag and tag not in s.get("tagi", "").lower():
                    continue
                opis_skrot = s["opis"][:80] + ("…" if len(s["opis"]) > 80 else "")
                self.tree.insert("", "end", iid=str(i),
                                 values=(s["nazwa"], kat_label(s["kategoria"]),
                                         s["tagi"], opis_skrot),
                                 tags=("odd" if i % 2 == 0 else "even",))
            dlg.destroy()
        e.bind("<Return>", lambda _: apply())
        self._trw(tk.Button(dlg, text=_tr("Filtruj"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", command=apply), "Filtruj").pack(pady=10)

    def _menu_sortuj(self, pole, kierunek):
        self._menu_pokaz_liste()
        rev = (kierunek == "DESC")
        self.skrypty.sort(key=lambda s: s.get(pole, "").lower(), reverse=rev)
        self._refresh_lista()

    def _menu_wyczysc_baze(self):
        if not self.skrypty:
            messagebox.showinfo(_tr("Baza pusta"), _tr("CodeMate jest już pusta."))
            return
        if messagebox.askyesno(_tr("Wyczyść bazę"),                              f"Usunąć wszystkie {len(self.skrypty)} skrypt(ów)?\n"
                               "Tej operacji nie można cofnąć!"):
            self.skrypty.clear()
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            self.save_db(silent=True)
            messagebox.showinfo(_tr("Wyczyszczono"), _tr("CodeMate została wyczyszczona."))

    def _menu_statystyki(self):
        self._menu_pokaz_szukaj()
        # przełącz na zakładkę Statystyki
        for j, ib in enumerate(self._inner_btns):
            ib.configure(bg=BG_SUBTAB_ACT if j == 2 else BG_SUBTAB_INACT,
                         fg=FG_WHITE       if j == 2 else FG_GRAY)
        for f in self._inner_frames.values():
            f.pack_forget()
        self._inner_frames["statystyki"].pack(fill="both", expand=True)
        self._update_minsize()
        self._adv_refresh_stats()

    def _menu_odswiez(self):
        self._refresh_lista()
        self._mod_refresh_info()
        self._update_count()

    def _menu_ustawienia_kategorie(self):
        dlg = _popup(self)
        dlg.title(_tr("Kategorie skryptów"))
        dlg.configure(bg=BG_DARK)
        dlg.geometry("340x320")
        dlg.resizable(False, True)
        dlg.grab_set()
        self._trw(tk.Label(dlg, text=_tr("Aktywne kategorie:"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), "Aktywne kategorie:").pack(anchor="w", padx=14, pady=(12, 4))
        sc = tk.Scrollbar(dlg, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=8)
        sc.pack(side="right", fill="y", padx=(0, 6), pady=4)
        lb = tk.Listbox(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                        selectmode="browse", relief="flat", highlightthickness=0,
                        selectbackground=BG_ROW_SEL, activestyle="none",
                        yscrollcommand=sc.set)
        sc.config(command=lb.yview)
        lb.pack(fill="both", expand=True, padx=(14, 0), pady=4)
        for cat in CATEGORIES:
            lb.insert("end", kat_label(cat))
            lb.itemconfig("end", foreground=KAT_COLOR.get(cat, FG_WHITE))
        self._trw(tk.Label(dlg, text=_tr("(edycja kategorii w przyszłej wersji)"),
                 font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY), "(edycja kategorii w przyszłej wersji)").pack(pady=(0, 8))

    def _menu_self_check(self):
        """Statyczna kontrola kodu aplikacji z GUI (wynik: okno dialogowe)."""
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self_check(self.skrypty)
        text = buf.getvalue()
        self._diag_show("Diagnostyka kodu", text, rc)

    def _menu_verify_db(self):
        """Sprawdzienie spójności pliku bazy z GUI."""
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = verify_db(self.skrypty, self.db_path)
        self._diag_show("Diagnostyka bazy", buf.getvalue(), rc)

    def _diag_show(self, title, text, rc):
        dlg = _popup(self)
        dlg.title(title)
        dlg.configure(bg=BG_DARK)
        dlg.geometry("760x460")
        dlg.transient(self)
        tk.Label(dlg, text=("✓ " if rc == 0 else "✗ ") + title,
                 font=FONT_BOLD, bg=BG_DARK,
                 fg="#6dde84" if rc == 0 else "#e05c5c").pack(anchor="w", padx=12, pady=(10, 4))
        txt = tk.Text(dlg, font=("Consolas", 9), bg="#14161f", fg="#c8d0f0",
                      relief="flat", wrap="none")
        txt.pack(fill="both", expand=True, padx=12, pady=6)
        txt.insert("1.0", text)
        for i, line in enumerate(text.splitlines(), 1):
            if "[BŁĄD]" in line:
                txt.tag_add("err", f"{i}.0", f"{i}.end")
            elif "[UWAGA]" in line or "[INFO]" in line:
                txt.tag_add("warn", f"{i}.0", f"{i}.end")
        txt.tag_config("err", foreground="#e05c5c")
        txt.tag_config("warn", foreground="#e0c040")
        txt.config(state="disabled")
        tk.Button(dlg, text=_tr("Zamknij"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  command=dlg.destroy).pack(pady=8)

    def _menu_skroty(self):
        dlg = _popup(self)
        dlg.title(_tr("Skróty klawiszowe"))
        dlg.configure(bg=BG_DARK)
        dlg.geometry("420x470")
        dlg.resizable(False, False)
        dlg.grab_set()
        self._trw(tk.Label(dlg, text=_tr("⌨ Skróty klawiszowe"), font=FONT_BOLD,
                 bg=BG_DARK, fg=ACCENT_BLUE), "⌨ Skróty klawiszowe").pack(anchor="w", padx=14, pady=(12, 6))
        skroty = [
            ("Ctrl+N",        "Nowy skrypt"),
            ("Ctrl+S",        "Zapisz skrypt (i bazę)"),
            ("Ctrl+Shift+S",  "Zapisz bazę jako / kopia zapasowa"),
            ("Ctrl+O",        "Otwórz plik"),
            ("Ctrl+W",        "Wyczyść formularz"),
            ("Ctrl+F",        "Zaawansowane wyszukiwanie"),
            ("Ctrl+Shift+C",  "Kopiuj kod do schowka"),
            ("F9",            "Uruchom skrypt (Runner)"),
            ("Shift+F9",      "Uruchom bez zapisu"),
            ("Ctrl+R",        "Pokaż panel Runner"),
            ("Ctrl+F9",       "Uruchom w nowej konsoli"),
            ("Ctrl+F5",       "Zatrzymaj proces"),
            ("Ctrl+Shift+F",  "Szukaj w wyjściu runnera"),
            ("Ctrl+L",        "Przejdź do linii błędu"),
            ("Alt+F4",        "Zamknij aplikację (zapisze bazę)"),
            ("Delete",        "Usuń zaznaczony skrypt"),
            ("F5",            "Odśwież widoki"),
        ]
        for skrot, opis in skroty:
            row = tk.Frame(dlg, bg=BG_DARK)
            row.pack(fill="x", padx=14, pady=2)
            tk.Label(row, text=skrot, font=FONT_BOLD, bg=BG_INPUT, fg=ACCENT_BLUE,
                     width=18, anchor="w", padx=6, pady=2).pack(side="left")
            self._trw(tk.Label(row, text=_tr(opis), font=FONT_UI, bg=BG_DARK,
                     fg=FG_WHITE, anchor="w"), opis).pack(side="left", padx=8)
        self._trw(tk.Button(dlg, text=_tr("Zamknij"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=12, pady=4,
                  cursor="hand2", command=dlg.destroy), "Zamknij").pack(pady=14)

    def _menu_obslugiwane(self):
        """Okno z listą obsługiwanych skryptów, plików i rozszerzeń."""
        # Liczba wierszy = grupy + wpisy; wysokość wiersza wg stylu drzewa.
        wiersze = sum(len(wpisy) for _, wpisy in OBSL_GRUPY) + len(OBSL_GRUPY)
        kolumny = (190, 140, 140, 260)
        szer = sum(kolumny) + 56          # + pasek przewijania i marginesy
        total = sum(len(wpisy) for _, wpisy in OBSL_GRUPY)

        dlg = _popup(self)
        dlg.withdraw()                    # budowa bez migotania, pokazanie na końcu
        dlg.title(_tr("Obsługiwane skrypty i pliki"))
        dlg.configure(bg=BG_DARK)

        # ── Nagłówek (baner) ────────────────────────────────────────────────
        naglowek = tk.Frame(dlg, bg=BG_PANEL)
        naglowek.pack(fill="x")
        self._trw(tk.Label(naglowek, text=_tr("📦 Obsługiwane skrypty i pliki"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE),
                 "📦 Obsługiwane skrypty i pliki").pack(anchor="w", padx=14, pady=(12, 1))
        self._trw(tk.Label(naglowek,
                 text=_tr("Rozszerzenia, kategorie i polecenia uruchomieniowe"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                 "Rozszerzenia, kategorie i polecenia uruchomieniowe").pack(
                     anchor="w", padx=14, pady=(0, 11))
        tk.Frame(dlg, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Tabela ──────────────────────────────────────────────────────────
        wrap = tk.Frame(dlg, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=14, pady=(10, 6))
        vsb = tk.Scrollbar(wrap, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=10, relief="flat",
                           bd=0, highlightthickness=0)
        vsb.pack(side="right", fill="y")
        tree = ttk.Treeview(wrap, columns=("rozsz", "kat", "run"),
                            show="tree headings", style="Dark.Treeview",
                            height=wiersze, yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        self._trh(tree, "#0", "Grupa")
        tree.heading("#0", anchor="w")
        self._trh(tree, "rozsz", "Rozszerzenie")
        self._trh(tree, "kat", "Kategoria")
        self._trh(tree, "run", "Runner / interpreter")
        tree.column("#0", width=kolumny[0], minwidth=140, anchor="w")
        tree.column("rozsz", width=kolumny[1], minwidth=100, anchor="w")
        tree.column("kat", width=kolumny[2], minwidth=100, anchor="w")
        tree.column("run", width=kolumny[3], minwidth=160, anchor="w")
        tree.pack(side="left", fill="both", expand=True)

        # Wiersze grup — pasek tła i akcent. Wpisy — tło naprzemienne oraz
        # kolor kategorii (spójnie z drzewem szablonów i listą skryptów).
        tree.tag_configure("grupa", background=BG_PANEL,
                           foreground=ACCENT_BLUE, font=FONT_BOLD)
        for grupa, wpisy in OBSL_GRUPY:
            parent = tree.insert("", "end", text=f"  {_tr(grupa)}", open=True,
                                 tags=("grupa",))
            for i, (rozsz, kat, run) in enumerate(wpisy):
                tag = f"kat_{kat}"
                tree.tag_configure(
                    tag,
                    background=BG_ROW_EVEN if i % 2 else BG_ROW_ODD,
                    foreground=KAT_COLOR.get(kat, FG_WHITE))
                tree.insert(parent, "end", text="",
                            values=(rozsz, kat_label(kat), _tr(run)), tags=(tag,))

        # ── Stopka: podsumowanie + przycisk ─────────────────────────────────
        tk.Frame(dlg, bg=BORDER_CLR, height=1).pack(fill="x")
        stopka = tk.Frame(dlg, bg=BG_DARK)
        stopka.pack(fill="x", padx=14, pady=10)
        tk.Label(stopka, text=_tr("Łącznie: {n} typów plików").format(n=total),
                 font=FONT_UI, bg=BG_DARK, fg="#6dde84").pack(side="left")
        btn = self._trw(tk.Button(stopka, text=_tr("Zamknij"), font=FONT_UI,
                    bg=BTN_DARK, fg=FG_WHITE, activebackground=BTN_HOVER,
                    activeforeground=FG_WHITE, relief="flat", bd=0,
                    highlightthickness=0, padx=16, pady=5, cursor="hand2",
                    command=dlg.destroy), "Zamknij")
        btn.pack(side="right")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BTN_HOVER))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BTN_DARK))

        # ── Rozmiar z zawartości, potem pokazanie (bez migotania) ───────────
        dlg.update_idletasks()
        dlg.geometry(f"{max(szer, dlg.winfo_reqwidth())}x{dlg.winfo_reqheight()}")
        dlg.minsize(560, 320)
        dlg.resizable(True, True)
        dlg.deiconify()
        dlg.grab_set()
        dlg.lift()
        dlg.focus_set()

    # ══════════════════════════════════════════════════════════════════════════
    # MENEDŻER SEKRETÓW — szyfrowany sejf + wstrzykiwanie do Runnera
    # ══════════════════════════════════════════════════════════════════════════
    def _sek_script_names(self):
        """Nazwy skryptów możliwych do powiązania z sekretem."""
        return [str(s.get("nazwa") or "") for s in self.skrypty
                if isinstance(s, dict) and not s.get("usuniety")]

    def _menu_sekrety(self):
        """Okno menedżera sekretów (szyfrowanie Fernet + magazyn klucza keyring)."""
        if self._secrets is None:
            messagebox.showinfo(
                _tr("Menedżer sekretów"),
                _tr("Menedżer sekretów jest niedostępny — brak biblioteki „cryptography”."))
            return
        dlg = _popup(self)
        dlg.withdraw()                    # budowa bez migotania, pokazanie na końcu
        dlg.title(_tr("🔑 Menedżer sekretów"))
        dlg.configure(bg=BG_DARK)

        # ── Nagłówek ─────────────────────────────────────────────────────────
        hdr = tk.Frame(dlg, bg=BG_PANEL, padx=12, pady=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("🔑 Menedżer sekretów"), font=FONT_TITLE,
                 bg=BG_PANEL, fg=ACCENT_BLUE), "🔑 Menedżer sekretów").pack(anchor="w")
        self._trw(tk.Label(hdr, text=_tr("Zaszyfrowane tokeny i hasła wstrzykiwane jako "
                 "zmienne środowiskowe do uruchamianych skryptów."),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                 "Zaszyfrowane tokeny i hasła wstrzykiwane jako "
                 "zmienne środowiskowe do uruchamianych skryptów.").pack(anchor="w", pady=(2, 0))
        tk.Frame(dlg, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Informacja o magazynie klucza ────────────────────────────────────
        kr_msg = (_tr("Klucz szyfrujący: systemowy magazyn poświadczeń (keyring).")
                  if self._secrets.keyring_available()
                  else _tr("Klucz szyfrujący: lokalny plik klucza (keyring niedostępny)."))
        self._trw(tk.Label(dlg, text=kr_msg, font=("Consolas", 8), bg=BG_DARK,
                 fg=FG_GRAY), kr_msg).pack(anchor="w", padx=12, pady=(4, 0))

        body = tk.Frame(dlg, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        # ── Formularz ────────────────────────────────────────────────────────
        form = tk.Frame(body, bg=BG_PANEL, highlightthickness=1,
                        highlightbackground=BORDER_CLR, padx=10, pady=8)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        def lbl(r, c, txt):
            w = tk.Label(form, text=_tr(txt), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                         anchor="w")
            w.grid(row=r, column=c, sticky="w", padx=(0, 6), pady=3)
            self._trw(w, txt)

        def ent(r, c, show=None):
            e = tk.Entry(form, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat", show=show or "",
                         highlightthickness=1, highlightbackground=BORDER_CLR,
                         highlightcolor=ACCENT_BLUE)
            e.grid(row=r, column=c, sticky="ew", padx=(0, 12), pady=3, ipady=3)
            return e

        lbl(0, 0, "Nazwa (zmienna)")
        self._sek_nazwa = ent(0, 1)
        lbl(0, 2, "Zakres")
        self._sek_zakres = ttk.Combobox(form, font=FONT_UI, style="Dark.TCombobox",
                                        state="readonly", width=10,
                                        values=["global", "skrypt"])
        self._trc(self._sek_zakres, ("global", "skrypt"))
        self._sek_zakres.set(_tr("global"))
        self._sek_zakres.grid(row=0, column=3, sticky="w", pady=3)
        self._sek_zakres.bind("<<ComboboxSelected>>", lambda e: self._sek_sync_scope())

        lbl(1, 0, "Skrypt")
        self._sek_skrypt = ttk.Combobox(form, font=FONT_UI, style="Dark.TCombobox",
                                        values=self._sek_script_names(), width=32)
        self._sek_skrypt.grid(row=1, column=1, columnspan=3, sticky="ew", pady=3)

        lbl(2, 0, "Wartość")
        self._sek_wartosc = ent(2, 1, show="•")
        lbl(2, 2, "Opis")
        self._sek_opis = ent(2, 3)

        bar = tk.Frame(form, bg=BG_PANEL)
        bar.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self._trw(tk.Button(bar, text=_tr("💾 Zapisz sekret"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._sek_save), "💾 Zapisz sekret").pack(side="left")
        self._trw(tk.Button(bar, text=_tr("🔄 Wyczyść"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sek_clear), "🔄 Wyczyść").pack(side="left", padx=6)
        self.lbl_sek_status = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL,
                                       fg=FG_GRAY)
        self.lbl_sek_status.pack(side="left", padx=10)

        # ── Lista sekretów ───────────────────────────────────────────────────
        listwrap = tk.Frame(body, bg=BG_PANEL, highlightthickness=1,
                            highlightbackground=BORDER_CLR)
        listwrap.pack(fill="both", expand=True, pady=(8, 0))
        tvs = tk.Scrollbar(listwrap, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=8)
        tvs.pack(side="right", fill="y")
        self.sek_tree = ttk.Treeview(listwrap, columns=("zakres", "skrypt", "opis", "zm"),
                                     show="tree headings", style="Dark.Treeview",
                                     height=8, yscrollcommand=tvs.set)
        tvs.config(command=self.sek_tree.yview)
        self._trh(self.sek_tree, "#0", "Nazwa")
        self._trh(self.sek_tree, "zakres", "Zakres")
        self._trh(self.sek_tree, "skrypt", "Skrypt")
        self._trh(self.sek_tree, "opis", "Opis")
        self._trh(self.sek_tree, "zm", "Zmieniony")
        self.sek_tree.column("#0", width=160, minwidth=110, anchor="w")
        self.sek_tree.column("zakres", width=70, minwidth=60, anchor="w")
        self.sek_tree.column("skrypt", width=140, minwidth=90, anchor="w")
        self.sek_tree.column("opis", width=200, minwidth=100, anchor="w")
        self.sek_tree.column("zm", width=140, minwidth=110, anchor="w")
        self.sek_tree.pack(fill="both", expand=True, padx=(8, 0), pady=6)
        self.sek_tree.bind("<<TreeviewSelect>>", self._sek_select)

        # ── Stopka: akcje + zamknij ──────────────────────────────────────────
        foot = tk.Frame(body, bg=BG_DARK)
        foot.pack(fill="x", pady=(6, 0))
        self._trw(tk.Button(foot, text=_tr("👁 Pokaż wartość"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sek_reveal), "👁 Pokaż wartość").pack(side="left")
        self._trw(tk.Button(foot, text=_tr("📋 Kopiuj wartość"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sek_copy), "📋 Kopiuj wartość").pack(side="left", padx=6)
        self._trw(tk.Button(foot, text=_tr("🗑 Usuń"), font=FONT_UI,
                  bg=BTN_DARK, fg="#e07070", relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sek_delete), "🗑 Usuń").pack(side="left")
        self._trw(tk.Button(foot, text=_tr("Zamknij"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=12, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=dlg.destroy), "Zamknij").pack(side="right")

        self._sek_refresh()
        self._sek_sync_scope()

        # ── Rozmiar z zawartości, potem pokazanie (bez migotania) ───────────
        dlg.update_idletasks()
        dlg.geometry(f"{max(760, dlg.winfo_reqwidth())}x{dlg.winfo_reqheight()}")
        dlg.minsize(700, 500)
        dlg.deiconify()
        dlg.grab_set()
        dlg.lift()
        dlg.focus_set()

    def _sek_status(self, text, color=None):
        if hasattr(self, "lbl_sek_status"):
            self.lbl_sek_status.config(text=text, fg=color or FG_GRAY)

    def _sek_sync_scope(self):
        """Pole „Skrypt" aktywne tylko dla zakresu „skrypt"."""
        state = "normal" if self._sek_zakres.get() == _tr("skrypt") else "disabled"
        self._sek_skrypt.config(state=state)

    def _sek_clear(self):
        """Czyści formularz i odznacza listę."""
        for w in (self._sek_nazwa, self._sek_wartosc, self._sek_opis):
            w.delete(0, "end")
        self._sek_skrypt.set("")
        self._sek_zakres.set(_tr("global"))
        self._sek_sync_scope()
        for it in self.sek_tree.selection():
            self.sek_tree.selection_remove(it)

    def _sek_refresh(self):
        """Odświeża listę sekretów."""
        for iid in self.sek_tree.get_children(""):
            self.sek_tree.delete(iid)
        for rec in self._secrets.sekrety:
            self.sek_tree.insert("", "end", iid=rec["id"], text="  " + rec["nazwa"],
                                 values=(rec["zakres"], rec["skrypt"] or "—",
                                         rec["opis"] or "—", rec["zmieniony"]))

    def _sek_select(self, event=None):
        """Wypełnia formularz danymi wybranego sekretu (bez wartości)."""
        sel = self.sek_tree.selection()
        if not sel:
            return
        rec = self._secrets.find(sel[0])
        if not rec:
            return
        self._sek_nazwa.delete(0, "end")
        self._sek_nazwa.insert(0, rec["nazwa"])
        self._sek_zakres.set(_tr(rec["zakres"]))
        self._sek_skrypt.set(rec["skrypt"])
        self._sek_opis.delete(0, "end")
        self._sek_opis.insert(0, rec["opis"])
        self._sek_wartosc.delete(0, "end")
        self._sek_sync_scope()

    def _sek_save(self):
        """Dodaje/aktualizuje sekret na podstawie formularza."""
        ok, msg = self._secrets.set(
            self._sek_nazwa.get().strip(),
            self._sek_wartosc.get(),
            zakres=self._cb_canon(self._sek_zakres.get(), ("global", "skrypt")),
            skrypt=self._sek_skrypt.get().strip(),
            opis=self._sek_opis.get().strip())
        if ok:
            self._sek_refresh()
            self._sek_clear()
        self._sek_status(_tr(msg), "#6dde84" if ok else "#e07070")

    def _sek_delete(self):
        """Usuwa wybrany sekret."""
        sel = self.sek_tree.selection()
        if not sel:
            self._sek_status(_tr("Zaznacz sekret do usunięcia."), "#f0c050")
            return
        if not messagebox.askyesno(_tr("Menedżer sekretów"),
                                   _tr("Usunąć wybrany sekret?")):
            return
        self._secrets.delete(sel[0])
        self._sek_refresh()
        self._sek_clear()
        self._sek_status(_tr("Sekret usunięty."), "#6dde84")

    def _sek_reveal(self):
        """Pokazuje odszyfrowaną wartość wybranego sekretu."""
        sel = self.sek_tree.selection()
        if not sel:
            self._sek_status(_tr("Zaznacz sekret do podglądu."), "#f0c050")
            return
        val = self._secrets.get_value(sel[0])
        if val is None:
            self._sek_status(_tr("Nie można odszyfrować wartości."), "#e07070")
            return
        messagebox.showinfo(_tr("Wartość sekretu"), val)

    def _sek_copy(self):
        """Kopiuje odszyfrowaną wartość wybranego sekretu do schowka."""
        sel = self.sek_tree.selection()
        if not sel:
            self._sek_status(_tr("Zaznacz sekret do skopiowania."), "#f0c050")
            return
        val = self._secrets.get_value(sel[0])
        if val is None:
            self._sek_status(_tr("Nie można odszyfrować wartości."), "#e07070")
            return
        self.clipboard_clear()
        self.clipboard_append(val)
        self._sek_status(_tr("Wartość skopiowana do schowka."), "#6dde84")

    def _menu_o_programie(self):
        """Okno „O programie" — informacje o aplikacji i autorze."""
        dlg = _popup(self)
        dlg.withdraw()                    # budowa bez migotania, pokazanie na końcu
        dlg.title(_tr("O programie"))
        dlg.configure(bg=BG_DARK)

        # ── Baner nagłówka ──────────────────────────────────────────────────
        naglowek = tk.Frame(dlg, bg=BG_PANEL)
        naglowek.pack(fill="x")
        baner = tk.Frame(naglowek, bg=BG_PANEL)
        baner.pack(pady=(18, 16))
        # Ikona aplikacji po lewej stronie banera.
        _icon_png = APP_DIR / "codemate.png"
        if _icon_png.exists():
            try:
                _img = tk.PhotoImage(file=str(_icon_png))
                _img = _img.subsample(8, 8)      # 500 px → ~62 px
                dlg._banner_icon = _img          # referencja — bez niej GC usunie obraz
                tk.Label(baner, image=_img, bg=BG_PANEL).pack(side="left", padx=(28, 16))
            except Exception:
                pass
        baner_txt = tk.Frame(baner, bg=BG_PANEL)
        baner_txt.pack(side="left")
        self._trw(tk.Label(baner_txt, text=_tr("CodeMate v4.0"),
                 font=FONT_TITLE, bg=BG_PANEL, fg=ACCENT_BLUE, anchor="w"),
             "CodeMate v4.0").pack(anchor="w")
        self._trw(tk.Label(baner_txt, text=_tr("Zaawansowana CodeMate i narzędzi developerskich"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY, anchor="w"),
                 "Zaawansowana CodeMate i narzędzi developerskich").pack(anchor="w", pady=(2, 0))
        tk.Frame(dlg, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Karta: informacje techniczne ────────────────────────────────────
        body = tk.Frame(dlg, bg=BG_DARK)
        body.pack(fill="x", padx=18, pady=(12, 0))
        karta1 = tk.Frame(body, bg=BG_PANEL)
        karta1.pack(fill="x")
        wnetrze1 = tk.Frame(karta1, bg=BG_PANEL)
        wnetrze1.pack(fill="x", padx=14, pady=10)
        for ln in ("Wersja:    4.0",
                   "Platforma: Python 3 / Tkinter",
                   "Kodowanie: UTF-8",
                   "Moduły: Info · Diagnostyka · Łączenie · Testy · Naprawa · Kreator Pluginów"):
            self._trw(tk.Label(wnetrze1, text=_tr(ln), font=FONT_UI, bg=BG_PANEL,
                     fg=FG_WHITE, anchor="w", justify="left"), ln).pack(anchor="w", pady=1)

        # ── Karta: autor ────────────────────────────────────────────────────
        karta2 = tk.Frame(body, bg=BG_PANEL)
        karta2.pack(fill="x", pady=(10, 0))
        wnetrze2 = tk.Frame(karta2, bg=BG_PANEL)
        wnetrze2.pack(fill="x", padx=14, pady=10)
        self._trw(tk.Label(wnetrze2, text=_tr("Autor:"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE, anchor="w"), "Autor:").pack(anchor="w", pady=(0, 4))
        for ln, fg in (("Autor:   Sebastian Januchowski", FG_WHITE),
                   ("Firma:   polsoft.ITS™ Group", FG_WHITE),
                   ("GitHub:  https://github.com/polsoft-IT", ACCENT_BLUE),
                   ("E-mail:  polsoft.its@mail.com", ACCENT_BLUE)):
            self._trw(tk.Label(wnetrze2, text=_tr(ln), font=FONT_UI, bg=BG_PANEL,
                     fg=fg, anchor="w"), ln).pack(anchor="w", pady=1)

        # ── Stopka: przycisk ────────────────────────────────────────────────
        tk.Frame(dlg, bg=BORDER_CLR, height=1).pack(fill="x", pady=(12, 0))
        stopka = tk.Frame(dlg, bg=BG_DARK)
        stopka.pack(fill="x", padx=18, pady=10)
        btn = self._trw(tk.Button(stopka, text=_tr("Zamknij"), font=FONT_UI,
                    bg=BTN_DARK, fg=FG_WHITE, activebackground=BTN_HOVER,
                    activeforeground=FG_WHITE, relief="flat", bd=0,
                    highlightthickness=0, padx=16, pady=5, cursor="hand2",
                    command=dlg.destroy), "Zamknij")
        btn.pack(side="right")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BTN_HOVER))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BTN_DARK))

        # ── Rozmiar z zawartości, potem pokazanie (bez migotania) ───────────
        dlg.update_idletasks()
        dlg.geometry(f"{max(560, dlg.winfo_reqwidth())}x{dlg.winfo_reqheight()}")
        dlg.resizable(False, False)
        dlg.deiconify()
        dlg.grab_set()
        dlg.lift()
        dlg.focus_set()

    # ── Nagłówek ──────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_PANEL, height=48)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        self.lbl_header_title = tk.Label(hdr, text=_t("header_title", ver=APP_VER),
                 font=FONT_TITLE, bg=BG_PANEL, fg=FG_WHITE)
        self.lbl_header_title.pack(side="left", padx=18)
        right = tk.Frame(hdr, bg=BG_PANEL)
        right.pack(side="right", padx=12)
        self.lbl_platform = tk.Label(right, text=_t("header_platform"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self.lbl_platform.pack(side="left", padx=6)
        self.lbl_count = tk.Label(right, text=_t("header_count", n=0),
                                  font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self.lbl_count.pack(side="left", padx=6)
        self.lbl_db_status = tk.Label(right, text="", font=("Consolas", 8),
                                      bg=BG_PANEL, fg="#6dde84")
        self.lbl_db_status.pack(side="left", padx=6)
        self.btn_lang = tk.Button(right, text=_t("lang_button"), font=FONT_BOLD,
                  bg=CHIP_BG, fg=CHIP_FG, relief="flat",
                  padx=8, pady=2, cursor="hand2", command=self._toggle_language)
        self.btn_lang.pack(side="left", padx=6)

    def _toggle_language(self) -> None:
        """Przełącza język interfejsu PL <-> EN i zapisuje wybór w konfiguracji."""
        new_lang = "en" if _UI_LANG == "pl" else "pl"
        _set_lang(new_lang)
        self._cfg["language"] = new_lang
        try:
            cfg_save(self._cfg)
        except Exception as e:
            logging.warning(f"Nie udało się zapisać języka interfejsu: {e}")
        self._retranslate_ui()

    # ── Motywy (jasny/ciemny + presety) ───────────────────────────────────────
    def _apply_theme(self, name: str, save: bool = True) -> None:
        """Przełącza motyw na żywo (bez restartu).

        Przypisuje nową paletę do globalnych stałych, przemapowuje kolory
        istniejących widżetów Tk, rekonfiguruje style ttk oraz tagi drzew tekstu,
        a na końcu utrwala wybór w konfiguracji.

        Args:
            name: Nazwa motywu (``ciemny`` / ``jasny`` / ``kontrastowy``).
            save: Czy zapisać wybór w pliku konfiguracji.
        """
        if name not in THEME_PRESETS:
            name = THEME_DEFAULT
        old_vals = getattr(self, "_theme_vals", theme_values(getattr(self, "_theme", THEME_DEFAULT)))
        appearance_cfg = dict(self._cfg)
        appearance_cfg.update(getattr(self, "_appearance_preview", {}))
        new_vals = _theme_values_with_custom(name, appearance_cfg)
        # Mapa: stara wartość koloru → nowa (pierwszeństwo pierwszego wystąpienia).
        cmap: Dict[str, str] = {}
        for key, old_v in old_vals.items():
            if key in CMAP_EXCLUDE or key in ("BG_TAB_ACT", "BG_TAB_INACT"):
                continue
            new_v = new_vals.get(key)
            if new_v and old_v != new_v and old_v not in cmap:
                cmap[old_v] = new_v

        self._theme = name
        self._theme_vals = new_vals
        for key, value in new_vals.items():
            globals()[key] = value
        _apply_hl_palette(name)

        # 1) Kolory okna i wszystkich widżetów Tk.
        try:
            self.configure(bg=BG_DARK)
        except Exception:
            pass
        self._recolor_widgets(self, cmap)
        self._apply_main_tab_colors()
        # 2) Style ttk (drzewa, comboboxy).
        self._style_ttk_theme()
        # 3) Tagi podświetlania składni w edytorach.
        self._reapply_highlight_tags()
        # 3b) Wygląd listy skryptów (kolory z motywu, gdy brak nadpisań).
        self._apply_list_appearance()
        # 4) Pasek menu — przebudowa z nową paletą.
        try:
            self._build_menu()
        except Exception as e:
            logging.warning(f"Nie udało się przebudować menu po zmianie motywu: {e}")
        # 5) Selektor motywu w zakładce Ustawienia.
        if hasattr(self, "_theme_combo"):
            try:
                self._theme_combo.set(_t("theme_" + name))
            except Exception:
                pass
        # 6) Utrwal wybór.
        if save:
            self._cfg["theme"] = name
            try:
                cfg_save(self._cfg)
            except Exception as e:
                logging.warning(f"Nie udało się zapisać motywu: {e}")

    def _apply_appearance_settings(self, config: Optional[Dict[str, str]] = None) -> None:
        global FONT_FAMILY, FONT_UI, FONT_BOLD, FONT_MONO, FONT_TITLE

        appearance_cfg = config or self._cfg
        old_vals = getattr(self, "_theme_vals", theme_values(self._theme))
        new_vals = _theme_values_with_custom(self._theme, appearance_cfg)
        cmap = {
            old_vals[key]: new_vals[key]
            for key in old_vals
            if key not in CMAP_EXCLUDE
            and key not in ("BG_TAB_ACT", "BG_TAB_INACT")
            and key in new_vals
            and old_vals[key] != new_vals[key]
        }
        self._theme_vals = new_vals
        for key, value in new_vals.items():
            globals()[key] = value

        family = appearance_cfg.get("font_family", "").strip() or "Consolas"
        try:
            size = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, int(appearance_cfg.get("font_size", "10"))))
        except (TypeError, ValueError):
            size = 10
        FONT_FAMILY = family
        FONT_UI = (family, 9)
        FONT_BOLD = (family, 9, "bold")
        FONT_MONO = (family, 10)
        FONT_TITLE = (family, 16, "bold")

        self._recolor_widgets(self, cmap)
        self._apply_main_tab_colors()
        self._style_ttk_theme()
        self._reapply_highlight_tags()
        self._apply_widget_font_family(self, family)
        self._apply_list_appearance()
        if hasattr(self, "_mouse"):
            self._mouse.FONT_FAMILY = family
            self._mouse._editor_font_size = size
            self._mouse._apply_zoom()

    def _apply_main_tab_colors(self) -> None:
        active_idx = getattr(self, "_main_active_idx", 0)
        for index, button in enumerate(getattr(self, "_main_btns", ())):
            button.configure(
                bg=BG_TAB_ACT if index == active_idx else BG_TAB_INACT,
                fg=FG_WHITE if index == active_idx else FG_GRAY)

    def _apply_widget_font_family(self, widget: tk.Widget, family: str) -> None:
        try:
            from tkinter import font as tkfont
            current_font = widget.cget("font")
            if current_font:
                actual = tkfont.Font(root=self, font=current_font).actual()
                widget.configure(font=(
                    family, actual["size"], actual["weight"], actual["slant"],
                    actual["underline"], actual["overstrike"]))
        except Exception:
            pass
        for child in widget.winfo_children():
            self._apply_widget_font_family(child, family)

    def _recolor_widgets(self, widget: tk.Widget, cmap: Dict[str, str]) -> None:
        """Rekurencyjnie podmienia kolory widżetów Tk wg mapy ``cmap``."""
        if cmap:
            try:
                keys = set(widget.keys())
            except Exception:
                keys = set()
            opts: Dict[str, str] = {}
            for opt in _WIDGET_COLOR_OPTS:
                if opt not in keys:
                    continue
                try:
                    cur = str(widget.cget(opt))
                except Exception:
                    continue
                new = cmap.get(cur)
                if new:
                    opts[opt] = new
            if opts:
                try:
                    widget.configure(**opts)
                except Exception:
                    pass
        if isinstance(widget, (ttk.Treeview, tk.Text)):
            self._retag_widget(widget)
        for child in widget.winfo_children():
            self._recolor_widgets(child, cmap)

    def _retag_widget(self, widget: tk.Widget) -> None:
        """Odświeża kolory tagów (Treeview/Text) dla aktywnego motywu."""
        vals = getattr(self, "_theme_vals", {})
        for tag, key in TAG_COLOR_KEYS.items():
            color = vals.get(key)
            if not color:
                continue
            kwargs: Dict[str, str] = {}
            if key in TAG_BG_KEYS:
                kwargs["background"] = color
            else:
                kwargs["foreground"] = color
            if tag == "errline":
                fg = vals.get("ERRLINE_FG")
                if fg:
                    kwargs["foreground"] = fg
            try:
                widget.tag_configure(tag, **kwargs)
            except Exception:
                pass

    def _style_ttk_theme(self) -> None:
        """Rekonfiguruje style ttk (drzewa, combobox) wg aktywnej palety."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Dark.TCombobox",
                        fieldbackground=BG_INPUT, background=BG_INPUT,
                        foreground=FG_WHITE, arrowcolor=FG_WHITE,
                        bordercolor=BORDER_CLR, lightcolor=BORDER_CLR,
                        darkcolor=BORDER_CLR)
        trees = (
            ("Dark.Treeview",   BG_ROW_ODD, FG_WHITE, BG_PANEL, FG_GRAY, 24),
            ("Adv.Treeview",    BG_ROW_ODD, FG_WHITE, BG_PANEL, FG_GRAY, 24),
            ("Perf.Treeview",   BG_ROW_ODD, FG_WHITE, BG_PANEL, FG_GRAY, 24),
            ("Fix.Treeview",    BG_ROW_ODD, FG_WHITE, BG_PANEL, FG_GRAY, 24),
            ("Pkg.Treeview",    BG_ROW_ODD, FG_WHITE, BG_PANEL, FG_GRAY, 22),
            ("VDrive.Treeview", BG_PANEL,   FG_WHITE, BG_INPUT, FG_GRAY, 26),
        )
        for name, bg, fg, hbg, hfg, rh in trees:
            style.configure(name, background=bg, foreground=fg,
                            fieldbackground=bg, rowheight=rh, font=FONT_UI)
            style.configure(name + ".Heading", background=hbg, foreground=hfg,
                            font=FONT_BOLD, relief="flat")
            style.map(name, background=[("selected", BG_ROW_SEL)],
                      foreground=[("selected", FG_WHITE)])

    def _reapply_highlight_tags(self) -> None:
        """Nakłada ponownie kolory podświetlania składni na edytory kodu."""
        hl = getattr(self, "_highlighter", None)
        if hl is None:
            return
        for w in (getattr(self, "text_kod", None), getattr(self, "edytor_text", None)):
            if w is None:
                continue
            for token, color in _HL_COLORS.items():
                try:
                    w.tag_configure(hl._tag(token), foreground=color)
                except Exception:
                    pass

    def _on_theme_combo(self, _event: Any = None) -> None:
        """Obsługuje wybór motywu w polu combobox zakładki Ustawienia."""
        label = self._theme_combo.get()
        for name in THEME_ORDER:
            if _t("theme_" + name) == label:
                if name != getattr(self, "_theme", THEME_DEFAULT):
                    self._apply_theme(name)
                break

    def _trw(self, widget: tk.Widget, pl_text: str) -> tk.Widget:
        """Rejestruje widżet do tłumaczenia na żywo i zwraca go (do łańcuchowania).

        Widżet należy utworzyć z tekstem ``_tr(pl_text)``; przy zmianie języka
        ``_retranslate_ui`` ustawia tekst ponownie na ``_tr(pl_text)``.
        """
        self._i18n_live.append((widget, pl_text))
        return widget

    def _trh(self, tree: Any, column: str, pl_text: str) -> Any:
        """Ustawia nagłówek kolumny Treeview z tłumaczeniem i rejestruje go."""
        tree.heading(column, text=_tr(pl_text))
        self._i18n_headings.append((tree, column, pl_text))
        return tree

    def _cb_canon(self, display: str, canon_seq) -> str:
        """Zwraca kanoniczną wartość PL odpowiadającą wyświetlanej (tłumaczonej)."""
        for c in canon_seq:
            if _tr(c) == display:
                return c
        return display

    def _trc(self, combobox: Any, canon_seq, var: Any = None) -> Any:
        """Combobox z kanonicznymi wartościami PL wyświetlanymi tłumaczonymi.

        Zapisuje (combobox, canon_seq, var) w _i18n_combos; _retranslate_ui
        odświeża values i bieżący wybór po zmianie języka.
        """
        canon_seq = tuple(canon_seq)
        self._i18n_combos.append((combobox, canon_seq, var))
        combobox.configure(values=[_tr(c) for c in canon_seq])
        cur = var.get() if var is not None else combobox.get()
        canon = self._cb_canon(cur, canon_seq)
        disp = _tr(canon)
        if var is not None:
            var.set(disp)
        elif combobox.get() != disp:
            combobox.set(disp)
        return combobox

    def _retranslate_ui(self) -> None:
        """Odświeża etykiety powłoki (tytuł, nagłówek, nawigacja) po zmianie języka."""
        self.title(_t("app_title", ver=APP_VER))
        if hasattr(self, "lbl_header_title"):
            self.lbl_header_title.configure(text=_t("header_title", ver=APP_VER))
        if hasattr(self, "lbl_platform"):
            self.lbl_platform.configure(text=_t("header_platform"))
        if hasattr(self, "lbl_count"):
            self.lbl_count.configure(text=_t("header_count", n=len(self.skrypty)))
        if hasattr(self, "btn_lang"):
            self.btn_lang.configure(text=_t("lang_button"))
        for btn, key in zip(getattr(self, "_main_btns", []),
                            getattr(self, "_main_tab_keys", [])):
            btn.configure(text=_t(key))
        # Etykiety zakładki Ustawienia (śledzone jako (widget, klucz i18n)).
        for widget, key in getattr(self, "_ust_i18n", []):
            try:
                widget.configure(text=_t(key))
            except Exception:
                pass
        if hasattr(self, "_ust_lbl_cfgfile"):
            self._ust_lbl_cfgfile.configure(text=_t("ust_cfg_file", file=CFG_FILE))
        if hasattr(self, "_ust_lbl_heading"):
            self._ust_lbl_heading.configure(text=_t("ust_header"))
        # Selektor motywu — przetłumacz etykiety opcji.
        if hasattr(self, "_theme_combo"):
            try:
                self._theme_combo.configure(
                    values=[_t("theme_" + n) for n in THEME_ORDER])
                self._theme_combo.set(_t("theme_" + self._theme))
            except Exception:
                pass
        if hasattr(self, "_git_notebook"):
            for index, label in enumerate(("Zmiany", "Historia")):
                try:
                    self._git_notebook.tab(index, text=_tr(label))
                except Exception:
                    pass
        # Treść zakładek: rejestr (widget, tekst PL) tłumaczony przez _tr().
        for widget, pl_text in getattr(self, "_i18n_live", []):
            try:
                widget.configure(text=_tr(pl_text))
            except Exception:
                pass
        if hasattr(self, "_vdrive_tool_win"):
            try:
                self._vdrive_refresh_localized_options()
            except Exception:
                pass
        if hasattr(self, "_vdrive_status_source"):
            self._vdrive_status_lbl.configure(text=_tr(self._vdrive_status_source))
        if getattr(self, "_vdrive_create_status_source", None):
            self._vdrive_create_status.config(
                text=_tr(self._vdrive_create_status_source).format(
                    **self._vdrive_create_status_args))
        if hasattr(self, "_vdrive_tree"):
            self._vdrive_rebuild_tree()
            self._vdrive_rebuild_icons()
            if self._vdrive_tree.selection():
                self._vdrive_on_tree_select()
        # Nagłówki kolumn Treeview (rejestr _i18n_headings).
        for tree, column, pl_text in getattr(self, "_i18n_headings", []):
            try:
                tree.heading(column, text=_tr(pl_text))
            except Exception:
                pass
        for cb, canon_seq, var in getattr(self, "_i18n_combos", []):
            try:
                cb.configure(values=[_tr(c) for c in canon_seq])
                cur = var.get() if var is not None else cb.get()
                canon = self._cb_canon(cur, canon_seq)
                disp = _tr(canon)
                if var is not None:
                    var.set(disp)
                else:
                    cb.set(disp)
            except Exception:
                pass
        # Menu nie da się edytować punktowo — przebuduj cały pasek.
        try:
            self._build_menu()
        except Exception as e:
            logging.warning(f"Nie udało się przebudować menu po zmianie języka: {e}")
        self._update_minsize()

    # ══════════════════════════════════════════════════════════════════════════
    # GŁÓWNY PASEK ZAKŁADEK
    # ══════════════════════════════════════════════════════════════════════════
    def _build_main_tabs(self):
        self.main_tab_bar = tk.Frame(self, bg=BG_DARK)
        self.main_tab_bar.pack(fill="x", side="top", pady=(2, 0))
        self.main_tab_content = tk.Frame(self, bg=BG_DARK)
        self.main_tab_content.pack(fill="both", expand=True)

        main_tabs = [
            ("tab_skrypty",   self._show_skrypty),
            ("tab_szukaj",    self._show_szukaj),
            ("tab_moduly",    self._show_moduly),
            ("tab_baza",      self._show_db),
            ("tab_venv",      self._show_venv),
            ("tab_vdrive",    self._show_vdrive),
            ("tab_narzedzia", self._show_narzedzia),
            ("tab_terminal",  self._show_terminal),
            ("tab_runner",    self._show_runner),
            ("tab_git",       self._show_git),
            ("tab_plugins",   self._show_plugins),
            ("tab_ustawienia", self._show_ustawienia),
        ]
        self._main_btns = []
        self._main_active_idx = 0
        self._main_tab_keys = [key for key, _ in main_tabs]
        self._main_tab_cmds = {key: cmd for key, cmd in main_tabs}
        self._main_tab_builders = {
            "tab_szukaj": self._build_szukaj_frame,
            "tab_moduly": self._build_moduly_frame,
            "tab_baza": self._build_db_frame,
            "tab_venv": self._build_venv_frame,
            "tab_vdrive": self._build_vdrive_frame,
            "tab_narzedzia": self._build_narzedzia_frame,
            "tab_terminal": self._build_terminal_frame,
            "tab_runner": self._ensure_runner_frame,
            "tab_git": self._build_git_frame,
            "tab_plugins": self._build_plugins_frame,
            "tab_ustawienia": self._build_ustawienia_frame,
        }
        self._main_tabs_built = {"tab_skrypty"}
        self.main_frames = {}

        for i, (key, cmd) in enumerate(main_tabs):
            b = tk.Button(self.main_tab_bar, text=_t(key), font=FONT_UI,
                          bg=BG_TAB_ACT if i == 0 else BG_TAB_INACT,
                          fg=FG_WHITE    if i == 0 else FG_GRAY,
                          relief="flat", padx=10, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i, c=cmd: self._sel_main(i, c))
            b.pack(side="left")
            self._main_btns.append(b)

        # Rejestr widżetów tłumaczonych na żywo: (widżet, polski tekst źródłowy).
        # Wypełniany przez _trw() przy budowie zakładek; odświeżany w _retranslate_ui.
        self._i18n_live: List[Tuple[tk.Widget, str]] = []
        # Rejestr nagłówków drzew (Treeview): (drzewo, kolumna, polski tekst).
        self._i18n_headings: List[Tuple[Any, str, str]] = []
        # Comboboxy z kanonicznymi wartościami: (widget, canon_seq, StringVar|None)
        self._i18n_combos: List[Tuple[Any, tuple, Any]] = []
        self._build_skrypty_frame()
        self._show_skrypty()

    def _sel_main(self, idx, cmd):
        self._main_active_idx = idx
        key = self._main_tab_keys[idx]
        builder = self._main_tab_builders.get(key)
        if builder and key not in self._main_tabs_built:
            builder()
            self._main_tabs_built.add(key)
        for i, b in enumerate(self._main_btns):
            b.configure(bg=BG_TAB_ACT if i == idx else BG_TAB_INACT,
                        fg=FG_WHITE    if i == idx else FG_GRAY)
        for f in self.main_frames.values():
            f.pack_forget()
        cmd()
        self._update_minsize()

    def _update_minsize(self):
        """Podnosi minimalny rozmiar okna do wymaganej wielkości widocznej treści.

        Mierzy ``winfo_reqwidth/reqheight`` w **bieżącym** języku — tanio,
        bez przełączania języka. ``_min_w/_min_h`` trzymają maksimum, więc
        raz zmierzony polski (najszerszy) wymiar zostaje na zawsze.
        """
        if getattr(self, "_in_minsize", False):
            return
        self._in_minsize = True
        try:
            self.update_idletasks()
            req_w = max(self.winfo_reqwidth(), 700)
            req_h = max(self.winfo_reqheight(), 500)
            mw = max(getattr(self, "_min_w", 0), req_w)
            mh = max(getattr(self, "_min_h", 0), req_h)
            # Nie wymagaj więcej, niż mieści się na ekranie — inaczej okno
            # wychodzi poza pulpit i nie da się go zmniejszyć.
            screen_w = max(self.winfo_screenwidth() - 80, 640)
            screen_h = max(self.winfo_screenheight() - 120, 400)
            mw, mh = min(mw, screen_w), min(mh, screen_h)
            self._min_w, self._min_h = mw, mh
            self.minsize(mw, mh)
            if self.winfo_width() < mw or self.winfo_height() < mh:
                self.geometry(f"{mw}x{mh}")
            # Okno większe niż ekran — zmniejsz do pulpitu.
            if self.winfo_width() > screen_w or self.winfo_height() > screen_h:
                self.geometry(
                    f"{min(self.winfo_width(), screen_w)}x"
                    f"{min(self.winfo_height(), screen_h)}")
        except Exception:
            pass
        finally:
            self._in_minsize = False

    def _update_minsize_boot_pl(self):
        """Jednorazowy pomiar minsize po polsku — wołany w __init__
        przed mainloop, więc zmiana języka na moment jest niewidoczna."""
        if _UI_LANG == "pl":
            self._update_minsize()
            return
        cur = _UI_LANG
        self._in_minsize = True
        try:
            _set_lang("pl")
            self._retranslate_ui()
            self.update_idletasks()
            req_w = max(self.winfo_reqwidth(), 700)
            req_h = max(self.winfo_reqheight(), 500)
            self._min_w = max(getattr(self, "_min_w", 0), req_w)
            self._min_h = max(getattr(self, "_min_h", 0), req_h)
            # Ogranicz do rozmiaru pulpitu (patrz _update_minsize).
            self._min_w = min(self._min_w, max(self.winfo_screenwidth() - 80, 640))
            self._min_h = min(self._min_h, max(self.winfo_screenheight() - 120, 400))
            self.minsize(self._min_w, self._min_h)
        except Exception:
            pass
        finally:
            try:
                _set_lang(cur)
                self._retranslate_ui()
            except Exception:
                pass
            self._in_minsize = False

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA SKRYPTY (poziom 1) — zawiera pod-zakładki
    # ══════════════════════════════════════════════════════════════════════════
    def _build_skrypty_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["skrypty"] = outer

        sub_bar = tk.Frame(outer, bg=BG_PANEL)
        sub_bar.pack(fill="x", side="top")
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        self.sub_content = tk.Frame(outer, bg=BG_DARK)
        self.sub_content.pack(fill="both", expand=True)

        self._sub_btns = []
        self.sub_frames = {}

        sub_tabs = [
            ("+ Nowy skrypt",    self._show_sub_dodaj),
            ("Lista skryptów",   self._show_sub_lista),
            ("Edytor skryptów",  self._show_sub_edytor),
            ("📦 Szablony",      self._show_sub_szablony),
            ("📚 Snippety",      self._show_sub_snippety),
            ("📊 Statystyki",    self._show_sub_statystyki),
            ("⚙ Zaawansowane",  self._show_sub_zaawansowane),
            ("▶ Runner",        self._show_sub_runner),
            ("🗑 Kosz",         self._show_sub_kosz),
        ]
        for i, (label, cmd) in enumerate(sub_tabs):
            b = self._trw(tk.Button(sub_bar, text=_tr(label), font=FONT_UI,
                          bg=BG_SUBTAB_ACT if i == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if i == 0 else FG_GRAY,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i, c=cmd: self._sel_sub(i, c)), label)
            b.pack(side="left")
            self._sub_btns.append(b)
        self._sub_tab_keys = [
            "dodaj", "lista", "edytor", "szablony", "snippety",
            "statystyki", "zaawansowane", "runner", "kosz",
        ]
        self._sub_tab_cmds = {key: cmd for key, (_, cmd) in
                              zip(self._sub_tab_keys, sub_tabs)}
        self._sub_tab_builders = {
            "edytor": self._build_sub_edytor,
            "szablony": self._build_sub_szablony,
            "snippety": self._build_sub_snippety,
            "statystyki": self._build_sub_statystyki,
            "zaawansowane": self._build_sub_zaawansowane,
            "runner": self._ensure_runner_frame,
            "kosz": self._build_sub_kosz,
        }
        self._sub_tabs_built = {"dodaj", "lista"}

        # Separator + Importuj (rozwijane menu) / Eksportuj
        tk.Frame(sub_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=4)

        # ── Importuj — rozwijane menu w dół z 3 opcjami ────────────────────────
        # Dropdown zbudowany z realnych widżetów (Frame + Button) — pokazywany
        # przez place(), więc renderuje się zawsze (niezależnie od popupów Tk).
        self._import_btn = self._trw(tk.Button(sub_bar, text=_tr("📥 Importuj  ▾"), font=FONT_UI,
                                     bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                                     padx=10, pady=5, cursor="hand2", bd=0,
                                     highlightthickness=0,
                                     activebackground=BTN_HOVER,
                                     activeforeground=FG_WHITE,
                                     command=self._toggle_import_menu), "📥 Importuj  ▾")
        self._import_btn.pack(side="left", padx=2)

        # Panel dropdown (ukryty aż do kliknięcia)
        self._import_dropdown = tk.Frame(self, bg=BORDER_CLR, bd=0,
                                         highlightthickness=1,
                                         highlightbackground=ACCENT_BLUE)
        self._import_dd_open = False
        for _lbl, _cmd in (
                ("📄  Importuj bazę (JSON)…",  self._lista_importuj),
                ("📂  Importuj plik skryptu…",  self._importuj_plik_skryptu),
                ("🗂  Importuj cały katalog…",  self._importuj_katalog)):
            self._trw(tk.Button(self._import_dropdown, text=_tr(_lbl), font=FONT_UI,
                      bg="#252840", fg="#c8d0f0", relief="flat", anchor="w",
                      padx=14, pady=7, cursor="hand2", bd=0,
                      highlightthickness=0,
                      activebackground=BTN_ACCENT,
                      activeforeground="#ffffff",
                      command=lambda c=_cmd: self._pick_import(c)), _lbl
                      ).pack(fill="x")

        # Zamknij dropdown kliknięciem w dowolnym innym miejscu
        self.bind_all("<Button-1>", self._maybe_close_import_menu, add="+")

        self._trw(tk.Button(sub_bar, text=_tr("📤 Eksportuj"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", bd=0, highlightthickness=0,
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._lista_eksportuj), "📤 Eksportuj").pack(side="left", padx=2)

        self._build_sub_dodaj()
        self._build_sub_lista()
        self._show_sub_dodaj()

    def _toggle_import_menu(self):
        """Pokazuje/ukrywa rozwijane menu importu pod przyciskiem."""
        if self._import_dd_open:
            self._close_import_menu()
            return
        btn = self._import_btn
        # Współrzędne względem okna głównego (rodzica panelu dropdown)
        x = btn.winfo_rootx() - self.winfo_rootx()
        y = btn.winfo_rooty() - self.winfo_rooty() + btn.winfo_height() + 1
        self._import_dropdown.place(x=x, y=y, width=max(btn.winfo_width(), 210))
        self._import_dropdown.lift()
        self._import_dd_open = True

    def _close_import_menu(self):
        """Ukrywa menu importu."""
        if self._import_dd_open:
            self._import_dropdown.place_forget()
            self._import_dd_open = False

    def _maybe_close_import_menu(self, event):
        """Zamyka menu przy kliknięciu poza nim (i poza przyciskiem)."""
        if not self._import_dd_open:
            return
        w = event.widget
        # Jeśli kliknięto w przycisk lub w panel menu — nie zamykaj tutaj
        parent = w
        while parent is not None:
            if parent is self._import_btn or parent is self._import_dropdown:
                return
            try:
                parent = parent.master
            except Exception:
                parent = None
        self._close_import_menu()

    def _pick_import(self, cmd):
        """Wybrano opcję z menu importu — zamknij menu i wykonaj akcję."""
        self._close_import_menu()
        try:
            cmd()
        except Exception as ex:
            messagebox.showerror(_tr("Błąd importu"), str(ex))

    def _nav_goto(self, target: str) -> bool:
        """Nawiguje do zakładki — API dla pluginów (``_nav_goto``).

        Format targetu: ``"<klucz zakładki głównej>"`` (np. ``"tab_runner"``)
        lub ``"<główna>:<podzakładka Skryptów>"`` (np. ``"tab_skrypty:statystyki"``).

        Args:
            target: Klucz zakładki z ``_main_tab_keys`` / ``_sub_tab_keys``.

        Returns:
            bool: True gdy target został rozpoznany.
        """
        main_key, _, sub_key = target.partition(":")
        if main_key not in getattr(self, "_main_tab_keys", []):
            return False
        idx = self._main_tab_keys.index(main_key)
        cmd = self._main_tab_cmds.get(main_key)
        if cmd is not None:
            self._sel_main(idx, cmd)
        if sub_key:
            if main_key != "tab_skrypty" or sub_key not in self._sub_tab_keys:
                return True
            sidx = self._sub_tab_keys.index(sub_key)
            scmd = self._sub_tab_cmds.get(sub_key)
            if scmd is not None:
                self._sel_sub(sidx, scmd)
        return True

    def _sel_sub(self, idx, cmd):
        key = self._sub_tab_keys[idx]
        builder = self._sub_tab_builders.get(key)
        if builder and key not in self._sub_tabs_built:
            builder()
            self._sub_tabs_built.add(key)
            if key == "edytor":
                self._attach_editor_highlighter()
        for i, b in enumerate(self._sub_btns):
            b.configure(bg=BG_SUBTAB_ACT if i == idx else BG_SUBTAB_INACT,
                        fg=FG_WHITE       if i == idx else FG_GRAY)
        for f in self.sub_frames.values():
            f.pack_forget()
        cmd()
        self._update_minsize()

    def _show_skrypty(self):
        self.main_frames["skrypty"].pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: + Dodaj Skrypt
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_dodaj(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["dodaj"] = frame

        # pasek narzędzi
        toolbar = tk.Frame(frame, bg=BG_PANEL, pady=7, padx=8)
        toolbar.pack(fill="x")

        def vsep():
            tk.Frame(toolbar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=8, pady=4)

        self._trw(tk.Button(toolbar, text=_tr("+ Nowy skrypt"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  activebackground="#3a7bc8", activeforeground=FG_WHITE,
                  command=self._wyczysc), "+ Nowy skrypt").pack(side="left")
        vsep()

        self._trw(tk.Label(toolbar, text=_tr("Nazwa:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Nazwa:").pack(side="left", padx=(0, 4))
        self.entry_nazwa = tk.Entry(toolbar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                    insertbackground=FG_WHITE, relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER_CLR,
                                    highlightcolor=ACCENT_BLUE, width=22)
        self.entry_nazwa.pack(side="left")
        vsep()

        self._trw(tk.Label(toolbar, text=_tr("Kategoria:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Kategoria:").pack(side="left", padx=(0, 4))
        self.var_kat = tk.StringVar(value="Python")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
                        fieldbackground=BG_INPUT, background=BG_INPUT,
                        foreground=FG_WHITE, arrowcolor=FG_WHITE,
                        bordercolor=BORDER_CLR, lightcolor=BORDER_CLR,
                        darkcolor=BORDER_CLR)
        ttk.Combobox(toolbar, textvariable=self.var_kat, values=CATEGORIES,
                     font=FONT_UI, state="readonly", style="Dark.TCombobox",
                     width=12).pack(side="left", padx=(0, 4))
        self._trw(tk.Button(toolbar, text=_tr("⚙ Auto"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=7, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE), "⚙ Auto").pack(side="left")
        vsep()

        self._trw(tk.Label(toolbar, text=_tr("Tagi:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Tagi:").pack(side="left", padx=(0, 4))
        self.entry_tagi = tk.Entry(toolbar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                   insertbackground=FG_WHITE, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER_CLR,
                                   highlightcolor=ACCENT_BLUE)
        self.entry_tagi.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # opis
        self.text_opis = tk.Text(frame, font=FONT_MONO, bg=BG_INPUT, fg=FG_GRAY,
                                  insertbackground=FG_WHITE, relief="flat",
                                  highlightthickness=1, highlightbackground=BORDER_CLR,
                                  highlightcolor=ACCENT_BLUE, height=4, wrap="word")
        self.text_opis.pack(fill="x", padx=8, pady=(6, 4))
        self.text_opis.insert("1.0", "Opis skryptu…")
        self.text_opis.bind("<FocusIn>",  self._opis_focus_in)
        self.text_opis.bind("<FocusOut>", self._opis_focus_out)

        # edytor kodu
        kod_frame = tk.Frame(frame, bg=BG_DARK)
        kod_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.line_nums = tk.Text(kod_frame, font=FONT_MONO, bg=BG_PANEL, fg=FG_GRAY,
                                  width=4, state="disabled", relief="flat",
                                  highlightthickness=0, bd=0)
        self.line_nums.pack(side="left", fill="y")

        code_scroll = tk.Scrollbar(kod_frame, orient="vertical", bg=BG_PANEL,
                                    troughcolor=BG_PANEL, width=10)
        code_scroll.pack(side="right", fill="y")

        self.text_kod = tk.Text(kod_frame, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                 insertbackground=FG_WHITE, relief="flat",
                                 highlightthickness=1, highlightbackground=BORDER_CLR,
                                 highlightcolor=ACCENT_BLUE, wrap="none",
                                 yscrollcommand=code_scroll.set, tabs="4c")
        self.text_kod.pack(side="left", fill="both", expand=True)
        code_scroll.config(command=self._sync_scroll)
        self.text_kod.bind("<KeyRelease>", self._update_line_nums)
        self.text_kod.bind("<MouseWheel>", self._on_mousewheel)
        self._update_line_nums()

        self._build_bottom_bar(frame)

    def _show_sub_dodaj(self):
        self.sub_frames["dodaj"].pack(fill="both", expand=True, padx=4, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: Lista skryptów
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_lista(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["lista"] = frame

        # pasek wyszukiwania
        search_bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        search_bar.pack(fill="x")
        self._trw(tk.Label(search_bar, text=_tr("🔍 Szukaj:"), font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY), "🔍 Szukaj:").pack(side="left", padx=(0, 4))
        self.entry_search = tk.Entry(search_bar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      insertbackground=FG_WHITE, relief="flat",
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      highlightcolor=ACCENT_BLUE, width=30)
        self.entry_search.pack(side="left")
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_lista())

        self._trw(tk.Button(search_bar, text=_tr("🗑 Usuń zaznaczony"), font=FONT_UI,
                  bg=BTN_DARK, fg="#e07070", relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._usun_skrypt), "🗑 Usuń zaznaczony").pack(side="right", padx=4)
        self._trw(tk.Button(search_bar, text=_tr("✏ Edytuj"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._edytuj_skrypt), "✏ Edytuj").pack(side="right", padx=4)
        self._trw(tk.Button(search_bar, text=_tr("📂 Otwórz"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._otworz_skrypt), "📂 Otwórz").pack(side="right", padx=4)

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # tabela — styl „ScriptList.Treeview" konfigurowany przez
        # _apply_list_appearance() (wygląd listy z Ustawień → Personalizacja)
        cols = ("Nazwa", "Kategoria", "Tagi", "Opis")

        tree_frame = tk.Frame(frame, bg=BG_DARK)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=6)

        vsb = tk.Scrollbar(tree_frame, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=10)
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style="ScriptList.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)

        self._trh(self.tree, "Nazwa",     "Nazwa")
        self._trh(self.tree, "Kategoria", "Kategoria")
        self._trh(self.tree, "Tagi",      "Tagi")
        self._trh(self.tree, "Opis",      "Opis")

        self.tree.column("Nazwa",     width=220, minwidth=120)
        self.tree.column("Kategoria", width=100, minwidth=80)
        self.tree.column("Tagi",      width=200, minwidth=100)
        self.tree.column("Opis",      width=400, minwidth=150)

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._edytuj_skrypt())
        self._apply_list_appearance()

        # podgląd kodu na dole listy
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x", padx=8)
        preview_frame = tk.Frame(frame, bg=BG_DARK)
        preview_frame.pack(fill="x", padx=8, pady=(4, 6))
        self._trw(tk.Label(preview_frame, text=_tr("Podgląd kodu:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Podgląd kodu:").pack(anchor="w")
        self.text_preview = tk.Text(preview_frame, font=FONT_MONO,
                                     bg=BG_INPUT, fg="#c8d0f0",
                                     relief="flat", height=7, state="disabled",
                                     highlightthickness=1,
                                     highlightbackground=BORDER_CLR)
        self.text_preview.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _show_sub_lista(self):
        self._refresh_lista()
        self.sub_frames["lista"].pack(fill="both", expand=True, padx=4, pady=4)

    def _show_sub_edytor(self):
        self.sub_frames["edytor"].pack(fill="both", expand=True, padx=4, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: Edytor skryptów
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_edytor(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["edytor"] = frame

        # nagłówek
        hdr = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("✏ Edytor skryptów — zaawansowany podgląd i edycja"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "✏ Edytor skryptów — zaawansowany podgląd i edycja").pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # LEWA: lista skryptów do wyboru
        left = tk.Frame(body, bg=BG_PANEL, width=240,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        self._trw(tk.Label(left, text=_tr("📋 Skrypty w bazie"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "📋 Skrypty w bazie").pack(anchor="w", padx=10, pady=(8, 2))

        ed_flt_var = tk.StringVar()
        flt_e = tk.Entry(left, textvariable=ed_flt_var, font=FONT_MONO,
                         bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE,
                         relief="flat", highlightthickness=1,
                         highlightbackground=BORDER_CLR, highlightcolor=ACCENT_BLUE)
        flt_e.pack(fill="x", padx=8, pady=(0, 4))

        sc_ed = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                             troughcolor=BG_PANEL, width=8)
        sc_ed.pack(side="right", fill="y", pady=2, padx=(0, 2))
        self.edytor_listbox = tk.Listbox(left, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                          selectmode="single", relief="flat",
                                          highlightthickness=0,
                                          selectbackground=BG_ROW_SEL,
                                          activestyle="none",
                                          yscrollcommand=sc_ed.set)
        sc_ed.config(command=self.edytor_listbox.yview)
        self.edytor_listbox.pack(fill="both", expand=True, padx=(8, 0), pady=2)
        self.edytor_listbox.bind("<<ListboxSelect>>", self._edytor_load_selected)

        btn_ed = tk.Frame(left, bg=BG_PANEL)
        btn_ed.pack(fill="x", padx=6, pady=(4, 6))
        self._trw(tk.Button(btn_ed, text=_tr("▶ Uruchom"), font=FONT_UI,
                  bg=BTN_OK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_OK_HOVER,
                  command=self._edytor_run), "▶ Uruchom").pack(fill="x", padx=2, pady=2)
        self._trw(tk.Button(btn_ed, text=_tr("🕘 Historia wersji"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._edytor_versions), "🕘 Historia wersji").pack(fill="x", padx=2, pady=2)
        self._trw(tk.Button(btn_ed, text=_tr("📦 Eksportuj do .exe"), font=FONT_UI,
              bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
              cursor="hand2", activebackground=BTN_HOVER,
              command=self._edytor_export_exe), "📦 Eksportuj do .exe").pack(fill="x", padx=2, pady=2)
        self._trw(tk.Button(btn_ed, text=_tr("🔍 Sprawdź kod (lint)"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._edytor_lint), "🔍 Sprawdź kod (lint)").pack(fill="x", padx=2, pady=2)
        self._trw(tk.Button(btn_ed, text=_tr("💾 Zapisz zmiany"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._edytor_save), "💾 Zapisz zmiany").pack(fill="x", padx=2, pady=2)
        self._trw(tk.Button(btn_ed, text=_tr("📋 Kopiuj kod"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._edytor_copy), "📋 Kopiuj kod").pack(fill="x", padx=2, pady=2)
        self._trw(tk.Button(btn_ed, text=_tr("🗑 Usuń skrypt"), font=FONT_UI,
                  bg=BTN_ERR, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_ERR_HOVER,
                  command=self._edytor_delete), "🗑 Usuń skrypt").pack(fill="x", padx=2, pady=2)

        def _edytor_refresh(*_):
            # Powiąż wiersze z ID, bo nazwy skryptów nie muszą być unikalne.
            if not hasattr(self, "_edytor_current_idx"):
                self._edytor_current_idx = None
            current_id = None
            current_idx = getattr(self, "_edytor_current_idx", None)
            if current_idx is not None and current_idx < len(self.skrypty):
                current_id = self.skrypty[current_idx].get("id")

            q = ed_flt_var.get().strip().casefold()
            self.edytor_listbox.delete(0, "end")
            visible_ids = []
            selected_row = None
            for s in self.skrypty:
                if s.get("usuniety"):
                    continue
                n = str(s.get("nazwa", ""))
                if q and q not in n.casefold():
                    continue
                row = self.edytor_listbox.size()
                self.edytor_listbox.insert("end", n)
                visible_ids.append(s.get("id"))
                if current_id is not None and s.get("id") == current_id:
                    selected_row = row
            self._edytor_visible_ids = visible_ids
            if selected_row is not None:
                self.edytor_listbox.selection_set(selected_row)
                self.edytor_listbox.see(selected_row)
        ed_flt_var.trace_add("write", _edytor_refresh)
        self._edytor_refresh = _edytor_refresh

        # PRAWA: edytor kodu
        right = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="both", expand=True)

        info_bar = tk.Frame(right, bg=BG_PANEL, pady=4, padx=8)
        info_bar.pack(fill="x")
        self.edytor_lbl_nazwa = self._trw(tk.Label(info_bar, text=_tr("— brak wybranego skryptu —"),
                                          font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "— brak wybranego skryptu —")
        self.edytor_lbl_nazwa.pack(side="left")
        self.edytor_lbl_info = tk.Label(info_bar, text="",
                                         font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self.edytor_lbl_info.pack(side="right")

        tk.Frame(right, bg=BORDER_CLR, height=1).pack(fill="x")

        ed_kod_frame = tk.Frame(right, bg=BG_DARK)
        ed_kod_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.edytor_line_nums = tk.Text(ed_kod_frame, font=FONT_MONO, bg=BG_PANEL, fg=FG_GRAY,
                                         width=4, state="disabled", relief="flat",
                                         highlightthickness=0, bd=0)
        self.edytor_line_nums.pack(side="left", fill="y")

        ed_sc = tk.Scrollbar(ed_kod_frame, orient="vertical", bg=BG_PANEL,
                              troughcolor=BG_PANEL, width=10)
        ed_sc.pack(side="right", fill="y")

        self.edytor_text = tk.Text(ed_kod_frame, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                    insertbackground=FG_WHITE, relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER_CLR,
                                    highlightcolor=ACCENT_BLUE, wrap="none",
                                    yscrollcommand=ed_sc.set, tabs="4c")
        self.edytor_text.pack(side="left", fill="both", expand=True)
        ed_sc.config(command=lambda *a: (self.edytor_text.yview(*a), self._edytor_update_lines()))

        self.edytor_text.bind("<KeyRelease>", self._edytor_update_lines)
        self.edytor_text.bind("<MouseWheel>", lambda e: self._edytor_update_lines())
        self.edytor_text.bind("<KeyRelease>", self._edytor_update_cursor_pos)
        self.edytor_text.bind("<ButtonRelease-1>", self._edytor_update_cursor_pos)
        self.edytor_text.bind("<Return>", self._edytor_auto_indent)
        self.edytor_text.bind("<Control-f>", self._edytor_show_search)
        self.edytor_text.bind("<Control-g>", self._edytor_goto_line)
        self.edytor_text.bind("<Control-d>", self._edytor_format_code)
        self.edytor_text.bind("<KeyRelease>", self._edytor_bracket_match)

        # Skróty klawiszowe do nawigacji
        self.edytor_text.bind("<Control-Home>", lambda e: (self.edytor_text.mark_set("insert", "1.0"), self.edytor_text.see("1.0")))
        self.edytor_text.bind("<Control-End>", lambda e: (self.edytor_text.mark_set("insert", "end"), self.edytor_text.see("end")))
        self.edytor_text.bind("<Control-Up>", lambda e: self._edytor_scroll_page(-1))
        self.edytor_text.bind("<Control-Down>", lambda e: self._edytor_scroll_page(1))
        self.edytor_text.bind("<Control-Left>", lambda e: self._edytor_move_word(-1))
        self.edytor_text.bind("<Control-Right>", lambda e: self._edytor_move_word(1))

        self._edytor_current_idx = None
        _edytor_refresh()

        # ── Panel wyników lintu (ukryty do pierwszego sprawdzenia) ─────────────
        self.edytor_text.tag_configure("lint_err", background="#4a2430")
        self.edytor_text.tag_configure("lint_warn", background="#3f3a24")
        panel = tk.Frame(right, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        self._lint_panel = panel
        lhdr = tk.Frame(panel, bg=BG_PANEL)
        lhdr.pack(fill="x")
        self._trw(tk.Label(lhdr, text=_tr("🔍 Wyniki lintu"), font=FONT_BOLD,
                  bg=BG_PANEL, fg=ACCENT_BLUE), "🔍 Wyniki lintu").pack(side="left", padx=8, pady=4)
        self._lint_status_lbl = tk.Label(lhdr, text="", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self._lint_status_lbl.pack(side="left", padx=6)
        self._trw(tk.Button(lhdr, text=_tr("✖ Zamknij"), font=FONT_UI, bg=BTN_DARK,
                  fg=FG_WHITE, relief="flat", padx=8, pady=2, cursor="hand2",
                  activebackground=BTN_HOVER, command=self._lint_hide),
                  "✖ Zamknij").pack(side="right", padx=6, pady=3)
        lbody = tk.Frame(panel, bg=BG_PANEL)
        lbody.pack(fill="x", padx=6, pady=(0, 6))
        lsc = tk.Scrollbar(lbody, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=8)
        lsc.pack(side="right", fill="y")
        self._lint_tree = ttk.Treeview(lbody, columns=("line", "code", "severity", "message"),
                                       show="headings", height=5, yscrollcommand=lsc.set)
        lsc.config(command=self._lint_tree.yview)
        self._lint_tree.column("line", width=60, anchor="e")
        self._lint_tree.column("code", width=80, anchor="w")
        self._lint_tree.column("severity", width=100, anchor="w")
        self._lint_tree.column("message", width=520, anchor="w")
        self._trh(self._lint_tree, "line", "Linia")
        self._trh(self._lint_tree, "code", "Kod")
        self._trh(self._lint_tree, "severity", "Poziom")
        self._trh(self._lint_tree, "message", "Opis")
        self._lint_tree.pack(side="left", fill="both", expand=True)
        self._lint_tree.bind("<Double-1>", self._lint_goto)
        self._lint_tree.bind("<Return>", self._lint_goto)

        # Status bar
        status_bar = tk.Frame(right, bg=BG_PANEL, height=24)
        status_bar.pack(fill="x", padx=6, pady=(0, 6))
        self._edytor_status_bar = status_bar
        self.edytor_status_pos = self._trw(tk.Label(status_bar, text=_tr("Ln 1, Col 1"), font=FONT_UI,
                                          bg=BG_PANEL, fg=FG_GRAY, anchor="w"), "Ln 1, Col 1")
        self.edytor_status_pos.pack(side="left", padx=4)
        self.edytor_status_stats = self._trw(tk.Label(status_bar, text=_tr("0 znaków, 0 słów"),
                                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY, anchor="e"), "0 znaków, 0 słów")
        self.edytor_status_stats.pack(side="right", padx=4)

    def _edytor_update_lines(self, _e=None):
        self.edytor_line_nums.config(state="normal")
        self.edytor_line_nums.delete("1.0", "end")
        n = int(self.edytor_text.index("end-1c").split(".")[0])
        self.edytor_line_nums.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self.edytor_line_nums.config(state="disabled")
        lines = int(self.edytor_text.index("end-1c").split(".")[0])
        self.edytor_lbl_info.config(text=f"Linii: {lines}")
        self._edytor_update_cursor_pos()

    def _edytor_update_cursor_pos(self, _e=None):
        """Aktualizuje pozycję kursora w status barze."""
        try:
            idx = self.edytor_text.index("insert")
            line, col = idx.split(".")
            self.edytor_status_pos.config(text=f"Ln {line}, Col {col}")

            # Statystyki
            text = self.edytor_text.get("1.0", "end-1c")
            chars = len(text)
            words = len(text.split()) if text.strip() else 0
            self.edytor_status_stats.config(text=f"{chars} znaków, {words} słów")
        except Exception:
            pass

    def _edytor_auto_indent(self, event):
        """Automatyczne wcięcie przy wciśnięciu Enter."""
        # Gdy otwarte podpowiedzi — Enter zatwierdza wybór (obsługuje AutoCompleter).
        if getattr(self, "_autocomplete", None) is not None and self._autocomplete.is_open():
            return None
        try:
            line = self.edytor_text.get("insert linestart", "insert lineend")
            indent = len(line) - len(line.lstrip())
            if line.strip().endswith(":"):
                indent += 4  # dodatkowe wcięcie po dwukropku (Python)
            self.edytor_text.insert("insert", "\n" + " " * indent)
            return "break"
        except Exception:
            return None

    def _edytor_show_search(self, event):
        """Pokazuje dialog wyszukiwania."""
        from tkinter import simpledialog
        search_term = simpledialog.askstring(_tr("Szukaj"), _tr("Wyszukaj:"))
        if search_term:
            idx = self.edytor_text.search(search_term, "1.0", stopindex="end")
            if idx:
                self.edytor_text.tag_remove("sel", "1.0", "end")
                end_idx = f"{idx}+{len(search_term)}c"
                self.edytor_text.tag_add("sel", idx, end_idx)
                self.edytor_text.see(idx)
                self.edytor_text.focus_set()
            else:
                messagebox.showinfo(_tr("Szukaj"), _tr("Nie znaleziono"))
        return "break"

    def _edytor_goto_line(self, event):
        """Przechodzi do wskazanej linii."""
        from tkinter import simpledialog
        line_num = simpledialog.askinteger(_tr("Przejdź do linii"), _tr("Numer linii:"))
        if line_num and line_num > 0:
            try:
                self.edytor_text.see(f"{line_num}.0")
                self.edytor_text.mark_set("insert", f"{line_num}.0")
                self.edytor_text.focus_set()
            except Exception:
                messagebox.showerror(_tr("Błąd"), _tr("Nieprawidłowy numer linii"))
        return "break"

    def _edytor_format_code(self, event):
        """Formatuje kod (jeśli dostępny autopep8)."""
        try:
            import autopep8
            code = self.edytor_text.get("1.0", "end-1c")
            formatted = autopep8.fix_code(code)
            self.edytor_text.delete("1.0", "end")
            self.edytor_text.insert("1.0", formatted)
            self._edytor_update_lines()
            messagebox.showinfo(_tr("Formatowanie"), _tr("Kód sformatowany"))
        except ImportError:
            messagebox.showinfo(_tr("Formatowanie"), _tr("autopep8 nie jest zainstalowany"))
        except Exception as e:
            messagebox.showerror(_tr("Błąd"), f"Nie udało się sformatować: {e}")
        return "break"

    def _edytor_bracket_match(self, event):
        """Podświetla pasujący nawias."""
        try:
            idx = self.edytor_text.index("insert")
            char = self.edytor_text.get(f"{idx}-1c", idx)

            brackets = {'(': ')', '[': ']', '{': '}', ')': '(', ']': '[', '}': '{'}
            if char in brackets:
                matching = brackets[char]
                # Szukaj pasującego nawiasu
                if char in '([{':
                    # Szukaj do przodu
                    search_idx = self.edytor_text.search(matching, idx, stopindex="end")
                else:
                    # Szukaj do tyłu
                    search_idx = self.edytor_text.search(matching, f"{idx}-1c", stopindex="1.0", backwards=True)

                if search_idx:
                    # Usuń stare podświetlenie
                    self.edytor_text.tag_remove("bracket_match", "1.0", "end")
                    # Dodaj nowy tag podświetlenia
                    self.edytor_text.tag_config("bracket_match", background="#5a6b8a")
                    self.edytor_text.tag_add("bracket_match", f"{idx}-1c", idx)
                    self.edytor_text.tag_add("bracket_match", search_idx, f"{search_idx}+1c")
                    # Usuń po 1 sekundzie
                    self.after(1000, lambda: self.edytor_text.tag_remove("bracket_match", "1.0", "end"))
        except Exception:
            pass

    def _edytor_scroll_page(self, direction):
        """Przewija stronę w górę/dół."""
        self.edytor_text.yview_scroll(direction, "pages")

    def _edytor_move_word(self, direction):
        """Przesuwa kursor o słowo w lewo/prawo."""
        current = self.edytor_text.index("insert")
        if direction == -1:  # w lewo
            # Szukaj początku słowa
            new_pos = self.edytor_text.search(r"\S", f"{current}-1c", stopindex="1.0", backwards=True, regexp=True)
            if new_pos:
                self.edytor_text.mark_set("insert", new_pos)
        else:  # w prawo
            # Szukaj końca słowa
            new_pos = self.edytor_text.search(r"\s", current, stopindex="end", regexp=True)
            if new_pos:
                self.edytor_text.mark_set("insert", f"{new_pos}+1c")

    def _edytor_load_selected(self, event=None):
        sel = self.edytor_listbox.curselection()
        if not sel:
            return
        row = sel[0]
        visible_ids = getattr(self, "_edytor_visible_ids", [])
        if row >= len(visible_ids):
            return
        script_id = visible_ids[row]
        for i, s in enumerate(self.skrypty):
            if s.get("id") == script_id and not s.get("usuniety"):
                self._edytor_current_idx = i
                nazwa = str(s.get("nazwa", ""))
                self.edytor_lbl_nazwa.config(text=f"✏  {nazwa}  [{s.get('kategoria','')}]")
                self.edytor_text.delete("1.0", "end")
                self.edytor_text.insert("1.0", s.get("kod", ""))
                if hasattr(self, "_lint_panel"):
                    self._lint_clear_marks()
                self._edytor_update_lines()
                # Podświetl składnię w edytorze
                self._highlighter.highlight(self.edytor_text, s.get("kategoria", "Python"))
                return
        self._edytor_current_idx = None

    def _edytor_save(self) -> None:
        if self._edytor_current_idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz skrypt z listy."))
            return
        if self._edytor_current_idx >= len(self.skrypty):
            self._edytor_current_idx = None
            messagebox.showwarning(_tr("Nieaktualny wybór"), _tr("Wybierz skrypt ponownie z listy."))
            return
        sc = self.skrypty[self._edytor_current_idx]
        if sc.get("usuniety"):
            messagebox.showinfo(_tr("Kosz"), _tr("Ten skrypt jest w koszu — najpierw go przywróć."))
            return

        # ── Hook przed zapisem skryptu ─────────────────────────────────────────
        if self._plugin_manager:
            self._plugin_manager.trigger_hook("before_script_save", sc)

        new_kod = self.edytor_text.get("1.0", "end-1c")
        if new_kod != (sc.get("kod") or ""):
            sc_add_version(sc, autor="edytor")
        sc["kod"] = new_kod
        sc["checksum"] = kod_checksum(new_kod)
        sc["zmieniony"] = now_str()
        self._edytor_refresh()
        self._after_db_change()
        self._sync_form_from_record(sc)
        self._clear_errline()

        # ── Commit zmiany skryptu do Git ───────────────────────────────────────
        git = self._ensure_git()
        if git and git.is_available():
            try:
                git.commit_script_change(
                    script_id=sc.get("id"),
                    script_name=sc.get("nazwa"),
                    change_type="update"
                )
            except Exception as e:
                logging.warning(f"Git script commit failed: {e}")

        # ── Hook po zapisie skryptu ───────────────────────────────────────────
        if self._plugin_manager:
            self._plugin_manager.trigger_hook("after_script_save", sc)

        messagebox.showinfo(_tr("Zapisano"), _tr("Zmiany zapisane w bazie (poprzednia wersja w historii)."))

    def _sync_form_from_record(self, sc: Dict[str, Any]) -> None:
        """Odświeża formularz „Nowy skrypt” zawartością zapisanego rekordu."""
        try:
            self._editing_nazwa = sc.get("nazwa")
            if hasattr(self, "entry_nazwa"):
                self.entry_nazwa.delete(0, "end")
                self.entry_nazwa.insert(0, sc.get("nazwa", ""))
            if hasattr(self, "var_kat"):
                self.var_kat.set(sc.get("kategoria", "Python"))
            if hasattr(self, "entry_tagi"):
                self.entry_tagi.delete(0, "end")
                self.entry_tagi.insert(0, sc.get("tagi", ""))
            if hasattr(self, "text_opis"):
                self.text_opis.delete("1.0", "end")
                self.text_opis.insert("1.0", sc.get("opis") or "Opis skryptu…")
        except Exception:
            pass

    def _edytor_versions(self):
        """Okno historii wersji skryptu otwartego w edytorze (z diffem)."""
        if self._edytor_current_idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz skrypt z listy."))
            return
        sc = self.skrypty[self._edytor_current_idx]
        wersje = list(reversed(sc.get("wersje") or []))
        dlg = _popup(self)
        dlg.title(f"Historia wersji — {sc.get('nazwa')}")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("900x600")
        dlg.transient(self)

        left = tk.Frame(dlg, bg=BG_PANEL, width=260)
        left.pack(side="left", fill="y")
        lb = tk.Listbox(left, font=FONT_UI, bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                        selectbackground=BG_ROW_SEL, activestyle="none")
        lb.pack(fill="both", expand=True, padx=6, pady=6)
        lb.insert("end", f"{sc.get('zmieniony', '?'):<20}  (bieżąca)")
        for v in wersje:
            lb.insert("end", f"{v.get('ts', '?'):<20}  {v.get('autor', '')}")
        right = tk.Frame(dlg, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        txt = tk.Text(right, font=("Consolas", 9), bg="#14161f", fg="#c8d0f0",
                      relief="flat", wrap="none")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("add", foreground="#6dde84")
        txt.tag_configure("del", foreground="#e05c5c")
        txt.tag_configure("hdr", foreground="#89ddff")
        txt.config(state="disabled")

        def show_diff(event=None):
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            if i == 0 or i > len(wersje):
                old = wersje[0].get("kod", "") if wersje else ""
                new = sc.get("kod", "")
                title = "bieżąca vs poprzednia"
            else:
                old = wersje[i - 1].get("kod", "")
                new = wersje[i - 2].get("kod", "") if i - 2 < len(wersje) else sc.get("kod", "")
                title = f"{wersje[i-1].get('ts')} vs następna"
            import difflib
            diff = list(difflib.unified_diff(
                (old or "").splitlines(), (new or "").splitlines(),
                fromfile="starsza", tofile="nowsza", lineterm=""))
            txt.config(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", f"== {title} ==\n\n", "hdr")
            for line in diff or [_tr("(brak różnic)")]:
                if line.startswith("+") and not line.startswith("+++"):
                    tag = "add"
                elif line.startswith("-") and not line.startswith("---"):
                    tag = "del"
                else:
                    tag = ""
                txt.insert("end", line + "\n", tag)
            txt.config(state="disabled")

        def restore_version():
            sel = lb.curselection()
            if not sel or sel[0] == 0 or sel[0] > len(wersje):
                return
            v = wersje[sel[0] - 1]
            if not messagebox.askyesno(_tr("Przywróć wersję"),
                                       f"Przywrócić kod z {v.get('ts')} do edytora?"):
                return
            self.edytor_text.delete("1.0", "end")
            self.edytor_text.insert("1.0", v.get("kod", ""))
            self._edytor_update_lines()
            self._highlighter.highlight(self.edytor_text, sc.get("kategoria", "Python"))
            lb.selection_clear(0, "end")
            lb.selection_set(0)
            show_diff()

        bar = tk.Frame(right, bg=BG_DARK)
        bar.pack(side="bottom", fill="x")
        self._trw(tk.Button(bar, text=_tr("↺ Przywróć wybraną wersję do edytora"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", command=restore_version), "↺ Przywróć wybraną wersję do edytora").pack(side="left", padx=4, pady=4)
        self._trw(tk.Button(bar, text=_tr("Zamknij"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=dlg.destroy), "Zamknij").pack(side="right", padx=4, pady=4)
        lb.bind("<<ListboxSelect>>", show_diff)
        if lb.size():
            lb.selection_set(0)
            show_diff()

    def _lint_show(self) -> None:
        """Pokazuje panel wyników lintu (nad paskiem statusu edytora)."""
        if self._lint_panel.winfo_manager():
            return
        sb = getattr(self, "_edytor_status_bar", None)
        if sb is not None:
            self._lint_panel.pack(fill="x", padx=6, pady=(0, 4), before=sb)
        else:
            self._lint_panel.pack(fill="x", padx=6, pady=(0, 4))

    def _lint_hide(self) -> None:
        """Ukrywa panel wyników lintu."""
        self._lint_panel.pack_forget()

    def _lint_clear_marks(self) -> None:
        """Usuwa znaczniki lintu z edytora."""
        try:
            self.edytor_text.tag_remove("lint_err", "1.0", "end")
            self.edytor_text.tag_remove("lint_warn", "1.0", "end")
        except Exception:
            pass

    def _lint_summary(self, issues: List[Dict[str, Any]]) -> str:
        """Zwraca tekst podsumowania problemów lintu."""
        errs = sum(1 for i in issues if i["severity"] == LINT_ERROR)
        warns = len(issues) - errs
        return _tr("Problemy: {n} · błędy: {e} · ostrzeżenia: {w}").format(
            n=len(issues), e=errs, w=warns)

    def _edytor_lint(self) -> None:
        """Uruchamia analizę statyczną kodu w edytorze i pokazuje panel wyników."""
        if self._edytor_current_idx is None or self._edytor_current_idx >= len(self.skrypty):
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz skrypt z listy."))
            return
        sc = self.skrypty[self._edytor_current_idx]
        self._lint_show()
        self._lint_tree.delete(*self._lint_tree.get_children())
        self._lint_clear_marks()
        kategoria = sc.get("kategoria")
        if not lint_supported(kategoria):
            self._lint_status_lbl.config(
                text=_tr("Lint nie obsługuje kategorii {k}.").format(k=kategoria or "?"))
            return
        kod = self.edytor_text.get("1.0", "end-1c")
        try:
            issues = lint_code(kod, kategoria, sc.get("nazwa"),
                               sc.get("interpreter", ""))
        except Exception as e:
            logging.warning(f"Lint failed: {e}")
            issues = []
        for it in issues:
            sev = _tr("błąd") if it["severity"] == LINT_ERROR else _tr("ostrzeżenie")
            self._lint_tree.insert("", "end", values=(
                it["line"], it["code"], sev, it["message"]))
            tag = "lint_err" if it["severity"] == LINT_ERROR else "lint_warn"
            ln = max(1, int(it["line"]))
            self.edytor_text.tag_add(tag, f"{ln}.0", f"{ln}.end")
        self._lint_status_lbl.config(
            text=self._lint_summary(issues) if issues else _tr("Brak problemów"))

    def _lint_goto(self, event=None) -> None:
        """Przechodzi do linii wskazanej w panelu lintu."""
        sel = self._lint_tree.selection()
        if not sel:
            return
        vals = self._lint_tree.item(sel[0], "values")
        try:
            ln = int(vals[0])
        except (TypeError, ValueError, IndexError):
            return
        self.edytor_text.mark_set("insert", f"{ln}.0")
        self.edytor_text.see(f"{ln}.0")
        self.edytor_text.focus_set()

    def _edytor_run(self):
        """Uruchamia skrypt otwarty w edytorze."""
        if self._edytor_current_idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz skrypt z listy."))
            return
        sc = self.skrypty[self._edytor_current_idx]
        kod = self.edytor_text.get("1.0", "end-1c")
        # Ostrzeżenie o błędach składni wykrytych przez linter (można wymusić start).
        if lint_supported(sc.get("kategoria")):
            try:
                errors = [i for i in lint_code(kod, sc.get("kategoria"), sc.get("nazwa"),
                                               sc.get("interpreter", ""))
                          if i["severity"] == LINT_ERROR]
            except Exception:
                errors = []
            if errors:
                proceed = messagebox.askyesno(
                    _tr("Lint: wykryto błędy"),
                    _tr("Wykryto {n} błąd(ów) w kodzie.\nUruchomić mimo to?").format(n=len(errors)))
                if not proceed:
                    self._edytor_lint()
                    return
        sc["kod"] = kod
        self._runner_current_idx = self._edytor_current_idx
        self._runner_mode_edit = False
        self._after_db_change()
        self._menu_pokaz_runner()
        self._runner_start()

    def _edytor_export_exe(self):
        """Buduje plik wykonywalny z aktualnego kodu Python w edytorze."""
        if self._edytor_current_idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz skrypt z listy."))
            return
        script = dict(self.skrypty[self._edytor_current_idx])
        if script.get("kategoria") != "Python":
            messagebox.showwarning(_tr("Eksport .exe"), _tr("Eksport do .exe obsługuje tylko skrypty Python."))
            return
        script["kod"] = self.edytor_text.get("1.0", "end-1c")
        default_dir = Path.home() / "VDriveImages" / "Exports"
        output_dir = filedialog.askdirectory(
            title=_tr("Folder docelowy eksportu .exe"), initialdir=str(default_dir.parent))
        if not output_dir:
            return

        dialog = _popup(self)
        dialog.title(f"Eksport .exe — {script.get('nazwa', '')}")
        dialog.geometry("680x420")
        dialog.transient(self)
        dialog.grab_set()
        options = tk.Frame(dialog, padx=10, pady=8)
        options.pack(fill="x")
        onefile = tk.BooleanVar(value=True)
        console = tk.BooleanVar(value=True)
        self._trw(ttk.Checkbutton(options, text=_tr("Jeden plik (onefile)"), variable=onefile), "Jeden plik (onefile)").pack(side="left", padx=4)
        ttk.Checkbutton(options, text=_tr("Pokaż konsolę"), variable=console).pack(side="left", padx=4)
        icon_var = tk.StringVar()
        icon_row = tk.Frame(dialog, padx=10)
        icon_row.pack(fill="x")
        tk.Entry(icon_row, textvariable=icon_var).pack(side="left", fill="x", expand=True)
        self._trw(tk.Button(icon_row, text=_tr("Ikona .ico…"), command=lambda: icon_var.set(
            filedialog.askopenfilename(filetypes=[("Ikony Windows", "*.ico")]) or icon_var.get()
        )), "Ikona .ico…").pack(side="left", padx=5)
        progress = ttk.Progressbar(dialog, mode="indeterminate")
        progress.pack(fill="x", padx=10, pady=8)
        log = tk.Text(dialog, height=16, wrap="word", state="disabled")
        log.pack(fill="both", expand=True, padx=10, pady=4)
        start = self._trw(ttk.Button(options, text=_tr("Buduj")), "Buduj")
        start.pack(side="right", padx=4)

        def finish(result=None, error=None):
            progress.stop()
            log.configure(state="normal")
            log.insert("end", (result or {}).get("log", "") if result else str(error))
            if result:
                log.insert("end", f"\n\nArtefakt: {result['path']}\n")
            log.configure(state="disabled")
            start.configure(state="normal", text=_tr("Buduj ponownie"))
            if result:
                messagebox.showinfo(_tr("Eksport zakończony"), f"Plik zapisano:\n{result['path']}", parent=dialog)

        def build():
            from src.exe_export import build_executable
            build_onefile = onefile.get()
            build_console = console.get()
            build_icon = icon_var.get() or None
            start.configure(state="disabled")
            progress.start(10)

            def worker():
                try:
                    result = build_executable(
                        script, output_dir, build_onefile, build_icon, build_console)
                    self._safe_after(0, lambda: finish(result=result))
                except Exception as exc:
                    self._safe_after(0, lambda error=exc: finish(error=error))

            import threading
            threading.Thread(target=worker, daemon=True, name="pyinstaller-export").start()

        start.configure(command=build)

    def _edytor_copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.edytor_text.get("1.0", "end-1c"))
        messagebox.showinfo(_tr("Skopiowano"), _tr("Kod skopiowany do schowka."))

    def _edytor_delete(self):
        if self._edytor_current_idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz skrypt z listy."))
            return
        nazwa = self.skrypty[self._edytor_current_idx].get("nazwa", "?")
        if messagebox.askyesno(_tr("Kosz"), f"Przenieść '{nazwa}' do kosza?"):
            self.skrypty[self._edytor_current_idx] = dict(
                self.skrypty[self._edytor_current_idx], usuniety=now_str())
            self._edytor_current_idx = None
            self._runner_current_idx = None
            self.edytor_text.delete("1.0", "end")
            self.edytor_lbl_nazwa.config(text=_tr("— brak wybranego skryptu —"))
            self._edytor_update_lines()
            self._edytor_refresh()
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            self._trash_fill()
            self._after_db_change()

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: SZABLONY KODU
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_szablony(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["szablony"] = frame

        # wbudowane szablony kodu
        self._SZABLONY = {
            "Python": {
                "Skrypt podstawowy": (
                    "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\"\"\"\nOpis skryptu\n\"\"\"\n\n\ndef main():\n    pass\n\n\nif __name__ == '__main__':\n    main()\n"
                ),
                "Klasa z __init__": (
                    "class NazwaKlasy:\n    \"\"\"Opis klasy.\"\"\"\n\n    def __init__(self, arg1, arg2):\n        self.arg1 = arg1\n        self.arg2 = arg2\n\n    def __repr__(self):\n        return f'NazwaKlasy({self.arg1!r}, {self.arg2!r})'\n\n    def metoda(self):\n        pass\n"
                ),
                "Obsługa pliku": (
                    "from pathlib import Path\n\npath = Path('plik.txt')\n\n# Zapis\npath.write_text('treść', encoding='utf-8')\n\n# Odczyt\ntext = path.read_text(encoding='utf-8')\nprint(text)\n"
                ),
                "Argparse CLI": (
                    "import argparse\n\ndef parse_args():\n    p = argparse.ArgumentParser(description='Opis narzędzia')\n    p.add_argument('wejscie', help='Plik wejściowy')\n    p.add_argument('-o', '--output', default='out.txt', help='Plik wyjściowy')\n    p.add_argument('-v', '--verbose', action='store_true')\n    return p.parse_args()\n\ndef main():\n    args = parse_args()\n    if args.verbose:\n        print(f'Plik: {args.wejscie}')\n\nif __name__ == '__main__':\n    main()\n"
                ),
                "Requests HTTP": (
                    "import requests\n\nurl = 'https://api.example.com/data'\nheaders = {'Authorization': 'Bearer TOKEN'}\nparams = {'limit': 100}\n\ntry:\n    r = requests.get(url, headers=headers, params=params, timeout=10)\n    r.raise_for_status()\n    data = r.json()\n    print(data)\nexcept requests.RequestException as e:\n    print(f'Błąd: {e}')\n"
                ),
                "Logging": (
                    "import logging\n\nlogging.basicConfig(\n    level=logging.DEBUG,\n    format='%(asctime)s [%(levelname)s] %(message)s',\n    handlers=[\n        logging.FileHandler('app.log', encoding='utf-8'),\n        logging.StreamHandler()\n    ]\n)\nlog = logging.getLogger(__name__)\n\nlog.debug('Debug')\nlog.info('Info')\nlog.warning('Uwaga')\nlog.error('Błąd')\n"
                ),
                "SQLite CRUD": (
                    "import sqlite3\n\ncon = sqlite3.connect('baza.db')\ncon.row_factory = sqlite3.Row\ncur = con.cursor()\n\ncur.execute('''\n    CREATE TABLE IF NOT EXISTS elementy (\n        id   INTEGER PRIMARY KEY AUTOINCREMENT,\n        nazwa TEXT NOT NULL,\n        wartosc TEXT\n    )\n''')\ncon.commit()\n\n# INSERT\ncur.execute('INSERT INTO elementy (nazwa, wartosc) VALUES (?, ?)', ('klucz', 'wartość'))\ncon.commit()\n\n# SELECT\nfor row in cur.execute('SELECT * FROM elementy'):\n    print(dict(row))\n\ncon.close()\n"
                ),
                "Dataclass": (
                    "from dataclasses import dataclass, field\nfrom typing import List\n\n@dataclass\nclass Produkt:\n    nazwa: str\n    cena: float\n    tagi: List[str] = field(default_factory=list)\n\n    @property\n    def cena_brutto(self) -> float:\n        return self.cena * 1.23\n\np = Produkt('Kawa', 12.50, ['napój', 'gorący'])\nprint(p)\nprint(f'Brutto: {p.cena_brutto:.2f} zł')\n"
                ),
                "Dekorator": (
                    "import functools\nimport time\n\ndef timer(func):\n    @functools.wraps(func)\n    def wrapper(*args, **kwargs):\n        start = time.perf_counter()\n        result = func(*args, **kwargs)\n        elapsed = time.perf_counter() - start\n        print(f'{func.__name__} — {elapsed:.4f}s')\n        return result\n    return wrapper\n\n@timer\ndef przyklad():\n    time.sleep(0.1)\n    return 42\n\nprzyklad()\n"
                ),
            },
            "Bash": {
                "Skrypt podstawowy": (
                    "#!/usr/bin/env bash\nset -euo pipefail\n\n# ── Zmienne ───────────────────────────────────\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nLOG=\"${SCRIPT_DIR}/script.log\"\n\nlog() { echo \"[$(date '+%H:%M:%S')] $*\" | tee -a \"$LOG\"; }\n\nmain() {\n    log 'Start'\n    log 'Koniec'\n}\n\nmain \"$@\"\n"
                ),
                "Sprawdź zależności": (
                    "#!/usr/bin/env bash\ndeps=(git curl python3 jq)\n\nfor dep in \"${deps[@]}\"; do\n    if ! command -v \"$dep\" &>/dev/null; then\n        echo \"BRAK: $dep\"\n        exit 1\n    fi\n    echo \"OK: $dep ($(command -v \"$dep\"))\"\ndone\n"
                ),
                "Pętla po plikach": (
                    "#!/usr/bin/env bash\nset -euo pipefail\n\nSRC_DIR=\"./pliki\"\nEXT=\".txt\"\n\nfind \"$SRC_DIR\" -name \"*${EXT}\" | while read -r plik; do\n    echo \"Przetwarzam: $plik\"\n    # tu Twoja logika\ndone\n"
                ),
                "Menu interaktywne": (
                    "#!/usr/bin/env bash\nwhile true; do\n    echo '1) Opcja A'\n    echo '2) Opcja B'\n    echo '0) Wyjście'\n    read -rp 'Wybór: ' wybor\n    case $wybor in\n        1) echo 'Opcja A' ;;\n        2) echo 'Opcja B' ;;\n        0) echo 'Do widzenia'; exit 0 ;;\n        *) echo 'Nieznana opcja' ;;\n    esac\ndone\n"
                ),
            },
            "PowerShell": {
                "Skrypt podstawowy": (
                    "#Requires -Version 5.1\n[CmdletBinding()]\nparam(\n    [Parameter(Mandatory)][string]$Sciezka,\n    [switch]$Verbose\n)\n\nSet-StrictMode -Version Latest\n$ErrorActionPreference = 'Stop'\n\nfunction Write-Log {\n    param([string]$Msg)\n    \"[{0}] {1}\" -f (Get-Date -f 'HH:mm:ss'), $Msg | Tee-Object -Append -FilePath script.log\n}\n\nWrite-Log 'Start'\n# Twoja logika tutaj\nWrite-Log 'Koniec'\n"
                ),
                "Przetwarzanie plików": (
                    "Get-ChildItem -Path . -Filter '*.txt' -Recurse | ForEach-Object {\n    $content = Get-Content $_.FullName -Encoding UTF8\n    $lines   = $content.Count\n    Write-Host \"$($_.Name): $lines linii\"\n}\n"
                ),
                "Moduł AD / LDAP": (
                    "Import-Module ActiveDirectory\n\n$users = Get-ADUser -Filter {Enabled -eq $true} -Properties DisplayName, Mail |\n    Select-Object SamAccountName, DisplayName, Mail\n\n$users | Export-Csv -Path users.csv -Encoding UTF8 -NoTypeInformation\nWrite-Host \"Wyeksportowano $($users.Count) użytkowników.\"\n"
                ),
            },
            "JavaScript": {
                "Async / Await fetch": (
                    "const API = 'https://api.example.com';\n\nasync function getData(endpoint) {\n  try {\n    const res = await fetch(`${API}/${endpoint}`);\n    if (!res.ok) throw new Error(`HTTP ${res.status}`);\n    return await res.json();\n  } catch (err) {\n    console.error('Błąd:', err);\n    throw err;\n  }\n}\n\n(async () => {\n  const data = await getData('users');\n  console.log(data);\n})();\n"
                ),
                "Node.js CLI": (
                    "#!/usr/bin/env node\n'use strict';\nconst fs = require('fs');\nconst path = require('path');\n\nconst [,, ...args] = process.argv;\nif (!args.length) {\n  console.error('Użycie: script.js <plik>');\n  process.exit(1);\n}\n\nconst content = fs.readFileSync(path.resolve(args[0]), 'utf8');\nconsole.log(`Znaki: ${content.length}`);\n"
                ),
                "Klasa ES6": (
                    "class Pojazd {\n  #predkosc = 0;\n\n  constructor(marka, model) {\n    this.marka = marka;\n    this.model = model;\n  }\n\n  przyspiesz(delta) { this.#predkosc = Math.max(0, this.#predkosc + delta); }\n  zatrzymaj()       { this.#predkosc = 0; }\n\n  get predkosc() { return this.#predkosc; }\n\n  toString() { return `${this.marka} ${this.model} @ ${this.#predkosc} km/h`; }\n}\n\nconst auto = new Pojazd('Fiat', '126p');\nauto.przyspiesz(60);\nconsole.log(`${auto}`);\n"
                ),
            },
            "SQL": {
                "SELECT z JOIN": (
                    "SELECT\n    u.id,\n    u.nazwa,\n    COUNT(z.id) AS zamowien,\n    SUM(z.kwota)  AS suma\nFROM uzytkownicy u\nLEFT JOIN zamowienia z ON z.uzytkownik_id = u.id\nWHERE u.aktywny = 1\nGROUP BY u.id, u.nazwa\nHAVING COUNT(z.id) > 0\nORDER BY suma DESC\nLIMIT 50;\n"
                ),
                "CREATE TABLE": (
                    "CREATE TABLE IF NOT EXISTS produkty (\n    id          INTEGER      PRIMARY KEY AUTOINCREMENT,\n    kod         VARCHAR(20)  NOT NULL UNIQUE,\n    nazwa       VARCHAR(200) NOT NULL,\n    cena        DECIMAL(10,2) DEFAULT 0.00,\n    kategoria   VARCHAR(100),\n    aktywny     BOOLEAN      DEFAULT 1,\n    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP\n);\n\nCREATE INDEX idx_produkty_kod ON produkty(kod);\nCREATE INDEX idx_produkty_kat ON produkty(kategoria);\n"
                ),
                "CTE (WITH)": (
                    "WITH ranked AS (\n    SELECT\n        *,\n        ROW_NUMBER() OVER (PARTITION BY kategoria ORDER BY cena DESC) AS rn\n    FROM produkty\n    WHERE aktywny = 1\n)\nSELECT id, kod, nazwa, cena, kategoria\nFROM ranked\nWHERE rn = 1;\n"
                ),
            },
            "Batch": {
                "Skrypt podstawowy": (
                    "@echo off\nsetlocal enabledelayedexpansion\nchcp 65001 >nul\n\nrem ── Zmienne ─────────────────────────────────\nset \"SKRYPT=%~nx0\"\nset \"KATALOG=%~dp0\"\n\necho [%date% %time%] Start: %SKRYPT%\n\nrem Twoja logika tutaj\n\necho [%date% %time%] Koniec\nendlocal\npause\n"
                ),
                "Parametry %1 %2": (
                    "@echo off\nsetlocal\n\nif \"%~1\"==\"\" (\n    echo Uzycie: %~nx0 ^<nazwa^> [opcje]\n    exit /b 1\n)\n\nset \"NAZWA=%~1\"\necho Przetwarzam: %NAZWA%\nshift\necho Pozostale argumenty: %*\n\nendlocal\n"
                ),
                "Petla po plikach": (
                    "@echo off\nsetlocal enabledelayedexpansion\n\nset \"SRC=%~dp0pliki\"\nfor %%F in (\"%SRC%\\*.txt\") do (\n    echo Przetwarzam: %%~nxF\n    rem tu Twoja logika\n)\n\nendlocal\npause\n"
                ),
                "Menu wyboru": (
                    "@echo off\nsetlocal enabledelayedexpansion\n:menu\ncls\necho 1) Opcja A\necho 2) Opcja B\necho 0) Wyjscie\nset /p \"wybor=Wybor: \"\nif \"%wybor%\"==\"1\" goto opcjaA\nif \"%wybor%\"==\"2\" goto opcjaB\nif \"%wybor%\"==\"0\" exit /b 0\ngoto menu\n\n:opcjaA\necho Opcja A\npause\ngoto menu\n\n:opcjaB\necho Opcja B\npause\ngoto menu\n"
                ),
            },
            "VBScript": {
                "Skrypt podstawowy": (
                    "' Skrypt podstawowy VBScript\nOption Explicit\n\nDim fso, wsh\nSet fso = CreateObject(\"Scripting.FileSystemObject\")\nSet wsh = WScript.CreateObject(\"WScript.Shell\")\n\nWScript.Echo \"Start: \" & WScript.ScriptName\n' Twoja logika tutaj\nWScript.Echo \"Koniec\"\n"
                ),
                "Operacje na plikach": (
                    "' Operacje na plikach\nOption Explicit\n\nDim fso, plik, tekst\nSet fso = CreateObject(\"Scripting.FileSystemObject\")\n\nSet plik = fso.CreateTextFile(\"dane.txt\", True)\nplik.WriteLine \"linia 1\"\nplik.WriteLine \"linia 2\"\nplik.Close\n\nSet plik = fso.OpenTextFile(\"dane.txt\", 1)\nDo Until plik.AtEndOfStream\n    tekst = plik.ReadLine\n    WScript.Echo tekst\nLoop\nplik.Close\n"
                ),
                "Argumenty i wejscie": (
                    "' Argumenty i wejscie\nOption Explicit\n\nDim args, odp\nSet args = WScript.Arguments\n\nIf args.Count = 0 Then\n    WScript.Echo \"Uzycie: cscript //nologo skrypt.vbs <parametr>\"\n    WScript.Quit 1\nEnd If\n\nWScript.Echo \"Parametr: \" & args(0)\nodp = InputBox(\"Podaj wartosc:\", \"Dane\")\nWScript.Echo \"Wprowadzono: \" & odp\n"
                ),
            },
            "Java": {
                "Klasa z main": (
                    "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Witaj, Java!\");\n        for (String arg : args) {\n            System.out.println(\"Argument: \" + arg);\n        }\n    }\n}\n"
                ),
                "Klasa z polami": (
                    "public class Osoba {\n    private final String imie;\n    private final int wiek;\n\n    public Osoba(String imie, int wiek) {\n        this.imie = imie;\n        this.wiek = wiek;\n    }\n\n    public String opis() {\n        return imie + \" (\" + wiek + \" lat)\";\n    }\n\n    public static void main(String[] args) {\n        Osoba o = new Osoba(\"Anna\", 30);\n        System.out.println(o.opis());\n    }\n}\n"
                ),
                "Obsługa wyjątków": (
                    "import java.nio.file.Files;\nimport java.nio.file.Path;\n\npublic class Main {\n    public static void main(String[] args) {\n        try {\n            String tresc = Files.readString(Path.of(\"dane.txt\"));\n            System.out.println(tresc);\n        } catch (Exception e) {\n            System.err.println(\"Blad: \" + e.getMessage());\n            System.exit(1);\n        }\n    }\n}\n"
                ),
            },
            "JAR": {
                "Uruchom (java -jar)": (
                    "Archiwum JAR nie jest edytowalne jako tekst.\nZapisz plik .jar lokalnie i uruchom:\n\n    java -jar nazwa.jar\n\nlub w aplikacji: zakładka Runner -> Uruchom (kategoria JAR).\n"
                ),
            },
            "Ruby": {
                "Skrypt podstawowy": (
                    "#!/usr/bin/env ruby\n# encoding: UTF-8\n\nputs 'Witaj, Ruby!'\nARGV.each { |arg| puts \"Argument: #{arg}\" }\n"
                ),
                "Klasa z metodami": (
                    "class Osoba\n  attr_reader :imie, :wiek\n\n  def initialize(imie, wiek)\n    @imie = imie\n    @wiek = wiek\n  end\n\n  def opis\n    \"#{@imie} (#{@wiek} lat)\"\n  end\nend\n\nputs Osoba.new('Anna', 30).opis\n"
                ),
                "Operacje na plikach": (
                    "File.write('dane.txt', \"linia 1\\nlinia 2\\n\")\n\nFile.foreach('dane.txt') do |linia|\n  puts linia.chomp\nend\n"
                ),
            },
            "Perl": {
                "Skrypt podstawowy": (
                    "#!/usr/bin/env perl\nuse strict;\nuse warnings;\n\nprint \"Witaj, Perl!\\n\";\nforeach my $arg (@ARGV) {\n    print \"Argument: $arg\\n\";\n}\n"
                ),
                "Operacje na plikach": (
                    "use strict;\nuse warnings;\n\nopen(my $fh, '>', 'dane.txt') or die \"Nie moge zapisac: $!\";\nprint $fh \"linia 1\\nlinia 2\\n\";\nclose($fh);\n\nopen($fh, '<', 'dane.txt') or die \"Nie moge odczytac: $!\";\nwhile (my $linia = <$fh>) {\n    chomp $linia;\n    print \"$linia\\n\";\n}\nclose($fh);\n"
                ),
                "Wyrażenia regularne": (
                    "use strict;\nuse warnings;\n\nmy $tekst = \"kontakt: jan\\@example.com, tel. 123-456-789\";\nif ($tekst =~ /(\\S+)\\@(\\S+)/) {\n    print \"E-mail: $1\\@$2\\n\";\n}\n$tekst =~ s/(\\d{3})-(\\d{3})-(\\d{3})/$1 $2 $3/g;\nprint \"$tekst\\n\";\n"
                ),
            },
            "PHP": {
                "Skrypt CLI": (
                    "<?php\ndeclare(strict_types=1);\n\necho \"Witaj, PHP!\\n\";\n$args = array_slice($argv, 1);\nforeach ($args as $arg) {\n    echo \"Argument: {$arg}\\n\";\n}\n"
                ),
                "Klasa": (
                    "<?php\ndeclare(strict_types=1);\n\nclass Osoba {\n    public function __construct(\n        private string $imie,\n        private int $wiek,\n    ) {}\n\n    public function opis(): string {\n        return \"{$this->imie} ({$this->wiek} lat)\";\n    }\n}\n\necho (new Osoba('Anna', 30))->opis() . PHP_EOL;\n"
                ),
                "Operacje na plikach": (
                    "<?php\ndeclare(strict_types=1);\n\nfile_put_contents('dane.txt', \"linia 1\\nlinia 2\\n\");\n\nforeach (file('dane.txt') as $linia) {\n    echo trim($linia) . PHP_EOL;\n}\n"
                ),
            },
            "WSF": {
                "Job VBScript": (
                    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<job id=\"Main\">\n  <script language=\"VBScript\">\n    Option Explicit\n    WScript.Echo \"Witaj z WSF!\"\n    WScript.Echo \"Liczba argumentow: \" & WScript.Arguments.Count\n  </script>\n</job>\n"
                ),
                "Job z dwoma skryptami": (
                    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<job id=\"Main\">\n  <script language=\"VBScript\">\n    WScript.Echo \"Czesc z VBScript\"\n  </script>\n  <script language=\"JScript\">\n    WScript.Echo(\"Czesc z JScript\");\n  </script>\n</job>\n"
                ),
            },
            "HTA": {
                "Aplikacja HTA": (
                    "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n<title>Moja aplikacja HTA</title>\n<HTA:APPLICATION ID=\"oApp\" BORDER=\"thin\" CAPTION=\"yes\"\n               SHOWINTASKBAR=\"yes\" SINGLEINSTANCE=\"yes\" WINDOWSTATE=\"normal\" />\n<script language=\"VBScript\">\nSub Klik\n    MsgBox \"Witaj z HTA!\", 64, \"HTA\"\nEnd Sub\n</script>\n</head>\n<body style=\"font-family: Segoe UI; background:#1e2130; color:#e0e4f0; padding:20px\">\n  <h1>HTML Application</h1>\n  <button onclick=\"Klik\">Kliknij mnie</button>\n</body>\n</html>\n"
                ),
            },
            "HTML": {
                "Strona podstawowa": (
                    "<!DOCTYPE html>\n<html lang=\"pl\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Strona</title>\n<style>\n  body { font-family: system-ui, sans-serif; margin: 2rem; }\n</style>\n</head>\n<body>\n  <h1>Witaj!</h1>\n  <script>\n    console.log('Gotowe');\n  </script>\n</body>\n</html>\n"
                ),
            },
            "CSS": {
                "Arkusz podstawowy": (
                    ":root {\n  --akcent: #4a90d9;\n  --tlo: #1e2130;\n}\n\nbody {\n  margin: 0;\n  font-family: system-ui, sans-serif;\n  background: var(--tlo);\n  color: #e0e4f0;\n}\n\n.przycisk {\n  padding: .5rem 1rem;\n  border-radius: 14px;\n  background: var(--akcent);\n  transition: filter .2s ease;\n}\n\n.przycisk:hover { filter: brightness(1.15); }\n"
                ),
            },
            "JSON": {
                "Obiekt przykładowy": (
                    "{\n  \"nazwa\": \"przyklad\",\n  \"wersja\": 1,\n  \"aktywny\": true,\n  \"elementy\": [1, 2, 3],\n  \"opcje\": { \"tryb\": \"auto\", \"poziom\": 3 }\n}\n"
                ),
            },
            "Markdown": {
                "Dokument podstawowy": (
                    "# Tytuł dokumentu\n\nKrótki opis projektu.\n\n## Sekcja\n\n- punkt pierwszy\n- punkt drugi\n\n**Pogrubienie**, *kursywa*, `kod`.\n\n```python\nprint(\"Witaj\")\n```\n"
                ),
            },
        }

        # ── pasek narzędzi ────────────────────────────────────────────────────
        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        self._trw(tk.Label(top, text=_tr("📦 Szablony kodu — gotowe fragmenty do wklejenia do edytora"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "📦 Szablony kodu — gotowe fragmenty do wklejenia do edytora").pack(side="left")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # ── lewa: drzewo kategorii + szablonów ───────────────────────────────
        left = tk.Frame(body, bg=BG_PANEL, width=230,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        self._trw(tk.Label(left, text=_tr("Kategoria / Szablon"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "Kategoria / Szablon").pack(anchor="w", padx=10, pady=(8, 2))

        sz_sc = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                             troughcolor=BG_PANEL, width=8)
        sz_sc.pack(side="right", fill="y", pady=2)

        self._sz_tree = ttk.Treeview(left, show="tree", selectmode="browse",
                                      yscrollcommand=sz_sc.set)
        sz_sc.config(command=self._sz_tree.yview)
        self._sz_tree.pack(fill="both", expand=True, padx=(6, 0), pady=4)

        for kat, tpls in self._SZABLONY.items():
            tag_kat = f"kat_{kat}"
            parent = self._sz_tree.insert("", "end", text=f"  {kat_label(kat)}",
                                          open=True, tags=(tag_kat,))
            self._sz_tree.tag_configure(
                tag_kat, foreground=KAT_COLOR.get(kat, ACCENT_BLUE))
            for nazwa in tpls:
                self._sz_tree.insert(parent, "end", text=f"    • {nazwa}",
                                     tags=("tpl",), iid=f"{kat}||{nazwa}")
        self._sz_tree.tag_configure("tpl", foreground=FG_WHITE)

        btn_f = tk.Frame(left, bg=BG_PANEL)
        btn_f.pack(fill="x", padx=6, pady=(2, 6))
        self._trw(tk.Button(btn_f, text=_tr("➕ Użyj w edytorze"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._sz_uzyj_w_edytorze), "➕ Użyj w edytorze").pack(fill="x", pady=2)
        self._trw(tk.Button(btn_f, text=_tr("💾 Zapisz jako skrypt"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sz_zapisz_jako_skrypt), "💾 Zapisz jako skrypt").pack(fill="x", pady=2)
        self._trw(tk.Button(btn_f, text=_tr("📋 Kopiuj do schowka"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sz_kopiuj), "📋 Kopiuj do schowka").pack(fill="x", pady=2)

        # ── prawa: podgląd szablonu + własny szablon ─────────────────────────
        right = tk.Frame(body, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        info_r = tk.Frame(right, bg=BG_PANEL, pady=4, padx=8)
        info_r.pack(fill="x")
        self._sz_lbl = self._trw(tk.Label(info_r, text=_tr("Wybierz szablon z listy po lewej"),
                                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_GRAY), "Wybierz szablon z listy po lewej")
        self._sz_lbl.pack(side="left")

        self._sz_preview = tk.Text(right, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                    insertbackground=FG_WHITE, relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER_CLR,
                                    highlightcolor=ACCENT_BLUE, wrap="none", height=18)
        sz_xsc = tk.Scrollbar(right, orient="horizontal",
                               command=self._sz_preview.xview,
                               bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        sz_xsc.pack(side="bottom", fill="x", padx=6)
        self._sz_preview.configure(xscrollcommand=sz_xsc.set)
        self._sz_preview.pack(fill="both", expand=True, padx=6, pady=(4, 0))

        # własny szablon
        tk.Frame(right, bg=BORDER_CLR, height=1).pack(fill="x", padx=6, pady=4)
        own_hdr = tk.Frame(right, bg=BG_DARK)
        own_hdr.pack(fill="x", padx=6)
        self._trw(tk.Label(own_hdr, text=_tr("✏ Własny szablon — nazwa:"),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "✏ Własny szablon — nazwa:").pack(side="left")
        self._sz_own_kat = ttk.Combobox(own_hdr, values=list(self._SZABLONY.keys()),
                                          font=FONT_UI, style="Dark.TCombobox",
                                          width=12, state="readonly")
        self._sz_own_kat.set("Python")
        self._sz_own_kat.pack(side="left", padx=6)
        self._sz_own_name = tk.Entry(own_hdr, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      insertbackground=FG_WHITE, relief="flat",
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      highlightcolor=ACCENT_BLUE, width=22)
        self._sz_own_name.pack(side="left", padx=4)
        self._trw(tk.Button(own_hdr, text=_tr("💾 Dodaj własny"), font=FONT_UI,
                  bg=BTN_OK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_OK_HOVER,
                  command=self._sz_dodaj_wlasny), "💾 Dodaj własny").pack(side="left", padx=4)

        self._sz_tree.bind("<<TreeviewSelect>>", self._sz_on_select)

    def _sz_on_select(self, event=None):
        sel = self._sz_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if "||" not in iid:
            return
        kat, nazwa = iid.split("||", 1)
        kod = self._SZABLONY.get(kat, {}).get(nazwa, "")
        self._sz_lbl.config(text=f"{kat}  ▸  {nazwa}", fg=ACCENT_BLUE)
        self._sz_preview.delete("1.0", "end")
        self._sz_preview.insert("1.0", kod)

    def _sz_get_selected_code(self):
        sel = self._sz_tree.selection()
        if not sel or "||" not in sel[0]:
            return None, None
        kat, nazwa = sel[0].split("||", 1)
        return nazwa, self._SZABLONY.get(kat, {}).get(nazwa, "")

    def _sz_uzyj_w_edytorze(self):
        nazwa, kod = self._sz_get_selected_code()
        if not kod:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz szablon z listy."))
            return
        self._sel_sub(0, self._show_sub_dodaj)
        self.text_kod.delete("1.0", "end")
        self.text_kod.insert("1.0", kod)
        self._update_line_nums()
        self._update_status()
        self._highlighter.highlight(self.text_kod, self.var_kat.get())

    def _sz_zapisz_jako_skrypt(self):
        nazwa, kod = self._sz_get_selected_code()
        if not kod:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz szablon z listy."))
            return
        self._sel_sub(0, self._show_sub_dodaj)
        self._wyczysc()
        self.entry_nazwa.insert(0, f"Szablon — {nazwa}")
        self.text_kod.insert("1.0", kod)
        self._update_line_nums()
        self._update_status()
        self._highlighter.highlight(self.text_kod, self.var_kat.get())

    def _sz_kopiuj(self):
        _, kod = self._sz_get_selected_code()
        if not kod:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz szablon z listy."))
            return
        self.clipboard_clear()
        self.clipboard_append(kod)
        messagebox.showinfo(_tr("Skopiowano"), _tr("Szablon skopiowany do schowka."))

    def _sz_dodaj_wlasny(self):
        kat   = self._sz_own_kat.get()
        nazwa = self._sz_own_name.get().strip()
        kod   = self._sz_preview.get("1.0", "end-1c")
        if not nazwa:
            messagebox.showwarning(_tr("Brak nazwy"), _tr("Podaj nazwę własnego szablonu."))
            return
        if not kod.strip():
            messagebox.showwarning(_tr("Brak kodu"), _tr("Edytor podglądu jest pusty."))
            return
        if kat not in self._SZABLONY:
            self._SZABLONY[kat] = {}
        self._SZABLONY[kat][nazwa] = kod
        iid = f"{kat}||{nazwa}"
        # znajdź węzeł kategorii
        for item in self._sz_tree.get_children():
            if self._sz_tree.item(item, "text").strip() == kat:
                self._sz_tree.insert(item, "end", text=f"    • {nazwa}",
                                     tags=("tpl",), iid=iid)
                break
        messagebox.showinfo(_tr("Dodano"), f"Szablon '{nazwa}' dodany do kategorii '{kat}'.")

    def _show_sub_szablony(self):
        self.sub_frames["szablony"].pack(fill="both", expand=True, padx=4, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: BIBLIOTEKA SNIPPETÓW
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_snippety(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["snippety"] = frame

        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        self._trw(tk.Label(top, text=_tr("📚 Biblioteka snippetów — własne fragmenty kodu"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE),
                 "📚 Biblioteka snippetów — własne fragmenty kodu").pack(side="left")
        self._trw(tk.Label(top, text=_tr("Placeholdery: ${nazwa}"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                 "Placeholdery: ${nazwa}").pack(side="right")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # ── lewa: lista snippetów ────────────────────────────────────────────
        left = tk.Frame(body, bg=BG_PANEL, width=280,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        self._trw(tk.Label(left, text=_tr("Nazwa / kategoria / tagi"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE),
                 "Nazwa / kategoria / tagi").pack(anchor="w", padx=10, pady=(8, 2))

        self._sn_flt_var = tk.StringVar()
        flt = tk.Entry(left, textvariable=self._sn_flt_var, font=FONT_MONO,
                       bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE,
                       relief="flat", highlightthickness=1,
                       highlightbackground=BORDER_CLR, highlightcolor=ACCENT_BLUE)
        flt.pack(fill="x", padx=8, pady=(0, 4))
        self._sn_flt_var.trace_add("write", lambda *_: self._sn_fill())

        sn_sc = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                             troughcolor=BG_PANEL, width=8)
        sn_sc.pack(side="right", fill="y", pady=2)

        cols = ("nazwa", "kategoria", "tagi")
        self._sn_tree = ttk.Treeview(left, columns=cols, show="headings",
                                     selectmode="browse", yscrollcommand=sn_sc.set)
        for c, w in zip(cols, (130, 70, 70)):
            self._trh(self._sn_tree, c, c)
            self._sn_tree.column(c, width=w, anchor="w")
        sn_sc.config(command=self._sn_tree.yview)
        self._sn_tree.pack(fill="both", expand=True, padx=(8, 0), pady=2)
        self._sn_tree.bind("<<TreeviewSelect>>", self._sn_on_select)
        self._sn_tree.bind("<Double-1>", lambda e: self._sn_insert())

        sn_btn = tk.Frame(left, bg=BG_PANEL)
        sn_btn.pack(fill="x", padx=6, pady=(2, 6))
        self._trw(tk.Button(sn_btn, text=_tr("➕ Nowy"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sn_new), "➕ Nowy").pack(fill="x", pady=2)
        self._trw(tk.Button(sn_btn, text=_tr("💾 Zapisz"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._sn_save), "💾 Zapisz").pack(fill="x", pady=2)
        self._trw(tk.Button(sn_btn, text=_tr("🗑 Usuń"), font=FONT_UI,
                  bg=BTN_ERR, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_ERR_HOVER,
                  command=self._sn_delete), "🗑 Usuń").pack(fill="x", pady=2)

        # ── prawa: formularz + treść snippetu ────────────────────────────────
        right = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="both", expand=True)

        info = tk.Frame(right, bg=BG_PANEL, pady=5, padx=8)
        info.pack(fill="x")
        self._trw(tk.Label(info, text=_tr("Nazwa:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                 "Nazwa:").pack(side="left")
        self._sn_name = tk.Entry(info, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                 insertbackground=FG_WHITE, relief="flat",
                                 highlightthickness=1, highlightbackground=BORDER_CLR,
                                 highlightcolor=ACCENT_BLUE, width=24)
        self._sn_name.pack(side="left", padx=(4, 10))
        self._trw(tk.Label(info, text=_tr("Kategoria:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                 "Kategoria:").pack(side="left")
        self._sn_kat = tk.StringVar(value="Python")
        ttk.Combobox(info, textvariable=self._sn_kat, values=CATEGORIES,
                     font=FONT_UI, state="readonly", style="Dark.TCombobox",
                     width=11).pack(side="left", padx=(4, 10))
        self._trw(tk.Label(info, text=_tr("Tagi:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                 "Tagi:").pack(side="left")
        self._sn_tags = tk.Entry(info, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                 insertbackground=FG_WHITE, relief="flat",
                                 highlightthickness=1, highlightbackground=BORDER_CLR,
                                 highlightcolor=ACCENT_BLUE, width=18)
        self._sn_tags.pack(side="left", padx=(4, 0))

        tk.Frame(right, bg=BORDER_CLR, height=1).pack(fill="x")

        sn_ed = tk.Frame(right, bg=BG_DARK)
        sn_ed.pack(fill="both", expand=True, padx=6, pady=6)
        sn_ysc = tk.Scrollbar(sn_ed, orient="vertical", bg=BG_PANEL,
                              troughcolor=BG_PANEL, width=10)
        sn_ysc.pack(side="right", fill="y")
        self._sn_text = tk.Text(sn_ed, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                insertbackground=FG_WHITE, relief="flat",
                                highlightthickness=1, highlightbackground=BORDER_CLR,
                                highlightcolor=ACCENT_BLUE, wrap="none", tabs="4c",
                                yscrollcommand=sn_ysc.set)
        sn_ysc.config(command=self._sn_text.yview)
        self._sn_text.pack(side="left", fill="both", expand=True)

        bar = tk.Frame(right, bg=BG_PANEL, pady=5, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("➕ Wstaw do edytora"), font=FONT_UI,
                  bg=BTN_OK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_OK_HOVER,
                  command=self._sn_insert), "➕ Wstaw do edytora").pack(side="left")
        self._trw(tk.Button(bar, text=_tr("📋 Kopiuj"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sn_copy), "📋 Kopiuj").pack(side="left", padx=4)
        self._sn_status = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self._sn_status.pack(side="right")

    def _sn_fill(self):
        """Wypełnia listę snippetów (z filtrem po nazwie/kategorii/tagach)."""
        if not hasattr(self, "_sn_tree"):
            return
        tree = self._sn_tree
        for row in tree.get_children():
            tree.delete(row)
        q = self._sn_flt_var.get().strip().casefold() if hasattr(self, "_sn_flt_var") else ""
        for it in self.snippety:
            hay = " ".join(str(it.get(k, "")) for k in ("nazwa", "kategoria", "tagi"))
            if q and q not in hay.casefold():
                continue
            tree.insert("", "end", iid=it["id"], values=(
                it.get("nazwa", "?"), it.get("kategoria", "?"), it.get("tagi", "")))

    def _sn_current(self) -> Optional[Dict[str, Any]]:
        """Zwraca zaznaczony snippet lub None."""
        sel = self._sn_tree.selection() if hasattr(self, "_sn_tree") else ()
        if not sel:
            return None
        for it in self.snippety:
            if it["id"] == sel[0]:
                return it
        return None

    def _sn_on_select(self, _e=None):
        """Wczytuje zaznaczony snippet do formularza."""
        it = self._sn_current()
        if it is None:
            return
        self._sn_name.delete(0, "end")
        self._sn_name.insert(0, it.get("nazwa", ""))
        self._sn_kat.set(it.get("kategoria", "Python"))
        self._sn_tags.delete(0, "end")
        self._sn_tags.insert(0, it.get("tagi", ""))
        self._sn_text.delete("1.0", "end")
        self._sn_text.insert("1.0", it.get("tresc", ""))

    def _sn_new(self):
        """Czyści formularz — przygotowanie nowego snippetu."""
        if hasattr(self, "_sn_tree"):
            self._sn_tree.selection_remove(*self._sn_tree.selection())
        self._sn_name.delete(0, "end")
        self._sn_kat.set(self.var_kat.get() if hasattr(self, "var_kat") else "Python")
        self._sn_tags.delete(0, "end")
        self._sn_text.delete("1.0", "end")
        self._sn_name.focus_set()

    def _sn_save(self):
        """Dodaje nowy snippet lub aktualizuje zaznaczony i zapisuje bibliotekę."""
        nazwa = self._sn_name.get().strip()
        tresc = self._sn_text.get("1.0", "end-1c")
        if not nazwa:
            messagebox.showwarning(_tr("Brak nazwy"), _tr("Podaj nazwę snippetu."))
            return
        if not tresc.strip():
            messagebox.showwarning(_tr("Brak kodu"), _tr("Treść snippetu jest pusta."))
            return
        cur = self._sn_current()
        if cur is None:
            it = snippet_normalize({
                "nazwa": nazwa, "kategoria": self._sn_kat.get(),
                "tagi": self._sn_tags.get().strip(), "tresc": tresc})
            self.snippety.append(it)
            new_id = it["id"]
        else:
            cur.update({"nazwa": nazwa, "kategoria": self._sn_kat.get(),
                        "tagi": self._sn_tags.get().strip(), "tresc": tresc,
                        "zmieniony": now_str()})
            new_id = cur["id"]
        snippets_save(self.snippety)
        self._sn_fill()
        if self._sn_tree.exists(new_id):
            self._sn_tree.selection_set(new_id)
        self._sn_status.config(text=_t("sn_status_saved"), fg="#6dde84")

    def _sn_delete(self):
        """Trwale usuwa zaznaczony snippet z biblioteki."""
        it = self._sn_current()
        if it is None:
            messagebox.showinfo(_tr("Snippety"), _tr("Zaznacz snippet do usunięcia."))
            return
        if not messagebox.askyesno(_tr("Snippety"), f"Usunąć snippet '{it.get('nazwa', '')}'?"):
            return
        self.snippety = [s for s in self.snippety if s["id"] != it["id"]]
        snippets_save(self.snippety)
        self._sn_fill()
        self._sn_new()
        self._sn_status.config(text=_t("sn_status_deleted"), fg="#e0c040")

    def _sn_apply_placeholders(self, text: str) -> Optional[str]:
        """Zamienia ``${nazwa}`` na wartości podane w dialogu (None = anulowano)."""
        names: List[str] = []
        for m in PLACEHOLDER_RE.finditer(text):
            if m.group(1) not in names:
                names.append(m.group(1))
        if not names:
            return text
        from tkinter import simpledialog
        values: Dict[str, str] = {}
        for name in names:
            val = simpledialog.askstring(_tr("Snippet — wypełnij placeholdery"),
                                         f"${{{name}}} →")
            if val is None:
                return None
            values[name] = val
        return PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)

    def _sn_target_editor(self):
        """Zwraca (widget Text, kategoria) aktywnego edytora do wstawienia."""
        try:
            foc = self.focus_get()
        except Exception:
            foc = None
        if foc is getattr(self, "edytor_text", None):
            idx = getattr(self, "_edytor_current_idx", None)
            kat = "Python"
            if idx is not None and 0 <= idx < len(self.skrypty):
                kat = self.skrypty[idx].get("kategoria", "Python")
            return self.edytor_text, kat
        return self.text_kod, self.var_kat.get()

    def _sn_insert(self):
        """Wstawia fragment w miejscu kursora aktywnego edytora."""
        it = self._sn_current()
        tresc = it.get("tresc", "") if it else self._sn_text.get("1.0", "end-1c")
        if not tresc.strip():
            messagebox.showinfo(_tr("Snippety"), _tr("Wybierz snippet z listy."))
            return
        resolved = self._sn_apply_placeholders(tresc)
        if resolved is None:
            return
        editor, kat = self._sn_target_editor()
        editor.insert("insert", resolved)
        if editor is getattr(self, "text_kod", None):
            self._update_line_nums()
            self._update_status()
        elif editor is getattr(self, "edytor_text", None):
            self._edytor_update_lines()
        if hasattr(self, "_highlighter"):
            self._highlighter.highlight(editor, kat)
        editor.focus_set()
        self._sn_status.config(text=_t("sn_status_inserted"), fg="#6dde84")

    def _sn_copy(self):
        """Kopiuje treść zaznaczonego snippetu do schowka."""
        it = self._sn_current()
        tresc = it.get("tresc", "") if it else self._sn_text.get("1.0", "end-1c")
        if not tresc.strip():
            messagebox.showinfo(_tr("Snippety"), _tr("Wybierz snippet z listy."))
            return
        self.clipboard_clear()
        self.clipboard_append(tresc)
        self._sn_status.config(text=_t("sn_status_copied"), fg="#6dde84")

    def _show_sub_snippety(self):
        self._sn_fill()
        self.sub_frames["snippety"].pack(fill="both", expand=True, padx=4, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: STATYSTYKI
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_statystyki(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["statystyki_skr"] = frame

        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        self._trw(tk.Label(top, text=_tr("📊 Statystyki bazy skryptów"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "📊 Statystyki bazy skryptów").pack(side="left")
        self._trw(tk.Button(top, text=_tr("🔄 Odśwież"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._stat_refresh), "🔄 Odśwież").pack(side="right", padx=4)
        self._trw(tk.Button(top, text=_tr("💾 Eksportuj raport"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._stat_export), "💾 Eksportuj raport").pack(side="right", padx=4)

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        # ── karty podsumowania ────────────────────────────────────────────────
        cards = tk.Frame(body, bg=BG_DARK)
        cards.pack(fill="x", pady=(0, 10))
        self._stat_cards = {}
        card_defs = [
            ("skryptow",    "Skryptów",       "📄", ACCENT_BLUE),
            ("kategorii",   "Kategorii",       "🗂",  "#6dde84"),
            ("tagów",       "Unikalnych tagów", "🏷",  "#e0c040"),
            ("linii_kodu",  "Linii kodu",       "📝", "#c070e0"),
            ("uruchomien",  "Uruchomień",      "▶",  "#4caf50"),
            ("kosz",        "W koszu",          "🗑",  "#e0a020"),
        ]
        for key, label, icon, color in card_defs:
            card = tk.Frame(cards, bg=BG_PANEL, padx=18, pady=10,
                            highlightthickness=1, highlightbackground=color)
            card.pack(side="left", padx=6, fill="y")
            tk.Label(card, text=icon, font=("Consolas", 18),
                     bg=BG_PANEL, fg=color).pack()
            v = tk.StringVar(value="0")
            self._stat_cards[key] = v
            tk.Label(card, textvariable=v, font=("Consolas", 20, "bold"),
                     bg=BG_PANEL, fg=FG_WHITE).pack()
            self._trw(tk.Label(card, text=_tr(label), font=("Consolas", 8),
                     bg=BG_PANEL, fg=FG_GRAY), label).pack()

        # ── pasek kosza: rozmiar + liczba + ręczne opróżnienie ───────────────
        trash_bar = tk.Frame(body, bg=BG_PANEL, padx=10, pady=6,
                             highlightthickness=1, highlightbackground=BORDER_CLR)
        trash_bar.pack(fill="x", pady=(0, 10))
        self._trw(tk.Label(trash_bar, text=_tr("🗑 Kosz:"), font=FONT_BOLD,
                 bg=BG_PANEL, fg="#e0c040"), "🗑 Kosz:").pack(side="left")
        self._stat_trash_lbl = tk.Label(trash_bar, text="", font=FONT_UI,
                                        bg=BG_PANEL, fg=FG_GRAY)
        self._stat_trash_lbl.pack(side="left", padx=8)
        self._trw(tk.Button(trash_bar, text=_tr("✕ Opróżnij kosz"), font=FONT_UI,
                  bg=BTN_DARK, fg=ERROR, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  activeforeground=ERROR,
                  command=lambda: (self._trash_clear(), self._stat_refresh())
                  ), "✕ Opróżnij kosz").pack(side="right")

        # ── wykresy tekstowe i tabele: siatka 2×2 ────────────────────────────
        # górny rząd: kategorie | tagi ; dolny rząd: runner | największe skrypty
        row_top = tk.Frame(body, bg=BG_DARK)
        row_top.pack(fill="both", expand=True)
        row_bot = tk.Frame(body, bg=BG_DARK)
        row_bot.pack(fill="both", expand=True, pady=(6, 0))

        def _stat_panel(parent):
            return tk.Frame(parent, bg=BG_PANEL,
                            highlightthickness=1, highlightbackground=BORDER_CLR)

        def _stat_text(parent):
            return tk.Text(parent, font=("Consolas", 9), bg=BG_PANEL,
                           fg=FG_WHITE, relief="flat", height=8,
                           highlightthickness=0, state="disabled")

        # góra lewo: według kategorii
        left = _stat_panel(row_top)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._trw(tk.Label(left, text=_tr("Skrypty wg kategorii"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "Skrypty wg kategorii").pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_kat_text = _stat_text(left)
        self._stat_kat_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # góra prawo: top tagi
        mid = _stat_panel(row_top)
        mid.pack(side="left", fill="both", expand=True)
        self._trw(tk.Label(mid, text=_tr("Najczęstsze tagi (top 15)"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "Najczęstsze tagi (top 15)").pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_tag_text = _stat_text(mid)
        self._stat_tag_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # dół lewo: najczęściej uruchamiane (runner)
        runs = _stat_panel(row_bot)
        runs.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._trw(tk.Label(runs, text=_tr("Najczęściej uruchamiane (top 10) — runner"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "Najczęściej uruchamiane (top 10) — runner").pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_run_text = _stat_text(runs)
        self._stat_run_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # dół prawo: top 10 wg rozmiaru kodu (pod tagami)
        right = _stat_panel(row_bot)
        right.pack(side="left", fill="both", expand=True)
        self._trw(tk.Label(right, text=_tr("Największe skrypty (top 10)"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "Największe skrypty (top 10)").pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_size_text = _stat_text(right)
        self._stat_size_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _stat_refresh(self):
        from collections import Counter
        s = self._live_skrypty()

        # karty
        total = len(s)
        cats  = len({x.get("kategoria", "") for x in s if x.get("kategoria")})
        tags  = Counter()
        lines = 0
        for sc in s:
            for t in sc.get("tagi", "").split(","):
                t = t.strip()
                if t:
                    tags[t] += 1
            lines += len(sc.get("kod", "").splitlines())

        self._stat_cards["skryptow"].set(str(total))
        self._stat_cards["kategorii"].set(str(cats))
        self._stat_cards["tagów"].set(str(len(tags)))
        self._stat_cards["linii_kodu"].set(f"{lines:,}")
        self._stat_cards["uruchomien"].set(f"{sum(int(x.get('uruchomien') or 0) for x in s):,}")
        # kosz: liczba + rozmiar kodu
        t_n, t_size = self._trash_stats()
        self._stat_cards["kosz"].set(str(t_n))
        if hasattr(self, "_stat_trash_lbl"):
            self._stat_trash_lbl.config(
                text=_t("stat_trash_info", n=t_n, size=f"{t_size:,}"))

        # kategorie
        kat_cnt = Counter(x.get("kategoria", "—") for x in s)
        max_cnt = max(kat_cnt.values(), default=1)
        lines_kat = []
        for kat, cnt in sorted(kat_cnt.items(), key=lambda x: -x[1]):
            bar = "█" * int(cnt / max_cnt * 20)
            lines_kat.append(f"  {kat:<14} {bar:<20} {cnt}")
        self._stat_kat_text.config(state="normal")
        self._stat_kat_text.delete("1.0", "end")
        self._stat_kat_text.insert("1.0", "\n".join(lines_kat) if lines_kat else _tr("(brak danych)"))
        self._stat_kat_text.config(state="disabled")

        # tagi
        top_tags = tags.most_common(15)
        max_t = top_tags[0][1] if top_tags else 1
        lines_tag = []
        for tag, cnt in top_tags:
            bar = "█" * int(cnt / max_t * 18)
            lines_tag.append(f"  {tag:<16} {bar:<18} {cnt}")
        self._stat_tag_text.config(state="normal")
        self._stat_tag_text.delete("1.0", "end")
        self._stat_tag_text.insert("1.0", "\n".join(lines_tag) if lines_tag else _tr("(brak tagów)"))
        self._stat_tag_text.config(state="disabled")

        # największe skrypty
        sized = sorted(s, key=lambda x: len(x.get("kod", "")), reverse=True)[:10]
        lines_size = []
        for i, sc in enumerate(sized, 1):
            lc = len(sc.get("kod", "").splitlines())
            ch = len(sc.get("kod", ""))
            lines_size.append(_tr("  {i:2}. {n:<22} {lc:5} linii  {ch:6} zn").format(
                i=i, n=sc.get('nazwa','?')[:22], lc=lc, ch=ch))
        self._stat_size_text.config(state="normal")
        self._stat_size_text.delete("1.0", "end")
        self._stat_size_text.insert("1.0", "\n".join(lines_size) if lines_size else _tr("(brak)"))
        self._stat_size_text.config(state="disabled")

        # najczęściej uruchamiane (statystyki runnera)
        top_runs = sorted([x for x in s if int(x.get("uruchomien") or 0) > 0],
                          key=lambda x: -int(x.get("uruchomien") or 0))[:10]
        lines_run = []
        for i, sc in enumerate(top_runs, 1):
            ok = sc.get("ostatni_wynik") or "—"
            lines_run.append(
                f"  {i:2}. {sc.get('nazwa','?')[:22]:<22} {int(sc.get('uruchomien') or 0):4}×  "
                f"[{ok}]  {sc.get('ostatni_run') or '-'}")
        self._stat_run_text.config(state="normal")
        self._stat_run_text.delete("1.0", "end")
        self._stat_run_text.insert("1.0", "\n".join(lines_run) if lines_run else _tr("(brak uruchomień — F9 w zakładce Runner)"))
        self._stat_run_text.config(state="disabled")

    def _stat_export(self):
        from collections import Counter
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile="raport_skryptow.txt",
            filetypes=[("Text", "*.txt"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        s = self.skrypty
        tags = Counter()
        lines = 0
        for sc in s:
            for t in sc.get("tagi", "").split(","):
                t = t.strip()
                if t:
                    tags[t] += 1
            lines += len(sc.get("kod", "").splitlines())
        kat_cnt = Counter(x.get("kategoria", "—") for x in s)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = [
            "=" * 60,
            _tr("  RAPORT BAZY SKRYPTÓW — {ts}").format(ts=ts),
            "=" * 60,
            _tr("  Łącznie skryptów  : {n}").format(n=len(s)),
            _tr("  Kategorii         : {n}").format(n=len(kat_cnt)),
            _tr("  Unikalnych tagów  : {n}").format(n=len(tags)),
            _tr("  Łącznie linii kodu: {n}").format(n=f"{lines:,}"),
            "",
            _tr("── Według kategorii ──────────────────────────"),
        ]
        for kat, cnt in sorted(kat_cnt.items(), key=lambda x: -x[1]):
            report.append(_tr("  {kat:<20} {cnt} skryptów").format(kat=kat, cnt=cnt))
        report += ["", _tr("── Top 20 tagów ──────────────────────────────")]
        for tag, cnt in tags.most_common(20):
            report.append(f"  {tag:<20} {cnt}×")
        report += ["", _tr("── Lista wszystkich skryptów ─────────────────")]
        for i, sc in enumerate(s, 1):
            report.append(f"  {i:3}. [{sc.get('kategoria','?'):12}] {sc.get('nazwa','?')}")
        report.append("=" * 60)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(report))
        messagebox.showinfo(_tr("Eksport"), _tr("Raport zapisany:\n{path}").format(path=path))

    def _show_sub_statystyki(self):
        self._stat_refresh()
        self.sub_frames["statystyki_skr"].pack(fill="both", expand=True, padx=4, pady=4)

    def _show_sub_runner(self):
        runner = getattr(self, "_runner_main_frame", None)
        if runner is not None:
            runner.pack(fill="both", expand=True, padx=4, pady=4)
        self._runner_load_form()

    def _build_sub_runner(self):
        """Pod-zakładka Skrypty → Runner: wspólny panel wyjścia runnera."""
        self._build_runner_frame()

    def _ensure_runner_frame(self):
        """Buduje współdzielony Runner dopiero przy pierwszym otwarciu."""
        if getattr(self, "_runner_frame_built", False):
            return
        self._build_sub_runner()
        self._runner_frame_built = True

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: ZAAWANSOWANE (porównanie, duplikaty, masowe operacje)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_zaawansowane(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["zaawansowane"] = frame

        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        self._trw(tk.Label(top, text=_tr("⚙ Zaawansowane operacje na skryptach"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "⚙ Zaawansowane operacje na skryptach").pack(side="left")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # ── SEKCJA 1: Wyszukaj i zastąp ──────────────────────────────────────
        sec1 = self._trw(tk.LabelFrame(body, text=_tr(" 🔄 Znajdź i zastąp w kodach wszystkich skryptów "),
                             font=FONT_UI, bg=BG_DARK, fg=ACCENT_BLUE,
                             relief="flat", highlightthickness=1,
                             highlightbackground=BORDER_CLR, padx=10, pady=8), " 🔄 Znajdź i zastąp w kodach wszystkich skryptów ")
        sec1.pack(fill="x", pady=(0, 10))

        r1 = tk.Frame(sec1, bg=BG_DARK); r1.pack(fill="x", pady=2)
        self._trw(tk.Label(r1, text=_tr("Szukaj:  "), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                 width=12, anchor="w"), "Szukaj:  ").pack(side="left")
        self._zaw_find = tk.Entry(r1, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                   insertbackground=FG_WHITE, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER_CLR,
                                   highlightcolor=ACCENT_BLUE, width=40)
        self._zaw_find.pack(side="left", padx=4)

        r2 = tk.Frame(sec1, bg=BG_DARK); r2.pack(fill="x", pady=2)
        self._trw(tk.Label(r2, text=_tr("Zastąp:  "), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                 width=12, anchor="w"), "Zastąp:  ").pack(side="left")
        self._zaw_replace = tk.Entry(r2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      insertbackground=FG_WHITE, relief="flat",
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      highlightcolor=ACCENT_BLUE, width=40)
        self._zaw_replace.pack(side="left", padx=4)

        r3 = tk.Frame(sec1, bg=BG_DARK); r3.pack(fill="x", pady=4)
        self._zaw_regex_var   = tk.BooleanVar(value=False)
        self._zaw_case_var    = tk.BooleanVar(value=False)
        self._zaw_kat_var     = tk.StringVar(value="Wszystkie")
        self._trw(tk.Checkbutton(r3, text=_tr("Wyrażenie regularne (regex)"), variable=self._zaw_regex_var,
                       font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                       activebackground=BG_DARK, selectcolor=BG_INPUT), "Wyrażenie regularne (regex)").pack(side="left")
        self._trw(tk.Checkbutton(r3, text=_tr("Uwzględnij wielkość liter"), variable=self._zaw_case_var,
                       font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                       activebackground=BG_DARK, selectcolor=BG_INPUT), "Uwzględnij wielkość liter").pack(side="left", padx=16)
        self._trw(tk.Label(r3, text=_tr("Kategoria:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "Kategoria:").pack(side="left")
        self._trc(ttk.Combobox(r3, textvariable=self._zaw_kat_var,
                     values=list(_CAT_FILTER_CHOICES),
                     font=FONT_UI, style="Dark.TCombobox",
                     width=12, state="readonly"), _CAT_FILTER_CHOICES,
                  self._zaw_kat_var).pack(side="left", padx=6)

        r4 = tk.Frame(sec1, bg=BG_DARK); r4.pack(fill="x", pady=2)
        self._trw(tk.Button(r4, text=_tr("🔍 Podgląd zmian"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_preview_replace), "🔍 Podgląd zmian").pack(side="left", padx=(0, 6))
        self._trw(tk.Button(r4, text=_tr("✅ Zastąp we wszystkich"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._zaw_do_replace), "✅ Zastąp we wszystkich").pack(side="left", padx=(0, 6))

        self._zaw_replace_result = tk.Label(sec1, text="", font=("Consolas", 8),
                                             bg=BG_DARK, fg=FG_GRAY, anchor="w")
        self._zaw_replace_result.pack(fill="x")

        # ── SEKCJA 2: Duplikaty ───────────────────────────────────────────────
        sec2 = self._trw(tk.LabelFrame(body, text=_tr(" 🔎 Wykrywanie duplikatów "),
                             font=FONT_UI, bg=BG_DARK, fg="#e0c040",
                             relief="flat", highlightthickness=1,
                             highlightbackground=BORDER_CLR, padx=10, pady=8), " 🔎 Wykrywanie duplikatów ")
        sec2.pack(fill="x", pady=(0, 10))

        dup_top = tk.Frame(sec2, bg=BG_DARK)
        dup_top.pack(fill="x")
        self._zaw_dup_mode = tk.StringVar(value="nazwa")
        for val, txt in [("nazwa", "Po nazwie"), ("kod", "Po kodzie (hash)"), ("oba", "Nazwa i kod")]:
            self._trw(tk.Radiobutton(dup_top, text=_tr(txt), variable=self._zaw_dup_mode, value=val,
                           font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                           activebackground=BG_DARK, selectcolor=BG_INPUT), txt).pack(side="left", padx=8)
        self._trw(tk.Button(dup_top, text=_tr("🔍 Szukaj duplikatów"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_find_dups), "🔍 Szukaj duplikatów").pack(side="left", padx=10)
        self._trw(tk.Button(dup_top, text=_tr("🗑 Usuń duplikaty"), font=FONT_UI,
                  bg=BTN_ERR, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_ERR_HOVER,
                  command=self._zaw_remove_dups), "🗑 Usuń duplikaty").pack(side="left", padx=4)

        self._zaw_dup_result = tk.Text(sec2, font=("Consolas", 8), bg=BG_PANEL,
                                        fg=FG_WHITE, relief="flat", height=5,
                                        highlightthickness=0, state="disabled")
        self._zaw_dup_result.pack(fill="x", pady=(6, 0))

        # ── SEKCJA 3: Masowe operacje ─────────────────────────────────────────
        sec3 = self._trw(tk.LabelFrame(body, text=_tr(" ⚡ Masowe operacje "),
                             font=FONT_UI, bg=BG_DARK, fg="#6dde84",
                             relief="flat", highlightthickness=1,
                             highlightbackground=BORDER_CLR, padx=10, pady=8), " ⚡ Masowe operacje ")
        sec3.pack(fill="x", pady=(0, 10))

        mass_row1 = tk.Frame(sec3, bg=BG_DARK)
        mass_row1.pack(fill="x", pady=2)
        self._trw(tk.Label(mass_row1, text=_tr("Zmień kategorię na:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Zmień kategorię na:").pack(side="left")
        self._zaw_mass_kat_src = ttk.Combobox(mass_row1,
                                               values=CATEGORIES, font=FONT_UI,
                                               style="Dark.TCombobox", width=12, state="readonly")
        self._zaw_mass_kat_src.set("Python")
        self._zaw_mass_kat_src.pack(side="left", padx=6)
        self._trw(tk.Label(mass_row1, text=_tr("→"), font=FONT_BOLD, bg=BG_DARK, fg=FG_GRAY), "→").pack(side="left")
        self._zaw_mass_kat_dst = ttk.Combobox(mass_row1,
                                               values=CATEGORIES, font=FONT_UI,
                                               style="Dark.TCombobox", width=12, state="readonly")
        self._zaw_mass_kat_dst.set("Python")
        self._zaw_mass_kat_dst.pack(side="left", padx=6)
        self._trw(tk.Button(mass_row1, text=_tr("✅ Zmień"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_mass_change_kat), "✅ Zmień").pack(side="left", padx=4)

        mass_row2 = tk.Frame(sec3, bg=BG_DARK)
        mass_row2.pack(fill="x", pady=4)
        self._trw(tk.Label(mass_row2, text=_tr("Dodaj tag do kategorii:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Dodaj tag do kategorii:").pack(side="left")
        self._zaw_mass_tag_kat = self._trc(ttk.Combobox(mass_row2,
                                               values=list(_CAT_FILTER_CHOICES),
                                               font=FONT_UI, style="Dark.TCombobox",
                                               width=12, state="readonly"),
                                          _CAT_FILTER_CHOICES)
        self._zaw_mass_tag_kat.set(_tr("Wszystkie"))
        self._zaw_mass_tag_kat.pack(side="left", padx=6)
        self._zaw_mass_tag_val = tk.Entry(mass_row2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                           insertbackground=FG_WHITE, relief="flat",
                                           highlightthickness=1, highlightbackground=BORDER_CLR,
                                           highlightcolor=ACCENT_BLUE, width=18)
        self._zaw_mass_tag_val.pack(side="left", padx=4)
        self._trw(tk.Button(mass_row2, text=_tr("➕ Dodaj tag"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_mass_add_tag), "➕ Dodaj tag").pack(side="left", padx=4)

        mass_row3 = tk.Frame(sec3, bg=BG_DARK)
        mass_row3.pack(fill="x", pady=2)
        for txt, cmd in [
            ("📤 Eksportuj wszystkie jako ZIP", self._zaw_export_zip),
            ("📋 Eksportuj jako CSV",            self._zaw_export_csv),
            ("📥 Importuj CSV",                  self._zaw_import_csv),
        ]:
            self._trw(tk.Button(mass_row3, text=_tr(txt), font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=cmd), txt).pack(side="left", padx=4)

        # log zaawansowanych
        self._zaw_log = tk.Text(body, font=("Consolas", 8), bg=BG_PANEL,
                                 fg=FG_WHITE, relief="flat", height=5,
                                 highlightthickness=1, highlightbackground=BORDER_CLR,
                                 state="disabled")
        self._zaw_log.pack(fill="x", pady=(4, 0))
        self._zaw_log.tag_configure("ok",  foreground="#6dde84")
        self._zaw_log.tag_configure("err", foreground="#e05c5c")
        self._zaw_log.tag_configure("inf", foreground="#c8c040")

    def _zaw_log_msg(self, msg, tag="inf"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._zaw_log.config(state="normal")
        self._zaw_log.insert("end", f"[{ts}] {msg}\n", tag)
        self._zaw_log.see("end")
        self._zaw_log.config(state="disabled")

    def _zaw_preview_replace(self):
        phrase = self._zaw_find.get()
        if not phrase:
            messagebox.showinfo(_tr("Brak frazy"), _tr("Podaj frazę do wyszukania."))
            return
        import re as _re
        flags = 0 if self._zaw_case_var.get() else _re.IGNORECASE
        kat_filter = self._cb_canon(self._zaw_kat_var.get(), _CAT_FILTER_CHOICES)
        count = 0
        affected = 0
        for sc in self.skrypty:
            if kat_filter != "Wszystkie" and sc.get("kategoria") != kat_filter:
                continue
            kod = sc.get("kod", "")
            try:
                pat = phrase if self._zaw_regex_var.get() else _re.escape(phrase)
                hits = len(_re.findall(pat, kod, flags))
            except _re.error:
                hits = 0
            if hits:
                count += hits
                affected += 1
        self._zaw_replace_result.config(
            text=f"Znaleziono {count} wystąpień w {affected} skryptach.",
            fg="#e0c040")
        self._zaw_log_msg(f"Podgląd: '{phrase}' → {count} wystąpień w {affected} skryptach.", "inf")

    def _zaw_do_replace(self):
        phrase  = self._zaw_find.get()
        replace = self._zaw_replace.get()
        if not phrase:
            messagebox.showinfo(_tr("Brak frazy"), _tr("Podaj frazę do wyszukania."))
            return
        if not messagebox.askyesno(_tr("Zastąp"),
                                    f"Zastąpić '{phrase}' → '{replace}'\nwe wszystkich skryptach?"):
            return
        import re as _re
        flags = 0 if self._zaw_case_var.get() else _re.IGNORECASE
        kat_filter = self._cb_canon(self._zaw_kat_var.get(), _CAT_FILTER_CHOICES)
        total = 0; affected = 0
        for sc in self.skrypty:
            if kat_filter != "Wszystkie" and sc.get("kategoria") != kat_filter:
                continue
            kod = sc.get("kod", "")
            try:
                pat = phrase if self._zaw_regex_var.get() else _re.escape(phrase)
                new_kod, n = _re.subn(pat, replace, kod, flags=flags)
            except _re.error as ex:
                messagebox.showerror(_tr("Błąd regex"), str(ex)); return
            if n:
                sc["kod"] = new_kod
                total += n; affected += 1
        self._zaw_replace_result.config(
            text=f"✅ Zastąpiono {total} wystąpień w {affected} skryptach.", fg="#6dde84")
        self._zaw_log_msg(f"Zastąpiono {total}× w {affected} skryptach.", "ok")

    def _zaw_find_dups(self):
        import hashlib
        mode = self._zaw_dup_mode.get()
        seen = {}; dups = []
        for sc in self.skrypty:
            if mode == "nazwa":
                key = sc.get("nazwa", "").lower()
            elif mode == "kod":
                key = hashlib.md5(sc.get("kod", "").encode()).hexdigest()
            else:
                key = (sc.get("nazwa", "").lower(),
                       hashlib.md5(sc.get("kod", "").encode()).hexdigest())
            if key in seen:
                dups.append((sc.get("nazwa", "?"), seen[key]))
            else:
                seen[key] = sc.get("nazwa", "?")
        self._zaw_dup_result.config(state="normal")
        self._zaw_dup_result.delete("1.0", "end")
        if dups:
            for a, b in dups:
                self._zaw_dup_result.insert("end", f"  DUPLIKAT: '{a}'  ←→  '{b}'\n")
        else:
            self._zaw_dup_result.insert("end", "  ✅ Brak duplikatów.")
        self._zaw_dup_result.config(state="disabled")
        self._zaw_log_msg(f"Duplikaty: {len(dups)} znaleziono.", "ok" if not dups else "inf")

    def _zaw_remove_dups(self):
        import hashlib
        mode = self._zaw_dup_mode.get()
        before = len(self.skrypty)
        seen = set(); kept = []
        for sc in self.skrypty:
            if mode == "nazwa":
                key = sc.get("nazwa", "").lower()
            elif mode == "kod":
                key = hashlib.md5(sc.get("kod", "").encode()).hexdigest()
            else:
                key = (sc.get("nazwa", "").lower(),
                       hashlib.md5(sc.get("kod", "").encode()).hexdigest())
            if key not in seen:
                seen.add(key); kept.append(sc)
        removed = before - len(kept)
        if removed == 0:
            messagebox.showinfo(_tr("Brak duplikatów"), _tr("Nie znaleziono duplikatów do usunięcia."))
            return
        if messagebox.askyesno(_tr("Usuń duplikaty"), f"Usunąć {removed} duplikat(ów)?"):
            self.skrypty = kept
            self._update_count()
            self._refresh_lista()
            self._zaw_log_msg(f"Usunięto {removed} duplikatów.", "ok")

    def _zaw_mass_change_kat(self):
        src = self._zaw_mass_kat_src.get()
        dst = self._zaw_mass_kat_dst.get()
        if src == dst:
            messagebox.showinfo(_tr("Bez zmian"), _tr("Kategorie są identyczne."))
            return
        changed = 0
        for sc in self.skrypty:
            if sc.get("kategoria") == src:
                sc["kategoria"] = dst
                changed += 1
        self._zaw_log_msg(f"Zmieniono kategorię {src}→{dst} w {changed} skryptach.", "ok")
        self._refresh_lista()
        messagebox.showinfo(_tr("Zmieniono"), f"Zaktualizowano {changed} skryptów.")

    def _zaw_mass_add_tag(self):
        kat = self._cb_canon(self._zaw_mass_tag_kat.get(), _CAT_FILTER_CHOICES)
        tag = self._zaw_mass_tag_val.get().strip()
        if not tag:
            messagebox.showinfo(_tr("Brak tagu"), _tr("Wpisz tag do dodania."))
            return
        changed = 0
        for sc in self.skrypty:
            if kat != "Wszystkie" and sc.get("kategoria") != kat:
                continue
            existing = [t.strip() for t in sc.get("tagi", "").split(",") if t.strip()]
            if tag not in existing:
                existing.append(tag)
                sc["tagi"] = ", ".join(existing)
                changed += 1
        self._zaw_log_msg(f"Dodano tag '{tag}' do {changed} skryptów.", "ok")
        messagebox.showinfo(_tr("Dodano tag"), f"Tag '{tag}' dodany do {changed} skryptów.")

    def _zaw_export_zip(self):
        import zipfile, io
        if not self.skrypty:
            messagebox.showinfo(_tr("Brak skryptów"), _tr("CodeMate jest pusta."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", initialfile="skrypty.zip",
            filetypes=[("ZIP", "*.zip"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for sc in self.skrypty:
                kat = sc.get("kategoria", "Other")
                ext = RUNNER_EXT.get(kat, ".txt")
                fname = f"{kat}/{sc.get('nazwa','skrypt')}{ext}"
                if ext == ".jar":
                    zf.writestr(fname, jar_bytes(sc.get("kod", "")))
                else:
                    zf.writestr(fname, sc.get("kod", ""))
        self._zaw_log_msg(f"Eksport ZIP: {len(self.skrypty)} skryptów → {path}", "ok")
        messagebox.showinfo(_tr("Eksport ZIP"), f"Zapisano {len(self.skrypty)} skryptów do:\n{path}")

    def _zaw_export_csv(self):
        import csv
        if not self.skrypty:
            messagebox.showinfo(_tr("Brak skryptów"), _tr("CodeMate jest pusta."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="skrypty.csv",
            filetypes=[("CSV", "*.csv"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        cols = ["nazwa", "kategoria", "tagi", "opis", "kod"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for sc in self.skrypty:
                w.writerow({c: sc.get(c, "") for c in cols})
        self._zaw_log_msg(f"Eksport CSV: {len(self.skrypty)} skryptów → {path}", "ok")
        messagebox.showinfo(_tr("Eksport CSV"), f"Zapisano:\n{path}")

    def _zaw_import_csv(self):
        import csv
        path = filedialog.askopenfilename(
            filetypes=[("CSV", "*.csv"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = [{k: (v if v is not None else "") for k, v in row.items()}
                        for row in reader if row.get("nazwa")]
            lista, _ = db_to_list(rows)
            added, updated, skipped, merged = self._merge_records(lista)
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            self._after_db_change()
            self._zaw_log_msg(f"Import CSV: +{added} nowych, ~{updated} zaktual., {skipped} pominiętych.", "ok")
            messagebox.showinfo(_tr("Import CSV"),
                                f"Dodane: {added}\nZaktualizowane: {updated}\nPominięte: {skipped}")
        except Exception as ex:
            messagebox.showerror(_tr("Błąd importu CSV"), str(ex))
            self._zaw_log_msg(f"Błąd importu CSV: {ex}", "err")

    def _show_sub_zaawansowane(self):
        self.sub_frames["zaawansowane"].pack(fill="both", expand=True, padx=4, pady=4)

    def _build_sub_kosz(self):
        """Pod-zakładka Kosz: przywracanie i trwałe usuwanie skryptów."""
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["kosz"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Label(bar, text=_tr("🗑 Kosz"), font=FONT_BOLD, bg=BG_PANEL,
                 fg="#e0c040"), "🗑 Kosz").pack(side="left")
        self._trash_badge = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#e0c040")
        self._trash_badge.pack(side="left", padx=6)
        for txt, cmd, color in (("↺ Przywróć", self._trash_restore, SUCCESS),
                                ("🗑 Usuń trwale", self._trash_delete_permanent, ERROR),
                                ("✕ Opróżnij kosz", self._trash_clear, FG_WHITE)):
            self._trw(tk.Button(bar, text=_tr(txt), font=FONT_UI, bg=BTN_DARK, fg=color, relief="flat",
                      padx=10, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                      activeforeground=color,
                      command=cmd), txt).pack(side="right", padx=3)

        cols = ("nazwa", "kategoria", "tagi", "usunięty", "zmieniony")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, w in zip(cols, (200, 110, 180, 140, 140)):
            self._trh(tree, c, c)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        tree.bind("<Double-1>", lambda e: self._trash_restore())
        self._trash_tree = tree

    def _show_sub_kosz(self):
        self._trash_fill()
        self.sub_frames["kosz"].pack(fill="both", expand=True, padx=4, pady=4)

    # ── Import / Eksport listy skryptów ───────────────────────────────────────
    def _lista_eksport_bsdb(self):
        """Eksport .bsdb — ZIP z bazą JSON i załącznikami (jeden plik do przenoszenia)."""
        import zipfile
        if not self.skrypty:
            messagebox.showinfo(_tr("Brak skryptów"), _tr("CodeMate jest pusta."))
            return
        path = filedialog.asksaveasfilename(
            title=_tr("Eksportuj bazę .bsdb"), defaultextension=".bsdb",
            initialfile="baza_skryptow.bsdb",
            filetypes=[(_tr("CodeMate (bundle)"), "*.bsdb"), ("ZIP", "*.zip")])
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("baza.json", json.dumps(db_wrap(self.skrypty),
                                                    ensure_ascii=False, indent=2))
                # załączniki: rekordy mogą mieć pole "pliki": {nazwa: tekst}
                n_att = 0
                for sc in self.skrypty:
                    for nazwa in (sc.get("pliki") or {}):
                        zf.writestr(f"zalaczniki/{sc.get('id','x')}/{nazwa}",
                                    str(sc["pliki"][nazwa]))
                        n_att += 1
                zf.writestr("README.txt",
                            "CodeMate v%s — format .bsdb (ZIP)\n"
                            "baza.json — dane (schema %d)\n"
                            "zalaczniki/<id>/ — pliki pomocnicze skryptów\n" % (APP_VER, DB_SCHEMA))
            msg = f"Wyeksportowano {len(self.skrypty)} skrypt(ów)"
            if n_att:
                msg += f" + {n_att} załączników"
            messagebox.showinfo(_tr("Eksport .bsdb"), msg + f"\n{path}")
        except Exception as e:
            messagebox.showerror(_tr("Błąd eksportu"), str(e))

    def _lista_import_bsdb(self):
        """Import .bsdb: scala rekordy z bazy.json i odłącza załączniki do pól."""
        import zipfile
        path = filedialog.askopenfilename(
            title=_tr("Importuj bazę .bsdb"),
            filetypes=[(_tr("CodeMate (bundle)"), "*.bsdb"), ("ZIP", "*.zip"),
                       (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                if "baza.json" not in names:
                    raise ValueError("Brak pliku baza.json w archiwum.")
                data = json.loads(zf.read("baza.json").decode("utf-8"))
                lista, notes = db_to_list(data)
                attach = {}
                for n in names:
                    if n.startswith("zalaczniki/") and not n.endswith("/"):
                        parts = n.split("/", 2)
                        if len(parts) == 3:
                            attach.setdefault(parts[1], {})[parts[2]] = \
                                zf.read(n).decode("utf-8", "replace")
            for sc in lista:
                if sc.get("id") in attach:
                    sc["pliki"] = attach[sc["id"]]
            self._merge_choice_cache = None
            added, updated, skipped, merged = self._merge_records(lista)
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            self._after_db_change()
            msg = (f"Import .bsdb: {path}\n\nDodane: {added}\nZaktualizowane: {updated}\n"
                   f"Pominięte: {skipped}\nZałączników: {sum(len(v) for v in attach.values())}")
            if notes:
                msg += "\n\n" + "\n".join(notes)
            messagebox.showinfo(_tr("Import .bsdb"), msg)
        except Exception as e:
            messagebox.showerror(_tr("Błąd importu"), str(e))

    def _lista_importuj(self):
        path = filedialog.askopenfilename(
            title=_tr("Importuj skrypty"),
            filetypes=[("JSON", "*.json"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        self._merge_choice_cache = None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            lista, notes = db_read(path) if isinstance(raw, dict) else db_to_list(raw)
            if not lista:
                raise ValueError("Plik nie zawiera żadnych rekordów skryptów.")
            added, updated, skipped, merged = self._merge_records(lista)
            self._rebuild_index()
            self._update_count()
            self._after_db_change()
            msg = (f"Import z:\n{path}\n\n"
                   f"Dodane:            {added}\n"
                   f"Zaktualizowane:  {updated}\n"
                   f"Pominięte:        {skipped}")
            if merged:
                msg += f"\nScalone duplikaty treści: {merged}"
            if notes:
                msg += "\n\n" + "\n".join(notes)
            messagebox.showinfo(_tr("Import"), msg)
        except Exception as e:
            messagebox.showerror(_tr("Błąd importu"), str(e))

    def _merge_records(self, incoming, ask=True):
        """
        Scalanie importu z bazą — dopasowanie po id, potem po nazwie.
        Zwraca (dodane, zaktualizowane, pominięte, scalone_duplikaty_treści).
        """
        by_id   = {s.get("id"): s for s in self.skrypty}
        by_name = {s.get("nazwa"): s for s in self.skrypty}
        sums   = {s.get("checksum") or kod_checksum(s.get("kod", "")) for s in self.skrypty}
        added = updated = skipped = merged = 0
        for sc in incoming:
            sc = sc_normalize(sc)
            old = by_id.get(sc["id"]) or by_name.get(sc["nazwa"])
            if old is None:
                if sc["checksum"] in sums and sc["kod"]:
                    merged += 1          # identyczna treść — nie dublujemy
                    continue
                self.skrypty.append(sc)
                by_id[sc["id"]] = sc
                by_name[sc["nazwa"]] = sc
                sums.add(sc["checksum"])
                added += 1
                continue
            same = (old.get("kod", "") == sc["kod"])
            if same:
                skipped += 1
                continue
            choice = "overwrite"
            if ask:
                choice = self._ask_conflict(old, sc)
            if choice == "skip":
                skipped += 1
            elif choice == "dup":
                sc["id"] = uuid.uuid4().hex
                sc["nazwa"] = f"{sc['nazwa']} (import)"
                self.skrypty.append(sc)
                by_id[sc["id"]] = sc
                added += 1
            else:
                old.update({k: sc[k] for k in ("kategoria", "tagi", "opis", "kod", "checksum")})
                old["zmieniony"] = sc["zmieniony"]
                updated += 1
        return added, updated, skipped, merged

    def _ask_conflict(self, old, new):
        """Dialog konfliktu przy scalaniu — decyzja dla jednego rekordu lub wszystkich."""
        if getattr(self, "_merge_choice_cache", None):
            return self._merge_choice_cache
        dlg = _popup(self)
        dlg.title(_tr("Konflikt importu"))
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text=f"Skrypt '{old.get('nazwa')}' istnieje w bazie i różni się treścią.",
                 font=FONT_UI, bg=BG_DARK, fg=FG_WHITE).pack(padx=14, pady=(12, 4))
        tk.Label(dlg, text=f"Lokalny: {old.get('zmieniony','?')}   |   Import: {new.get('zmieniony','?')}",
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(padx=14, pady=(0, 10))
        var = tk.StringVar(value="")
        result = {"v": "skip"}
        btns = tk.Frame(dlg, bg=BG_DARK)
        btns.pack(fill="x", padx=14, pady=(0, 12))

        def pick(v):
            result["v"] = v
            if var.get() == "all":
                self._merge_choice_cache = v
            dlg.destroy()

        for txt, v in (("Nadpisz", "overwrite"), ("Pomiń", "skip"), ("Duplikuj", "dup")):
            self._trw(tk.Button(btns, text=_tr(txt), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER, command=lambda v=v: pick(v)), txt).pack(side="left", padx=3)
        self._trw(tk.Checkbutton(dlg, text=_tr("zastosuj do wszystkich"), variable=var,
                       onvalue="all", offvalue="", bg=BG_DARK, fg=FG_GRAY,
                       selectcolor=BG_INPUT, activebackground=BG_DARK,
                       activeforeground=FG_WHITE, font=FONT_UI), "zastosuj do wszystkich").pack(padx=14, pady=(0, 10))
        self.wait_window(dlg)
        return result["v"]

    def _lista_eksportuj(self):
        if not self.skrypty:
            messagebox.showinfo(_tr("Brak skryptów"), _tr("CodeMate jest pusta."))
            return
        path = filedialog.asksaveasfilename(
            title=_tr("Eksportuj skrypty"),
            defaultextension=".json", initialfile="baza_skryptow.json",
            filetypes=[("JSON", "*.json"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        try:
            db_write(path, self.skrypty, backup_count=0)
            messagebox.showinfo(_tr("Eksport"), f"Wyeksportowano {len(self.skrypty)} skrypt(ów) do:\n{path}")
        except Exception as e:
            messagebox.showerror(_tr("Błąd eksportu"), str(e))

    def _refresh_lista(self):
        query = self.entry_search.get().lower().strip() if hasattr(self, "entry_search") else ""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, s in enumerate(self.skrypty):
            if s.get("usuniety"):
                continue
            if query and query not in s["nazwa"].lower() \
                     and query not in s["kategoria"].lower() \
                     and query not in s["tagi"].lower():
                continue
            opis_skrot = s["opis"][:80] + ("…" if len(s["opis"]) > 80 else "")
            tag = "odd" if i % 2 == 0 else "even"
            self.tree.insert("", "end", iid=str(i),
                             values=(s["nazwa"], kat_label(s["kategoria"]),
                                     s["tagi"], opis_skrot),
                             tags=(tag,))

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.skrypty):
            return
        kod = self.skrypty[idx]["kod"]
        self.text_preview.config(state="normal")
        self.text_preview.delete("1.0", "end")
        self.text_preview.insert("1.0", kod[:500] + ("…" if len(kod) > 500 else ""))
        self.text_preview.config(state="disabled")

    def _edytuj_skrypt(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz skrypt z listy."))
            return
        idx = int(sel[0])
        s = self.skrypty[idx]
        # załaduj do formularza
        self.entry_nazwa.delete(0, "end")
        self.entry_nazwa.insert(0, s["nazwa"])
        self.var_kat.set(s["kategoria"])
        self.entry_tagi.delete(0, "end")
        self.entry_tagi.insert(0, s["tagi"])
        self.text_opis.delete("1.0", "end")
        self.text_opis.insert("1.0", s["opis"])
        self.text_opis.config(fg=FG_WHITE)
        self.text_kod.delete("1.0", "end")
        self.text_kod.insert("1.0", s["kod"])
        self._update_line_nums()
        self._editing_nazwa = s["nazwa"]
        # Resetuj ramkę walidacji (edycja istniejącego)
        self.entry_nazwa.config(highlightbackground=BORDER_CLR,
                                highlightcolor=ACCENT_BLUE)
        # Podświetl składnię i odśwież pasek stanu
        self._highlighter.highlight(self.text_kod, s["kategoria"])
        self._update_status()
        # przejdź do zakładki Dodaj Skrypt
        self._sel_sub(0, self._show_sub_dodaj)

    def _sc_by_id(self, sid):
        """Szybkie wyszukanie rekordu po id (indeks budowany przy zmianach)."""
        idx = getattr(self, "_sc_index", None)
        if idx is None or len(idx) != len(self.skrypty):
            self._sc_index = {s.get("id"): i for i, s in enumerate(self.skrypty)}
            idx = self._sc_index
        return idx.get(sid)

    def _rebuild_index(self):
        """Przebudowuje indeksy: id → pozycja, tagi → zbiór id, checksum → zbiór id."""
        self._build_indexes()
        self._apply_edytor_spec()

    def _build_indexes(self):
        """Same indeksy — bez efektów ubocznych w UI (używane w __init__)."""
        from collections import defaultdict
        self._sc_index = {s.get("id"): i for i, s in enumerate(self.skrypty)}
        self._tag_index = defaultdict(set)
        self._checksum_index = defaultdict(set)
        for s in self.skrypty:
            for t in str(s.get("tagi", "")).split(","):
                t = t.strip().lower()
                if t:
                    self._tag_index[t].add(s.get("id"))
            self._checksum_index[s.get("checksum") or kod_checksum(s.get("kod", ""))].add(s.get("id"))

    def _apply_edytor_spec(self):
        spec = getattr(self, "_edytor_spec", None)
        if spec:
            if hasattr(self, "entry_nazwa"):
                self.entry_nazwa.delete(0, "end")
                self.entry_nazwa.insert(0, spec["nazwa"])
            self.var_kat.set(spec["kategoria"])
            if hasattr(self, "entry_tagi"):
                self.entry_tagi.delete(0, "end")
                self.entry_tagi.insert(0, spec["tagi"])
            if hasattr(self, "text_opis"):
                self.text_opis.delete("1.0", "end")
                self.text_opis.insert("1.0", spec["opis"] or "Opis skryptu…")
                self.text_opis.config(fg=FG_GRAY if not spec["opis"] else FG_WHITE)
            if hasattr(self, "text_kod"):
                self.text_kod.delete("1.0", "end")
                self.text_kod.insert("1.0", spec["kod"])
            self._edytor_spec = None
            self._edytor_current_idx = None
            self._editing_nazwa = None
            self._update_line_nums()
            self.entry_nazwa.config(highlightbackground=BORDER_CLR, highlightcolor=ACCENT_BLUE)
            self._highlighter.highlight(self.text_kod, spec["kategoria"])

    def _usun_skrypt(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz skrypt do usunięcia."))
            return
        idx = int(sel[0])
        nazwa = self.skrypty[idx]["nazwa"]
        if not messagebox.askyesno(_tr("Usuń"), f"Przenieść skrypt '{nazwa}' do kosza?"):
            return
        rec = dict(self.skrypty[idx])
        rec["usuniety"] = now_str()
        self.skrypty[idx] = rec
        self._trash_fill()
        self._after_db_change()
        self._refresh_lista()

    def _live_skrypty(self):
        """Tylko aktywne skrypty (bez kosza)."""
        return [s for s in self.skrypty if not s.get("usuniety")]

    def _trash_count(self):
        n = sum(1 for s in self.skrypty if s.get("usuniety"))
        if hasattr(self, "_trash_badge"):
            self._trash_badge.config(text=f"({n})" if n else "", fg="#e0c040")
        return n

    def _trash_stats(self) -> Tuple[int, int]:
        """Zwraca (liczba elementów kosza, łączny rozmiar kodu w znakach)."""
        n = 0
        size = 0
        for sc in self.skrypty:
            if sc.get("usuniety"):
                n += 1
                size += len(str(sc.get("kod") or ""))
        return n, size

    def _trash_purge_old(self) -> int:
        """Trwale usuwa elementy kosza starsze niż ``trash_days`` dni.

        ``trash_days`` = 0 wyłącza auto-czyszczenie. Zwraca liczbę usuniętych
        rekordów. Rekordy z nierozpoznaną datą usunięcia pozostają nietknięte.
        """
        try:
            days = int(self._cfg.get("trash_days", "0") or 0)
        except (TypeError, ValueError):
            days = 0
        if days <= 0:
            return 0
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        kept: List[Dict[str, Any]] = []
        removed = 0
        for sc in self.skrypty:
            us = sc.get("usuniety")
            if not us:
                kept.append(sc)
                continue
            try:
                dt = datetime.datetime.strptime(str(us), "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                kept.append(sc)
                continue
            if dt < cutoff:
                removed += 1
            else:
                kept.append(sc)
        if removed:
            self.skrypty = kept
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            if hasattr(self, "_trash_fill"):
                self._trash_fill()
            self._after_db_change()
        return removed

    def _trash_put(self, sc):
        """Miękkie usunięcie — rekord zostaje w bazie z datą usunięcia."""
        sc["usuniety"] = now_str()
        sc.setdefault("historia", [])
        return sc

    def _trash_restore(self):
        sel = self._trash_tree.selection() if hasattr(self, "_trash_tree") else ()
        if not sel:
            messagebox.showinfo(_tr("Kosz"), _tr("Zaznacz skrypt do przywrócenia."))
            return
        for iid in sel:
            try:
                rec = dict(self.skrypty[int(iid)])
            except (ValueError, IndexError):
                continue
            rec.pop("usuniety", None)
            self.skrypty[int(iid)] = rec
        self._rebuild_index()
        self._trash_fill()
        self._refresh_lista()
        self._update_count()
        self._after_db_change()

    def _trash_delete_permanent(self):
        sel = self._trash_tree.selection() if hasattr(self, "_trash_tree") else ()
        if not sel:
            return
        n = len(sel)
        if not messagebox.askyesno(_tr("Kosz"), f"Usunąć trwale {n} skrypt(ów)?\nTej operacji nie można cofnąć."):
            return
        idxs = sorted((int(i) for i in sel), reverse=True)
        for i in idxs:
            if 0 <= i < len(self.skrypty):
                self.skrypty.pop(i)
        self._rebuild_index()
        self._trash_fill()
        self._refresh_lista()
        self._update_count()
        self._after_db_change()

    def _trash_clear(self):
        n = self._trash_count()
        if not n:
            messagebox.showinfo(_tr("Kosz"), _tr("Kosz jest pusty."))
            return
        if messagebox.askyesno(_tr("Kosz"), f"Opróżnić kosz ({n} skrypt(ów))?"):
            self.skrypty = [s for s in self.skrypty if not s.get("usuniety")]
            self._rebuild_index()
            self._trash_fill()
            self._refresh_lista()
            self._update_count()
            self._after_db_change()

    def _trash_fill(self):
        if not hasattr(self, "_trash_tree"):
            return
        tree = self._trash_tree
        for row in tree.get_children():
            tree.delete(row)
        for i, sc in enumerate(self.skrypty):
            if not sc.get("usuniety"):
                continue
            tree.insert("", "end", iid=str(i), values=(
                sc.get("nazwa", "?"), sc.get("kategoria", "?"),
                sc.get("tagi", ""), sc.get("usuniety", ""),
                sc.get("zmieniony", "")))
        self._trash_count()

    def _kopiuj_kod_z_listy(self, tree=None):
        """Kopiuj kod zaznaczonego skryptu z Treeview do schowka."""
        if tree is None:
            tree = getattr(self, "tree", None)
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz skrypt z listy."))
            return
        idx = int(sel[0])
        if idx < len(self.skrypty):
            self.clipboard_clear()
            self.clipboard_append(self.skrypty[idx]["kod"])
            messagebox.showinfo(_tr("Skopiowano"), f"Kod skryptu '{self.skrypty[idx]['nazwa']}' skopiowany.")

    def _otworz_skrypt(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz skrypt do otwarcia."))
            return
        idx = int(sel[0])
        s = self.skrypty[idx]
        # przejdź do zakładki Edytor skryptów i załaduj skrypt
        self._sel_sub(2, self._show_sub_edytor)
        self._edytor_refresh()
        # znajdź i zaznacz na liście edytora
        items = self.edytor_listbox.get(0, "end")
        for i, name in enumerate(items):
            if name == s["nazwa"]:
                self.edytor_listbox.selection_clear(0, "end")
                self.edytor_listbox.selection_set(i)
                self.edytor_listbox.see(i)
                self._edytor_load_selected()
                break

    # ── placeholder głównych zakładek ─────────────────────────────────────────

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKLADKA: Szukaj - Advanced Pro
    # ══════════════════════════════════════════════════════════════════════════
    def _build_szukaj_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["szukaj"] = outer

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("Advanced Search Pro"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), "Advanced Search Pro").pack(side="left")
        self.lbl_search_stats = self._trw(tk.Label(hdr, text=_tr("Wynikow: -  |  Czas: -"),
                                          font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Wynikow: -  |  Czas: -")
        self.lbl_search_stats.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        paned = tk.Frame(outer, bg=BG_DARK)
        paned.pack(fill="both", expand=True)

        left = tk.Frame(paned, bg=BG_PANEL, width=305)
        left.pack(side="left", fill="y", padx=(6, 0), pady=6)
        left.pack_propagate(False)

        # Panel jest przewijany pionowo — zawartość może przekraczać wysokość okna.
        l_sb = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=10)
        l_sb.pack(side="right", fill="y")
        l_canvas = tk.Canvas(left, bg=BG_PANEL, highlightthickness=0,
                             yscrollcommand=l_sb.set)
        l_canvas.pack(side="left", fill="both", expand=True)
        l_sb.config(command=l_canvas.yview)
        left = tk.Frame(l_canvas, bg=BG_PANEL)
        l_win = l_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>",
                  lambda _e: l_canvas.configure(scrollregion=l_canvas.bbox("all")))
        l_canvas.bind("<Configure>",
                      lambda e: l_canvas.itemconfigure(l_win, width=e.width))

        def section(parent, title):
            tk.Frame(parent, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 2))
            self._trw(tk.Label(parent, text=_tr(title), font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), title).pack(anchor="w", padx=8)

        self._trw(tk.Label(left, text=_tr("Fraza / wyrazenie:"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "Fraza / wyrazenie:").pack(anchor="w", padx=8, pady=(10, 2))
        self.adv_entry = tk.Entry(left, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                   insertbackground=FG_WHITE, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER_CLR,
                                   highlightcolor=ACCENT_BLUE)
        self.adv_entry.pack(fill="x", padx=8, pady=(0, 4))
        self.adv_entry.bind("<Return>", lambda e: self._adv_search())
        self.adv_entry.bind("<KeyRelease>", self._adv_live_search)

        opts_row = tk.Frame(left, bg=BG_PANEL)
        opts_row.pack(fill="x", padx=8, pady=(0, 2))
        self.var_case  = tk.BooleanVar(value=False)
        self.var_whole = tk.BooleanVar(value=False)
        self.var_regex = tk.BooleanVar(value=False)
        self.var_fuzzy = tk.BooleanVar(value=False)
        for text, var in [("Aa Duze/male", self.var_case),
                          ("<> Cale slowo", self.var_whole),
                          (".* Regex",     self.var_regex),
                          ("~ Fuzzy",      self.var_fuzzy)]:
            self._trw(tk.Checkbutton(opts_row, text=_tr(text), variable=var,
                           font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search), text).pack(anchor="w", pady=0)

        section(left, "Operator logiczny")
        op_row = tk.Frame(left, bg=BG_PANEL)
        op_row.pack(fill="x", padx=8, pady=4)
        self.var_logic = tk.StringVar(value="AND")
        for op in ("AND", "OR", "NOT"):
            self._trw(tk.Radiobutton(op_row, text=_tr(op), variable=self.var_logic, value=op,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search), op).pack(side="left", padx=6)

        section(left, "Szukaj w polach")
        self.var_in_nazwa = tk.BooleanVar(value=True)
        self.var_in_kat   = tk.BooleanVar(value=True)
        self.var_in_tagi  = tk.BooleanVar(value=True)
        self.var_in_opis  = tk.BooleanVar(value=True)
        self.var_in_kod   = tk.BooleanVar(value=True)
        fields_frame = tk.Frame(left, bg=BG_PANEL)
        fields_frame.pack(fill="x", padx=8, pady=4)
        for text, var in [("Nazwa", self.var_in_nazwa), ("Kategoria", self.var_in_kat),
                          ("Tagi",  self.var_in_tagi),  ("Opis",      self.var_in_opis),
                          ("Kod",   self.var_in_kod)]:
            self._trw(tk.Checkbutton(fields_frame, text=_tr(text), variable=var,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search), text).pack(anchor="w", pady=1)

        section(left, "Kategoria")
        cat_frame = tk.Frame(left, bg=BG_PANEL)
        cat_frame.pack(fill="x", padx=8, pady=4)
        self.var_cats = {}
        for cat in ["Wszystkie"] + CATEGORIES:
            v = tk.BooleanVar(value=True)
            self.var_cats[cat] = v
            self._trw(tk.Checkbutton(cat_frame, text=_tr(cat), variable=v,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search), cat).pack(anchor="w", pady=1)

        section(left, "Filtr tagów (zawiera)")
        self.adv_tag_entry = tk.Entry(left, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                       insertbackground=FG_WHITE, relief="flat",
                                       highlightthickness=1, highlightbackground=BORDER_CLR,
                                       highlightcolor=ACCENT_BLUE)
        self.adv_tag_entry.pack(fill="x", padx=8, pady=4)
        self.adv_tag_entry.bind("<KeyRelease>", lambda e: self._adv_search())

        section(left, "Sortowanie")
        sort_row = tk.Frame(left, bg=BG_PANEL)
        sort_row.pack(fill="x", padx=8, pady=4)
        self._trw(tk.Label(sort_row, text=_tr("Pole:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Pole:").pack(side="left")
        self.var_sort_field = tk.StringVar(value="nazwa")
        self._trc(ttk.Combobox(sort_row, textvariable=self.var_sort_field,
                     values=["nazwa", "kategoria", "tagi"],
                     font=FONT_UI, state="readonly", style="Dark.TCombobox",
                     width=10), ("nazwa", "kategoria", "tagi"),
                  self.var_sort_field).pack(side="left", padx=4)
        self.var_sort_dir = tk.StringVar(value="ASC")
        for d in ("ASC", "DESC"):
            self._trw(tk.Radiobutton(sort_row, text=_tr(d), variable=self.var_sort_dir, value=d,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search), d).pack(side="left", padx=3)
        self.var_sort_field.trace_add("write", lambda *_: self._adv_search())

        section(left, "Limit wynikow")
        limit_row = tk.Frame(left, bg=BG_PANEL)
        limit_row.pack(fill="x", padx=8, pady=4)
        self.var_limit = tk.StringVar(value="Wszystkie")
        self._trc(ttk.Combobox(limit_row, textvariable=self.var_limit,
                     values=["Wszystkie", "5", "10", "20", "50"],
                     font=FONT_UI, state="readonly", style="Dark.TCombobox",
                     width=12), ("Wszystkie", "5", "10", "20", "50"),
                  self.var_limit).pack(side="left")
        self.var_limit.trace_add("write", lambda *_: self._adv_search())

        tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x", pady=(10, 4))
        btn_row = tk.Frame(left, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=8, pady=(0, 4))

        def sbtn(master, text, color, cmd):
            self._trw(tk.Button(master, text=_tr(text), font=FONT_UI,
                      bg=color, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER,
                      activeforeground=FG_WHITE, command=cmd), text).pack(side="left", padx=2, pady=2)

        sbtn(btn_row, "Szukaj",        BTN_ACCENT, self._adv_search)
        sbtn(btn_row, "Wyczysc filtry", BTN_DARK,    self._adv_clear)
        btn_row2 = tk.Frame(left, bg=BG_PANEL)
        btn_row2.pack(fill="x", padx=8, pady=(0, 8))
        sbtn(btn_row2, "Kopiuj wyniki", BTN_DARK, self._adv_copy_results)
        sbtn(btn_row2, "Eksportuj .txt", BTN_DARK, self._adv_export)

        # PRAWA: wyniki + zakladki wewnetrzne
        right = tk.Frame(paned, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        inner_bar = tk.Frame(right, bg=BG_PANEL)
        inner_bar.pack(fill="x")
        self._inner_btns   = []
        self._inner_frames = {}
        inner_content = tk.Frame(right, bg=BG_DARK)
        inner_content.pack(fill="both", expand=True)

        def _sel_inner(idx, frame_key):
            for j, ib in enumerate(self._inner_btns):
                ib.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                              fg=FG_WHITE       if j == idx else FG_GRAY)
            for f in self._inner_frames.values():
                f.pack_forget()
            self._inner_frames[frame_key].pack(fill="both", expand=True)
            self._update_minsize()

        for j, (lbl, key) in enumerate([("Wyniki","wyniki"),
                                         ("Historia","historia"),
                                         ("Statystyki","statystyki")]):
            ib = self._trw(tk.Button(inner_bar, text=_tr(lbl), font=FONT_UI,
                           bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                           fg=FG_WHITE       if j == 0 else FG_GRAY,
                           relief="flat", padx=12, pady=5, cursor="hand2",
                           bd=0, highlightthickness=0,
                           command=lambda j=j, k=key: _sel_inner(j, k)), lbl)
            ib.pack(side="left")
            self._inner_btns.append(ib)

        # Panel wynikow
        res_frame = tk.Frame(inner_content, bg=BG_DARK)
        self._inner_frames["wyniki"] = res_frame

        cols_adv = ("Nazwa", "Kategoria", "Tagi", "Opis", "Trafnosc")
        style2 = ttk.Style()
        style2.configure("Adv.Treeview",
                         background=BG_ROW_ODD, foreground=FG_WHITE,
                         fieldbackground=BG_ROW_ODD, rowheight=24, font=FONT_UI)
        style2.configure("Adv.Treeview.Heading",
                         background=BG_PANEL, foreground=FG_GRAY,
                         font=FONT_BOLD, relief="flat")
        style2.map("Adv.Treeview",
                   background=[("selected", BG_ROW_SEL)],
                   foreground=[("selected", FG_WHITE)])

        tree_wrap = tk.Frame(res_frame, bg=BG_DARK)
        tree_wrap.pack(fill="both", expand=True)
        vsb2 = tk.Scrollbar(tree_wrap, orient="vertical",
                             bg=BG_PANEL, troughcolor=BG_PANEL, width=10)
        vsb2.pack(side="right", fill="y")
        hsb2 = tk.Scrollbar(tree_wrap, orient="horizontal",
                             bg=BG_PANEL, troughcolor=BG_PANEL)
        hsb2.pack(side="bottom", fill="x")
        self.adv_tree = ttk.Treeview(tree_wrap, columns=cols_adv, show="headings",
                                      style="Adv.Treeview",
                                      yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.config(command=self.adv_tree.yview)
        hsb2.config(command=self.adv_tree.xview)
        for col, w in [("Nazwa",200),("Kategoria",90),
                       ("Tagi",160),("Opis",260),("Trafnosc",70)]:
            self._trh(self.adv_tree, col, col)
            self.adv_tree.heading(col, command=lambda c=col: self._adv_sort_col(c))
            self.adv_tree.column(col, width=w, minwidth=60)
        self.adv_tree.pack(fill="both", expand=True)
        self.adv_tree.tag_configure("odd",   background=BG_ROW_ODD)
        self.adv_tree.tag_configure("even",  background=BG_ROW_EVEN)
        self.adv_tree.tag_configure("match", background="#2e4a2e")
        self.adv_tree.bind("<<TreeviewSelect>>", self._adv_on_select)
        self.adv_tree.bind("<Double-1>", lambda e: self._adv_open_in_editor())

        tk.Frame(res_frame, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4,0))
        prev_row = tk.Frame(res_frame, bg=BG_DARK)
        prev_row.pack(fill="x", padx=4, pady=(4,2))
        self._trw(tk.Label(prev_row, text=_tr("Podglad kodu (dopasowanie podswietlone):"),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "Podglad kodu (dopasowanie podswietlone):").pack(side="left")
        self._trw(tk.Button(prev_row, text=_tr("Otworz w edytorze"),
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=8, pady=2, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._adv_open_in_editor), "Otworz w edytorze").pack(side="right", padx=4)
        self.adv_preview = tk.Text(res_frame, font=FONT_MONO,
                                    bg=BG_INPUT, fg="#c8d0f0",
                                    relief="flat", height=8, state="disabled",
                                    highlightthickness=1, highlightbackground=BORDER_CLR)
        self.adv_preview.pack(fill="x", padx=4, pady=(0,4))
        self.adv_preview.tag_configure("highlight",
                                        background="#5a3a00", foreground="#ffd080")

        # Panel historii
        hist_frame = tk.Frame(inner_content, bg=BG_DARK)
        self._inner_frames["historia"] = hist_frame
        hist_top = tk.Frame(hist_frame, bg=BG_PANEL, pady=6, padx=8)
        hist_top.pack(fill="x")
        self._trw(tk.Label(hist_top, text=_tr("Historia wyszukiwan"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "Historia wyszukiwan").pack(side="left")
        self._trw(tk.Label(hist_top, text=_tr("(dwuklik = przywroc zapytanie)"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "(dwuklik = przywroc zapytanie)").pack(side="left", padx=8)
        self._trw(tk.Button(hist_top, text=_tr("Wyczysc historię"),
                  font=FONT_UI, bg=BTN_DARK, fg="#e07070", relief="flat",
                  padx=8, pady=2, cursor="hand2",
                  command=self._adv_clear_history), "Wyczysc historię").pack(side="right")
        hist_cols = ("Fraza","Pola","Kategoria","Wynikow","Czas","Data")
        hist_vsb = tk.Scrollbar(hist_frame, orient="vertical",
                                 bg=BG_PANEL, troughcolor=BG_PANEL, width=10)
        self.hist_tree = ttk.Treeview(hist_frame, columns=hist_cols,
                                       show="headings", style="Adv.Treeview", height=14)
        for col, w in [("Fraza",160),("Pola",130),("Kategoria",90),
                       ("Wynikow",70),("Czas",70),("Data",130)]:
            self._trh(self.hist_tree, col, col)
            self.hist_tree.column(col, width=w, minwidth=50)
        self.hist_tree.configure(yscrollcommand=hist_vsb.set)
        hist_vsb.config(command=self.hist_tree.yview)
        self.hist_tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        hist_vsb.pack(side="left", fill="y", pady=4)
        self.hist_tree.tag_configure("odd",  background=BG_ROW_ODD)
        self.hist_tree.tag_configure("even", background=BG_ROW_EVEN)
        self.hist_tree.bind("<Double-1>", self._adv_recall_history)

        # Panel statystyk
        stat_frame = tk.Frame(inner_content, bg=BG_DARK)
        self._inner_frames["statystyki"] = stat_frame
        stat_top = tk.Frame(stat_frame, bg=BG_PANEL, pady=6, padx=8)
        stat_top.pack(fill="x")
        self._trw(tk.Label(stat_top, text=_tr("Statystyki bazy skryptow"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "Statystyki bazy skryptow").pack(side="left")
        self._trw(tk.Button(stat_top, text=_tr("Odswiez"),
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=8, pady=2, cursor="hand2",
                  command=self._adv_refresh_stats), "Odswiez").pack(side="right")
        self.stat_text = tk.Text(stat_frame, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                  relief="flat", state="disabled",
                                  highlightthickness=1, highlightbackground=BORDER_CLR)
        self.stat_text.pack(fill="both", expand=True, padx=4, pady=4)

        self._inner_frames["wyniki"].pack(fill="both", expand=True)
        self._adv_sort_state = {}

    def _show_szukaj(self):
        self.main_frames["szukaj"].pack(fill="both", expand=True)
        self._adv_refresh_stats()

    def _adv_live_search(self, event=None):
        if hasattr(self, "_adv_after_id"):
            self.after_cancel(self._adv_after_id)
        self._adv_after_id = self.after(300, self._adv_search)

    def _adv_search(self, event=None):
        t0 = datetime.datetime.now()
        query    = self.adv_entry.get().strip()
        tag_filt = self.adv_tag_entry.get().strip().lower()
        case_sen = self.var_case.get()
        whole    = self.var_whole.get()
        use_re   = self.var_regex.get()
        fuzzy    = self.var_fuzzy.get()
        logic    = self.var_logic.get()

        terms = query.split() if logic in ("AND", "OR") and not use_re else ([query] if query else [])
        if not case_sen:
            terms = [t.casefold() for t in terms]
        regex = None
        if use_re and query:
            try:
                regex = re.compile(query, 0 if case_sen else re.IGNORECASE)
            except re.error as exc:
                self.lbl_search_stats.config(text=_tr("Nieprawidłowe wyrażenie regularne: {exc}").format(exc=exc))
                return
        def match_term(text, term):
            if regex is not None:
                return regex.search(text) is not None
            haystack = text if case_sen else text.casefold()
            if whole:
                return re.search(r"\b" + re.escape(term) + r"\b", haystack) is not None
            if fuzzy and len(term) >= 3:
                return term[:3] in haystack
            return term in haystack

        def matches(skrypt):
            fields = []
            if self.var_in_nazwa.get(): fields.append(str(skrypt.get("nazwa", "")))
            if self.var_in_kat.get():   fields.append(str(skrypt.get("kategoria", "")))
            if self.var_in_tagi.get():  fields.append(str(skrypt.get("tagi", "")))
            if self.var_in_opis.get():  fields.append(str(skrypt.get("opis", "")))
            if self.var_in_kod.get():   fields.append(str(skrypt.get("kod", "")))
            if not terms:
                return True, 100
            hits = [any(match_term(field, term) for field in fields) for term in terms]
            if logic == "AND":
                ok = all(hits)
            elif logic == "OR":
                ok = any(hits)
            else:
                ok = not any(hits)
            score = int(sum(hits) * 100 / len(hits)) if ok and hits else 0
            return ok, score

        sel_cats = {c for c, v in self.var_cats.items() if v.get() and c != "Wszystkie"}
        all_cats_on = bool(self.var_cats.get("Wszystkie") and self.var_cats["Wszystkie"].get())
        if not all_cats_on and not sel_cats:
            self.lbl_search_stats.config(text=_tr("Wybierz co najmniej jedną kategorię."))
            return
        tag_filt = tag_filt.casefold()

        results = []
        for s in self.skrypty:
            if s.get("usuniety"):
                continue
            cat_ok = all_cats_on or (s.get("kategoria", "") in sel_cats)
            tag_ok = tag_filt in str(s.get("tagi", "")).casefold() if tag_filt else True
            ok, score = matches(s)
            if ok and cat_ok and tag_ok:
                results.append((score, s))

        sort_field = self._cb_canon(self.var_sort_field.get(), ("nazwa", "kategoria", "tagi"))
        sort_rev = self.var_sort_dir.get() == "DESC"
        results.sort(key=lambda x: str(x[1].get(sort_field, "")).casefold(), reverse=sort_rev)

        limit_val = self._cb_canon(self.var_limit.get(), ("Wszystkie", "5", "10", "20", "50"))
        if limit_val != "Wszystkie":
            try:
                limit = max(1, int(limit_val))
            except (TypeError, ValueError):
                limit = len(results)
            results = results[:limit]

        elapsed = int((datetime.datetime.now() - t0).total_seconds() * 1000)

        for row in self.adv_tree.get_children():
            self.adv_tree.delete(row)
        # Treeview IDs need to refer to stable records, not result positions.
        self._adv_result_ids = []
        for i, (score, s) in enumerate(results):
            opis_s = str(s.get("opis", ""))
            opis_skrot = opis_s[:70] + ("..." if len(opis_s) > 70 else "")
            row_tag = "match" if score >= 80 else ("odd" if i % 2 == 0 else "even")
            sid = str(s.get("id") or i)
            self._adv_result_ids.append(sid)
            self.adv_tree.insert("", "end", iid=sid,
                                  values=(s.get("nazwa", ""), kat_label(s.get("kategoria", "")),
                                          s.get("tagi", ""), opis_skrot, f"{score}%"),
                                  tags=(row_tag,))

        fields_active = [n for n, v in [("nazwa", self.var_in_nazwa), ("kat.", self.var_in_kat),
                                         ("tagi", self.var_in_tagi),  ("opis", self.var_in_opis),
                                         ("kod",  self.var_in_kod)] if v.get()]
        self.lbl_search_stats.config(
            text=_tr("Wynikow: {n} z {t}  |  Czas: {ms} ms").format(n=len(results), t=len(self.skrypty), ms=elapsed))

        if query or tag_filt:
            entry = {
                "fraza":   query or f"[tag:{tag_filt}]",
                "pola":    ",".join(fields_active),
                "kat":     ",".join(sel_cats) if not all_cats_on else "Wszystkie",
                "wynikow": len(results),
                "czas_ms": elapsed,
                "data":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.search_history.insert(0, entry)
            if len(self.search_history) > 100:
                self.search_history = self.search_history[:100]
            self._adv_refresh_history()

        self.adv_preview.config(state="normal")
        self.adv_preview.delete("1.0", "end")
        self.adv_preview.config(state="disabled")

    def _adv_on_select(self, event=None):
        sel = self.adv_tree.selection()
        if not sel:
            return
        skrypt = next((s for s in self.skrypty if str(s.get("id")) == sel[0]), None)
        if not skrypt:
            return
        code = str(skrypt.get("kod", ""))
        preview = code[:600] + ("..." if len(code) > 600 else "")
        self.adv_preview.config(state="normal")
        self.adv_preview.delete("1.0", "end")
        self.adv_preview.tag_remove("highlight", "1.0", "end")
        self.adv_preview.insert("1.0", preview)
        query = self.adv_entry.get().strip()
        try:
            if query:
                flags = 0 if self.var_case.get() else re.IGNORECASE
                pattern = query if self.var_regex.get() else re.escape(query)
                for match in re.finditer(pattern, preview, flags):
                    start = match.start()
                    end = match.end()
                    start_idx = f"{preview.count(chr(10), 0, start) + 1}.{start - preview.rfind(chr(10), 0, start) - 1}"
                    end_idx = f"{preview.count(chr(10), 0, end) + 1}.{end - preview.rfind(chr(10), 0, end) - 1}"
                    self.adv_preview.tag_add("highlight", start_idx, end_idx)
        except re.error:
            pass
        self.adv_preview.config(state="disabled")

    def _adv_open_in_editor(self):
        sel = self.adv_tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz skrypt z listy wyników."))
            return
        skrypt = next((s for s in self.skrypty if str(s.get("id")) == sel[0]), None)
        if not skrypt:
            return
        self.entry_nazwa.delete(0, "end")
        self.entry_nazwa.insert(0, skrypt.get("nazwa", ""))
        self.var_kat.set(skrypt.get("kategoria", "Other"))
        self.entry_tagi.delete(0, "end")
        self.entry_tagi.insert(0, skrypt.get("tagi", ""))
        self.text_opis.delete("1.0", "end")
        self.text_opis.insert("1.0", skrypt.get("opis", ""))
        self.text_opis.config(fg=FG_WHITE)
        self.text_kod.delete("1.0", "end")
        self.text_kod.insert("1.0", skrypt.get("kod", ""))
        self._editing_nazwa = skrypt.get("nazwa")
        self._edytor_current_idx = self._sc_by_id(skrypt.get("id"))
        self._update_line_nums()
        self._update_status()
        self._highlighter.highlight(self.text_kod, self.var_kat.get())
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(0, self._show_sub_dodaj)

    def _adv_clear(self):
        self.adv_entry.delete(0, "end")
        self.adv_tag_entry.delete(0, "end")
        self.var_case.set(False); self.var_whole.set(False)
        self.var_regex.set(False); self.var_fuzzy.set(False)
        self.var_logic.set("AND")
        for v in [self.var_in_nazwa, self.var_in_kat, self.var_in_tagi,
                  self.var_in_opis, self.var_in_kod]:
            v.set(True)
        for v in self.var_cats.values():
            v.set(True)
        self.var_limit.set(_tr("Wszystkie"))
        self.var_sort_field.set(_tr("nazwa")); self.var_sort_dir.set("ASC")
        for row in self.adv_tree.get_children():
            self.adv_tree.delete(row)
        self.adv_preview.config(state="normal")
        self.adv_preview.delete("1.0", "end")
        self.adv_preview.config(state="disabled")
        self.lbl_search_stats.config(text=_tr("Wynikow: -  |  Czas: -"))

    def _adv_copy_results(self):
        rows = ["	".join(str(v) for v in self.adv_tree.item(iid)["values"])
                for iid in self.adv_tree.get_children()]
        if rows:
            self.clipboard_clear(); self.clipboard_append("\n".join(rows))
            messagebox.showinfo(_tr("Skopiowano"), _tr("Skopiowano {n} wierszy do schowka.").format(n=len(rows)))
        else:
            messagebox.showinfo(_tr("Brak wynikow"), _tr("Brak wynikow do skopiowania."))

    def _adv_export(self):
        rows = ["	".join(str(v) for v in self.adv_tree.item(iid)["values"])
                for iid in self.adv_tree.get_children()]
        if not rows:
            messagebox.showinfo(_tr("Brak wynikow"), _tr("Brak wynikow do eksportu.")); return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_tr("Plik tekstowy"),"*.txt"),("CSV","*.csv")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(_tr("Nazwa\tKategoria\tTagi\tOpis\tTrafnosc\n") + "\n".join(rows))
            messagebox.showinfo(_tr("Eksport"), _tr("Wyeksportowano {n} wierszy do:\n{path}").format(n=len(rows), path=path))

    def _adv_sort_col(self, col):
        state = self._adv_sort_state.get(col, False)
        self._adv_sort_state[col] = not state
        items = [(self.adv_tree.set(iid, col), iid) for iid in self.adv_tree.get_children()]
        items.sort(reverse=state)
        for idx, (_, iid) in enumerate(items):
            self.adv_tree.move(iid, "", idx)

    def _adv_refresh_history(self):
        for row in self.hist_tree.get_children():
            self.hist_tree.delete(row)
        for i, h in enumerate(self.search_history[:50]):
            self.hist_tree.insert("", "end", iid=str(i),
                                   values=(h["fraza"], h["pola"], h["kat"],
                                           h["wynikow"], f"{h['czas_ms']} ms", h["data"]),
                                   tags=("odd" if i % 2 == 0 else "even",))

    def _adv_clear_history(self):
        if messagebox.askyesno(_tr("Wyczysc"), _tr("Wyczyścić całą historię wyszukiwań?")):
            self.search_history.clear()
            self._adv_refresh_history()

    def _adv_recall_history(self, event=None):
        sel = self.hist_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.search_history):
            return
        self.adv_entry.delete(0, "end")
        self.adv_entry.insert(0, self.search_history[idx]["fraza"])
        self._adv_search()
        for j, ib in enumerate(self._inner_btns):
            ib.configure(bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY)
        for f in self._inner_frames.values():
            f.pack_forget()
        self._inner_frames["wyniki"].pack(fill="both", expand=True)

    def _adv_refresh_stats(self):
        if not hasattr(self, "stat_text"):
            return
        total = len(self.skrypty)
        by_cat = {}
        total_lines = 0
        for s in self.skrypty:
            cat = s.get("kategoria", "?")
            by_cat[cat] = by_cat.get(cat, 0) + 1
            total_lines += s.get("kod", "").count("\n") + 1
        lines = ["=" * 44, _tr("  CodeMate - Statystyki"), "=" * 44,
                 _tr("  Laczna liczba skryptow  : {n}").format(n=total),
                 _tr("  Laczna liczba linii kodu : {n}").format(n=total_lines),
                 _tr("  Wpisy historii wyszukiwan: {n}").format(n=len(self.search_history)),
                 "", _tr("  Rozklad wg kategorii:"), "  " + "-" * 42]
        for cat in CATEGORIES:
            count = by_cat.get(cat, 0)
            bar = chr(9608) * count + chr(9617) * max(0, 10 - count)
            pct = (count / total * 100) if total else 0
            lines.append(f"  {cat:<12} {bar}  {count:>3}  ({pct:.1f}%)")
        lines += ["", _tr("  Ostatnio wyszukiwane:"), "  " + "-" * 42]
        for h in self.search_history[:5]:
            lines.append(_tr("  [{data}]  \"{fraza}\"  -> {n} wynikow").format(data=h['data'], fraza=h['fraza'], n=h['wynikow']))
        if not self.search_history:
            lines.append(_tr("  (brak historii)"))
        lines.append("=" * 44)
        self.stat_text.config(state="normal")
        self.stat_text.delete("1.0", "end")
        self.stat_text.insert("1.0", "\n".join(lines))
        self.stat_text.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Moduły — 5 pod-zakładek
    # ══════════════════════════════════════════════════════════════════════════
    def _build_moduly_frame(self):
        if getattr(self, "_moduly_building", False):
            return
        self._moduly_building = True
        try:
            self._build_moduly_frame_inner()
        finally:
            self._moduly_building = False

    def _build_moduly_frame_inner(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["moduly"] = outer

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=10, padx=12,
                       highlightthickness=1, highlightbackground=BORDER_CLR)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("⚙ Moduły — Centrum Zarządzania"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), "⚙ Moduły — Centrum Zarządzania").pack(side="left")
        self.lbl_mod_status = self._trw(tk.Label(hdr, text=_tr("Status: gotowy"),
                                        font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3"), "Status: gotowy")
        self.lbl_mod_status.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4, 0))

        mod_sub_bar = tk.Frame(outer, bg=BG_PANEL, pady=6, padx=8,
                               highlightthickness=1, highlightbackground=BORDER_CLR)
        mod_sub_bar.pack(fill="x")

        mod_content = tk.Frame(outer, bg=BG_DARK, pady=8)
        mod_content.pack(fill="both", expand=True)

        self._mod_btns   = []
        self._mod_frames = {}

        def sel_mod(idx, key):
            for j, b in enumerate(self._mod_btns):
                b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                             fg=FG_WHITE       if j == idx else FG_GRAY,
                             highlightbackground=BORDER_CLR if j != idx else ACCENT_BLUE,
                             highlightthickness=1)
            for f in self._mod_frames.values():
                f.pack_forget()
            self._mod_frames[key].pack(fill="both", expand=True)
            self._update_minsize()

        mod_tabs = [
            ("📋 Info",           "info"),
            ("🔬 Diagnostyka",    "diag"),
            ("🔗 Łączenie funkcji","laczen"),
            ("🕸 Graf zależności", "graf"),
            ("⚡ Testy osiągów",  "testy"),
            ("🔧 Naprawa",        "naprawa"),
            ("🔌 Kreator Pluginów","plugin"),
        ]
        for j, (lbl, key) in enumerate(mod_tabs):
            b = self._trw(tk.Button(mod_sub_bar, text=_tr(lbl), font=FONT_UI,
                          bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY,
                          relief="flat", padx=12, pady=6, cursor="hand2",
                          bd=0, highlightthickness=1,
                          highlightbackground=BORDER_CLR if j != 0 else ACCENT_BLUE,
                          activebackground=BG_SUBTAB_ACT,
                          command=lambda j=j, k=key: sel_mod(j, k)), lbl)
            b.pack(side="left", padx=(0, 4), pady=2)
            self._mod_btns.append(b)

        # Buduj każdą pod-zakładkę
        self._build_mod_info(mod_content)
        self._build_mod_diag(mod_content)
        self._build_mod_laczen(mod_content)
        self._build_mod_graf(mod_content)
        self._build_mod_testy(mod_content)
        self._build_mod_naprawa(mod_content)
        self._build_mod_plugin(mod_content)

        # pokaż pierwszą
        sel_mod(0, "info")

    def _show_moduly(self):
        self.main_frames["moduly"].pack(fill="both", expand=True, padx=8, pady=8)

    def _ensure_moduly_built(self):
        """Buduje zakładkę Moduły, jeśli jeszcze nie istnieje (lazy tabs)."""
        if ("tab_moduly" not in self._main_tabs_built
                and not getattr(self, "_moduly_building", False)):
            self._build_moduly_frame()
            self._main_tabs_built.add("tab_moduly")

    # ── helper: sekcja nagłówkowa ─────────────────────────────────────────────
    def _mod_section(self, parent, title):
        tk.Frame(parent, bg=BORDER_CLR, height=1).pack(fill="x", pady=(10, 2))
        wrap = tk.Frame(parent, bg=BG_PANEL, padx=8, pady=4,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        wrap.pack(fill="x", padx=8, pady=(0, 4))
        self._trw(tk.Label(wrap, text=_tr(title), font=FONT_BOLD, bg=BG_PANEL,
                 fg=ACCENT_BLUE), title).pack(anchor="w", padx=4, pady=2)

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 1: INFO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_info(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["info"] = frame

        # górny pasek przycisków
        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("🔄 Odśwież info"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._mod_refresh_info), "🔄 Odśwież info").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("📋 Kopiuj raport"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._mod_copy_info), "📋 Kopiuj raport").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("💾 Eksportuj raport"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._mod_export_info), "💾 Eksportuj raport").pack(side="left", padx=2)
        tk.Frame(bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=4)
        self._trw(tk.Button(bar, text=_tr("📥 Załaduj"), font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("info")), "📥 Załaduj").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("🔌 Odłącz"), font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("info")), "🔌 Odłącz").pack(side="left", padx=2)

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # dwie kolumny
        cols = tk.Frame(frame, bg=BG_DARK)
        cols.pack(fill="both", expand=True, padx=8, pady=6)

        left_col = tk.Frame(cols, bg=BG_PANEL, relief="flat",
                             highlightthickness=1, highlightbackground=BORDER_CLR)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 4))
        right_col = tk.Frame(cols, bg=BG_PANEL, relief="flat",
                              highlightthickness=1, highlightbackground=BORDER_CLR)
        right_col.pack(side="left", fill="both", expand=True, padx=(4, 0))

        # ─ Lewa kolumna: info systemowe ───────────────────────────────────────
        self._trw(tk.Label(left_col, text=_tr("📦 Informacje o bazie skryptów"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "📦 Informacje o bazie skryptów").pack(anchor="w", padx=10, pady=(8, 4))

        self.info_text = tk.Text(left_col, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                  relief="flat", state="disabled", wrap="word",
                                  highlightthickness=1, highlightbackground=BORDER_CLR)
        sc1 = tk.Scrollbar(left_col, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8, command=self.info_text.yview)
        sc1.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.info_text.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        self.info_text.config(yscrollcommand=sc1.set)

        # ─ Prawa kolumna: środowisko Python ──────────────────────────────────
        self._trw(tk.Label(right_col, text=_tr("🐍 Środowisko Python"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "🐍 Środowisko Python").pack(anchor="w", padx=10, pady=(8, 4))

        self.info_env_text = tk.Text(right_col, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      relief="flat", state="disabled", wrap="word",
                                      highlightthickness=1, highlightbackground=BORDER_CLR)
        sc2 = tk.Scrollbar(right_col, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8, command=self.info_env_text.yview)
        sc2.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.info_env_text.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        self.info_env_text.config(yscrollcommand=sc2.set)

        self._mod_refresh_info()

    def _mod_refresh_info(self):
        import sys, platform
        self._ensure_moduly_built()
        total   = len(self.skrypty)
        by_cat  = {}
        lines_t = 0
        tags_all = set()
        for s in self.skrypty:
            c = s.get("kategoria", "?")
            by_cat[c] = by_cat.get(c, 0) + 1
            lines_t += s.get("kod", "").count("\n") + 1
            for t in s.get("tagi", "").split(","):
                if t.strip():
                    tags_all.add(t.strip())

        lines = [
            "=" * 46,
            _tr("  CodeMate — Pełny raport informacyjny"),
            "=" * 46,
            _tr("  Wersja aplikacji    : 3.0"),
            _tr("  Data / czas         : {d}").format(d=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            "",
            _tr("  ── Zawartość bazy ──────────────────────"),
            _tr("  Łączna liczba skryptów : {n}").format(n=total),
            _tr("  Łączna liczba linii    : {n}").format(n=lines_t),
            _tr("  Unikalne tagi          : {n}").format(n=len(tags_all)),
            _tr("  Wpisy historii szukaj  : {n}").format(n=len(self.search_history)),
            "",
            _tr("  ── Rozkład wg kategorii ────────────────"),
        ]
        for cat in CATEGORIES:
            cnt = by_cat.get(cat, 0)
            bar = "█" * cnt + "░" * max(0, 12 - cnt)
            pct = (cnt / total * 100) if total else 0
            lines.append(f"  {cat:<12} {bar}  {cnt:>3}  ({pct:.1f}%)")

        if tags_all:
            lines += ["", _tr("  ── Popularne tagi ──────────────────────")]
            for t in sorted(tags_all)[:20]:
                lines.append(f"  • {t}")

        lines += ["", "=" * 46]
        self._set_text(self.info_text, "\n".join(lines))

        env_lines = [
            "=" * 46,
            _tr("  ŚRODOWISKO PYTHON"),
            "=" * 46,
            _tr("  Python              : {v}").format(v=sys.version.split()[0]),
            _tr("  Platform            : {os} {rel}").format(os=platform.system(), rel=platform.release()),
            _tr("  Architektura        : {v}").format(v=platform.machine()),
            _tr("  Procesor            : {v}").format(v=platform.processor() or 'n/d'),
            _tr("  Plik wykonywalny    : {v}").format(v=sys.executable),
            _tr("  Kodowanie           : {v}").format(v=sys.getdefaultencoding().upper()),
            "",
            _tr("  ── Zainstalowane moduły (stdlib) ───────"),
        ]
        stdlib_mods = ["os", "sys", "re", "json", "datetime", "pathlib",
                       "subprocess", "threading", "tkinter", "collections",
                       "itertools", "functools", "math", "random", "hashlib"]
        for mod in stdlib_mods:
            try:
                __import__(mod)
                env_lines.append(f"  ✔ {mod}")
            except ImportError:
                env_lines.append(f"  ✘ {mod}")
        env_lines.append("=" * 46)
        self._set_text(self.info_env_text, "\n".join(env_lines))

    def _mod_copy_info(self):
        self._ensure_moduly_built()
        content = self.info_text.get("1.0", "end-1c") + "\n\n" + self.info_env_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo(_tr("Skopiowano"), _tr("Raport skopiowany do schowka."))

    def _mod_export_info(self):
        self._ensure_moduly_built()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_tr("Plik tekstowy"), "*.txt"), (_tr("Wszystkie"), "*.*")])
        if path:
            content = self.info_text.get("1.0", "end-1c") + "\n\n" + self.info_env_text.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo(_tr("Eksport"), _tr("Raport zapisany:\n{path}").format(path=path))

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 2: DIAGNOSTYKA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_diag(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["diag"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("▶ Uruchom diagnostykę"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._run_diag), "▶ Uruchom diagnostykę").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("🧹 Wyczyść log"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=lambda: self._set_text(self.diag_text, "")), "🧹 Wyczyść log").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("💾 Zapisz log"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._diag_save_log), "💾 Zapisz log").pack(side="left", padx=2)
        self.lbl_diag_ok = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_diag_ok.pack(side="right", padx=8)
        self._trw(tk.Button(bar, text=_tr("🔌 Odłącz"), font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("diag")), "🔌 Odłącz").pack(side="right", padx=2)
        self._trw(tk.Button(bar, text=_tr("📥 Załaduj"), font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("diag")), "📥 Załaduj").pack(side="right", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # checkboxy testów
        chk_row = tk.Frame(frame, bg=BG_DARK)
        chk_row.pack(fill="x", padx=8, pady=(6, 2))
        self.diag_checks = {}
        tests = [
            ("Spójność danych",    "spojnosc"),
            ("Brakujące pola",     "pola"),
            ("Duplikaty nazw",     "duplikaty"),
            ("Puste skrypty",      "puste"),
            ("Kodowanie UTF-8",    "utf8"),
            ("Składnia Python",    "skladnia"),
            ("Niebezpieczne kody", "niebezp"),
        ]
        for i, (lbl, key) in enumerate(tests):
            v = tk.BooleanVar(value=True)
            self.diag_checks[key] = v
            self._trw(tk.Checkbutton(chk_row, text=_tr(lbl), variable=v, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT), lbl).grid(row=i // 4, column=i % 4,
                           padx=8, pady=2, sticky="w")

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4, 0))

        self.diag_text = tk.Text(frame, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                  relief="flat", wrap="word",
                                  highlightthickness=1, highlightbackground=BORDER_CLR)
        sc = tk.Scrollbar(frame, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=8, command=self.diag_text.yview)
        sc.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.diag_text.pack(fill="both", expand=True, padx=8, pady=6)
        self.diag_text.config(yscrollcommand=sc.set)

        # tagi kolorów logu
        self.diag_text.tag_configure("ok",    foreground="#6dde84")
        self.diag_text.tag_configure("warn",  foreground="#f0c050")
        self.diag_text.tag_configure("error", foreground="#e07070")
        self.diag_text.tag_configure("head",  foreground=ACCENT_BLUE)

    def _run_diag(self):
        import ast
        self._menu_pokaz_mod("diag")
        self.diag_text.config(state="normal")
        self.diag_text.delete("1.0", "end")
        errors = 0
        warnings = 0

        def log(msg, tag=""):
            self.diag_text.insert("end", msg + "\n", tag)

        log("=" * 54, "head")
        log(_tr("  DIAGNOSTYKA — {d}").format(d=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')), "head")
        log(_tr("  Skryptów w bazie: {n}").format(n=len(self.skrypty)), "head")
        log("=" * 54, "head")

        # 1. Spójność danych
        if self.diag_checks["spojnosc"].get():
            log(_tr("\n[1] Spójność danych"), "head")
            required = ["nazwa", "kategoria", "tagi", "opis", "kod"]
            for i, s in enumerate(self.skrypty):
                missing = [f for f in required if f not in s]
                if missing:
                    log(_tr("  ✘ Skrypt #{i} '{nazwa}' — brak pól: {missing}").format(i=i, nazwa=s.get('nazwa','?'), missing=missing), "error")
                    errors += 1
                else:
                    log(_tr("  ✔ Skrypt #{i} '{nazwa}' — OK").format(i=i, nazwa=s['nazwa']), "ok")

        # 2. Brakujące pola
        if self.diag_checks["pola"].get():
            log(_tr("\n[2] Brakujące / puste pola"), "head")
            for i, s in enumerate(self.skrypty):
                empty = [f for f in ["nazwa", "kategoria", "kod"] if not s.get(f, "").strip()]
                if empty:
                    log(_tr("  ⚠ Skrypt #{i} '{nazwa}' — puste: {empty}").format(i=i, nazwa=s.get('nazwa','?'), empty=empty), "warn")
                    warnings += 1
                else:
                    log(_tr("  ✔ Skrypt #{i} '{nazwa}' — wszystkie pola wypełnione").format(i=i, nazwa=s.get('nazwa','?')), "ok")

        # 3. Duplikaty
        if self.diag_checks["duplikaty"].get():
            log(_tr("\n[3] Duplikaty nazw"), "head")
            names = [s.get("nazwa", "") for s in self.skrypty]
            seen = set()
            dups = set()
            for n in names:
                if n in seen:
                    dups.add(n)
                seen.add(n)
            if dups:
                for d in dups:
                    log(_tr("  ✘ Duplikat: '{d}'").format(d=d), "error")
                    errors += 1
            else:
                log(_tr("  ✔ Brak duplikatów nazw"), "ok")

        # 4. Puste skrypty
        if self.diag_checks["puste"].get():
            log(_tr("\n[4] Puste skrypty (bez kodu)"), "head")
            any_empty = False
            for i, s in enumerate(self.skrypty):
                if not s.get("kod", "").strip():
                    log(_tr("  ⚠ Skrypt #{i} '{nazwa}' — brak kodu!").format(i=i, nazwa=s.get('nazwa','?')), "warn")
                    warnings += 1
                    any_empty = True
            if not any_empty:
                log(_tr("  ✔ Wszystkie skrypty mają kod"), "ok")

        # 5. UTF-8
        if self.diag_checks["utf8"].get():
            log(_tr("\n[5] Kodowanie UTF-8"), "head")
            for i, s in enumerate(self.skrypty):
                try:
                    s.get("kod", "").encode("utf-8")
                    log(_tr("  ✔ Skrypt #{i} '{nazwa}' — UTF-8 OK").format(i=i, nazwa=s.get('nazwa','?')), "ok")
                except UnicodeEncodeError as e:
                    log(_tr("  ✘ Skrypt #{i} '{nazwa}' — błąd UTF-8: {e}").format(i=i, nazwa=s.get('nazwa','?'), e=e), "error")
                    errors += 1

        # 6. Składnia Python
        if self.diag_checks["skladnia"].get():
            log(_tr("\n[6] Sprawdzanie składni Python"), "head")
            for i, s in enumerate(self.skrypty):
                if s.get("kategoria") == "Python":
                    try:
                        ast.parse(s.get("kod", ""))
                        log(_tr("  ✔ '{nazwa}' — składnia poprawna").format(nazwa=s['nazwa']), "ok")
                    except SyntaxError as e:
                        log(_tr("  ✘ '{nazwa}' — błąd składni linia {linia}: {msg}").format(nazwa=s['nazwa'], linia=e.lineno, msg=e.msg), "error")
                        errors += 1

        # 7. Niebezpieczne wzorce
        if self.diag_checks["niebezp"].get():
            log(_tr("\n[7] Niebezpieczne wzorce kodu"), "head")
            danger_patterns = [
                (r"\bos\.system\s*\(", "os.system()"),
                (r"\beval\s*\(",       "eval()"),
                (r"\bexec\s*\(",       "exec()"),
                (r"rm\s+-rf",          "rm -rf"),
                (r"__import__",        "__import__"),
            ]
            for i, s in enumerate(self.skrypty):
                kod = s.get("kod", "")
                found = []
                for pattern, name in danger_patterns:
                    if re.search(pattern, kod):
                        found.append(name)
                if found:
                    log(_tr("  ⚠ '{nazwa}' — wzorce: {wzorce}").format(nazwa=s.get('nazwa','?'), wzorce=', '.join(found)), "warn")
                    warnings += 1
                else:
                    log(_tr("  ✔ '{nazwa}' — brak niebezpiecznych wzorców").format(nazwa=s.get('nazwa','?')), "ok")

        log(f"\n{'=' * 54}", "head")
        log(_tr("  PODSUMOWANIE: ✘ Błędy: {e}  ⚠ Ostrzeżenia: {w}").format(e=errors, w=warnings), "head")
        log("=" * 54, "head")
        self.lbl_diag_ok.config(
            text=_tr("✘ {e} błędów  ⚠ {w} ostrzeżeń").format(e=errors, w=warnings),
            fg="#e07070" if errors else ("#f0c050" if warnings else "#6dde84"))
        self.diag_text.config(state="disabled")

    def _diag_save_log(self):
        self._ensure_moduly_built()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_tr("Log"), "*.txt"), (_tr("Wszystkie"), "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.diag_text.get("1.0", "end-1c"))
            messagebox.showinfo(_tr("Zapisano"), _tr("Log zapisany:\n{path}").format(path=path))

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 3: ŁĄCZENIE FUNKCJI
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_laczen(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["laczen"] = frame

        # słownik załadowanych modułów: {nazwa: {nazwa, kategoria, opis, kod, źródło}}
        self._laczen_modules = {}   # załadowane moduły (lewa kolumna)
        self._laczen_queue   = []   # kolejka do połączenia (środkowa kolumna) — lista nazw

        # ── nagłówek ──────────────────────────────────────────────────────────
        hdr = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("🔗 Łączenie modułów — załaduj pliki lub skrypty z bazy, ułóż kolejność, połącz"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "🔗 Łączenie modułów — załaduj pliki lub skrypty z bazy, ułóż kolejność, połącz").pack(side="left")
        self.lbl_laczen_info = self._trw(tk.Label(hdr, text=_tr("Modułów: 0 | Kolejka: 0"),
                                         font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3"), "Modułów: 0 | Kolejka: 0")
        self.lbl_laczen_info.pack(side="right", padx=8)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── 3-kolumnowy układ ──────────────────────────────────────────────────
        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # ════════════════════════════
        # KOLUMNA 1: Dostępne moduły
        # ════════════════════════════
        col1 = tk.Frame(body, bg=BG_PANEL, width=280,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        col1.pack(side="left", fill="y", padx=(0, 4))
        col1.pack_propagate(False)

        self._trw(tk.Label(col1, text=_tr("📦 Dostępne moduły"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "📦 Dostępne moduły").pack(anchor="w", padx=10, pady=(8, 2))

        # przyciski załaduj
        btn1 = tk.Frame(col1, bg=BG_PANEL)
        btn1.pack(fill="x", padx=6, pady=(0, 4))
        self._trw(tk.Button(btn1, text=_tr("📂 Załaduj plik(i)"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._laczen_load_files), "📂 Załaduj plik(i)").pack(side="left", padx=2)
        self._trw(tk.Button(btn1, text=_tr("📋 Z bazy"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_load_from_base), "📋 Z bazy").pack(side="left", padx=2)

        # filtr modułów
        flt = tk.Frame(col1, bg=BG_PANEL)
        flt.pack(fill="x", padx=6, pady=(0, 2))
        self._trw(tk.Label(flt, text=_tr("🔍"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "🔍").pack(side="left")
        self.laczen_filter_var = tk.StringVar()
        self.laczen_filter_var.trace_add("write", lambda *_: self._laczen_refresh_modules())
        tk.Entry(flt, textvariable=self.laczen_filter_var, font=FONT_MONO,
                 bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER_CLR,
                 highlightcolor=ACCENT_BLUE, width=18).pack(side="left", fill="x", expand=True, padx=4)

        # lista modułów
        sc1 = tk.Scrollbar(col1, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8)
        sc1.pack(side="right", fill="y", pady=2, padx=(0, 2))
        self.laczen_mod_list = tk.Listbox(col1, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                           selectmode="extended", relief="flat",
                                           highlightthickness=0,
                                           selectbackground=BG_ROW_SEL,
                                           activestyle="none",
                                           yscrollcommand=sc1.set)
        sc1.config(command=self.laczen_mod_list.yview)
        self.laczen_mod_list.pack(fill="both", expand=True, padx=(6, 0), pady=2)
        self.laczen_mod_list.bind("<Double-1>", lambda e: self._laczen_add_to_queue())

        # info o module
        tk.Frame(col1, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4, 2))
        self.laczen_mod_info = tk.Text(col1, font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY,
                                        relief="flat", height=4, state="disabled", wrap="word",
                                        highlightthickness=0)
        self.laczen_mod_info.pack(fill="x", padx=6, pady=(0, 2))
        self.laczen_mod_list.bind("<<ListboxSelect>>", self._laczen_show_mod_info)

        # przyciski dolne col1
        btn1b = tk.Frame(col1, bg=BG_PANEL)
        btn1b.pack(fill="x", padx=6, pady=(2, 6))
        self._trw(tk.Button(btn1b, text=_tr("➕ Dodaj do kolejki"), font=FONT_UI,
                  bg="#3a6040", fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#4a7850",
                  command=self._laczen_add_to_queue), "➕ Dodaj do kolejki").pack(side="left", padx=2, fill="x", expand=True)
        self._trw(tk.Button(btn1b, text=_tr("❌ Odłącz"), font=FONT_UI,
                  bg=BTN_ERR, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_ERR_HOVER,
                  command=self._laczen_detach), "❌ Odłącz").pack(side="left", padx=2)

        # ════════════════════════════
        # KOLUMNA 2: Kolejka łączenia
        # ════════════════════════════
        col2 = tk.Frame(body, bg=BG_PANEL, width=240,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        col2.pack(side="left", fill="y", padx=(0, 4))
        col2.pack_propagate(False)

        self._trw(tk.Label(col2, text=_tr("🗂 Kolejka łączenia"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "🗂 Kolejka łączenia").pack(anchor="w", padx=10, pady=(8, 2))
        self._trw(tk.Label(col2, text=_tr("(dwuklik = usuń z kolejki)"),
                 font=("Consolas", 7), bg=BG_PANEL, fg=FG_GRAY), "(dwuklik = usuń z kolejki)").pack(anchor="w", padx=10)

        sc2 = tk.Scrollbar(col2, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8)
        sc2.pack(side="right", fill="y", pady=2, padx=(0, 2))
        self.laczen_queue_list = tk.Listbox(col2, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                             selectmode="single", relief="flat",
                                             highlightthickness=0,
                                             selectbackground=BG_ROW_SEL,
                                             activestyle="none",
                                             yscrollcommand=sc2.set)
        sc2.config(command=self.laczen_queue_list.yview)
        self.laczen_queue_list.pack(fill="both", expand=True, padx=(6, 0), pady=2)
        self.laczen_queue_list.bind("<Double-1>", lambda e: self._laczen_remove_from_queue())

        # przyciski kolejka
        tk.Frame(col2, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4, 2))
        btn2 = tk.Frame(col2, bg=BG_PANEL)
        btn2.pack(fill="x", padx=6, pady=2)
        self._trw(tk.Button(btn2, text=_tr("⬆"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._laczen_queue_up), "⬆").pack(side="left", padx=2)
        self._trw(tk.Button(btn2, text=_tr("⬇"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._laczen_queue_down), "⬇").pack(side="left", padx=2)
        self._trw(tk.Button(btn2, text=_tr("🗑 Wyczyść"), font=FONT_UI, bg=BTN_ERR, fg=FG_WHITE,
                  relief="flat", padx=6, pady=3, cursor="hand2",
                  activebackground=BTN_ERR_HOVER,
                  command=self._laczen_queue_clear), "🗑 Wyczyść").pack(side="left", padx=2, fill="x", expand=True)

        # tryb łączenia
        tk.Frame(col2, bg=BORDER_CLR, height=1).pack(fill="x", pady=(6, 2))
        self._trw(tk.Label(col2, text=_tr("Tryb łączenia:"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE), "Tryb łączenia:").pack(anchor="w", padx=10, pady=(2, 2))
        self.var_laczen_mode = tk.StringVar(value="sekwencja")
        modes = [
            ("Sekwencja",  "sekwencja"),
            ("Funkcje",    "funkcje"),
            ("Pipeline",   "pipeline"),
            ("Klasa",      "klasa"),
        ]
        for lbl, val in modes:
            self._trw(tk.Radiobutton(col2, text=_tr(lbl), variable=self.var_laczen_mode, value=val,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT), lbl).pack(anchor="w", padx=14)

        tk.Frame(col2, bg=BORDER_CLR, height=1).pack(fill="x", pady=(6, 2))
        self._trw(tk.Label(col2, text=_tr("Nazwa wynikowego skryptu:"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Nazwa wynikowego skryptu:").pack(anchor="w", padx=10)
        self.laczen_out_name = tk.Entry(col2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                         insertbackground=FG_WHITE, relief="flat",
                                         highlightthickness=1, highlightbackground=BORDER_CLR,
                                         highlightcolor=ACCENT_BLUE)
        self.laczen_out_name.insert(0, "polaczony_skrypt")
        self.laczen_out_name.pack(fill="x", padx=8, pady=4)

        self._trw(tk.Button(col2, text=_tr("⚡ Połącz wszystkie w kolejce"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=8, pady=6,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._laczen_run), "⚡ Połącz wszystkie w kolejce").pack(padx=8, pady=(0, 8), fill="x")

        # ════════════════════════════
        # KOLUMNA 3: Podgląd wyniku
        # ════════════════════════════
        col3 = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        col3.pack(side="left", fill="both", expand=True)

        self._trw(tk.Label(col3, text=_tr("📄 Podgląd połączonego kodu:"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "📄 Podgląd połączonego kodu:").pack(anchor="w", padx=10, pady=(8, 4))

        btn3 = tk.Frame(col3, bg=BG_PANEL)
        btn3.pack(fill="x", padx=8, pady=(0, 4))
        self._trw(tk.Button(btn3, text=_tr("📋 Kopiuj"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_copy), "📋 Kopiuj").pack(side="left", padx=2)
        self._trw(tk.Button(btn3, text=_tr("💾 Zapisz w bazie"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_save_as_script), "💾 Zapisz w bazie").pack(side="left", padx=2)
        self._trw(tk.Button(btn3, text=_tr("📁 Eksportuj .py"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_export), "📁 Eksportuj .py").pack(side="left", padx=2)
        self._trw(tk.Button(btn3, text=_tr("🔄 Odśwież"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_refresh_modules), "🔄 Odśwież").pack(side="right", padx=2)

        sc3 = tk.Scrollbar(col3, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8)
        sc3.pack(side="right", fill="y", pady=4, padx=(0, 4))
        sc3h = tk.Scrollbar(col3, orient="horizontal", bg=BG_PANEL,
                             troughcolor=BG_PANEL, width=8)
        sc3h.pack(side="bottom", fill="x", padx=8)
        self.laczen_out_text = tk.Text(col3, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                        relief="flat", wrap="none",
                                        highlightthickness=1, highlightbackground=BORDER_CLR,
                                        yscrollcommand=sc3.set, xscrollcommand=sc3h.set)
        sc3.config(command=self.laczen_out_text.yview)
        sc3h.config(command=self.laczen_out_text.xview)
        self.laczen_out_text.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 4))

    # ── helpers modułów ───────────────────────────────────────────────────────

    def _laczen_update_info_label(self):
        self.lbl_laczen_info.config(
            text=_tr("Modułów: {m} | Kolejka: {q}").format(m=len(self._laczen_modules), q=len(self._laczen_queue)))

    def _laczen_refresh_modules(self, *_):
        """Odśwież listę dostępnych modułów (po filtrze)."""
        flt = self.laczen_filter_var.get().lower().strip()
        self.laczen_mod_list.delete(0, "end")
        for name in sorted(self._laczen_modules.keys()):
            if flt and flt not in name.lower():
                continue
            m = self._laczen_modules[name]
            prefix = "🔵" if m.get("zrodlo") == "plik" else "🟢"
            self.laczen_mod_list.insert("end", f"{prefix} {name}")
        self._laczen_update_info_label()

    def _laczen_refresh_queue(self):
        """Odśwież widok kolejki."""
        self.laczen_queue_list.delete(0, "end")
        for j, name in enumerate(self._laczen_queue):
            self.laczen_queue_list.insert("end", f"{j+1:>2}. {name}")
        self._laczen_update_info_label()

    def _laczen_load_files(self):
        """Załaduj jeden lub wiele plików z dysku."""
        paths = filedialog.askopenfilenames(
            title=_tr("Wybierz pliki modułów (można zaznaczyć wiele)"),
            filetypes=[
                (_tr("Skrypty Python"), "*.py"),
                (_tr("Bash / Shell"),   "*.sh"),
                (_tr("PowerShell"),     "*.ps1"),
                (_tr("JavaScript"),     "*.js"),
                (_tr("Batch"),          "*.bat *.cmd"),
                (_tr("VBScript"),       "*.vbs"),
                (_tr("Java"),           "*.java"),
                (_tr("Archiwa JAR"),    "*.jar"),
                (_tr("C"),              "*.c *.h"),
                (_tr("C++"),            "*.cpp *.cc *.cxx *.c++ *.hpp *.hh *.hxx"),
                (_tr("Ruby"),           "*.rb"),
                (_tr("Perl"),           "*.pl"),
                (_tr("PHP"),            "*.php"),
                (_tr("WSF"),            "*.wsf"),
                (_tr("HTA"),            "*.hta"),
                (_tr("HTML"),           "*.html *.htm"),
                (_tr("CSS"),            "*.css"),
                (_tr("JSON"),           "*.json"),
                (_tr("Markdown"),       "*.md *.markdown"),
                (_tr("SQL"),            "*.sql"),
                (_tr("Tekstowe"),       "*.txt"),
                (_tr("Wszystkie"),      "*.*"),
            ])
        if not paths:
            return
        loaded = 0
        for path in paths:
            try:
                name = os.path.basename(path)
                ext  = os.path.splitext(name)[1].lower()
                if ext in BIN_EXT:
                    kod = jar_base64(path)
                else:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        kod = fh.read()
                kat  = EXT_KAT.get(ext, "Other")
                self._laczen_modules[name] = {
                    "nazwa": name, "kategoria": kat,
                    "opis": f"Załadowany z pliku: {path}",
                    "kod": kod, "zrodlo": "plik", "sciezka": path,
                }
                loaded += 1
            except Exception as e:
                messagebox.showerror(_tr("Błąd"), _tr("Nie można wczytać:\n{path}\n{e}").format(path=path, e=e))
        self._laczen_refresh_modules()
        messagebox.showinfo(_tr("Załadowano"), _tr("Załadowano {n} plik(ów) jako moduły.\nDwukliknij nazwę lub użyj 'Dodaj do kolejki'.").format(n=loaded))

    def _laczen_load_from_base(self):
        """Okno dialogowe: zaznacz skrypty z bazy i załaduj jako moduły."""
        if not self.skrypty:
            messagebox.showinfo(_tr("Brak skryptów"), _tr("CodeMate jest pusta."))
            return

        dlg = _popup(self)
        dlg.title(_tr("Załaduj moduły z bazy skryptów"))
        dlg.configure(bg=BG_DARK)
        dlg.geometry("480x420")
        dlg.resizable(True, True)
        dlg.grab_set()

        self._trw(tk.Label(dlg, text=_tr("Zaznacz skrypty do załadowania (Ctrl+klik = wiele):"),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "Zaznacz skrypty do załadowania (Ctrl+klik = wiele):").pack(anchor="w", padx=10, pady=(10, 4))

        # filtr
        flt_var = tk.StringVar()
        flt_e = tk.Entry(dlg, textvariable=flt_var, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                          insertbackground=FG_WHITE, relief="flat",
                          highlightthickness=1, highlightbackground=BORDER_CLR)
        flt_e.pack(fill="x", padx=10, pady=(0, 4))

        sc = tk.Scrollbar(dlg, orient="vertical", bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        sc.pack(side="right", fill="y", padx=(0, 6), pady=4)
        lb = tk.Listbox(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                        selectmode="extended", relief="flat", highlightthickness=0,
                        selectbackground=BG_ROW_SEL, activestyle="none",
                        yscrollcommand=sc.set)
        sc.config(command=lb.yview)
        lb.pack(fill="both", expand=True, padx=(10, 0), pady=4)

        all_items = [(s["nazwa"], s) for s in self.skrypty]

        def refresh_dlg(*_):
            q = flt_var.get().lower()
            lb.delete(0, "end")
            for name, s in all_items:
                if q and q not in name.lower() and q not in s.get("kategoria","").lower():
                    continue
                lb.insert("end", f"[{s.get('kategoria','?')}]  {name}")

        flt_var.trace_add("write", refresh_dlg)
        refresh_dlg()

        btn_row = tk.Frame(dlg, bg=BG_DARK)
        btn_row.pack(fill="x", padx=10, pady=(4, 10))

        def zaladuj():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning(_tr("Brak wyboru"), _tr("Zaznacz przynajmniej jeden skrypt."), parent=dlg)
                return
            # mapuj indeksy listboxa do faktycznych skryptów (po filtrze)
            visible = [(name, s) for name, s in all_items
                       if not flt_var.get().lower()
                       or flt_var.get().lower() in name.lower()
                       or flt_var.get().lower() in s.get("kategoria","").lower()]
            for i in sel:
                if i < len(visible):
                    name, s = visible[i]
                    self._laczen_modules[name] = {
                        "nazwa": name, "kategoria": s.get("kategoria","?"),
                        "opis": s.get("opis",""), "kod": s.get("kod",""),
                        "zrodlo": "baza", "sciezka": "",
                    }
            self._laczen_refresh_modules()
            dlg.destroy()
            messagebox.showinfo(_tr("Załadowano"),
                                _tr("Załadowano {n} moduł(ów) z bazy.\nTeraz dodaj je do kolejki łączenia.").format(n=len(sel)))

        self._trw(tk.Button(btn_row, text=_tr("✅ Załaduj zaznaczone"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=12, pady=5,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=zaladuj), "✅ Załaduj zaznaczone").pack(side="left", padx=4)
        self._trw(tk.Button(btn_row, text=_tr("Anuluj"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=dlg.destroy), "Anuluj").pack(side="left", padx=4)
        self._trw(tk.Button(btn_row, text=_tr("Zaznacz wszystkie"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=lambda: lb.select_set(0, "end")), "Zaznacz wszystkie").pack(side="right", padx=4)

    def _laczen_detach(self):
        """Odłącz zaznaczone moduły z listy dostępnych."""
        sel = self.laczen_mod_list.curselection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz moduł(y) do odłączenia."))
            return
        names = [self.laczen_mod_list.get(i).split(" ", 1)[1] for i in sel]
        if not messagebox.askyesno(_tr("Odłącz moduły"),
                                    _tr("Odłączyć {n} moduł(ów)?\n").format(n=len(names)) + "\n".join(f"• {n}" for n in names)):
            return
        for name in names:
            self._laczen_modules.pop(name, None)
            if name in self._laczen_queue:
                self._laczen_queue.remove(name)
        self._laczen_refresh_modules()
        self._laczen_refresh_queue()

    def _laczen_show_mod_info(self, event=None):
        sel = self.laczen_mod_list.curselection()
        if not sel:
            return
        raw  = self.laczen_mod_list.get(sel[0])
        name = raw.split(" ", 1)[1] if " " in raw else raw
        m    = self._laczen_modules.get(name)
        if not m:
            return
        linie = m["kod"].count("\n") + 1
        info  = (_tr("Nazwa    : {v}\n").format(v=m['nazwa']) +
                 _tr("Kategoria: {v}\n").format(v=m['kategoria']) +
                 _tr("Źródło   : {v}\n").format(v=m.get('zrodlo','?')) +
                 _tr("Linie    : {v}\n").format(v=linie) +
                 _tr("Opis     : {v}").format(v=m.get('opis','')[:60]))
        self._set_text(self.laczen_mod_info, info)

    def _laczen_add_to_queue(self):
        """Dodaj zaznaczone moduły do kolejki łączenia."""
        sel = self.laczen_mod_list.curselection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz moduł(y) do dodania do kolejki."))
            return
        added = 0
        for i in sel:
            raw  = self.laczen_mod_list.get(i)
            name = raw.split(" ", 1)[1] if " " in raw else raw
            if name not in self._laczen_queue:
                self._laczen_queue.append(name)
                added += 1
        self._laczen_refresh_queue()
        if added == 0:
            messagebox.showinfo(_tr("Info"), _tr("Zaznaczone moduły są już w kolejce."))

    def _laczen_remove_from_queue(self):
        sel = self.laczen_queue_list.curselection()
        if not sel:
            return
        idx  = sel[0]
        name = self._laczen_queue[idx]
        self._laczen_queue.pop(idx)
        self._laczen_refresh_queue()

    def _laczen_queue_up(self):
        sel = self.laczen_queue_list.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self._laczen_queue[i], self._laczen_queue[i-1] = \
            self._laczen_queue[i-1], self._laczen_queue[i]
        self._laczen_refresh_queue()
        self.laczen_queue_list.selection_set(i - 1)

    def _laczen_queue_down(self):
        sel = self.laczen_queue_list.curselection()
        if not sel or sel[0] >= len(self._laczen_queue) - 1:
            return
        i = sel[0]
        self._laczen_queue[i], self._laczen_queue[i+1] = \
            self._laczen_queue[i+1], self._laczen_queue[i]
        self._laczen_refresh_queue()
        self.laczen_queue_list.selection_set(i + 1)

    def _laczen_queue_clear(self):
        if self._laczen_queue and messagebox.askyesno(_tr("Wyczyść kolejkę"), _tr("Wyczyścić całą kolejkę?")):
            self._laczen_queue.clear()
            self._laczen_refresh_queue()

    def _laczen_run(self):
        if not self._laczen_queue:
            messagebox.showwarning(_tr("Pusta kolejka"),
                                   _tr("Dodaj przynajmniej jeden moduł do kolejki łączenia."))
            return
        missing = [n for n in self._laczen_queue if n not in self._laczen_modules]
        if missing:
            messagebox.showerror(_tr("Brakujące moduły"),
                                  _tr("Brakuje modułów:\n") + "\n".join(f"• {n}" for n in missing))
            return

        mode     = self.var_laczen_mode.get()
        selected = [self._laczen_modules[n] for n in self._laczen_queue]
        name     = self.laczen_out_name.get().strip() or "polaczony_skrypt"
        ts       = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = (
            f"# ╔══════════════════════════════════════════════════╗\n"
            f"# ║  Skrypt połączony : {name}\n"
            f"# ║  Tryb             : {mode}\n"
            f"# ║  Wygenerowano     : {ts}\n"
            f"# ║  Modułów          : {len(selected)}\n"
            f"# ║  Źródła           : {', '.join(s['nazwa'] for s in selected)}\n"
            f"# ╚══════════════════════════════════════════════════╝\n\n"
        )

        if mode == "sekwencja":
            parts = [header]
            for s in selected:
                sep = "─" * 44
                parts.append(f"# ┌─ {s['nazwa']} [{s.get('kategoria','?')}]\n"
                              f"# └─ {sep}\n{s['kod']}\n\n")
            result = "".join(parts)

        elif mode == "funkcje":
            parts = [header]
            for s in selected:
                fname = re.sub(r"[^a-z0-9_]", "_", s["nazwa"].lower())
                body  = "\n".join("    " + l for l in s["kod"].splitlines())
                parts.append(
                    f"def {fname}():\n"
                    f"    \"\"\"{s.get('opis','brak opisu')} [{s.get('kategoria','?')}]\"\"\"\n"
                    f"{body}\n\n\n")
            parts.append("if __name__ == '__main__':\n")
            for s in selected:
                fname = re.sub(r"[^a-z0-9_]", "_", s["nazwa"].lower())
                parts.append(f"    {fname}()\n")
            result = "".join(parts)

        elif mode == "pipeline":
            parts = [header]
            for j, s in enumerate(selected):
                fname = re.sub(r"[^a-z0-9_]", "_", s["nazwa"].lower())
                body  = "\n".join("    " + l for l in s["kod"].splitlines())
                arg   = "data=None" if j == 0 else "data"
                parts.append(
                    f"def step_{j+1:02d}_{fname}({arg}):\n"
                    f"    \"\"\"{s.get('opis','brak opisu')}\"\"\"\n"
                    f"{body}\n    return data\n\n\n")
            parts.append("def run_pipeline():\n    data = None\n")
            for j, s in enumerate(selected):
                fname = re.sub(r"[^a-z0-9_]", "_", s["nazwa"].lower())
                parts.append(f"    data = step_{j+1:02d}_{fname}(data)\n")
            parts.append("    return data\n\n\nif __name__ == '__main__':\n"
                         "    result = run_pipeline()\n    print(result)\n")
            result = "".join(parts)

        else:  # klasa
            cls_name = re.sub(r"[^a-zA-Z0-9]", "", name).capitalize() or "ModulPolaczony"
            parts = [header, f"class {cls_name}:\n    \"\"\"Połączone moduły: "
                              f"{', '.join(s['nazwa'] for s in selected)}\"\"\"\n\n"]
            for s in selected:
                fname = re.sub(r"[^a-z0-9_]", "_", s["nazwa"].lower())
                body  = "\n".join("        " + l for l in s["kod"].splitlines())
                parts.append(
                    f"    def {fname}(self):\n"
                    f"        \"\"\"{s.get('opis','brak opisu')}\"\"\"\n"
                    f"{body}\n\n")
            parts.append(f"\n\nif __name__ == '__main__':\n"
                         f"    obj = {cls_name}()\n")
            for s in selected:
                fname = re.sub(r"[^a-z0-9_]", "_", s["nazwa"].lower())
                parts.append(f"    obj.{fname}()\n")
            result = "".join(parts)

        self.laczen_out_text.delete("1.0", "end")
        self.laczen_out_text.insert("1.0", result)

    def _laczen_copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.laczen_out_text.get("1.0", "end-1c"))
        messagebox.showinfo(_tr("Skopiowano"), _tr("Połączony kod skopiowany do schowka."))

    def _laczen_save_as_script(self):
        kod  = self.laczen_out_text.get("1.0", "end-1c")
        name = self.laczen_out_name.get().strip() or "polaczony_skrypt"
        if not kod.strip():
            messagebox.showwarning(_tr("Brak kodu"), _tr("Najpierw połącz skrypty."))
            return
        now = now_str()
        skrypt = sc_normalize({"nazwa": name, "kategoria": "Python",
                  "tagi": "połączony,auto",
                  "opis": f"Automatycznie połączony z {len(self._laczen_queue)} modułów",
                  "kod": kod, "zmieniony": now})
        for i, s in enumerate(self.skrypty):
            if s.get("nazwa") == name:
                skrypt["id"] = s.get("id")
                skrypt["utworzony"] = s.get("utworzony")
                self.skrypty[i] = skrypt
                self._rebuild_index()
                self._update_count()
                self._after_db_change()
                messagebox.showinfo(_tr("Zapisano"), _tr("Skrypt '{name}' zaktualizowany w bazie.").format(name=name))
                return
        self.skrypty.append(skrypt)
        self._rebuild_index()
        self._update_count()
        self._after_db_change()
        messagebox.showinfo(_tr("Zapisano"), _tr("Skrypt '{name}' dodany do bazy.").format(name=name))

    def _laczen_export(self):
        kod = self.laczen_out_text.get("1.0", "end-1c")
        if not kod.strip():
            messagebox.showwarning(_tr("Brak kodu"), _tr("Najpierw połącz skrypty."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[(_tr("Python"), "*.py"), (_tr("Tekstowy"), "*.txt"), (_tr("Wszystkie"), "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(kod)
            messagebox.showinfo(_tr("Eksport"), _tr("Wyeksportowano:\n{path}").format(path=path))

    # ══════════════════════════════════════════════════════════════════════════
    # MOD: GRAF ZALEŻNOŚCI (poz. 8 planu działania)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_graf(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["graf"] = frame
        self._graf_data = None

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("🔄 Odśwież graf"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._mod_graf_refresh), "🔄 Odśwież graf").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("📋 Kopiuj raport"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._mod_graf_copy), "📋 Kopiuj raport").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("💾 Eksportuj raport"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._mod_graf_export), "💾 Eksportuj raport").pack(side="left", padx=2)
        self.lbl_graf_info = self._trw(
            tk.Label(bar, text=_tr("Skrypty: 0 · Zależności: 0 · Cykle: 0"),
                     font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3"),
            "Skrypty: 0 · Zależności: 0 · Cykle: 0")
        self.lbl_graf_info.pack(side="right", padx=8)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        self._trw(tk.Label(frame,
                 text=_tr("Zależności wykrywane są z importów skryptów Python."),
                 font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY),
                 "Zależności wykrywane są z importów skryptów Python.").pack(
                     anchor="w", padx=10, pady=(4, 2))

        self.graf_canvas = tk.Canvas(frame, bg=BG_INPUT, height=240, relief="flat",
                                     highlightthickness=1, highlightbackground=BORDER_CLR)
        self.graf_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.graf_canvas.bind("<Configure>", lambda e: self._graf_redraw())

        bottom = tk.Frame(frame, bg=BG_DARK)
        bottom.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = tk.Frame(bottom, bg=BG_PANEL, highlightthickness=1,
                        highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self._trw(tk.Label(left, text=_tr("🕸 Zależności i importy"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), "🕸 Zależności i importy").pack(
                     anchor="w", padx=10, pady=(6, 2))
        tvs = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=8)
        tvs.pack(side="right", fill="y", pady=2)
        self.graf_tree = ttk.Treeview(left, columns=("zal", "zewn"),
                                      show="tree headings", style="Dark.Treeview",
                                      height=7, yscrollcommand=tvs.set)
        tvs.config(command=self.graf_tree.yview)
        self._trh(self.graf_tree, "#0", "Skrypt")
        self._trh(self.graf_tree, "zal", "Zależy od")
        self._trh(self.graf_tree, "zewn", "Zewnętrzne importy")
        self.graf_tree.column("#0", width=180, minwidth=110, anchor="w")
        self.graf_tree.column("zal", width=180, minwidth=110, anchor="w")
        self.graf_tree.column("zewn", width=180, minwidth=110, anchor="w")
        self.graf_tree.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 6))
        self.graf_tree.tag_configure("cykl", foreground="#e07070")
        self.graf_tree.tag_configure("osier", foreground="#f0c050")

        right = tk.Frame(bottom, bg=BG_PANEL, width=300, highlightthickness=1,
                         highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="y", padx=(4, 0))
        right.pack_propagate(False)
        self._trw(tk.Label(right, text=_tr("⚠ Cykle"), font=FONT_BOLD,
                 bg=BG_PANEL, fg="#e07070"), "⚠ Cykle").pack(anchor="w", padx=10, pady=(6, 2))
        cyc_wrap = tk.Frame(right, bg=BG_PANEL)
        cyc_wrap.pack(fill="x", padx=8, pady=(0, 6))
        cyc_sb = tk.Scrollbar(cyc_wrap, orient="vertical", bg=BG_PANEL,
                              troughcolor=BG_PANEL, width=8)
        cyc_sb.pack(side="right", fill="y")
        self.graf_cycles = tk.Listbox(cyc_wrap, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      relief="flat", highlightthickness=0, height=5,
                                      selectbackground=BG_ROW_SEL, activestyle="none",
                                      yscrollcommand=cyc_sb.set)
        self.graf_cycles.pack(side="left", fill="x", expand=True)
        cyc_sb.config(command=self.graf_cycles.yview)
        self._trw(tk.Label(right, text=_tr("🕳 Osierocone"), font=FONT_BOLD,
                 bg=BG_PANEL, fg="#f0c050"), "🕳 Osierocone").pack(anchor="w", padx=10, pady=(2, 2))
        orp_wrap = tk.Frame(right, bg=BG_PANEL)
        orp_wrap.pack(fill="x", padx=8, pady=(0, 8))
        orp_sb = tk.Scrollbar(orp_wrap, orient="vertical", bg=BG_PANEL,
                              troughcolor=BG_PANEL, width=8)
        orp_sb.pack(side="right", fill="y")
        self.graf_orphans = tk.Listbox(orp_wrap, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                       relief="flat", highlightthickness=0, height=5,
                                       selectbackground=BG_ROW_SEL, activestyle="none",
                                       yscrollcommand=orp_sb.set)
        self.graf_orphans.pack(side="left", fill="x", expand=True)
        orp_sb.config(command=self.graf_orphans.yview)

        self._mod_graf_refresh()

    def _mod_graf_refresh(self):
        """Przebudowuje graf zależności i odświeża widok (canvas, tabela, listy)."""
        graf = build_dep_graph(self.skrypty)
        nodes, edges = graf["nodes"], graf["edges"]
        cycles = find_cycles(nodes, edges)
        isolated = find_isolated(nodes, edges)
        cyc_keys = {k for c in cycles for k in c}
        self._graf_data = (nodes, edges, cyc_keys, isolated)

        # tabela: skrypt → zależności / importy zewnętrzne
        for iid in self.graf_tree.get_children(""):
            self.graf_tree.delete(iid)
        ext_map = graf["external"]
        for key in sorted(nodes):
            deps = sorted({b for a, b in edges if a == key})
            deps_lbl = ", ".join(nodes[b]["nazwa"] for b in deps) or "—"
            ext_lbl = ", ".join(ext_map.get(key, [])) or "—"
            tags = ("cykl",) if key in cyc_keys else (("osier",) if key in isolated else ())
            self.graf_tree.insert("", "end", text="  " + nodes[key]["nazwa"],
                                  values=(deps_lbl, ext_lbl), tags=tags)

        # listy: cykle i moduły osierocone
        self.graf_cycles.delete(0, "end")
        if cycles:
            for c in cycles:
                self.graf_cycles.insert("end", " → ".join(nodes[k]["nazwa"] for k in c))
        else:
            self.graf_cycles.insert("end", _tr("Brak cykli"))
        self.graf_orphans.delete(0, "end")
        if isolated:
            for k in isolated:
                self.graf_orphans.insert("end", nodes[k]["nazwa"])
        else:
            self.graf_orphans.insert("end", _tr("Brak modułów osieroconych"))

        self.lbl_graf_info.config(
            text=_tr("Skrypty: {n} · Zależności: {m} · Cykle: {c}").format(
                n=len(nodes), m=len(edges), c=len(cycles)))
        self._graf_redraw()

    def _graf_redraw(self):
        """Rysuje graf na canvasie (układ kołowy) na podstawie ostatnich danych."""
        canvas = getattr(self, "graf_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        data = self._graf_data
        if not data:
            return
        nodes, edges, cyc_keys, isolated = data
        keys = sorted(nodes)
        if not keys:
            canvas.create_text(16, 16, anchor="nw",
                               text=_tr("Brak skryptów Python w bazie."),
                               fill=FG_GRAY, font=FONT_UI)
            return
        import math
        w = max(canvas.winfo_width(), 200)
        h = max(canvas.winfo_height(), 160)
        cx, cy = w / 2.0, h / 2.0
        r = max(min(w, h) / 2.0 - 56, 30)
        pos = {}
        n = len(keys)
        for i, k in enumerate(keys):
            ang = 2 * math.pi * i / n - math.pi / 2
            pos[k] = (cx + r * math.cos(ang), cy + r * math.sin(ang))
        for a, b in sorted(edges):
            x1, y1 = pos[a]
            x2, y2 = pos[b]
            canvas.create_line(x1, y1, x2, y2, fill="#5a6a8a",
                               arrow="last", arrowshape=(9, 11, 4), width=1)
        for k in keys:
            x, y = pos[k]
            if k in cyc_keys:
                outline = "#e07070"
            elif k in isolated:
                outline = "#f0c050"
            else:
                outline = KAT_COLOR.get(nodes[k]["kategoria"], ACCENT_BLUE)
            canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=BG_PANEL,
                               outline=outline, width=2)
            canvas.create_text(x, y - 19, text=nodes[k]["nazwa"][:20],
                               fill=FG_WHITE, font=("Consolas", 8))

    def _graf_report(self) -> str:
        """Buduje tekstowy (Markdown) raport z grafu zależności."""
        data = self._graf_data
        if not data:
            return ""
        nodes, edges, _cyc, isolated = data
        cycles = find_cycles(nodes, edges)
        lines = ["# " + _tr("Graf zależności skryptów"), "",
                 f"- {_tr('Skrypty')}: {len(nodes)}",
                 f"- {_tr('Zależności')}: {len(edges)}", "",
                 "## " + _tr("Zależności")]
        for key in sorted(nodes):
            deps = sorted({b for a, b in edges if a == key})
            if deps:
                lines.append(f"- **{nodes[key]['nazwa']}** → " +
                             ", ".join(nodes[b]["nazwa"] for b in deps))
        lines += ["", "## " + _tr("Cykle")]
        if cycles:
            for c in cycles:
                lines.append("- " + " → ".join(nodes[k]["nazwa"] for k in c))
        else:
            lines.append("- " + _tr("Brak cykli"))
        lines += ["", "## " + _tr("Osierocone")]
        if isolated:
            for k in isolated:
                lines.append(f"- {nodes[k]['nazwa']}")
        else:
            lines.append("- " + _tr("Brak modułów osieroconych"))
        return "\n".join(lines) + "\n"

    def _mod_graf_copy(self):
        """Kopiuje raport grafu zależności do schowka."""
        raport = self._graf_report()
        if raport:
            self.clipboard_clear()
            self.clipboard_append(raport)
            if hasattr(self, "lbl_mod_status"):
                self.lbl_mod_status.config(text=_tr("Raport skopiowany do schowka."))

    def _mod_graf_export(self):
        """Zapisuje raport grafu zależności do pliku."""
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[(_tr("Markdown"), "*.md"), (_tr("Plik tekstowy"), "*.txt"),
                       (_tr("Wszystkie"), "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._graf_report())
            messagebox.showinfo(_tr("Eksport"), _tr("Raport zapisany:\n{path}").format(path=path))

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 4: TESTY OSIĄGÓW
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_testy(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["testy"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("▶ Uruchom testy"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._run_testy), "▶ Uruchom testy").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("🔄 Odśwież listę"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._testy_refresh), "🔄 Odśwież listę").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("📊 Eksportuj wyniki"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._testy_export), "📊 Eksportuj wyniki").pack(side="left", padx=2)
        self.lbl_testy_status = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_testy_status.pack(side="right", padx=8)
        self._trw(tk.Button(bar, text=_tr("🔌 Odłącz"), font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("testy")), "🔌 Odłącz").pack(side="right", padx=2)
        self._trw(tk.Button(bar, text=_tr("📥 Załaduj"), font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("testy")), "📥 Załaduj").pack(side="right", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # górna część: tabela wyników
        self._trw(tk.Label(body, text=_tr("📊 Wyniki testów osiągów:"),
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE), "📊 Wyniki testów osiągów:").pack(anchor="w", pady=(0, 4))

        tree_f = tk.Frame(body, bg=BG_DARK)
        tree_f.pack(fill="both", expand=True)

        cols = ("Skrypt", "Kategoria", "Linie", "Znaki", "Tokeny~", "Złożoność", "Ocena")
        style = ttk.Style()
        style.configure("Perf.Treeview",
                        background=BG_ROW_ODD, foreground=FG_WHITE,
                        fieldbackground=BG_ROW_ODD, rowheight=24, font=FONT_UI)
        style.configure("Perf.Treeview.Heading",
                        background=BG_PANEL, foreground=FG_GRAY,
                        font=FONT_BOLD, relief="flat")
        style.map("Perf.Treeview",
                  background=[("selected", BG_ROW_SEL)],
                  foreground=[("selected", FG_WHITE)])

        vsb = tk.Scrollbar(tree_f, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8)
        vsb.pack(side="right", fill="y")
        self.testy_tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                                        style="Perf.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.testy_tree.yview)
        widths = [200, 90, 60, 70, 80, 100, 80]
        for col, w in zip(cols, widths):
            self._trh(self.testy_tree, col, col)
            self.testy_tree.column(col, width=w, minwidth=50)
        self.testy_tree.pack(fill="both", expand=True)
        self.testy_tree.tag_configure("A", foreground="#6dde84")
        self.testy_tree.tag_configure("B", foreground="#7ec8e3")
        self.testy_tree.tag_configure("C", foreground="#f0c050")
        self.testy_tree.tag_configure("D", foreground="#e07070")

        # dolna część: szczegóły
        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(6, 2))
        self._trw(tk.Label(body, text=_tr("Szczegóły wybranego skryptu:"),
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE), "Szczegóły wybranego skryptu:").pack(anchor="w")
        self.testy_detail = tk.Text(body, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                     relief="flat", height=8, state="disabled", wrap="word",
                                     highlightthickness=1, highlightbackground=BORDER_CLR)
        self.testy_detail.pack(fill="x", pady=4)
        self.testy_tree.bind("<<TreeviewSelect>>", self._testy_on_select)
        self._testy_results = []

    def _testy_refresh(self):
        for row in self.testy_tree.get_children():
            self.testy_tree.delete(row)
        self._testy_results = []

    def _run_testy(self):
        import time
        self._menu_pokaz_mod("testy")
        self._testy_refresh()
        if not self.skrypty:
            messagebox.showinfo(_tr("Brak skryptów"), _tr("Dodaj skrypty do bazy przed testami."))
            return

        for i, s in enumerate(self.skrypty):
            kod      = s.get("kod", "")
            linie    = kod.count("\n") + 1
            znaki    = len(kod)
            tokeny   = len(kod.split())
            # prosta złożoność: if/for/while/def/class
            zloz_cnt = sum(len(re.findall(rf"\b{kw}\b", kod))
                           for kw in ["if", "elif", "else", "for", "while", "def", "class", "try", "except"])
            # ocena
            if linie < 20 and zloz_cnt < 5:
                ocena, grade = _tr("A — Prosta"), "A"
            elif linie < 80 and zloz_cnt < 15:
                ocena, grade = _tr("B — Dobra"),  "B"
            elif linie < 200:
                ocena, grade = _tr("C — Średnia"), "C"
            else:
                ocena, grade = _tr("D — Złożona"), "D"

            tag = "odd" if i % 2 == 0 else "even"
            self.testy_tree.insert("", "end", iid=str(i),
                                   values=(s["nazwa"], s.get("kategoria","?"),
                                           linie, znaki, tokeny, zloz_cnt, ocena),
                                   tags=(grade,))
            self._testy_results.append({
                "nazwa": s["nazwa"], "linie": linie, "znaki": znaki,
                "tokeny": tokeny, "zlozonosc": zloz_cnt, "ocena": ocena, "kod": kod
            })

        self.lbl_testy_status.config(text=_tr("Przetestowano {n} skryptów").format(n=len(self.skrypty)),
                                      fg="#6dde84")

    def _testy_on_select(self, event=None):
        sel = self.testy_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._testy_results):
            return
        r = self._testy_results[idx]
        # policz unikalne słowa kluczowe
        kw_counts = {}
        for kw in ["def", "class", "if", "for", "while", "import", "return", "try"]:
            c = len(re.findall(rf"\b{kw}\b", r["kod"]))
            if c:
                kw_counts[kw] = c
        detail = (
            _tr("Skrypt   : {v}\n").format(v=r['nazwa']) +
            _tr("Linie    : {v}\n").format(v=r['linie']) +
            _tr("Znaki    : {v}\n").format(v=r['znaki']) +
            _tr("Tokeny~  : {v}\n").format(v=r['tokeny']) +
            _tr("Złożoność: {v} (if/for/while/def/class/try)\n").format(v=r['zlozonosc']) +
            _tr("Ocena    : {v}\n").format(v=r['ocena']) +
            _tr("\nSłowa kluczowe:\n") +
            "\n".join(f"  {k:<10} x{v}" for k, v in kw_counts.items())
        )
        self._set_text(self.testy_detail, detail)

    def _testy_export(self):
        self._ensure_moduly_built()
        if not self._testy_results:
            messagebox.showinfo(_tr("Brak danych"), _tr("Najpierw uruchom testy."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_tr("Raport"), "*.txt"), ("CSV", "*.csv"), (_tr("Wszystkie"), "*.*")])
        if path:
            lines = [_tr("Nazwa;Linie;Znaki;Tokeny;Złożoność;Ocena")]
            for r in self._testy_results:
                lines.append(f"{r['nazwa']};{r['linie']};{r['znaki']};{r['tokeny']};{r['zlozonosc']};{r['ocena']}")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            messagebox.showinfo(_tr("Eksport"), _tr("Wyniki zapisane:\n{path}").format(path=path))

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 5: NAPRAWA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_naprawa(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["naprawa"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("🔍 Znajdź problemy"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._naprawa_scan), "🔍 Znajdź problemy").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("🔧 Napraw wszystkie"), font=FONT_UI,
                  bg="#5a3080", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a40a0",
                  command=self._naprawa_fix_all), "🔧 Napraw wszystkie").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("✅ Napraw zaznaczony"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._naprawa_fix_selected), "✅ Napraw zaznaczony").pack(side="left", padx=2)
        self._trw(tk.Button(bar, text=_tr("💾 Zapisz raport"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._naprawa_save), "💾 Zapisz raport").pack(side="left", padx=2)
        self.lbl_naprawa_st = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_naprawa_st.pack(side="right", padx=8)
        self._trw(tk.Button(bar, text=_tr("🔌 Odłącz"), font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("naprawa")), "🔌 Odłącz").pack(side="right", padx=2)
        self._trw(tk.Button(bar, text=_tr("📥 Załaduj"), font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("naprawa")), "📥 Załaduj").pack(side="right", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # opcje naprawy
        opts = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        opts.pack(fill="x", pady=(0, 6))
        self._trw(tk.Label(opts, text=_tr("Opcje automatycznej naprawy:"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "Opcje automatycznej naprawy:").pack(anchor="w", padx=10, pady=(6, 2))
        chk_row = tk.Frame(opts, bg=BG_PANEL)
        chk_row.pack(fill="x", padx=8, pady=(0, 6))
        self.naprawa_opts = {}
        naprawy = [
            ("Usuń końcowe spacje",        "trailing"),
            ("Zamień taby na 4 spacje",    "tabs"),
            ("Normalizuj nowe linie",       "newlines"),
            ("Usuń wielokrotne puste linie","blank"),
            ("Dodaj kodowanie UTF-8",       "encoding"),
            ("Dodaj brakujące pola",        "fields"),
        ]
        for i, (lbl, key) in enumerate(naprawy):
            v = tk.BooleanVar(value=True)
            self.naprawa_opts[key] = v
            self._trw(tk.Checkbutton(chk_row, text=_tr(lbl), variable=v, font=FONT_UI,
                           bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT
                           ), lbl).grid(row=i // 3, column=i % 3, padx=12, pady=2, sticky="w")

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(0, 4))

        # lista problemów (Treeview)
        cols = ("Skrypt", "Problem", "Priorytet", "Status")
        style = ttk.Style()
        style.configure("Fix.Treeview",
                        background=BG_ROW_ODD, foreground=FG_WHITE,
                        fieldbackground=BG_ROW_ODD, rowheight=24, font=FONT_UI)
        style.configure("Fix.Treeview.Heading",
                        background=BG_PANEL, foreground=FG_GRAY,
                        font=FONT_BOLD, relief="flat")
        style.map("Fix.Treeview",
                  background=[("selected", BG_ROW_SEL)],
                  foreground=[("selected", FG_WHITE)])

        tree_f = tk.Frame(body, bg=BG_DARK)
        tree_f.pack(fill="both", expand=True)

        vsb = tk.Scrollbar(tree_f, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8)
        vsb.pack(side="right", fill="y")
        self.naprawa_tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                                          style="Fix.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.naprawa_tree.yview)
        wsb = [220, 280, 80, 100]
        for col, w in zip(cols, wsb):
            self._trh(self.naprawa_tree, col, col)
            self.naprawa_tree.column(col, width=w, minwidth=60)
        self.naprawa_tree.pack(fill="both", expand=True)
        self.naprawa_tree.tag_configure("high",   foreground="#e07070")
        self.naprawa_tree.tag_configure("medium", foreground="#f0c050")
        self.naprawa_tree.tag_configure("low",    foreground="#7ec8e3")
        self.naprawa_tree.tag_configure("fixed",  foreground="#6dde84")

        # log naprawy
        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4, 2))
        self._trw(tk.Label(body, text=_tr("Log naprawy:"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), "Log naprawy:").pack(anchor="w")
        self.naprawa_log = tk.Text(body, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                    relief="flat", height=6, state="disabled", wrap="word",
                                    highlightthickness=1, highlightbackground=BORDER_CLR)
        self.naprawa_log.pack(fill="x", pady=4)
        self.naprawa_log.tag_configure("ok",    foreground="#6dde84")
        self.naprawa_log.tag_configure("warn",  foreground="#f0c050")
        self.naprawa_log.tag_configure("head",  foreground=ACCENT_BLUE)
        self._naprawa_issues = []

    def _naprawa_scan(self):
        import re as re2
        self._menu_pokaz_mod("naprawa")
        for row in self.naprawa_tree.get_children():
            self.naprawa_tree.delete(row)
        self._naprawa_issues = []
        self._naprawa_log_clear()

        def add_issue(skrypt_idx, problem, priorytet):
            iid = f"{skrypt_idx}_{len(self._naprawa_issues)}"
            self._naprawa_issues.append({
                "skrypt_idx": skrypt_idx, "problem": problem,
                "priorytet": priorytet, "status": "Oczekuje", "iid": iid
            })
            tag = {"Wysoki": "high", "Średni": "medium", "Niski": "low"}.get(priorytet, "low")
            self.naprawa_tree.insert("", "end", iid=iid,
                                     values=(self.skrypty[skrypt_idx].get("nazwa","?"),
                                             _tr(problem), _tr(priorytet), _tr("Oczekuje")),
                                     tags=(tag,))

        for i, s in enumerate(self.skrypty):
            kod = s.get("kod", "")

            if any(line != line.rstrip() for line in kod.splitlines()):
                add_issue(i, "Końcowe spacje w liniach",        "Niski")
            if "\t" in kod:
                add_issue(i, "Znaki tabulacji (zamiast spacji)", "Niski")
            if "\r\n" in kod or "\r" in kod:
                add_issue(i, "Niezgodne znaki nowej linii",     "Średni")
            if re2.search(r"\n{3,}", kod):
                add_issue(i, "Wielokrotne puste linie (>2)",    "Niski")
            if not s.get("nazwa", "").strip():
                add_issue(i, "Brakująca nazwa skryptu",          "Wysoki")
            if not s.get("kategoria", "").strip():
                add_issue(i, "Brakująca kategoria",              "Wysoki")
            if not kod.strip():
                add_issue(i, "Pusty kod skryptu",                "Wysoki")
            if not s.get("opis", "").strip():
                add_issue(i, "Brak opisu skryptu",               "Średni")
            if not s.get("tagi", "").strip():
                add_issue(i, "Brak tagów skryptu",               "Niski")

        cnt = len(self._naprawa_issues)
        self.lbl_naprawa_st.config(
            text=_tr("Znaleziono {n} problemów").format(n=cnt),
            fg="#e07070" if cnt else "#6dde84")
        self._naprawa_log_add(
            _tr("Skan ukończony: {n} problemów w {t} skryptach.\n").format(n=cnt, t=len(self.skrypty)), "head")

    def _naprawa_fix_one(self, issue):
        import re as re2
        if issue["status"] == "Naprawiono":
            return False
        idx  = issue["skrypt_idx"]
        if idx >= len(self.skrypty):
            return False
        s    = self.skrypty[idx]
        prob = issue["problem"]
        kod  = s.get("kod", "")
        changed = False

        if "Końcowe spacje" in prob and self.naprawa_opts["trailing"].get():
            new = "\n".join(l.rstrip() for l in kod.splitlines())
            if new != kod:
                s["kod"] = new; changed = True

        if "tabulacji" in prob and self.naprawa_opts["tabs"].get():
            new = kod.replace("\t", "    ")
            if new != kod:
                s["kod"] = new; changed = True

        if "nowej linii" in prob and self.naprawa_opts["newlines"].get():
            new = kod.replace("\r\n", "\n").replace("\r", "\n")
            if new != kod:
                s["kod"] = new; changed = True

        if "puste linie" in prob and self.naprawa_opts["blank"].get():
            new = re2.sub(r"\n{3,}", "\n\n", kod)
            if new != kod:
                s["kod"] = new; changed = True

        if "kategoria" in prob and self.naprawa_opts["fields"].get():
            if not s.get("kategoria", "").strip():
                s["kategoria"] = "Other"; changed = True

        if "opisu" in prob and self.naprawa_opts["fields"].get():
            if not s.get("opis", "").strip():
                s["opis"] = "(brak opisu)"; changed = True

        if "tagów" in prob and self.naprawa_opts["fields"].get():
            if not s.get("tagi", "").strip():
                s["tagi"] = "auto"; changed = True

        return changed

    def _naprawa_fix_all(self):
        if not self._naprawa_issues:
            messagebox.showinfo(_tr("Brak danych"), _tr("Najpierw wykonaj skan."))
            return
        naprawiono = 0
        for issue in self._naprawa_issues:
            if self._naprawa_fix_one(issue):
                issue["status"] = "Naprawiono"
                self.naprawa_tree.item(issue["iid"],
                    values=(self.skrypty[issue["skrypt_idx"]].get("nazwa","?"),
                            _tr(issue["problem"]), _tr(issue["priorytet"]), _tr("✔ Naprawiono")),
                    tags=("fixed",))
                naprawiono += 1
                self._naprawa_log_add(
                    _tr("  ✔ '{name}' — {prob}\n").format(
                        name=self.skrypty[issue['skrypt_idx']].get('nazwa','?'),
                        prob=_tr(issue['problem'])), "ok")
        self._naprawa_log_add(_tr("Naprawiono {n} problemów.\n").format(n=naprawiono), "head")
        self.lbl_naprawa_st.config(text=_tr("Naprawiono {n}").format(n=naprawiono), fg="#6dde84")

    def _naprawa_fix_selected(self):
        sel = self.naprawa_tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz problem z listy."))
            return
        for iid in sel:
            issue = next((x for x in self._naprawa_issues if x["iid"] == iid), None)
            if issue and self._naprawa_fix_one(issue):
                issue["status"] = "Naprawiono"
                self.naprawa_tree.item(iid,
                    values=(self.skrypty[issue["skrypt_idx"]].get("nazwa","?"),
                            _tr(issue["problem"]), _tr(issue["priorytet"]), _tr("✔ Naprawiono")),
                    tags=("fixed",))
                self._naprawa_log_add(
                    _tr("  ✔ '{name}' — {prob}\n").format(
                        name=self.skrypty[issue['skrypt_idx']].get('nazwa','?'),
                        prob=_tr(issue['problem'])), "ok")

    def _naprawa_log_add(self, msg, tag=""):
        self.naprawa_log.config(state="normal")
        self.naprawa_log.insert("end", msg, tag)
        self.naprawa_log.see("end")
        self.naprawa_log.config(state="disabled")

    def _naprawa_log_clear(self):
        self.naprawa_log.config(state="normal")
        self.naprawa_log.delete("1.0", "end")
        self.naprawa_log.config(state="disabled")

    def _naprawa_save(self):
        self._ensure_moduly_built()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_tr("Raport"), "*.txt"), (_tr("Wszystkie"), "*.*")])
        if path:
            lines = [_tr("RAPORT NAPRAWY — {d}\n").format(d=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))]
            for issue in self._naprawa_issues:
                idx = issue["skrypt_idx"]
                n   = self.skrypty[idx].get("nazwa","?") if idx < len(self.skrypty) else "?"
                lines.append(f"[{_tr(issue['priorytet'])}] {n} — {_tr(issue['problem'])} — {_tr(issue['status'])}")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            messagebox.showinfo(_tr("Zapisano"), _tr("Raport naprawy zapisany:\n{path}").format(path=path))

    # ── helper ────────────────────────────────────────────────────────────────
    def _set_text(self, widget, content):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.config(state="disabled")

    # ── Wspólne pomocniki: Załaduj / Odłącz dla pod-zakładek Modułów ─────────
    def _mod_zaladuj(self, tab_key):
        path = filedialog.askopenfilename(
            title=_tr("Załaduj moduł — {tab}").format(tab=tab_key),
            filetypes=[(_tr("Python"), "*.py"), (_tr("Bash"), "*.sh"),
                       (_tr("PowerShell"), "*.ps1"), (_tr("JavaScript"), "*.js"),
                       (_tr("Batch"), "*.bat *.cmd"), (_tr("VBScript"), "*.vbs"),
                       (_tr("Java"), "*.java"), (_tr("Archiwa JAR"), "*.jar"),
                       (_tr("C"), "*.c *.h"),
                       (_tr("C++"), "*.cpp *.cc *.cxx *.c++ *.hpp *.hh *.hxx"),
                       (_tr("Ruby"), "*.rb"), (_tr("Perl"), "*.pl"),
                       (_tr("PHP"), "*.php"), (_tr("WSF"), "*.wsf"),
                       (_tr("HTA"), "*.hta"), (_tr("HTML"), "*.html *.htm"),
                       (_tr("CSS"), "*.css"), (_tr("JSON"), "*.json"),
                       (_tr("Markdown"), "*.md *.markdown"),
                       (_tr("SQL"), "*.sql"), (_tr("Wszystkie"), "*.*")])
        if not path:
            return
        try:
            name = os.path.basename(path)
            ext = os.path.splitext(name)[1].lower()
            if ext in BIN_EXT:
                kod = jar_base64(path)
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    kod = fh.read()
            # dodaj do bazy jako nowy skrypt jeśli nie istnieje
            existing = [s["nazwa"] for s in self.skrypty]
            if name not in existing:
                kat = EXT_KAT.get(ext, "Other")
                self.skrypty.append(sc_normalize({
                    "nazwa": name, "kategoria": kat,
                    "tagi": f"modul,{tab_key}",
                    "opis": f"Załadowany jako moduł z: {path}",
                    "kod": kod,
                }))
                self._rebuild_index()
                self._update_count()
                self._after_db_change()
                messagebox.showinfo(_tr("Załadowano"),
                    _tr("Moduł '{name}' załadowany i dodany do bazy skryptów.").format(name=name))
            else:
                messagebox.showinfo(_tr("Załadowano"),
                    _tr("Plik '{name}' już istnieje w bazie — pomięto duplikat.").format(name=name))
        except Exception as e:
            messagebox.showerror(_tr("Błąd"), str(e))

    def _mod_odlacz(self, tab_key):
        # Odłącz = usuń skrypty otagowane jako moduł tej zakładki
        candidates = [s for s in self.skrypty if tab_key in s.get("tagi", "")]
        if not candidates:
            messagebox.showinfo(_tr("Odłącz"), _tr("Brak modułów oznaczonych tagiem '{tag}'.").format(tag=tab_key))
            return
        names = [s["nazwa"] for s in candidates]
        if messagebox.askyesno(_tr("Odłącz moduły"),
                               _tr("Odłączyć {n} moduł(ów)?\n").format(n=len(names)) +
                               "\n".join(f"• {n}" for n in names[:10]) +
                               ("\n…" if len(names) > 10 else "")):
            self.skrypty = [s for s in self.skrypty if tab_key not in s.get("tagi", "")]
            self._update_count()
            messagebox.showinfo(_tr("Odłączono"), _tr("Odłączono {n} moduł(ów).").format(n=len(names)))

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 6: KREATOR PLUGINÓW
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_plugin(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["plugin"] = frame

        # ── nagłówek ──────────────────────────────────────────────────────────
        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("🔌 Kreator Pluginów — generuj gotowy plugin z nowymi komendami"),
                 font=("Consolas", 11, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), "🔌 Kreator Pluginów — generuj gotowy plugin z nowymi komendami").pack(side="left")
        self.lbl_plugin_status = self._trw(tk.Label(hdr, text=_tr("Gotowy do generowania"),
                                           font=FONT_UI, bg=BG_PANEL, fg="#6dde84"), "Gotowy do generowania")
        self.lbl_plugin_status.pack(side="right", padx=8)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # ════════════════
        # LEWA: formularz
        # ════════════════
        left = tk.Frame(body, bg=BG_PANEL, width=330,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 5))
        left.pack_propagate(False)

        # Formularz jest przewijany pionowo — pola mogą przekraczać wysokość okna.
        l_sb = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=10)
        l_sb.pack(side="right", fill="y")
        l_canvas = tk.Canvas(left, bg=BG_PANEL, highlightthickness=0,
                             yscrollcommand=l_sb.set)
        l_canvas.pack(side="left", fill="both", expand=True)
        l_sb.config(command=l_canvas.yview)
        left = tk.Frame(l_canvas, bg=BG_PANEL)
        l_win = l_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>",
                  lambda _e: l_canvas.configure(scrollregion=l_canvas.bbox("all")))
        l_canvas.bind("<Configure>",
                      lambda e: l_canvas.itemconfigure(l_win, width=e.width))

        def section(txt):
            tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 2))
            self._trw(tk.Label(left, text=_tr(txt), font=FONT_BOLD, bg=BG_PANEL,
                     fg=ACCENT_BLUE), txt).pack(anchor="w", padx=10)

        # — Podstawowe info —
        self._trw(tk.Label(left, text=_tr("📦 Informacje o pluginie"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "📦 Informacje o pluginie").pack(anchor="w", padx=10, pady=(10, 4))

        def lbl_entry(parent, label, width=28):
            row = tk.Frame(parent, bg=BG_PANEL)
            row.pack(fill="x", padx=10, pady=2)
            self._trw(tk.Label(row, text=_tr(label), font=FONT_UI, bg=BG_PANEL,
                     fg=FG_GRAY, width=14, anchor="w"), label).pack(side="left")
            e = tk.Entry(row, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat",
                         highlightthickness=1, highlightbackground=BORDER_CLR,
                         highlightcolor=ACCENT_BLUE, width=width)
            e.pack(side="left", fill="x", expand=True)
            return e

        self.plugin_nazwa     = lbl_entry(left, "Nazwa pluginu:")
        self.plugin_autor     = lbl_entry(left, "Autor:")
        self.plugin_wersja    = lbl_entry(left, "Wersja:")
        self.plugin_wersja.insert(0, "1.0.0")
        self.plugin_opis_e    = lbl_entry(left, "Opis:")

        section("⚙ Typ pluginu")
        self.var_plugin_typ = tk.StringVar(value="standalone")
        typy = [
            ("Samodzielny skrypt (.py)",  "standalone"),
            ("Moduł biblioteki",           "library"),
            ("Plugin CLI (argparse)",      "cli"),
            ("Plugin Flask/API",           "flask"),
        ]
        for lbl, val in typy:
            self._trw(tk.Radiobutton(left, text=_tr(lbl), variable=self.var_plugin_typ, value=val,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT), lbl).pack(anchor="w", padx=16)

        section("📋 Komendy / funkcje")
        self._trw(tk.Label(left, text=_tr("Dodaj komendy (jedna per linia):"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Dodaj komendy (jedna per linia):").pack(anchor="w", padx=10, pady=(4, 2))
        self.plugin_komendy = tk.Text(left, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                       insertbackground=FG_WHITE, relief="flat", height=6,
                                       highlightthickness=1, highlightbackground=BORDER_CLR,
                                       highlightcolor=ACCENT_BLUE)
        self.plugin_komendy.pack(fill="x", padx=10, pady=(0, 4))
        self.plugin_komendy.insert("1.0", "komenda_1\nkomenda_2\nkomenda_3")

        section("🔧 Opcje generowania")
        self.var_plugin_docstring  = tk.BooleanVar(value=True)
        self.var_plugin_logging    = tk.BooleanVar(value=True)
        self.var_plugin_typehints  = tk.BooleanVar(value=True)
        self.var_plugin_main       = tk.BooleanVar(value=True)
        self.var_plugin_tests      = tk.BooleanVar(value=False)
        opts_chk = [
            ("Docstringi",         self.var_plugin_docstring),
            ("Logowanie (logging)", self.var_plugin_logging),
            ("Type hints",          self.var_plugin_typehints),
            ("Blok __main__",       self.var_plugin_main),
            ("Szkielet testów",     self.var_plugin_tests),
        ]
        chk_frame = tk.Frame(left, bg=BG_PANEL)
        chk_frame.pack(fill="x", padx=10, pady=4)
        for lbl, var in opts_chk:
            self._trw(tk.Checkbutton(chk_frame, text=_tr(lbl), variable=var, font=FONT_UI,
                           bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT), lbl).pack(anchor="w")

        tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 4))
        btn_gen = tk.Frame(left, bg=BG_PANEL)
        btn_gen.pack(fill="x", padx=10, pady=(0, 8))
        self._trw(tk.Button(btn_gen, text=_tr("⚡ Generuj plugin"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=12, pady=6,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._plugin_generuj), "⚡ Generuj plugin").pack(fill="x", pady=2)
        self._trw(tk.Button(btn_gen, text=_tr("📥 Załaduj"), font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("plugin")), "📥 Załaduj").pack(side="left", pady=2, fill="x", expand=True, padx=(0, 2))
        self._trw(tk.Button(btn_gen, text=_tr("🔌 Odłącz"), font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("plugin")), "🔌 Odłącz").pack(side="left", pady=2, fill="x", expand=True, padx=(2, 0))

        # ══════════════════
        # PRAWA: podgląd + akcje
        # ══════════════════
        right = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="both", expand=True)

        top_r = tk.Frame(right, bg=BG_PANEL, pady=6, padx=8)
        top_r.pack(fill="x")
        self._trw(tk.Label(top_r, text=_tr("📄 Wygenerowany kod pluginu:"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), "📄 Wygenerowany kod pluginu:").pack(side="left")

        act_bar = tk.Frame(right, bg=BG_PANEL, padx=8)
        act_bar.pack(fill="x")
        self._trw(tk.Button(act_bar, text=_tr("💾 Zapisz w bazie"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_zapisz_w_bazie), "💾 Zapisz w bazie").pack(side="left", padx=2, pady=4)
        self._trw(tk.Button(act_bar, text=_tr("📁 Eksportuj .py"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_eksportuj), "📁 Eksportuj .py").pack(side="left", padx=2, pady=4)
        self._trw(tk.Button(act_bar, text=_tr("📋 Kopiuj kod"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_kopiuj), "📋 Kopiuj kod").pack(side="left", padx=2, pady=4)
        self._trw(tk.Button(act_bar, text=_tr("🗑 Wyczyść"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_wyczysc), "🗑 Wyczyść").pack(side="left", padx=2, pady=4)
        self.lbl_plugin_lines = tk.Label(act_bar, text="",
                                          font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self.lbl_plugin_lines.pack(side="right", padx=8)

        tk.Frame(right, bg=BORDER_CLR, height=1).pack(fill="x")

        plugin_kod_frame = tk.Frame(right, bg=BG_DARK)
        plugin_kod_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.plugin_line_nums = tk.Text(plugin_kod_frame, font=FONT_MONO,
                                         bg=BG_PANEL, fg=FG_GRAY, width=4,
                                         state="disabled", relief="flat",
                                         highlightthickness=0, bd=0)
        self.plugin_line_nums.pack(side="left", fill="y")

        pl_sc = tk.Scrollbar(plugin_kod_frame, orient="vertical", bg=BG_PANEL,
                              troughcolor=BG_PANEL, width=10)
        pl_sc.pack(side="right", fill="y")

        self.plugin_text = tk.Text(plugin_kod_frame, font=FONT_MONO,
                                    bg=BG_INPUT, fg="#c8d0f0",
                                    insertbackground=FG_WHITE, relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER_CLR,
                                    highlightcolor=ACCENT_BLUE, wrap="none",
                                    yscrollcommand=pl_sc.set, tabs="4c")
        self.plugin_text.pack(side="left", fill="both", expand=True)
        pl_sc.config(command=lambda *a: (self.plugin_text.yview(*a),
                                         self._plugin_update_lines()))
        self.plugin_text.bind("<KeyRelease>", self._plugin_update_lines)

    def _plugin_update_lines(self, _e=None):
        self.plugin_line_nums.config(state="normal")
        self.plugin_line_nums.delete("1.0", "end")
        n = int(self.plugin_text.index("end-1c").split(".")[0])
        self.plugin_line_nums.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self.plugin_line_nums.config(state="disabled")
        self.lbl_plugin_lines.config(text=_tr("Linii kodu: {n}").format(n=n))

    def _plugin_generuj(self):
        nazwa   = self.plugin_nazwa.get().strip()
        autor   = self.plugin_autor.get().strip() or "Nieznany"
        wersja  = self.plugin_wersja.get().strip() or "1.0.0"
        opis    = self.plugin_opis_e.get().strip() or "Plugin wygenerowany przez CodeMate"
        typ     = self.var_plugin_typ.get()
        komendy_raw = self.plugin_komendy.get("1.0", "end-1c").strip().splitlines()
        komendy = [k.strip() for k in komendy_raw if k.strip()]

        if not nazwa:
            messagebox.showwarning(_tr("Brak nazwy"), _tr("Podaj nazwę pluginu!"))
            return
        if not komendy:
            messagebox.showwarning(_tr("Brak komend"), _tr("Dodaj przynajmniej jedną komendę."))
            return

        use_doc  = self.var_plugin_docstring.get()
        use_log  = self.var_plugin_logging.get()
        use_type = self.var_plugin_typehints.get()
        use_main = self.var_plugin_main.get()
        use_test = self.var_plugin_tests.get()

        lines = []
        # Nagłówek
        lines += [
            f"# {'=' * 68}",
            f"# Plugin: {nazwa}",
            f"# Autor:  {autor}",
            f"# Wersja: {wersja}",
            f"# Opis:   {opis}",
            f"# Typ:    {typ}",
            f"# Wygenerowano: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# {'=' * 68}",
            "",
        ]

        # Importy
        imports = ["import os", "import sys"]
        if use_log:
            imports.append("import logging")
        if typ == "cli":
            imports.append("import argparse")
        if typ == "flask":
            imports += ["from flask import Flask, request, jsonify"]
        lines += imports + [""]

        # Logging setup
        if use_log:
            lines += [
                "logging.basicConfig(",
                "    level=logging.INFO,",
                "    format='%(asctime)s [%(levelname)s] %(message)s'",
                ")",
                f"logger = logging.getLogger('{nazwa}')",
                "",
            ]

        # Klasa pluginu
        class_name = "".join(w.capitalize() for w in nazwa.replace("-", "_").split("_"))
        lines += [f"class {class_name}Plugin:"]
        if use_doc:
            lines += [
                f'    """{opis}',
                f"",
                f"    Autor:  {autor}",
                f"    Wersja: {wersja}",
                f'    """',
            ]
        lines += [""]

        # __init__
        lines += ["    def __init__(self):"]
        if use_doc:
            lines += ['        """Inicjalizacja pluginu."""']
        if use_log:
            lines += [f"        logger.info('Plugin {nazwa} v{wersja} — zainicjalizowany')"]
        lines += [
            "        self.version = " + f'"{wersja}"',
            "        self.name    = " + f'"{nazwa}"',
            "",
        ]

        # Komendy
        for komenda in komendy:
            safe = komenda.replace(" ", "_").replace("-", "_")
            if use_type:
                sig = f"    def {safe}(self, *args, **kwargs) -> None:"
            else:
                sig = f"    def {safe}(self, *args, **kwargs):"
            lines.append(sig)
            if use_doc:
                lines += [
                    f'        """Wykonuje komendę: {komenda}.',
                    f"",
                    f"        Args:",
                    f"            *args:    Argumenty pozycyjne.",
                    f"            **kwargs: Argumenty słownikowe.",
                    f'        """',
                ]
            if use_log:
                lines.append(f"        logger.info('Wywołano: {komenda}')")
            lines += [
                f"        # TODO: implementacja komendy '{komenda}'",
                "        raise NotImplementedError(",
                f"            f\"Komenda '{komenda}' nie jest jeszcze zaimplementowana.\"",
                "        )",
                "",
            ]

        # run_command dispatcher
        lines += [
            "    def run_command(self, command" + (": str" if use_type else "") + ", *args, **kwargs)" + (" -> None:" if use_type else ":"),
        ]
        if use_doc:
            lines += [
                '        """Dispatcher — wywołuje komendę po nazwie."""',
            ]
        lines += [
            "        commands = {",
        ]
        for komenda in komendy:
            safe = komenda.replace(" ", "_").replace("-", "_")
            lines.append(f'            "{komenda}": self.{safe},')
        lines += [
            "        }",
            "        if command not in commands:",
            "            raise ValueError(f'Nieznana komenda: {command}')",
            "        commands[command](*args, **kwargs)",
            "",
        ]

        # Flask routes
        if typ == "flask":
            lines += [
                "app = Flask(__name__)",
                f"_plugin = {class_name}Plugin()",
                "",
                "@app.route('/run/<command>', methods=['POST'])",
                "def api_run(command):",
                "    data = request.get_json(force=True) or {}",
                "    try:",
                "        _plugin.run_command(command, **data)",
                "        return jsonify({'status': 'ok', 'command': command})",
                "    except Exception as e:",
                "        return jsonify({'status': 'error', 'message': str(e)}), 400",
                "",
            ]

        # CLI
        if typ == "cli":
            lines += [
                "def _build_parser():",
                "    parser = argparse.ArgumentParser(",
                f"        prog='{nazwa}',",
                f"        description='{opis}'",
                "    )",
                "    sub = parser.add_subparsers(dest='command', required=True)",
            ]
            for komenda in komendy:
                lines.append(f"    sub.add_parser('{komenda}', help='Wykonuje {komenda}')")
            lines += [
                "    return parser",
                "",
            ]

        # __main__
        if use_main:
            lines += ["", "if __name__ == '__main__':"]
            if typ == "flask":
                lines += [
                    "    print(f'Uruchamianie API pluginu {nazwa}...')",
                    "    app.run(debug=True, port=5000)",
                ]
            elif typ == "cli":
                lines += [
                    "    parser = _build_parser()",
                    "    args = parser.parse_args()",
                    f"    plugin = {class_name}Plugin()",
                    "    plugin.run_command(args.command)",
                ]
            else:
                lines += [
                    f"    plugin = {class_name}Plugin()",
                    "    print(f'Plugin: {plugin.name}  v{plugin.version}')",
                    "    print('Dostępne komendy:')",
                ]
                for komenda in komendy:
                    lines.append(f"    print('  - {komenda}')")

        # Szkielet testów
        if use_test:
            lines += [
                "",
                "# ── Testy (unittest) ────────────────────────────────────────",
                "import unittest",
                "",
                f"class Test{class_name}Plugin(unittest.TestCase):",
            ]
            if use_doc:
                lines += [f'    """Testy jednostkowe dla {class_name}Plugin."""']
            lines += [""]
            for komenda in komendy:
                safe = komenda.replace(" ", "_").replace("-", "_")
                lines += [
                    f"    def test_{safe}(self):",
                    f"        plugin = {class_name}Plugin()",
                    "        with self.assertRaises(NotImplementedError):",
                    f"            plugin.{safe}()",
                    "",
                ]
            lines += [
                "if __name__ == '__main__':",
                "    unittest.main()",
            ]

        kod = "\n".join(lines)
        self.plugin_text.delete("1.0", "end")
        self.plugin_text.insert("1.0", kod)
        self._plugin_update_lines()
        self.lbl_plugin_status.config(
            text=_tr("✔ Plugin '{nazwa}' wygenerowany — {n} komend(y)").format(nazwa=nazwa, n=len(komendy)),
            fg="#6dde84")

    def _plugin_zapisz_w_bazie(self):
        nazwa = self.plugin_nazwa.get().strip()
        if not nazwa:
            messagebox.showwarning(_tr("Brak nazwy"), _tr("Podaj nazwę pluginu przed zapisem."))
            return
        kod = self.plugin_text.get("1.0", "end-1c")
        if not kod.strip():
            messagebox.showwarning(_tr("Brak kodu"), _tr("Wygeneruj najpierw plugin."))
            return
        for i, s in enumerate(self.skrypty):
            if s["nazwa"] == nazwa:
                self.skrypty[i]["kod"] = kod
                self.skrypty[i]["checksum"] = kod_checksum(kod)
                self.skrypty[i]["zmieniony"] = now_str()
                self._after_db_change()
                messagebox.showinfo(_tr("Zapisano"), _tr("Plugin '{nazwa}' zaktualizowany w bazie.").format(nazwa=nazwa))
                self._update_count()
                return
        self.skrypty.append(sc_normalize({
            "nazwa":     nazwa,
            "kategoria": "Python",
            "tagi":      "plugin,modul",
            "opis":      self.plugin_opis_e.get().strip() or "",
            "kod":       kod,
        }))
        self._rebuild_index()
        self._update_count()
        self._after_db_change()
        messagebox.showinfo(_tr("Zapisano"), _tr("Plugin '{nazwa}' dodany do bazy — gotowy do pracy!").format(nazwa=nazwa))

    def _plugin_eksportuj(self):
        nazwa = self.plugin_nazwa.get().strip() or "plugin"
        kod   = self.plugin_text.get("1.0", "end-1c")
        if not kod.strip():
            messagebox.showwarning(_tr("Brak kodu"), _tr("Wygeneruj najpierw plugin."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            initialfile=nazwa,
            filetypes=[(_tr("Python"), "*.py"), (_tr("Wszystkie"), "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(kod)
            messagebox.showinfo(_tr("Eksport"), _tr("Plugin zapisany jako plik:\n{path}").format(path=path))

    def _plugin_kopiuj(self):
        self.clipboard_clear()
        self.clipboard_append(self.plugin_text.get("1.0", "end-1c"))
        messagebox.showinfo(_tr("Skopiowano"), _tr("Kod pluginu skopiowany do schowka."))

    def _plugin_wyczysc(self):
        self.plugin_text.delete("1.0", "end")
        self._plugin_update_lines()
        self.lbl_plugin_status.config(text=_tr("Gotowy do generowania"), fg="#6dde84")

    def _build_narzedzia_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["narzedzia"] = outer

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("🔧 Narzędzia"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), "🔧 Narzędzia").pack(side="left")
        self._trw(tk.Label(hdr, text=_tr("Sebastian Januchowski · polsoft.ITS™ Group"),
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), "Sebastian Januchowski · polsoft.ITS™ Group").pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        # Główny pionowy PanedWindow (góra/dół)
        vpaned = tk.PanedWindow(outer, orient="vertical", bg=BG_DARK,
                                sashwidth=6, sashrelief="flat",
                                sashpad=2, handlesize=8,
                                opaqueresize=True)
        vpaned.pack(fill="both", expand=True, padx=4, pady=4)

        # ── GÓRNA połowa: poziomy PanedWindow ────────────────────────────────
        top_paned = tk.PanedWindow(vpaned, orient="horizontal", bg=BG_DARK,
                                   sashwidth=6, sashrelief="flat",
                                   sashpad=2, handlesize=8,
                                   opaqueresize=True)
        vpaned.add(top_paned, stretch="always")

        # Panel 1: Kopiuj / Wczytaj / Importuj
        p1 = tk.Frame(top_paned, bg=BG_PANEL,
                      highlightthickness=1, highlightbackground=BORDER_CLR)
        top_paned.add(p1, stretch="always")
        self._trw(tk.Label(p1, text=_tr("📂 Operacje na plikach"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE), "📂 Operacje na plikach").pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p1, bg=BORDER_CLR, height=1).pack(fill="x")
        for txt, cmd in [
            ("📋 Kopiuj kod",         self._kopiuj_kod),
            ("📂 Wczytaj plik…",      self._wczytaj_plik),
            ("📁 Importuj katalog…",   self._importuj_katalog),
            ("⬆ Eksportuj (.py)…",   lambda: self._eksportuj("py")),
            ("⬆ Eksportuj (.txt)…",  lambda: self._eksportuj("txt")),
            ("📥 Importuj bazę…",     self._lista_importuj),
            ("📤 Eksportuj bazę…",    self._lista_eksportuj),
        ]:
            self._trw(tk.Button(p1, text=_tr(txt), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2", anchor="w",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(fill="x", padx=8, pady=2)

        # Panel 2: Diagnostyka i Naprawa
        p2 = tk.Frame(top_paned, bg=BG_PANEL,
                      highlightthickness=1, highlightbackground=BORDER_CLR)
        top_paned.add(p2, stretch="always")
        self._trw(tk.Label(p2, text=_tr("🔬 Diagnostyka i Naprawa"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE), "🔬 Diagnostyka i Naprawa").pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p2, bg=BORDER_CLR, height=1).pack(fill="x")
        for txt, cmd in [
            ("▶ Uruchom diagnostykę",  self._run_diag),
            ("🔧 Naprawa błędów",       self._naprawa_scan),
            ("📊 Statystyki bazy",      self._menu_statystyki),
            ("🔄 Odśwież widoki",       self._menu_odswiez),
            ("🗑 Wyczyść całą bazę…",   self._menu_wyczysc_baze),
        ]:
            self._trw(tk.Button(p2, text=_tr(txt), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2", anchor="w",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(fill="x", padx=8, pady=2)

        # ── DOLNA połowa: poziomy PanedWindow ────────────────────────────────
        bot_paned = tk.PanedWindow(vpaned, orient="horizontal", bg=BG_DARK,
                                   sashwidth=6, sashrelief="flat",
                                   sashpad=2, handlesize=8,
                                   opaqueresize=True)
        vpaned.add(bot_paned, stretch="always")

        # Panel 3: Kreator Pluginów / Moduły
        p3 = tk.Frame(bot_paned, bg=BG_PANEL,
                      highlightthickness=1, highlightbackground=BORDER_CLR)
        bot_paned.add(p3, stretch="always")
        self._trw(tk.Label(p3, text=_tr("🔌 Kreator i Moduły"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE), '🔌 Kreator i Moduły').pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p3, bg=BORDER_CLR, height=1).pack(fill="x")
        for txt, cmd in [
            ("🔌 Kreator Pluginów",      self._menu_pokaz_plugin),
            ("🔗 Łączenie modułów",      self._menu_pokaz_laczen),
            ("🔑 Menedżer sekretów",     self._menu_sekrety),
            ("⚡ Testy osiągów",         self._run_testy),
            ("📋 Info o modułach",       lambda: self._menu_pokaz_mod("info")),
            ("🔄 Odśwież info modułów",  self._mod_refresh_info),
        ]:
            self._trw(tk.Button(p3, text=_tr(txt), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2", anchor="w",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(fill="x", padx=8, pady=2)

        # Panel 4: Informacje o autorze
        p4 = tk.Frame(bot_paned, bg=BG_PANEL,
                      highlightthickness=1, highlightbackground=BORDER_CLR)
        bot_paned.add(p4, stretch="always")
        self._trw(tk.Label(p4, text=_tr("👤 Informacje o autorze"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE), "👤 Informacje o autorze").pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p4, bg=BORDER_CLR, height=1).pack(fill="x")
        author_info = [
            ("Autor",   "Sebastian Januchowski"),
            ("Firma",   "polsoft.ITS™ Group"),
            ("GitHub",  "https://github.com/polsoft-IT"),
            ("E-mail",  "polsoft.its@mail.com"),
            ("Wersja",  "3.0"),
            ("Platforma", "Python 3 / Tkinter"),
        ]
        for label, value in author_info:
            row = tk.Frame(p4, bg=BG_PANEL)
            row.pack(fill="x", padx=10, pady=3)
            self._trw(tk.Label(row, text=_tr(f"{label}:"), font=FONT_BOLD, bg=BG_PANEL,
                     fg=FG_GRAY, width=10, anchor="w"), f"{label}:").pack(side="left")
            tk.Label(row, text=value, font=FONT_UI, bg=BG_PANEL,
                     fg=FG_WHITE, anchor="w").pack(side="left", padx=4)

        tk.Frame(p4, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 4))
        self._trw(tk.Button(p4, text=_tr("ℹ O programie"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=5, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._menu_o_programie), "ℹ O programie").pack(fill="x", padx=8, pady=2)

    def _show_narzedzia(self):
        self.main_frames["narzedzia"].pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: VirtualEnv — pełne zarządzanie środowiskami
    # ══════════════════════════════════════════════════════════════════════════
    def _build_venv_frame(self):
        import subprocess, sys, shutil
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["venv"] = outer

        # ── Nagłówek ─────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("🐍 VirtualEnv — Zarządzanie środowiskami Python"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), '🐍 VirtualEnv — Zarządzanie środowiskami Python').pack(side="left")
        self.venv_lbl_status = tk.Label(hdr, text=_tr("Gotowy"), font=FONT_UI,
                                         bg=BG_PANEL, fg="#6dde84")
        self.venv_lbl_status.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Pod-zakładki ──────────────────────────────────────────────────────
        venv_sub_bar = tk.Frame(outer, bg=BG_PANEL)
        venv_sub_bar.pack(fill="x")
        venv_content = tk.Frame(outer, bg=BG_DARK)
        venv_content.pack(fill="both", expand=True)

        self._venv_btns   = []
        self._venv_frames = {}

        def sel_venv(idx, key):
            for j, b in enumerate(self._venv_btns):
                b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                             fg=FG_WHITE       if j == idx else FG_GRAY)
            for f in self._venv_frames.values():
                f.pack_forget()
            self._venv_frames[key].pack(fill="both", expand=True)
            self._update_minsize()
            if key == "settings" and not self._venv_tools_checked:
                self._venv_refresh_tools()

        venv_tabs = [
            ("📋 Lista envów",    "lista"),
            ("➕ Utwórz env",    "create"),
            ("📦 Pakiety",        "pakiety"),
            ("📄 Requirements",   "req"),
            ("⚙ Ustawienia",     "settings"),
            ("📟 Log / Terminal", "log"),
        ]
        for j, (lbl, key) in enumerate(venv_tabs):
            b = self._trw(tk.Button(venv_sub_bar, text=_tr(lbl), font=FONT_UI,
                          bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY,
                          relief="flat", padx=14, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda j=j, k=key: sel_venv(j, k)), lbl)
            b.pack(side="left")
            self._venv_btns.append(b)

        # store selector for later use
        self._venv_sel = sel_venv

        # Stan zarządzania envami
        self._venv_dir   = tk.StringVar(value=os.path.expanduser("~/.virtualenvs"))
        self._venv_list  = []  # [{name, path, python, active}]
        self._venv_active = None  # aktualnie wybrany env
        self._venv_tools_checked = False
        self._venv_tools_loading = False

        self._build_venv_lista(venv_content)
        self._build_venv_create(venv_content)
        self._build_venv_pakiety(venv_content)
        self._build_venv_req(venv_content)
        self._build_venv_settings(venv_content)
        self._build_venv_log(venv_content)

        sel_venv(0, "lista")
        self.after(100, self._venv_refresh_list)

    # ── VENV helpers ─────────────────────────────────────────────────────────
    def _venv_log(self, msg, tag="info"):
        """Dopisz linię do logu terminala."""
        if not hasattr(self, "venv_log_text"):
            return
        self.venv_log_text.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.venv_log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self.venv_log_text.see("end")
        self.venv_log_text.config(state="disabled")

    def _venv_set_status(self, msg, color="#6dde84"):
        self.venv_lbl_status.config(text=msg, fg=color)

    def _venv_run(self, cmd, success_msg=None, error_prefix=None):
        """Uruchom polecenie subprocess, zaloguj wynik."""
        import subprocess
        success_msg = _tr(success_msg) if success_msg else ""
        error_prefix = _tr(error_prefix) if error_prefix else _tr("Błąd")
        self._venv_log(f"$ {' '.join(cmd)}", "cmd")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.stdout:
                for line in result.stdout.strip().splitlines():
                    self._venv_log(line, "out")
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    self._venv_log(line, "warn")
            if result.returncode == 0:
                self._venv_log(success_msg, "ok")
                self._venv_set_status(success_msg)
                return True
            else:
                self._venv_log(_tr("{error_prefix}: kod {code}").format(error_prefix=error_prefix, code=result.returncode), "error")
                self._venv_set_status(f"{error_prefix}!", "#e07070")
                return False
        except FileNotFoundError:
            self._venv_log(_tr("Nie znaleziono polecenia: {cmd}").format(cmd=cmd[0]), "error")
            self._venv_set_status(_tr("Błąd — brak polecenia"), "#e07070")
            return False
        except subprocess.TimeoutExpired:
            self._venv_log(_tr("Przekroczono limit czasu (120s)"), "error")
            self._venv_set_status("Timeout!", "#e07070")
            return False

    def _venv_python_in_env(self, env_path):
        """Zwróć ścieżkę do python w danym env."""
        import sys
        if os.name == "nt":
            return os.path.join(env_path, "Scripts", "python.exe")
        return os.path.join(env_path, "bin", "python")

    def _venv_pip_in_env(self, env_path):
        if os.name == "nt":
            return os.path.join(env_path, "Scripts", "pip.exe")
        return os.path.join(env_path, "bin", "pip")

    def _venv_refresh_list(self):
        """Skanuj katalog środowisk i odśwież listę."""
        base = self._venv_dir.get().strip()
        self._venv_list.clear()
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                path = os.path.join(base, name)
                py  = self._venv_python_in_env(path)
                if os.path.isfile(py):
                    self._venv_list.append({"name": name, "path": path})
        self._venv_update_listbox()
        self._venv_log(_tr("Znaleziono {n} środowisk w: {base}").format(n=len(self._venv_list), base=base), "info")

    def _venv_update_listbox(self):
        if not hasattr(self, "venv_listbox"):
            return
        self.venv_listbox.delete(0, "end")
        for env in self._venv_list:
            self.venv_listbox.insert("end", env["name"])

    def _venv_get_selected(self):
        """Zwróć słownik aktualnie zaznaczonego enva lub None."""
        if not hasattr(self, "venv_listbox"):
            return None
        sel = self.venv_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx < len(self._venv_list):
            return self._venv_list[idx]
        return None

    def _venv_on_select(self, event=None):
        env = self._venv_get_selected()
        if not env:
            return
        self._venv_active = env
        self._venv_set_status(_tr("Wybrano: {name}").format(name=env['name']))
        self._venv_fill_info(env)

    def _venv_fill_info(self, env):
        """Wypełnij panel informacyjny po wyborze enva."""
        import subprocess, sys
        if not hasattr(self, "venv_info_text"):
            return
        py = self._venv_python_in_env(env["path"])
        lines = [
            _tr("  Nazwa:   {v}").format(v=env['name']),
            _tr("  Ścieżka: {v}").format(v=env['path']),
            _tr("  Python:  {v}").format(v=py),
        ]
        # wersja pythona
        try:
            r = subprocess.run([py, "--version"], capture_output=True, text=True, timeout=5)
            ver = (r.stdout or r.stderr).strip()
            lines.append(_tr("  Wersja:  {v}").format(v=ver))
        except Exception:
            lines.append(_tr("  Wersja:  (nie można sprawdzić)"))
        # rozmiar
        try:
            total = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, dn, fn in os.walk(env["path"]) for f in fn
            )
            lines.append(_tr("  Rozmiar: {v}").format(v=f"{total / 1024 / 1024:.1f} MB"))
        except Exception:
            pass
        self.venv_info_text.config(state="normal")
        self.venv_info_text.delete("1.0", "end")
        self.venv_info_text.insert("1.0", "\n".join(lines))
        self.venv_info_text.config(state="disabled")

    # ── POD-ZAKŁADKA 1: Lista envów ──────────────────────────────────────────
    def _build_venv_lista(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["lista"] = frame

        # pasek akcji
        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")

        def btn(text, cmd, color=BTN_DARK):
            self._trw(tk.Button(bar, text=_tr(text), font=FONT_UI, bg=color, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), text).pack(side="left", padx=3)

        btn("🔄 Odśwież",        self._venv_refresh_list)
        btn("➕ Utwórz nowy",    lambda: self._venv_sel(1, "create"), ACCENT_BLUE)
        btn("🗑 Usuń env",       self._venv_delete)
        btn("📋 Kopiuj ścieżkę", self._venv_copy_path)
        btn("📂 Otwórz folder",  self._venv_open_folder)

        tk.Frame(bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=8, pady=3)
        self._trw(tk.Label(bar, text=_tr("Katalog envów:"), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY), 'Katalog envów:').pack(side="left")
        venv_dir_e = tk.Entry(bar, textvariable=self._venv_dir, font=FONT_MONO,
                              bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE,
                              relief="flat", highlightthickness=1,
                              highlightbackground=BORDER_CLR, highlightcolor=ACCENT_BLUE,
                              width=32)
        venv_dir_e.pack(side="left", padx=4)
        self._trw(tk.Button(bar, text=_tr("📁"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._venv_browse_dir), "📁").pack(side="left")

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # split: lista po lewej, info po prawej
        body = tk.PanedWindow(frame, orient="horizontal", bg=BG_DARK,
                              sashwidth=6, sashrelief="flat", opaqueresize=True)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # lista
        left = tk.Frame(body, bg=BG_PANEL,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        body.add(left, width=260)

        self._trw(tk.Label(left, text=_tr("🐍 Środowiska wirtualne"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), '🐍 Środowiska wirtualne').pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x")

        sc_l = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                             troughcolor=BG_PANEL, width=8)
        sc_l.pack(side="right", fill="y", pady=4, padx=(0, 2))
        self.venv_listbox = tk.Listbox(left, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                        selectmode="single", relief="flat",
                                        highlightthickness=0, selectbackground=BG_ROW_SEL,
                                        activestyle="none", yscrollcommand=sc_l.set)
        sc_l.config(command=self.venv_listbox.yview)
        self.venv_listbox.pack(fill="both", expand=True, padx=(8, 0), pady=4)
        self.venv_listbox.bind("<<ListboxSelect>>", self._venv_on_select)

        # info panel
        right = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        body.add(right, stretch="always")

        self._trw(tk.Label(right, text=_tr("ℹ Informacje o środowisku"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE), 'ℹ Informacje o środowisku').pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(right, bg=BORDER_CLR, height=1).pack(fill="x")

        self.venv_info_text = tk.Text(right, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                       relief="flat", state="disabled", wrap="word",
                                       highlightthickness=1, highlightbackground=BORDER_CLR,
                                       height=8)
        self.venv_info_text.pack(fill="x", padx=8, pady=8)

        tk.Frame(right, bg=BORDER_CLR, height=1).pack(fill="x", padx=8)
        act_bar = tk.Frame(right, bg=BG_PANEL, pady=6, padx=8)
        act_bar.pack(fill="x")

        def abtn(text, cmd, color=BTN_DARK):
            self._trw(tk.Button(act_bar, text=_tr(text), font=FONT_UI, bg=color, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER,
                      command=cmd), text).pack(side="left", padx=3)

        abtn("📦 Pokaż pakiety",     self._venv_show_packages)
        abtn("⬆ Aktualizuj pip",    self._venv_upgrade_pip, BTN_OK)
        abtn("🗑 Usuń env",          self._venv_delete, BTN_ERR)

    def _venv_browse_dir(self):
        d = filedialog.askdirectory(title=_tr("Wybierz katalog środowisk"))
        if d:
            self._venv_dir.set(d)
            self._venv_refresh_list()

    def _venv_delete(self):
        import shutil
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz środowisko z listy."))
            return
        if messagebox.askyesno(_tr("Usuń env"),
                               _tr("Usunąć środowisko '{name}'?\n{path}\n\nTej operacji nie można cofnąć!").format(name=env['name'], path=env['path'])):
            try:
                shutil.rmtree(env["path"])
                self._venv_log(_tr("Usunięto: {name}").format(name=env['name']), "ok")
                self._venv_set_status(_tr("Usunięto: {name}").format(name=env['name']))
                self._venv_refresh_list()
            except Exception as e:
                self._venv_log(_tr("Błąd usuwania: {e}").format(e=e), "error")
                messagebox.showerror(_tr("Błąd"), str(e))

    def _venv_copy_path(self):
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz środowisko z listy."))
            return
        self.clipboard_clear()
        self.clipboard_append(env["path"])
        messagebox.showinfo(_tr("Skopiowano"), _tr("Ścieżka skopiowana:\n{path}").format(path=env['path']))

    def _venv_open_folder(self):
        import subprocess, sys
        env = self._venv_get_selected()
        path = env["path"] if env else self._venv_dir.get()
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror(_tr("Błąd"), str(e))

    def _venv_show_packages(self):
        """Przełącz na zakładkę Pakiety i załaduj listę."""
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz środowisko z listy."))
            return
        self._venv_active = env
        self._venv_sel(2, "pakiety")
        self._venv_load_packages()

    def _venv_upgrade_pip(self):
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz środowisko z listy."))
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(_tr("Aktualizuję pip w: {name}").format(name=env['name']), "info")
        self.after(50, lambda: self._venv_run(
            [pip, "install", "--upgrade", "pip"],
            success_msg=_tr("pip zaktualizowany!")))

    # ── POD-ZAKŁADKA 2: Utwórz env ───────────────────────────────────────────
    def _build_venv_create(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["create"] = frame

        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("➕ Utwórz nowe środowisko wirtualne"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), '➕ Utwórz nowe środowisko wirtualne').pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        def row(label, widget_factory):
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=5)
            self._trw(tk.Label(r, text=_tr(label), font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=22, anchor="w"), label).pack(side="left")
            w = widget_factory(r)
            w.pack(side="left", fill="x", expand=True)
            return w

        # Nazwa
        self.venv_new_name = row("Nazwa środowiska:",
            lambda p: tk.Entry(p, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                               insertbackground=FG_WHITE, relief="flat",
                               highlightthickness=1, highlightbackground=BORDER_CLR,
                               highlightcolor=ACCENT_BLUE))

        # Katalog docelowy
        dir_row = tk.Frame(body, bg=BG_DARK)
        dir_row.pack(fill="x", pady=5)
        self._trw(tk.Label(dir_row, text=_tr("Katalog docelowy:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w"), "Katalog docelowy:").pack(side="left")
        self.venv_new_dir = tk.Entry(dir_row, textvariable=self._venv_dir,
                                     font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                     insertbackground=FG_WHITE, relief="flat",
                                     highlightthickness=1, highlightbackground=BORDER_CLR,
                                     highlightcolor=ACCENT_BLUE)
        self.venv_new_dir.pack(side="left", fill="x", expand=True)
        self._trw(tk.Button(dir_row, text=_tr("📁"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._venv_browse_dir), "📁").pack(side="left", padx=4)

        # Interpreter Pythona
        import sys
        py_row = tk.Frame(body, bg=BG_DARK)
        py_row.pack(fill="x", pady=5)
        self._trw(tk.Label(py_row, text=_tr("Interpreter Python:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w"), "Interpreter Python:").pack(side="left")
        self.venv_new_python = tk.Entry(py_row, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                        insertbackground=FG_WHITE, relief="flat",
                                        highlightthickness=1, highlightbackground=BORDER_CLR,
                                        highlightcolor=ACCENT_BLUE)
        self.venv_new_python.insert(0, sys.executable)
        self.venv_new_python.pack(side="left", fill="x", expand=True)
        self._trw(tk.Button(py_row, text=_tr("📁"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._venv_browse_python), "📁").pack(side="left", padx=4)

        # Opcje
        opts = tk.Frame(body, bg=BG_DARK)
        opts.pack(fill="x", pady=8)
        tk.Label(opts, text=_tr("Opcje:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self.venv_opt_pip       = tk.BooleanVar(value=True)
        self.venv_opt_system    = tk.BooleanVar(value=False)
        self.venv_opt_clear     = tk.BooleanVar(value=False)
        self.venv_opt_upgrade   = tk.BooleanVar(value=False)
        for text, var in [
            ("Instaluj pip",           self.venv_opt_pip),
            ("Dostęp do system-site",  self.venv_opt_system),
            ("Wyczyść jeśli istnieje", self.venv_opt_clear),
            ("Aktualizuj deps",        self.venv_opt_upgrade),
        ]:
            self._trw(tk.Checkbutton(opts, text=_tr(text), variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT), text).pack(side="left", padx=10)

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=12)

        btn_row = tk.Frame(body, bg=BG_DARK)
        btn_row.pack(fill="x")
        self._trw(tk.Button(btn_row, text=_tr("✅ Utwórz środowisko"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat",
                  padx=18, pady=8, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._venv_create), '✅ Utwórz środowisko').pack(side="left", padx=4)
        self._trw(tk.Button(btn_row, text=_tr("🧹 Wyczyść formularz"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=lambda: (self.venv_new_name.delete(0, "end"),
                                   self.venv_create_progress.config(text=""))), '🧹 Wyczyść formularz').pack(side="left", padx=4)

        self.venv_create_progress = tk.Label(body, text="", font=FONT_UI,
                                              bg=BG_DARK, fg="#6dde84")
        self.venv_create_progress.pack(anchor="w", pady=8)

    def _venv_browse_python(self):
        path = filedialog.askopenfilename(
            title=_tr("Wybierz interpreter Python"),
            filetypes=[("Python", "python* python3* python.exe"),
                       ("Wszystkie", "*.*")])
        if path:
            self.venv_new_python.delete(0, "end")
            self.venv_new_python.insert(0, path)

    def _venv_create(self):
        import subprocess
        name   = self.venv_new_name.get().strip()
        base   = self._venv_dir.get().strip()
        python = self.venv_new_python.get().strip()

        if not name:
            messagebox.showwarning(_tr("Brak nazwy"), _tr("Podaj nazwę środowiska."))
            return
        if not base:
            messagebox.showwarning(_tr("Brak katalogu"), _tr("Podaj katalog docelowy."))
            return

        env_path = os.path.join(base, name)
        os.makedirs(base, exist_ok=True)

        cmd = [python, "-m", "venv"]
        if not self.venv_opt_pip.get():
            cmd.append("--without-pip")
        if self.venv_opt_system.get():
            cmd.append("--system-site-packages")
        if self.venv_opt_clear.get():
            cmd.append("--clear")
        if self.venv_opt_upgrade.get():
            cmd.append("--upgrade")
        cmd.append(env_path)

        self.venv_create_progress.config(text=_tr("⏳ Tworzenie '{name}'…").format(name=name), fg="#f0c050")
        self._venv_sel(5, "log")
        self._venv_log(_tr("Tworzenie środowiska: {name}").format(name=name), "info")
        self._venv_log(_tr("Ścieżka: {path}").format(path=env_path), "info")

        def do_create():
            ok = self._venv_run(cmd, success_msg=_tr("Środowisko '{name}' utworzone!").format(name=name))
            if ok:
                self.venv_create_progress.config(text=_tr("✅ Środowisko '{name}' gotowe!").format(name=name), fg="#6dde84")
                self._venv_refresh_list()
                self._venv_sel(0, "lista")
            else:
                self.venv_create_progress.config(text=_tr("❌ Błąd tworzenia '{name}'").format(name=name), fg="#e07070")

        self.after(50, do_create)

    # ── POD-ZAKŁADKA 3: Pakiety ──────────────────────────────────────────────
    def _build_venv_pakiety(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["pakiety"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")

        self.venv_pkg_env_label = self._trw(tk.Label(bar, text=_tr("— brak wybranego env —"),
                                            font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "— brak wybranego env —")
        self.venv_pkg_env_label.pack(side="left", padx=4)

        self._trw(tk.Button(bar, text=_tr("🔄 Odśwież listę"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_load_packages), '🔄 Odśwież listę').pack(side="right", padx=3)

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Install bar
        inst_bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        inst_bar.pack(fill="x")
        self._trw(tk.Label(inst_bar, text=_tr("Zainstaluj pakiet:"), font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY), "Zainstaluj pakiet:").pack(side="left")
        self.venv_pkg_install_e = tk.Entry(inst_bar, font=FONT_MONO, bg=BG_INPUT,
                                            fg=FG_WHITE, insertbackground=FG_WHITE,
                                            relief="flat", highlightthickness=1,
                                            highlightbackground=BORDER_CLR,
                                            highlightcolor=ACCENT_BLUE, width=30)
        self.venv_pkg_install_e.pack(side="left", padx=6)
        self.venv_pkg_install_e.bind("<Return>", lambda e: self._venv_install_pkg())
        self._trw(tk.Button(inst_bar, text=_tr("⬇ Instaluj"), font=FONT_UI, bg=BTN_OK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_OK_HOVER,
                  command=self._venv_install_pkg), "⬇ Instaluj").pack(side="left", padx=3)
        self._trw(tk.Button(inst_bar, text=_tr("⬆ Aktualizuj pip"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_upgrade_pip), "⬆ Aktualizuj pip").pack(side="left", padx=3)
        self._trw(tk.Button(inst_bar, text=_tr("🗑 Odinstaluj"), font=FONT_UI, bg=BTN_ERR, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_ERR_HOVER,
                  command=self._venv_uninstall_pkg), "🗑 Odinstaluj").pack(side="right", padx=3)

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Tabela pakietów
        pkg_wrap = tk.Frame(frame, bg=BG_DARK)
        pkg_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        cols = ("Pakiet", "Wersja", "Lokalizacja")
        style = ttk.Style()
        style.configure("Pkg.Treeview",
                        background=BG_ROW_ODD, foreground=FG_WHITE,
                        fieldbackground=BG_ROW_ODD, rowheight=22, font=FONT_UI)
        style.configure("Pkg.Treeview.Heading",
                        background=BG_PANEL, foreground=FG_GRAY,
                        font=FONT_BOLD, relief="flat")
        style.map("Pkg.Treeview",
                  background=[("selected", BG_ROW_SEL)],
                  foreground=[("selected", FG_WHITE)])

        vsb = tk.Scrollbar(pkg_wrap, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=10)
        vsb.pack(side="right", fill="y")
        self.venv_pkg_tree = ttk.Treeview(pkg_wrap, columns=cols,
                                           show="headings", style="Pkg.Treeview",
                                           yscrollcommand=vsb.set)
        vsb.config(command=self.venv_pkg_tree.yview)
        for col, w in [("Pakiet", 200), ("Wersja", 120), ("Lokalizacja", 500)]:
            self._trh(self.venv_pkg_tree, col, col)
            self.venv_pkg_tree.column(col, width=w, minwidth=80)
        self.venv_pkg_tree.pack(fill="both", expand=True)
        self.venv_pkg_tree.tag_configure("odd",  background=BG_ROW_ODD)
        self.venv_pkg_tree.tag_configure("even", background=BG_ROW_EVEN)

        self.venv_pkg_count = self._trw(tk.Label(frame, text=_tr("Pakietów: 0"),
                                        font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), 'Pakietów: 0')
        self.venv_pkg_count.pack(anchor="w", padx=10, pady=2)

    def _venv_load_packages(self):
        import subprocess, json
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak env"), _tr("Najpierw wybierz środowisko z Listy envów."))
            return
        pip = self._venv_pip_in_env(env["path"])
        self.venv_pkg_env_label.config(text=f"🐍 {env['name']}")
        self._venv_log(_tr("Ładowanie pakietów z: {name}").format(name=env['name']), "info")
        try:
            result = subprocess.run([pip, "list", "--format=json"],
                                    capture_output=True, text=True, timeout=30)
            pkgs = json.loads(result.stdout or "[]")
            for row in self.venv_pkg_tree.get_children():
                self.venv_pkg_tree.delete(row)
            for i, pkg in enumerate(pkgs):
                loc = ""
                try:
                    r2 = subprocess.run([pip, "show", pkg["name"]],
                                        capture_output=True, text=True, timeout=10)
                    for line in r2.stdout.splitlines():
                        if line.startswith("Location:"):
                            loc = line.split(":", 1)[1].strip()
                            break
                except Exception:
                    pass
                tag = "odd" if i % 2 == 0 else "even"
                self.venv_pkg_tree.insert("", "end",
                                           values=(pkg["name"], pkg["version"], loc),
                                           tags=(tag,))
            self.venv_pkg_count.config(text=_tr("Pakietów: {n}").format(n=len(pkgs)))
            self._venv_log(_tr("Załadowano {n} pakietów.").format(n=len(pkgs)), "ok")
        except Exception as e:
            self._venv_log(_tr("Błąd ładowania pakietów: {e}").format(e=e), "error")

    def _venv_install_pkg(self):
        pkg = self.venv_pkg_install_e.get().strip()
        env = self._venv_active or self._venv_get_selected()
        if not pkg:
            messagebox.showwarning(_tr("Brak pakietu"), _tr("Wpisz nazwę pakietu."))
            return
        if not env:
            messagebox.showinfo(_tr("Brak env"), _tr("Wybierz środowisko z Listy envów."))
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(_tr("Instaluję: {pkg} w {env}").format(pkg=pkg, env=env['name']), "info")
        self.after(50, lambda: (
            self._venv_run([pip, "install", pkg],
                           success_msg=_tr("Zainstalowano: {pkg}").format(pkg=pkg)),
            self._venv_load_packages()
        ))

    def _venv_uninstall_pkg(self):
        sel = self.venv_pkg_tree.selection()
        if not sel:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz pakiet z listy."))
            return
        pkg = self.venv_pkg_tree.item(sel[0])["values"][0]
        env = self._venv_active or self._venv_get_selected()
        if not env:
            return
        if not messagebox.askyesno(_tr("Odinstaluj"), _tr("Odinstalować '{pkg}' z '{env}'?").format(pkg=pkg, env=env['name'])):
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(_tr("Odinstaluję: {pkg}").format(pkg=pkg), "info")
        self.after(50, lambda: (
            self._venv_run([pip, "uninstall", "-y", pkg],
                           success_msg=_tr("Odinstalowano: {pkg}").format(pkg=pkg)),
            self._venv_load_packages()
        ))

    # ── POD-ZAKŁADKA 4: Requirements ─────────────────────────────────────────
    def _build_venv_req(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["req"] = frame

        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("📄 Requirements.txt — eksport i import zależności"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), '📄 Requirements.txt — eksport i import zależności').pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Button(bar, text=_tr("📤 Generuj requirements.txt"),
                  font=FONT_UI, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._venv_generate_req), "📤 Generuj requirements.txt").pack(side="left", padx=3)
        self._trw(tk.Button(bar, text=_tr("💾 Zapisz do pliku…"),
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_save_req), "💾 Zapisz do pliku…").pack(side="left", padx=3)
        self._trw(tk.Button(bar, text=_tr("📥 Instaluj z pliku…"),
                  font=FONT_UI, bg=BTN_OK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_OK_HOVER,
                  command=self._venv_install_req), "📥 Instaluj z pliku…").pack(side="left", padx=3)
        tk.Button(bar, text=_tr("📋 Kopiuj"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_copy_req).pack(side="left", padx=3)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        self.venv_req_text = tk.Text(frame, font=FONT_MONO, bg=BG_INPUT, fg="#c8d0f0",
                                      relief="flat", wrap="none",
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      insertbackground=FG_WHITE)
        sc = tk.Scrollbar(frame, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=8,
                           command=self.venv_req_text.yview)
        sc.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.venv_req_text.pack(fill="both", expand=True, padx=8, pady=6)
        self.venv_req_text.config(yscrollcommand=sc.set)

    def _venv_generate_req(self):
        import subprocess
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak env"), _tr("Wybierz środowisko z Listy envów."))
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_log(_tr("Generuję requirements dla: {name}").format(name=env['name']), "info")
        try:
            result = subprocess.run([pip, "freeze"], capture_output=True, text=True, timeout=30)
            self.venv_req_text.delete("1.0", "end")
            self.venv_req_text.insert("1.0", result.stdout)
            self._venv_log(_tr("requirements.txt wygenerowany."), "ok")
        except Exception as e:
            self._venv_log(_tr("Błąd: {e}").format(e=e), "error")

    def _venv_save_req(self):
        content = self.venv_req_text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showwarning(_tr("Brak zawartości"), _tr("Najpierw wygeneruj requirements."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="requirements.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self._venv_log(_tr("Zapisano: {path}").format(path=path), "ok")
            messagebox.showinfo(_tr("Zapisano"), _tr("Plik zapisany:\n{path}").format(path=path))

    def _venv_install_req(self):
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak env"), _tr("Wybierz środowisko z Listy envów."))
            return
        path = filedialog.askopenfilename(
            title=_tr("Wybierz requirements.txt"),
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if not path:
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(_tr("Instaluję z: {path}").format(path=path), "info")
        self.after(50, lambda: self._venv_run(
            [pip, "install", "-r", path],
            success_msg=_tr("Pakiety zainstalowane z requirements.txt!")))

    def _venv_copy_req(self):
        content = self.venv_req_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo(_tr("Skopiowano"), _tr("requirements.txt skopiowany do schowka."))

    # ── POD-ZAKŁADKA 5: Ustawienia ───────────────────────────────────────────
    def _build_venv_settings(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["settings"] = frame

        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("⚙ Ustawienia VirtualEnv"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "⚙ Ustawienia VirtualEnv").pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        def section(title):
            tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(14, 4))
            self._trw(tk.Label(body, text=_tr(title), font=FONT_BOLD, bg=BG_DARK,
                     fg=ACCENT_BLUE), title).pack(anchor="w")

        section("📁 Domyślny katalog środowisk")
        dr = tk.Frame(body, bg=BG_DARK)
        dr.pack(fill="x", pady=4)
        tk.Entry(dr, textvariable=self._venv_dir, font=FONT_MONO, bg=BG_INPUT,
                 fg=FG_WHITE, insertbackground=FG_WHITE, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER_CLR,
                 highlightcolor=ACCENT_BLUE).pack(side="left", fill="x", expand=True)
        self._trw(tk.Button(dr, text=_tr("📁 Przeglądaj"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._venv_browse_dir), '📁 Przeglądaj').pack(side="left", padx=6)

        section("🐍 Narzędzia")
        import sys
        self._venv_tool_labels = {}
        for tool in ("venv", "virtualenv", "pipenv", "poetry", "conda"):
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=tool, font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=16, anchor="w").pack(side="left")
            value = self._trw(tk.Label(r, text=_tr("nie sprawdzono"), font=FONT_UI,
                             bg=BG_DARK, fg=FG_GRAY), "nie sprawdzono")
            value.pack(side="left", padx=8)
            self._venv_tool_labels[tool] = value
        self._trw(tk.Button(
            body, text=_tr("🔍 Sprawdź narzędzia"), font=FONT_UI, bg=BTN_DARK,
            fg=FG_WHITE, relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._venv_refresh_tools), "🔍 Sprawdź narzędzia").pack(anchor="w", pady=4)

        section("ℹ Środowisko Python (bieżące)")
        import platform
        for label, val in [
            (_tr("Python:"), sys.version.split()[0]),
            (_tr("Plik:"),   sys.executable),
            (_tr("Platforma:"), f"{platform.system()} {platform.release()}"),
        ]:
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=14, anchor="w").pack(side="left")
            tk.Label(r, text=val, font=FONT_UI, bg=BG_DARK,
                     fg=FG_WHITE).pack(side="left", padx=4)

    def _venv_refresh_tools(self):
        """Detect optional environment managers without blocking the Tk event loop."""
        if self._venv_tools_loading:
            return
        self._venv_tools_loading = True
        for label in self._venv_tool_labels.values():
            label.configure(text=_tr("sprawdzanie…"), fg=FG_GRAY)

        def finish(results):
            self._venv_tools_loading = False
            self._venv_tools_checked = True
            for tool, label in self._venv_tool_labels.items():
                found = results.get(tool, "")
                label.configure(
                    text=str(found) if found else _tr("nie znaleziono"),
                    fg="#6dde84" if found else "#e07070",
                )

        def worker():
            results = discover_venv_tools()
            self._safe_after(0, lambda values=results: finish(values))

        import threading
        threading.Thread(target=worker, daemon=True, name="venv-tool-discovery").start()

    # ── POD-ZAKŁADKA 6: Log / Terminal ───────────────────────────────────────
    def _build_venv_log(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["log"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Label(bar, text=_tr("📟 Log operacji / output komend"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), "📟 Log operacji / output komend").pack(side="left")
        self._trw(tk.Button(bar, text=_tr("🧹 Wyczyść"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=lambda: (self.venv_log_text.config(state="normal"),
                                   self.venv_log_text.delete("1.0", "end"),
                                   self.venv_log_text.config(state="disabled"))
                  ), '🧹 Wyczyść').pack(side="right", padx=3)
        self._trw(tk.Button(bar, text=_tr("💾 Zapisz log…"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_save_log), "💾 Zapisz log…").pack(side="right", padx=3)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Wbudowany mini-terminal (pip polecenia)
        cmd_bar = tk.Frame(frame, bg=BG_PANEL, pady=5, padx=8)
        cmd_bar.pack(fill="x")
        self._trw(tk.Label(cmd_bar, text=_tr("pip:"), font=FONT_BOLD, bg=BG_PANEL,
                 fg=FG_GRAY), "pip:").pack(side="left")
        self.venv_cmd_entry = tk.Entry(cmd_bar, font=FONT_MONO, bg=BG_INPUT,
                                        fg=FG_WHITE, insertbackground=FG_WHITE,
                                        relief="flat", highlightthickness=1,
                                        highlightbackground=BORDER_CLR,
                                        highlightcolor=ACCENT_BLUE)
        self.venv_cmd_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.venv_cmd_entry.bind("<Return>", lambda e: self._venv_run_pip_cmd())
        tk.Button(cmd_bar, text=_tr("▶ Uruchom"), font=FONT_UI, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._venv_run_pip_cmd).pack(side="left", padx=3)
        self._trw(tk.Label(cmd_bar, text=_tr("(np. install numpy  |  list  |  show requests)"),
                 font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY), "(np. install numpy  |  list  |  show requests)").pack(side="left", padx=8)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Pole logu
        log_wrap = tk.Frame(frame, bg=BG_DARK)
        log_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        sc = tk.Scrollbar(log_wrap, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=10)
        sc.pack(side="right", fill="y")
        self.venv_log_text = tk.Text(log_wrap, font=("Consolas", 9), bg="#111520",
                                      fg="#c8d0f0", relief="flat", state="disabled",
                                      wrap="word", highlightthickness=1,
                                      highlightbackground=BORDER_CLR,
                                      yscrollcommand=sc.set)
        sc.config(command=self.venv_log_text.yview)
        self.venv_log_text.pack(fill="both", expand=True)

        # Kolory tagów
        self.venv_log_text.tag_configure("cmd",   foreground="#7ec8e3")
        self.venv_log_text.tag_configure("out",   foreground="#c8d0f0")
        self.venv_log_text.tag_configure("ok",    foreground="#6dde84")
        self.venv_log_text.tag_configure("warn",  foreground="#f0c050")
        self.venv_log_text.tag_configure("error", foreground="#e07070")
        self.venv_log_text.tag_configure("info",  foreground="#8a8fa8")

        self._venv_log(_tr("VirtualEnv Manager gotowy."), "ok")

    def _venv_run_pip_cmd(self):
        cmd_str = self.venv_cmd_entry.get().strip()
        if not cmd_str:
            return
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo(_tr("Brak env"), _tr("Wybierz środowisko z Listy envów."))
            return
        pip = self._venv_pip_in_env(env["path"])
        args = cmd_str.split()
        self.venv_cmd_entry.delete(0, "end")
        self.after(50, lambda: self._venv_run([pip] + args))

    def _venv_save_log(self):
        content = self.venv_log_text.get("1.0", "end-1c")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="venv_log.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo(_tr("Zapisano"), _tr("Log zapisany:\n{path}").format(path=path))

    def _show_venv(self):
        self.main_frames["venv"].pack(fill="both", expand=True)

    def _show_vdrive(self):
        self.main_frames["vdrive"].pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: VDrive — Wirtualne nośniki (FDD / HDD / VHD / CD/DVD/BD)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_vdrive_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["vdrive"] = outer

        # ── Nagłówek ─────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("💾 VDrive — Wirtualne nośniki danych"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), '💾 VDrive — Wirtualne nośniki danych').pack(side="left")
        self._vdrive_status_lbl = self._trw(tk.Label(
            hdr, text=_tr("Gotowy"), font=FONT_UI,
            bg=BG_PANEL, fg="#6dde84"), "Gotowy")
        self._vdrive_status_lbl.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Pod-zakładki ──────────────────────────────────────────────────────
        vd_sub_bar = tk.Frame(outer, bg=BG_PANEL)
        vd_sub_bar.pack(fill="x")
        vd_content = tk.Frame(outer, bg=BG_DARK)
        vd_content.pack(fill="both", expand=True)

        self._vdrive_btns   = []
        self._vdrive_frames = {}

        def sel_vd(idx, key):
            for j, b in enumerate(self._vdrive_btns):
                b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                             fg=FG_WHITE       if j == idx else FG_GRAY)
            for f in self._vdrive_frames.values():
                f.pack_forget()
            self._vdrive_frames[key].pack(fill="both", expand=True)
            self._update_minsize()

        self._vdrive_sel = sel_vd

        vd_tabs = [
            ("🖥 Panel nośników",  "panel"),
            ("➕ Utwórz nośnik",   "create"),
            ("⚙ Ustawienia",      "settings"),
            ("📋 Log",             "log"),
        ]
        for j, (lbl, key) in enumerate(vd_tabs):
            button = tk.Button(vd_sub_bar, text=_tr(lbl), font=FONT_UI,
                          bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY,
                          relief="flat", padx=14, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda j=j, k=key: sel_vd(j, k))
            b = self._trw(button, lbl)
            b.pack(side="left")
            self._vdrive_btns.append(b)

        # stan nośników: lista słowników
        self._vdrive_state = load_vdrive_state(VDRIVE_STATE_FILE)
        self._vdrives = self._vdrive_state["drives"]
        self._vdrive_settings = self._vdrive_state["settings"]

        self._build_vdrive_panel(vd_content)
        self._build_vdrive_create(vd_content)
        self._build_vdrive_settings(vd_content)
        self._build_vdrive_log(vd_content)
        sel_vd(0, "panel")

    # ── LOG helper ────────────────────────────────────────────────────────────
    def _vdrive_log(self, msg, tag="info"):
        if not hasattr(self, "_vdrive_log_text"):
            return
        self._vdrive_log_text.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._vdrive_log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self._vdrive_log_text.see("end")
        self._vdrive_log_text.config(state="disabled")

    def _vdrive_set_status(self, msg, color="#6dde84"):
        self._vdrive_status_source = msg
        if hasattr(self, "_vdrive_status_lbl"):
            self._vdrive_status_lbl.config(text=_tr(msg), fg=color)

    def _vdrive_collect_settings(self):
        return {
            "images_dir": self._vdrive_images_dir.get().strip(),
            "tool_win": self._vdrive_tool_win_map.get(
                self._vdrive_tool_win.get(), self._vdrive_tool_win.get()),
            "tool_lin": self._vdrive_tool_lin_map.get(
                self._vdrive_tool_lin.get(), self._vdrive_tool_lin.get()),
            "global_automount": self._vdrive_global_automount.get(),
            "global_notify": self._vdrive_global_notify.get(),
            "global_autostart": self._vdrive_global_autostart.get(),
        }

    def _vdrive_refresh_localized_options(self):
        if hasattr(self, "_vdrive_type_combo"):
            options = self._vdrive_type_options
            self._DRIVE_TYPES_MAP = {
                _tr(label): drive_type for label, drive_type in options}
            self._vdrive_type_combo.configure(
                values=[_tr(label) for label, _ in options])
            selected = next(
                label for label, drive_type in options
                if drive_type == self._vdrive_selected_type)
            self._vdrive_type_combo.set(_tr(selected))

        for widget_name, options_name, map_name in (
                ("_vdrive_tool_win", "_vdrive_tool_win_options", "_vdrive_tool_win_map"),
                ("_vdrive_tool_lin", "_vdrive_tool_lin_options", "_vdrive_tool_lin_map")):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            options = getattr(self, options_name)
            old_map = getattr(self, map_name, {})
            canonical = old_map.get(widget.get(), widget.get())
            localized = {_tr(value): value for value in options}
            setattr(self, map_name, localized)
            widget.configure(values=[_tr(value) for value in options])
            widget.set(_tr(canonical))

        if hasattr(self, "_vdrive_new_fs"):
            current = self._vdrive_new_fs.get()
            display_map = getattr(
                self, "_vdrive_fs_display_to_value",
                {_tr(value): value for value in self._vdrive_fs_values})
            canonical = display_map.get(current, current)
            self._vdrive_fs_display_to_value = {
                _tr(value): value for value in self._vdrive_fs_values}
            self._vdrive_new_fs.configure(
                values=[_tr(value) for value in self._vdrive_fs_values])
            self._vdrive_new_fs.set(_tr(canonical))

    def _vdrive_persist_state(self):
        try:
            settings = self._vdrive_collect_settings()
            self._vdrive_state = save_vdrive_state(
                VDRIVE_STATE_FILE, self._vdrives, settings)
            self._vdrive_settings = self._vdrive_state["settings"]
            self._vdrive_log(_tr("Zapisano konfigurację i listę nośników."), "ok")
            return True
        except (OSError, TypeError, ValueError) as ex:
            self._vdrive_log(_tr("Błąd zapisu konfiguracji VDrive: {error}").format(error=ex), "error")
            self._vdrive_set_status(_tr("Błąd zapisu VDrive"), "#e07070")
            return False

    def _vdrive_save_settings(self):
        if self._vdrive_persist_state():
            self._vdrive_set_status(_tr("Ustawienia zapisane"), "#6dde84")
            messagebox.showinfo(_tr("Ustawienia"), _tr("Ustawienia VDrive zapisane."))
        else:
            messagebox.showerror(_tr("Ustawienia"), _tr("Nie udało się zapisać ustawień VDrive."))

    # ── IKONY nośników (Canvas SVG-style) ────────────────────────────────────
    def _vdrive_draw_icon(self, canvas, drive_type, x, y, mounted=False):
        """Rysuje ikonę nośnika na Canvas (20×20 px, środek x,y)."""
        c  = ACCENT_BLUE if mounted else "#5a6080"
        hl = "#7ec8e3"   if mounted else "#8090b0"
        dt = drive_type.upper()

        if dt == "FDD":
            # dyskietka 3.5″
            canvas.create_rectangle(x-10, y-12, x+10, y+12, fill=c, outline=hl, width=1)
            canvas.create_rectangle(x-6,  y-12, x+6,  y-6,  fill=hl, outline="")
            canvas.create_rectangle(x-2,  y-12, x+2,  y-6,  fill="#1e2130", outline="")
            canvas.create_rectangle(x+4,  y+2,  x+8,  y+8,  fill="#1e2130", outline=hl, width=1)

        elif dt in ("HDD", "VHD", "VHDX"):
            # dysk twardy / VHD
            canvas.create_rectangle(x-11, y-7, x+11, y+7, fill=c, outline=hl, width=1)
            canvas.create_oval(x-5, y-4, x+5, y+4, fill=hl, outline="")
            canvas.create_oval(x-2, y-2, x+2, y+2, fill=c, outline="")
            canvas.create_line(x+6, y-7, x+6, y+7, fill=hl, width=1)
            canvas.create_rectangle(x+8, y-4, x+10, y+4, fill=hl, outline="")

        elif dt in ("ISO", "CD", "DVD"):
            # płyta CD/DVD
            canvas.create_oval(x-11, y-11, x+11, y+11, fill=c, outline=hl, width=1)
            canvas.create_oval(x-4,  y-4,  x+4,  y+4,  fill="#1e2130", outline=hl, width=1)
            canvas.create_arc(x-9,   y-9,  x+9,  y+9,
                              start=20, extent=60, style="arc", outline=hl, width=1)

        elif dt in ("BD", "BLURAY"):
            # Blu-ray — niebieska poświata
            canvas.create_oval(x-11, y-11, x+11, y+11, fill="#1a2a6c", outline="#4a80ff", width=2)
            canvas.create_oval(x-4,  y-4,  x+4,  y+4,  fill="#0a0a1a", outline="#4a80ff", width=1)
            canvas.create_arc(x-8,   y-8,  x+8,  y+8,
                              start=30, extent=80, style="arc", outline="#7aa8ff", width=2)

        elif dt in ("IMG", "BIN", "NRG", "MDF"):
            # obraz dysku — plik z symbolem dysku
            canvas.create_rectangle(x-9, y-11, x+9, y+11, fill=c, outline=hl, width=1)
            canvas.create_polygon(x+3, y-11, x+9, y-5, x+9, y-11, fill=BG_PANEL, outline=hl)
            canvas.create_oval(x-5, y+1, x+5, y+9, fill=hl, outline="")
            canvas.create_oval(x-2, y+3, x+2, y+7, fill=c, outline="")

        elif dt == "RAM":
            # RAM drive — pamięć
            canvas.create_rectangle(x-11, y-5, x+11, y+5, fill=c, outline=hl, width=1)
            for ox in range(-8, 9, 4):
                canvas.create_rectangle(x+ox-1, y-9, x+ox+1, y-5, fill=hl, outline="")
                canvas.create_rectangle(x+ox-1, y+5,  x+ox+1, y+9, fill=hl, outline="")

        else:
            # ogólny nośnik
            canvas.create_rectangle(x-10, y-10, x+10, y+10, fill=c, outline=hl, width=1)
            canvas.create_text(x, y, text="?", font=("Consolas", 8, "bold"), fill=hl)

    # ── POD-ZAKŁADKA 1: Panel nośników ───────────────────────────────────────
    def _build_vdrive_panel(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["panel"] = frame

        # Pasek akcji
        toolbar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        toolbar.pack(fill="x")
        for txt, cmd in [
            ("🔄 Odśwież", self._vdrive_refresh_panel),
            ("➕ Dodaj nośnik", lambda: self._vdrive_sel(1, "create")),
            ("🗑 Usuń nośnik", self._vdrive_delete_selected),
        ]:
            self._trw(tk.Button(toolbar, text=_tr(txt), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER,
                      command=cmd), txt).pack(side="left", padx=3)
        tk.Frame(toolbar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=8, pady=2)
        self._trw(tk.Button(toolbar, text=_tr("📋 Kopiuj polecenie"), font=FONT_BOLD, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground="#3a7bc8",
              command=self._vdrive_copy_mount_command), "📋 Kopiuj polecenie").pack(side="left", padx=3)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Legenda typów
        leg = tk.Frame(frame, bg=BG_PANEL, pady=4, padx=10)
        leg.pack(fill="x")
        self._trw(tk.Label(leg, text=_tr("Typy nośników:"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_GRAY), 'Typy nośników:').pack(side="left", padx=(0, 10))
        legend_items = [
            ("FDD", "💾 Dyskietka"),
            ("HDD", "🖴 Dysk HDD"),
            ("VHD", "📦 Wirtualny VHD"),
            ("ISO", "💿 Obraz CD/DVD"),
            ("BD",  "🔵 Blu-ray"),
            ("IMG", "🗂 Obraz IMG"),
            ("RAM", "⚡ RAM Drive"),
        ]
        for typ, label in legend_items:
            fr = tk.Frame(leg, bg=BG_PANEL)
            fr.pack(side="left", padx=6)
            ic = tk.Canvas(fr, width=22, height=22, bg=BG_PANEL,
                           highlightthickness=0)
            ic.pack(side="left")
            self._vdrive_draw_icon(ic, typ, 11, 11, mounted=True)
            self._trw(tk.Label(fr, text=_tr(label), font=("Consolas", 8),
                     bg=BG_PANEL, fg=FG_GRAY), label).pack(side="left", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Siatka nośników (canvas z ikonami + Treeview)
        split = tk.PanedWindow(frame, orient="horizontal", bg=BG_DARK,
                               sashwidth=6, sashrelief="flat")
        split.pack(fill="both", expand=True)

        # Lewa: ikony nośników (Canvas scrollable)
        left_wrap = tk.Frame(split, bg=BG_DARK, width=260)
        split.add(left_wrap, stretch="never")
        self._trw(tk.Label(left_wrap, text=_tr("Nośniki"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), 'Nośniki').pack(anchor="w", padx=8, pady=(6, 2))
        tk.Frame(left_wrap, bg=BORDER_CLR, height=1).pack(fill="x")

        icon_sc = tk.Scrollbar(left_wrap, orient="vertical", bg=BG_PANEL,
                                troughcolor=BG_PANEL, width=8)
        icon_sc.pack(side="right", fill="y")
        self._vdrive_icon_canvas = tk.Canvas(left_wrap, bg=BG_DARK,
                                              highlightthickness=0,
                                              yscrollcommand=icon_sc.set)
        self._vdrive_icon_canvas.pack(fill="both", expand=True)
        icon_sc.config(command=self._vdrive_icon_canvas.yview)
        self._vdrive_icon_frame = tk.Frame(self._vdrive_icon_canvas, bg=BG_DARK)
        self._vdrive_icon_canvas.create_window((0, 0), window=self._vdrive_icon_frame,
                                                anchor="nw")
        self._vdrive_icon_frame.bind("<Configure>",
            lambda e: self._vdrive_icon_canvas.configure(
                scrollregion=self._vdrive_icon_canvas.bbox("all")))

        # Prawa: szczegóły w Treeview
        right_wrap = tk.Frame(split, bg=BG_DARK)
        split.add(right_wrap, stretch="always")
        self._trw(tk.Label(right_wrap, text=_tr("Szczegóły nośników"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), 'Szczegóły nośników').pack(anchor="w", padx=8, pady=(6, 2))
        tk.Frame(right_wrap, bg=BORDER_CLR, height=1).pack(fill="x")

        tree_wrap = tk.Frame(right_wrap, bg=BG_DARK)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=4)

        cols = ("Typ", "Etykieta", "Plik / ścieżka", "Rozmiar", "Status", "Litera")
        style = ttk.Style()
        style.configure("VDrive.Treeview",
                         background=BG_PANEL, foreground=FG_WHITE,
                         fieldbackground=BG_PANEL, rowheight=26,
                         font=FONT_UI)
        style.configure("VDrive.Treeview.Heading",
                         background=BG_INPUT, foreground=FG_GRAY,
                         relief="flat", font=FONT_BOLD)
        style.map("VDrive.Treeview",
                  background=[("selected", BG_ROW_SEL)],
                  foreground=[("selected", FG_WHITE)])

        tv_sc = tk.Scrollbar(tree_wrap, orient="vertical", bg=BG_PANEL,
                              troughcolor=BG_PANEL, width=8)
        tv_sc.pack(side="right", fill="y")
        self._vdrive_tree = ttk.Treeview(tree_wrap, columns=cols, show="headings",
                                          style="VDrive.Treeview",
                                          yscrollcommand=tv_sc.set,
                                          selectmode="browse")
        tv_sc.config(command=self._vdrive_tree.yview)
        self._vdrive_tree.pack(fill="both", expand=True)

        widths = {"Typ": 70, "Etykieta": 110, "Plik / ścieżka": 280,
                  "Rozmiar": 80, "Status": 90, "Litera": 60}
        for col in cols:
            self._trh(self._vdrive_tree, col, col)
            self._vdrive_tree.column(col, width=widths.get(col, 100),
                                      minwidth=40, anchor="w")
        self._vdrive_tree.tag_configure("mounted",
                                         foreground="#6dde84")
        self._vdrive_tree.tag_configure("unmounted",
                                         foreground=FG_GRAY)
        self._vdrive_tree.bind("<<TreeviewSelect>>",
                               self._vdrive_on_tree_select)
        self._vdrive_tree.bind("<Double-1>",
                               lambda e: self._vdrive_copy_mount_command())

        # Dolny pasek informacyjny
        info_bar = tk.Frame(right_wrap, bg=BG_PANEL, pady=4, padx=8)
        info_bar.pack(fill="x", side="bottom")
        self._vdrive_info_lbl = self._trw(tk.Label(info_bar, text=_tr("Wybierz nośnik aby zobaczyć szczegóły"),
                                          font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                                          anchor="w"), 'Wybierz nośnik aby zobaczyć szczegóły')
        self._vdrive_info_lbl.pack(fill="x")

        # Wypełnij przykładowymi nośnikami na start
        self.after(150, self._vdrive_refresh_panel)

    # ── POD-ZAKŁADKA 2: Utwórz nośnik ────────────────────────────────────────
    def _build_vdrive_create(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["create"] = frame

        hdr2 = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        hdr2.pack(fill="x")
        self._trw(tk.Label(hdr2, text=_tr("➕ Utwórz / Zarejestruj nowy nośnik"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE), '➕ Utwórz / Zarejestruj nowy nośnik').pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        def field_row(label, widget_factory):
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=5)
            self._trw(tk.Label(r, text=_tr(label), font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=22, anchor="w"), label).pack(side="left")
            return r, widget_factory(r)

        # Typ nośnika
        r = tk.Frame(body, bg=BG_DARK)
        r.pack(fill="x", pady=5)
        self._trw(tk.Label(r, text=_tr("Typ nośnika:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w"), 'Typ nośnika:').pack(side="left")
        DRIVE_TYPES = [
            ("💾 FDD — Dyskietka 3.5″",    "FDD"),
            ("🖴 HDD — Wirtualny dysk",     "HDD"),
            ("📦 VHD — Virtual Hard Disk",  "VHD"),
            ("📦 VHDX — Rozszerzony VHD",   "VHDX"),
            ("💿 ISO — Obraz CD/DVD",       "ISO"),
            ("💿 CD  — Napęd CD-ROM",       "CD"),
            ("📀 DVD — Napęd DVD",          "DVD"),
            ("🔵 BD  — Blu-ray Disc",       "BD"),
            ("🗂 IMG — Obraz dysku",        "IMG"),
            ("🗂 BIN/CUE — Obraz binarny",  "BIN"),
            ("🗂 NRG — Nero Image",         "NRG"),
            ("⚡ RAM Drive — Dysk w RAM",   "RAM"),
        ]
        self._vdrive_type_labels = [label for label, _ in DRIVE_TYPES]
        self._vdrive_type_var = tk.StringVar(value="VHD")
        type_frame = tk.Frame(r, bg=BG_DARK)
        type_frame.pack(side="left", fill="x", expand=True)
        self._vdrive_type_combo = ttk.Combobox(
            type_frame, textvariable=self._vdrive_type_var,
            values=[_tr(t[0]) for t in DRIVE_TYPES],
            state="readonly", font=FONT_MONO, width=34)
        self._vdrive_type_combo.pack(side="left")
        self._vdrive_type_combo.set(_tr(DRIVE_TYPES[2][0]))
        self._vdrive_type_options = DRIVE_TYPES
        self._vdrive_selected_type = "VHD"
        self._DRIVE_TYPES_MAP = {_tr(label): typ for label, typ in DRIVE_TYPES}
        # ikona podglądu przy combo
        self._vdrive_create_icon_c = tk.Canvas(type_frame, width=26, height=26,
                                                bg=BG_DARK, highlightthickness=0)
        self._vdrive_create_icon_c.pack(side="left", padx=8)
        self._vdrive_draw_icon(self._vdrive_create_icon_c, "VHD", 13, 13, mounted=True)
        self._vdrive_type_combo.bind("<<ComboboxSelected>>",
                                     self._vdrive_on_type_change)

        # Etykieta
        r2, self._vdrive_new_label = field_row(
            "Etykieta (nazwa):",
            lambda p: tk.Entry(p, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                               insertbackground=FG_WHITE, relief="flat",
                               highlightthickness=1, highlightbackground=BORDER_CLR,
                               highlightcolor=ACCENT_BLUE, width=36))
        self._vdrive_new_label.insert(0, _tr("MójNosnik"))

        # Plik / ścieżka
        r3 = tk.Frame(body, bg=BG_DARK)
        r3.pack(fill="x", pady=5)
        self._trw(tk.Label(r3, text=_tr("Plik / ścieżka:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w"), 'Plik / ścieżka:').pack(side="left")
        self._vdrive_new_path = tk.Entry(r3, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                          insertbackground=FG_WHITE, relief="flat",
                                          highlightthickness=1, highlightbackground=BORDER_CLR,
                                          highlightcolor=ACCENT_BLUE)
        self._vdrive_new_path.pack(side="left", fill="x", expand=True)
        self._trw(tk.Button(r3, text=_tr("📁 Przeglądaj…"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
              command=self._vdrive_browse_path), "📁 Przeglądaj…").pack(side="left", padx=4)

        # Rozmiar (dla VHD/HDD/RAM)
        r4, self._vdrive_new_size = field_row(
            "Rozmiar (MB):",
            lambda p: tk.Entry(p, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                               insertbackground=FG_WHITE, relief="flat",
                               highlightthickness=1, highlightbackground=BORDER_CLR,
                               highlightcolor=ACCENT_BLUE, width=12))
        self._vdrive_new_size.insert(0, "1024")

        # Litera dysku (Windows)
        r5 = tk.Frame(body, bg=BG_DARK)
        r5.pack(fill="x", pady=5)
        self._trw(tk.Label(r5, text=_tr("Litera dysku (Win):"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w"), "Litera dysku (Win):").pack(side="left")
        self._vdrive_auto_letter_label = _tr("(auto)")
        self._vdrive_new_letter = ttk.Combobox(
            r5, values=[self._vdrive_auto_letter_label] + [f"{c}:" for c in "DEFGHIJKLMNOPQRSTUVWXYZ"],
            font=FONT_MONO, state="readonly", width=8)
        self._vdrive_new_letter.set(self._vdrive_auto_letter_label)
        self._vdrive_new_letter.pack(side="left")

        # System plików
        r6 = tk.Frame(body, bg=BG_DARK)
        r6.pack(fill="x", pady=5)
        self._trw(tk.Label(r6, text=_tr("System plików:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w"), 'System plików:').pack(side="left")
        fs_values = ["NTFS", "FAT32", "exFAT", "ext4", "ISO 9660", "(brak)"]
        self._vdrive_fs_values = fs_values
        self._vdrive_new_fs = ttk.Combobox(
            r6, values=[_tr(value) for value in fs_values],
            font=FONT_MONO, state="readonly", width=14)
        self._vdrive_new_fs.set(_tr("NTFS"))
        self._vdrive_fs_display_to_value = {
            _tr(value): value for value in fs_values}
        self._vdrive_new_fs.pack(side="left")

        # Opcje
        r7 = tk.Frame(body, bg=BG_DARK)
        r7.pack(fill="x", pady=8)
        self._trw(tk.Label(r7, text=_tr("Opcje:"), font=FONT_BOLD, bg=BG_DARK,
             fg=FG_GRAY, width=22, anchor="w"), "Opcje:").pack(side="left")
        self._vdrive_opt_automount  = tk.BooleanVar(value=True)
        self._vdrive_opt_persistent = tk.BooleanVar(value=True)
        self._vdrive_opt_readonly   = tk.BooleanVar(value=False)
        self._vdrive_opt_compress   = tk.BooleanVar(value=False)
        for text, var in [
            ("Przypisz literę automatycznie", self._vdrive_opt_automount),
            ("Trwały (persistent)",self._vdrive_opt_persistent),
            ("Tylko do odczytu",   self._vdrive_opt_readonly),
            ("Kompresja",          self._vdrive_opt_compress),
        ]:
            self._trw(tk.Checkbutton(r7, text=_tr(text), variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT), text).pack(side="left", padx=10)

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=12)

        # Przyciski akcji
        btn_row = tk.Frame(body, bg=BG_DARK)
        btn_row.pack(fill="x")
        self._trw(tk.Button(btn_row, text=_tr("✅ Zarejestruj nośnik"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat",
                  padx=18, pady=8, cursor="hand2",
                  activebackground="#3a7bc8",
              command=self._vdrive_do_create), '✅ Zarejestruj nośnik').pack(side="left", padx=4)
        self._trw(tk.Button(btn_row, text=_tr("📂 Zarejestruj bez litery"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  activebackground=BTN_HOVER,
              command=self._vdrive_do_register), "📂 Zarejestruj bez litery").pack(side="left", padx=4)
        self._trw(tk.Button(btn_row, text=_tr("🧹 Wyczyść"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._vdrive_clear_create_form), '🧹 Wyczyść').pack(side="left", padx=4)

        self._vdrive_create_status = tk.Label(body, text="", font=FONT_UI,
                                               bg=BG_DARK, fg="#6dde84")
        self._vdrive_create_status.pack(anchor="w", pady=8)

        # Info o narzędziach systemowych
        info_wrap = tk.Frame(body, bg=BG_PANEL, padx=12, pady=8)
        info_wrap.pack(fill="x", pady=(8, 0))
        self._trw(tk.Label(info_wrap, text=_tr("ℹ Informacje o obsłudze nośników"),
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE), 'ℹ Informacje o obsłudze nośników').pack(anchor="w")
        info_lines = [
            "• VHD/VHDX  — Windows: diskpart / PowerShell New-VHD; Linux: qemu-img",
            "• ISO/CD/DVD — Windows: PowerShell Mount-DiskImage; Linux: mount -o loop",
            "• Blu-ray    — Windows: MakeMKV / ImgBurn; Linux: cdrecord / k3b",
            "• IMG/BIN    — Windows: OSFMount, ImDisk; Linux: mount -o loop",
            "• RAM Drive  — Windows: ImDisk / OSFMount; Linux: mount -t tmpfs",
            "• FDD (obraz)— Windows: WinImage; Linux: mount -t msdos / dosfsck",
        ]
        for line in info_lines:
            self._trw(tk.Label(info_wrap, text=_tr(line), font=("Consolas", 8),
                     bg=BG_PANEL, fg=FG_GRAY, anchor="w"), line).pack(fill="x")

    # ── POD-ZAKŁADKA 3: Ustawienia ────────────────────────────────────────────
    def _build_vdrive_settings(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["settings"] = frame

        hdr3 = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        hdr3.pack(fill="x")
        self._trw(tk.Label(hdr3, text=_tr("⚙ Ustawienia VDrive"),
             font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE),
             "⚙ Ustawienia VDrive").pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        # Domyślny katalog
        r = tk.Frame(body, bg=BG_DARK)
        r.pack(fill="x", pady=5)
        self._trw(tk.Label(r, text=_tr("Katalog obrazów:"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w"), 'Katalog obrazów:').pack(side="left")
        self._vdrive_images_dir = tk.Entry(r, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                            insertbackground=FG_WHITE, relief="flat",
                                            highlightthickness=1, highlightbackground=BORDER_CLR,
                                            highlightcolor=ACCENT_BLUE)
        self._vdrive_images_dir.insert(0, self._vdrive_settings["images_dir"])
        self._vdrive_images_dir.pack(side="left", fill="x", expand=True)
        self._trw(tk.Button(r, text=_tr("📁"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=lambda: (
                      self._vdrive_images_dir.delete(0, "end"),
                      self._vdrive_images_dir.insert(0,
                          filedialog.askdirectory(title=_tr("Wybierz katalog obrazów")) or
                          self._vdrive_images_dir.get())
                  )), "📁").pack(side="left", padx=4)

        # Narzędzie montowania (Windows/Linux)
        r2 = tk.Frame(body, bg=BG_DARK)
        r2.pack(fill="x", pady=5)
        self._trw(tk.Label(r2, text=_tr("Narzędzie (Windows):"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w"), 'Narzędzie (Windows):').pack(side="left")
        self._vdrive_tool_win = ttk.Combobox(
            r2, values=[_tr(value) for value in (
                "diskpart (wbudowany)", "PowerShell Mount-DiskImage",
                "ImDisk Toolkit", "OSFMount", "Arsenal Image Mounter")],
            font=FONT_MONO, state="readonly", width=34)
        self._vdrive_tool_win_options = [
            "diskpart (wbudowany)", "PowerShell Mount-DiskImage",
            "ImDisk Toolkit", "OSFMount", "Arsenal Image Mounter"]
        self._vdrive_tool_win_map = {
            _tr(value): value for value in self._vdrive_tool_win_options}
        self._vdrive_tool_win.set(_tr(self._vdrive_settings["tool_win"]))
        self._vdrive_tool_win.pack(side="left")

        r3 = tk.Frame(body, bg=BG_DARK)
        r3.pack(fill="x", pady=5)
        self._trw(tk.Label(r3, text=_tr("Narzędzie (Linux):"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w"), 'Narzędzie (Linux):').pack(side="left")
        self._vdrive_tool_lin = ttk.Combobox(
            r3, values=[_tr(value) for value in (
                "mount (wbudowany)", "qemu-img + mount", "fuseiso",
                "acetoneiso2", "gnome-disk-image-mounter")],
            font=FONT_MONO, state="readonly", width=34)
        self._vdrive_tool_lin_options = [
            "mount (wbudowany)", "qemu-img + mount", "fuseiso",
            "acetoneiso2", "gnome-disk-image-mounter"]
        self._vdrive_tool_lin_map = {
            _tr(value): value for value in self._vdrive_tool_lin_options}
        self._vdrive_tool_lin.set(_tr(self._vdrive_settings["tool_lin"]))
        self._vdrive_tool_lin.pack(side="left")

        # Opcje globalne
        r4 = tk.Frame(body, bg=BG_DARK)
        r4.pack(fill="x", pady=10)
        self._trw(tk.Label(r4, text=_tr("Opcje globalne:"), font=FONT_BOLD, bg=BG_DARK,
             fg=FG_GRAY, width=24, anchor="w"), "Opcje globalne:").pack(side="left")
        self._vdrive_global_automount  = tk.BooleanVar(value=self._vdrive_settings["global_automount"])
        self._vdrive_global_notify     = tk.BooleanVar(value=self._vdrive_settings["global_notify"])
        self._vdrive_global_autostart  = tk.BooleanVar(value=self._vdrive_settings["global_autostart"])
        for text, var in [
            ("Auto-montuj przy starcie", self._vdrive_global_automount),
            ("Powiadomienia",            self._vdrive_global_notify),
            ("Uruchom przy logowaniu",   self._vdrive_global_autostart),
        ]:
            self._trw(tk.Checkbutton(r4, text=_tr(text), variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT), text).pack(side="left", padx=10)

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=12)

        self._trw(tk.Button(body, text=_tr("💾 Zapisz ustawienia"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  activebackground="#3a7bc8",
              command=self._vdrive_save_settings), "💾 Zapisz ustawienia").pack(anchor="w")

    # ── POD-ZAKŁADKA 4: Log ───────────────────────────────────────────────────
    def _build_vdrive_log(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["log"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=5, padx=8)
        bar.pack(fill="x")
        self._trw(tk.Label(bar, text=_tr("📋 Log operacji VDrive"),
             font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE),
             "📋 Log operacji VDrive").pack(side="left")
        self._trw(tk.Button(bar, text=_tr("🗑 Wyczyść log"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=lambda: (
                      self._vdrive_log_text.config(state="normal"),
                      self._vdrive_log_text.delete("1.0", "end"),
                      self._vdrive_log_text.config(state="disabled")
                  )), '🗑 Wyczyść log').pack(side="right", padx=4)
        self._trw(tk.Button(bar, text=_tr("💾 Zapisz log"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
              command=self._vdrive_save_log), "💾 Zapisz log").pack(side="right", padx=4)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        log_wrap = tk.Frame(frame, bg=BG_DARK)
        log_wrap.pack(fill="both", expand=True, padx=6, pady=6)
        sc = tk.Scrollbar(log_wrap, orient="vertical", bg=BG_PANEL,
                           troughcolor=BG_PANEL, width=10)
        sc.pack(side="right", fill="y")
        self._vdrive_log_text = tk.Text(log_wrap, font=("Consolas", 9),
                                         bg="#111520", fg="#c8d0f0",
                                         relief="flat", state="disabled",
                                         wrap="word", highlightthickness=1,
                                         highlightbackground=BORDER_CLR,
                                         yscrollcommand=sc.set)
        sc.config(command=self._vdrive_log_text.yview)
        self._vdrive_log_text.pack(fill="both", expand=True)
        self._vdrive_log_text.tag_configure("cmd",   foreground="#7ec8e3")
        self._vdrive_log_text.tag_configure("out",   foreground="#c8d0f0")
        self._vdrive_log_text.tag_configure("ok",    foreground="#6dde84")
        self._vdrive_log_text.tag_configure("warn",  foreground="#f0c050")
        self._vdrive_log_text.tag_configure("error", foreground="#e07070")
        self._vdrive_log_text.tag_configure("info",  foreground="#8a8fa8")
        self._vdrive_log(_tr("VDrive Manager gotowy."), "ok")

    # ── Akcje i helpery VDrive ────────────────────────────────────────────────
    def _vdrive_refresh_panel(self):
        """Odśwież listę i panel ikon nośników."""
        self._vdrive_rebuild_icons()
        self._vdrive_rebuild_tree()
        self._vdrive_log(_tr("Odświeżono panel. Nośników: {count}").format(
            count=len(self._vdrives)), "info")

    def _vdrive_rebuild_icons(self):
        """Odbuduj siatkę ikon nośników."""
        for w in self._vdrive_icon_frame.winfo_children():
            w.destroy()
        cols_per_row = 3
        for idx, drv in enumerate(self._vdrives):
            col = idx % cols_per_row
            row = idx // cols_per_row
            cell = tk.Frame(self._vdrive_icon_frame, bg=BG_PANEL,
                            relief="flat", bd=0,
                            highlightthickness=1,
                            highlightbackground=BORDER_CLR if not drv["mounted"]
                                               else ACCENT_BLUE)
            cell.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            ic = tk.Canvas(cell, width=40, height=40, bg=BG_PANEL,
                           highlightthickness=0)
            ic.pack(pady=(8, 2))
            self._vdrive_draw_icon(ic, drv["typ"], 20, 20, drv["mounted"])
            tk.Label(cell, text=drv["label"], font=("Consolas", 8, "bold"),
                     bg=BG_PANEL, fg=FG_WHITE if drv["mounted"] else FG_GRAY,
                     wraplength=80).pack()
            status_color = "#6dde84" if drv["mounted"] else FG_GRAY
            status_text  = f"● {drv['drive_letter']}" if drv["mounted"] else _tr("○ odmontowany")
            tk.Label(cell, text=status_text, font=("Consolas", 7),
                     bg=BG_PANEL, fg=status_color).pack(pady=(0, 6))
            # klik zaznacza w tree
            for w in [cell, ic]:
                w.bind("<Button-1>",
                       lambda e, i=idx: self._vdrive_icon_click(i))
            cell.bind("<Double-1>", lambda e, i=idx: self._vdrive_icon_dblclick(i))

    def _vdrive_rebuild_tree(self):
        for row in self._vdrive_tree.get_children():
            self._vdrive_tree.delete(row)
        for drv in self._vdrives:
            tag = "mounted" if drv["mounted"] else "unmounted"
            size_str = f"{drv['size_mb']} MB" if drv["size_mb"] else "—"
            self._vdrive_tree.insert("", "end",
                values=(drv["typ"], drv["label"],
                        drv["path"] or "—",
                        size_str,
                        _tr("✔ Zamontowany") if drv["mounted"] else _tr("✗ Odmontowany"),
                        drv["drive_letter"] or "—"),
                tags=(tag,))

    def _vdrive_icon_click(self, idx):
        children = self._vdrive_tree.get_children()
        if idx < len(children):
            self._vdrive_tree.selection_set(children[idx])
            self._vdrive_tree.focus(children[idx])

    def _vdrive_icon_dblclick(self, idx):
        self._vdrive_icon_click(idx)
        self._vdrive_copy_mount_command()

    def _vdrive_on_tree_select(self, event=None):
        sel = self._vdrive_tree.selection()
        if not sel:
            return
        children = self._vdrive_tree.get_children()
        idx = list(children).index(sel[0])
        if idx < len(self._vdrives):
            drv = self._vdrives[idx]
            info = _tr("Typ: {type}  |  Etykieta: {label}  |  Ścieżka: {path}  |  Rozmiar: {size} MB  |  Status: {status}  |  Litera: {letter}").format(
                type=drv["typ"], label=drv["label"],
                path=drv["path"] or "—", size=drv["size_mb"],
                status=_tr("Zamontowany") if drv["mounted"] else _tr("Odmontowany"),
                letter=drv["drive_letter"] or "—")
            self._vdrive_info_lbl.config(text=info, fg=FG_WHITE)

    def _vdrive_get_selected_idx(self):
        sel = self._vdrive_tree.selection()
        if not sel:
            return None
        children = list(self._vdrive_tree.get_children())
        if sel[0] in children:
            return children.index(sel[0])
        return None

    def _vdrive_copy_mount_command(self):
        idx = self._vdrive_get_selected_idx()
        if idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz nośnik na liście."))
            return
        drv = self._vdrives[idx]
        if drv["mounted"]:
            messagebox.showinfo(_tr("Stan nośnika"),
                                _tr("VDrive nie weryfikuje ani nie zmienia stanu systemowego montowania."))
            return
        if drv["path"] and not os.path.exists(drv["path"]):
            messagebox.showwarning(_tr("Brak pliku"),
                                   _tr("Plik nie istnieje:\n{path}").format(path=drv["path"]))
            return
        cmd = self._vdrive_build_mount_cmd(drv)
        self.clipboard_clear()
        self.clipboard_append(cmd)
        self._vdrive_log(_tr("Skopiowano sugerowane polecenie dla '{label}': {command}").format(
            label=drv["label"], command=cmd), "cmd")
        self._vdrive_set_status(_tr("Polecenie skopiowane; nie zostało wykonane"), "#f0c050")

    def _vdrive_unmount_selected(self):
        idx = self._vdrive_get_selected_idx()
        if idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz nośnik na liście."))
            return
        drv = self._vdrives[idx]
        if not drv["mounted"]:
            messagebox.showinfo(_tr("Nie zamontowany"),
                                _tr("Nośnik '{label}' nie jest zamontowany.").format(label=drv["label"]))
            return
        drv["mounted"] = False
        self._vdrive_log(_tr("Odmontowano: {label}").format(label=drv["label"]), "warn")
        self._vdrive_persist_state()
        self._vdrive_set_status(_tr("Odmontowano: {label}").format(label=drv["label"]), "#f0c050")
        self._vdrive_refresh_panel()

    def _vdrive_delete_selected(self):
        idx = self._vdrive_get_selected_idx()
        if idx is None:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Zaznacz nośnik na liście."))
            return
        drv = self._vdrives[idx]
        if not messagebox.askyesno(
            _tr("Usuń nośnik"),
            _tr("Usunąć nośnik '{label}' z listy?\n(plik na dysku nie zostanie usunięty)").format(label=drv["label"])):
            return
        self._vdrive_log(_tr("Usunięto z listy: {label}").format(label=drv["label"]), "warn")
        self._vdrives.pop(idx)
        self._vdrive_persist_state()
        self._vdrive_refresh_panel()

    def _vdrive_build_mount_cmd(self, drv):
        """Zwraca sugerowaną komendę montowania dla danego nośnika."""
        typ  = drv["typ"].upper()
        path = drv.get("path", "")
        let  = drv.get("drive_letter", "D:")
        if os.name == "nt":
            if typ in ("VHD", "VHDX"):
                return f'Mount-DiskImage -ImagePath "{path}"'
            elif typ in ("ISO", "CD", "DVD"):
                return f'Mount-DiskImage -ImagePath "{path}" -StorageType ISO'
            elif typ == "RAM":
                size_mb = drv.get("size_mb", 256)
                return f'imdisk -a -s {size_mb}M -m {let} -p "/fs:ntfs /q /y"'
            else:
                return f'diskpart  (attach vdisk file="{path}")'
        else:
            if typ in ("ISO", "CD", "DVD", "BD"):
                return f'sudo mount -o loop "{path}" /mnt/vdrive'
            elif typ in ("VHD", "VHDX"):
                return f'sudo qemu-nbd --connect=/dev/nbd0 "{path}" && sudo mount /dev/nbd0 /mnt/vdrive'
            elif typ == "RAM":
                size_mb = drv.get("size_mb", 256)
                return f'sudo mount -t tmpfs -o size={size_mb}m tmpfs /mnt/ramdrive'
            else:
                return f'sudo mount -o loop "{path}" /mnt/vdrive'

    def _vdrive_on_type_change(self, event=None):
        sel = self._vdrive_type_var.get()
        typ = self._DRIVE_TYPES_MAP.get(sel, "HDD")
        self._vdrive_selected_type = typ
        self._vdrive_create_icon_c.delete("all")
        self._vdrive_draw_icon(self._vdrive_create_icon_c, typ, 13, 13, mounted=True)

    def _vdrive_browse_path(self):
        sel = self._vdrive_type_var.get()
        typ = self._DRIVE_TYPES_MAP.get(sel, "HDD")
        if typ in ("ISO", "IMG", "BIN", "NRG", "MDF"):
            path = filedialog.askopenfilename(
                title=_tr("Wybierz plik obrazu"),
                filetypes=[(_tr("Obrazy dysków"),
                            "*.iso *.img *.bin *.nrg *.mdf *.vhd *.vhdx"),
                           (_tr("Wszystkie pliki"), "*.*")])
        else:
            path = filedialog.askopenfilename(
                title=_tr("Wybierz plik VHD/VHDX"),
                filetypes=[(_tr("VHD/VHDX"), "*.vhd *.vhdx"),
                           (_tr("Wszystkie pliki"), "*.*")])
        if path:
            self._vdrive_new_path.delete(0, "end")
            self._vdrive_new_path.insert(0, path)

    def _vdrive_do_create(self):
        label  = self._vdrive_new_label.get().strip()
        path   = self._vdrive_new_path.get().strip()
        size   = self._vdrive_new_size.get().strip()
        sel    = self._vdrive_type_var.get()
        typ    = self._DRIVE_TYPES_MAP.get(sel, "HDD")
        letter = self._vdrive_new_letter.get()
        if letter in ("(auto)", self._vdrive_auto_letter_label):
            used = {d["drive_letter"] for d in self._vdrives}
            letter = next(
                (f"{c}:" for c in "DEFGHIJKLMNOPQRSTUVWXYZ"
                 if f"{c}:" not in used), "Z:")

        if not label:
            messagebox.showwarning(_tr("Brak etykiety"), _tr("Podaj etykietę nośnika."))
            return

        try:
            size_mb = int(size)
        except ValueError:
            size_mb = 0

        drv = {
            "id":           len(self._vdrives),
            "typ":          typ,
            "label":        label,
            "path":         path,
            "size_mb":      size_mb,
            "mounted":      False,
            "drive_letter": letter if self._vdrive_opt_automount.get() else "",
            "fs":           self._vdrive_fs_display_to_value.get(
                self._vdrive_new_fs.get(), self._vdrive_new_fs.get()),
            "readonly":     self._vdrive_opt_readonly.get(),
            "persistent":   self._vdrive_opt_persistent.get(),
            "compress":     self._vdrive_opt_compress.get(),
        }
        self._vdrives.append(drv)
        self._vdrive_persist_state()
        self._vdrive_create_status_source = "✅ Nośnik '{label}' ({type}) dodany."
        self._vdrive_create_status_args = {"label": label, "type": typ}
        self._vdrive_create_status.config(
            text=_tr(self._vdrive_create_status_source).format(
                **self._vdrive_create_status_args), fg="#6dde84")
        self._vdrive_log(_tr("Zarejestrowano nośnik: {label} ({type}), ścieżka: {path}").format(
            label=label, type=typ, path=path or "—"), "ok")
        cmd = self._vdrive_build_mount_cmd(drv)
        self._vdrive_log(_tr("Sugerowane polecenie montowania: {command}").format(command=cmd), "cmd")
        self._vdrive_set_status(_tr("Dodano: {label}").format(label=label), "#6dde84")
        self._vdrive_sel(0, "panel")
        self._vdrive_refresh_panel()

    def _vdrive_do_register(self):
        """Tylko rejestruje nośnik bez montowania."""
        self._vdrive_opt_automount.set(False)
        self._vdrive_do_create()
        self._vdrive_opt_automount.set(True)

    def _vdrive_clear_create_form(self):
        self._vdrive_new_label.delete(0, "end")
        self._vdrive_new_label.insert(0, _tr("MójNosnik"))
        self._vdrive_new_path.delete(0, "end")
        self._vdrive_new_size.delete(0, "end")
        self._vdrive_new_size.insert(0, "1024")
        self._vdrive_create_status.config(text="")
        self._vdrive_create_status_source = ""

    def _vdrive_save_log(self):
        content = self._vdrive_log_text.get("1.0", "end-1c")
        path = filedialog.asksaveasfilename(
            title=_tr("Zapisz log VDrive"),
            defaultextension=".txt",
            initialfile="vdrive_log.txt",
            filetypes=[(_tr("Plik tekstowy"), "*.txt"), (_tr("Wszystkie pliki"), "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo(_tr("Zapisano"), _tr("Log zapisany:\n{path}").format(path=path))

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: BAZA DANYCH
    # ══════════════════════════════════════════════════════════════════════════
    def _build_db_frame(self):
        import json, sqlite3

        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["db"] = outer

        # ── stan wewnętrzny ──────────────────────────────────────────────────
        self._db_online      = False          # True = połączono z SQLite
        self._db_conn        = None
        self._db_path        = tk.StringVar(value="")
        self._db_status_var  = tk.StringVar(value="⚪  Offline — brak połączenia")
        self._db_query_hist  = []
        self._db_brow_offset = 0
        self._db_history_var = tk.StringVar(value="")

        # ── górny pasek pod-zakładek ─────────────────────────────────────────
        sub_bar = tk.Frame(outer, bg=BG_PANEL)
        sub_bar.pack(fill="x", side="top")
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        db_content = tk.Frame(outer, bg=BG_DARK)
        db_content.pack(fill="both", expand=True)

        self._db_sub_btns   = []
        self._db_sub_frames = {}

        db_sub_tabs = [
            ("🔌 Połączenie",    "_db_show_conn"),
            ("📁 Pliki bazy",    "_db_show_files"),
            ("🔍 Zapytania SQL", "_db_show_query"),
            ("📊 Przeglądarka",  "_db_show_browser"),
            ("📋 Log",           "_db_show_log"),
        ]

        def _sel_db_sub(idx, key):
            for j, b in enumerate(self._db_sub_btns):
                b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                            fg=FG_WHITE       if j == idx else FG_GRAY)
            for f in self._db_sub_frames.values():
                f.pack_forget()
            self._db_sub_frames[key].pack(fill="both", expand=True, padx=4, pady=4)
            self._update_minsize()

        self._db_sel_sub = _sel_db_sub

        for i, (label, key) in enumerate(db_sub_tabs):
            b = self._trw(tk.Button(sub_bar, text=_tr(label), font=FONT_UI,
                          bg=BG_SUBTAB_ACT if i == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if i == 0 else FG_GRAY,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i, k=key: _sel_db_sub(i, k)), label)
            b.pack(side="left")
            self._db_sub_btns.append(b)

        # ── pasek stanu (wspólny) ────────────────────────────────────────────
        status_bar = tk.Frame(outer, bg=BG_PANEL, pady=3)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self._db_status_var,
                 font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY,
                 anchor="w").pack(side="left", padx=10)

        # ════════════════════════════════════════════════════════════════════
        # PANEL 1 — POŁĄCZENIE (on/offline)
        # ════════════════════════════════════════════════════════════════════
        pconn = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_conn"] = pconn

        self._trw(tk.Label(pconn, text=_tr("🔌 Zarządzanie połączeniem z bazą danych"),
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE), '🔌 Zarządzanie połączeniem z bazą danych').pack(anchor="w", padx=12, pady=(10, 4))

        # wybór pliku
        row_path = tk.Frame(pconn, bg=BG_DARK)
        row_path.pack(fill="x", padx=12, pady=4)
        self._trw(tk.Label(row_path, text=_tr("Plik bazy SQLite:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY, anchor="w"), "Plik bazy SQLite:").pack(side="left")
        tk.Entry(row_path, textvariable=self._db_path, font=FONT_MONO,
                 bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE,
                 relief="flat", highlightthickness=1, highlightbackground=BORDER_CLR,
                 highlightcolor=ACCENT_BLUE, width=36).pack(side="left", padx=(0, 6), fill="x", expand=True)
        self._trw(tk.Button(row_path, text=_tr("📂 Przeglądaj…"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_browse_file), '📂 Przeglądaj…').pack(side="left", padx=2)
        self._trw(tk.Button(row_path, text=_tr("🆕 Nowa baza"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_new_file), "🆕 Nowa baza").pack(side="left", padx=2)

        # przyciski połączenia
        row_btns = tk.Frame(pconn, bg=BG_DARK)
        row_btns.pack(fill="x", padx=12, pady=6)
        self._db_btn_connect = self._trw(tk.Button(row_btns, text=_tr("🟢 Połącz (Online)"),
                  font=FONT_BOLD, bg=BTN_OK, fg=FG_WHITE, relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  activebackground=BTN_OK_HOVER, activeforeground=FG_WHITE,
                  command=self._db_connect), '🟢 Połącz (Online)')
        self._db_btn_connect.pack(side="left", padx=(0, 6))
        self._db_btn_disconnect = self._trw(tk.Button(row_btns, text=_tr("🔴 Rozłącz (Offline)"),
                  font=FONT_BOLD, bg=BTN_ERR, fg=FG_WHITE, relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  activebackground=BTN_ERR_HOVER, activeforeground=FG_WHITE,
                  state="disabled",
                  command=self._db_disconnect), '🔴 Rozłącz (Offline)')
        self._db_btn_disconnect.pack(side="left", padx=(0, 6))
        self._trw(tk.Button(row_btns, text=_tr("🔄 Test połączenia"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_test_conn), '🔄 Test połączenia').pack(side="left", padx=(0, 6))

        # panel informacji o połączeniu
        tk.Frame(pconn, bg=BORDER_CLR, height=1).pack(fill="x", padx=12, pady=6)
        self._trw(tk.Label(pconn, text=_tr("ℹ Informacje o bazie:"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_GRAY), "ℹ Informacje o bazie:").pack(anchor="w", padx=12)

        self._db_info_text = tk.Text(pconn, font=("Consolas", 9), bg=BG_PANEL,
                                      fg=FG_WHITE, relief="flat", height=14,
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      state="disabled", wrap="none")
        self._db_info_text.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        # pasek szybkich akcji
        row_quick = tk.Frame(pconn, bg=BG_DARK)
        row_quick.pack(fill="x", padx=12, pady=(0, 8))
        for txt, cmd in [
            ("📊 Odśwież info",  self._db_refresh_info),
            ("💾 Eksportuj do JSON", self._db_export_json),
            ("📥 Importuj z JSON",   self._db_import_json),
            ("🗑 Wyczyść tabele",    self._db_drop_all),
        ]:
            self._trw(tk.Button(row_quick, text=_tr(txt), font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(side="left", padx=3)

        # ════════════════════════════════════════════════════════════════════
        # PANEL 2 — PLIKI BAZY DANYCH
        # ════════════════════════════════════════════════════════════════════
        pfiles = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_files"] = pfiles

        self._trw(tk.Label(pfiles, text=_tr("📁 Pliki baz danych"),
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE), "📁 Pliki baz danych").pack(anchor="w", padx=12, pady=(10, 4))

        # pasek akcji
        fbar = tk.Frame(pfiles, bg=BG_PANEL, pady=6, padx=8)
        fbar.pack(fill="x")
        for txt, cmd in [
            ("📂 Otwórz plik",   self._db_browse_file),
            ("🆕 Nowa baza",     self._db_new_file),
            ("📋 Kopiuj ścieżkę",self._db_copy_path),
            ("🔍 Skanuj folder", self._db_scan_folder),
            ("♻ Odśwież",       self._db_refresh_files),
        ]:
            self._trw(tk.Button(fbar, text=_tr(txt), font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(side="left", padx=3)

        # drzewko plików
        tree_frame = tk.Frame(pfiles, bg=BG_DARK)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(6, 4))

        cols = ("Plik", "Rozmiar", "Ostatnia modyfikacja", "Ścieżka")
        self._db_files_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                            height=14, selectmode="browse")
        for c, w in zip(cols, (180, 90, 160, 360)):
            self._trh(self._db_files_tree, c, c)
            self._db_files_tree.column(c, width=w, anchor="w")
        self._db_files_tree.tag_configure("odd",  background=BG_ROW_ODD)
        self._db_files_tree.tag_configure("even", background=BG_ROW_EVEN)
        self._db_files_tree.tag_configure("sel",  background=BG_ROW_SEL)

        ysb = tk.Scrollbar(tree_frame, orient="vertical",
                           command=self._db_files_tree.yview,
                           bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        ysb.pack(side="right", fill="y")
        self._db_files_tree.configure(yscrollcommand=ysb.set)
        self._db_files_tree.pack(fill="both", expand=True)
        self._db_files_tree.bind("<Double-1>", lambda e: self._db_open_selected_file())

        # dolne akcje
        fbtm = tk.Frame(pfiles, bg=BG_DARK)
        fbtm.pack(fill="x", padx=12, pady=(0, 8))
        for txt, cmd in [
            ("✅ Połącz wybrany",    self._db_open_selected_file),
            ("🗑 Usuń plik",         self._db_delete_selected_file),
            ("📤 Eksportuj wybrany", self._db_export_selected),
        ]:
            self._trw(tk.Button(fbtm, text=_tr(txt), font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(side="left", padx=3)

        # ════════════════════════════════════════════════════════════════════
        # PANEL 3 — ZAPYTANIA SQL
        # ════════════════════════════════════════════════════════════════════
        pquery = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_query"] = pquery

        self._trw(tk.Label(pquery, text=_tr("🔍 Edytor zapytań SQL"),
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE), '🔍 Edytor zapytań SQL').pack(anchor="w", padx=12, pady=(10, 4))

        # edytor SQL
        sql_frame = tk.Frame(pquery, bg=BG_DARK)
        sql_frame.pack(fill="x", padx=12, pady=(0, 4))
        self._trw(tk.Label(sql_frame, text=_tr("Zapytanie SQL:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Zapytanie SQL:").pack(anchor="w")
        self._db_sql_text = tk.Text(sql_frame, font=FONT_MONO, bg=BG_INPUT,
                                     fg="#c8d0f0", insertbackground=FG_WHITE,
                                     relief="flat", height=6,
                                     highlightthickness=1, highlightbackground=BORDER_CLR,
                                     highlightcolor=ACCENT_BLUE, wrap="none")
        self._db_sql_text.pack(fill="x", pady=(2, 0))

        # historia zapytań + szablony
        qbar = tk.Frame(pquery, bg=BG_PANEL, pady=5, padx=8)
        qbar.pack(fill="x")
        self._trw(tk.Button(qbar, text=_tr("▶ Wykonaj (F9)"), font=FONT_BOLD,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=12, pady=4,
                  cursor="hand2", activebackground="#3a7bc8", activeforeground=FG_WHITE,
                  command=self._db_run_query), "▶ Wykonaj (F9)").pack(side="left", padx=(0, 6))
        self._trw(tk.Button(qbar, text=_tr("🗑 Wyczyść"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=lambda: self._db_sql_text.delete("1.0", "end")), '🗑 Wyczyść').pack(side="left", padx=3)
        self._trw(tk.Button(qbar, text=_tr("📋 Kopiuj wyniki"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_copy_results), "📋 Kopiuj wyniki").pack(side="left", padx=3)
        self._trw(tk.Button(qbar, text=_tr("💾 Eksportuj CSV"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_export_csv), "💾 Eksportuj CSV").pack(side="left", padx=3)

        # szablony SQL
        self._trw(tk.Label(qbar, text=_tr(" | Szablony:"), font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY), " | Szablony:").pack(side="left", padx=(10, 4))
        templates = [
            ("SELECT *",      "SELECT * FROM tabela LIMIT 100;"),
            ("CREATE TABLE",  "CREATE TABLE IF NOT EXISTS nowa_tabela (\n  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  nazwa TEXT NOT NULL,\n  wartosc TEXT\n);"),
            ("INSERT",        "INSERT INTO tabela (kolumna1, kolumna2) VALUES (?, ?);"),
            ("Tabele",        "SELECT name FROM sqlite_master WHERE type='table';"),
            ("Schemat",       "SELECT sql FROM sqlite_master WHERE type='table' AND name='tabela';"),
        ]
        for lbl, sql in templates:
            self._trw(tk.Button(qbar, text=_tr(lbl), font=("Consolas", 8),
                      bg=BG_SUBTAB_INACT, fg=FG_GRAY, relief="flat", padx=6, pady=3,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=lambda s=sql: (self._db_sql_text.delete("1.0", "end"),
                                            self._db_sql_text.insert("1.0", s))
                      ), lbl).pack(side="left", padx=2)

        history_bar = tk.Frame(pquery, bg=BG_DARK)
        history_bar.pack(fill="x", padx=12, pady=(5, 3))
        self._trw(tk.Label(history_bar, text=_tr("Historia zapytań:"),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "Historia zapytań:").pack(side="left", padx=(0, 6))
        self._db_query_history_combo = ttk.Combobox(
            history_bar, textvariable=self._db_history_var,
            values=(), state="readonly", width=72)
        self._db_query_history_combo.pack(side="left", fill="x", expand=True)
        self._db_query_history_combo.bind(
            "<<ComboboxSelected>>", self._db_restore_query)

        # wyniki
        self._trw(tk.Label(pquery, text=_tr("Wyniki:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Wyniki:").pack(anchor="w", padx=12)
        res_frame = tk.Frame(pquery, bg=BG_DARK)
        res_frame.pack(fill="both", expand=True, padx=12, pady=(2, 8))

        self._db_result_tree = ttk.Treeview(res_frame, show="headings",
                                             height=10, selectmode="browse")
        ys2 = tk.Scrollbar(res_frame, orient="vertical",
                            command=self._db_result_tree.yview,
                            bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        xs2 = tk.Scrollbar(res_frame, orient="horizontal",
                            command=self._db_result_tree.xview,
                            bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        ys2.pack(side="right", fill="y")
        xs2.pack(side="bottom", fill="x")
        self._db_result_tree.configure(yscrollcommand=ys2.set, xscrollcommand=xs2.set)
        self._db_result_tree.pack(fill="both", expand=True)
        self._db_result_tree.tag_configure("odd",  background=BG_ROW_ODD)
        self._db_result_tree.tag_configure("even", background=BG_ROW_EVEN)

        self._db_query_status = tk.Label(pquery, text="", font=("Consolas", 8),
                                          bg=BG_DARK, fg=FG_GRAY, anchor="w")
        self._db_query_status.pack(fill="x", padx=12)

        # bind F9
        self._db_sql_text.bind("<F9>", lambda e: self._db_run_query())

        # ════════════════════════════════════════════════════════════════════
        # PANEL 4 — PRZEGLĄDARKA TABEL
        # ════════════════════════════════════════════════════════════════════
        pbrow = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_browser"] = pbrow

        self._trw(tk.Label(pbrow, text=_tr("📊 Przeglądarka tabel"),
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE), '📊 Przeglądarka tabel').pack(anchor="w", padx=12, pady=(10, 4))

        brow_top = tk.Frame(pbrow, bg=BG_DARK)
        brow_top.pack(fill="x", padx=12, pady=(0, 4))

        # lewa lista tabel
        left_col = tk.Frame(brow_top, bg=BG_DARK)
        left_col.pack(side="left", fill="y", padx=(0, 10))
        self._trw(tk.Label(left_col, text=_tr("Tabele:"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Tabele:").pack(anchor="w")

        self._db_tables_lb = tk.Listbox(left_col, font=FONT_MONO, bg=BG_INPUT,
                                         fg=FG_WHITE, selectmode="browse",
                                         relief="flat", highlightthickness=1,
                                         highlightbackground=BORDER_CLR,
                                         highlightcolor=ACCENT_BLUE,
                                         selectbackground=BG_ROW_SEL,
                                         activestyle="none", width=22, height=18)
        self._db_tables_lb.pack(fill="y", expand=True)
        self._db_tables_lb.bind(
            "<<ListboxSelect>>", lambda e: self._db_load_table(reset_offset=True))

        brow_btn_f = tk.Frame(left_col, bg=BG_DARK)
        brow_btn_f.pack(fill="x", pady=4)
        self._trw(tk.Button(brow_btn_f, text=_tr("🔄 Odśwież"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_refresh_tables), '🔄 Odśwież').pack(fill="x")

        # prawa: podgląd tabeli
        right_col = tk.Frame(brow_top, bg=BG_DARK)
        right_col.pack(side="left", fill="both", expand=True)

        brow_top2 = tk.Frame(right_col, bg=BG_PANEL, pady=4, padx=6)
        brow_top2.pack(fill="x")
        self._trw(tk.Label(brow_top2, text=_tr("Wiersze:"), font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY), "Wiersze:").pack(side="left")
        self._db_brow_limit = tk.Entry(brow_top2, font=FONT_MONO, bg=BG_INPUT,
                                        fg=FG_WHITE, insertbackground=FG_WHITE,
                                        relief="flat", width=6)
        self._db_brow_limit.insert(0, "500")
        self._db_brow_limit.pack(side="left", padx=4)
        self._trw(tk.Button(brow_top2, text=_tr("▶ Załaduj"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground="#3a7bc8", activeforeground=FG_WHITE,
                  command=lambda: self._db_load_table(reset_offset=True)), '▶ Załaduj').pack(side="left", padx=4)
        self._db_brow_prev_btn = self._trw(tk.Button(
            brow_top2, text=_tr("◀ Poprzednia"), font=FONT_UI,
            bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
            cursor="hand2", activebackground=BTN_HOVER,
            command=lambda: self._db_brow_move_page(-1)), "◀ Poprzednia")
        self._db_brow_prev_btn.pack(side="left", padx=3)
        self._db_brow_next_btn = self._trw(tk.Button(
            brow_top2, text=_tr("Następna ▶"), font=FONT_UI,
            bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
            cursor="hand2", activebackground=BTN_HOVER,
            command=lambda: self._db_brow_move_page(1)), "Następna ▶")
        self._db_brow_next_btn.pack(side="left", padx=3)
        self._trw(tk.Button(brow_top2, text=_tr("💾 Eksportuj CSV"), font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_export_table_csv), "💾 Eksportuj CSV").pack(side="left", padx=4)

        brow_tree_f = tk.Frame(right_col, bg=BG_DARK)
        brow_tree_f.pack(fill="both", expand=True)
        self._db_brow_tree = ttk.Treeview(brow_tree_f, show="headings",
                                           height=16, selectmode="browse")
        ys3 = tk.Scrollbar(brow_tree_f, orient="vertical",
                            command=self._db_brow_tree.yview,
                            bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        xs3 = tk.Scrollbar(brow_tree_f, orient="horizontal",
                            command=self._db_brow_tree.xview,
                            bg=BG_PANEL, troughcolor=BG_PANEL, width=8)
        ys3.pack(side="right", fill="y")
        xs3.pack(side="bottom", fill="x")
        self._db_brow_tree.configure(yscrollcommand=ys3.set, xscrollcommand=xs3.set)
        self._db_brow_tree.pack(fill="both", expand=True)
        self._db_brow_tree.tag_configure("odd",  background=BG_ROW_ODD)
        self._db_brow_tree.tag_configure("even", background=BG_ROW_EVEN)

        self._db_brow_status = tk.Label(pbrow, text="", font=("Consolas", 8),
                                         bg=BG_DARK, fg=FG_GRAY, anchor="w")
        self._db_brow_status.pack(fill="x", padx=12, pady=(2, 6))

        # ════════════════════════════════════════════════════════════════════
        # PANEL 5 — LOG
        # ════════════════════════════════════════════════════════════════════
        plog = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_log"] = plog

        self._trw(tk.Label(plog, text=_tr("📋 Log operacji bazodanowych"),
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE), "📋 Log operacji bazodanowych").pack(anchor="w", padx=12, pady=(10, 4))

        log_btn_f = tk.Frame(plog, bg=BG_PANEL, pady=5, padx=8)
        log_btn_f.pack(fill="x")
        for txt, cmd in [
            ("🗑 Wyczyść log", lambda: self._db_log_text.delete("1.0", "end")),
            ("💾 Zapisz log",  self._db_save_log),
            ("📋 Kopiuj log",  self._db_copy_log),
        ]:
            self._trw(tk.Button(log_btn_f, text=_tr(txt), font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd), txt).pack(side="left", padx=3)

        self._db_log_text = tk.Text(plog, font=("Consolas", 9), bg=BG_PANEL,
                                     fg=FG_WHITE, relief="flat",
                                     highlightthickness=1, highlightbackground=BORDER_CLR,
                                     state="disabled", wrap="word")
        self._db_log_text.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        self._db_log_text.tag_configure("ok",  foreground="#6dde84")
        self._db_log_text.tag_configure("err", foreground="#e05c5c")
        self._db_log_text.tag_configure("cmd", foreground="#7ec8e3")
        self._db_log_text.tag_configure("inf", foreground="#c8c040")

        # pokaż pierwszy panel
        _sel_db_sub(0, "_db_show_conn")

    def _show_db(self):
        self.main_frames["db"].pack(fill="both", expand=True)

    # ── DB helpers ────────────────────────────────────────────────────────────
    def _db_log(self, msg, tag="inf"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._db_log_text.config(state="normal")
        self._db_log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self._db_log_text.see("end")
        self._db_log_text.config(state="disabled")

    def _db_set_status(self, msg, fg=FG_GRAY):
        self._db_status_var.set(msg)

    def _db_record_query(self, sql):
        self._db_query_hist = [query for query in self._db_query_hist if query != sql]
        self._db_query_hist.insert(0, sql)
        del self._db_query_hist[20:]
        self._db_query_history_combo.configure(values=self._db_query_hist)
        self._db_history_var.set(sql)

    def _db_restore_query(self, event=None):
        sql = self._db_history_var.get()
        if not sql:
            return
        self._db_sql_text.delete("1.0", "end")
        self._db_sql_text.insert("1.0", sql)
        return "break"

    def _db_connect(self):
        import sqlite3
        path = self._db_path.get().strip()
        if not path:
            messagebox.showwarning(_tr("Brak ścieżki"), _tr("Podaj ścieżkę do pliku bazy SQLite."))
            return
        try:
            if self._db_conn:
                self._db_conn.close()
            self._db_conn = sqlite3.connect(path)
            self._db_online = True
            self._db_btn_connect.config(state="disabled")
            self._db_btn_disconnect.config(state="normal")
            self._db_set_status(f"🟢  Online — {path}", "#6dde84")
            self._db_log(f"Połączono z bazą: {path}", "ok")
            self._db_refresh_info()
            self._db_refresh_tables()
            self._db_refresh_files()
        except Exception as ex:
            self._db_log(f"Błąd połączenia: {ex}", "err")
            messagebox.showerror(_tr("Błąd połączenia"), str(ex))

    def _db_disconnect(self):
        if self._db_conn:
            try:
                self._db_conn.close()
            except Exception:
                pass
        self._db_conn   = None
        self._db_online = False
        self._db_btn_connect.config(state="normal")
        self._db_btn_disconnect.config(state="disabled")
        self._db_set_status("⚪  Offline — brak połączenia")
        self._db_log("Rozłączono.", "inf")
        self._db_info_text.config(state="normal")
        self._db_info_text.delete("1.0", "end")
        self._db_info_text.config(state="disabled")

    def _db_test_conn(self):
        if not self._db_online or not self._db_conn:
            messagebox.showinfo(_tr("Test"), _tr("Brak aktywnego połączenia."))
            return
        try:
            self._db_conn.execute("SELECT 1")
            messagebox.showinfo(_tr("Test połączenia"), _tr("✅ Połączenie aktywne i sprawne."))
            self._db_log("Test połączenia: OK", "ok")
        except Exception as ex:
            messagebox.showerror(_tr("Test połączenia"),f"Błąd: {ex}")
            self._db_log(f"Test połączenia: BŁĄD — {ex}", "err")

    def _db_refresh_info(self):
        if not self._db_online or not self._db_conn:
            return
        try:
            cur = self._db_conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            lines = []
            lines.append(f"Plik bazy  : {self._db_path.get()}")
            lines.append(f"Tabele ({len(tables)}): {', '.join(tables) if tables else '(brak)'}")
            for t in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                    cnt = cur.fetchone()[0]
                    cur.execute(f"PRAGMA table_info([{t}])")
                    cols = cur.fetchall()
                    lines.append(f"  • {t}: {cnt} wierszy, {len(cols)} kolumn")
                except Exception:
                    lines.append(f"  • {t}: (błąd odczytu)")
            lines.append("")
            lines.append(f"SQLite wersja: {self._db_conn.execute('SELECT sqlite_version()').fetchone()[0]}")
            import os
            sz = os.path.getsize(self._db_path.get()) if os.path.exists(self._db_path.get()) else 0
            lines.append(f"Rozmiar pliku: {sz:,} B ({sz // 1024} KB)")
            self._db_info_text.config(state="normal")
            self._db_info_text.delete("1.0", "end")
            self._db_info_text.insert("1.0", "\n".join(lines))
            self._db_info_text.config(state="disabled")
        except Exception as ex:
            self._db_log(f"Błąd odczytu info: {ex}", "err")

    def _db_browse_file(self):
        path = filedialog.askopenfilename(
            title=_tr("Wybierz plik bazy SQLite"),
            filetypes=[("SQLite", "*.db *.sqlite *.sqlite3 *.s3db"),
                       ("Wszystkie", "*.*")])
        if path:
            self._db_path.set(path)
            self._db_log(f"Wybrany plik: {path}", "inf")

    def _db_new_file(self):
        import sqlite3
        path = filedialog.asksaveasfilename(
            title=_tr("Nowy plik bazy SQLite"),
            defaultextension=".db",
            filetypes=[("SQLite", "*.db *.sqlite *.sqlite3"),
                       ("Wszystkie", "*.*")])
        if path:
            try:
                conn = sqlite3.connect(path)
                conn.close()
                self._db_path.set(path)
                self._db_log(f"Utworzono nową bazę: {path}", "ok")
                self._db_refresh_files()
            except Exception as ex:
                messagebox.showerror(_tr("Błąd"), str(ex))

    def _db_copy_path(self):
        path = self._db_path.get().strip()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)
            messagebox.showinfo(_tr("Skopiowano"), _tr("Ścieżka skopiowana do schowka.")
)
    def _db_scan_folder(self):
        folder = filedialog.askdirectory(title=_tr("Wybierz folder do skanowania"))
        if not folder:
            return
        import os
        self._db_log(f"Skanowanie folderu: {folder}", "inf")
        found = []
        for root, _, files in os.walk(folder):
            for fn in files:
                if fn.lower().endswith((".db", ".sqlite", ".sqlite3", ".s3db")):
                    found.append(os.path.join(root, fn))
        self._db_populate_files(found)
        self._db_log(f"Znaleziono {len(found)} plików baz danych.", "ok")

    def _db_refresh_files(self):
        import os
        cur_path = self._db_path.get().strip()
        files = []
        if cur_path and os.path.isfile(cur_path):
            files.append(cur_path)
        # szukaj w bieżącym katalogu
        try:
            for fn in os.listdir("."):
                if fn.lower().endswith((".db", ".sqlite", ".sqlite3", ".s3db")):
                    full = os.path.abspath(fn)
                    if full not in files:
                        files.append(full)
        except Exception:
            pass
        self._db_populate_files(files)

    def _db_populate_files(self, file_list):
        import os
        for row in self._db_files_tree.get_children():
            self._db_files_tree.delete(row)
        for i, fp in enumerate(file_list):
            try:
                sz  = os.path.getsize(fp)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
                szstr = f"{sz:,} B" if sz < 1024 * 1024 else f"{sz / 1024 / 1024:.1f} MB"
            except Exception:
                szstr = "—"; mtime = "—"
            tag = "odd" if i % 2 == 0 else "even"
            self._db_files_tree.insert("", "end",
                values=(os.path.basename(fp), szstr, mtime, fp),
                tags=(tag,))

    def _db_open_selected_file(self):
        sel = self._db_files_tree.selection()
        if not sel:
            return
        path = self._db_files_tree.item(sel[0], "values")[3]
        self._db_path.set(path)
        self._db_connect()

    def _db_delete_selected_file(self):
        import os
        sel = self._db_files_tree.selection()
        if not sel:
            return
        path = self._db_files_tree.item(sel[0], "values")[3]
        if messagebox.askyesno(_tr("Usuń plik"), f"Usunąć plik bazy:\n{path}\n\nTej operacji nie można cofnąć!"):
            try:
                if self._db_online and self._db_path.get() == path:
                    self._db_disconnect()
                os.remove(path)
                self._db_log(f"Usunięto plik: {path}", "inf")
                self._db_refresh_files()
            except Exception as ex:
                messagebox.showerror(_tr("Błąd"), str(ex))

    def _db_export_selected(self):
        sel = self._db_files_tree.selection()
        if not sel:
            return
        src = self._db_files_tree.item(sel[0], "values")[3]
        dst = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite", "*.db *.sqlite"), ("Wszystkie", "*.*")])
        if dst:
            import shutil
            shutil.copy2(src, dst)
            self._db_log(f"Skopiowano {src} → {dst}", "ok")
            messagebox.showinfo(_tr("Eksport"), f"Skopiowano do:\n{dst}")

    def _db_run_query(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning(_tr("Offline"), _tr("Najpierw połącz się z bazą danych."))
            return
        sql = self._db_sql_text.get("1.0", "end-1c").strip()
        if not sql:
            return
        self._db_record_query(sql)
        self._db_log(f"SQL: {sql[:80]}{'…' if len(sql) > 80 else ''}", "cmd")
        try:
            cur = self._db_conn.cursor()
            cur.execute(sql)
            if sql.strip().upper().startswith("SELECT"):
                rows = cur.fetchall()
                cols = [d[0] for d in (cur.description or [])]
                # wyczyść tree
                self._db_result_tree.delete(*self._db_result_tree.get_children())
                self._db_result_tree["columns"] = cols
                for c in cols:
                    self._db_result_tree.heading(c, text=c)
                    self._db_result_tree.column(c, width=max(100, len(c)*10), anchor="w")
                for i, row in enumerate(rows):
                    tag = "odd" if i % 2 == 0 else "even"
                    self._db_result_tree.insert("", "end", values=row, tags=(tag,))
                self._db_query_status.config(
                    text=f"✅ Zwrócono {len(rows)} wierszy, {len(cols)} kolumn.",
                    fg="#6dde84")
                self._db_log(f"Wynik: {len(rows)} wierszy.", "ok")
            else:
                self._db_conn.commit()
                self._db_query_status.config(
                    text=f"✅ Zapytanie wykonane. Dotknięte wiersze: {cur.rowcount}",
                    fg="#6dde84")
                self._db_log(f"Wykonano (rowcount={cur.rowcount}).", "ok")
                self._db_refresh_tables()
        except Exception as ex:
            self._db_query_status.config(text=f"❌ Błąd: {ex}", fg="#e05c5c")
            self._db_log(f"Błąd SQL: {ex}", "err")

    def _db_copy_results(self):
        cols = self._db_result_tree["columns"]
        rows = [self._db_result_tree.item(r, "values") for r in self._db_result_tree.get_children()]
        if not rows:
            return
        lines = ["\t".join(cols)] + ["\t".join(str(v) for v in r) for r in rows]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        messagebox.showinfo(_tr("Skopiowano"), f"Skopiowano {len(rows)} wierszy.")

    def _db_export_csv(self):
        cols = self._db_result_tree["columns"]
        rows = [self._db_result_tree.item(r, "values") for r in self._db_result_tree.get_children()]
        if not rows:
            messagebox.showinfo(_tr("Brak danych"), _tr("Brak wyników do eksportu."))
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV", "*.csv"), ("Wszystkie", "*.*")])
        if path:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
            self._db_log(f"Eksportowano CSV: {path}", "ok")
            messagebox.showinfo(_tr("Eksport CSV"), f"Zapisano:\n{path}")

    def _db_export_table_csv(self):
        sel = self._db_tables_lb.curselection()
        if not sel:
            return
        table = self._db_tables_lb.get(sel[0])
        cols  = self._db_brow_tree["columns"]
        rows  = [self._db_brow_tree.item(r, "values") for r in self._db_brow_tree.get_children()]
        path  = filedialog.asksaveasfilename(
            initialfile=f"{table}.csv",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Wszystkie", "*.*")])
        if path:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
            self._db_log(f"Eksportowano tabelę '{table}' → {path}", "ok")
            messagebox.showinfo(_tr("Eksport"), f"Tabela '{table}' zapisana do:\n{path}")

    def _db_refresh_tables(self):
        if not self._db_online or not self._db_conn:
            return
        try:
            cur = self._db_conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = [r[0] for r in cur.fetchall()]
            self._db_tables_lb.delete(0, "end")
            for t in tables:
                self._db_tables_lb.insert("end", t)
        except Exception as ex:
            self._db_log(f"Błąd odczytu tabel: {ex}", "err")

    @staticmethod
    def _db_fetch_table_page(connection, table, limit, offset):
        limit = max(1, min(10000, int(limit)))
        offset = max(0, int(offset))
        quoted_table = '"' + str(table).replace('"', '""') + '"'
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT * FROM {quoted_table} LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        columns = [description[0] for description in (cursor.description or [])]
        cursor.execute(f"SELECT COUNT(*) FROM {quoted_table}")
        total = cursor.fetchone()[0]
        return columns, rows, total

    def _db_brow_move_page(self, direction):
        try:
            limit = int(self._db_brow_limit.get())
        except ValueError:
            limit = 500
        limit = max(1, min(10000, limit))
        self._db_brow_offset = max(0, self._db_brow_offset + direction * limit)
        self._db_load_table()

    def _db_load_table(self, reset_offset=False):
        if not self._db_online or not self._db_conn:
            return
        sel = self._db_tables_lb.curselection()
        if not sel:
            return
        table = self._db_tables_lb.get(sel[0])
        if reset_offset:
            self._db_brow_offset = 0
        try:
            limit = int(self._db_brow_limit.get())
        except ValueError:
            limit = 500
        limit = max(1, min(10000, limit))
        try:
            offset = max(0, self._db_brow_offset)
            cols, rows, total = self._db_fetch_table_page(
                self._db_conn, table, limit, offset)
            if offset >= total and offset:
                offset = ((total - 1) // limit) * limit if total else 0
                self._db_brow_offset = offset
                cols, rows, total = self._db_fetch_table_page(
                    self._db_conn, table, limit, offset)
            self._db_brow_tree.delete(*self._db_brow_tree.get_children())
            self._db_brow_tree["columns"] = cols
            for c in cols:
                self._db_brow_tree.heading(c, text=c)
                self._db_brow_tree.column(c, width=max(90, len(c)*9), anchor="w")
            for i, row in enumerate(rows):
                tag = "odd" if i % 2 == 0 else "even"
                self._db_brow_tree.insert("", "end", values=row, tags=(tag,))
            page = offset // limit + 1
            pages = max(1, (total + limit - 1) // limit)
            first = offset + 1 if rows else 0
            last = offset + len(rows)
            self._db_brow_status.config(
                text=_tr("Strona {page}/{pages} | wiersze {first}-{last} z {total} | kolumn: {cols}").format(
                    page=page, pages=pages, first=first, last=last,
                    total=total, cols=len(cols)),
                fg="#6dde84")
            self._db_brow_prev_btn.configure(
                state="normal" if offset > 0 else "disabled")
            self._db_brow_next_btn.configure(
                state="normal" if offset + len(rows) < total else "disabled")
            self._db_log(f"Załadowano tabelę '{table}': {len(rows)} wierszy.", "ok")
        except Exception as ex:
            self._db_log(f"Błąd ładowania tabeli '{table}': {ex}", "err")

    def _db_export_json(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning(_tr("Offline"), _tr("Najpierw połącz się z bazą."))
            return
        import json
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
        if not path:
            return
        try:
            cur = self._db_conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            dump = {}
            for t in tables:
                cur.execute(f"SELECT * FROM [{t}]")
                cols = [d[0] for d in cur.description]
                dump[t] = [dict(zip(cols, row)) for row in cur.fetchall()]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, indent=2, default=str)
            self._db_log(f"Eksportowano bazę do JSON: {path}", "ok")
            messagebox.showinfo(_tr("Eksport JSON"), f"Baza zapisana do:\n{path}")
        except Exception as ex:
            self._db_log(f"Błąd eksportu JSON: {ex}", "err")
            messagebox.showerror(_tr("Błąd eksportu"), str(ex))

    def _db_import_json(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning(_tr("Offline"), _tr("Najpierw połącz się z bazą."))
            return
        import json
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                messagebox.showerror(_tr("Błąd"), _tr("Plik JSON powinien zawierać słownik tabel."))
                return
            cur = self._db_conn.cursor()
            imported = 0
            for table, rows in data.items():
                if not rows:
                    continue
                cols = list(rows[0].keys())
                col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
                cur.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')
                for row in rows:
                    vals = [str(row.get(c, "")) for c in cols]
                    ph = ", ".join("?" * len(cols))
                    cur.execute(f'INSERT INTO "{table}" VALUES ({ph})', vals)
                    imported += 1
            self._db_conn.commit()
            self._db_log(f"Zaimportowano {imported} wierszy z: {path}", "ok")
            self._db_refresh_tables()
            self._db_refresh_info()
            messagebox.showinfo(_tr("Import JSON"), f"Zaimportowano {imported} wierszy.")
        except Exception as ex:
            self._db_log(f"Błąd importu JSON: {ex}", "err")
            messagebox.showerror(_tr("Błąd importu"), str(ex))

    def _db_drop_all(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning(_tr("Offline"), _tr("Najpierw połącz się z bazą."))
            return
        if not messagebox.askyesno(_tr("Wyczyść tabele"), _tr("Usunąć WSZYSTKIE tabele z bazy danych?\n"
                                    "Tej operacji nie można cofnąć!")):
            return
        try:
            cur = self._db_conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            for (t,) in cur.fetchall():
                cur.execute(f"DROP TABLE IF EXISTS [{t}]")
            self._db_conn.commit()
            self._db_log("Wszystkie tabele usunięte.", "inf")
            self._db_refresh_tables()
            self._db_refresh_info()
        except Exception as ex:
            self._db_log(f"Błąd czyszczenia tabel: {ex}", "err")

    def _db_save_log(self):
        content = self._db_log_text.get("1.0", "end-1c")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile="db_log.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo(_tr("Zapisano"), f"Log zapisany:\n{path}")

    def _db_copy_log(self):
        content = self._db_log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo(_tr("Skopiowano"), _tr("Log skopiowany do schowka."))

    # ── helpers ───────────────────────────────────────────────────────────────
    def _opis_focus_in(self, event):
        if self.text_opis.get("1.0", "end-1c") == "Opis skryptu…":
            self.text_opis.delete("1.0", "end")
            self.text_opis.config(fg=FG_WHITE)

    def _opis_focus_out(self, event):
        if not self.text_opis.get("1.0", "end-1c").strip():
            self.text_opis.insert("1.0", "Opis skryptu…")
            self.text_opis.config(fg=FG_GRAY)

    def _sync_scroll(self, *args):
        self.text_kod.yview(*args)
        self._update_line_nums()

    def _on_mousewheel(self, _e):
        self._update_line_nums()

    def _update_line_nums(self, _e=None):
        self.line_nums.config(state="normal")
        self.line_nums.delete("1.0", "end")
        n = int(self.text_kod.index("end-1c").split(".")[0])
        self.line_nums.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self.line_nums.config(state="disabled")

    def _update_count(self):
        self.lbl_count.config(text=_t("header_count", n=len(self.skrypty)))
        if hasattr(self, "_runner_list"):
            sig = tuple((s.get("id"), int(s.get("uruchomien") or 0)) for s in self.skrypty)
            self._runner_list_sig = sig

    # ══════════════════════════════════════════════════════════════════════════
    # JEDNOPLIKOWA BAZA — autoload, atomowy zapis, backup, autosave
    # ══════════════════════════════════════════════════════════════════════════
    def _autoload_db(self):
        """Wczytuje bazę z pliku przy starcie (jednoplikowa CodeMate)."""
        self._autoload_done = True
        if getattr(self, "_shutting_down", False):
            return
        path = getattr(self, "db_path", DB_FILE)
        if not path or not os.path.exists(path):
            self._rebuild_index()
            if hasattr(self, "_runner_fill_list"):
                self._runner_fill_list()
            return
        try:
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("before_db_load", path)
            # dzienna kopia zapasowa — raz na dzień, zanim baza zostanie zmieniona
            bk = daily_backup(path, keep=int(self._cfg.get("backup_days", DAILY_BACKUP_KEEP)))
            if bk:
                logging.info("Dzienny backup bazy: %s", bk)
            lista, notes = db_read(path)
            self.skrypty = lista
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("after_db_load", path, lista)
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            if hasattr(self, "_runner_fill_list"):
                self._runner_fill_list()
            if hasattr(self, "_sched_fill"):
                self._sched_fill()
            if notes:
                self._log_runner("Baza", " " + " | ".join(notes))
            # harmonogram: jeśli jakikolwiek plan jest aktywny — włącz pętlę planów
            if any((self._sched_plan(s) or {}).get("aktywny") for s in self.skrypty):
                self._sched_start()
            # kosz: trwałe usunięcie elementów starszych niż trash_days (jeśli włączone)
            purged = self._trash_purge_old()
            if purged:
                self._log_runner("Kosz", f"Auto-czyszczenie: trwale usunięto {purged} element(ów).")
        except Exception as e:
            messagebox.showwarning(
                _tr("Baza"), f"Nie udało się wczytać bazy:\n{path}\n\n{e}\n\n"
                         "Kopia .bak zostanie użyta przy ręcznym otwarciu.")

    def save_db(self, path: Optional[Union[str, Path]] = None, save_as: bool = False, silent: bool = False) -> bool:
        """Zapisuje całą bazę do stałego pliku JSON (atomowo + backup)."""
        path = path or getattr(self, "db_path", DB_FILE)
        if save_as:
            chosen = filedialog.asksaveasfilename(
                title=_tr("Zapisz bazę skryptów"), defaultextension=".json",
                initialfile=os.path.basename(path or "baza_skryptow.json"),
                filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
            if not chosen:
                return False
            path = chosen
        try:
            try:
                n_bak = int(self._cfg.get("backup_count", "3"))
            except ValueError:
                n_bak = 3
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("before_db_save", path, self.skrypty)
            db_write(path, self.skrypty, backup_count=n_bak)
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("after_db_save", path, self.skrypty)
        except Exception as e:
            messagebox.showerror(_tr("Błąd zapisu"),f"Nie udało się zapisać bazy:\n{e}")
            return False
        self.db_path = Path(path)
        self._cfg["db_path"] = str(path)
        cfg_save(self._cfg)
        self._last_save = now_str()

        # ── Automatyczny commit do Git (tylko gdy auto-commit włączony) ───────
        git = self._ensure_git() if getattr(self, "_git_auto_commit", True) else self._git
        if git and git.is_available() and getattr(self, "_git_auto_commit", True):
            try:
                db_file = Path(path)
                if git.add_file(db_file):
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    commit_msg = f"[AUTO] Baza zapisana - {timestamp}"
                    committed = git.commit(commit_msg)
                    if committed and getattr(self, "_git_auto_push", False):
                        if not git.push():
                            logging.warning("Git auto-push failed: %s", git.last_error)
                    if not silent:
                        logging.info(f"Git commit: {commit_msg}")
            except Exception as e:
                logging.warning(f"Git commit failed: {e}")

        if not silent:
            self._set_db_status(f"✓ Zapisano bazę: {os.path.basename(str(path))}")
        return True
        return True

    def _manual_backup(self):
        """Ręczna dzienna kopia bazy (Ctrl+B / menu Baza) — zawsze tworzy plik."""
        path = getattr(self, "db_path", DB_FILE)
        if not os.path.exists(path):
            messagebox.showinfo(_tr("Backup"), _tr("Baza jeszcze nie istnieje — najpierw zapisz skrypty."))
            return
        target = daily_backup(path, keep=int(self._cfg.get("backup_days", DAILY_BACKUP_KEEP)))
        if target is None:
            # dzisiejsza już istnieje — zrób kopię z godziną, żeby nie nadpisywać
            p = Path(path)
            stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            target = p.parent / DAILY_BACKUP_DIR / f"{p.stem}.{stamp}{p.suffix}"
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
            except OSError as e:
                messagebox.showerror(_tr("Backup"), str(e))
                return
        self._log_runner("Backup", f"kopia zapisana: {target}", "ok")
        self._notify(_tr("Backup"), f"{target.name}", "ok")

    def _save_db(self, save_as=False):
        if self.save_db(save_as=save_as):
            messagebox.showinfo(_tr("Baza"), f"Baza zapisana:\n{self.db_path}")

    def _after_db_change(self) -> None:
        """Wywoływane po zmianach w bazie — planuje autosave (odporny na klikanie)."""
        if str(self._cfg.get("autosave", "1")) != "1":
            return
        if getattr(self, "_shutting_down", False):
            return
        if getattr(self, "_autosave_pending", None):
            try:
                self.after_cancel(self._autosave_pending)
            except Exception:
                pass
        self._autosave_pending = self.after(1500, self._autosave_now)
        try:
            self._after_ids.append(self._autosave_pending)
        except AttributeError:
            pass

    def _autosave_now(self) -> None:
        self._autosave_pending = None
        if getattr(self, "_shutting_down", False):
            return
        self.save_db(silent=True)

    def _open_db(self):
        path = filedialog.askopenfilename(
            title=_tr("Otwórz bazę skryptów"), filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
        if not path:
            return
        try:
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("before_db_load", path)
            lista, notes = db_read(path)
            if self._plugin_manager:
                self._plugin_manager.trigger_hook("after_db_load", path, lista)
        except Exception as e:
            messagebox.showerror(_tr("Błąd"),f"Nie można wczytać bazy:\n{e}")
            return
        self.skrypty = lista
        self.db_path = path
        self._cfg["db_path"] = path
        cfg_save(self._cfg)
        self._rebuild_index()
        self._update_count()
        self._refresh_lista()
        self._set_db_status(f"✓ Baza: {os.path.basename(path)}")
        msg = f"Wczytano {len(lista)} skrypt(ów) z:\n{path}"
        if notes:
            msg += "\n\n" + "\n".join(notes)
        messagebox.showinfo(_tr("Baza"), msg)

    def _open_db_folder(self):
        import subprocess
        path = os.path.dirname(os.path.abspath(getattr(self, "db_path", DB_FILE)))
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror(_tr("Błąd"), str(e))

    def mainloop(self, n=0):
        """Pętla główna — dopiero po wejściu do niej działają after()/dialogi."""
        self._gui_ready = True
        return super().mainloop(n)

    def _on_close(self):
        """Zapis przy zamykaniu — autosave nie gubi ostatnich zmian.

        Bezpieczeństwo wątków: flaga ``_shutting_down`` odcina nadchodzące
        ``_safe_after`` z wątków tła; działający proces runnera jest ubijany,
        a ``_runner_finished`` blokuje ``_runner_finish`` z martwą kolejką.
        """
        self._shutting_down = True
        for aid in list(getattr(self, "_after_ids", [])) + [
                getattr(self, "_sched_after_id", None), getattr(self, "_autosave_pending", None),
                getattr(self, "_runner_after_id", None), getattr(self, "_runner_tick_id", None)]:
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        self._after_ids = []
        # Runner: zakończ proces potomny i oznacz przebieg jako domknięty,
        # żeby wątek pump nie wywoływał finish() na zamkniętym UI.
        proc = getattr(self, "_runner_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                runner_kill_tree(proc)
            except Exception:
                pass
        self._runner_finished = True
        self._runner_proc = None
        try:
            self._sched_running = False
        except Exception:
            pass
        try:
            if self.skrypty:
                self.save_db(silent=True)
        except Exception:
            pass
        if self._plugin_manager:
            try:
                self._plugin_manager.trigger_hook("on_app_close")
            except Exception:
                pass
        for toast in list(getattr(self, "_toasts", [])):
            self._toast_close(toast)
        self.destroy()

    def _set_db_status(self, text):
        if hasattr(self, "lbl_db_status"):
            self.lbl_db_status.config(text=text)

    # ══════════════════════════════════════════════════════════════════════════
    # RUNNER — uruchamianie skryptów z panelu wyjścia
    # ══════════════════════════════════════════════════════════════════════════
    def _runner_env(self, nazwa=""):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        # Sekrety: globalne zawsze, powiązane ze skryptem — gdy zgadza się nazwa.
        if self._secrets is not None:
            try:
                env.update(self._secrets.resolve_env(nazwa))
            except Exception as e:
                logging.warning(f"Nie udało się wstrzyknąć sekretów: {e}")
        # Zmienne środowiskowe per skrypt (pole ENV w rekordzie: KLUCZ=WARTOŚĆ w liniach).
        idx = getattr(self, "_runner_current_idx", None)
        sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if isinstance(sc, dict):
            for line in str(sc.get("runner_env") or "").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                klucz, _, wart = line.partition("=")
                klucz, wart = klucz.strip(), wart.strip()
                if klucz:
                    env[klucz] = wart
        return env

    def _runner_target(self):
        """Zwraca (rekord, kod, kategoria, nazwa) dla wybranego skryptu/formularza."""
        if getattr(self, "_runner_mode_edit", False) and hasattr(self, "text_kod"):
            kod = self.text_kod.get("1.0", "end-1c")
            nazwa = (self.entry_nazwa.get().strip() or _tr("formularz"))
            return None, kod, self.var_kat.get(), nazwa
        idx = getattr(self, "_runner_current_idx", None)
        if idx is None or idx >= len(self.skrypty):
            return None, None, None, None
        sc = self.skrypty[idx]
        return sc, sc.get("kod", ""), sc.get("kategoria", "Other"), sc.get("nazwa", "?")

    def _runner_run_form(self, save_first=True, new_console=False):
        """F9 — uruchamia kod z formularza (opcjonalnie najpierw zapisuje)."""
        if save_first and hasattr(self, "entry_nazwa") and self.entry_nazwa.get().strip():
            self._zapisz(quiet=True)
        self._sel_main(8, self._show_runner)
        self._runner_apply_form_to_list()
        if new_console:
            self._runner_start_new_console()
        else:
            self._runner_start()

    def _runner_open_pane(self, key):
        """Otwiera zakładkę Runner i aktywuje pod-zakładkę (run/hist/plan/stats).
        Bezpieczne nawet, gdy panel Runner nie został jeszcze zbudowany —
        wtedy buduje go na żądanie, a przełączenie panele odbywa się po budowie."""
        self._sel_main(8, self._show_runner)

        def _select_when_ready():
            show = getattr(self, "_runner_show_pane", None)
            if callable(show):
                try:
                    show(key)
                except Exception as e:
                    logging.warning("Nie udało się otworzyć pod-zakładki runnera %r: %s", key, e)
            else:
                # panel jeszcze niezbudowany — spróbuj ponownie po krótkiej chwili
                self.after(120, _select_when_ready)

        _select_when_ready()

    # ══════════════════════════════════════════════════════════════════════════
    # HARMONOGRAM — uruchamianie skryptów z planu (co N minut / o HH:MM)
    # ══════════════════════════════════════════════════════════════════════════
    def _sched_init(self):
        self._sched_running = False
        self._sched_after_id = None
        self._sched_last = {}   # id skryptu → ostatnie dopasowanie slotu

    def _sched_plan(self, sc):
        """Normalizuje plan harmonogramu rekordu. Zwraca dict lub None."""
        plan = sc.get("harmonogram") if isinstance(sc, dict) else None
        if not isinstance(plan, dict):
            return None
        try:
            every = int(plan.get("co_min") or 0)
        except (TypeError, ValueError):
            every = 0
        return {
            "aktywny": bool(plan.get("aktywny")),
            "co_min":  max(0, every),
            "o_godzinie": (plan.get("o_godzinie") or "").strip(),
            "args":    str(plan.get("args") or ""),
        }

    @staticmethod
    def _sched_due(plan, now, last_slot):
        """Sprawdza, czy plan jest do uruchomienia w chwili `now`.
        Zwraca identyfikator slotu (str) albo None. Slot to konkretna minuta —
        dzięki temu jeden slot to jeden przebieg."""
        if not plan or not plan.get("aktywny"):
            return None
        slot_hm = now.strftime("%H:%M")
        if plan.get("o_godzinie") and plan["o_godzinie"] == slot_hm:
            slot = f"hm:{now:%Y-%m-%d %H:%M}"
            if slot != last_slot:
                return slot
        every = plan.get("co_min") or 0
        if every > 0 and now.second < 30:
            stamp = int(now.timestamp() // 60)
            if stamp % every == 0:
                slot = f"iv:{now:%Y-%m-%d %H:%M}"
                if slot != last_slot:
                    return slot
        return None

    def _sched_start(self):
        """Uruchamia pętlę harmonogramu (sprawdza plan co 30 s)."""
        if getattr(self, "_sched_running", False):
            return
        self._sched_init()
        self._sched_running = True
        self._sched_tick()
        self._sched_sync_ui()
        self._log_runner("Harmonogram", "włączony — sprawdzam plany co 30 s", "ok")

    def _sched_stop(self):
        self._sched_running = False
        if getattr(self, "_sched_after_id", None):
            try:
                self.after_cancel(self._sched_after_id)
            except Exception:
                pass
            self._sched_after_id = None
        self._sched_sync_ui()
        self._log_runner("Harmonogram", "wyłączony")

    def _sched_sync_ui(self):
        """Ustawia przycisk start/stop, etykietę stanu i ikonę zakładki."""
        on = getattr(self, "_sched_running", False)
        if hasattr(self, "_sched_btn_on"):
            try:
                self._sched_btn_on.config(
                    text=_tr("■ Zatrzymaj harmonogram") if on else _tr("▶ Włącz harmonogram"),
                    bg=BTN_ERR if on else BTN_ACCENT)
            except Exception:
                pass
        if hasattr(self, "_sched_lbl_state"):
            try:
                self._sched_lbl_state.config(
                    text=_tr("● harmonogram działa") if on else _tr("○ harmonogram zatrzymany"),
                    fg="#6dde84" if on else FG_GRAY)
            except Exception:
                pass
        self._sched_badge()

    def _sched_tick(self):
        """Sprawdza wszystkie plany; uruchamia co najwyżej jeden skrypt naraz."""
        self._sched_after_id = None
        if not getattr(self, "_sched_running", False):
            return
        if not getattr(self, "_runner_busy", False):
            now = datetime.datetime.now()
            for sc in list(self.skrypty):
                plan = self._sched_plan(sc)
                sid = sc.get("id")
                slot = self._sched_due(plan, now, self._sched_last.get(sid))
                if not slot:
                    continue
                self._sched_last[sid] = slot
                self._log_runner("Harmonogram", f"uruchamiam '{sc.get('nazwa')}' (slot {slot})")
                self._sched_fire(sc, slot)
                break
        if getattr(self, "_shutting_down", False):
            return
        self._sched_after_id = self.after(30000, self._sched_tick)

    def _sched_fire(self, sc, slot):
        """Uruchamia skrypt z planu. Wynik ląduje w historii z tagiem harmonogramu."""
        if not sc.get("zaufany"):
            self._log_runner("Harmonogram", f"pomijam '{sc.get('nazwa')}' — skrypt nie jest zaufany "
                                            "(uruchom go raz ręcznie)", "err")
            return
        plan = self._sched_plan(sc) or {}
        self._runner_current_idx = self.skrypty.index(sc) if sc in self.skrypty else None
        self._runner_mode_edit = False
        if hasattr(self, "_runner_entry_args"):
            self._runner_entry_args.delete(0, "end")
            self._runner_entry_args.insert(0, plan.get("args") or sc.get("runner_args") or "")
        self._runner_start()
        cur = getattr(self, "_runner_current", None)
        if isinstance(cur, dict):
            cur["plan"] = slot

    def _sched_run_now(self):
        sel = self._sched_tree.selection() if hasattr(self, "_sched_tree") else ()
        if not sel:
            return
        try:
            idx = int(sel[0])
            sc = self.skrypty[idx]
        except (ValueError, IndexError):
            return
        if not sc.get("zaufany"):
            if not self._runner_check_trust(sc, sc.get("kod", ""), sc.get("nazwa", "")):
                return
        if getattr(self, "_runner_busy", False):
            messagebox.showinfo(_tr("Harmonogram"), _tr("Wykonuje się już inny skrypt — spróbuj później."))
            return
        self._sched_fire(sc, "ręcznie")
        self._sched_fill()

    def _runner_apply_form_to_list(self):
        """Jeśli w formularzu jest kod nowego skryptu, podłącz go do runnera."""
        if getattr(self, "_runner_current_idx", None) is not None:
            return
        if not hasattr(self, "text_kod") or not self.text_kod.get("1.0", "end-1c").strip():
            return
        self._runner_mode_edit = True

    def _runner_run_selected(self):
        sel = self.tree.selection() if hasattr(self, "tree") else ()
        if not sel:
            messagebox.showinfo(_tr("Runner"), _tr("Zaznacz skrypt na liście."))
        else:
            self._runner_current_idx = int(sel[0])
            self._runner_mode_edit = False
        self._menu_pokaz_runner()
        self._runner_fill_list()
        self._runner_start()

    def _runner_check_trust(self, sc, kod, nazwa):
        """Pierwsze uruchomienie danego skryptu wymaga zatwierdzenia."""
        if sc is not None and sc.get("zaufany"):
            return True
        if not getattr(self, "_gui_ready", True):
            # praca programowa / testy — bez modalnego dialogu
            if sc is not None:
                sc["zaufany"] = True
            return True
        dlg = _popup(self)
        dlg.title("Uruchomienie kodu")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()
        self._trw(tk.Label(dlg, text=_tr("⚠  Uruchamiasz kod ze skryptu"), font=("Consolas", 11, "bold"),
                 bg=BG_DARK, fg="#e0a020"), "⚠  Uruchamiasz kod ze skryptu").pack(padx=16, pady=(14, 4))
        tk.Label(dlg, text=f"'{nazwa}'  —  kod zostanie wykonany lokalnie.",
                 font=FONT_UI, bg=BG_DARK, fg=FG_WHITE).pack(padx=16)
        self._trw(tk.Label(dlg, text=_tr("Uruchamiaj tylko kod z zaufanego źródła."),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), 'Uruchamiaj tylko kod z zaufanego źródła.').pack(padx=16, pady=(2, 10))
        box = tk.Text(dlg, font=("Consolas", 8), bg=BG_PANEL, fg=FG_WHITE, height=8, width=70)
        box.insert("1.0", (kod or "")[:1200])
        box.config(state="disabled", relief="flat")
        box.pack(padx=16, fill="x")
        var = tk.BooleanVar(value=False)
        self._trw(tk.Checkbutton(dlg, text=_tr("Nie pytaj ponownie dla tego skryptu"), variable=var,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK), "Nie pytaj ponownie dla tego skryptu").pack(padx=16, pady=6, anchor="w")
        res = {"ok": False}
        row = tk.Frame(dlg, bg=BG_DARK)
        row.pack(pady=(0, 14))

        def go():
            res["ok"] = True
            if var.get() and sc is not None:
                sc["zaufany"] = True
            dlg.destroy()

        tk.Button(row, text=_tr("▶ Uruchom"), font=FONT_UI, bg=BTN_OK, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=go).pack(side="left", padx=6)
        tk.Button(row, text=_tr("Anuluj"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=dlg.destroy).pack(side="left", padx=6)
        self.wait_window(dlg)
        return res["ok"]

    def _runner_start(self):
        import subprocess
        import shlex
        if getattr(self, "_runner_proc", None) is not None:
            if self._runner_proc.poll() is None:
                if not messagebox.askyesno(_tr("Runner"), _tr("Proces wciąż działa. Zatrzymać go?")):
                    return
                self._runner_stop()
        sc, kod, kat, nazwa = self._runner_target()
        if not kod:
            self._log_runner("Runner", "Brak skryptu do uruchomienia.")
            return
        if not self._runner_check_trust(sc, kod, nazwa):
            return
        if self._plugin_manager:
            self._plugin_manager.trigger_hook("before_script_run", sc, kat, nazwa)
        interpreter = self._runner_venv_var.get().strip() if hasattr(self, "_runner_venv_var") else ""
        interpreter = "" if not interpreter or interpreter in (_tr("(domyślny)"), "(domyślny)") else interpreter
        ok, info = runner_analyze(kod, kat, nazwa, interpreter)
        if not ok:
            self._log_runner("Analiza", info)
            if getattr(self, "_gui_ready", True):
                messagebox.showerror(_tr("Analiza kodu"), info)
            self._runner_current = {"sc": sc, "t0": datetime.datetime.now(), "info": info}
            self._runner_finished = False
            self._runner_finish(1)
            return
        args_raw = self._runner_entry_args.get().strip() if hasattr(self, "_runner_entry_args") else ""
        # zapamiętaj argumenty przy rekordzie (przetrwa import/eksport bazy)
        target_idx = getattr(self, "_runner_current_idx", None)
        rec = sc if isinstance(sc, dict) else None
        if rec is None and target_idx is not None and target_idx < len(self.skrypty):
            rec = self.skrypty[target_idx]
        if isinstance(rec, dict):
            rec["runner_args"] = args_raw
        try:
            args = shlex.split(args_raw, posix=False)
        except ValueError:
            args = args_raw.split()
        try:
            timeout = int(self._runner_entry_timeout.get() or 60)
        except ValueError:
            timeout = 60
        self._runner_workdir = tempfile.mkdtemp(prefix="bs_runner_")
        path = runner_save_temp(kod, kat, self._runner_workdir, interpreter)
        self._runner_current = {"sc": sc, "path": path, "kat": kat, "nazwa": nazwa,
                                "t0": datetime.datetime.now(), "info": info,
                                "workdir": self._runner_workdir,
                                "args": args_raw,
                                "checksum": kod_checksum(kod)}
        self._runner_finished = False
        self._runner_started = False
        new_console = (getattr(self, "_runner_console_var", None) is not None
                       and bool(self._runner_console_var.get())) or getattr(self, "_runner_force_new_console", False)
        self._runner_force_new_console = False
        try:
            if new_console:
                cmd_str = runner_shell_cmd(kat, path, args, interpreter)
                if not cmd_str:
                    raise ValueError(f"Brak obsługi interpretera dla kategorii {kat}.")
                flags = subprocess.CREATE_NEW_CONSOLE if sys.platform.startswith("win") else 0
                self._runner_started = True
                self._runner_proc = subprocess.Popen(cmd_str, cwd=self._runner_workdir,
                                                     env=self._runner_env(nazwa), creationflags=flags)
                self._log_runner(f"{nazwa} [{kat}]", "uruchomiono w nowej konsoli: " + cmd_str)
                # proces w osobnej konsoli nie jest czytany przez wątek — wynik z kodu wyjścia
                import threading
                threading.Thread(
                    target=lambda p=self._runner_proc: self._runner_queue.put(
                        f"__EXIT__{p.wait()}"),
                    daemon=True).start()
            elif kat == "SQL":
                self._runner_run_sql(kod)
                return
            else:
                cmd = runner_cmd(kat, path, args, interpreter)
                if not cmd:
                    raise ValueError(f"Brak obsługi interpretera dla kategorii {kat}.")
                self._runner_started = True
                self._runner_proc = subprocess.Popen(
                    cmd, cwd=self._runner_workdir, env=self._runner_env(nazwa),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="replace", bufsize=1)
                self._log_runner(f"{nazwa} [{kat}]", "START  " + " ".join(cmd))
                self._log_runner("Analiza", info)
                import threading
                threading.Thread(target=self._runner_pump, args=(self._runner_proc,), daemon=True).start()
        except FileNotFoundError as e:
            self._log_runner("Błąd", f"Nie znaleziono interpretera: {e}")
        except Exception as e:
            self._log_runner("Błąd", str(e))
        if not getattr(self, "_runner_started", False):
            # nic się nie uruchomiło — zamknij przebieg i pokaż błąd zamiast wisieć w trybie "działa"
            self._runner_finish(1)
            return
        self._runner_set_busy(True)
        self._runner_tick_start()
        if hasattr(self, "_runner_after_id") and self._runner_after_id:
            try:
                self.after_cancel(self._runner_after_id)
            except Exception:
                pass
        self._runner_watchdog(timeout, datetime.datetime.now())

    def _runner_pump(self, proc):
        """Wątek czytający wyjście — do UI przekazuje przez queue (nietykalny dla Tk)."""
        import queue
        if not hasattr(self, "_runner_queue"):
            self._runner_queue = queue.Queue()
        q = self._runner_queue
        try:
            for line in proc.stdout:
                q.put(line.rstrip("\n"))
        except Exception as e:
            q.put(f"[błąd odczytu wyjścia: {e}]")
        rc = proc.wait()
        q.put(f"__EXIT__{rc}")
        # bezpośrednie wywołania Tk z innego wątku są niebezpieczne —
        # pętla watchdog w wątku głównym opróżnia kolejkę.

    def _runner_drain(self):
        if not hasattr(self, "_runner_queue"):
            return
        q = self._runner_queue
        while True:
            try:
                line = q.get_nowait()
            except Exception:
                break
            if isinstance(line, str) and line.startswith("__EXIT__"):
                if not getattr(self, "_runner_finished", False):
                    self._runner_finish(int(line.replace("__EXIT__", "") or 0))
            else:
                self._log_runner("", line)

    def _runner_watchdog(self, timeout, t0):
        proc = getattr(self, "_runner_proc", None)
        self._runner_after_id = None
        if proc is None:
            return
        self._runner_drain()
        if getattr(self, "_runner_finished", False):
            return
        if proc.poll() is not None:
            # proces zakończony — dajmy wątkowi czytającemu chwilę na dopłynięcie
            # reszty wyjścia, potem zamknij przebieg (bez czekania na __EXIT__)
            self._runner_after_id = self.after(500, lambda: self._runner_exit_now(proc.returncode))
            return
        elapsed = (datetime.datetime.now() - t0).total_seconds()
        if timeout and elapsed > timeout:
            self._log_runner("Timeout", f"Przekroczono {timeout}s — zatrzymuję proces.")
            runner_kill_tree(proc)
            self._runner_finish(-9)
            return
        left = f"{max(0, int(timeout - elapsed))}s" if timeout else "∞"
        # zegar prowadzi osobny tick (co 200 ms); tu pilnujemy tylko limitu
        self._runner_after_id = self.after(300, lambda: self._runner_watchdog(timeout, t0))

    def _runner_exit_now(self, rc):
        """Domknięcie przebiegu, gdy proces już się zakończył."""
        self._runner_after_id = None
        self._runner_drain()
        if not getattr(self, "_runner_finished", False):
            self._runner_finish(rc if rc is not None else 0)

    def _runner_finish(self, rc):
        if getattr(self, "_runner_finished", False):
            return
        self._runner_finished = True
        cur = getattr(self, "_runner_current", None) or {}
        dt = (datetime.datetime.now() - cur.get("t0", datetime.datetime.now())).total_seconds()
        ok = (rc == 0)
        self._runner_set_busy(False)
        self._log_runner(_tr("Koniec"), _tr("kod wyjścia={rc}  czas={dt}s  {st}").format(
            rc=rc, dt=f"{dt:.2f}", st=_tr("OK") if ok else _tr("BŁĄD")),
                         "ok" if ok else "err")
        # Powiadomienie systemowe po zakończeniu zadania harmonogramu.
        if cur.get("plan"):
            self._notify_scheduled(cur.get("sc"), rc, dt)
        sc = cur.get("sc")
        if isinstance(sc, dict):
            sc["uruchomien"] = int(sc.get("uruchomien") or 0) + 1
            sc["ostatni_run"] = now_str()
            sc["ostatni_wynik"] = _tr("OK") if ok else _tr("błąd({rc})").format(rc=rc)
            sc["ostatni_czas_ms"] = int(dt * 1000)
            # historia: ostatnie 50 przebiegów per skrypt (najnowsze na końcu)
            hist = sc.setdefault("historia", [])
            entry = {
                "ts":       sc["ostatni_run"],
                "rc":       rc,
                "ms":       int(dt * 1000),
                "args":     cur.get("args", ""),
                "checksum": cur.get("checksum") or kod_checksum(sc.get("kod", "")),
                "out":      self._runner_out_tail() if ok else self._runner_out_tail(5),
            }
            hist.append(entry)
            if len(hist) > 50:
                del hist[:-50]
            if ok:
                # wzorzec do porównania „kod zmieniony od ostatniego OK”
                sc["ok_checksum"] = entry["checksum"]
                sc["ok_run"] = entry["ts"]
                sc["ok_kod"] = sc.get("kod", "")
            self._after_db_change()
            if hasattr(self, "_runner_hist_tree"):
                self._runner_hist_fill(sc)
            if hasattr(self, "_sched_fill"):
                self._sched_fill()
            if hasattr(self, "_runner_stat_vars"):
                # odśwież statystyki, tylko gdy pod-zakładka jest widoczna
                try:
                    if self._runner_panes["stats"].winfo_ismapped():
                        self._runner_stats_fill(sc)
                except Exception:
                    pass
        if self._runner_proc is not None and self._runner_proc.poll() is None:
            runner_kill_tree(self._runner_proc)
        self._runner_tick_stop()
        self._runner_check_drift(cur.get("sc"))
        # błędy: rozpoznaj linię w kodzie i odblokuj skok do niej
        if not ok:
            try:
                wyjscie = self._runner_out.get("1.0", "end-1c") if getattr(self, "_runner_out", None) else ""
            except Exception:
                wyjscie = ""
            info = runner_parse_error(wyjscie, cur.get("kat", "Python"))
            cur["error_info"] = info
            self._runner_current = cur
            if info and info.get("linia"):
                self._log_runner(
                    "Linia błędu",
                    f"linia {info['linia']} — {info.get('typ') or 'błąd'}: "
                    f"{(info.get('komunikat') or '').strip()}"[:160],
                    "err")
                self._runner_goto_error_button("normal")
            else:
                self._runner_goto_error_button("disabled")
        else:
            self._runner_goto_error_button("disabled")
            self._clear_errline()
        # posprzątaj katalog roboczy procesu
        wd = cur.get("workdir")
        if wd and os.path.isdir(wd):
            try:
                import shutil
                shutil.rmtree(wd, ignore_errors=True)
            except Exception:
                pass
        if self._plugin_manager:
            self._plugin_manager.trigger_hook(
                "after_script_run", cur.get("sc"), cur.get("kat"), cur.get("nazwa"), rc)

    def _runner_out_tail(self, n=8):
        """Ostatnie n linii wyjścia (zrzut do historii uruchomień)."""
        try:
            if not getattr(self, "_runner_out", None):
                return ""
            lines = self._runner_out.get("1.0", "end-1c").splitlines()
        except Exception:
            return ""
        return "\n".join(lines[-n:])[:4000]

    def _clear_errline(self):
        for w in (getattr(self, "text_kod", None), getattr(self, "edytor_text", None)):
            try:
                if w is not None:
                    w.tag_remove("errline", "1.0", "end")
            except Exception:
                pass

    def _runner_show_error_line(self):
        """Przechodzi do linii błędu w formularzu „Nowy skrypt” (po ostatnim przebiegu)."""
        cur = getattr(self, "_runner_current", None) or {}
        info = cur.get("error_info")
        if not info:
            text = self._runner_out.get("1.0", "end-1c") if getattr(self, "_runner_out", None) else ""
            info = runner_parse_error(text, cur.get("kat", "Python"))
        if not info or not info.get("linia"):
            messagebox.showinfo(_tr("Błąd"), _tr("Nie rozpoznano linii błędu w wyjściu."))
            return
        linia = max(1, int(info["linia"]))
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(0, self._show_sub_dodaj)
        w = getattr(self, "text_kod", None)
        if w is None:
            return
        w.tag_remove("errline", "1.0", "end")
        w.tag_add("errline", f"{linia}.0", f"{linia}.end")
        w.tag_configure("errline", background="#5a1f1f", foreground="#ffffff")
        w.mark_set("insert", f"{linia}.0")
        w.see(f"{linia}.0")
        w.focus_set()
        self._update_status()
        typ = info.get("typ") or "Błąd"
        kom = info.get("komunikat") or ""
        self._log_runner(_tr("Błąd w kodzie"), _tr("linia {ln}: {typ}: {kom}").format(
            ln=linia, typ=typ, kom=kom).strip(), "err")

    def _runner_goto_error_button(self, state="normal"):
        if hasattr(self, "_runner_btn_goto"):
            try:
                self._runner_btn_goto.config(state=state)
            except Exception:
                pass

    def _runner_check_drift(self, sc):
        """Ostrzega, gdy kod zmienił się od ostatniego udanego uruchomienia."""
        if not isinstance(sc, dict):
            return
        ok_cs = sc.get("ok_checksum")
        cur_cs = kod_checksum(sc.get("kod", ""))
        hist = sc.get("historia") or []
        last = hist[-1] if hist else {}
        if ok_cs and cur_cs != ok_cs:
            self._log_runner(
                _tr("Drift"),
                _tr("kod zmieniony od ostatniego udanego przebiegu ({ts}).").format(ts=sc.get("ok_run")),
                "err")
        # wpisy sprzed wprowadzenia pola 'checksum' nie mają skrótu — nie zgłaszamy fałszywego driftu
        last_cs = last.get("checksum")
        if last_cs and last_cs != cur_cs and last.get("rc") == 0:
            self._log_runner(_tr("Uwaga"), _tr("kod zmienił się od ostatniego udanego uruchomienia"), "inf")
        if sc.get("ok_kod") and sc.get("ok_kod") != sc.get("kod"):
            self._log_runner(_tr("Podpowiedź"), _tr("Możesz przywrócić kod z ostatniego OK "
                                            "(Historia przebiegów → ⏪ Przywróć kod)."))

    def _sched_fill(self):
        """Wypełnia tabelę planów harmonogramu."""
        if not hasattr(self, "_sched_tree"):
            return
        tree = self._sched_tree
        for row in tree.get_children():
            tree.delete(row)
        for i, sc in enumerate(self.skrypty):
            if sc.get("usuniety"):
                continue
            plan = self._sched_plan(sc)
            if not plan:
                continue
            kiedys = []
            if plan["co_min"]:
                kiedys.append(_tr("co {n} min").format(n=plan["co_min"]))
            if plan["o_godzinie"]:
                kiedys.append(_tr("o {hm}").format(hm=plan["o_godzinie"]))
            tree.insert("", "end", iid=str(i), values=(
                sc.get("nazwa", "?"),
                _tr("● aktywny") if plan["aktywny"] else _tr("○ wyłączony"),
                " + ".join(kiedys) or "—",
                plan["args"] or "—",
                sc.get("ostatni_run") or "-",
                sc.get("ostatni_wynik") or "-",
            ))
    def _sched_selected_script(self):
        sel = self._sched_tree.selection() if hasattr(self, "_sched_tree") else ()
        if not sel:
            messagebox.showinfo(_tr("Harmonogram"), _tr("Zaznacz skrypt w tabeli."))
            return None
        try:
            return self.skrypty[int(sel[0])]
        except (ValueError, IndexError):
            return None

    def _sched_edit(self):
        """Okno ustawień planu dla zaznaczonego skryptu."""
        sc = self._sched_selected_script()
        if sc is None:
            return
        plan = self._sched_plan(sc) or {"aktywny": False, "co_min": 0, "o_godzinie": "",
                                        "args": sc.get("runner_args") or ""}
        dlg = _popup(self)
        dlg.title(_tr("Harmonogram") + f" — {sc.get('nazwa')}")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()
        v_act = tk.BooleanVar(value=plan["aktywny"])
        self._trw(tk.Checkbutton(dlg, text=_tr("Plan aktywny"), variable=v_act, bg=BG_DARK, fg=FG_WHITE,
                       selectcolor=BG_INPUT, font=FONT_UI, activebackground=BG_DARK
                       ), "Plan aktywny").pack(anchor="w", padx=14, pady=(12, 4))
        row1 = tk.Frame(dlg, bg=BG_DARK)
        row1.pack(fill="x", padx=14)
        self._trw(tk.Label(row1, text=_tr("Co ile minut (0 = nie):"), font=FONT_UI, bg=BG_DARK,
                 fg=FG_GRAY), "Co ile minut (0 = nie):").pack(side="left")
        e_every = tk.Entry(row1, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE, width=8, relief="flat",
                           insertbackground=FG_WHITE, highlightthickness=1,
                           highlightbackground=BORDER_CLR)
        e_every.insert(0, str(plan["co_min"] or 0))
        e_every.pack(side="left", padx=6)
        row2 = tk.Frame(dlg, bg=BG_DARK)
        row2.pack(fill="x", padx=14, pady=4)
        self._trw(tk.Label(row2, text=_tr("O godzinie (HH:MM, puste = nie):"), font=FONT_UI, bg=BG_DARK,
                 fg=FG_GRAY), "O godzinie (HH:MM, puste = nie):").pack(side="left")
        e_hm = tk.Entry(row2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE, width=8, relief="flat",
                        insertbackground=FG_WHITE, highlightthickness=1,
                        highlightbackground=BORDER_CLR)
        e_hm.insert(0, plan["o_godzinie"])
        e_hm.pack(side="left", padx=6)
        row3 = tk.Frame(dlg, bg=BG_DARK)
        row3.pack(fill="x", padx=14, pady=4)
        tk.Label(row3, text=_tr("Argumenty:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        e_args = tk.Entry(row3, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                          insertbackground=FG_WHITE, highlightthickness=1,
                          highlightbackground=BORDER_CLR, width=34)
        e_args.insert(0, plan["args"] or "")
        e_args.pack(side="left", padx=6, fill="x", expand=True)

        root = self

        def save():
            hm = e_hm.get().strip()
            if hm:
                try:
                    hh, mm = hm.split(":")
                    if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                        raise ValueError
                    hm = f"{int(hh):02d}:{int(mm):02d}"
                except ValueError:
                    messagebox.showerror(_tr("Harmonogram"), _tr("Godzina w formacie HH:MM (00:00–23:59)."))
                    return
            try:
                every = max(0, int(e_every.get() or 0))
            except ValueError:
                messagebox.showerror(_tr("Harmonogram"), _tr("Interwał w minutach musi być liczbą."))
                return
            sc["harmonogram"] = {"aktywny": bool(v_act.get()), "co_min": every,
                                 "o_godzinie": hm, "args": e_args.get().strip()}
            root._rebuild_index()
            root._after_db_change()
            root._sched_fill()
            root._sched_badge()
            dlg.destroy()

        def remove():
            sc.pop("harmonogram", None)
            root._after_db_change()
            root._sched_fill()
            root._sched_badge()
            dlg.destroy()

        row = tk.Frame(dlg, bg=BG_DARK)
        row.pack(pady=12)
        self._trw(tk.Button(row, text=_tr("Zapisz plan"), font=FONT_UI, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  command=save), "Zapisz plan").pack(side="left", padx=4)
        self._trw(tk.Button(row, text=_tr("Usuń plan"), font=FONT_UI, bg=BTN_ERR, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  command=remove), 'Usuń plan').pack(side="left", padx=4)
        tk.Button(row, text=_tr("Anuluj"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  command=dlg.destroy).pack(side="left", padx=4)

    def _sched_set_plan(self, sc, every=0, hm="", args="", active=True):
        """Programowe ustawienie planu (CLI / testy)."""
        sc["harmonogram"] = {"aktywny": bool(active), "co_min": int(every or 0),
                             "o_godzinie": hm or "", "args": args or ""}
        self._after_db_change()
        self._sched_fill()
        self._sched_badge()

    def _sched_badge(self):
        """Oznaczenie stanu harmonogramu na przycisku zakładki Runner."""
        active = getattr(self, "_sched_running", False)
        for b in getattr(self, "_main_btns", []):
            try:
                if "Runner" in b.cget("text"):
                    b.config(text="⏰ Runner" if active else "▶ Runner")
            except Exception:
                pass

    # ── Powiadomienia systemowe (toast) ───────────────────────────────────────
    def _notify(self, title: str, message: str, level: str = "info") -> None:
        """Wysyła powiadomienie: natywne (plyer) albo toast w oknie aplikacji.

        Wyłączone, gdy ``notify_enabled`` w konfiguracji jest wyłączone.
        """
        if str(self._cfg.get("notify_enabled", "1")) != "1":
            return
        if _NOTIFY_AVAILABLE and _notify_available() and _notify_send_native(title, message):
            self._log_runner("Powiadomienie", f"{title}: {message}", level)
            return
        self._toast(title, message, level)

    def _toast(self, title: str, message: str, level: str = "info") -> None:
        """Lekki toast nakładany na prawy dolny róg okna (fallback bez plyer)."""
        accent = {"ok": BTN_OK_HOVER, "err": BTN_ERR_HOVER,
                  "warn": "#e0c040"}.get(level, ACCENT_BLUE)
        if getattr(self, "_shutting_down", False):
            return
        try:
            t = _popup(self)
            t.withdraw()
            t.overrideredirect(True)
            try:
                t.attributes("-topmost", True)
            except Exception:
                pass
            outer = tk.Frame(t, bg=accent)
            outer.pack(fill="both", expand=True, padx=1, pady=1)
            card = tk.Frame(outer, bg=BG_PANEL)
            card.pack(fill="both", expand=True)
            tk.Label(card, text=title, font=FONT_BOLD, bg=BG_PANEL, fg=accent,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(card, text=message, font=FONT_UI, bg=BG_PANEL, fg=FG_WHITE,
                     anchor="w", justify="left", wraplength=280
                     ).pack(fill="x", padx=12, pady=(2, 10))
            t.update_idletasks()
            w = max(240, min(360, t.winfo_reqwidth()))
            h = t.winfo_reqheight()
            x = self.winfo_rootx() + self.winfo_width() - w - 18
            y = self.winfo_rooty() + self.winfo_height() - h - 18
            t.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
            t.bind("<Button-1>", lambda _e, wnd=t: self._toast_close(wnd))
            self._toasts = getattr(self, "_toasts", [])
            self._toasts.append(t)
            t.deiconify()
            t.after(6000, lambda wnd=t: self._toast_close(wnd))
        except Exception as e:
            logging.warning(f"Nie udało się pokazać toastu: {e}")

    def _toast_close(self, window) -> None:
        """Zamyka toast i usuwa go z listy aktywnych."""
        try:
            if window is not None and window.winfo_exists():
                window.destroy()
        except Exception:
            pass
        try:
            if window in getattr(self, "_toasts", []):
                self._toasts.remove(window)
        except Exception:
            pass

    def _notify_scheduled(self, sc, rc: int, dt: float) -> None:
        """Powiadamia o zakończeniu zadania uruchomionego przez harmonogram."""
        nazwa = (sc or {}).get("nazwa") or _t("notify_title")
        if rc == 0:
            self._notify(_t("notify_title"),
                         _t("notify_done_ok", nazwa=nazwa, czas=f"{dt:.1f}"), "ok")
        else:
            self._notify(_t("notify_title"),
                         _t("notify_done_err", nazwa=nazwa, rc=rc, czas=f"{dt:.1f}"), "err")

    def _runner_build_scheduler(self, frame):
        """Pod-zakładka Harmonogram: tabela planów + sterowanie."""
        bar = tk.Frame(frame, bg=BG_DARK)
        bar.pack(fill="x", pady=(6, 4))
        self._trw(tk.Label(bar, text=_tr("Plany uruchomień"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), 'Plany uruchomień').pack(side="left")
        self._sched_lbl_state = self._trw(tk.Label(bar, text=_tr("○ harmonogram zatrzymany"),
                                         font=FONT_UI, bg=BG_DARK, fg=FG_GRAY),
                                         "○ harmonogram zatrzymany")
        self._sched_lbl_state.pack(side="left", padx=12)
        self._trw(tk.Button(bar, text=_tr("▶ Uruchom teraz"), font=FONT_UI, bg=BTN_OK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sched_run_now), "▶ Uruchom teraz").pack(side="right", padx=3)
        self._trw(tk.Button(bar, text=_tr("↻ Odśwież"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                  command=lambda: (self._sched_fill(), self._sched_badge())), '↻ Odśwież').pack(side="right", padx=3)

        cols = ("skrypt", "stan", "kiedy", "argumenty", "ostatni", "wynik")
        col_labels = {"skrypt": "Skrypt", "stan": "Stan", "kiedy": "Kiedy",
                      "argumenty": "Argumenty", "ostatni": "Ostatni przebieg", "wynik": "Wynik"}
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (170, 100, 150, 140, 140, 90)):
            self._trh(tree, c, col_labels[c])
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True)
        tree.bind("<Double-1>", lambda e: self._sched_edit())
        self._sched_tree = tree

        row = tk.Frame(frame, bg=BG_DARK)
        row.pack(fill="x", pady=(6, 0))
        self._trw(tk.Button(row, text=_tr("⚙ Edytuj plan"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sched_edit), "⚙ Edytuj plan").pack(side="left", padx=3)
        self._trw(tk.Button(row, text=_tr("+ Dodaj plan dla bieżącego skryptu"), font=FONT_UI, bg=BTN_DARK,
                  fg=FG_WHITE, relief="flat", padx=10, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER, command=self._sched_add_current
                  ), '+ Dodaj plan dla bieżącego skryptu').pack(side="left", padx=3)
        self._sched_btn_on = self._trw(tk.Button(row, text=_tr("▶ Włącz harmonogram"), font=FONT_UI,
                                       bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=10,
                                       pady=3, cursor="hand2", activebackground=BTN_HOVER,
                                       command=self._sched_toggle), '▶ Włącz harmonogram')
        self._sched_btn_on.pack(side="right", padx=3)

    def _sched_add_current(self):
        """Tworzy domyślny plan (co 60 min) dla skryptu wybranego w Runnerze."""
        idx = getattr(self, "_runner_current_idx", None)
        if idx is None or idx >= len(self.skrypty):
            messagebox.showinfo(_tr("Harmonogram"), _tr("Najpierw wybierz skrypt w zakładce Sterowanie."))
            return
        sc = self.skrypty[idx]
        self._sched_set_plan(sc, every=60, args=sc.get("runner_args") or "", active=False)
        try:
            self._sched_tree.selection_set(str(idx))
        except Exception:
            pass
        self._sched_edit()

    def _sched_toggle(self):
        if getattr(self, "_sched_running", False):
            self._sched_stop()
        else:
            self._sched_start()
        self._sched_fill()
        self._sched_sync_ui()

    def _runner_hist_fill(self, sc=None):
        """Wypełnia tabelę historii przebiegów wybranego skryptu."""
        if not hasattr(self, "_runner_hist_tree"):
            return
        tree = self._runner_hist_tree
        for row in tree.get_children():
            tree.delete(row)
        if sc is None:
            idx = getattr(self, "_runner_current_idx", None)
            sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if not isinstance(sc, dict):
            return
        for i, h in enumerate(reversed(sc.get("historia") or [])):
            tree.insert("", "end", iid=str(i), values=(
                h.get("ts", ""),
                "OK" if h.get("rc") == 0 else _tr("błąd({rc})").format(rc=h.get("rc")),
                f"{h.get('ms', 0)} ms",
                h.get("args") or "—",
                (h.get("out") or "").splitlines()[-1][:60] if h.get("out") else "",
            ))

    def _runner_hist_show(self, event=None):
        """Podgląd pełnego wyjścia z wybranego wpisu historii."""
        sel = self._runner_hist_tree.selection() if hasattr(self, "_runner_hist_tree") else ()
        if not sel:
            return
        idx = getattr(self, "_runner_current_idx", None)
        sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if not isinstance(sc, dict):
            return
        hist = list(reversed(sc.get("historia") or []))
        try:
            h = hist[int(sel[0])]
        except (IndexError, ValueError, TypeError):
            return
        self._runner_clear()
        self._log_runner(h.get("ts", ""), f"kod={h.get('rc')}  {h.get('ms')} ms  args={h.get('args') or '-'}",
                         "ok" if h.get("rc") == 0 else "err")
        for line in (h.get("out") or "").splitlines():
            self._log_runner("", line)

    def _runner_hist_restore_args(self):
        """Przywraca argumenty z wybranego wpisu historii do pola Argumenty."""
        sel = self._runner_hist_tree.selection() if hasattr(self, "_runner_hist_tree") else ()
        idx = getattr(self, "_runner_current_idx", None)
        sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if not sel or not isinstance(sc, dict):
            return
        hist = list(reversed(sc.get("historia") or []))
        try:
            args = hist[int(sel[0])].get("args") or ""
        except (IndexError, ValueError, TypeError):
            return
        self._runner_entry_args.delete(0, "end")
        self._runner_entry_args.insert(0, args)
        self._log_runner("Historia", f"przywrócono argumenty: {args or '(brak)'}")

    def _runner_restore_ok_code(self):
        """Przywraca kod z ostatniego udanego uruchomienia (gdy bieżący się nie uruchamia)."""
        idx = getattr(self, "_runner_current_idx", None)
        sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if not isinstance(sc, dict):
            return
        target = None
        for h in reversed(sc.get("historia") or []):
            if h.get("rc") == 0 and h.get("checksum"):
                target = h
                break
        if not target:
            messagebox.showinfo(_tr("Historia"), _tr("Brak udanego uruchomienia w historii."))
            return
        if not messagebox.askyesno(
                _tr("Przywróć kod"), _tr(f"Przywrócić kod z przebiegu {target.get('ts')}?\n"
                "Zmiany wprowadzone później zostaną nadpisane.")):
            return
        # odtworzenie nie jest możliwe bez kopii kodu — zapisujemy snapshot przy każdym OK
        snap = sc.get("ok_kod")
        if not snap:
            messagebox.showinfo(
                _tr("Historia"),
                _tr("Ten skrypt nie ma zapisanej kopii kodu z udanego przebiegu.\n"
                "Kolejne udane uruchomienia będą ją już zapisywać."))
        return
        if hasattr(self, "text_kod"):
            self.text_kod.delete("1.0", "end")
            self.text_kod.insert("1.0", snap)
            self.var_kat.set(sc.get("kategoria", "Python"))
            self._highlighter.highlight(self.text_kod, self.var_kat.get())
        sc["kod"] = snap
        sc["checksum"] = kod_checksum(snap)
        sc["zmieniony"] = now_str()
        self._rebuild_index()
        self._after_db_change()
        self._log_runner("Przywrócono", f"kod z {target.get('ts')}", "ok")

    def _runner_run_sql(self, kod):
        """SQL uruchamiane na aktywnym połączeniu z zakładki Baza Danych."""
        conn = getattr(self, "_db_conn", None)
        online = getattr(self, "_db_online", False)
        if not online or conn is None:
            self._log_runner("SQL", "Brak aktywnego połączenia — podłącz bazę w zakładce Baza Danych.")
            messagebox.showwarning(_tr("SQL"), _tr("Najpierw połącz się z bazą w zakładce 'Baza Danych'."))
            self._runner_set_busy(False)
            return
        try:
            cur = conn.cursor()
            start = datetime.datetime.now()
            cur.executescript(kod) if hasattr(cur, "executescript") else cur.execute(kod)
            rows = []
            desc = cur.description or []
            if desc:
                rows = cur.fetchmany(200)
                self._log_runner("SQL", " | ".join(d[0] for d in desc))
                for r in rows:
                    self._log_runner("", " | ".join(str(v) for v in r))
            conn.commit()
            dt = (datetime.datetime.now() - start).total_seconds()
            self._log_runner("SQL", f"OK  {len(rows)} wierszy  {dt*1000:.0f} ms", "ok")
            self._runner_current = {"sc": self._runner_current.get("sc"), "t0": start}
            self._runner_finish(0)
        except Exception as e:
            self._log_runner("SQL", f"Błąd: {e}", "err")
            self._runner_set_busy(False)

    def _runner_edit_env(self):
        """Dialog edycji zmiennych środowiskowych per skrypt (pole runner_env)."""
        idx = getattr(self, "_runner_current_idx", None)
        sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if not isinstance(sc, dict):
            messagebox.showinfo(_tr("ENV"), _tr("Najpierw wybierz skrypt."))
            return
        dlg = _popup(self)
        dlg.title(_tr("ENV") + " — " + sc.get("nazwa", ""))
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.geometry("520x300")
        self._trw(tk.Label(dlg, text=_tr("Jedna zmienna na linię: KLUCZ=wartość (linie z # są ignorowane)"),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY),
                 "Jedna zmienna na linię: KLUCZ=wartość (linie z # są ignorowane)").pack(
                     anchor="w", padx=10, pady=(10, 4))
        txt = tk.Text(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                      insertbackground=FG_WHITE, relief="flat",
                      highlightthickness=1, highlightbackground=BORDER_CLR,
                      highlightcolor=ACCENT_BLUE, height=10)
        txt.pack(fill="both", expand=True, padx=10)
        txt.insert("1.0", str(sc.get("runner_env") or ""))
        row = tk.Frame(dlg, bg=BG_DARK)
        row.pack(fill="x", pady=8)

        def zapisz():
            sc["runner_env"] = txt.get("1.0", "end-1c").strip()
            self._after_db_change()
            self._log_runner("ENV", f"zapisano zmienne dla {sc.get('nazwa', '')}", "ok")
            dlg.destroy()

        self._trw(tk.Button(row, text=_tr("💾 Zapisz"), font=FONT_UI, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2", activebackground=BTN_HOVER,
                  command=zapisz), "💾 Zapisz").pack(side="right", padx=(0, 10))
        self._trw(tk.Button(row, text=_tr("Zamknij"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2", activebackground=BTN_HOVER,
                  command=dlg.destroy), "Zamknij").pack(side="right")

    def _runner_stop(self):
        proc = getattr(self, "_runner_proc", None)
        if proc is None or proc.poll() is not None:
            self._log_runner("Runner", "Brak działającego procesu.")
            return
        runner_kill_tree(proc)
        self._log_runner("Stop", "Proces zatrzymany przez użytkownika.", "err")
        # zamknij stdin, żeby wątek pump nie wisiał na otwartym pipe
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        self._runner_finish(-1)

    def _runner_send_stdin(self):
        proc = getattr(self, "_runner_proc", None)
        if proc is None or proc.poll() is not None or proc.stdin is None:
            if hasattr(self, "_runner_entry_stdin"):
                self._log_runner("stdin", "Brak działającego procesu — nie można wysłać.", "err")
            return
        line = self._runner_entry_stdin.get()
        if not line:
            return
        try:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            self._log_runner(">", line)
        except (OSError, ValueError):
            self._log_runner("stdin", "Proces już nie przyjmuje danych (strumień zamknięty).", "err")
            return
        self._runner_entry_stdin.delete(0, "end")

    def _runner_set_busy(self, busy):
        self._runner_busy = busy
        for w in ([getattr(self, "_runner_btn_run", None), getattr(self, "_runner_btn_run_nc", None)]
                  + [getattr(self, "_runner_btn_run2", None)]):
            if w is not None:
                try:
                    w.config(state="disabled" if busy else "normal")
                except Exception:
                    pass
        if hasattr(self, "_runner_btn_stop"):
            self._runner_btn_stop.config(state="normal" if busy else "disabled")
        # wskaźnik przebiegu w nagłówku zakładki i w pasku kliknięcia
        if hasattr(self, "_runner_spinner_lbl"):
            self._runner_spinner_lbl.config(
                text="⏳ działa…" if busy else "", fg="#e0c040")
        for i, b in enumerate(getattr(self, "_main_btns", [])):
            try:
                if "Runner" in b.cget("text"):
                    b.config(text="⏳ Runner" if busy else "▶ Runner")
            except Exception:
                pass
        # F9 / Shift+F9 / Ctrl+F9 wyłączone podczas przebiegu — Ctrl+F5 (stop) działa zawsze
        if busy:
            self.unbind_all("<F9>")
            self.unbind_all("<Shift-F9>")
            self.unbind_all("<Control-F9>")
        else:
            self.bind_all("<F9>", lambda e: self._runner_run_form())
            self.bind_all("<Shift-F9>", lambda e: self._runner_run_form(save_first=False))
            self.bind_all("<Control-F9>", lambda e: self._runner_run_form(new_console=True))
        # Ctrl+F5 — zatrzymanie — pozostaje aktywne także w trakcie przebiegu
        self.bind_all("<Control-F5>", lambda e: self._runner_stop())

    def _log_runner(self, tag, text, level=""):
        if not getattr(self, "_runner_out", None):
            return
        for w in (self._runner_out, getattr(self, "_runner_out_sub", None)):
            if w is None:
                continue
            w.config(state="normal")
            if tag:
                w.insert("end", f"[{tag}] ", "tag")
            w.insert("end", (text or "") + "\n", level or "")
            if getattr(self, "_runner_follow", True):
                w.see("end")
            w.config(state="disabled")

    def _runner_mirror_content(self, widget):
        """Przepisuje całe wyjście do drugiego panelu (zakładka Skrypty → Runner)."""
        if not hasattr(self, "_runner_out"):
            return
        dst = widget
        src = self._runner_out if widget is getattr(self, "_runner_out_sub", None) else self._runner_out_sub
        if src is None:
            return
        try:
            content = src.get("1.0", "end-1c")
            dst.config(state="normal")
            dst.delete("1.0", "end")
            dst.insert("1.0", content)
            dst.see("end")
            dst.config(state="disabled")
        except Exception:
            pass

    def _runner_clear(self):
        for w in (getattr(self, "_runner_out", None), getattr(self, "_runner_out_sub", None)):
            if w is not None:
                w.config(state="normal")
                w.delete("1.0", "end")
                w.config(state="disabled")

    def _runner_export_out(self):
        if not hasattr(self, "_runner_out"):
            return
        path = filedialog.asksaveasfilename(defaultextension=".log",
                                            initialfile="runner_output.log",
                                            filetypes=[("Log", "*.log"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._runner_out.get("1.0", "end-1c"))
            messagebox.showinfo(_tr("Runner"), f"Zapisano:\n{path}")

    def _runner_export_bat(self):
        """Zapisuje skrypt jako gotowy plik do uruchomienia poza aplikacją."""
        sc, kod, kat, nazwa = self._runner_target()
        if not kod:
            messagebox.showinfo(_tr("Runner"), _tr("Najpierw wybierz skrypt."))
            return
        ext = RUNNER_EXT.get(kat, ".bat")
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=re.sub(r"[^\w.-]+", "_", nazwa or "skrypt") + ext,
            filetypes=[(f"Plik {ext}", f"*{ext}"), ("Wszystkie", "*.*")])
        if not path:
            return
        base = os.path.splitext(path)[0]
        try:
            if kat == "JAR":
                with open(path, "wb") as fh:
                    fh.write(jar_bytes(kod))
            elif kat == "Java":
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(kod)
                main = runner_java_class(kod)
                pkg = runner_java_package(kod)
                fq = f"{pkg}.{main}" if pkg else main
                interp = ""
                if hasattr(self, "_runner_venv_var"):
                    interp = self._runner_venv_var.get().strip()
                    if interp in ("(domyślny)", _tr("(domyślny)")):
                        interp = ""
                lines = runner_java_launcher_lines(
                    os.path.basename(path), fq,
                    _java_tool("javac", interp), _java_tool("java", interp))
                lines.append("pause")
                bat_path = base + ".bat"
                with open(bat_path, "w", encoding="utf-8", newline="\r\n") as fh:
                    fh.write("\r\n".join(lines) + "\r\n")
                messagebox.showinfo(
                    _tr("Runner"), f"Zapisano źródło:\n{path}\noraz launcher:\n{bat_path}")
                return
            elif kat == "VBScript":
                if any(ord(ch) > 127 for ch in kod):
                    with open(path, "wb") as fh:            # UTF-16 LE + BOM
                        fh.write(kod.encode("utf-16"))
                else:
                    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
                        fh.write(kod)
            elif kat == "Batch":
                with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
                    fh.write(kod)
            elif ext == ".ps1":
                with open(path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
                    fh.write(kod)
            elif kat in ("WSF", "HTA", "HTML", "CSS", "JSON", "Markdown"):
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(kod)
            else:
                payload = base + ".src" + RUNNER_EXT.get(kat, ".txt")
                with open(payload, "w", encoding="utf-8", newline="\n") as pf:
                    pf.write(kod)
                payload_name = os.path.basename(payload)
                if kat == "Bash":
                    line = f'bash "$(dirname "$0")/{payload_name}" %*'
                    with open(path, "w", encoding="utf-8", newline="\n") as fh:
                        fh.write("#!/usr/bin/env bash\n" + line + "\n")
                else:
                    line = f'%~dp0{payload_name} %*'
                    if kat == "Python":
                        py = self._cfg.get("interpreter") or sys.executable
                        line = f'"{py}" "%~dp0{payload_name}" %*'
                    elif kat == "JavaScript":
                        line = f'node "%~dp0{payload_name}" %*'
                    elif kat == "Ruby":
                        line = f'ruby "%~dp0{payload_name}" %*'
                    elif kat == "Perl":
                        line = f'perl "%~dp0{payload_name}" %*'
                    elif kat == "PHP":
                        line = f'php "%~dp0{payload_name}" %*'
                    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
                        fh.write("@echo off\r\n" + line + "\r\npause\r\n")
            messagebox.showinfo(_tr("Runner"), f"Zapisano:\n{path}")
        except Exception as e:
            messagebox.showerror(_tr("Błąd"), str(e))

    def _runner_load_form(self):
        """Wczytuje kod z formularza 'Nowy skrypt' do runnera."""
        self._runner_mode_edit = True
        nm = (self.entry_nazwa.get().strip() if hasattr(self, "entry_nazwa") else "") or _tr("(bez nazwy)")
        kat = self.var_kat.get() if hasattr(self, "var_kat") else ""
        label = f"{_tr('Formularz:')} {nm}  [{kat}]"
        if hasattr(self, "_runner_lbl_target"):
            self._runner_lbl_target.config(text=label)
        if hasattr(self, "_runner_lbl_target2"):
            self._runner_lbl_target2.config(text=label)

    def _runner_fill_list(self, force=False):
        if not hasattr(self, "_runner_list"):
            return
        # odbudowa tylko przy realnej zmianie zbioru — inaczej zaznaczenie znika przy każdym zapisie
        signature = tuple((s.get("id"), int(s.get("uruchomien") or 0)) for s in self.skrypty)
        if not force and signature == getattr(self, "_runner_list_sig", None):
            return
        self._runner_list_sig = signature
        self._runner_list.delete(0, "end")
        for s in self.skrypty:
            if s.get("usuniety"):
                continue
            runs = int(s.get("uruchomien") or 0)
            self._runner_list.insert("end", f"{s.get('nazwa','?')}  [{s.get('kategoria','?')}]" +
                                             (f"  ×{runs}" if runs else ""))
        cur = getattr(self, "_runner_current_idx", None)
        if cur is not None and 0 <= cur < len(self.skrypty):
            try:
                self._runner_list.selection_clear(0, "end")
                self._runner_list.selection_set(cur)
                self._runner_list.see(cur)
            except Exception:
                pass

    def _runner_pick(self, event=None):
        sel = self._runner_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.skrypty):
            return
        self._runner_current_idx = idx
        self._runner_mode_edit = False
        sc = self.skrypty[idx]
        # argumenty zapamiętane dla tego skryptu
        if hasattr(self, "_runner_entry_args"):
            self._runner_entry_args.delete(0, "end")
            self._runner_entry_args.insert(0, sc.get("runner_args") or "")
        self._runner_lbl_target.config(text=f"{sc.get('nazwa')}  [{sc.get('kategoria')}]")
        if hasattr(self, "_runner_lbl_target2"):
            self._runner_lbl_target2.config(text=f"{sc.get('nazwa')}  [{sc.get('kategoria')}]")
        self._runner_hist_fill(sc)
        self._runner_out.config(state="normal")
        self._runner_out.delete("1.0", "end")
        self._runner_out.insert("end", f"// {sc.get('nazwa')} [{sc.get('kategoria')}]\n", "tag")
        self._runner_out.insert("end", (sc.get("kod") or "")[:3000], "")
        self._runner_out.config(state="disabled")
        self._runner_mirror_content(getattr(self, "_runner_out_sub", None))

    def _runner_double_click(self, event):
        row = self._runner_list.nearest(event.y)
        bounds = self._runner_list.bbox(row)
        if not bounds or not bounds[1] <= event.y < bounds[1] + bounds[3]:
            return "break"
        self._runner_list.selection_clear(0, "end")
        self._runner_list.selection_set(row)
        self._runner_pick()
        self._runner_start()
        return "break"

    def _runner_tick(self):
        """Żywy zegar przebiegu — aktualizowany co 200 ms przez cały czas działania procesu."""
        self._runner_tick_id = None
        cur = getattr(self, "_runner_current", None) or {}
        t0 = cur.get("t0")
        if not t0 or getattr(self, "_runner_finished", True):
            return
        elapsed = (datetime.datetime.now() - t0).total_seconds()
        try:
            timeout = int(self._runner_entry_timeout.get() or 0)
        except (ValueError, TypeError, AttributeError):
            timeout = 0
        txt = f"● działa  {elapsed:5.1f}s"
        if timeout:
            txt += f" / {timeout}s"
        if hasattr(self, "_runner_lbl_time"):
            self._runner_lbl_time.config(text=txt, fg="#e0c040")
        self._runner_tick_id = self.after(200, self._runner_tick)

    def _runner_tick_start(self):
        if getattr(self, "_runner_tick_id", None):
            try:
                self.after_cancel(self._runner_tick_id)
            except Exception:
                pass
        self._runner_tick()

    def _runner_tick_stop(self):
        if getattr(self, "_runner_tick_id", None):
            try:
                self.after_cancel(self._runner_tick_id)
            except Exception:
                pass
        self._runner_tick_id = None
        if hasattr(self, "_runner_lbl_time"):
            self._runner_lbl_time.config(text=_tr("● gotowy"), fg="#6dde84")

    # ── Wyszukiwanie w wyjściu runnera ───────────────────────────────────────
    def _runner_find_focus(self):
        """Ctrl+Shift+F / menu Run — przechodzi do pola szukania w wyjściu."""
        if not getattr(self, "_runner_current", None):
            self._menu_pokaz_runner()
        if hasattr(self, "_runner_entry_find"):
            try:
                self._runner_entry_find.focus_set()
                self._runner_entry_find.select_range(0, "end")
            except Exception:
                pass

    def _runner_find(self, event=None):
        """Ctrl+F w panelu wyjścia — zaznacza kolejne wystąpienie frazy."""
        if not hasattr(self, "_runner_out"):
            return "break"
        phrase = self._runner_find_var.get().strip() if hasattr(self, "_runner_find_var") else ""
        if not phrase:
            if hasattr(self, "_runner_entry_find"):
                self._runner_entry_find.focus_set()
            return "break"
        w = self._runner_out
        start = w.index("insert")
        pos = w.search(phrase, start, nocase=True, stopindex="end")
        if not pos:
            pos = w.search(phrase, "1.0", nocase=True, stopindex="end")
        if pos:
            end = f"{pos}+{len(phrase)}c"
            w.tag_remove("find_hl", "1.0", "end")
            w.tag_add("find_hl", pos, end)
            w.tag_configure("find_hl", background="#5a4a1a", foreground=FG_WHITE)
            w.mark_set("insert", end)
            w.see(pos)
        if hasattr(self, "_runner_lbl_find"):
            self._runner_lbl_find.config(text="znaleziono" if pos else "brak",
                                         fg="#6dde84" if pos else "#e05c5c")
        return "break"

    def _runner_toggle_follow(self):
        """Włącz/wyłącz automatyczne przewijanie do końca wyjścia."""
        self._runner_follow = not getattr(self, "_runner_follow", True)
        if hasattr(self, "_runner_btn_follow"):
            self._runner_btn_follow.config(
                bg=BTN_OK if self._runner_follow else BTN_DARK,
                text="📌 auto-scroll: ON" if self._runner_follow else "📌 auto-scroll: OFF")
        if self._runner_follow:
            for w in (getattr(self, "_runner_out", None), getattr(self, "_runner_out_sub", None)):
                if w is not None:
                    w.see("end")

    def _menu_ustawienia_runner(self):
        dlg = _popup(self)
        dlg.title("Runner — ustawienia")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()
        self._trw(tk.Label(dlg, text=_tr("Interpreter (pusty = domyślny)"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), 'Interpreter (pusty = domyślny)').pack(anchor="w", padx=14, pady=(12, 0))
        e_int = tk.Entry(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat", width=60)
        e_int.insert(0, self._cfg.get("interpreter", ""))
        e_int.pack(padx=14, pady=(2, 8))
        self._trw(tk.Label(dlg, text=_tr("Timeout [s] (0 = brak)"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Timeout [s] (0 = brak)").pack(anchor="w", padx=14)
        e_to = tk.Entry(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                        insertbackground=FG_WHITE, relief="flat", width=10)
        e_to.insert(0, self._cfg.get("timeout", "60"))
        e_to.pack(anchor="w", padx=14, pady=(2, 8))
        v_auto = tk.BooleanVar(value=str(self._cfg.get("autosave", "1")) == "1")
        self._trw(tk.Checkbutton(dlg, text=_tr("Autosave bazy po zmianach"), variable=v_auto,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK), "Autosave bazy po zmianach").pack(anchor="w", padx=14, pady=2)
        v_con = tk.BooleanVar(value=str(self._cfg.get("runner_console", "0")) == "1")
        self._trw(tk.Checkbutton(dlg, text=_tr("Domyślnie uruchamiaj w nowej konsoli"), variable=v_con,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK), 'Domyślnie uruchamiaj w nowej konsoli').pack(anchor="w", padx=14, pady=2)
        self._trw(tk.Label(dlg, text=_tr("Kopie zapasowe (.bak)"), font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY), "Kopie zapasowe (.bak)").pack(anchor="w", padx=14, pady=(8, 0))
        e_bak = tk.Entry(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat", width=10)
        e_bak.insert(0, self._cfg.get("backup_count", "3"))
        e_bak.pack(anchor="w", padx=14, pady=(2, 8))

        def save():
            self._cfg["interpreter"] = e_int.get().strip()
            self._cfg["timeout"] = e_to.get().strip() or "60"
            self._cfg["autosave"] = "1" if v_auto.get() else "0"
            self._cfg["runner_console"] = "1" if v_con.get() else "0"
            self._cfg["backup_count"] = e_bak.get().strip() or "3"
            cfg_save(self._cfg)
            if hasattr(self, "_runner_entry_timeout"):
                self._runner_entry_timeout.delete(0, "end")
                self._runner_entry_timeout.insert(0, self._cfg["timeout"])
            dlg.destroy()

        row = tk.Frame(dlg, bg=BG_DARK)
        row.pack(pady=12)
        self._trw(tk.Button(row, text=_tr("Zapisz"), font=FONT_UI, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=save), "Zapisz").pack(side="left", padx=4)
        tk.Button(row, text=_tr("Anuluj"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=dlg.destroy).pack(side="left", padx=4)

    def _build_runner_frame(self):
        self._runner_current_idx = None
        self._runner_mode_edit = False
        self._runner_proc = None
        self._runner_busy = False
        outer = self._runner_outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["runner"] = outer

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("▶ Runner — uruchamianie skryptów"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), '▶ Runner — uruchamianie skryptów').pack(side="left")
        self._runner_lbl_time = self._trw(tk.Label(hdr, text=_tr("● gotowy"), font=FONT_UI,
                                         bg=BG_PANEL, fg="#6dde84"), "● gotowy")
        self._runner_lbl_time.pack(side="right", padx=8)
        self._runner_spinner_lbl = tk.Label(hdr, text="", font=FONT_UI,
                                            bg=BG_PANEL, fg="#e0c040")
        self._runner_spinner_lbl.pack(side="right", padx=4)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(outer, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        self._runner_build_body(body)

        # Wspólny panel wyjścia — w zakładce Skrypty → Runner oraz w zakładce Runner
        self._runner_main_frame = tk.Frame(self.sub_content, bg=BG_DARK)
        # Zarejestruj w sub_frames, żeby _sel_sub() chował go przy zmianie
        # pod-zakładki (inaczej panel zostaje widoczny na każdej pod-zakładce).
        self.sub_frames["runner"] = self._runner_main_frame
        inner = tk.Frame(self._runner_main_frame, bg=BG_DARK)
        inner.pack(fill="both", expand=True, padx=10, pady=8)
        bar = tk.Frame(inner, bg=BG_DARK)
        bar.pack(fill="x")
        self._runner_lbl_target2 = self._trw(tk.Label(bar, text=_tr("kod z formularza / wybrany skrypt"),
                                            font=FONT_BOLD, bg=BG_DARK, fg="#e0c040", anchor="w"), "kod z formularza / wybrany skrypt")
        self._runner_lbl_target2.pack(side="left")
        tk.Button(bar, text=_tr("▶ Uruchom (F9)"), font=FONT_UI, bg=BTN_OK, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_start).pack(side="right", padx=3)
        self._trw(tk.Button(bar, text=_tr("■ Stop"), font=FONT_UI, bg=BTN_ERR, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_stop), "■ Stop").pack(side="right", padx=3)
        cons = tk.Frame(inner, bg=BG_DARK)
        cons.pack(fill="both", expand=True, pady=(6, 0))
        sb = tk.Scrollbar(cons, orient="vertical")
        sb.pack(side="right", fill="y")
        text = tk.Text(cons, font=("Consolas", 9), bg="#14161f", fg="#c8d0f0",
                       relief="flat", wrap="none", yscrollcommand=sb.set,
                       highlightthickness=0)
        text.pack(side="left", fill="both", expand=True)
        sb.config(command=text.yview)
        text.tag_configure("tag", foreground="#e0c040")
        text.tag_configure("ok", foreground="#6dde84")
        text.tag_configure("err", foreground="#e05c5c")
        text.config(state="disabled")
        text.bind("<KeyRelease>", lambda e: self._runner_mirror_content(text))
        self._runner_out_sub = text

    def _runner_build_body(self, body):
        workdir = body
        # pod-zakładki: sterowanie / historia przebiegów
        nb = tk.Frame(workdir, bg=BG_DARK)
        nb.pack(fill="x")
        content = tk.Frame(workdir, bg=BG_DARK)
        content.pack(fill="both", expand=True)
        panes = {"run": tk.Frame(content, bg=BG_DARK),
                 "hist": tk.Frame(content, bg=BG_DARK),
                 "plan": tk.Frame(content, bg=BG_DARK),
                 "stats": tk.Frame(content, bg=BG_DARK)}
        self._runner_panes = panes
        self._runner_hist_frame = panes["hist"]
        btns = {}

        def show(key):
            for k, f in panes.items():
                f.pack_forget()
            panes[key].pack(fill="both", expand=True)
            self._update_minsize()
            for k, b in btns.items():
                b.configure(bg=BG_SUBTAB_ACT if k == key else BG_SUBTAB_INACT,
                            fg=FG_WHITE if k == key else FG_GRAY)
            if key == "hist":
                self._runner_hist_fill()
            elif key == "plan":
                self._sched_fill()
            elif key == "stats":
                self._runner_stats_fill()

        for key, label in (("run", "Sterowanie"), ("hist", "Historia przebiegów"),
                           ("plan", "Harmonogram"), ("stats", "Statystyki")):
            b = self._trw(tk.Button(nb, text=_tr(label), font=FONT_UI, bg=BG_SUBTAB_INACT, fg=FG_GRAY,
                          relief="flat", padx=12, pady=3, cursor="hand2", bd=0,
                          highlightthickness=0, command=lambda k=key: show(k)), label)
            b.pack(side="left")
            btns[key] = b
        self._runner_show_pane = show
        show("run")
        body = panes["run"]
        self._runner_build_history(panes["hist"])
        self._runner_build_scheduler(panes["plan"])
        self._runner_build_stats(panes["stats"])

        # Pasek sterowania procesu i panel wyjścia nie zależą od pod-zakładki —
        # budujemy je raz, pod treścią (żadnych duplikatów widżetów).
        # Kolejność pakowania: opcje (top) → panel wyjścia (bottom).
        # Wyjście dostaje expand=True, więc jest pakowane jako OSTATNIE —
        # dzięki temu opcje (interpreter/argumenty/przyciski) są zawsze
        # widoczne u góry, a nie schowane poniżej widocznej wysokości okna.
        top = tk.Frame(workdir, bg=BG_DARK)
        top.pack(fill="x", before=workdir.winfo_children()[0] if workdir.winfo_children() else workdir)

        # lewa — lista skryptów
        left = tk.Frame(top, bg=BG_PANEL, highlightthickness=1,
                        highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="both", padx=(0, 8))
        tk.Label(left, text=_tr("Skrypty"), font=FONT_BOLD, bg=BG_PANEL,
                 fg=FG_WHITE).pack(anchor="w", padx=8, pady=(6, 2))
        self._runner_list = tk.Listbox(left, font=FONT_UI, bg=BG_INPUT, fg=FG_WHITE,
                                       selectbackground=BG_ROW_SEL, relief="flat",
                                       height=12, width=40, activestyle="none")
        self._runner_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._runner_list.bind("<<ListboxSelect>>", self._runner_pick)
        self._runner_list.bind("<Double-Button-1>", self._runner_double_click)
        self._runner_fill_list(force=True)
        if hasattr(self, "_sched_tree"):
            self._sched_fill()

        # prawa — opcje uruchomienia
        right = tk.Frame(top, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._runner_lbl_target = self._trw(tk.Label(right, text=_tr("wybierz skrypt lub kod z formularza"),
                                           font=FONT_BOLD, bg=BG_DARK, fg="#e0c040",
                                           anchor="w"), "wybierz skrypt lub kod z formularza")
        self._runner_lbl_target.pack(fill="x")
        row1 = tk.Frame(right, bg=BG_DARK)
        row1.pack(fill="x", pady=(6, 2))
        self._trw(tk.Label(row1, text=_tr("Interpreter:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "Interpreter:").pack(side="left")
        self._runner_venv_var = tk.StringVar(value=self._cfg.get("interpreter") or _tr("(domyślny)"))
        self._runner_venv_cb = ttk.Combobox(row1, textvariable=self._runner_venv_var,
                                            font=FONT_UI, style="Dark.TCombobox", width=36)
        initial_interpreters = [_tr("(domyślny)"), sys.executable]
        configured_interpreter = self._cfg.get("interpreter") or ""
        if configured_interpreter and configured_interpreter not in initial_interpreters:
            initial_interpreters.insert(1, configured_interpreter)
        self._runner_venv_cb["values"] = initial_interpreters
        self._runner_venv_cb.pack(side="left", padx=6)
        self.after(250, self._runner_load_interpreters_async)
        self._trw(tk.Button(row1, text=_tr("…"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=6, pady=2, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_pick_interpreter), "…").pack(side="left")

        self._runner_interp2 = tk.Entry(right, font=FONT_MONO, bg=BG_INPUT, fg=FG_GRAY,
                                        relief="flat", highlightthickness=1,
                                        highlightbackground=BORDER_CLR, width=40)

        row2 = tk.Frame(right, bg=BG_DARK)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text=_tr("Argumenty:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._runner_entry_args = tk.Entry(row2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                           insertbackground=FG_WHITE, relief="flat",
                                           highlightthickness=1, highlightbackground=BORDER_CLR)
        self._runner_entry_args.pack(side="left", fill="x", expand=True, padx=6)

        row3 = tk.Frame(right, bg=BG_DARK)
        row3.pack(fill="x", pady=2)
        self._trw(tk.Label(row3, text=_tr("Timeout [s]:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "Timeout [s]:").pack(side="left")
        self._runner_entry_timeout = tk.Entry(row3, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                              insertbackground=FG_WHITE, relief="flat",
                                              highlightthickness=1, highlightbackground=BORDER_CLR,
                                              width=8)
        self._runner_entry_timeout.insert(0, self._cfg.get("timeout", "60"))
        self._runner_entry_timeout.pack(side="left", padx=6)
        self._runner_console_var = tk.BooleanVar(value=str(self._cfg.get("runner_console", "0")) == "1")
        self._trw(tk.Checkbutton(row3, text=_tr("Nowa konsola"), variable=self._runner_console_var,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK), "Nowa konsola").pack(side="left", padx=10)

        row4 = tk.Frame(right, bg=BG_DARK)
        row4.pack(fill="x", pady=(8, 4))

        def rbtn(text, color, cmd, attr=None, state="normal"):
            b = self._trw(tk.Button(row4, text=_tr(text), font=FONT_UI, bg=color, fg=FG_WHITE,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                          command=cmd, state=state), text)
            b.pack(side="left", padx=3)
            if attr:
                setattr(self, attr, b)

        rbtn("▶ Uruchom  (F9)", BTN_OK, self._runner_start, "_runner_btn_run")
        rbtn("▶ W nowej konsoli", BTN_DARK, lambda: self._runner_start_new_console(), "_runner_btn_run_nc")
        rbtn("📍 Przejdź do błędu", BTN_ERR, self._runner_show_error_line, "_runner_btn_goto", "disabled")
        rbtn("■ Zatrzymaj", BTN_ERR, self._runner_stop, "_runner_btn_stop", "disabled")
        rbtn("✕ Wyczyść", BTN_DARK, self._runner_clear)
        rbtn("💾 Eksport wyjścia", BTN_DARK, self._runner_export_out)
        rbtn("📄 .bat/.ps1", BTN_DARK, self._runner_export_bat)

        # ── zmienne środowiskowe per skrypt (ENV) ───────────────────────────
        row_env = tk.Frame(right, bg=BG_DARK)
        row_env.pack(fill="x", pady=(4, 0))
        self._trw(tk.Label(row_env, text=_tr("ENV (KLUCZ=wartość, linia po linii):"),
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY),
                 "ENV (KLUCZ=wartość, linia po linii):"
                 ).pack(side="left", anchor="n")
        self._runner_btn_env = self._trw(tk.Button(
            row_env, text=_tr("⚙ Edytuj ENV"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
            relief="flat", padx=8, pady=2, cursor="hand2", activebackground=BTN_HOVER,
            command=self._runner_edit_env), "⚙ Edytuj ENV").pack(side="left", padx=6)

        row5 = tk.Frame(right, bg=BG_DARK)
        row5.pack(fill="x", pady=(0, 4))
        self._trw(tk.Label(row5, text=_tr("stdin:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY), "stdin:").pack(side="left")
        self._runner_entry_stdin = tk.Entry(row5, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                            insertbackground=FG_WHITE, relief="flat",
                                            highlightthickness=1, highlightbackground=BORDER_CLR)
        self._runner_entry_stdin.pack(side="left", fill="x", expand=True, padx=6)
        self._runner_entry_stdin.bind("<Return>", lambda e: self._runner_send_stdin())
        self._trw(tk.Button(row5, text=_tr("Wyślij"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=8, pady=2, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_send_stdin), 'Wyślij').pack(side="left")

        # panel wyjścia pakowany na końcu — reszta już siedzi w layout (patrz wyżej)
        self._runner_build_bottom(workdir)

    def _runner_build_bottom(self, workdir):
        cons_hdr = tk.Frame(workdir, bg=BG_DARK)
        cons_hdr.pack(fill="x", pady=(8, 2))
        self._trw(tk.Label(cons_hdr, text=_tr("Wyjście"), font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_WHITE, anchor="w"), 'Wyjście').pack(side="left")
        self._runner_follow = True
        self._runner_btn_follow = self._trw(tk.Button(cons_hdr, text=_tr("📌 auto-scroll: ON"), font=FONT_UI,
                                            bg=BTN_OK, fg=FG_WHITE, relief="flat",
                                            padx=8, pady=1, cursor="hand2",
                                            activebackground=BTN_HOVER,
                                            command=self._runner_toggle_follow), "📌 auto-scroll: ON")
        self._runner_btn_follow.pack(side="right")
        self._runner_lbl_find = tk.Label(cons_hdr, text="", font=("Consolas", 8),
                                         bg=BG_DARK, fg=FG_GRAY)
        self._runner_lbl_find.pack(side="right", padx=8)
        self._runner_find_var = tk.StringVar(value="")
        self._runner_entry_find = tk.Entry(cons_hdr, textvariable=self._runner_find_var,
                                           font=FONT_UI, bg=BG_INPUT, fg=FG_WHITE,
                                           insertbackground=FG_WHITE, relief="flat",
                                           highlightthickness=1, highlightbackground=BORDER_CLR,
                                           width=18)
        self._runner_entry_find.pack(side="right", padx=(6, 2))
        self._runner_entry_find.bind("<Return>", self._runner_find)
        self._trw(tk.Button(cons_hdr, text=_tr("🔍"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=6, pady=1, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_find), "🔍").pack(side="right")
        cons = tk.Frame(workdir, bg=BG_DARK)
        cons.pack(fill="both", expand=True)
        sb = tk.Scrollbar(cons, orient="vertical")
        sb.pack(side="right", fill="y")
        self._runner_out = tk.Text(cons, font=("Consolas", 9), bg="#14161f", fg="#c8d0f0",
                                   insertbackground=FG_WHITE, relief="flat", wrap="none",
                                   yscrollcommand=sb.set, highlightthickness=0)
        self._runner_out.pack(side="left", fill="both", expand=True)
        sb.config(command=self._runner_out.yview)
        self._runner_out.tag_configure("tag", foreground="#e0c040")
        self._runner_out.tag_configure("ok", foreground="#6dde84")
        self._runner_out.tag_configure("err", foreground="#e05c5c")
        self._runner_out.config(state="disabled")

    def _runner_build_stats(self, frame):
        """Pod-zakładka Statystyki: podsumowanie przebiegów + benchmark + raport."""
        bar = tk.Frame(frame, bg=BG_DARK)
        bar.pack(fill="x", pady=(6, 4))
        self._trw(tk.Label(bar, text=_tr("Statystyki uruchomień wybranego skryptu"),
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE),
                 'Statystyki uruchomień wybranego skryptu').pack(side="left")
        self._trw(tk.Button(bar, text=_tr("💾 Eksportuj raport…"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_stats_export), '💾 Eksportuj raport…').pack(side="right", padx=3)

        # ── kafelki podsumowania ────────────────────────────────────────────
        tiles = tk.Frame(frame, bg=BG_DARK)
        tiles.pack(fill="x", pady=(0, 6))
        self._runner_stat_vars = {}
        for i, (klucz, domysl) in enumerate((
                ("Przebiegi", "0"), ("OK", "0"), ("Błędy", "0"),
                ("Skuteczność", "—"), ("Średni czas", "—"),
                ("Najlepszy", "—"), ("Najgorszy", "—"))):
            cell = tk.Frame(tiles, bg=BG_PANEL, highlightthickness=1,
                            highlightbackground=BORDER_CLR, padx=10, pady=6)
            cell.grid(row=0, column=i, sticky="nsew", padx=3)
            tiles.columnconfigure(i, weight=1)
            self._trw(tk.Label(cell, text=_tr(klucz), font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY),
                     klucz).pack(anchor="w")
            var = tk.StringVar(value=domysl)
            tk.Label(cell, textvariable=var, font=FONT_BOLD, bg=BG_PANEL,
                     fg=FG_WHITE).pack(anchor="w")
            self._runner_stat_vars[klucz] = var

        # ── benchmark ───────────────────────────────────────────────────────
        bench = tk.LabelFrame(frame, text=_tr("⏱ Benchmark — porównanie przebiegów"),
                              font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE)
        bench.pack(fill="both", expand=True, pady=(0, 6))
        brow = tk.Frame(bench, bg=BG_DARK)
        brow.pack(fill="x", pady=(4, 2))
        self._trw(tk.Label(brow, text=_tr("Przebieg A:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY),
                 "Przebieg A:").pack(side="left")
        self._runner_bench_a = ttk.Combobox(brow, state="readonly", width=12,
                                            font=FONT_MONO, style="Dark.TCombobox")
        self._runner_bench_a.pack(side="left", padx=(4, 10))
        self._trw(tk.Label(brow, text=_tr("Przebieg B:"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY),
                 "Przebieg B:").pack(side="left")
        self._runner_bench_b = ttk.Combobox(brow, state="readonly", width=12,
                                            font=FONT_MONO, style="Dark.TCombobox")
        self._runner_bench_b.pack(side="left", padx=4)
        self._trw(tk.Button(brow, text=_tr("⚖ Porównaj"), font=FONT_UI, bg=BTN_ACCENT, fg=FG_WHITE,
                  relief="flat", padx=10, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_bench_compare), "⚖ Porównaj").pack(side="left", padx=10)
        self._runner_bench_lbl = self._trw(tk.Label(bench, text=_tr("Wybierz dwa przebiegi z listy historii."),
                                          font=FONT_MONO, bg=BG_DARK, fg=FG_GRAY, justify="left",
                                          anchor="w"), "Wybierz dwa przebiegi z listy historii.")
        self._runner_bench_lbl.pack(fill="x", padx=8, pady=(2, 8))

    def _runner_stats_records(self, sc=None):
        """Zwraca (rekord, lista wpisów historii) dla wybranego skryptu."""
        if sc is None:
            idx = getattr(self, "_runner_current_idx", None)
            sc = self.skrypty[idx] if idx is not None and idx < len(self.skrypty) else None
        if not isinstance(sc, dict):
            return None, []
        return sc, list(sc.get("historia") or [])

    def _runner_stats_fill(self, sc=None):
        """Odświeża kafelki statystyk i listy wyboru benchmarku."""
        if not hasattr(self, "_runner_stat_vars"):
            return
        sc, hist = self._runner_stats_records(sc)
        v = self._runner_stat_vars
        if not hist:
            for var in v.values():
                var.set("—" if var.get() not in ("0",) else var.get())
            v["Przebiegi"].set("0")
            v["OK"].set("0")
            v["Błędy"].set("0")
            v["Skuteczność"].set("—")
            v["Średni czas"].set("—")
            v["Najlepszy"].set("—")
            v["Najgorszy"].set("—")
        else:
            czasy = [int(h.get("ms", 0)) for h in hist]
            ok_n = sum(1 for h in hist if h.get("rc") == 0)
            err_n = len(hist) - ok_n
            avg = sum(czasy) / len(czasy)
            best_i = czasy.index(min(czasy))
            worst_i = czasy.index(max(czasy))
            v["Przebiegi"].set(str(len(hist)))
            v["OK"].set(str(ok_n))
            v["Błędy"].set(str(err_n))
            v["Skuteczność"].set(f"{100 * ok_n / len(hist):.0f}%")
            v["Średni czas"].set(f"{avg:.0f} ms")
            v["Najlepszy"].set(f"{czasy[best_i]} ms")
            v["Najgorszy"].set(f"{czasy[worst_i]} ms")
        # wybory benchmarku — najnowsze 20 przebiegów (najstarszy = A)
        choices = [f"#{i + 1}  {h.get('ts', '')[:16]}  {h.get('ms', 0)} ms"
                   for i, h in enumerate(hist[-20:])]
        offset = max(0, len(hist) - 20)
        for combo in (getattr(self, "_runner_bench_a", None),
                      getattr(self, "_runner_bench_b", None)):
            if combo is not None:
                combo["values"] = choices
                combo.current(0) if choices else combo.set("")
        self._runner_bench_offset = offset
        self._runner_bench_hist = hist

    def _runner_bench_pick(self, which):
        """Zwraca (numer_przebiegu_w_historii, wpis) dla wyboru A/B."""
        combo = getattr(self, f"_runner_bench_{which}", None)
        hist = getattr(self, "_runner_bench_hist", None) or []
        offset = getattr(self, "_runner_bench_offset", 0)
        if combo is None or not hist:
            return None, None
        try:
            i = int(combo.current())
        except (TypeError, ValueError):
            return None, None
        pos = offset + i
        if 0 <= pos < len(hist):
            return pos, hist[pos]
        return None, None

    def _runner_bench_compare(self):
        """Porównuje czasy dwóch wybranych przebiegów (A vs B)."""
        pa, ha = self._runner_bench_pick("a")
        pb, hb = self._runner_bench_pick("b")
        if ha is None or hb is None or pa == pb:
            self._runner_bench_lbl.config(text=_tr("Wybierz dwa różne przebiegi z listy historii."),
                                          fg="#e0c040")
            return
        ta, tb = int(ha.get("ms", 0)), int(hb.get("ms", 0))
        d = tb - ta
        if ta > 0:
            pct = 100.0 * d / ta
            kier = _tr("B wolniejszy (+{p:.1f}%)") if d > 0 else _tr("B szybszy ({p:.1f}%)")
            txt = (f"A: {ta} ms  ·  B: {tb} ms  ·  Δ {d:+d} ms  ·  "
                   + kier.format(p=abs(pct)))
        else:
            txt = f"A: {ta} ms  ·  B: {tb} ms  ·  Δ {d:+d} ms"
        self._runner_bench_lbl.config(text=txt,
                                      fg="#6dde84" if d < 0 else ("#e05c5c" if d > 0 else FG_GRAY))

    def _runner_stats_export(self):
        """Eksportuje raport statystyk wybranego skryptu do pliku tekstowego."""
        sc, hist = self._runner_stats_records()
        if sc is None:
            messagebox.showinfo(_tr("Statystyki"), _tr("Najpierw wybierz skrypt."))
            return
        nazwa = sc.get("nazwa", "skrypt")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"raport_{nazwa}.txt",
            filetypes=(("Plik tekstowy", "*.txt"), ("Wszystkie", "*.*")))
        if not path:
            return
        czasy = [int(h.get("ms", 0)) for h in hist]
        ok_n = sum(1 for h in hist if h.get("rc") == 0)
        lines = [
            f"Raport uruchomień — {nazwa}",
            f"Wygenerowano: {now_str()}",
            "=" * 56,
            f"Przebiegi: {len(hist)}  OK: {ok_n}  Błędy: {len(hist) - ok_n}",
        ]
        if czasy:
            avg = sum(czasy) / len(czasy)
            lines += [
                f"Skuteczność: {100 * ok_n / len(hist):.0f}%",
                f"Średni czas: {avg:.0f} ms",
                f"Najlepszy: {min(czasy)} ms  Najgorszy: {max(czasy)} ms",
                "-" * 56,
                "Przebiegi (od najnowszego):",
            ]
            for i, h in enumerate(reversed(hist)):
                wynik = "OK" if h.get("rc") == 0 else f"błąd({h.get('rc')})"
                lines.append(f"  {h.get('ts', '')}  {wynik:12}  {h.get('ms', 0)} ms"
                             f"  args={h.get('args') or '-'}")
        try:
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            messagebox.showerror(_tr("Statystyki"), str(e))
            return
        self._log_runner("Statystyki", f"raport zapisany: {path}", "ok")

    def _runner_build_history(self, frame):
        """Tabela historii przebiegów wybranego skryptu + akcje."""
        bar = tk.Frame(frame, bg=BG_DARK)
        bar.pack(fill="x", pady=(6, 4))
        self._trw(tk.Label(bar, text=_tr("Historia uruchomień (max 50 na skrypt)"), font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE), 'Historia uruchomień (max 50 na skrypt)').pack(side="left")
        self._trw(tk.Button(bar, text=_tr("↺ Przywróć argumenty"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_hist_restore_args), '↺ Przywróć argumenty').pack(side="right", padx=3)
        self._trw(tk.Button(bar, text=_tr("⏪ Przywróć kod z ostatniego OK"), font=FONT_UI, bg="#4a3a10",
                  fg=FG_WHITE, relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground="#6a5418",
                  command=self._runner_restore_ok_code), '⏪ Przywróć kod z ostatniego OK').pack(side="right", padx=3)

        cols = ("ts", "wynik", "czas", "argumenty", "ostatnia linia")
        col_labels = {"ts": "Data", "wynik": "Wynik", "czas": "Czas [s]",
                      "argumenty": "Argumenty", "ostatnia linia": "Ostatnia linia wyjścia"}
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (130, 90, 80, 160, 280)):
            self._trh(tree, c, col_labels[c])
            tree.column(c, width=w, anchor="w")
        sb = tk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", self._runner_hist_show)
        tree.bind("<Double-1>", self._runner_hist_restore_args)
        self._runner_hist_tree = tree

    def _runner_start_new_console(self):
        self._runner_force_new_console = True
        self._runner_start()

    def _runner_interpreter_choices(self):
        """Lista interpreterów: domyślny + wykryte venv/python."""
        vals = [_tr("(domyślny)")]
        cur = self._cfg.get("interpreter") if getattr(self, "_cfg", None) else ""
        if cur:
            vals.append(cur)
        try:
            for d in os.listdir(APP_DIR):
                for cand in (os.path.join(APP_DIR, d, "Scripts", "python.exe"),
                             os.path.join(APP_DIR, d, "bin", "python")):
                    if os.path.exists(cand):
                        vals.append(cand)
        except OSError:
            pass
        vals.append(sys.executable)
        # interpretery innych języków (jeśli są w PATH)
        import shutil as _sh
        extra = ["node", "pwsh", "java", "ruby", "perl", "php"]
        if os.name == "nt":
            extra += ["cscript.exe", "wscript.exe", "cmd.exe", "mshta.exe"]
        for exe in extra:
            found = _sh.which(exe)
            if found and found not in vals:
                vals.append(found)
        jh = os.environ.get("JAVA_HOME")
        if jh:
            cand = os.path.join(jh, "bin", "java.exe" if os.name == "nt" else "java")
            if os.path.exists(cand) and cand not in vals:
                vals.append(cand)
        gb = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Git", "bin", "bash.exe")
        if os.path.exists(gb) and gb not in vals:
            vals.append(gb)
        # usuń duplikaty zachowując kolejność
        seen = set()
        return [v for v in vals if not (v in seen or seen.add(v))]

    def _runner_load_interpreters_async(self):
        """Discover PATH interpreters after the window is visible, off the UI thread."""
        if getattr(self, "_runner_interpreters_loading", False):
            return
        self._runner_interpreters_loading = True

        def finish(values):
            self._runner_interpreters_loading = False
            if not self._runner_venv_cb.winfo_exists():
                return
            selected = self._runner_venv_var.get()
            if selected and selected not in values:
                values.insert(1, selected)
            self._runner_venv_cb["values"] = values
            self._runner_venv_var.set(selected)

        def worker():
            try:
                values = self._runner_interpreter_choices()
            except Exception:
                logging.exception("Interpreter discovery failed")
                values = [_tr("(domyślny)"), sys.executable]
            self._safe_after(0, lambda result=values: finish(result))

        import threading
        threading.Thread(target=worker, daemon=True, name="runner-interpreter-discovery").start()

    def _runner_pick_interpreter(self):
        path = filedialog.askopenfilename(
            title=_tr("Wybierz interpreter"),
            filetypes=[("Programy (*.exe)", "*.exe"),
                       ("Python", "python*.exe python*"),
                       ("Java", "java.exe java"),
                       ("Ruby", "ruby.exe ruby"),
                       ("Perl", "perl.exe perl"),
                       ("PHP", "php.exe php"),
                       ("Wszystkie pliki", "*.*")])
        if path:
            self._runner_venv_var.set(path)

    # ── dolny pasek ───────────────────────────────────────────────────────────
    def _build_bottom_bar(self, parent):
        bar = tk.Frame(parent, bg=BG_DARK, pady=6)
        bar.pack(fill="x", side="bottom", padx=8)

        def btn(master, text, color=BTN_DARK, cmd=None):
            self._trw(tk.Button(master, text=_tr(text), font=FONT_UI,
                      bg=color, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                      cursor="hand2", activebackground=BTN_HOVER,
                      activeforeground=FG_WHITE, command=cmd
                      ), text).pack(side="left", padx=3)

        btn(bar, "💾 Zapisz",          color=BTN_ACCENT, cmd=self._zapisz)
        btn(bar, "▶ Uruchom (F9)",     color=BTN_OK,     cmd=self._runner_run_form)
        btn(bar, "🗑 Wyczyść",                             cmd=self._wyczysc)
        btn(bar, "📋 Kopiuj Kod",                          cmd=self._kopiuj_kod)
        btn(bar, "📂 Wczytaj plik",                        cmd=self._wczytaj_plik)

        # ── Pasek stanu: linia / kolumna / znaki / słowa ──────────────────────
        self._status_lbl = self._trw(tk.Label(bar, text=_tr("Ln 1  Col 1  |  0 zn  0 słów"),
                                    font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY,
                                    anchor="w", padx=10), "Ln 1  Col 1  |  0 zn  0 słów")
        self._status_lbl.pack(side="left", fill="x", expand=True)

        right = tk.Frame(bar, bg=BG_DARK)
        right.pack(side="right")
        btn(right, "⬆ Eksportuj (.txt)", cmd=lambda: self._eksportuj("txt"))
        btn(right, "⬆ Eksportuj (.ext)", cmd=lambda: self._eksportuj("ext"))

        # Podłącz odświeżanie paska stanu do edytora kodu
        self.after(400, self._attach_status_bar)

    def _attach_status_bar(self):
        """Podłącz odświeżanie paska stanu do text_kod."""
        if hasattr(self, "text_kod"):
            self.text_kod.bind("<KeyRelease>",  self._update_status, add="+")
            self.text_kod.bind("<ButtonRelease>", self._update_status, add="+")

    def _update_status(self, event=None):
        """Odśwież etykietę paska stanu: linia, kolumna, znaki, słowa."""
        if not hasattr(self, "_status_lbl"):
            return
        try:
            index = self.text_kod.index("insert")
            ln, col = index.split(".")
            code = self.text_kod.get("1.0", "end-1c")
            znaki = len(code)
            slowa = len(code.split()) if code.strip() else 0
            self._status_lbl.config(
                text=f"Ln {ln}  Col {int(col)+1}  |  {znaki:,} zn  {slowa:,} słów"
            )
        except Exception:
            pass

    # ── akcje ─────────────────────────────────────────────────────────────────
    def _zapisz(self, quiet=False):
        nazwa = self.entry_nazwa.get().strip()
        if not nazwa:
            if not quiet:
                messagebox.showwarning(_tr("Brak nazwy"), _tr("Podaj nazwę skryptu!"))
            self.entry_nazwa.config(highlightbackground="#e05c5c",
                                    highlightcolor="#e05c5c")
            return False
        opis = self.text_opis.get("1.0", "end-1c")
        if opis == "Opis skryptu…":
            opis = ""
        kod = self.text_kod.get("1.0", "end-1c")
        now = now_str()
        ts = now
        data = {
            "nazwa":     nazwa,
            "kategoria": self.var_kat.get(),
            "tagi":      self.entry_tagi.get().strip(),
            "opis":      opis,
            "kod":       kod,
            "zmieniony": ts,
            "checksum":  kod_checksum(kod),
        }
        # aktualizuj jeśli istnieje (po nazwie), dodaj jeśli nowy
        target = None
        for i, s in enumerate(self.skrypty):
            if s.get("nazwa") == nazwa and not s.get("usuniety"):
                target = i
                break
        if target is None and getattr(self, "_edytor_current_idx", None) is not None:
            # ten sam skrypt może być zmieniany z edytora (indeks może się różnić)
            try:
                cand = self.skrypty[self._edytor_current_idx]
                if cand.get("nazwa") == nazwa and not cand.get("usuniety"):
                    target = self._edytor_current_idx
            except IndexError:
                pass
        if target is not None:
            old = self.skrypty[target]
            if (old.get("kod") or "") != kod:
                sc_add_version(old, autor="zapis formularza")
            data["id"] = old.get("id") or uuid.uuid4().hex
            data["utworzony"] = old.get("utworzony") or now
            for k in ("uruchomien", "ostatni_run", "ostatni_wynik",
                      "ostatni_czas_ms", "zaufany", "historia",
                      "ok_checksum", "ok_run", "ok_kod", "runner_args",
                      "harmonogram", "pliki"):
                if k in old:
                    data[k] = old[k]
            data["wersje"] = old.get("wersje") or []
            self.skrypty[target] = sc_normalize(data)
            self._edytor_current_idx = target
            akcja = f"Skrypt '{nazwa}' zaktualizowany."
        else:
            self.skrypty.append(sc_normalize(data))
            self._edytor_current_idx = len(self.skrypty) - 1
            akcja = f"Skrypt '{nazwa}' zapisany."
        self._editing_nazwa = nazwa
        self.entry_nazwa.config(highlightbackground=BORDER_CLR,
                                highlightcolor=ACCENT_BLUE)
        self._rebuild_index()
        self._update_count()
        self._refresh_lista()
        self._highlighter.highlight(self.text_kod, self.var_kat.get())
        self.save_db(silent=True)
        self._set_db_status(f"✓ {now[-8:]}  {len(self.skrypty)} skryptów")
        if not quiet:
            messagebox.showinfo(_tr("Zapisano"), akcja)
        return True

    def _wyczysc(self):
        self.entry_nazwa.delete(0, "end")
        self.entry_nazwa.config(highlightbackground=BORDER_CLR,
                                highlightcolor=ACCENT_BLUE)
        self._editing_nazwa = None
        self.entry_tagi.delete(0, "end")
        self.text_opis.delete("1.0", "end")
        self.text_opis.insert("1.0", "Opis skryptu…")
        self.text_opis.config(fg=FG_GRAY)
        self.text_kod.delete("1.0", "end")
        self.var_kat.set("Python")
        self._update_line_nums()
        if hasattr(self, "_status_lbl"):
            self._status_lbl.config(text=_tr("Ln 1  Col 1  |  0 zn  0 słów")
)
    def _kopiuj_kod(self):
        self.clipboard_clear()
        self.clipboard_append(self.text_kod.get("1.0", "end-1c"))
        messagebox.showinfo(_tr("Skopiowano"), _tr("Kod skopiowany do schowka."))

    def _wczytaj_plik(self):
        path = filedialog.askopenfilename(
            filetypes=[("Skrypty", "*.py *.sh *.ps1 *.js *.bat *.cmd "
                                   "*.vbs *.java *.c *.h *.cpp *.cc *.cxx *.c++ "
                                   "*.hpp *.hh *.hxx "
                                   "*.rb *.pl *.php *.wsf *.hta "
                                   "*.html *.htm *.css *.json *.md *.sql *.txt"),
                       ("Wszystkie pliki", "*.*")])
        if path:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.text_kod.delete("1.0", "end")
            self.text_kod.insert("1.0", content)
            self.entry_nazwa.delete(0, "end")
            self.entry_nazwa.insert(0, os.path.basename(path))
            self._update_line_nums()
            self._update_status()
            # Wywnioskuj kategorię z rozszerzenia
            ext = os.path.splitext(path)[1].lower()
            if ext in self._EXT_KAT:
                self.var_kat.set(self._EXT_KAT[ext])
            # Podświetl składnię
            self._highlighter.highlight(self.text_kod, self.var_kat.get())

    # Rozszerzenie pliku → kategoria skryptu
    _EXT_KAT = EXT_KAT
    _SKRYPT_EXT = tuple(_EXT_KAT.keys()) + (".txt",)
    # Rozszerzenia plików binarnych przechowywanych jako base64
    _BIN_EXT = BIN_EXT

    def _importuj_plik_skryptu(self):
        """Importuje pojedynczy plik skryptu jako nowy wpis w bazie."""
        path = filedialog.askopenfilename(
            title=_tr("Importuj plik skryptu"),
            filetypes=[("Skrypty", "*.py *.sh *.ps1 *.js *.bat *.cmd "
                                   "*.vbs *.java *.jar *.c *.h *.cpp *.cc *.cxx "
                                   "*.c++ *.hpp *.hh *.hxx "
                                   "*.rb *.pl *.php *.wsf *.hta "
                                   "*.html *.htm *.css *.json *.md *.sql *.txt"),
                       ("Wszystkie pliki", "*.*")])
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in self._BIN_EXT:
                content = jar_base64(path)
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
        except Exception as e:
            messagebox.showerror(_tr("Błąd importu"), str(e))
            return
        nazwa = os.path.basename(path)
        kategoria = self._EXT_KAT.get(ext, "Other")
        existing = [x["nazwa"] for x in self.skrypty]
        if nazwa in existing:
            if not messagebox.askyesno(
                    _tr("Skrypt istnieje"),
                    f"Skrypt '{nazwa}' już istnieje. Nadpisać?"):
                return
            for i, s in enumerate(self.skrypty):
                if s["nazwa"] == nazwa:
                    self.skrypty[i] = {
                        "nazwa": nazwa, "kategoria": kategoria,
                        "tagi": f"import:{ext.lstrip('.')}",
                        "opis": f"Zaimportowano z {path}", "kod": content}
                    break
            akcja = "zaktualizowano"
        else:
            self.skrypty.append(sc_normalize({
                "nazwa": nazwa, "kategoria": kategoria,
                "tagi": f"import:{ext.lstrip('.')}",
                "opis": f"Zaimportowano z {path}", "kod": content}))
            akcja = "dodano"
        self._rebuild_index()
        self._update_count()
        self._refresh_lista()
        messagebox.showinfo(_tr("Import"), f"Plik '{nazwa}' {akcja} do bazy.")

    def _importuj_katalog(self):
        """Importuje wszystkie pliki skryptów z wybranego katalogu."""
        folder = filedialog.askdirectory(title=_tr("Importuj cały katalog"))
        if not folder:
            return
        znalezione = []
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(name)[1].lower() in self._SKRYPT_EXT:
                znalezione.append(full)
        if not znalezione:
            messagebox.showinfo(
                _tr("Import"),
                "Nie znaleziono plików skryptów w wybranym katalogu.\n"
                "Obsługiwane rozszerzenia: " + ", ".join(self._SKRYPT_EXT))
            return
        if not messagebox.askyesno(
                _tr("Import katalogu"),
                f"Znaleziono {len(znalezione)} plików skryptów w:\n{folder}\n\n"
                "Zaimportować je do bazy?"):
            return
        dodane, nadpisane, pominiete = 0, 0, 0
        for full in znalezione:
            ext = os.path.splitext(full)[1].lower()
            try:
                if ext in self._BIN_EXT:
                    content = jar_base64(full)
                else:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
            except Exception:
                pominiete += 1
                continue
            nazwa = os.path.basename(full)
            kategoria = self._EXT_KAT.get(ext, "Other")
            wpis = sc_normalize({"nazwa": nazwa, "kategoria": kategoria,
                    "tagi": f"import:{ext.lstrip('.')}",
                    "opis": f"Zaimportowano z {full}", "kod": content})
            idx = next((i for i, s in enumerate(self.skrypty)
                        if s["nazwa"] == nazwa), None)
            if idx is None:
                self.skrypty.append(wpis)
                dodane += 1
            else:
                wpis["id"] = self.skrypty[idx].get("id")
                wpis["utworzony"] = self.skrypty[idx].get("utworzony")
                self.skrypty[idx] = wpis
                nadpisane += 1
        self._rebuild_index()
        self._update_count()
        self._refresh_lista()
        self._after_db_change()
        messagebox.showinfo(
            _tr("Import katalogu"),
            f"Zaimportowano z:\n{folder}\n\n"
            f"Dodano: {dodane}\nNadpisano: {nadpisane}\nPominięto: {pominiete}")

    def _eksportuj(self, ext):
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=[(f"Plik .{ext}", f"*.{ext}")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_kod.get("1.0", "end-1c"))
            messagebox.showinfo(_tr("Eksport"), f"Wyeksportowano do:\n{path}")


    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Terminal — osadzony TerminalX (terminal.py)
    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Terminal — osadzony TerminalX (terminal.py) przez PTY
    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Terminal — osadzony TerminalX (terminal.py)
    # Obsługa: Windows (pywinpty/ConPTY) + Linux/macOS (pty)
    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Terminal — osadzony TerminalX (terminal.py)
    # Obsługa: Windows (pywinpty) + Linux/macOS (pty)
    # Parser ANSI: 16 kolorów + pełna paleta 256 + RGB (24-bit)
    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Terminal — uruchamia terminal.py w osobnym oknie systemowym
    # ══════════════════════════════════════════════════════════════════════════
    def _build_terminal_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["terminal"] = outer

        # ── Nagłówek ─────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._trw(tk.Label(hdr, text=_tr("🖥 Terminal"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE), "🖥 Terminal").pack(side="left")
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")
        from src.term.terminal import TerminalWidget

        self._terminal_widget = TerminalWidget(
            outer, bg=BG_DARK, on_plugin_command=self._plugin_terminal_command,
            tr=_tr)
        self._terminal_widget.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_git_frame(self):
        """Buduje ramkę dla zakładki Git."""
        self._ensure_git()
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["git"] = outer

        toolbar = tk.Frame(outer, bg=BG_PANEL, padx=8, pady=6)
        toolbar.pack(fill="x", side="top")
        for label, command, color in (
                ("Odśwież", self._git_refresh, ACCENT_BLUE),
            ("Commit staged…", self._git_commit, ACCENT_BLUE),
                ("Push", self._git_push, BTN_DARK),
                ("Pull", self._git_pull, BTN_DARK),
                ("Remote…", self._git_configure_remote, BTN_DARK),
                ("Synchronizuj bazę", self._git_sync_database, BTN_DARK)):
            button = self._trw(tk.Button(
                toolbar, text=_tr(label), font=FONT_UI, bg=color, fg=FG_WHITE,
                relief="flat", padx=10, pady=4, command=command), label)
            button.pack(side="left", padx=3)
        self._git_auto_push_var = tk.BooleanVar(
            value=str(self._cfg.get("git_auto_push", "0")) == "1")
        self._trw(ttk.Checkbutton(
            toolbar, text=_tr("Auto push po zapisie"),
            variable=self._git_auto_push_var,
            command=self._git_toggle_auto_push), "Auto push po zapisie").pack(
                side="right", padx=4)

        branch_bar = tk.Frame(outer, bg=BG_DARK, padx=10, pady=6)
        branch_bar.pack(fill="x")
        self._trw(tk.Label(branch_bar, text=_tr("Branch:"), font=FONT_BOLD,
             bg=BG_DARK, fg=FG_GRAY), "Branch:").pack(side="left", padx=(0, 6))
        self._git_branch_var = tk.StringVar()
        self._git_branch_combo = ttk.Combobox(
            branch_bar, textvariable=self._git_branch_var, state="readonly",
            font=FONT_MONO, width=28)
        self._git_branch_combo.pack(side="left")
        self._trw(tk.Button(branch_bar, text=_tr("Przełącz"), font=FONT_UI,
              bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
              command=self._git_checkout_branch), "Przełącz").pack(side="left", padx=4)
        self._trw(tk.Button(branch_bar, text=_tr("Nowy branch…"), font=FONT_UI,
              bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
              command=self._git_create_branch), "Nowy branch…").pack(side="left", padx=4)
        self._git_summary = tk.Label(branch_bar, text="", font=FONT_UI,
                                     bg=BG_DARK, fg=FG_GRAY, anchor="e")
        self._git_summary.pack(side="right", padx=4)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        content = tk.Frame(outer, bg=BG_DARK)
        content.pack(fill="both", expand=True, padx=8, pady=8)
        panes = ttk.Panedwindow(content, orient="horizontal")
        panes.pack(fill="both", expand=True)

        left = tk.Frame(panes, bg=BG_DARK)
        panes.add(left, weight=1)
        self._git_notebook = ttk.Notebook(left)
        self._git_notebook.pack(fill="both", expand=True)

        changes_frame = tk.Frame(self._git_notebook, bg=BG_DARK)
        self._git_notebook.add(changes_frame, text=_tr("Zmiany"))
        changes_toolbar = tk.Frame(changes_frame, bg=BG_PANEL, padx=4, pady=4)
        changes_toolbar.pack(fill="x")
        self._trw(tk.Button(
            changes_toolbar, text=_tr("Stage selected"), font=FONT_UI,
            bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=9, pady=3,
            command=self._git_stage_selected), "Stage selected").pack(side="left", padx=2)
        self._trw(tk.Button(
            changes_toolbar, text=_tr("Unstage selected"), font=FONT_UI,
            bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=9, pady=3,
            command=self._git_unstage_selected), "Unstage selected").pack(side="left", padx=2)
        self._trw(tk.Button(
            changes_toolbar, text=_tr("Discard worktree…"), font=FONT_UI,
            bg=BTN_ERR, fg=FG_WHITE, relief="flat", padx=9, pady=3,
            command=self._git_discard_worktree_selected), "Discard worktree…").pack(
                side="left", padx=2)
        changes_wrap = tk.Frame(changes_frame, bg=BG_DARK)
        changes_wrap.pack(fill="both", expand=True, padx=4, pady=4)
        changes_scroll = tk.Scrollbar(changes_wrap, orient="vertical")
        changes_scroll.pack(side="right", fill="y")
        self._git_changes_tree = ttk.Treeview(
            changes_wrap, columns=("status", "path"), show="headings",
            selectmode="extended", yscrollcommand=changes_scroll.set)
        changes_scroll.config(command=self._git_changes_tree.yview)
        self._trh(self._git_changes_tree, "status", "Stan")
        self._trh(self._git_changes_tree, "path", "Plik")
        self._git_changes_tree.column("status", width=120, minwidth=90, stretch=False)
        self._git_changes_tree.column("path", width=360, minwidth=160)
        self._git_changes_tree.pack(fill="both", expand=True)
        self._git_changes_tree.bind("<<TreeviewSelect>>", self._git_show_change)

        history_frame = tk.Frame(self._git_notebook, bg=BG_DARK)
        self._git_notebook.add(history_frame, text=_tr("Historia"))
        history_wrap = tk.Frame(history_frame, bg=BG_DARK)
        history_wrap.pack(fill="both", expand=True, padx=4, pady=4)
        history_scroll = tk.Scrollbar(history_wrap, orient="vertical")
        history_scroll.pack(side="right", fill="y")
        self._git_history_tree = ttk.Treeview(
            history_wrap, columns=("hash", "date", "author", "message"),
            show="headings", selectmode="browse",
            yscrollcommand=history_scroll.set)
        history_scroll.config(command=self._git_history_tree.yview)
        for column, title, width in (
                ("hash", "Commit", 90), ("date", "Data", 145),
                ("author", "Autor", 130), ("message", "Wiadomość", 260)):
            self._trh(self._git_history_tree, column, title)
            self._git_history_tree.column(
                column, width=width, minwidth=70,
                stretch=column == "message", anchor="w")
        self._git_history_tree.pack(fill="both", expand=True)
        self._git_history_tree.bind("<<TreeviewSelect>>", self._git_show_commit)

        detail = tk.Frame(panes, bg=BG_DARK)
        panes.add(detail, weight=2)
        detail_scroll = tk.Scrollbar(detail, orient="vertical")
        detail_scroll.pack(side="right", fill="y")
        self._git_output = tk.Text(
            detail, font=("Consolas", 9), bg="#1e2130", fg="#c8d0f0",
            insertbackground="#c8d0f0", wrap="none", relief="flat",
            yscrollcommand=detail_scroll.set, state="disabled")
        detail_scroll.config(command=self._git_output.yview)
        self._git_output.pack(side="left", fill="both", expand=True)
        self._git_history_items = {}
        self._git_changed_paths = {}
        self._git_refresh()

    def _show_git(self):
        self.main_frames["git"].pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Ustawienia — scentralizowana konfiguracja (CFG_KEYS / AppConfig)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ustawienia_frame(self):
        """Buduje zakładkę Ustawienia — formularz powiązany z kluczami konfiguracji."""
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["ustawienia"] = outer

        # (widget, klucz i18n) — etykiety odświeżane przy zmianie języka
        self._ust_i18n: List[Tuple[tk.Widget, str]] = []

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        self._ust_lbl_heading = tk.Label(hdr, text=_t("ust_header"),
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE)
        self._ust_lbl_heading.pack(side="left")
        self._ust_i18n.append((self._ust_lbl_heading, "ust_header"))
        # Selektor motywu — przełącza kolory interfejsu na żywo (bez zapisu formularza).
        self._ust_lbl_theme = tk.Label(hdr, text=_t("ust_look_theme"), font=FONT_UI,
                                       bg=BG_PANEL, fg=FG_GRAY)
        self._ust_lbl_theme.pack(side="left", padx=(18, 4))
        self._ust_i18n.append((self._ust_lbl_theme, "ust_look_theme"))
        self._theme_combo = ttk.Combobox(hdr, font=FONT_MONO, width=14,
                                         state="readonly",
                                         values=[_t("theme_" + n) for n in THEME_ORDER])
        self._theme_combo.set(_t("theme_" + self._theme))
        self._theme_combo.pack(side="left")
        self._theme_combo.bind("<<ComboboxSelected>>", self._on_theme_combo)
        self._ust_lbl_status = tk.Label(hdr, text="", font=FONT_UI,
                                        bg=BG_PANEL, fg="#6dde84")
        self._ust_lbl_status.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Pasek pod-zakładek: Ogólne / Personalizacja ─────────────────────
        sub_bar = tk.Frame(outer, bg=BG_PANEL)
        sub_bar.pack(fill="x")
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        sub_content = tk.Frame(outer, bg=BG_DARK)
        sub_content.pack(fill="both", expand=True)

        self._ust_sub_keys = ["ogolne", "personalizacja"]
        self._ust_sub_btns = []
        self._ust_sub_frames: Dict[str, tk.Frame] = {}
        for i, key in enumerate(self._ust_sub_keys):
            b = tk.Button(sub_bar, text=_t("ust_sub_" + key), font=FONT_UI,
                          bg=BG_SUBTAB_ACT if i == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE if i == 0 else FG_GRAY,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i: self._ust_sel_sub(i))
            b.pack(side="left")
            self._ust_sub_btns.append(b)
            self._ust_i18n.append((b, "ust_sub_" + key))

        bodies: Dict[str, tk.Frame] = {}
        for key in self._ust_sub_keys:
            host = tk.Frame(sub_content, bg=BG_DARK)
            self._ust_sub_frames[key] = host
            bodies[key] = self._ust_scroll_body(host)
        body_g = bodies["ogolne"]
        body_p = bodies["personalizacja"]
        self._ust_sel_sub(0)

        def lbl(parent, key, row):
            w = tk.Label(parent, text=_t(key), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
            w.grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
            self._ust_i18n.append((w, key))

        def section(parent, key, row):
            w = tk.Label(parent, text=_t(key), font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE)
            w.grid(row=row, column=0, columnspan=3, sticky="w", pady=(14, 4))
            self._ust_i18n.append((w, key))

        def entry(parent, row, value, read_only=False):
            e = tk.Entry(parent, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat")
            e.insert(0, "" if value is None else str(value))
            if read_only:
                e.configure(state="readonly")
            e.grid(row=row, column=1, sticky="ew", pady=4)
            return e

        def spin(parent, row, value, frm, to, width=8):
            sp = tk.Spinbox(parent, from_=frm, to=to, width=width, font=FONT_MONO,
                            bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                            insertbackground=FG_WHITE, buttonbackground=BG_PANEL)
            sp.delete(0, "end")
            sp.insert(0, "" if value is None else str(value))
            sp.grid(row=row, column=1, sticky="w", pady=4)
            return sp

        def check(parent, row, text, value):
            var = tk.BooleanVar(value=bool(value))
            tk.Checkbutton(parent, text=text, variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT,
                           activebackground=BG_DARK, activeforeground=FG_WHITE
                           ).grid(row=row, column=1, sticky="w", pady=4)
            return var

        def bind_preview(*widgets):
            for w in widgets:
                w.bind("<KeyRelease>", self._ust_preview_appearance)
                w.bind("<FocusOut>", self._ust_preview_appearance)
                w.bind("<Return>", self._ust_preview_appearance)

        # ══ Pod-zakładka: Ogólne ════════════════════════════════════════════
        # ── Baza danych — wszystkie opcje w jednym poziomym pasku ─────────────
        section(body_g, "ust_sec_db", 0)
        db_bar = tk.Frame(body_g, bg=BG_DARK)
        db_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=4)

        def bar_lbl(key):
            w = tk.Label(db_bar, text=_t(key), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
            self._ust_i18n.append((w, key))
            w.pack(side="left", padx=(0, 6))

        bar_lbl("ust_db_file")
        e_db = tk.Entry(db_bar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                        insertbackground=FG_WHITE, relief="flat", width=46)
        e_db.insert(0, str(self.db_path))
        e_db.configure(state="readonly")
        e_db.pack(side="left", fill="x", expand=True)
        b_open = tk.Button(db_bar, text=_t("ust_btn_open_folder"), font=FONT_UI, bg=BTN_DARK,
                  fg=FG_WHITE, relief="flat", padx=10, pady=2, cursor="hand2",
                  command=self._open_db_folder)
        b_open.pack(side="left", padx=(8, 0))
        self._ust_i18n.append((b_open, "ust_btn_open_folder"))

        tk.Frame(db_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=14, pady=2)
        bar_lbl("ust_db_backups")
        sp_bak = tk.Spinbox(db_bar, from_=0, to=10, width=6, font=FONT_MONO,
                            bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                            insertbackground=FG_WHITE, buttonbackground=BG_PANEL)
        sp_bak.delete(0, "end")
        sp_bak.insert(0, str(self._cfg.get("backup_count", DEFAULT_BACKUP_COUNT)))
        sp_bak.pack(side="left")

        bar_lbl("ust_db_autosave")
        v_auto = tk.BooleanVar(value=str(self._cfg.get("autosave", "1")) == "1")
        tk.Checkbutton(db_bar, variable=v_auto, font=FONT_UI,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT,
                       activebackground=BG_DARK, activeforeground=FG_WHITE
                       ).pack(side="left")

        # ── Runner — wszystkie opcje w jednym poziomym pasku ──────────────────
        section(body_g, "ust_sec_runner", 4)
        run_bar = tk.Frame(body_g, bg=BG_DARK)
        run_bar.grid(row=5, column=0, columnspan=3, sticky="ew", pady=4)

        def run_lbl(key):
            w = tk.Label(run_bar, text=_t(key), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
            self._ust_i18n.append((w, key))
            w.pack(side="left", padx=(0, 6))

        def run_sep():
            tk.Frame(run_bar, bg=BORDER_CLR, width=1).pack(
                side="left", fill="y", padx=10, pady=2)

        run_lbl("ust_run_interp")
        e_int = tk.Entry(run_bar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat", width=30)
        e_int.insert(0, self._cfg.get("interpreter", ""))
        e_int.pack(side="left")
        b_browse = tk.Button(run_bar, text=_t("ust_btn_browse"), font=FONT_UI, bg=BTN_DARK,
                  fg=FG_WHITE, relief="flat", padx=10, pady=2, cursor="hand2",
                  command=lambda: self._ust_wybierz_interpreter(e_int))
        b_browse.pack(side="left", padx=(6, 0))
        self._ust_i18n.append((b_browse, "ust_btn_browse"))

        run_sep()
        run_lbl("ust_run_timeout")
        sp_to = tk.Spinbox(run_bar, from_=1, to=3600, width=6, font=FONT_MONO,
                           bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                           insertbackground=FG_WHITE, buttonbackground=BG_PANEL)
        sp_to.delete(0, "end")
        sp_to.insert(0, str(self._cfg.get("timeout", DEFAULT_TIMEOUT)))
        sp_to.pack(side="left")

        run_sep()
        run_lbl("ust_run_args")
        e_args = tk.Entry(run_bar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                          insertbackground=FG_WHITE, relief="flat", width=22)
        e_args.insert(0, self._cfg.get("runner_args", ""))
        e_args.pack(side="left", fill="x", expand=True)

        run_sep()
        run_lbl("ust_run_console")
        v_con = tk.BooleanVar(value=str(self._cfg.get("runner_console", "0")) == "1")
        tk.Checkbutton(run_bar, variable=v_con, font=FONT_UI,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT,
                       activebackground=BG_DARK, activeforeground=FG_WHITE
                       ).pack(side="left")

        # ── Git — obie opcje w jednym poziomym pasku ──────────────────────────
        section(body_g, "ust_sec_git", 9)
        git_bar = tk.Frame(body_g, bg=BG_DARK)
        git_bar.grid(row=10, column=0, columnspan=3, sticky="w", pady=4)

        def git_lbl(key):
            w = tk.Label(git_bar, text=_t(key), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
            self._ust_i18n.append((w, key))
            w.pack(side="left", padx=(0, 6))

        def git_check(var):
            tk.Checkbutton(git_bar, variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT,
                           activebackground=BG_DARK, activeforeground=FG_WHITE
                           ).pack(side="left")

        git_lbl("ust_git_enabled")
        v_git_on = tk.BooleanVar(value=str(self._cfg.get("git_enabled", "1")) == "1")
        git_check(v_git_on)
        tk.Frame(git_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=2)
        git_lbl("ust_git_auto_commit")
        v_git_auto = tk.BooleanVar(value=str(self._cfg.get("git_auto_commit", "1")) == "1")
        git_check(v_git_auto)

        # ── Pluginy + Kosz + Powiadomienia — trzy sekcje w jednym pasku ────
        plug_bar = tk.Frame(body_g, bg=BG_DARK)
        plug_bar.grid(row=15, column=0, columnspan=3, sticky="w", pady=4)

        # Pluginy — jak pozostałe grupy: nagłówek, etykieta, opcja pod nią.
        plugins_grp = tk.Frame(plug_bar, bg=BG_DARK)
        plugins_grp.pack(side="left")
        w = tk.Label(plugins_grp, text=_t("ust_sec_plugins"), font=FONT_BOLD,
                     bg=BG_DARK, fg=ACCENT_BLUE)
        self._ust_i18n.append((w, "ust_sec_plugins"))
        w.pack(side="top", anchor="w", padx=(0, 6))
        w = tk.Label(plugins_grp, text=_t("ust_plugins_enabled"), font=FONT_UI,
                     bg=BG_DARK, fg=FG_GRAY)
        self._ust_i18n.append((w, "ust_plugins_enabled"))
        w.pack(side="top", anchor="w", pady=(2, 0))
        v_plug_on = tk.BooleanVar(value=str(self._cfg.get("plugins_enabled", "1")) == "1")
        tk.Checkbutton(plugins_grp, variable=v_plug_on, font=FONT_UI,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT,
                       activebackground=BG_DARK, activeforeground=FG_WHITE
                       ).pack(side="top", anchor="w", pady=(2, 0))
        # Kosz — po prawej stronie tego samego paska: nagłówek "Kosz",
        # a opcja (dni) pod etykietą — układ jak przy Pluginach.
        tk.Frame(plug_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=2)
        trash_grp = tk.Frame(plug_bar, bg=BG_DARK)
        trash_grp.pack(side="left")
        w = tk.Label(trash_grp, text=_t("ust_sec_trash"), font=FONT_BOLD,
                     bg=BG_DARK, fg=ACCENT_BLUE)
        self._ust_i18n.append((w, "ust_sec_trash"))
        w.pack(side="top", anchor="w", padx=(0, 6))
        w = tk.Label(trash_grp, text=_t("ust_trash_days"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
        self._ust_i18n.append((w, "ust_trash_days"))
        w.pack(side="top", anchor="w", pady=(2, 0))
        sp_trash = tk.Spinbox(trash_grp, from_=0, to=365, width=8, font=FONT_MONO,
                              bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                              insertbackground=FG_WHITE, buttonbackground=BG_PANEL)
        sp_trash.delete(0, "end")
        sp_trash.insert(0, str(self._cfg.get("trash_days", "0")))
        sp_trash.pack(side="top", anchor="w", pady=(2, 0))

        # Powiadomienia — po prawej stronie tego samego paska: nagłówek,
        # a opcja pod etykietą — układ jak przy Pluginach/Koszu.
        tk.Frame(plug_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=2)
        notify_grp = tk.Frame(plug_bar, bg=BG_DARK)
        notify_grp.pack(side="left")
        w = tk.Label(notify_grp, text=_t("ust_sec_notify"), font=FONT_BOLD,
                     bg=BG_DARK, fg=ACCENT_BLUE)
        self._ust_i18n.append((w, "ust_sec_notify"))
        w.pack(side="top", anchor="w", padx=(0, 6))
        w = tk.Label(notify_grp, text=_t("ust_notify_enabled"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
        self._ust_i18n.append((w, "ust_notify_enabled"))
        w.pack(side="top", anchor="w", pady=(2, 0))
        v_notify = tk.BooleanVar(value=str(self._cfg.get("notify_enabled", "1")) == "1")
        tk.Checkbutton(notify_grp, variable=v_notify, font=FONT_UI,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT,
                       activebackground=BG_DARK, activeforeground=FG_WHITE
                       ).pack(side="top", anchor="w", pady=(2, 0))

        # Język — po prawej stronie tego samego paska: nagłówek,
        # etykieta i combobox pod nią — układ jak w pozostałych grupach.
        tk.Frame(plug_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=2)
        lang_grp = tk.Frame(plug_bar, bg=BG_DARK)
        lang_grp.pack(side="left")
        w = tk.Label(lang_grp, text=_t("ust_sec_lang"), font=FONT_BOLD,
                     bg=BG_DARK, fg=ACCENT_BLUE)
        self._ust_i18n.append((w, "ust_sec_lang"))
        w.pack(side="top", anchor="w", padx=(0, 6))
        w = tk.Label(lang_grp, text=_t("ust_lang_label"), font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
        self._ust_i18n.append((w, "ust_lang_label"))
        w.pack(side="top", anchor="w", pady=(2, 0))
        cb_lang = ttk.Combobox(lang_grp, font=FONT_MONO, values=list(UI_LANGS), width=8,
                               state="readonly")
        cb_lang.set(_UI_LANG)
        cb_lang.pack(side="top", anchor="w", pady=(2, 0))

        # ══ Pod-zakładka: Personalizacja ══════════════════════════════════════
        # ── Wygląd ogólny ──────────────────────────────────────────────────────
        section(body_p, "ust_sec_look", 0)
        lbl(body_p, "ust_look_font", 1)
        cb_font = ttk.Combobox(body_p, font=FONT_MONO, values=[
            "Consolas", "Courier New", "Cascadia Mono", "Lucida Console",
            "Fira Code", "JetBrains Mono"])
        cb_font.set(self._cfg.get("font_family") or FONT_FAMILY)
        cb_font.grid(row=1, column=1, sticky="w", pady=4)
        lbl(body_p, "ust_look_fontsize", 2)
        sp_fs = spin(body_p, 2, self._cfg.get("font_size", "10"), FONT_SIZE_MIN, FONT_SIZE_MAX)
        lbl(body_p, "ust_look_bgact", 3)
        e_bgact = entry(body_p, 3, self._cfg.get("bg_tab_act") or BG_TAB_ACT)
        lbl(body_p, "ust_look_bginact", 4)
        e_bginact = entry(body_p, 4, self._cfg.get("bg_tab_inact") or BG_TAB_INACT)
        lbl(body_p, "ust_look_fg", 5)
        e_fg = entry(body_p, 5, self._cfg.get("fg_text") or FG_TEXT)
        # Przycisk wyboru koloru czcionki — obok comboboxa czcionki (wiersz 1).
        self._ust_color_btn = self._trw(tk.Button(
            body_p, text=_tr("🎨"), font=FONT_UI,
            bg=e_fg.get().strip() or FG_TEXT, fg="#ffffff",
            relief="flat", padx=8, pady=2, cursor="hand2",
            command=lambda: self._ust_pick_font_color(e_fg)), "🎨")
        self._ust_color_btn.grid(row=1, column=2, padx=(8, 0), sticky="w")
        self._ust_appearance_fields = (cb_font, sp_fs, e_bgact, e_bginact, e_fg)
        cb_font.bind("<<ComboboxSelected>>", self._ust_preview_appearance)
        cb_font.bind("<FocusOut>", self._ust_preview_appearance)
        bind_preview(sp_fs, e_bgact, e_bginact, e_fg)

        # ── Wygląd listy skryptów ──────────────────────────────────────────────
        section(body_p, "ust_sec_list", 6)
        lbl(body_p, "ust_list_alt", 7)
        v_alt = check(body_p, 7, "", str(self._cfg.get("list_alt_rows", "1")) == "1")
        v_alt.trace_add("write", lambda *_: self._ust_preview_appearance())
        lbl(body_p, "ust_list_bgodd", 8)
        e_bgodd = entry(body_p, 8, self._cfg.get("list_bg_odd", ""))
        lbl(body_p, "ust_list_bgeven", 9)
        e_bgeven = entry(body_p, 9, self._cfg.get("list_bg_even", ""))
        lbl(body_p, "ust_list_sel", 10)
        e_lsel = entry(body_p, 10, self._cfg.get("list_sel_bg", ""))
        lbl(body_p, "ust_list_rowheight", 11)
        sp_rowh = spin(body_p, 11, self._cfg.get("list_row_height", "24"), 16, 64)
        lbl(body_p, "ust_list_fontsize", 12)
        sp_lfs = spin(body_p, 12, self._cfg.get("list_font_size", "10"),
                      FONT_SIZE_MIN, 20)
        self._ust_list_fields = (v_alt, e_bgodd, e_bgeven, e_lsel, sp_rowh, sp_lfs)
        bind_preview(e_bgodd, e_bgeven, e_lsel, sp_rowh, sp_lfs)

        # ── Przyciski (wspólne dla obu pod-zakładek) ───────────────────────────
        footer = tk.Frame(outer, bg=BG_DARK, padx=14, pady=8)
        footer.pack(fill="x", side="bottom")
        row_btn = tk.Frame(footer, bg=BG_DARK)
        row_btn.pack(anchor="w")
        list_fields = self._ust_list_fields
        b_save = tk.Button(row_btn, text=_t("ust_btn_save"), font=FONT_BOLD, bg=ACCENT_BLUE,
                  fg=FG_WHITE, relief="flat", padx=14, pady=5, cursor="hand2",
                  command=lambda: self._ustawienia_save(
                      sp_bak, v_auto, e_int, sp_to, e_args, v_con,
                      cb_font, sp_fs, e_bgact, e_bginact, e_fg, cb_lang,
                      v_git_on, v_git_auto, v_plug_on, sp_trash, v_notify,
                      list_fields))
        b_save.pack(side="left", padx=(0, 8))
        b_reset = tk.Button(row_btn, text=_t("ust_btn_reset"), font=FONT_UI, bg=BTN_DARK,
                  fg=FG_WHITE, relief="flat", padx=14, pady=5, cursor="hand2",
                  command=lambda: self._ustawienia_reset(
                      sp_bak, v_auto, e_int, sp_to, e_args, v_con,
                      cb_font, sp_fs, e_bgact, e_bginact, e_fg, cb_lang,
                      v_git_on, v_git_auto, v_plug_on, sp_trash, v_notify,
                      list_fields))
        b_reset.pack(side="left")
        self._ust_i18n.append((b_save, "ust_btn_save"))
        self._ust_i18n.append((b_reset, "ust_btn_reset"))
        self._ust_lbl_cfgfile = tk.Label(footer, text=_t("ust_cfg_file", file=CFG_FILE),
                 font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY)
        self._ust_lbl_cfgfile.pack(anchor="w", pady=(8, 0))

    def _show_ustawienia(self):
        self.main_frames["ustawienia"].pack(fill="both", expand=True)

    def _ust_scroll_body(self, host: tk.Frame) -> tk.Frame:
        """Tworzy przewijany formularz w ``host``; zwraca ramkę siatki (body)."""
        scrollbar = tk.Scrollbar(host, orient="vertical", bg=BG_PANEL,
                                 troughcolor=BG_PANEL, width=10)
        scrollbar.pack(side="right", fill="y")
        canvas = tk.Canvas(host, bg=BG_DARK, highlightthickness=0,
                           yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)
        body = tk.Frame(canvas, bg=BG_DARK, padx=14, pady=10)
        win = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda event: canvas.itemconfigure(win, width=event.width))
        body.columnconfigure(1, weight=1)
        return body

    def _ust_sel_sub(self, idx: int) -> None:
        """Przełącza pod-zakładkę Ustawień (Ogólne / Personalizacja)."""
        key = self._ust_sub_keys[idx]
        for i, b in enumerate(self._ust_sub_btns):
            b.configure(bg=BG_SUBTAB_ACT if i == idx else BG_SUBTAB_INACT,
                        fg=FG_WHITE if i == idx else FG_GRAY)
        for k, frame in self._ust_sub_frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self._update_minsize()

    def _ust_pick_font_color(self, entry_widget: tk.Entry) -> None:
        """Otwiera systemowy wybór koloru i wpisuje hex do pola koloru czcionki."""
        from tkinter import colorchooser
        current = entry_widget.get().strip()
        picked = colorchooser.askcolor(
            color=current if _is_hex_color(current) else FG_TEXT, parent=self)
        if not picked or not picked[1]:
            return
        entry_widget.delete(0, "end")
        entry_widget.insert(0, picked[1])
        self._ust_preview_appearance()

    def _ust_wybierz_interpreter(self, entry_widget):
        """Otwiera dialog wyboru interpretera Python i wpisuje ścieżkę."""
        path = filedialog.askopenfilename(
            title=_t("ust_dlg_interp_title"),
            filetypes=[("Python", "python*.exe"), (_t("ust_dlg_all_files"), "*.*")])
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def _ust_preview_appearance(self, _event: Any = None) -> None:
        fields = getattr(self, "_ust_appearance_fields", None)
        list_fields = getattr(self, "_ust_list_fields", None)
        if not fields and not list_fields:
            return
        preview = dict(self._cfg)
        preview_keys: List[str] = []
        if fields:
            cb_font, sp_fs, e_bgact, e_bginact, e_fg = fields
            try:
                font_size = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, int(sp_fs.get())))
            except (TypeError, ValueError):
                font_size = int(preview.get("font_size", "10") or 10)
            colors = (e_bgact.get().strip(), e_bginact.get().strip(), e_fg.get().strip())
            if any(color and not _is_hex_color(color) for color in colors):
                return
            preview.update({
                "font_family": cb_font.get().strip(),
                "font_size": str(font_size),
                "bg_tab_act": colors[0],
                "bg_tab_inact": colors[1],
                "fg_text": colors[2],
            })
            preview_keys += ["font_family", "font_size",
                             "bg_tab_act", "bg_tab_inact", "fg_text"]
            color_btn = getattr(self, "_ust_color_btn", None)
            if color_btn is not None:
                try:
                    color_btn.configure(bg=colors[2] or FG_TEXT)
                except Exception:
                    pass
        if list_fields:
            v_alt, e_odd, e_even, e_lsel, sp_rowh, sp_lfs = list_fields
            lcolors = (e_odd.get().strip(), e_even.get().strip(),
                       e_lsel.get().strip())
            if any(color and not _is_hex_color(color) for color in lcolors):
                return
            try:
                row_h = max(16, min(64, int(sp_rowh.get())))
                lfs = max(FONT_SIZE_MIN, min(20, int(sp_lfs.get())))
            except (TypeError, ValueError):
                return
            preview.update({
                "list_alt_rows": "1" if v_alt.get() else "0",
                "list_bg_odd": lcolors[0],
                "list_bg_even": lcolors[1],
                "list_sel_bg": lcolors[2],
                "list_row_height": str(row_h),
                "list_font_size": str(lfs),
                "font_family": preview.get("font_family") or FONT_FAMILY,
            })
            preview_keys += ["list_alt_rows", "list_bg_odd", "list_bg_even",
                             "list_sel_bg", "list_row_height", "list_font_size"]
            if "font_family" not in preview_keys:
                preview_keys.append("font_family")
        self._appearance_preview = {key: preview[key] for key in preview_keys}
        self._apply_list_appearance(preview)
        self._apply_appearance_settings(preview)

    def _apply_list_appearance(self, config: Optional[Dict[str, str]] = None) -> None:
        """Stosuje wygląd listy skryptów: styl drzewa, wysokość i tagi wierszy.

        Puste kolory w konfiguracji oznaczają użycie palety aktywnego motywu.
        """
        tree = getattr(self, "tree", None)
        if tree is None:
            return
        cfg = dict(self._cfg)
        if config:
            cfg.update(config)
        fam = (cfg.get("font_family") or FONT_FAMILY).strip() or FONT_FAMILY
        try:
            lsize = max(FONT_SIZE_MIN, min(20, int(cfg.get("list_font_size") or 10)))
        except (TypeError, ValueError):
            lsize = 10
        try:
            row_h = max(16, min(64, int(cfg.get("list_row_height") or 24)))
        except (TypeError, ValueError):
            row_h = 24
        odd = cfg.get("list_bg_odd", "").strip()
        even = cfg.get("list_bg_even", "").strip()
        sel = cfg.get("list_sel_bg", "").strip()
        odd = odd if _is_hex_color(odd) else BG_ROW_ODD
        even = even if _is_hex_color(even) else BG_ROW_EVEN
        sel = sel if _is_hex_color(sel) else BG_ROW_SEL
        alt = str(cfg.get("list_alt_rows", "1")) == "1"

        style = ttk.Style(tree)
        style.configure("ScriptList.Treeview",
                        background=odd, fieldbackground=odd,
                        foreground=FG_WHITE, rowheight=row_h,
                        font=(fam, lsize))
        style.configure("ScriptList.Treeview.Heading",
                        background=BG_PANEL, foreground=FG_GRAY,
                        font=(fam, 9, "bold"), relief="flat")
        style.map("ScriptList.Treeview",
                  background=[("selected", sel)],
                  foreground=[("selected", FG_WHITE)])
        tree.tag_configure("odd", background=odd)
        tree.tag_configure("even", background=even if alt else odd)

    def _ustawienia_save(self, sp_bak, v_auto, e_int, sp_to, e_args, v_con,
                         cb_font, sp_fs, e_bgact, e_bginact, e_fg, cb_lang,
                         v_git_on=None, v_git_auto=None, v_plug_on=None, sp_trash=None,
                         v_notify=None, list_fields=None):
        """Zapisuje ustawienia z formularza do konfiguracji (cfg_save)."""
        try:
            backup_count = max(0, min(10, int(sp_bak.get())))
            timeout = max(1, min(3600, int(sp_to.get())))
            font_size = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, int(sp_fs.get())))
            trash_days = max(0, min(365, int(sp_trash.get()))) if sp_trash is not None else 0
        except ValueError:
            self._ust_lbl_status.config(text=_t("ust_status_err"), fg="#e0736a")
            return

        custom_colors = (e_bgact.get().strip(), e_bginact.get().strip(), e_fg.get().strip())
        if any(color and not _is_hex_color(color) for color in custom_colors):
            self._ust_lbl_status.config(text=_t("ust_status_err"), fg="#e0736a")
            return

        list_cfg: Dict[str, str] = {}
        if list_fields is not None:
            v_alt, e_odd, e_even, e_lsel, sp_rowh, sp_lfs = list_fields
            try:
                list_row_h = max(16, min(64, int(sp_rowh.get())))
                list_fs = max(FONT_SIZE_MIN, min(20, int(sp_lfs.get())))
            except ValueError:
                self._ust_lbl_status.config(text=_t("ust_status_err"), fg="#e0736a")
                return
            list_colors = (e_odd.get().strip(), e_even.get().strip(),
                           e_lsel.get().strip())
            if any(color and not _is_hex_color(color) for color in list_colors):
                self._ust_lbl_status.config(text=_t("ust_status_err"), fg="#e0736a")
                return
            list_cfg = {
                "list_alt_rows":   "1" if v_alt.get() else "0",
                "list_bg_odd":     list_colors[0],
                "list_bg_even":    list_colors[1],
                "list_sel_bg":     list_colors[2],
                "list_row_height": str(list_row_h),
                "list_font_size":  str(list_fs),
            }

        self._cfg.update({
            "autosave":       "1" if v_auto.get() else "0",
            "backup_count":   str(backup_count),
            "interpreter":    e_int.get().strip(),
            "timeout":        str(timeout),
            "runner_args":    e_args.get().strip(),
            "runner_console": "1" if v_con.get() else "0",
            "bg_tab_act":     e_bgact.get().strip(),
            "bg_tab_inact":   e_bginact.get().strip(),
            "fg_text":        e_fg.get().strip(),
            "font_family":    cb_font.get().strip(),
            "font_size":      str(font_size),
            "language":       cb_lang.get(),
            "git_enabled":     "1" if (v_git_on is None or v_git_on.get()) else "0",
            "git_auto_commit": "1" if (v_git_auto is None or v_git_auto.get()) else "0",
            "plugins_enabled": "1" if (v_plug_on is None or v_plug_on.get()) else "0",
            "trash_days":      str(trash_days),
            "notify_enabled":  "1" if (v_notify is None or v_notify.get()) else "0",
        })
        self._cfg.update(list_cfg)
        cfg_save(self._cfg)
        self._appearance_preview = {}
        self._apply_appearance_settings()
        self._apply_list_appearance()
        # Zastosuj język od razu, jeśli zmieniony.
        if self._cfg["language"] != _UI_LANG:
            _set_lang(self._cfg["language"])
            self._retranslate_ui()
        # Zastosuj przełączniki Git/pluginy na żywo.
        self._apply_git_plugins_config()
        # Auto-czyszczenie kosza wg nowej reguły (trash_days).
        purged = self._trash_purge_old()
        # Odśwież pole timeout w panelu Runnera, jeśli istnieje.
        if hasattr(self, "_runner_entry_timeout"):
            self._runner_entry_timeout.delete(0, "end")
            self._runner_entry_timeout.insert(0, self._cfg["timeout"])
        if purged:
            self._ust_lbl_status.config(
                text=_t("ust_status_purged", n=purged), fg="#e0c040")
        else:
            self._ust_lbl_status.config(text=_t("ust_status_saved"), fg="#6dde84")

    def _ustawienia_reset(self, sp_bak, v_auto, e_int, sp_to, e_args, v_con,
                          cb_font, sp_fs, e_bgact, e_bginact, e_fg, cb_lang,
                          v_git_on=None, v_git_auto=None, v_plug_on=None, sp_trash=None,
                          v_notify=None, list_fields=None):
        """Przywraca w formularzu wartości domyślne (bez zapisu)."""
        def set_spin(sp, val):
            sp.delete(0, "end")
            sp.insert(0, str(val))

        def set_entry(e, val, read_only=False):
            state = e.cget("state")
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, val)
            if read_only or state == "readonly":
                e.configure(state="readonly")

        set_spin(sp_bak, CFG_KEYS["backup_count"])
        v_auto.set(CFG_KEYS["autosave"] == "1")
        set_entry(e_int, CFG_KEYS["interpreter"])
        set_spin(sp_to, CFG_KEYS["timeout"])
        set_entry(e_args, CFG_KEYS["runner_args"])
        v_con.set(CFG_KEYS["runner_console"] == "1")
        cb_font.set(CFG_KEYS["font_family"] or "Consolas")
        set_spin(sp_fs, CFG_KEYS["font_size"])
        base_colors = theme_values(self._theme)
        set_entry(e_bgact, base_colors["BG_TAB_ACT"])
        set_entry(e_bginact, base_colors["BG_TAB_INACT"])
        set_entry(e_fg, base_colors["FG_TEXT"])
        cb_lang.set(CFG_KEYS["language"])
        if v_git_on is not None:
            v_git_on.set(CFG_KEYS["git_enabled"] == "1")
        if v_git_auto is not None:
            v_git_auto.set(CFG_KEYS["git_auto_commit"] == "1")
        if v_plug_on is not None:
            v_plug_on.set(CFG_KEYS["plugins_enabled"] == "1")
        if sp_trash is not None:
            set_spin(sp_trash, CFG_KEYS["trash_days"])
        if v_notify is not None:
            v_notify.set(CFG_KEYS["notify_enabled"] == "1")
        if list_fields is not None:
            v_alt, e_odd, e_even, e_lsel, sp_rowh, sp_lfs = list_fields
            v_alt.set(CFG_KEYS["list_alt_rows"] == "1")
            set_entry(e_odd, CFG_KEYS["list_bg_odd"])
            set_entry(e_even, CFG_KEYS["list_bg_even"])
            set_entry(e_lsel, CFG_KEYS["list_sel_bg"])
            set_spin(sp_rowh, CFG_KEYS["list_row_height"])
            set_spin(sp_lfs, CFG_KEYS["list_font_size"])
        self._ust_preview_appearance()
        self._ust_lbl_status.config(text=_t("ust_status_reset"), fg="#e0c040")

    def _apply_git_plugins_config(self) -> None:
        """Stosuje przełączniki Git/pluginy z konfiguracji na żywo (bez restartu)."""
        self._git_auto_commit = str(self._cfg.get("git_auto_commit", "1")) == "1"
        self._git_auto_push = str(self._cfg.get("git_auto_push", "0")) == "1"
        # Git — utwórz/usuń instancję integracji zależnie od git_enabled.
        self._git_enabled = (
            _GIT_AVAILABLE and str(self._cfg.get("git_enabled", "1")) == "1")
        if self._git_enabled:
            self._ensure_git()
        else:
            self._git = None
        # Pluginy — załaduj lub wyładuj menedżer zależnie od plugins_enabled.
        if str(self._cfg.get("plugins_enabled", "1")) == "1":
            if _PLUGINS_AVAILABLE and self._plugin_manager is None:
                try:
                    self._plugin_manager = PluginManager(self)
                    self._plugin_manager.load_plugins()
                    self._plugins_apply_disabled()
                    self._plugin_manager.trigger_hook("on_app_start")
                except Exception as e:
                    logging.warning(f"Nie udało się włączyć pluginów: {e}")
                    self._plugin_manager = None
        else:
            if self._plugin_manager is not None:
                for name in list(self._plugin_manager.plugins.keys()):
                    try:
                        self._plugin_manager.unload_plugin(name)
                    except Exception:
                        pass
            self._plugin_manager = None

    def _build_plugins_frame(self):
        """Buduje ramkę dla zakładki Plugins."""
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["plugins"] = outer

        # ── pasek wyszukiwania + status błędów ──────────────────────────────
        top = tk.Frame(outer, bg=BG_PANEL)
        top.pack(fill="x", side="top", padx=8, pady=(8, 4))
        self._trw(tk.Label(top, text=_tr("Szukaj:"), font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY), "Szukaj:").pack(side="left", padx=(8, 4))
        self._plugins_filter_var = tk.StringVar()
        self._plugins_filter_var.trace_add("write", lambda *_: self._plugins_refresh())
        self._trw(tk.Entry(top, textvariable=self._plugins_filter_var, font=FONT_UI,
                 bg=BG_INPUT, fg=FG_WHITE, relief="flat", width=28,
                 highlightthickness=1, highlightbackground=BORDER_CLR,
                 highlightcolor=ACCENT_BLUE), "Szukaj:").pack(side="left", padx=(0, 10))
        self._plugins_status_lbl = tk.Label(top, text="", font=FONT_UI,
                                            bg=BG_PANEL, fg="#e0a020", anchor="w")
        self._plugins_status_lbl.pack(side="left", fill="x", expand=True)

        # ── pasek akcji ─────────────────────────────────────────────────────
        toolbar = tk.Frame(outer, bg=BG_PANEL)
        toolbar.pack(fill="x", side="top", padx=8, pady=(0, 4))

        def _pbtn(text, cmd, color=BTN_DARK, fg=None):
            return self._trw(tk.Button(toolbar, text=_tr(text), font=FONT_UI,
                      bg=color, fg=fg or FG_WHITE, relief="flat", padx=10, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=cmd), text)

        _pbtn("Odśwież", self._plugins_refresh).pack(side="left", padx=4)
        _pbtn("Włącz/Wyłącz", self._plugins_toggle, BTN_ACCENT).pack(side="left", padx=4)
        _pbtn("Szczegóły", self._plugins_details, BTN_ACCENT).pack(side="left", padx=4)
        _pbtn("Przeładuj", self._plugins_reload).pack(side="left", padx=4)
        _pbtn("Usuń", self._plugins_delete, BTN_ERR, fg=ERROR).pack(side="left", padx=4)
        _pbtn("Folder", self._plugins_open_folder).pack(side="left", padx=4)
        _pbtn("Hooki", self._plugins_hooks_dialog).pack(side="left", padx=4)
        _pbtn("? Komendy", self._plugins_commands_dialog).pack(side="left", padx=4)
        _pbtn("Marketplace", self._plugins_marketplace, BTN_ACCENT).pack(side="left", padx=4)
        _pbtn("＋ Nowy", self._plugins_new, BTN_OK).pack(side="left", padx=4)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── lista pluginów ──────────────────────────────────────────────────
        content = tk.Frame(outer, bg=BG_DARK)
        content.pack(fill="both", expand=True, padx=8, pady=8)

        columns = ("name", "version", "author", "category", "hooks", "enabled")
        self._plugins_tree = ttk.Treeview(content, columns=columns, show="headings",
                                          selectmode="browse")
        for col, txt, w in (("name", "Nazwa", 190), ("version", "Wersja", 70),
                            ("author", "Autor", 140), ("category", "Kategoria", 90),
                            ("hooks", "Hooki", 60), ("enabled", "Status", 90)):
            self._trh(self._plugins_tree, col, txt)
            self._plugins_tree.column(col, width=w, anchor="w")
        self._plugins_tree.tag_configure("on", foreground=SUCCESS)
        self._plugins_tree.tag_configure("off", foreground=FG_GRAY)
        self._plugins_tree.pack(fill="both", expand=True)
        self._plugins_tree.bind("<Double-1>", lambda _e: self._plugins_details())

        if self._plugin_manager:
            self._plugins_refresh()

    def _show_plugins(self):
        self.main_frames["plugins"].pack(fill="both", expand=True)

    def _plugins_selected_name(self):
        """Zwraca nazwę wybranego pluginu lub None."""
        selection = self._plugins_tree.selection()
        if not selection:
            return None
        values = self._plugins_tree.item(selection[0], "values")
        return values[0] if values else None

    def _plugins_apply_disabled(self):
        """Wyłącza pluginy z listy ``plugins_disabled`` (po załadowaniu)."""
        if not self._plugin_manager:
            return
        disabled = {s.strip() for s in str(self._cfg.get("plugins_disabled", "")).split(",")
                    if s.strip()}
        for name in disabled:
            if name in self._plugin_manager.plugins:
                self._plugin_manager.disable_plugin(name)

    def _plugins_save_disabled(self):
        """Zapisuje listę wyłączonych pluginów do konfiguracji."""
        if not self._plugin_manager:
            return
        names = [n for n, p in self._plugin_manager.plugins.items() if not p.enabled]
        self._cfg["plugins_disabled"] = ",".join(sorted(names))
        try:
            cfg_save(self._cfg)
        except Exception:
            pass

    def _plugins_refresh(self):
        """Odświeża listę pluginów (z filtrem tekstowym)."""
        if not self._plugin_manager or not hasattr(self, "_plugins_tree"):
            return

        for item in self._plugins_tree.get_children():
            self._plugins_tree.delete(item)

        filt = ""
        if hasattr(self, "_plugins_filter_var"):
            filt = self._plugins_filter_var.get().strip().lower()

        n_err = len(getattr(self._plugin_manager, "load_errors", []))
        if hasattr(self, "_plugins_status_lbl"):
            self._plugins_status_lbl.config(
                text=(f"⚠ {n_err} {_tr('błąd(ów) ładowania')} — {_tr('szczegóły w: Hooki')}"
                      if n_err else ""))

        for plugin_name, plugin in self._plugin_manager.plugins.items():
            info = plugin.get_info()
            hay = " ".join(str(info.get(k, "")) for k in
                           ("name", "author", "category", "description")).lower()
            if filt and filt not in hay:
                continue
            enabled = info.get("enabled") == "True"
            self._plugins_tree.insert("", "end", iid=plugin_name, tags=("on" if enabled else "off"),
                                      values=(
                                          info.get("name", ""),
                                          info.get("version", ""),
                                          info.get("author", ""),
                                          info.get("category", ""),
                                          len(getattr(plugin, "registered_hooks", [])),
                                          _tr("Włączony") if enabled else _tr("Wyłączony"),
                                      ))

    def _plugins_toggle(self):
        """Przełącza status wybranego pluginu."""
        if not self._plugin_manager:
            return
        plugin_name = self._plugins_selected_name()
        if not plugin_name:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz plugin z listy."))
            return
        plugin = self._plugin_manager.plugins.get(plugin_name)
        if not plugin:
            return
        if plugin.enabled:
            self._plugin_manager.disable_plugin(plugin_name)
        else:
            self._plugin_manager.enable_plugin(plugin_name)
        self._plugins_save_disabled()
        self._plugins_refresh()

    def _plugins_reload(self, plugin_name=None):
        """Przeładowuje wybrany plugin z pliku (bez restartu)."""
        if not self._plugin_manager:
            return
        plugin_name = plugin_name or self._plugins_selected_name()
        if not plugin_name:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz plugin z listy."))
            return
        plugin = self._plugin_manager.plugins.get(plugin_name)
        if plugin is None:
            return
        was_enabled = plugin.enabled
        if self._plugin_manager.reload_plugin(plugin_name):
            plugin = self._plugin_manager.plugins.get(plugin_name)
            if plugin is not None and was_enabled != plugin.enabled:
                if was_enabled:
                    plugin.on_enable()
                else:
                    plugin.on_disable()
            self._plugins_save_disabled()
            self._plugins_refresh()
        else:
            messagebox.showerror(_tr("Przeładowanie"),
                                 _tr("Nie udało się przeładować pluginu."))

    def _plugins_delete(self, plugin_name=None):
        """Usuwa plik lokalnego pluginu i wyładowuje go."""
        if not self._plugin_manager:
            return
        plugin_name = plugin_name or self._plugins_selected_name()
        if not plugin_name:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz plugin z listy."))
            return
        path = self._plugin_manager.get_plugin_path(plugin_name)
        if path is None or not path.exists():
            messagebox.showerror(_tr("Usuń"), _tr("Nie znaleziono pliku pluginu."))
            return
        if not messagebox.askyesno(_tr("Usuń plugin"),
                                   f"{_tr('Usunąć trwale plik pluginu?')}\n{path}"):
            return
        try:
            path.unlink()
        except Exception as e:
            messagebox.showerror(_tr("Usuń"), f"{_tr('Nie udało się usunąć pliku:')}\n{e}")
            return
        self._plugin_manager.unload_plugin(plugin_name)
        self._plugin_manager._plugin_files.pop(plugin_name, None)
        self._plugins_save_disabled()
        self._plugins_refresh()

    def _plugins_open_folder(self):
        """Otwiera katalog z pluginami w eksploratorze."""
        if not self._plugin_manager:
            return
        import subprocess
        path = str(self._plugin_manager.plugins_dir)
        try:
            os.startfile(path)  # noqa: S606 — Windows
        except AttributeError:
            subprocess.Popen(["xdg-open", path])

    # ── katalog komend nawigacyjnych (moduł src/modules/plugin_creator.py) ──
    _NAV_COMMANDS = _CREATOR_NAV_COMMANDS
    _FILE_COMMANDS = _CREATOR_FILE_COMMANDS

    @staticmethod
    def _plugin_source(fname, cls_name, disp, version, author, desc, cat,
                       homepage="", license_="", alias="", hooks=(), nav=(),
                       files=()):
        """Generuje kod źródłowy pluginu — deleguje do modułu kreatora."""
        return _creator_plugin_source(
            fname=fname, cls_name=cls_name, disp=disp, version=version,
            author=author, desc=desc, cat=cat, homepage=homepage,
            license_=license_, alias=alias, hooks=hooks, nav=nav, files=files)

    def _plugins_new(self):
        """Kreator pluginu — generuje szablon pliku .py w katalogu plugins/."""
        if not self._plugin_manager or not _CREATOR_AVAILABLE:
            return
        dlg = _popup(self)
        dlg.title(_tr("Nowy plugin"))
        dlg.transient(self)
        dlg.grab_set()
        body = tk.Frame(dlg, bg=BG_PANEL, padx=14, pady=12)
        body.pack(fill="both", expand=True)

        entries = {}
        fields = (
            ("fname",   _tr("Nazwa pliku (np. moj_plugin):"), "moj_plugin"),
            ("disp",    _tr("Nazwa pluginu:"),             "Mój plugin"),
            ("version", _tr("Wersja:"),                    "1.0.0"),
            ("author",  _tr("Autor:"),                    "CodeMate User"),
            ("cat",     _tr("Kategoria:"),                 "Narzędzia"),
            ("desc",    _tr("Opis:"),                      ""),
            ("homepage", _tr("Strona domowa (opcjonalnie):"), ""),
            ("license", _tr("Licencja (opcjonalnie):"),    ""),
            ("alias",   _tr("Alias komendy, np. /stats (opcjonalnie):"), ""),
        )
        for i, (key, label, default) in enumerate(fields):
            tk.Label(body, text=label, font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                     anchor="w").grid(row=i * 2, column=0, sticky="w", pady=(6, 0))
            e = tk.Entry(body, font=FONT_UI, bg=BG_INPUT, fg=FG_WHITE, relief="flat",
                         highlightthickness=1, highlightbackground=BORDER_CLR,
                         highlightcolor=ACCENT_BLUE)
            e.insert(0, default)
            e.grid(row=i * 2 + 1, column=0, sticky="ew", pady=(0, 2))
            entries[key] = e
        body.columnconfigure(0, weight=1)

        # ── wybór hooków do wygenerowania (okno popup) ─────────────────────
        hook_vars = {}
        _hook_traced = set()

        def _mk_hook_var(h):
            if h not in hook_vars:
                var = tk.BooleanVar(value=False)
                hook_vars[h] = var
            var = hook_vars[h]
            if h not in _hook_traced:
                var.trace_add("write", lambda *_: _hook_count())
                _hook_traced.add(h)
            return var

        def _hook_count():
            hook_count_lbl.config(text=_tr("Wybrane: {n}").format(
                n=sum(1 for v in hook_vars.values() if v.get())))

        def _hooks_popup():
            top = _popup(dlg)
            top.title(_tr("Hooki do wygenerowania"))
            top.geometry("560x360")
            top.transient(dlg)
            pf = tk.Frame(top, bg=BG_PANEL, padx=14, pady=12)
            pf.pack(fill="both", expand=True)
            btns = tk.Frame(pf, bg=BG_PANEL)
            btns.pack(fill="x", pady=(0, 8))

            def _hooks_all(state):
                for h in PluginManager.HOOKS:
                    _mk_hook_var(h).set(state)
                _hook_count()

            tk.Button(btns, text=_tr("Zaznacz wszystkie"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=lambda: _hooks_all(True)).pack(side="left", padx=(0, 4))
            tk.Button(btns, text=_tr("Odznacz wszystkie"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=lambda: _hooks_all(False)).pack(side="left")
            tk.Button(btns, text=_tr("Zamknij"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=top.destroy).pack(side="right")

            grid = tk.Frame(pf, bg=BG_PANEL)
            grid.pack(fill="both", expand=True)
            for i, h in enumerate(PluginManager.HOOKS):
                var = _mk_hook_var(h)
                tk.Checkbutton(grid, text=h, variable=var, font=("Consolas", 8),
                               bg=BG_PANEL, fg=FG_GRAY, selectcolor=BG_INPUT,
                               activebackground=BG_PANEL,
                               activeforeground=FG_WHITE, anchor="w",
                               ).grid(row=i // 2, column=i % 2, sticky="w", pady=2)

        hook_row = tk.Frame(body, bg=BG_PANEL)
        hook_row.grid(row=len(fields) * 2, column=0, sticky="w", pady=(10, 0))
        tk.Button(hook_row, text=_tr("Hooks"), font=FONT_UI, bg=BTN_ACCENT,
                  fg=FG_WHITE, relief="flat", padx=14, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER, command=_hooks_popup).pack(side="left")
        hook_count_lbl = tk.Label(hook_row, text=_tr("Wybrane: {n}").format(n=0),
                                  font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY)
        hook_count_lbl.pack(side="left", padx=(8, 0))

        # ── komendy: separator + przycisk Navigation (popup) ────────────────
        nav_vars = {}
        _nav_traced = set()

        def _mk_nav_var(alias):
            if alias not in nav_vars:
                nav_vars[alias] = tk.BooleanVar(value=False)
            var = nav_vars[alias]
            if alias not in _nav_traced:
                var.trace_add("write", lambda *_: _nav_count())
                _nav_traced.add(alias)
            return var

        def _nav_count():
            nav_count_lbl.config(text=_tr("Wybrane: {n}").format(
                n=sum(1 for v in nav_vars.values() if v.get())))

        def _nav_popup():
            top = _popup(dlg)
            top.title(_tr("Komendy nawigacji"))
            top.geometry("640x480")
            top.transient(dlg)
            pf = tk.Frame(top, bg=BG_PANEL, padx=14, pady=12)
            pf.pack(fill="both", expand=True)
            btns = tk.Frame(pf, bg=BG_PANEL)
            btns.pack(fill="x", pady=(0, 8))

            def _nav_all(state):
                for alias, _t, _d in self._NAV_COMMANDS:
                    _mk_nav_var(alias).set(state)
                _nav_count()

            tk.Button(btns, text=_tr("Zaznacz wszystkie"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=lambda: _nav_all(True)).pack(side="left", padx=(0, 4))
            tk.Button(btns, text=_tr("Odznacz wszystkie"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=lambda: _nav_all(False)).pack(side="left")
            tk.Button(btns, text=_tr("Zamknij"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=top.destroy).pack(side="right")

            grid = tk.Frame(pf, bg=BG_PANEL)
            grid.pack(fill="both", expand=True)
            for i, (alias, _target, desc) in enumerate(self._NAV_COMMANDS):
                var = _mk_nav_var(alias)
                tk.Checkbutton(grid, text=f"/{alias} — {_tr(desc)}", variable=var,
                               font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY,
                               selectcolor=BG_INPUT, activebackground=BG_PANEL,
                               activeforeground=FG_WHITE, anchor="w",
                               ).grid(row=i // 2, column=i % 2, sticky="w", pady=2)

        sep_row = len(fields) * 2 + 1
        tk.Frame(body, bg=BORDER_CLR, height=1).grid(
            row=sep_row, column=0, sticky="ew", pady=(10, 6))
        tk.Label(body, text=_tr("Commands"), font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE, anchor="w").grid(
                     row=sep_row + 1, column=0, sticky="w")
        nav_row_fr = tk.Frame(body, bg=BG_PANEL)
        nav_row_fr.grid(row=sep_row + 2, column=0, sticky="w", pady=(4, 0))
        tk.Button(nav_row_fr, text=_tr("Navigation"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=14, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=_nav_popup).pack(side="left")
        nav_count_lbl = tk.Label(nav_row_fr, text=_tr("Wybrane: {n}").format(n=0),
                                 font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY)
        nav_count_lbl.pack(side="left", padx=(8, 0))

        # ── operacje plikowe: przycisk Files (popup) ────────────────────────
        file_vars = {}
        _file_traced = set()

        def _mk_file_var(alias):
            if alias not in file_vars:
                file_vars[alias] = tk.BooleanVar(value=False)
            var = file_vars[alias]
            if alias not in _file_traced:
                var.trace_add("write", lambda *_: _file_count())
                _file_traced.add(alias)
            return var

        def _file_count():
            file_count_lbl.config(text=_tr("Wybrane: {n}").format(
                n=sum(1 for v in file_vars.values() if v.get())))

        def _files_popup():
            top = _popup(dlg)
            top.title(_tr("Operacje na plikach"))
            top.geometry("560x380")
            top.transient(dlg)
            pf = tk.Frame(top, bg=BG_PANEL, padx=14, pady=12)
            pf.pack(fill="both", expand=True)
            btns = tk.Frame(pf, bg=BG_PANEL)
            btns.pack(fill="x", pady=(0, 8))

            def _files_all(state):
                for alias, _op, _d in self._FILE_COMMANDS:
                    _mk_file_var(alias).set(state)
                _file_count()

            tk.Button(btns, text=_tr("Zaznacz wszystkie"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=lambda: _files_all(True)).pack(side="left", padx=(0, 4))
            tk.Button(btns, text=_tr("Odznacz wszystkie"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=lambda: _files_all(False)).pack(side="left")
            tk.Button(btns, text=_tr("Zamknij"), font=("Consolas", 8),
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=2,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=top.destroy).pack(side="right")

            grid = tk.Frame(pf, bg=BG_PANEL)
            grid.pack(fill="both", expand=True)
            for i, (alias, _op, desc) in enumerate(self._FILE_COMMANDS):
                var = _mk_file_var(alias)
                tk.Checkbutton(grid, text=f"/{alias} — {_tr(desc)}", variable=var,
                               font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY,
                               selectcolor=BG_INPUT, activebackground=BG_PANEL,
                               activeforeground=FG_WHITE, anchor="w",
                               ).grid(row=i // 2, column=i % 2, sticky="w", pady=2)

        tk.Button(nav_row_fr, text=_tr("Pliki"), font=FONT_UI,
                  bg=BTN_ACCENT, fg=FG_WHITE, relief="flat", padx=14, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=_files_popup).pack(side="left", padx=(10, 0))
        file_count_lbl = tk.Label(nav_row_fr, text=_tr("Wybrane: {n}").format(n=0),
                                  font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY)
        file_count_lbl.pack(side="left", padx=(8, 0))

        def _create():
            fname = entries["fname"].get().strip()
            if not _creator_valid_filename(fname):
                messagebox.showerror(_tr("Błąd"),
                                     _tr("Nazwa pliku: tylko litery, cyfry i _ (nie może zaczynać się od cyfry)."),
                                     parent=dlg)
                return
            alias = entries["alias"].get().strip()
            if alias and not _creator_valid_alias(alias):
                messagebox.showerror(_tr("Błąd"),
                                     _tr("Alias: tylko litery, cyfry, _ i - (opcjonalnie poprzedzony /)."),
                                     parent=dlg)
                return
            cls_name = "".join(part.capitalize() for part in fname.split("_")) + "Plugin"
            selected = [h for h, v in hook_vars.items() if v.get()]
            nav_sel = [n for n in self._NAV_COMMANDS
                       if n[0] in nav_vars and nav_vars[n[0]].get()]
            file_sel = [f for f in self._FILE_COMMANDS
                        if f[0] in file_vars and file_vars[f[0]].get()]
            src = self._plugin_source(
                fname=fname, cls_name=cls_name,
                disp=entries["disp"].get().strip() or fname,
                version=entries["version"].get().strip() or "1.0.0",
                author=entries["author"].get().strip() or "CodeMate User",
                desc=entries["desc"].get().strip(),
                cat=entries["cat"].get().strip() or "Ogólne",
                homepage=entries["homepage"].get().strip(),
                license_=entries["license"].get().strip(),
                alias=alias.lstrip("/"),
                hooks=selected, nav=nav_sel, files=file_sel)
            path = self._plugin_manager.plugins_dir / f"{fname}.py"
            if path.exists():
                messagebox.showerror(_tr("Błąd"), _tr("Plik już istnieje."), parent=dlg)
                return
            try:
                path.write_text(src, encoding="utf-8")
            except Exception as e:
                messagebox.showerror(_tr("Błąd"), f"{_tr('Nie udało się zapisać pliku:')}\n{e}",
                                     parent=dlg)
                return
            self._plugin_manager.load_plugins()
            self._plugins_apply_disabled()
            self._plugins_refresh()
            try:
                self._plugins_tree.selection_set(fname)
                self._plugins_tree.see(fname)
            except Exception:
                pass
            dlg.destroy()

        btns = tk.Frame(dlg, bg=BG_PANEL)
        btns.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(btns, text=_tr("Utwórz"), font=FONT_UI, bg=BTN_OK, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  activebackground=BTN_OK_HOVER, command=_create).pack(side="left")
        tk.Button(btns, text=_tr("Anuluj"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER, command=dlg.destroy).pack(side="left", padx=6)

        # automatyczny rozmiar okna = dokładnie tyle, ile potrzeba treści;
        # minsize uniemożliwia ucicie zawartości przy zmniejszaniu
        dlg.update_idletasks()
        w = max(dlg.winfo_reqwidth(), 520)
        h = dlg.winfo_reqheight()
        dlg.minsize(w, h)
        dlg.geometry(f"{w}x{h}")

    def _plugins_commands_dialog(self):
        """Okno pomocy / runner komend pluginów (aliasy typu /stats)."""
        if not self._plugin_manager:
            return
        cmds = self._plugin_manager.plugin_commands()
        dlg = _popup(self)
        dlg.title(_tr("Komendy pluginów (/?)"))
        dlg.geometry("620x400")
        dlg.transient(self)

        tree = ttk.Treeview(dlg, columns=("plugin", "desc"), show="tree headings",
                            selectmode="browse")
        tree.heading("#0", text=_tr("Alias"))
        tree.heading("plugin", text=_tr("Plugin"))
        tree.heading("desc", text=_tr("Opis"))
        tree.column("#0", width=140)
        tree.column("plugin", width=160)
        tree.column("desc", width=300)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for alias, meta in cmds.items():
            tree.insert("", "end", iid=alias, text="/" + alias,
                        values=(meta["plugin"], _tr(meta["description"])))
        if not cmds:
            tk.Label(dlg, text=_tr("Brak komend — pluginy mogą definiować "
                                   "PLUGIN_COMMANDS = {alias: opis}."),
                     font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                     wraplength=560, justify="left").pack(padx=10)

        run_row = tk.Frame(dlg, bg=BG_PANEL)
        run_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(run_row, text=_tr("Argumenty:"), font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
        args_var = tk.StringVar()
        tk.Entry(run_row, textvariable=args_var, font=FONT_UI, bg=BG_INPUT,
                 fg=FG_WHITE, relief="flat", width=40,
                 highlightthickness=1, highlightbackground=BORDER_CLR).pack(
                     side="left", padx=6)
        status_lbl = tk.Label(run_row, text="", font=FONT_UI, bg=BG_PANEL,
                              fg=FG_GRAY)
        status_lbl.pack(side="left", padx=8)

        def _run():
            sel = tree.selection()
            if not sel:
                status_lbl.config(text=_tr("Wybierz komendę."), fg="#e0a020")
                return
            alias = sel[0]
            ok = self._plugin_manager.run_command(alias, args_var.get().strip())
            status_lbl.config(
                text=_tr("Wykonano") if ok else _tr("Nie znaleziono komendy"),
                fg=SUCCESS if ok else "#e0a020")

        tk.Button(run_row, text=_tr("Uruchom"), font=FONT_UI, bg=BTN_OK,
                  fg=FG_WHITE, relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground=BTN_OK_HOVER, command=_run).pack(side="right")
        tk.Button(run_row, text=_tr("Zamknij"), font=FONT_UI, bg=BTN_DARK,
                  fg=FG_WHITE, relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER, command=dlg.destroy).pack(side="right", padx=4)

    def _plugins_hooks_dialog(self):
        """Okno z listą hooków i liczbą zarejestrowanych callbacków."""
        if not self._plugin_manager:
            return
        dlg = _popup(self)
        dlg.title(_tr("Hooki pluginów"))
        dlg.geometry("560x420")
        dlg.transient(self)
        tree = ttk.Treeview(dlg, columns=("desc", "count"), show="tree headings",
                            selectmode="browse")
        tree.heading("#0", text=_tr("Hook"))
        tree.heading("desc", text=_tr("Opis"))
        tree.heading("count", text=_tr("Callbacki"))
        tree.column("#0", width=200)
        tree.column("desc", width=280)
        tree.column("count", width=70, anchor="e")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        usage = self._plugin_manager.hook_usage()
        for name, hook in self._plugin_manager.hooks.items():
            tree.insert("", "end", iid=name, text=name,
                        values=(_tr(hook.description), usage.get(name, 0)))
        errs = getattr(self._plugin_manager, "load_errors", [])
        if errs:
            tk.Label(dlg, text=_tr("Błędy ładowania:") + "\n" + "\n".join(errs[:10]),
                     font=FONT_UI, bg=BG_PANEL, fg="#e0a020",
                     justify="left", anchor="w").pack(fill="x", padx=8, pady=(0, 6))
        tk.Button(dlg, text=_tr("Zamknij"), font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER, command=dlg.destroy).pack(pady=6)

    def _plugins_details(self):
        """Okno szczegółów wybranego pluginu."""
        if not self._plugin_manager:
            return
        plugin_name = self._plugins_selected_name()
        if not plugin_name:
            messagebox.showinfo(_tr("Brak wyboru"), _tr("Wybierz plugin z listy."))
            return
        plugin = self._plugin_manager.plugins.get(plugin_name)
        if not plugin:
            return
        info = plugin.get_info()
        path = self._plugin_manager.get_plugin_path(plugin_name)

        dlg = _popup(self)
        dlg.title(f"Plugin: {plugin_name}")
        dlg.geometry("480x380")
        dlg.transient(self)
        body = tk.Frame(dlg, bg=BG_PANEL, padx=14, pady=12)
        body.pack(fill="both", expand=True)

        rows = (("Nazwa", info.get("name", "")), ("Wersja", info.get("version", "")),
                ("Autor", info.get("author", "")), ("Kategoria", info.get("category", "")),
                ("Status", _tr("Włączony") if info.get("enabled") == "True" else _tr("Wyłączony")),
                ("Plik", str(path) if path else "—"))
        for i, (k, v) in enumerate(rows):
            tk.Label(body, text=_tr(k) + ":", font=FONT_BOLD, bg=BG_PANEL,
                     fg=FG_GRAY, anchor="w").grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(body, text=v, font=FONT_UI, bg=BG_PANEL, fg=FG_WHITE,
                     anchor="w", wraplength=380, justify="left").grid(
                         row=i, column=1, sticky="w", padx=(8, 0), pady=2)

        hooks = getattr(plugin, "registered_hooks", [])
        tk.Label(body, text=_tr("Zarejestrowane hooki:") +
                 (", ".join(hooks) if hooks else " —"),
                 font=FONT_UI, bg=BG_PANEL, fg=ACCENT_BLUE, anchor="w",
                 wraplength=420, justify="left").grid(row=len(rows), column=0,
                                                       columnspan=2, sticky="w", pady=(8, 0))
        p_cmds = getattr(plugin, "PLUGIN_COMMANDS", {}) or {}
        if p_cmds:
            tk.Label(body, text=_tr("Komendy:") + " " +
                     ", ".join(f"/{a} — {d}" for a, d in p_cmds.items()),
                     font=FONT_UI, bg=BG_PANEL, fg=SUCCESS, anchor="w",
                     wraplength=420, justify="left").grid(
                         row=len(rows), column=0, columnspan=2, sticky="w")
        if info.get("description"):
            tk.Label(body, text=info["description"], font=FONT_UI, bg=BG_PANEL,
                     fg=FG_GRAY, anchor="w", wraplength=420, justify="left",
                     ).grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        btns = tk.Frame(body, bg=BG_PANEL)
        btns.grid(row=len(rows) + 2, column=0, columnspan=2, pady=(12, 0))

        def _d_btn(text, cmd, color=BTN_DARK, fg=None):
            tk.Button(btns, text=_tr(text), font=FONT_UI, bg=color,
                      fg=fg or FG_WHITE, relief="flat", padx=10, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=cmd).pack(side="left", padx=3)

        _d_btn("Przeładuj", lambda: (self._plugins_reload(plugin_name), dlg.destroy()))
        if path is not None:
            import subprocess
            _d_btn("Otwórz plik", lambda: os.startfile(str(path))
                   if sys.platform.startswith("win")
                   else subprocess.Popen(["xdg-open", str(path)]))
        _d_btn("Usuń", lambda: (self._plugins_delete(plugin_name), dlg.destroy()),
               BTN_ERR, fg=ERROR)
        _d_btn("Zamknij", dlg.destroy)

    def _plugins_marketplace(self):
        """Browses and manages plugins listed in a verified HTTPS catalog."""
        from tkinter import simpledialog
        import threading
        from src.plugin_marketplace import PluginMarketplace

        index_url = simpledialog.askstring(
            _tr("Marketplace pluginów"), _tr("Adres HTTPS pliku index.json:"), parent=self)
        if not index_url:
            return
        plugins_dir = (self._plugin_manager.plugins_dir if self._plugin_manager
                       else APP_DIR / "plugins")
        marketplace = PluginMarketplace(plugins_dir)

        dialog = _popup(self)
        dialog.title(_tr("Marketplace pluginów"))
        dialog.geometry("760x420")
        dialog.transient(self)
        dialog.grab_set()
        tree = ttk.Treeview(dialog, columns=("version", "description"), show="tree headings",
                            selectmode="browse")
        self._trh(tree, "#0", "Plugin")
        tree.heading("version", text=_tr("Wersja"))
        tree.heading("description", text=_tr("Opis"))
        tree.column("#0", width=180)
        tree.column("version", width=90)
        tree.column("description", width=440)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        progress = ttk.Progressbar(dialog, mode="indeterminate")
        progress.pack(fill="x", padx=10, pady=(0, 6))
        status_lbl = self._trw(tk.Label(dialog, text=_tr("Pobieranie katalogu…"), anchor="w"), "Pobieranie katalogu…")
        status_lbl.pack(fill="x", padx=10)
        actions = tk.Frame(dialog)
        actions.pack(fill="x", padx=8, pady=8)
        entries = []
        install_btn = self._trw(ttk.Button(actions, text=_tr("Zainstaluj / aktualizuj")), "Zainstaluj / aktualizuj")
        remove_btn = ttk.Button(actions, text=_tr("Usuń zarządzany plugin")
)
        def finish_async(result=None, error=None, on_success=None, error_prefix=""):
            if not dialog.winfo_exists():
                return
            progress.stop()
            if error is not None:
                status_lbl.configure(text=f"{error_prefix}{error}", fg="#e07070")
                return
            status_lbl.configure(fg=FG_TEXT)
            if on_success:
                on_success(result)
            install_btn.configure(state="normal" if entries else "disabled")
            remove_btn.configure(state="normal" if entries else "disabled")

        def run_async(action, on_success, busy_text, error_prefix=""):
            install_btn.configure(state="disabled")
            remove_btn.configure(state="disabled")
            status_lbl.configure(text=busy_text, fg=FG_TEXT)
            progress.start(10)

            def worker():
                try:
                    result = action()
                except Exception as exc:
                    self._safe_after(0, lambda error=exc: finish_async(
                        error=error, error_prefix=error_prefix))
                else:
                    self._safe_after(0, lambda value=result: finish_async(
                        result=value, on_success=on_success))

            threading.Thread(target=worker, daemon=True, name="plugin-marketplace").start()

        def selected_entry():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo(_tr("Marketplace"), _tr("Wybierz plugin z katalogu."), parent=dialog)
                return None
            return next(item for item in entries if item["name"] == selection[0])

        def install_selected():
            entry = selected_entry()
            if not entry:
                return
            if not messagebox.askyesno(
                    _tr("Zaufanie do pluginu"),
                    _tr("Plugin {name} zawiera wykonywalny kod. Zainstalować wersję {version}?").format(
                        name=entry['name'], version=entry['version']),
                    parent=dialog):
                return

            def installed(path):
                status_lbl.configure(
                    text=_tr("Zainstalowano {name}; uruchom aplikację ponownie, aby go załadować.").format(
                        name=path.name))

            run_async(lambda: marketplace.install(entry), installed,
                      _tr("Instalowanie {name}…").format(name=entry['name']),
                      _tr("Instalacja nie powiodła się: "))

        def remove_selected():
            entry = selected_entry()
            if not entry:
                return
            if not messagebox.askyesno(_tr("Usuń plugin"),
                                       _tr("Usunąć plugin {name} zainstalowany z marketplace?").format(
                                           name=entry['name']),
                                       parent=dialog):
                return
            try:
                removed = marketplace.remove(entry["name"])
            except Exception as exc:
                messagebox.showerror(_tr("Marketplace"), str(exc), parent=dialog)
                return
            if removed and self._plugin_manager and entry["name"] in self._plugin_manager.plugins:
                self._plugin_manager.unload_plugin(entry["name"])
            status_lbl.configure(text=(_tr("Usunięto plugin; zmiana będzie aktywna po restarcie.")
                                       if removed else _tr("Plugin nie jest zarządzany przez marketplace.")))

        install_btn.configure(command=install_selected, state="disabled")
        install_btn.pack(side="left", padx=4)
        remove_btn.configure(command=remove_selected, state="disabled")
        remove_btn.pack(side="left", padx=4)
        ttk.Button(actions, text=_tr("Zamknij"), command=dialog.destroy).pack(side="right", padx=4)

        def catalog_loaded(catalog):
            entries.extend(catalog)
            for entry in catalog:
                tree.insert("", "end", iid=entry["name"], text=entry["name"],
                            values=(entry["version"], entry["description"]))
            status_lbl.configure(text=_tr("{n} pluginów w katalogu").format(n=len(entries)))

        run_async(lambda: marketplace.fetch(index_url.strip()), catalog_loaded,
                  _tr("Pobieranie katalogu…"), _tr("Nie udało się pobrać katalogu: "))

    def _git_status(self):
        """Wyświetla status repozytorium Git."""
        if not self._git or not self._git.is_available():
            self._git_summary.config(text=_tr("Git niedostępny"), fg="#e07070")
            self._git_set_output(_tr("Git nie jest dostępny lub repozytorium nie zostało zainicjalizowane."))
            return
        status = self._git.status()
        staged = set(status.get("staged", []))
        modified = set(status.get("modified", []))
        untracked = set(status.get("untracked", []))
        changed = sorted(staged | modified | untracked)
        self._git_changes_tree.delete(*self._git_changes_tree.get_children())
        self._git_changed_paths = {}
        for index, path in enumerate(changed):
            labels = []
            if path in staged:
                labels.append(_tr("w indeksie"))
            if path in modified:
                labels.append(_tr("zmieniony"))
            if path in untracked:
                labels.append(_tr("nowy"))
            iid = str(index)
            self._git_changed_paths[iid] = path
            self._git_changes_tree.insert(
                "", "end", iid=iid, values=(" + ".join(labels), path))
        branch = status.get("branch") or _tr("(brak brancha)")
        self._git_summary.config(
            text=(f"{branch}  ·  {len(staged)} {_tr('w indeksie')}  ·  "
                  f"{len(modified)} {_tr('zmienionych')}  ·  "
                  f"{len(untracked)} {_tr('nowych')}"),
            fg=FG_WHITE)
        if not changed:
            self._git_set_output(_tr("Working tree czyste."))

    def _git_selected_change_paths(self):
        return [self._git_changed_paths[iid]
                for iid in self._git_changes_tree.selection()
                if iid in self._git_changed_paths]

    def _git_stage_selected(self):
        paths = self._git_selected_change_paths()
        if not paths:
            messagebox.showinfo(_tr("Git"), _tr("Zaznacz pliki do dodania do stage."))
            return
        staged = [path for path in paths if self._git.add_file(APP_DIR / path)]
        if len(staged) != len(paths):
            messagebox.showerror(
                _tr("Git"), _tr("Nie udało się dodać wszystkich zaznaczonych plików do stage."))
        self._git_refresh()

    def _git_unstage_selected(self):
        paths = self._git_selected_change_paths()
        if not paths:
            messagebox.showinfo(_tr("Git"), _tr("Zaznacz pliki do usunięcia ze stage."))
            return
        unstaged = [path for path in paths if self._git.unstage_file(APP_DIR / path)]
        if len(unstaged) != len(paths):
            messagebox.showerror(
                _tr("Git"), _tr("Nie udało się usunąć wszystkich zaznaczonych plików ze stage.")
                + (f"\n{self._git.last_error}" if self._git.last_error else ""))
        self._git_refresh()

    def _git_discard_worktree_selected(self):
        paths = self._git_selected_change_paths()
        if not paths:
            messagebox.showinfo(_tr("Git"), _tr("Zaznacz pliki, których zmiany robocze chcesz odrzucić."))
            return
        status = self._git.status()
        modified = set(status.get("modified", []))
        untracked = set(status.get("untracked", []))
        eligible = [path for path in paths if path in modified and path not in untracked]
        if not eligible:
            messagebox.showinfo(
                _tr("Git"),
                _tr("Brak zaznaczonych śledzonych plików ze zmianami roboczymi do odrzucenia."))
            return
        preview = "\n".join(eligible[:10])
        if len(eligible) > 10:
            preview += f"\n… (+{len(eligible) - 10})"
        confirmed = messagebox.askyesno(
            _tr("Odrzuć zmiany robocze"),
            _tr("Odrzucić zmiany robocze w {count} plikach?\n"
                "Treść zostanie przywrócona do wersji staged; zmiany staged pozostaną.\n\n{files}")
            .format(count=len(eligible), files=preview))
        if not confirmed:
            return
        restored = [path for path in eligible
                    if self._git.restore_worktree_file(APP_DIR / path)]
        if len(restored) != len(eligible):
            messagebox.showerror(
                _tr("Git"),
                _tr("Nie udało się odrzucić zmian dla wszystkich plików.")
                + (f"\n{self._git.last_error}" if self._git.last_error else ""))
        self._git_refresh()

    def _git_history(self):
        """Wyświetla historię commitów."""
        if not self._git or not self._git.is_available():
            return
        self._git_history_tree.delete(*self._git_history_tree.get_children())
        self._git_history_items = {}
        history = self._git.get_history(limit=50)
        for commit in history:
            commit_hash = commit.get("hash", "")
            if not commit_hash:
                continue
            self._git_history_items[commit_hash] = commit
            self._git_history_tree.insert(
                "", "end", iid=commit_hash,
                values=(commit_hash[:8], commit.get("date", ""),
                        commit.get("author", ""), commit.get("message", "")))
        if not history:
            self._git_set_output(_tr("Brak commitów do wyświetlenia."))

    def _git_show_commit(self, _event=None):
        try:
            selection = self._git_history_tree.selection()
            if not selection or not self._git:
                return
            commit = self._git_history_items.get(selection[0], {})
            diff = self._git.get_commit_diff(selection[0])
            header = (f"{_tr('Commit')}: {selection[0]}\n"
                  f"{_tr('Autor')}: {commit.get('author', '')}\n"
                  f"{_tr('Data')}: {commit.get('date', '')}\n"
                  f"{_tr('Wiadomość')}: {commit.get('message', '')}\n\n")
            self._git_set_output(header + (diff or _tr("Brak diffu dla tego commita.")))
        except Exception as e:
            logging.error("Błąd podglądu commita Git: %s", e, exc_info=True)
            try:
                self._git_set_output(f"{_tr('Błąd')}: {e}")
            except Exception:
                pass

    def _git_show_change(self, _event=None):
        try:
            selection = self._git_changes_tree.selection()
            if not selection or not self._git:
                return
            path = self._git_changed_paths.get(selection[0], "")
            if not path:
                return
            # Buforowany status z ostatniego odświeżenia (uniknięcie subprocess
            # przy każdym kliknięciu w listę zmian).
            untracked = set(getattr(self, "_git_last_untracked", []))
            if path in untracked:
                self._git_set_output(
                    f"{_tr('Nowy plik (nieśledzony)')}: {path}\n"
                    f"{_tr('Dodaj plik do repozytorium przed podglądem diffu.')}")
                return
            diff = self._git.get_diff("HEAD", file_path=APP_DIR / path)
            self._git_set_output(diff or f"{_tr('Brak diffu dla')}: {path}")
        except Exception as e:
            logging.error("Błąd podglądu zmiany Git: %s", e, exc_info=True)
            try:
                self._git_set_output(f"{_tr('Błąd')}: {e}")
            except Exception:
                pass

    def _git_set_output(self, text):
        self._git_output.config(state="normal")
        self._git_output.delete("1.0", "end")
        self._git_output.insert("1.0", text)
        self._git_output.config(state="disabled")

    def _git_refresh(self):
        """Odświeża zakładkę Git w wątku tła — UI nie blokuje się na subprocess.

        Status, branchę i historię pobiera worker; wynik aplikuje w wątku UI
        przez ``after``. Wskaźnik "odświeżanie…" pokazywany w podsumowaniu.
        """
        git = self._ensure_git()
        if not git or not git.is_available():
            self._git_summary.config(text=_tr("Git niedostępny"), fg="#e07070")
            self._git_set_output(_tr("Git nie jest dostępny lub repozytorium nie zostało zainicjalizowane."))
            self._git_changes_tree.delete(*self._git_changes_tree.get_children())
            self._git_history_tree.delete(*self._git_history_tree.get_children())
            self._git_branch_combo.configure(values=[])
            return
        self._git_summary.config(text=_tr("sprawdzanie…"), fg=FG_GRAY)
        self._git_refresh_seq = getattr(self, "_git_refresh_seq", 0) + 1
        seq = self._git_refresh_seq

        def worker():
            try:
                status = git.status()
            except Exception:
                status = {}
            try:
                branches = git.get_branches()
            except Exception:
                branches = []
            try:
                current = git.get_current_branch()
            except Exception:
                current = None
            try:
                history = git.get_history(limit=50)
            except Exception:
                history = []
            self._safe_after(0, lambda: self._git_apply_refresh(seq, status, branches,
                                                           current, history))

        threading.Thread(target=worker, daemon=True).start()

    def _git_apply_refresh(self, seq, status, branches, current, history):
        """Aplikuje wynik asynchronicznego odświeżenia Git (wątek UI)."""
        # Zignoruj wyniki starszego odświeżenia (np. po szybkim przełączeniu zakładek).
        if seq != getattr(self, "_git_refresh_seq", seq):
            return
        staged = set(status.get("staged", []))
        modified = set(status.get("modified", []))
        untracked = set(status.get("untracked", []))
        self._git_last_untracked = untracked
        changed = sorted(staged | modified | untracked)
        self._git_changes_tree.delete(*self._git_changes_tree.get_children())
        self._git_changed_paths = {}
        for index, path in enumerate(changed):
            labels = []
            if path in staged:
                labels.append(_tr("w indeksie"))
            if path in modified:
                labels.append(_tr("zmieniony"))
            if path in untracked:
                labels.append(_tr("nowy"))
            iid = str(index)
            self._git_changed_paths[iid] = path
            self._git_changes_tree.insert(
                "", "end", iid=iid, values=(" + ".join(labels), path))
        branch = current or status.get("branch") or _tr("(brak brancha)")
        self._git_summary.config(
            text=(f"{branch}  ·  {len(staged)} {_tr('w indeksie')}  ·  "
                  f"{len(modified)} {_tr('zmienionych')}  ·  "
                  f"{len(untracked)} {_tr('nowych')}"),
            fg=FG_WHITE)
        self._git_branch_combo.configure(values=branches)
        self._git_branch_var.set(current or "")
        self._git_history_tree.delete(*self._git_history_tree.get_children())
        self._git_history_items = {}
        for commit in history:
            commit_hash = commit.get("hash", "")
            if not commit_hash:
                continue
            self._git_history_items[commit_hash] = commit
            self._git_history_tree.insert(
                "", "end", iid=commit_hash,
                values=(commit_hash[:8], commit.get("date", ""),
                        commit.get("author", ""), commit.get("message", "")))
        if not changed and not history:
            self._git_set_output(_tr("Working tree czyste."))

    def _git_checkout_branch(self):
        branch = self._git_branch_var.get().strip()
        if not branch or not self._git:
            return
        current = self._git.get_current_branch()
        if branch == current:
            return
        if not messagebox.askyesno(
                _tr("Przełącz branch"),
                _tr("Przełączyć z '{current}' na '{branch}'?").format(
                    current=current or "?", branch=branch)):
            return
        if self._git.checkout_branch(branch):
            self._autoload_db()
            self._git_refresh()
        else:
            messagebox.showerror(_tr("Git"), _tr("Nie udało się przełączyć brancha."))

    def _git_create_branch(self):
        if not self._git or not self._git.is_available():
            return
        from tkinter import simpledialog
        name = simpledialog.askstring(
            _tr("Nowy branch"), _tr("Nazwa brancha:"), parent=self)
        if not name:
            return
        name = name.strip()
        if not name or name.startswith("-"):
            messagebox.showerror(_tr("Git"), _tr("Nieprawidłowa nazwa brancha."))
            return
        if self._git.create_branch(name):
            self._git_refresh()
            self._git_branch_var.set(name)
            self._git_checkout_branch()
        else:
            messagebox.showerror(_tr("Git"), _tr("Nie udało się utworzyć brancha."))

    def _git_branches(self):
        """Wyświetla listę branchów."""
        if not self._git or not self._git.is_available():
            return
        branches = self._git.get_branches()
        current = self._git.get_current_branch()
        self._git_branch_combo.configure(values=branches)
        self._git_branch_var.set(current or "")

    def _git_commit(self):
        """Tworzy commit z własną wiadomością."""
        if not self._git or not self._git.is_available():
            messagebox.showerror(_tr("Błąd"), _tr("Git nie jest dostępny"))
            return
        from tkinter import simpledialog
        msg = simpledialog.askstring(_tr("Commit"), _tr("Wpisz wiadomość commita:"))
        if msg:
            if self._git.commit(msg):
                messagebox.showinfo(_tr("Sukces"), _tr("Commit utworzony"))
                self._git_refresh()
            else:
                messagebox.showerror(_tr("Błąd"), _tr("Nie udało się utworzyć commita"))

    def _git_push(self):
        """Wypycha zmiany do zdalnego repozytorium."""
        if not self._git or not self._git.is_available():
            messagebox.showerror(_tr("Błąd"), _tr("Git nie jest dostępny"))
            return
        if self._git.push():
            messagebox.showinfo(_tr("Sukces"), _tr("Push zakończony"))
            self._git_refresh()
        else:
            messagebox.showerror(
                _tr("Błąd"), f"{_tr('Nie udało się wykonać push:')}\n{self._git.last_error}")

    def _git_pull(self):
        """Pobiera zmiany ze zdalnego repozytorium."""
        if not self._git or not self._git.is_available():
            messagebox.showerror(_tr("Błąd"), _tr("Git nie jest dostępny"))
            return
        if self._git.pull():
            messagebox.showinfo(_tr("Sukces"), _tr("Pull fast-forward zakończony"))
            self._autoload_db()
            self._git_refresh()
        else:
            messagebox.showerror(
                _tr("Konflikt synchronizacji"),
                _tr("Pull --ff-only nie powiódł się. Lokalna baza nie została scalona ani nadpisana.") + "\n\n"
                f"{self._git.last_error}")

    def _git_configure_remote(self):
        """Adds or updates a Git remote selected by the user."""
        from tkinter import simpledialog
        if not self._git or not self._git.is_available():
            messagebox.showerror(_tr("Błąd"), _tr("Git nie jest dostępny"))
            return
        remote = simpledialog.askstring(
            _tr("Git remote"), _tr("Nazwa remote:"), initialvalue="origin", parent=self)
        if not remote:
            return
        url = simpledialog.askstring(
            _tr("Git remote"), _tr("Adres repozytorium (HTTPS lub SSH):"), parent=self)
        if not url:
            return
        if self._git.set_remote(remote.strip(), url.strip()):
            messagebox.showinfo(
                _tr("Git remote"), _tr("Skonfigurowano remote {remote}.").format(
                    remote=remote.strip()))
        else:
            messagebox.showerror(_tr("Git remote"), self._git.last_error)

    def _git_toggle_auto_push(self):
        self._cfg["git_auto_push"] = "1" if self._git_auto_push_var.get() else "0"
        cfg_save(self._cfg)
        self._git_auto_push = self._git_auto_push_var.get()

    def _git_sync_database(self):
        if not self._git or not self._git.is_available():
            messagebox.showerror(_tr("Błąd"), _tr("Git nie jest dostępny"))
            return
        if self._git.sync_file(Path(self.db_path)):
            messagebox.showinfo(
                _tr("Synchronizacja"),
                _tr("Baza została zacommitowana i wypchnięta do remote."))
            self._git_refresh()
        else:
            messagebox.showerror(
                _tr("Synchronizacja"),
                _tr("Synchronizacja nie powiodła się. Lokalny commit pozostaje zachowany.") + "\n\n"
                f"{self._git.last_error}")

    def _plugin_terminal_command(self, alias, args=""):
        """Dispatch komendy pluginu wpisanej w terminalu jako /alias args."""
        if not self._plugin_manager:
            return False
        return bool(self._plugin_manager.run_command(alias, args))

    def _show_terminal(self):
        self.main_frames["terminal"].pack(fill="both", expand=True)
        self._terminal_widget.command.focus_set()


def _is_attr(name):
    """Rozstrzyga, czy nazwa `self._x` to atrybut (pole), a nie pomylona metoda:
    pole = w tej samej klasie występuje jako cel przypisania (self._x = ...)."""
    return name in _SELF_ATTRS


_SELF_ATTRS = set()
# nazwy pól-widżetów tworzonych warunkowo w runnerze (przyciski, etykiety)
_WIDGET_HINTS = ("_btn", "_lbl", "_entry", "_tree", "_list", "_out", "_text",
                 "_var", "_combo", "_cb", "_frame", "_pane", "_spin")


def self_check(lista_skryptow=None):
    """Statyczna kontrola kodu aplikacji: składnia, duplikaty metod, puste klasy.
    Zwraca kod wyjścia (0 = OK, 1 = problemy). Bez GUI."""
    import ast
    import collections
    src_path = os.path.abspath(__file__)
    with open(src_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    problems = []
    try:
        tree = ast.parse(src, filename=src_path)
    except SyntaxError as e:
        print(f"[BŁĄD] składnia: linia {e.lineno}: {e.msg}")
        return 1

    # duplikaty metod w klasach — w Pythonie cicho nadpisują poprzednią definicję
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        seen = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name in seen:
                    problems.append(
                        f"duplikat metody {node.name}.{item.name}: "
                        f"linia {item.lineno} nadpisuje linię {seen[item.name]}")
                else:
                    seen[item.name] = item.lineno

    # metody zwołane, ale nieistniejące na `self` klasy CodeMate
    cls = next((n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == "CodeMate"), None)
    if cls is not None:
        defined = {i.name for i in cls.body
                   if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))}
        # pola klasowe: _EXT_KAT = {...}, _SKRYPT_EXT = (...)
        for node in cls.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        defined.add(t.id)
        # atrybuty instancji: self._x = ... (w tym w całej klasie)
        for node in ast.walk(cls):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                for sub in ast.walk(t):
                    if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                            and sub.value.id in ("self", "app", "root")):
                        _SELF_ATTRS.add(sub.attr)
                        defined.add(sub.attr)

        defined |= {"__getattr__", "after", "after_cancel", "destroy", "update",
                    "__class__", "int", "str", "len", "enumerate", "range", "list", "dict",
                    "title", "geometry", "configure", "config", "bind_all", "unbind_all",
                    "bind", "protocol", "resizable", "clipboard_clear", "clipboard_append",
                    "wait_window", "focus_get", "winfo_children", "mainloop", "tk"}
        methods = [n for n in ast.walk(cls)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        calls = collections.Counter()
        for fn in methods:
            for call in ast.walk(fn):
                if (isinstance(call, ast.Attribute) and isinstance(call.value, ast.Name)
                        and call.value.id in ("self", "app", "root")
                        and call.attr.startswith("_")):
                    calls[call.attr] += 1
        missing = sorted(n for n in calls if n not in defined and not _is_attr(n)
                         and not any(w in n for w in _WIDGET_HINTS))
        if missing:
            problems.append("wywołania nieistniejących metod self: " + ", ".join(missing))

    # klasa / metoda zdefiniowana podwójnie na poziomie modułu
    top_funcs = collections.Counter(n.name for n in tree.body
                                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    for name, cnt in top_funcs.items():
        if cnt > 1:
            problems.append(f"duplikat funkcji modułu: {name} ({cnt}×)")

    # pusta apteczka: sprawdzenie, że wszystkie `self._xxx` z __getattr__ są spójne
    print(f"self-check: {src_path}")
    print(f"  linie kodu: {len(src.splitlines())}, klas: "
          f"{sum(isinstance(n, ast.ClassDef) for n in tree.body)}")
    if lista_skryptow is not None:
        print(f"  rekordów w bazie: {len(lista_skryptow)}")
    if problems:
        for p in problems:
            print("  [UWAGA] " + p)
        return 1
    print("  ✓ brak problemów struktury kodu")
    return 0


def verify_db(lista, db_path):
    """Sprawdza spójność bazy na surowym pliku (bez normalizacji).
    Przydatne w CI / przed backupem. Zwraca kod wyjścia."""
    problems, warn = [], []
    try:
        with open(db_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception as e:
        print(f"--verify: {db_path}\n  [BŁĄD] nie można odczytać pliku: {e}")
        return 2
    if isinstance(raw, dict):
        schema = raw.get("schema")
        data = raw.get("skrypty", [raw] if "nazwa" in raw else [])
        if schema not in (None, DB_SCHEMA):
            problems.append(f"schema pliku: {schema} (oczekiwana {DB_SCHEMA})")
    else:
        data = raw if isinstance(raw, list) else []
        warn.append("format v1 (lista) — zostanie zmigrowany przy wczytaniu")
    if not isinstance(data, list):
        print("--verify: niepoprawny format (oczekiwano listy skryptów)")
        return 2

    ids, checks, nazwy = {}, {}, {}
    for i, sc in enumerate(data):
        if not isinstance(sc, dict):
            problems.append(f"rekord #{i}: nie jest obiektem")
            continue
        nazwa = sc.get("nazwa") or f"rekord #{i}"
        sid = sc.get("id")
        if not sid:
            problems.append(f"{nazwa}: brak id")
        elif sid in ids:
            problems.append(f"{nazwa}: duplikat id (ten sam co {ids[sid]})")
        else:
            ids[sid] = nazwa
        for k in ("nazwa", "kategoria", "kod"):
            if k not in sc:
                problems.append(f"{nazwa}: brak pola '{k}'")
        if sc.get("kategoria") not in CATEGORIES:
            problems.append(f"{nazwa}: nieznana kategoria '{sc.get('kategoria')}'")
        if nazwa in nazwy:
            problems.append(f"{nazwa}: zduplikowana nazwa")
        nazwy[nazwa] = True
        cs = kod_checksum(sc.get("kod", ""))
        if sc.get("checksum") and sc["checksum"] != cs:
            problems.append(f"{nazwa}: checksum nie zgadza się z kodem")
        checks.setdefault(cs, []).append(nazwa)
        if sc.get("usuniety"):
            warn.append(f"{nazwa}: w koszu ({sc.get('usuniety')})")
        for k in ("historia", "wersje"):
            if k in sc and not isinstance(sc[k], list):
                problems.append(f"{nazwa}: pole '{k}' nie jest listą")
        if "harmonogram" in sc and sc["harmonogram"] is not None \
                and not isinstance(sc["harmonogram"], dict):
            problems.append(f"{nazwa}: pole 'harmonogram' nie jest obiektem")
    for cs, lst in checks.items():
        if len(lst) > 1:
            warn.append("identyczna treść: " + " ⟷ ".join(lst))

    print(f"--verify: {db_path}")
    print(f"  rekordów: {len(data)} (w koszu: {sum(1 for s in data if isinstance(s, dict) and s.get('usuniety'))})")
    for w in warn:
        print("  [INFO] " + w)
    for p in problems:
        print("  [BŁĄD] " + p)
    print("  ✓ baza spójna" if not problems else f"  ✗ problemów: {len(problems)}")
    return 0 if not problems else 1


def print_stats(lista, db_path):
    """Podsumowanie bazy w konsoli: liczby, kategorie, tagi, uruchomienia, harmonogram."""
    from collections import Counter
    live = [s for s in lista or [] if not s.get("usuniety")]
    kosz = len(lista or []) - len(live)
    kat = Counter(s.get("kategoria", "?") for s in live)
    tagi = Counter()
    linie = 0
    runs = 0
    for s in live:
        for t in str(s.get("tagi", "")).split(","):
            t = t.strip()
            if t:
                tagi[t] += 1
        linie += len((s.get("kod") or "").splitlines())
        runs += int(s.get("uruchomien") or 0)
    plany = [s for s in live if isinstance(s.get("harmonogram"), dict)]
    aktywne = [s for s in plany if s["harmonogram"].get("aktywny")]
    zaufane = sum(1 for s in live if s.get("zaufany"))
    z_wersjami = sum(1 for s in live if s.get("wersje"))
    print(f"== CodeMate — {db_path}")
    print(f"  skryptów: {len(live)}   w koszu: {kosz}   linii kodu: {linie:,}")
    print(f"  uruchomień: {runs}   zaufanych: {zaufane}/{len(live)}   z historią wersji: {z_wersjami}")
    print(f"  plany harmonogramu: {len(plany)} (aktywne: {len(aktywne)})")
    print("  kategorie:")
    for k, n in kat.most_common():
        print(f"    {k:<12} {n:4}  {'█' * min(30, n)}")
    if tagi:
        print("  top tagi:")
        for t, n in tagi.most_common(10):
            print(f"    {t:<16} {n:4}")
    return 0


def print_run_errors(lista, limit=10):
    """Ostatnie nieudane uruchomienia ze wszystkich skryptów (najnowsze pierwsze)."""
    rows = []
    for s in lista or []:
        for h in (s.get("historia") or []):
            if h.get("rc") not in (0, None):
                rows.append((h.get("ts", ""), s.get("nazwa", "?"), h.get("rc"),
                             h.get("ms"), h.get("args") or "",
                             (h.get("out") or "").splitlines()[-1][:70] if h.get("out") else ""))
    rows.sort(key=lambda r: r[0], reverse=True)
    if not rows:
        print("brak nieudanych uruchomień w historii")
        return 0
    print(f"== Ostatnie błędy uruchomień (max {limit})")
    for ts, nazwa, rc, ms, args, last in rows[:max(1, limit)]:
        print(f"  {ts}  {nazwa:<26} rc={rc:<4} {ms:6} ms  args={args or '-'}")
        if last:
            print(f"      {last}")
    return 1   # kod 1 = sę błędy (przydatne w CI)


def print_toc():
    """Spis treści pliku: klasy, główne funkcje i baner-sekcje z numerami linii."""
    src_path = os.path.abspath(__file__)
    with open(src_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    print(f"SPIS TREŚCI — {os.path.basename(src_path)} ({len(lines)} linii)")
    for i, line in enumerate(lines, 1):
        s = line.rstrip("\n")
        if s.startswith("class "):
            print(f"{i:6}  {s}")
        elif s.startswith("def ") or (s.startswith("    def ") and s[4:].split("(")[0].strip()
                                       in ("__init__", "main", "_autoload_db", "save_db",
                                           "_runner_start", "_sched_tick", "_runner_finish")):
            print(f"{i:6}    {s.strip()}")
        elif s.startswith("# ══") and i + 1 < len(lines):
            nxt = lines[i].strip()
            if nxt and not nxt.startswith("# ══"):
                print(f"{i:6}  ▸ {nxt.lstrip('# ')}")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# SEKCJA 8: CLI — interfejs wiersza poleceń
# ══════════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    import argparse

    def _cli_main(argv=None):
        """Tryb wiersza poleceń: lista, eksport, import, uruchomienie skryptu, GUI."""
        p = argparse.ArgumentParser(
            prog="baza_skryptow.py",
            description="CodeMate v%s — jednoplikowa baza + runner skryptów." % APP_VER,
            epilog="Bez argumentów uruchamia GUI. Przykłady:\n"
                   "  python baza_skryptow.py --list\n"
                   "  python baza_skryptow.py --backup backup.json\n"
                   "  python baza_skryptow.py --run \"Skrypt A\" --timeout 30\n"
                   "  python baza_skryptow.py --headless --export out.json")
        p.add_argument("--db", default="", help="ścieżka pliku bazy (domyślnie baza_skryptow.json)")
        p.add_argument("--toc", action="store_true",
                       help="wypisz spis treści pliku (klasy i sekcje z numerami linii)")
        p.add_argument("--list", action="store_true", help="wypisz skrypty z bazy")
        p.add_argument("--stats", action="store_true",
                       help="podsumowanie bazy: skrypty, kategorie, uruchomienia, harmonogram)")
        p.add_argument("--run-errors", action="store_true", dest="run_errors",
                       help="pokaż ostatnie nieudane uruchomienia (z historii)")
        p.add_argument("--verify", action="store_true",
                       help="sprawdź spójność bazy (duplikaty id/checksum, brakujące pola)")
        p.add_argument("--self-check", action="store_true", dest="self_check",
                       help="sprawdź kod aplikacji (składnia, duplikaty metod, martwe nazwy)")
        p.add_argument("--export", metavar="PLIK", help="zapisz kopię bazy do pliku JSON")
        p.add_argument("--import", metavar="PLIK", dest="import_",
                       help="scal skrypty z pliku JSON do bazy")
        p.add_argument("--backup", metavar="PLIK", help="kopia zapasowa bazy (alias --export)")
        p.add_argument("--run", metavar="NAZWA", help="uruchom skrypt z bazy po nazwie")
        p.add_argument("--search", metavar="FRAZA",
                       help="szukaj w nazwie/tagach/opisie/kodzie (przypadek ignorowany)")
        p.add_argument("--show", metavar="NAZWA", help="pokaż kod skryptu po nazwie")
        p.add_argument("--timeout", type=int, default=None, help="timeout uruchomienia [s]")
        p.add_argument("--args", default="", help="argumenty dla uruchamianego skryptu")
        p.add_argument("--limit", type=int, default=10, help="ile wpisów w --run-errors (domyślnie 10)")
        p.add_argument("--headless", action="store_true", help="nie otwieraj GUI")
        p.add_argument("--gui-runner", action="store_true", help="otwórz GUI na zakładce Runner")
        p.add_argument("--version", action="version", version=f"CodeMate v{APP_VER} (schema {DB_SCHEMA})")
        opts = p.parse_args(argv)

        cfg = cfg_load()
        db_path = os.path.abspath(opts.db) if opts.db else (cfg.get("db_path") or DB_FILE)
        if opts.db:
            # jawnie wskazana baza zostaje zapamiętana także dla GUI i kolejnych wywołań
            cfg["db_path"] = db_path
            cfg_save(cfg)
        if os.path.exists(db_path):
            try:
                lista, notes = db_read(db_path)
                for n in notes:
                    print("[baza]", n, file=sys.stderr)
            except Exception as e:
                print(f"[błąd] nie można wczytać bazy {db_path}: {e}", file=sys.stderr)
                return 2
        else:
            lista = []

        # --toc i --self-check działają bez wczytywania bazy
        if opts.toc:
            return print_toc()

        if opts.self_check:
            return self_check(lista)

        if opts.verify:
            return verify_db(lista or [], db_path)

        if opts.stats:
            return print_stats(lista or [], db_path)

        if opts.run_errors:
            return print_run_errors(lista or [], opts.limit)

        if opts.list:
            for sc in lista or []:
                if sc.get("usuniety"):
                    continue
                runs = int(sc.get("uruchomien") or 0)
                print(f"{sc.get('nazwa','?'):<30} [{sc.get('kategoria','?'):<10}]"
                      f"  {(sc.get('tagi') or '-'):<20} uruchomień: {runs}")
            print(f"-- razem: {len(lista or [])} skrypt(ów) w {db_path}", file=sys.stderr)

        if opts.import_:
            try:
                incoming, notes = db_read(opts.import_)
            except Exception as e:
                print(f"[błąd] import: {e}", file=sys.stderr)
                return 2
            by_name = {s.get("nazwa"): s for s in (lista or [])}
            by_id = {s.get("id"): s for s in (lista or [])}
            added = updated = 0
            for sc in incoming:
                old = by_id.get(sc["id"]) or by_name.get(sc["nazwa"])
                if old is None:
                    lista.append(sc); added += 1
                else:
                    old.update({k: sc[k] for k in ("kategoria", "tagi", "opis", "kod", "checksum")})
                    updated += 1
            db_write(db_path, lista, backup_count=int(cfg.get("backup_count", "3")))
            print(f"Import: +{added} nowych, ~{updated} zaktualizowanych → {db_path}")

        if opts.export or opts.backup:
            target = os.path.abspath(opts.export or opts.backup)
            db_write(target, [s for s in (lista or []) if not s.get("usuniety")], backup_count=0)
            print(f"Zapisano {len(lista or [])} skrypt(ów) → {target}")

        if opts.search:
            fraza = opts.search.casefold()
            hits = []
            for sc in lista or []:
                if sc.get("usuniety"):
                    continue
                hay = " ".join(str(sc.get(k, "")) for k in
                               ("nazwa", "tagi", "opis", "kategoria", "kod")).casefold()
                if fraza in hay:
                    hits.append(sc)
            for sc in hits:
                runs = int(sc.get("uruchomien") or 0)
                print(f"{sc.get('nazwa','?'):<30} [{sc.get('kategoria','?'):<10}]"
                      f"  {(sc.get('tagi') or '-'):<20} uruchomień: {runs}")
            print(f"-- znaleziono: {len(hits)} skrypt(ów) dla '{opts.search}'",
                  file=sys.stderr)
            if opts.headless:
                return 0

        if opts.show:
            sc = next((s for s in (lista or []) if s.get("nazwa") == opts.show), None)
            if sc is None:
                print(f"[błąd] nie znaleziono skryptu '{opts.show}' (użyj --list)", file=sys.stderr)
                return 1
            print(f"# {sc.get('nazwa')} [{sc.get('kategoria')}]  zmeniony: "
                  f"{sc.get('zmieniony', '?')}")
            print(sc.get("kod", ""))
            if opts.headless:
                return 0

        if opts.run:
            sc = next((s for s in (lista or []) if s.get("nazwa") == opts.run), None)
            if sc is None:
                print(f"[błąd] nie znaleziono skryptu '{opts.run}' (użyj --list)", file=sys.stderr)
                return 1
            import shlex, subprocess, time
            kat = sc.get("kategoria", "Other")
            workdir = tempfile.mkdtemp(prefix="bs_cli_")
            interpreter = cfg.get("interpreter") or ""
            if kat == "Python" and interpreter and not os.path.exists(interpreter):
                interpreter = ""
            path = runner_save_temp(sc.get("kod", ""), kat, workdir, interpreter)
            cmd = runner_cmd(kat, path, shlex.split(opts.args, posix=False) if opts.args else [], interpreter)
            if not cmd:
                print(f"[błąd] brak interpretera dla kategorii {kat}", file=sys.stderr)
                return 1
            timeout = opts.timeout if opts.timeout is not None else int(cfg.get("timeout", "60") or 60)
            t0 = time.time()
            try:
                proc = subprocess.run(cmd, cwd=workdir, timeout=timeout or None,
                                      capture_output=False, text=True)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                print(f"[timeout] przekroczono {timeout}s", file=sys.stderr)
                rc = -9
            except FileNotFoundError as e:
                print(f"[błąd] interpreter: {e}", file=sys.stderr)
                return 1
            dt = time.time() - t0
            sc["uruchomien"] = int(sc.get("uruchomien") or 0) + 1
            sc["ostatni_run"] = now_str()
            sc["ostatni_wynik"] = "OK" if rc == 0 else f"błąd({rc})"
            sc["ostatni_czas_ms"] = int(dt * 1000)
            db_write(db_path, lista, backup_count=int(cfg.get("backup_count", "3")))
            print(f"\n[{sc['nazwa']}] kod={rc} czas={dt:.2f}s", file=sys.stderr)
            return 0 if rc == 0 else rc if 0 < rc < 128 else 1

        if opts.export or opts.backup or opts.import_ or opts.list or opts.run \
                or opts.headless or opts.search or opts.show:
            return 0

        app = CodeMate(start_runner=opts.gui_runner)
        app.mainloop()
        return 0

    sys.exit(_cli_main())
