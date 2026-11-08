# ── Metadane ──────────────────────────────────────────────────────────────────
# autor:   Sebastian Januchowski
# company: polsoft.ITS(TM) Group
# web:     www.polsoft.gt.tc
# github:  https://github.com/seb07uk
# email:   polsoft.its@fastservice.com
# wersja:  3.0
# ──────────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import sys
import json
import uuid
import hashlib
import tempfile
import datetime

# ── Kodowanie konsoli: UTF-8 (polskie znaki w --list / --run) ────────────────
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURACJA — baza w jednym pliku JSON obok skryptu (+ plik .cfg)
# ══════════════════════════════════════════════════════════════════════════════
DB_SCHEMA = 2              # wersja formatu pliku bazy — podnoś przy zmianie struktury
APP_VER   = "3.0"          # wersja aplikacji (metadane / --version)

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(APP_DIR, "baza_skryptow.json")
CFG_FILE = os.path.join(APP_DIR, "baza_skryptow.cfg")
CFG_KEYS = {
    "db_path":        "",     # puste = DB_FILE
    "autosave":       "1",    # 1 = autosave po zapisie/usunięciu
    "backup_count":   "3",    # ile kopii .bak trzymać
    "interpreter":    "",     # puste = sys.executable
    "timeout":        "60",   # sekundy dla runnera
    "runner_args":    "",
    "runner_console": "0",    # 1 = uruchamiaj w nowej konsoli
}

CATEGORIES = ["Python", "Bash", "PowerShell", "JavaScript", "SQL", "Other"]


def cfg_load():
    """Wczytuje konfigurację z pliku .cfg; brak pliku = wartości domyślne."""
    import configparser
    cp = configparser.ConfigParser()
    try:
        cp.read(CFG_FILE, encoding="utf-8")
    except Exception:
        return dict(CFG_KEYS)
    out = dict(CFG_KEYS)
    if cp.has_section("baza"):
        for k in CFG_KEYS:
            if cp.has_option("baza", k):
                out[k] = cp.get("baza", k)
    if not out.get("db_path"):
        out["db_path"] = DB_FILE
    return out


def cfg_save(values):
    """Zapisuje konfigurację do pliku .cfg (atomowo)."""
    import configparser
    cp = configparser.ConfigParser()
    cp.add_section("baza")
    for k in CFG_KEYS:
        cp.set("baza", k, str(values.get(k, CFG_KEYS[k])))
    tmp = CFG_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            cp.write(fh)
        os.replace(tmp, CFG_FILE)
    except OSError:
        pass


def kod_checksum(kod):
    """Skrót SHA-256 kodu — do wykrywania duplikatów treści."""
    return hashlib.sha256((kod or "").encode("utf-8", "replace")).hexdigest()


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sc_normalize(sc, kat_default="Other"):
    """Sprowadza rekord do jednolitego słownika i uzupełnia brakujące pola."""
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
    return sc


def db_wrap(skrypty):
    """Opakowuje listę rekordów w strukturę pliku (schema + metadane)."""
    return {
        "schema":   DB_SCHEMA,
        "app":      f"Baza Skryptów v{APP_VER}",
        "exported": now_str(),
        "skrypty":  list(skrypty),
    }


def db_to_list(data):
    """
    Migracja danych dowolnej wersji do listy rekordów. Toleruje:
      v2: {"schema": 2, "skrypty": [...]}   — nowy format
      v1: [ {"nazwa": ...}, ... ]           — stary eksport (lista)
      v0: {"skrypty": [...]}                — dict bez schema
    Zwraca (lista, liczba_rekordów_z_uzupełnionymi_polami).
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


def db_read(path):
    """Czyta plik bazy z migracją. Zwraca (lista, lista_ostrzeżeń)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    schema = data.get("schema") if isinstance(data, dict) else 1
    lista, normalized = db_to_list(data)
    notes = []
    if schema != DB_SCHEMA:
        notes.append(f"Migracja formatu v{schema or 1} → v{DB_SCHEMA}.")
    if normalized:
        notes.append(f"Uzupełniono metadane w {normalized} rekordzie/-ach.")
    return lista, notes


def db_write(path, skrypty, backup_count=3):
    """
    Atomowy zapis bazy: .tmp → fsync → rotacja .bak → os.replace.
    Przy crashu zostaje poprzednia dobra wersja, nigdy plik pusty/ucięty.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    payload = db_wrap(skrypty)
    big = sum(len(str(sc.get("kod", ""))) for sc in skrypty) > 1_000_000
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=None if big else 2)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        n = max(1, int(backup_count))
        if os.path.exists(path):
            for i in range(n - 1, 0, -1):
                older, newer = f"{path}.bak.{i}", f"{path}.bak.{i + 1}"
                if os.path.exists(older):
                    os.replace(older, newer)
            os.replace(path, path + ".bak")
    except OSError:
        pass
    os.replace(tmp, path)
    return path

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
_HL_COLORS = {
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
}

_CATEGORY_LEXER = {
    "Python":     "python",
    "Bash":       "bash",
    "PowerShell": "powershell",
    "JavaScript": "javascript",
    "SQL":        "sql",
    "Other":      "text",
}


class SyntaxHighlighter:
    """
    Podświetla składnię kodu w widżecie tk.Text.
    Używa Pygments – jeśli niedostępny, jest transparentny (brak efektu).
    Wywołaj highlight(widget, kategoria) po każdej zmianie kodu.
    Debounce 120 ms – nie spowalnia pisania.
    """

    DEBOUNCE_MS = 120

    def __init__(self, app):
        self.app = app
        self._after_id = None
        self._active_widget = None
        self._active_category = "Python"

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

    def highlight(self, widget, category):
        """Pełne podświetlenie zawartości widżetu."""
        if not _PYGMENTS_OK:
            return
        code = widget.get("1.0", "end-1c")
        if not code.strip():
            return
        # Usuń stare tagi
        for tag in widget.tag_names():
            if tag.startswith("hl_"):
                widget.tag_remove(tag, "1.0", "end")
        # Wybierz lexer
        lex_name = _CATEGORY_LEXER.get(category, "text")
        try:
            lexer = get_lexer_by_name(lex_name, stripall=False)
        except Exception:
            return
        # Zastosuj tokeny
        row, col = 1, 0
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
                    if widget.tag_cget(tag, "foreground"):
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
                col = end_col


# ══════════════════════════════════════════════════════════════════════════════
# MOUSE MANAGER — pełna obsługa myszy
# ══════════════════════════════════════════════════════════════════════════════
class MouseManager:
    """
    Kompleksowa obsługa myszy dla całej aplikacji v2.0

    SCROLL
    ──────
    Kółko myszy        → płynny pionowy scroll (bubble-up do rodzica)
    Shift/Alt + kółko  → poziomy scroll
    Ctrl + kółko       → zoom czcionki edytorów (7-28 pt)
    Środkowy przycisk  → pan dla Text / Listbox / Treeview / Canvas

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
    """

    TOOLTIP_DELAY_MS  = 600
    GESTURE_THRESHOLD = 40
    FONT_SIZE_MIN     = 7
    FONT_SIZE_MAX     = 28
    FONT_FAMILY       = "Consolas"

    _EDITOR_ATTRS = [
        "text_kod", "text_opis", "text_preview",
        "edytor_text", "diag_text", "adv_preview",
        "venv_log_text", "venv_req_text",
        "db_result_text", "tools_text",
    ]

    def __init__(self, app):
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

        self._tooltip_win    = None
        self._tooltip_after  = None
        self._tooltip_widget = None

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
        app.bind_all("<Shift-Button-4>",  lambda e: self._hscroll(e.widget,  3))
        app.bind_all("<Shift-Button-5>",  lambda e: self._hscroll(e.widget, -3))
        app.bind_all("<Button-3>",        self._on_right_press)
        app.bind_all("<B3-Motion>",       self._on_gesture_motion)
        app.bind_all("<ButtonRelease-3>", self._on_right_release)
        app.bind_all("<Control-a>",       self._on_ctrl_a)

    # ── TOOLTIPS ──────────────────────────────────────────────────────────────
    def attach_tooltip(self, widget, text):
        widget.bind("<Enter>",       lambda e: self._tooltip_schedule(widget, text), add="+")
        widget.bind("<Leave>",       lambda e: self._tooltip_cancel(),                add="+")
        widget.bind("<ButtonPress>", lambda e: self._tooltip_cancel(),                add="+")

    def _tooltip_schedule(self, widget, text):
        self._tooltip_cancel()
        self._tooltip_widget = widget
        self._tooltip_after  = self.app.after(
            self.TOOLTIP_DELAY_MS,
            lambda: self._tooltip_show(widget, text))

    def _tooltip_cancel(self):
        if self._tooltip_after:
            self.app.after_cancel(self._tooltip_after)
            self._tooltip_after = None
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None

    def _tooltip_show(self, widget, text):
        if not widget.winfo_exists():
            return
        try:
            x = widget.winfo_rootx() + 12
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            sw = self.app.winfo_screenwidth()
            if x + 220 > sw:
                x = sw - 224
        except Exception:
            return
        win = tk.Toplevel(self.app)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        win.attributes("-topmost", True)
        outer = tk.Frame(win, bg="#3a3f58", bd=1)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text=text, font=("Consolas", 8),
                 bg="#1e2130", fg="#c8d0f0",
                 padx=10, pady=5, justify="left").pack()
        self._tooltip_win = win

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
            if isinstance(w, (tk.Text, tk.Listbox)):
                if iy: w.yview_scroll(iy, "units")
                if ix: w.xview_scroll(ix, "units")
            elif isinstance(w, ttk.Treeview):
                if iy: w.yview_scroll(iy, "units")
                if ix: w.xview_scroll(ix, "units")
            elif isinstance(w, tk.Canvas):
                if ix: w.xview_scroll(ix, "units")
                if iy: w.yview_scroll(iy, "units")
            else:
                self._scroll_parent(w, ix, iy)
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
            return
        if shift or alt:
            delta = self._get_delta(event)
            self._hscroll(event.widget, -delta)
            return
        self._vscroll_smart(event)

    def _get_delta(self, event):
        if event.num == 4: return  3
        if event.num == 5: return -3
        d = getattr(event, "delta", 0)
        if d == 0:         return  0
        return max(-5, min(5, d // 40)) or (1 if d > 0 else -1)

    def _vscroll_smart(self, event):
        delta = self._get_delta(event)
        w = event.widget
        if isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview)):
            try:
                w.yview_scroll(-delta, "units")
                return
            except Exception:
                pass
        if isinstance(w, tk.Canvas):
            try:
                w.yview_scroll(-delta, "units")
                return
            except Exception:
                pass
        if isinstance(w, ttk.Scrollbar):
            return
        self._scroll_parent(w, 0, -delta)

    def _scroll_parent(self, widget, ix, iy):
        try:
            parent = widget.nametowidget(widget.winfo_parent())
        except Exception:
            return
        visited = set()
        while parent and str(parent) not in visited:
            visited.add(str(parent))
            if isinstance(parent, (tk.Text, tk.Listbox, ttk.Treeview, tk.Canvas)):
                try:
                    if iy: parent.yview_scroll(iy, "units")
                    if ix: parent.xview_scroll(ix, "units")
                    return
                except Exception:
                    pass
            try:
                parent = parent.nametowidget(parent.winfo_parent())
            except Exception:
                break

    def _hscroll(self, widget, delta):
        for w in self._widget_chain(widget):
            if isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview, tk.Canvas)):
                try:
                    w.xview_scroll(-delta, "units")
                    return
                except Exception:
                    pass

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
        win = tk.Toplevel(self.app)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        rx = self.app.winfo_rootx() + self.app.winfo_width() - 170
        ry = self.app.winfo_rooty() + 55
        win.wm_geometry(f"+{rx}+{ry}")
        bar = tk.Frame(win, bg="#2a304a", bd=0)
        bar.pack(fill="both", expand=True)
        bar2 = tk.Frame(bar, bg="#4a90d9", width=3)
        bar2.pack(side="left", fill="y")
        tk.Label(bar, text=f"  Czcionka: {size} pt  ",
                 font=("Consolas", 10, "bold"),
                 bg="#2a304a", fg="#82aaff",
                 padx=6, pady=8).pack(side="left")
        self._zoom_toast = win
        self.app.after(1400, lambda: win.destroy() if win.winfo_exists() else None)

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
        win = tk.Toplevel(self.app)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        rx = self.app.winfo_rootx() + self.app.winfo_width()  // 2 - 110
        ry = self.app.winfo_rooty() + self.app.winfo_height() // 2 - 28
        win.wm_geometry(f"+{rx}+{ry}")
        frm = tk.Frame(win, bg="#1a2040", highlightthickness=1,
                       highlightbackground="#4a90d9")
        frm.pack(fill="both", expand=True)
        tk.Label(frm, text=text,
                 font=("Consolas", 12, "bold"),
                 bg="#1a2040", fg="#6dde84",
                 padx=22, pady=14).pack()
        self._gesture_toast = win
        self.app.after(900, lambda: win.destroy() if win.winfo_exists() else None)

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
        if self._ctx_menu:
            try:
                self._ctx_menu.destroy()
            except Exception:
                pass

        w    = event.widget
        app  = self.app
        menu = self._make_menu()

        def _add_zoom_submenu(m):
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
            m.add_cascade(label="Zoom czcionki", menu=zoom_m)

        # ── tk.Text edytowalne ─────────────────────────────────────────────────
        if isinstance(w, tk.Text) and str(w.cget("state")) != "disabled":
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
            _add_zoom_submenu(menu)

        # ── ttk.Treeview ───────────────────────────────────────────────────────
        elif isinstance(w, ttk.Treeview):
            sel = w.selection()
            n   = len(sel)

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

        # ── tk.Listbox ─────────────────────────────────────────────────────────
        elif isinstance(w, tk.Listbox):
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

        # ── Entry / Combobox ───────────────────────────────────────────────────
        elif isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox)):
            val = ""
            try:
                val = w.get()
            except Exception:
                pass
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

        # ── Canvas ─────────────────────────────────────────────────────────────
        elif isinstance(w, tk.Canvas):
            menu.add_command(label="Powieksz", command=lambda: self._zoom_step(+1))
            menu.add_command(label="Pomniejsz", command=lambda: self._zoom_step(-1))
            menu.add_command(label="Reset widoku",
                             command=lambda: (w.xview_moveto(0), w.yview_moveto(0)))
            menu.add_separator()
            menu.add_command(label="Eksportuj jako PS",
                             command=lambda: self._canvas_export_ps(w))
            menu.add_separator()
            menu.add_command(label="Odswiez", command=lambda: self._try_refresh(w))

        # ── ogolne ─────────────────────────────────────────────────────────────
        else:
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
            _add_zoom_submenu(menu)
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
            menu.add_command(label="Skroty klawisz.", command=app._menu_skroty)

        self._ctx_menu = menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

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
            messagebox.showinfo("Statystyki zaznaczenia",
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
            messagebox.showinfo("Wystapienia",
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
        win = tk.Toplevel(self.app)
        win.title("Znajdz / Zastap")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg="#1e2130")
        try:
            win.wm_geometry(f"+{widget.winfo_rootx()+20}+{widget.winfo_rooty()+40}")
        except Exception:
            pass

        pad = dict(padx=10, pady=4)
        tk.Label(win, text="Znajdz:", font=("Consolas", 9),
                 bg="#1e2130", fg="#c8d0f0").grid(row=0, column=0, sticky="w", **pad)
        e_find = tk.Entry(win, font=("Consolas", 9), bg="#252840", fg="#c8d0f0",
                          insertbackground="#c8d0f0", width=32, relief="flat")
        e_find.grid(row=0, column=1, columnspan=2, **pad)
        e_find.focus_set()

        tk.Label(win, text="Zastap:", font=("Consolas", 9),
                 bg="#1e2130", fg="#c8d0f0").grid(row=1, column=0, sticky="w", **pad)
        e_repl = tk.Entry(win, font=("Consolas", 9), bg="#252840", fg="#c8d0f0",
                          insertbackground="#c8d0f0", width=32, relief="flat")
        e_repl.grid(row=1, column=1, columnspan=2, **pad)

        var_case  = tk.BooleanVar(value=False)
        var_regex = tk.BooleanVar(value=False)
        tk.Checkbutton(win, text="Aa wielk.", variable=var_case,
                       bg="#1e2130", fg="#c8d0f0", selectcolor="#252840",
                       font=("Consolas", 8), activebackground="#1e2130",
                       activeforeground="#c8d0f0").grid(row=2, column=0, **pad)
        tk.Checkbutton(win, text="Regex", variable=var_regex,
                       bg="#1e2130", fg="#c8d0f0", selectcolor="#252840",
                       font=("Consolas", 8), activebackground="#1e2130",
                       activeforeground="#c8d0f0").grid(row=2, column=1, **pad)

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
            lbl_res.config(text=f"Znaleziono: {cnt}" if cnt else "Nie znaleziono")
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
                messagebox.showerror("Regex blad", str(exc))
                return
            widget.delete("1.0", "end")
            widget.insert("1.0", new_content)
            lbl_res.config(text=f"Zastapiono: {n}")

        btn_cfg = dict(font=("Consolas", 9), bg="#2e3350", fg="#c8d0f0",
                       relief="flat", padx=8, pady=3,
                       activebackground="#4a90d9", activeforeground="#fff",
                       cursor="hand2")
        tk.Button(win, text="Szukaj dalej",    **btn_cfg,
                  command=_find_next).grid(row=4, column=0, **pad)
        tk.Button(win, text="Zastap",          **btn_cfg,
                  command=_replace_one).grid(row=4, column=1, **pad)
        tk.Button(win, text="Zastap wszystko", **btn_cfg,
                  command=_replace_all).grid(row=4, column=2, **pad)
        tk.Button(win, text="Zamknij",         **btn_cfg,
                  command=win.destroy).grid(row=5, column=0, columnspan=3, pady=6)

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
            messagebox.showerror("Blad", str(e))

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
                title="Eksportuj zaznaczone jako JSON")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("Eksport", f"Wyeksportowano {len(items)} skryptow.")
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
                messagebox.showinfo("Eksport", f"Wyeksportowano {len(items)} skryptow.")

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
            messagebox.showinfo("Eksport", f"Zapisano {len(items)} elementow.")

    # ── Canvas ─────────────────────────────────────────────────────────────────
    def _canvas_export_ps(self, canvas):
        path = filedialog.asksaveasfilename(
            defaultextension=".ps",
            filetypes=[("PostScript", "*.ps")])
        if path:
            try:
                canvas.postscript(file=path)
                messagebox.showinfo("Eksport", f"Zapisano: {path}")
            except Exception as e:
                messagebox.showerror("Blad eksportu", str(e))

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
    "SQL":        ".sql",
    "Other":      ".txt",
}


def runner_path(path):
    """Ścieżka zdatna do przekazania interpreterowi na Windows.
    Git-Bash/Node lubią zjadać backslashe i mylić "C:" z opcją — używamy 'C:/...'.
    """
    path = os.path.abspath(path)
    return path.replace("\\", "/") if os.name == "nt" else path


def runner_cmd(kategoria, path, args=None, interpreter=""):
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
    return None


def runner_shell_cmd(categoria, path, args=None, interpreter=""):
    """Jak runner_cmd(), ale jako pojedynczy string dla nowej konsoli Windows."""
    import subprocess
    cmd = runner_cmd(categoria, path, args, interpreter)
    return subprocess.list2cmdline(cmd) if cmd else None


def runner_analyze(kod, kategoria, path):
    """Statyczna kontrola przed uruchomieniem: składnia + ostrzeżenia.
    Zwraca (ok, komunikat)."""
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
    return True, "OK"


def runner_save_temp(kod, kategoria, workdir=None):
    """Zapisuje kod do pliku tymczasowego (ASCII-safe nazwa) i zwraca ścieżkę."""
    d = workdir or tempfile.mkdtemp(prefix="runner_")
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

FONT_UI    = ("Consolas", 9)
FONT_BOLD  = ("Consolas", 9, "bold")
FONT_MONO  = ("Consolas", 10)
FONT_TITLE = ("Consolas", 16, "bold")


class BazaSkryptow(tk.Tk):
    def __init__(self, start_runner=False):
        super().__init__()
        self.title("Baza Skryptów v3.0")
        self.geometry("1130x780")
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        # lista zapisanych skryptów: [{id, nazwa, kategoria, tagi, opis, kod, ...}, ...]
        self.skrypty = []
        # historia wyszukiwań
        self.search_history = []

        # ── Konfiguracja + ścieżka bazy (stała, jednoplikowa baza) ──────────
        self._cfg = cfg_load()
        self.db_path = self._cfg.get("db_path") or DB_FILE
        self._last_save = None
        self._autosave_pending = None

        self._build_menu()
        self._build_header()
        self._build_main_tabs()
        self._bind_shortcuts()
        self._mouse = MouseManager(self)
        self.after(200, self._mouse.register_app_tooltips)
        self.after(200, lambda: self._mouse.setup_tree_enhanced(self.tree))
        # Syntax highlighter + walidacja nazwy
        self._highlighter = SyntaxHighlighter(self)
        self.after(300, self._attach_highlighter)
        self.after(300, self._attach_nazwa_validation)
        # ── Autoload bazy z pliku (jednoplikowa baza skryptów)
        self.after(100, self._autoload_db)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._gui_ready = False
        if start_runner:
            self.after(250, self._menu_pokaz_runner)

    def __getattr__(self, name):
        """Odporny dostęp do bazy — modułowe funkcje mogą ominąć __init__.
        Zapewnia sensowną wartość zamiast AttributeError dla pól infrastruktury.
        """
        if name.startswith("__") or not name.startswith("_"):
            raise AttributeError(name)
        defaults = {
            "_cfg": None, "db_path": "", "_last_save": None,
            "_autosave_pending": None, "_sc_index": None,
            "_runner_current_idx": None, "_runner_mode_edit": False,
            "_runner_proc": None, "_runner_busy": False,
            "_runner_force_new_console": False, "_runner_current": None,
            "_edytor_spec": None, "_runner_out": None, "_runner_out_sub": None,
        }
        if name in defaults:
            return defaults[name]
        raise AttributeError(name)

    def _attach_highlighter(self):
        """Podłącz highlighter do obu edytorów kodu po zbudowaniu UI."""
        if hasattr(self, "text_kod"):
            self._highlighter.attach(self.text_kod, lambda: self.var_kat.get())
        if hasattr(self, "edytor_text"):
            # edytor_text nie ma prostego dostępu do kategorii – czytamy z etykiety
            def _get_kat_edytor():
                idx = getattr(self, "_edytor_current_idx", None)
                if idx is not None and idx < len(self.skrypty):
                    return self.skrypty[idx].get("kategoria", "Python")
                return "Python"
            self._highlighter.attach(self.edytor_text, _get_kat_edytor)

    def _attach_nazwa_validation(self):
        """Podłącz walidację pola Nazwa na żywo."""
        if hasattr(self, "entry_nazwa"):
            self.entry_nazwa.bind("<KeyRelease>", self._validate_nazwa, add="+")

    def _validate_nazwa(self, event=None):
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
        self.bind_all("<Control-F5>",      lambda e: self._runner_stop())
        # ── Baza jednoplikowa ────────────────────────────────────────────────
        self.bind_all("<Control-Shift-S>", lambda e: self._save_db(save_as=True))

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        menubar = tk.Menu(self, bg=BG_PANEL, fg=FG_WHITE,
                          activebackground=ACCENT_BLUE, activeforeground=FG_WHITE,
                          relief="flat", bd=0)

        def menu(label):
            m = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=FG_WHITE,
                        activebackground=ACCENT_BLUE, activeforeground=FG_WHITE)
            menubar.add_cascade(label=label, menu=m)
            return m

        def sep(m):
            m.add_separator()

        def item(m, label, cmd=None, shortcut=None):
            kw = {}
            if shortcut:
                kw["accelerator"] = shortcut
            m.add_command(label=label, command=cmd or (lambda: None), **kw)

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
        sep(m_plik)
        item(m_plik, "Importuj bazę (JSON)…",   self._lista_importuj)
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
        item(m_skr, "Importuj skrypty (JSON)…", self._lista_importuj)
        item(m_skr, "Eksportuj skrypty (JSON)…",self._lista_eksportuj)

        # ── Run (runner) ──────────────────────────────────────────────────────
        m_run = menu("Run")
        item(m_run, "Pokaż panel Runner",        self._menu_pokaz_runner)
        sep(m_run)
        item(m_run, "Uruchom (zapisuje najpierw)", self._runner_run_form,      "F9")
        item(m_run, "Uruchom bez zapisu",         lambda: self._runner_run_form(save_first=False), "Shift+F9")
        item(m_run, "Uruchom w nowej konsoli",    lambda: self._runner_run_form(new_console=True), "Ctrl+F9")
        item(m_run, "Zatrzymaj",                  self._runner_stop,          "Ctrl+F5")
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
        item(m_wid, "Moduły — Testy osiągów",   lambda: self._menu_pokaz_mod("testy"))
        item(m_wid, "Moduły — Naprawa",         lambda: self._menu_pokaz_mod("naprawa"))
        item(m_wid, "Moduły — Kreator Pluginów",lambda: self._menu_pokaz_mod("plugin"))

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

    def _menu_pokaz_liste(self):
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(1, self._show_sub_lista)

    def _menu_pokaz_edytor(self):
        self._sel_main(0, self._show_skrypty)
        self._sel_sub(2, self._show_sub_edytor)

    def _menu_pokaz_szukaj(self):
        self._sel_main(1, self._show_szukaj)

    def _menu_pokaz_mod(self, key):
        self._sel_main(2, self._show_moduly)
        idx = ["info", "diag", "laczen", "testy", "naprawa", "plugin"].index(key)
        for j, b in enumerate(self._mod_btns):
            b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                        fg=FG_WHITE       if j == idx else FG_GRAY)
        for f in self._mod_frames.values():
            f.pack_forget()
        self._mod_frames[key].pack(fill="both", expand=True)

    def _menu_pokaz_plugin(self):
        self._menu_pokaz_mod("plugin")

    def _menu_pokaz_laczen(self):
        self._menu_pokaz_mod("laczen")

    def _menu_filtr_kategoria(self):
        dlg = tk.Toplevel(self)
        dlg.title("Filtruj wg kategorii")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("300x280")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="Wybierz kategorię:", font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE).pack(anchor="w", padx=14, pady=(12, 4))
        var = tk.StringVar(value="Wszystkie")
        for cat in ["Wszystkie"] + CATEGORIES:
            tk.Radiobutton(dlg, text=cat, variable=var, value=cat,
                           font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                           activebackground=BG_DARK, selectcolor=BG_INPUT).pack(anchor="w", padx=22)
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
                                 values=(s["nazwa"], s["kategoria"], s["tagi"], opis_skrot),
                                 tags=("odd" if i % 2 == 0 else "even",))
            dlg.destroy()
        tk.Button(dlg, text="Zastosuj filtr", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", command=apply_filter).pack(pady=14)

    def _menu_filtr_tagi(self):
        dlg = tk.Toplevel(self)
        dlg.title("Filtruj wg tagów")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("320x180")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="Wpisz tag (częściowe dopasowanie):",
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE).pack(anchor="w", padx=14, pady=(12, 4))
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
                                 values=(s["nazwa"], s["kategoria"], s["tagi"], opis_skrot),
                                 tags=("odd" if i % 2 == 0 else "even",))
            dlg.destroy()
        e.bind("<Return>", lambda _: apply())
        tk.Button(dlg, text="Filtruj", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", command=apply).pack(pady=10)

    def _menu_sortuj(self, pole, kierunek):
        self._menu_pokaz_liste()
        rev = (kierunek == "DESC")
        self.skrypty.sort(key=lambda s: s.get(pole, "").lower(), reverse=rev)
        self._refresh_lista()

    def _menu_wyczysc_baze(self):
        if not self.skrypty:
            messagebox.showinfo("Baza pusta", "Baza skryptów jest już pusta.")
            return
        if messagebox.askyesno("Wyczyść bazę",
                               f"Usunąć wszystkie {len(self.skrypty)} skrypt(ów)?\n"
                               "Tej operacji nie można cofnąć!"):
            self.skrypty.clear()
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            self.save_db(silent=True)
            messagebox.showinfo("Wyczyszczono", "Baza skryptów została wyczyszczona.")

    def _menu_statystyki(self):
        self._menu_pokaz_szukaj()
        # przełącz na zakładkę Statystyki
        for j, ib in enumerate(self._inner_btns):
            ib.configure(bg=BG_SUBTAB_ACT if j == 2 else BG_SUBTAB_INACT,
                         fg=FG_WHITE       if j == 2 else FG_GRAY)
        for f in self._inner_frames.values():
            f.pack_forget()
        self._inner_frames["statystyki"].pack(fill="both", expand=True)
        self._adv_refresh_stats()

    def _menu_odswiez(self):
        self._refresh_lista()
        self._mod_refresh_info()
        self._update_count()

    def _menu_ustawienia_kategorie(self):
        dlg = tk.Toplevel(self)
        dlg.title("Kategorie skryptów")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("340x320")
        dlg.resizable(False, True)
        dlg.grab_set()
        tk.Label(dlg, text="Aktywne kategorie:", font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE).pack(anchor="w", padx=14, pady=(12, 4))
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
            lb.insert("end", cat)
        tk.Label(dlg, text="(edycja kategorii w przyszłej wersji)",
                 font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY).pack(pady=(0, 8))

    def _menu_skroty(self):
        dlg = tk.Toplevel(self)
        dlg.title("Skróty klawiszowe")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("420x470")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="⌨ Skróty klawiszowe", font=FONT_BOLD,
                 bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w", padx=14, pady=(12, 6))
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
            ("Ctrl+F9",       "Uruchom w nowej konsoli"),
            ("Ctrl+F5",       "Zatrzymaj proces"),
            ("Alt+F4",        "Zamknij aplikację (zapisze bazę)"),
            ("Delete",        "Usuń zaznaczony skrypt"),
            ("F5",            "Odśwież widoki"),
        ]
        for skrot, opis in skroty:
            row = tk.Frame(dlg, bg=BG_DARK)
            row.pack(fill="x", padx=14, pady=2)
            tk.Label(row, text=skrot, font=FONT_BOLD, bg=BG_INPUT, fg=ACCENT_BLUE,
                     width=18, anchor="w", padx=6, pady=2).pack(side="left")
            tk.Label(row, text=opis, font=FONT_UI, bg=BG_DARK,
                     fg=FG_WHITE, anchor="w").pack(side="left", padx=8)
        tk.Button(dlg, text="Zamknij", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=12, pady=4,
                  cursor="hand2", command=dlg.destroy).pack(pady=14)

    def _menu_o_programie(self):
        dlg = tk.Toplevel(self)
        dlg.title("O programie")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("460x360")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="Baza Skryptów v3.0",
                 font=("Consolas", 16, "bold"), bg=BG_DARK, fg=ACCENT_BLUE).pack(pady=(24, 4))
        for line, fg in [
            ("Zaawansowana baza skryptów i narzędzi developerskich", FG_WHITE),
            ("", FG_GRAY),
            ("Wersja:    3.0", FG_GRAY),
            ("Platforma: Python 3 / Tkinter", FG_GRAY),
            ("Kodowanie: UTF-8", FG_GRAY),
            ("", FG_GRAY),
            ("Moduły: Info · Diagnostyka · Łączenie · Testy · Naprawa · Kreator Pluginów", FG_GRAY),
            ("", FG_GRAY),
            ("── Autor ──────────────────────────────────", BORDER_CLR),
            ("Autor:   Sebastian Januchowski", FG_WHITE),
            ("Firma:   polsoft.ITS™ Group", FG_WHITE),
            ("Web:     www.polsoft.gt.tc", ACCENT_BLUE),
            ("GitHub:  https://github.com/seb07uk", ACCENT_BLUE),
            ("E-mail:  polsoft.its@fastservice.com", ACCENT_BLUE),
        ]:
            tk.Label(dlg, text=line, font=FONT_UI, bg=BG_DARK, fg=fg).pack()
        tk.Button(dlg, text="Zamknij", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=14, pady=5,
                  cursor="hand2", command=dlg.destroy).pack(pady=16)

    # ── Nagłówek ──────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_PANEL, height=48)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Baza  Skryptów  v3.0",
                 font=FONT_TITLE, bg=BG_PANEL, fg=FG_WHITE).pack(side="left", padx=18)
        right = tk.Frame(hdr, bg=BG_PANEL)
        right.pack(side="right", padx=12)
        tk.Label(right, text="Windows 11",   font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=6)
        self.lbl_count = tk.Label(right, text="Skryptów: 0",
                                  font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self.lbl_count.pack(side="left", padx=6)
        self.lbl_db_status = tk.Label(right, text="", font=("Consolas", 8),
                                      bg=BG_PANEL, fg="#6dde84")
        self.lbl_db_status.pack(side="left", padx=6)
        tk.Button(right, text="● EN", font=FONT_BOLD,
                  bg="#3a4060", fg="#7ec8e3", relief="flat",
                  padx=8, pady=2, cursor="hand2").pack(side="left", padx=6)

    # ══════════════════════════════════════════════════════════════════════════
    # GŁÓWNY PASEK ZAKŁADEK
    # ══════════════════════════════════════════════════════════════════════════
    def _build_main_tabs(self):
        self.main_tab_bar = tk.Frame(self, bg=BG_DARK)
        self.main_tab_bar.pack(fill="x", side="top", pady=(2, 0))
        self.main_tab_content = tk.Frame(self, bg=BG_DARK)
        self.main_tab_content.pack(fill="both", expand=True)

        main_tabs = [
            ("Skrypty",       self._show_skrypty),
            ("Szukaj",        self._show_szukaj),
            ("Moduły",        self._show_moduly),
            ("Baza Danych",   self._show_db),
            ("VirtualEnv",    self._show_venv),
            ("💾 VDrive",     self._show_vdrive),
            ("Narzędzia",     self._show_narzedzia),
            ("🖥 Terminal",   self._show_terminal),
            ("▶ Runner",      self._show_runner),
        ]
        self._main_btns = []
        self.main_frames = {}

        for i, (label, cmd) in enumerate(main_tabs):
            b = tk.Button(self.main_tab_bar, text=label, font=FONT_UI,
                          bg=BG_TAB_ACT if i == 0 else BG_TAB_INACT,
                          fg=FG_WHITE    if i == 0 else FG_GRAY,
                          relief="flat", padx=10, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i, c=cmd: self._sel_main(i, c))
            b.pack(side="left")
            self._main_btns.append(b)

        self._build_skrypty_frame()
        self._build_szukaj_frame()
        self._build_moduly_frame()
        self._build_narzedzia_frame()
        self._build_venv_frame()
        self._build_vdrive_frame()
        self._build_db_frame()
        self._build_terminal_frame()
        self._show_skrypty()

    def _sel_main(self, idx, cmd):
        for i, b in enumerate(self._main_btns):
            b.configure(bg=BG_TAB_ACT if i == idx else BG_TAB_INACT,
                        fg=FG_WHITE    if i == idx else FG_GRAY)
        for f in self.main_frames.values():
            f.pack_forget()
        cmd()

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
            ("📊 Statystyki",    self._show_sub_statystyki),
            ("⚙ Zaawansowane",  self._show_sub_zaawansowane),
            ("▶ Runner",        self._show_sub_runner),
        ]
        for i, (label, cmd) in enumerate(sub_tabs):
            b = tk.Button(sub_bar, text=label, font=FONT_UI,
                          bg=BG_SUBTAB_ACT if i == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if i == 0 else FG_GRAY,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i, c=cmd: self._sel_sub(i, c))
            b.pack(side="left")
            self._sub_btns.append(b)

        # Separator + Importuj (rozwijane menu) / Eksportuj
        tk.Frame(sub_bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=4)

        # ── Importuj — rozwijane menu w dół z 3 opcjami ────────────────────────
        # Dropdown zbudowany z realnych widżetów (Frame + Button) — pokazywany
        # przez place(), więc renderuje się zawsze (niezależnie od popupów Tk).
        self._import_btn = tk.Button(sub_bar, text="📥 Importuj  ▾", font=FONT_UI,
                                     bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                                     padx=10, pady=5, cursor="hand2", bd=0,
                                     highlightthickness=0,
                                     activebackground=BTN_HOVER,
                                     activeforeground=FG_WHITE,
                                     command=self._toggle_import_menu)
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
            tk.Button(self._import_dropdown, text=_lbl, font=FONT_UI,
                      bg="#252840", fg="#c8d0f0", relief="flat", anchor="w",
                      padx=14, pady=7, cursor="hand2", bd=0,
                      highlightthickness=0,
                      activebackground=ACCENT_BLUE,
                      activeforeground="#ffffff",
                      command=lambda c=_cmd: self._pick_import(c)
                      ).pack(fill="x")

        # Zamknij dropdown kliknięciem w dowolnym innym miejscu
        self.bind_all("<Button-1>", self._maybe_close_import_menu, add="+")

        tk.Button(sub_bar, text="📤 Eksportuj", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", bd=0, highlightthickness=0,
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._lista_eksportuj).pack(side="left", padx=2)

        self._build_sub_dodaj()
        self._build_sub_lista()
        self._build_sub_edytor()
        self._build_sub_szablony()
        self._build_sub_statystyki()
        self._build_sub_zaawansowane()
        self._build_sub_runner()
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
            messagebox.showerror("Błąd importu", str(ex))

    def _sel_sub(self, idx, cmd):
        for i, b in enumerate(self._sub_btns):
            b.configure(bg=BG_SUBTAB_ACT if i == idx else BG_SUBTAB_INACT,
                        fg=FG_WHITE       if i == idx else FG_GRAY)
        for f in self.sub_frames.values():
            f.pack_forget()
        cmd()

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

        tk.Button(toolbar, text="+ Nowy skrypt", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  activebackground="#3a7bc8", activeforeground=FG_WHITE,
                  command=self._wyczysc).pack(side="left")
        vsep()

        tk.Label(toolbar, text="Nazwa:", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=(0, 4))
        self.entry_nazwa = tk.Entry(toolbar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                    insertbackground=FG_WHITE, relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER_CLR,
                                    highlightcolor=ACCENT_BLUE, width=22)
        self.entry_nazwa.pack(side="left")
        vsep()

        tk.Label(toolbar, text="Kategoria:", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=(0, 4))
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
        tk.Button(toolbar, text="⚙ Auto", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=7, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE).pack(side="left")
        vsep()

        tk.Label(toolbar, text="Tagi:", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=(0, 4))
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
        tk.Label(search_bar, text="🔍 Szukaj:", font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=(0, 4))
        self.entry_search = tk.Entry(search_bar, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      insertbackground=FG_WHITE, relief="flat",
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      highlightcolor=ACCENT_BLUE, width=30)
        self.entry_search.pack(side="left")
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_lista())

        tk.Button(search_bar, text="🗑 Usuń zaznaczony", font=FONT_UI,
                  bg=BTN_DARK, fg="#e07070", relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._usun_skrypt).pack(side="right", padx=4)
        tk.Button(search_bar, text="✏ Edytuj", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._edytuj_skrypt).pack(side="right", padx=4)
        tk.Button(search_bar, text="📂 Otwórz", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._otworz_skrypt).pack(side="right", padx=4)

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # tabela
        cols = ("Nazwa", "Kategoria", "Tagi", "Opis")
        style = ttk.Style()
        style.configure("Dark.Treeview",
                        background=BG_ROW_ODD, foreground=FG_WHITE,
                        fieldbackground=BG_ROW_ODD, rowheight=24,
                        font=FONT_UI)
        style.configure("Dark.Treeview.Heading",
                        background=BG_PANEL, foreground=FG_GRAY,
                        font=FONT_BOLD, relief="flat")
        style.map("Dark.Treeview",
                  background=[("selected", BG_ROW_SEL)],
                  foreground=[("selected", FG_WHITE)])

        tree_frame = tk.Frame(frame, bg=BG_DARK)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=6)

        vsb = tk.Scrollbar(tree_frame, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=10)
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style="Dark.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)

        self.tree.heading("Nazwa",     text="Nazwa")
        self.tree.heading("Kategoria", text="Kategoria")
        self.tree.heading("Tagi",      text="Tagi")
        self.tree.heading("Opis",      text="Opis")

        self.tree.column("Nazwa",     width=220, minwidth=120)
        self.tree.column("Kategoria", width=100, minwidth=80)
        self.tree.column("Tagi",      width=200, minwidth=100)
        self.tree.column("Opis",      width=400, minwidth=150)

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._edytuj_skrypt())

        # tagi wierszy (naprzemienne kolory)
        self.tree.tag_configure("odd",  background=BG_ROW_ODD)
        self.tree.tag_configure("even", background=BG_ROW_EVEN)

        # podgląd kodu na dole listy
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x", padx=8)
        preview_frame = tk.Frame(frame, bg=BG_DARK)
        preview_frame.pack(fill="x", padx=8, pady=(4, 6))
        tk.Label(preview_frame, text="Podgląd kodu:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w")
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
        tk.Label(hdr, text="✏ Edytor skryptów — zaawansowany podgląd i edycja",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # LEWA: lista skryptów do wyboru
        left = tk.Frame(body, bg=BG_PANEL, width=240,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        tk.Label(left, text="📋 Skrypty w bazie", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))

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
        tk.Button(btn_ed, text="▶ Uruchom", font=FONT_UI,
                  bg="#2f6b3f", fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#3d8a52",
                  command=self._edytor_run).pack(fill="x", padx=2, pady=2)
        tk.Button(btn_ed, text="💾 Zapisz zmiany", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._edytor_save).pack(fill="x", padx=2, pady=2)
        tk.Button(btn_ed, text="📋 Kopiuj kod", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._edytor_copy).pack(fill="x", padx=2, pady=2)
        tk.Button(btn_ed, text="🗑 Usuń skrypt", font=FONT_UI,
                  bg="#603030", fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#804040",
                  command=self._edytor_delete).pack(fill="x", padx=2, pady=2)

        def _edytor_refresh(*_):
            q = ed_flt_var.get().lower()
            self.edytor_listbox.delete(0, "end")
            for s in self.skrypty:
                n = s.get("nazwa", "")
                if q and q not in n.lower():
                    continue
                self.edytor_listbox.insert("end", n)
        ed_flt_var.trace_add("write", _edytor_refresh)
        self._edytor_refresh = _edytor_refresh

        # PRAWA: edytor kodu
        right = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="both", expand=True)

        info_bar = tk.Frame(right, bg=BG_PANEL, pady=4, padx=8)
        info_bar.pack(fill="x")
        self.edytor_lbl_nazwa = tk.Label(info_bar, text="— brak wybranego skryptu —",
                                          font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE)
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
        self._edytor_current_idx = None
        _edytor_refresh()

    def _edytor_update_lines(self, _e=None):
        self.edytor_line_nums.config(state="normal")
        self.edytor_line_nums.delete("1.0", "end")
        n = int(self.edytor_text.index("end-1c").split(".")[0])
        self.edytor_line_nums.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self.edytor_line_nums.config(state="disabled")
        lines = int(self.edytor_text.index("end-1c").split(".")[0])
        self.edytor_lbl_info.config(text=f"Linii: {lines}")

    def _edytor_load_selected(self, event=None):
        sel = self.edytor_listbox.curselection()
        if not sel:
            return
        nazwa = self.edytor_listbox.get(sel[0])
        for i, s in enumerate(self.skrypty):
            if s.get("nazwa") == nazwa:
                self._edytor_current_idx = i
                self.edytor_lbl_nazwa.config(text=f"✏  {nazwa}  [{s.get('kategoria','')}]")
                self.edytor_text.delete("1.0", "end")
                self.edytor_text.insert("1.0", s.get("kod", ""))
                self._edytor_update_lines()
                # Podświetl składnię w edytorze
                self._highlighter.highlight(self.edytor_text, s.get("kategoria", "Python"))
                return

    def _edytor_save(self):
        if self._edytor_current_idx is None:
            messagebox.showinfo("Brak wyboru", "Wybierz skrypt z listy.")
            return
        self.skrypty[self._edytor_current_idx]["kod"] = self.edytor_text.get("1.0", "end-1c")
        sc = self.skrypty[self._edytor_current_idx]
        sc["checksum"] = kod_checksum(sc["kod"])
        sc["zmieniony"] = now_str()
        self._after_db_change()
        messagebox.showinfo("Zapisano", "Zmiany zapisane w bazie.")

    def _edytor_run(self):
        """Uruchamia skrypt otwarty w edytorze."""
        if self._edytor_current_idx is None:
            messagebox.showinfo("Brak wyboru", "Wybierz skrypt z listy.")
            return
        self.skrypty[self._edytor_current_idx]["kod"] = self.edytor_text.get("1.0", "end-1c")
        self._runner_current_idx = self._edytor_current_idx
        self._runner_mode_edit = False
        self._after_db_change()
        self._menu_pokaz_runner()
        self._runner_start()

    def _edytor_copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.edytor_text.get("1.0", "end-1c"))
        messagebox.showinfo("Skopiowano", "Kod skopiowany do schowka.")

    def _edytor_delete(self):
        if self._edytor_current_idx is None:
            messagebox.showinfo("Brak wyboru", "Wybierz skrypt z listy.")
            return
        nazwa = self.skrypty[self._edytor_current_idx].get("nazwa", "?")
        if messagebox.askyesno("Usuń", f"Usunąć skrypt '{nazwa}'?"):
            self.skrypty.pop(self._edytor_current_idx)
            self._edytor_current_idx = None
            self._runner_current_idx = None
            self.edytor_text.delete("1.0", "end")
            self.edytor_lbl_nazwa.config(text="— brak wybranego skryptu —")
            self._edytor_update_lines()
            self._edytor_refresh()
            self._rebuild_index()
            self._update_count()
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
        }

        # ── pasek narzędzi ────────────────────────────────────────────────────
        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        tk.Label(top, text="📦 Szablony kodu — gotowe fragmenty do wklejenia do edytora",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # ── lewa: drzewo kategorii + szablonów ───────────────────────────────
        left = tk.Frame(body, bg=BG_PANEL, width=230,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        tk.Label(left, text="Kategoria / Szablon", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))

        sz_sc = tk.Scrollbar(left, orient="vertical", bg=BG_PANEL,
                             troughcolor=BG_PANEL, width=8)
        sz_sc.pack(side="right", fill="y", pady=2)

        self._sz_tree = ttk.Treeview(left, show="tree", selectmode="browse",
                                      yscrollcommand=sz_sc.set)
        sz_sc.config(command=self._sz_tree.yview)
        self._sz_tree.pack(fill="both", expand=True, padx=(6, 0), pady=4)

        for kat, tpls in self._SZABLONY.items():
            parent = self._sz_tree.insert("", "end", text=f"  {kat}", open=True,
                                           tags=("kat",))
            for nazwa in tpls:
                self._sz_tree.insert(parent, "end", text=f"    • {nazwa}",
                                     tags=("tpl",), iid=f"{kat}||{nazwa}")
        self._sz_tree.tag_configure("kat", foreground=ACCENT_BLUE)
        self._sz_tree.tag_configure("tpl", foreground=FG_WHITE)

        btn_f = tk.Frame(left, bg=BG_PANEL)
        btn_f.pack(fill="x", padx=6, pady=(2, 6))
        tk.Button(btn_f, text="➕ Użyj w edytorze", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._sz_uzyj_w_edytorze).pack(fill="x", pady=2)
        tk.Button(btn_f, text="💾 Zapisz jako skrypt", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sz_zapisz_jako_skrypt).pack(fill="x", pady=2)
        tk.Button(btn_f, text="📋 Kopiuj do schowka", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._sz_kopiuj).pack(fill="x", pady=2)

        # ── prawa: podgląd szablonu + własny szablon ─────────────────────────
        right = tk.Frame(body, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        info_r = tk.Frame(right, bg=BG_PANEL, pady=4, padx=8)
        info_r.pack(fill="x")
        self._sz_lbl = tk.Label(info_r, text="Wybierz szablon z listy po lewej",
                                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_GRAY)
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
        tk.Label(own_hdr, text="✏ Własny szablon — nazwa:",
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
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
        tk.Button(own_hdr, text="💾 Dodaj własny", font=FONT_UI,
                  bg="#2a5e2a", fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground="#3a7e3a",
                  command=self._sz_dodaj_wlasny).pack(side="left", padx=4)

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
            messagebox.showinfo("Brak wyboru", "Wybierz szablon z listy.")
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
            messagebox.showinfo("Brak wyboru", "Wybierz szablon z listy.")
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
            messagebox.showinfo("Brak wyboru", "Wybierz szablon z listy.")
            return
        self.clipboard_clear()
        self.clipboard_append(kod)
        messagebox.showinfo("Skopiowano", "Szablon skopiowany do schowka.")

    def _sz_dodaj_wlasny(self):
        kat   = self._sz_own_kat.get()
        nazwa = self._sz_own_name.get().strip()
        kod   = self._sz_preview.get("1.0", "end-1c")
        if not nazwa:
            messagebox.showwarning("Brak nazwy", "Podaj nazwę własnego szablonu.")
            return
        if not kod.strip():
            messagebox.showwarning("Brak kodu", "Edytor podglądu jest pusty.")
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
        messagebox.showinfo("Dodano", f"Szablon '{nazwa}' dodany do kategorii '{kat}'.")

    def _show_sub_szablony(self):
        self.sub_frames["szablony"].pack(fill="both", expand=True, padx=4, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: STATYSTYKI
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_statystyki(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["statystyki_skr"] = frame

        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        tk.Label(top, text="📊 Statystyki bazy skryptów",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Button(top, text="🔄 Odśwież", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._stat_refresh).pack(side="right", padx=4)
        tk.Button(top, text="💾 Eksportuj raport", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._stat_export).pack(side="right", padx=4)

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
            tk.Label(card, text=label, font=("Consolas", 8),
                     bg=BG_PANEL, fg=FG_GRAY).pack()

        # ── wykresy tekstowe i tabele ────────────────────────────────────────
        cols_frame = tk.Frame(body, bg=BG_DARK)
        cols_frame.pack(fill="both", expand=True)

        # lewa: według kategorii
        left = tk.Frame(cols_frame, bg=BG_PANEL,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(left, text="Skrypty wg kategorii", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_kat_text = tk.Text(left, font=("Consolas", 9), bg=BG_PANEL,
                                       fg=FG_WHITE, relief="flat", height=12,
                                       highlightthickness=0, state="disabled")
        self._stat_kat_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # środek: top tagi
        mid = tk.Frame(cols_frame, bg=BG_PANEL,
                       highlightthickness=1, highlightbackground=BORDER_CLR)
        mid.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(mid, text="Najczęstsze tagi (top 15)", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_tag_text = tk.Text(mid, font=("Consolas", 9), bg=BG_PANEL,
                                       fg=FG_WHITE, relief="flat", height=12,
                                       highlightthickness=0, state="disabled")
        self._stat_tag_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # prawa: top 10 wg rozmiaru kodu
        right = tk.Frame(cols_frame, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Największe skrypty (top 10)", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_size_text = tk.Text(right, font=("Consolas", 9), bg=BG_PANEL,
                                        fg=FG_WHITE, relief="flat", height=12,
                                        highlightthickness=0, state="disabled")
        self._stat_size_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # dolny: najczęściej uruchamiane (runner)
        runs = tk.Frame(body, bg=BG_PANEL,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        runs.pack(fill="both", expand=True, pady=(6, 0))
        tk.Label(runs, text="Najczęściej uruchamiane (top 10) — runner", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))
        self._stat_run_text = tk.Text(runs, font=("Consolas", 9), bg=BG_PANEL,
                                       fg=FG_WHITE, relief="flat", height=8,
                                       highlightthickness=0, state="disabled")
        self._stat_run_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _stat_refresh(self):
        from collections import Counter
        s = self.skrypty

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

        # kategorie
        kat_cnt = Counter(x.get("kategoria", "—") for x in s)
        max_cnt = max(kat_cnt.values(), default=1)
        lines_kat = []
        for kat, cnt in sorted(kat_cnt.items(), key=lambda x: -x[1]):
            bar = "█" * int(cnt / max_cnt * 20)
            lines_kat.append(f"  {kat:<14} {bar:<20} {cnt}")
        self._stat_kat_text.config(state="normal")
        self._stat_kat_text.delete("1.0", "end")
        self._stat_kat_text.insert("1.0", "\n".join(lines_kat) if lines_kat else "(brak danych)")
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
        self._stat_tag_text.insert("1.0", "\n".join(lines_tag) if lines_tag else "(brak tagów)")
        self._stat_tag_text.config(state="disabled")

        # największe skrypty
        sized = sorted(s, key=lambda x: len(x.get("kod", "")), reverse=True)[:10]
        lines_size = []
        for i, sc in enumerate(sized, 1):
            lc = len(sc.get("kod", "").splitlines())
            ch = len(sc.get("kod", ""))
            lines_size.append(f"  {i:2}. {sc.get('nazwa','?')[:22]:<22} {lc:5} linii  {ch:6} zn")
        self._stat_size_text.config(state="normal")
        self._stat_size_text.delete("1.0", "end")
        self._stat_size_text.insert("1.0", "\n".join(lines_size) if lines_size else "(brak)")
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
        self._stat_run_text.insert("1.0", "\n".join(lines_run) if lines_run else "(brak uruchomień — F9 w zakładce Runner)")
        self._stat_run_text.config(state="disabled")

    def _stat_export(self):
        from collections import Counter
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile="raport_skryptow.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
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
            f"  RAPORT BAZY SKRYPTÓW — {ts}",
            "=" * 60,
            f"  Łącznie skryptów  : {len(s)}",
            f"  Kategorii         : {len(kat_cnt)}",
            f"  Unikalnych tagów  : {len(tags)}",
            f"  Łącznie linii kodu: {lines:,}",
            "",
            "── Według kategorii ──────────────────────────",
        ]
        for kat, cnt in sorted(kat_cnt.items(), key=lambda x: -x[1]):
            report.append(f"  {kat:<20} {cnt} skryptów")
        report += ["", "── Top 20 tagów ──────────────────────────────"]
        for tag, cnt in tags.most_common(20):
            report.append(f"  {tag:<20} {cnt}×")
        report += ["", "── Lista wszystkich skryptów ─────────────────"]
        for i, sc in enumerate(s, 1):
            report.append(f"  {i:3}. [{sc.get('kategoria','?'):12}] {sc.get('nazwa','?')}")
        report.append("=" * 60)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(report))
        messagebox.showinfo("Eksport", f"Raport zapisany:\n{path}")

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

    # ══════════════════════════════════════════════════════════════════════════
    # POD-ZAKŁADKA: ZAAWANSOWANE (porównanie, duplikaty, masowe operacje)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sub_zaawansowane(self):
        frame = tk.Frame(self.sub_content, bg=BG_DARK)
        self.sub_frames["zaawansowane"] = frame

        top = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        top.pack(fill="x")
        tk.Label(top, text="⚙ Zaawansowane operacje na skryptach",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # ── SEKCJA 1: Wyszukaj i zastąp ──────────────────────────────────────
        sec1 = tk.LabelFrame(body, text=" 🔄 Znajdź i zastąp w kodach wszystkich skryptów ",
                             font=FONT_UI, bg=BG_DARK, fg=ACCENT_BLUE,
                             relief="flat", highlightthickness=1,
                             highlightbackground=BORDER_CLR, padx=10, pady=8)
        sec1.pack(fill="x", pady=(0, 10))

        r1 = tk.Frame(sec1, bg=BG_DARK); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="Szukaj:  ", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                 width=12, anchor="w").pack(side="left")
        self._zaw_find = tk.Entry(r1, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                   insertbackground=FG_WHITE, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER_CLR,
                                   highlightcolor=ACCENT_BLUE, width=40)
        self._zaw_find.pack(side="left", padx=4)

        r2 = tk.Frame(sec1, bg=BG_DARK); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="Zastąp:  ", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                 width=12, anchor="w").pack(side="left")
        self._zaw_replace = tk.Entry(r2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                      insertbackground=FG_WHITE, relief="flat",
                                      highlightthickness=1, highlightbackground=BORDER_CLR,
                                      highlightcolor=ACCENT_BLUE, width=40)
        self._zaw_replace.pack(side="left", padx=4)

        r3 = tk.Frame(sec1, bg=BG_DARK); r3.pack(fill="x", pady=4)
        self._zaw_regex_var   = tk.BooleanVar(value=False)
        self._zaw_case_var    = tk.BooleanVar(value=False)
        self._zaw_kat_var     = tk.StringVar(value="Wszystkie")
        tk.Checkbutton(r3, text="Wyrażenie regularne (regex)", variable=self._zaw_regex_var,
                       font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                       activebackground=BG_DARK, selectcolor=BG_INPUT).pack(side="left")
        tk.Checkbutton(r3, text="Uwzględnij wielkość liter", variable=self._zaw_case_var,
                       font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                       activebackground=BG_DARK, selectcolor=BG_INPUT).pack(side="left", padx=16)
        tk.Label(r3, text="Kategoria:", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        ttk.Combobox(r3, textvariable=self._zaw_kat_var,
                     values=["Wszystkie"] + CATEGORIES,
                     font=FONT_UI, style="Dark.TCombobox",
                     width=12, state="readonly").pack(side="left", padx=6)

        r4 = tk.Frame(sec1, bg=BG_DARK); r4.pack(fill="x", pady=2)
        tk.Button(r4, text="🔍 Podgląd zmian", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_preview_replace).pack(side="left", padx=(0, 6))
        tk.Button(r4, text="✅ Zastąp we wszystkich", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._zaw_do_replace).pack(side="left", padx=(0, 6))

        self._zaw_replace_result = tk.Label(sec1, text="", font=("Consolas", 8),
                                             bg=BG_DARK, fg=FG_GRAY, anchor="w")
        self._zaw_replace_result.pack(fill="x")

        # ── SEKCJA 2: Duplikaty ───────────────────────────────────────────────
        sec2 = tk.LabelFrame(body, text=" 🔎 Wykrywanie duplikatów ",
                             font=FONT_UI, bg=BG_DARK, fg="#e0c040",
                             relief="flat", highlightthickness=1,
                             highlightbackground=BORDER_CLR, padx=10, pady=8)
        sec2.pack(fill="x", pady=(0, 10))

        dup_top = tk.Frame(sec2, bg=BG_DARK)
        dup_top.pack(fill="x")
        self._zaw_dup_mode = tk.StringVar(value="nazwa")
        for val, txt in [("nazwa", "Po nazwie"), ("kod", "Po kodzie (hash)"), ("oba", "Nazwa i kod")]:
            tk.Radiobutton(dup_top, text=txt, variable=self._zaw_dup_mode, value=val,
                           font=FONT_UI, bg=BG_DARK, fg=FG_GRAY,
                           activebackground=BG_DARK, selectcolor=BG_INPUT).pack(side="left", padx=8)
        tk.Button(dup_top, text="🔍 Szukaj duplikatów", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_find_dups).pack(side="left", padx=10)
        tk.Button(dup_top, text="🗑 Usuń duplikaty", font=FONT_UI,
                  bg="#603030", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#804040",
                  command=self._zaw_remove_dups).pack(side="left", padx=4)

        self._zaw_dup_result = tk.Text(sec2, font=("Consolas", 8), bg=BG_PANEL,
                                        fg=FG_WHITE, relief="flat", height=5,
                                        highlightthickness=0, state="disabled")
        self._zaw_dup_result.pack(fill="x", pady=(6, 0))

        # ── SEKCJA 3: Masowe operacje ─────────────────────────────────────────
        sec3 = tk.LabelFrame(body, text=" ⚡ Masowe operacje ",
                             font=FONT_UI, bg=BG_DARK, fg="#6dde84",
                             relief="flat", highlightthickness=1,
                             highlightbackground=BORDER_CLR, padx=10, pady=8)
        sec3.pack(fill="x", pady=(0, 10))

        mass_row1 = tk.Frame(sec3, bg=BG_DARK)
        mass_row1.pack(fill="x", pady=2)
        tk.Label(mass_row1, text="Zmień kategorię na:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._zaw_mass_kat_src = ttk.Combobox(mass_row1,
                                               values=CATEGORIES, font=FONT_UI,
                                               style="Dark.TCombobox", width=12, state="readonly")
        self._zaw_mass_kat_src.set("Python")
        self._zaw_mass_kat_src.pack(side="left", padx=6)
        tk.Label(mass_row1, text="→", font=FONT_BOLD, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._zaw_mass_kat_dst = ttk.Combobox(mass_row1,
                                               values=CATEGORIES, font=FONT_UI,
                                               style="Dark.TCombobox", width=12, state="readonly")
        self._zaw_mass_kat_dst.set("Python")
        self._zaw_mass_kat_dst.pack(side="left", padx=6)
        tk.Button(mass_row1, text="✅ Zmień", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_mass_change_kat).pack(side="left", padx=4)

        mass_row2 = tk.Frame(sec3, bg=BG_DARK)
        mass_row2.pack(fill="x", pady=4)
        tk.Label(mass_row2, text="Dodaj tag do kategorii:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._zaw_mass_tag_kat = ttk.Combobox(mass_row2,
                                               values=["Wszystkie"] + CATEGORIES,
                                               font=FONT_UI, style="Dark.TCombobox",
                                               width=12, state="readonly")
        self._zaw_mass_tag_kat.set("Wszystkie")
        self._zaw_mass_tag_kat.pack(side="left", padx=6)
        self._zaw_mass_tag_val = tk.Entry(mass_row2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                           insertbackground=FG_WHITE, relief="flat",
                                           highlightthickness=1, highlightbackground=BORDER_CLR,
                                           highlightcolor=ACCENT_BLUE, width=18)
        self._zaw_mass_tag_val.pack(side="left", padx=4)
        tk.Button(mass_row2, text="➕ Dodaj tag", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._zaw_mass_add_tag).pack(side="left", padx=4)

        mass_row3 = tk.Frame(sec3, bg=BG_DARK)
        mass_row3.pack(fill="x", pady=2)
        for txt, cmd in [
            ("📤 Eksportuj wszystkie jako ZIP", self._zaw_export_zip),
            ("📋 Eksportuj jako CSV",            self._zaw_export_csv),
            ("📥 Importuj CSV",                  self._zaw_import_csv),
        ]:
            tk.Button(mass_row3, text=txt, font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER,
                      command=cmd).pack(side="left", padx=4)

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
            messagebox.showinfo("Brak frazy", "Podaj frazę do wyszukania.")
            return
        import re as _re
        flags = 0 if self._zaw_case_var.get() else _re.IGNORECASE
        kat_filter = self._zaw_kat_var.get()
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
            messagebox.showinfo("Brak frazy", "Podaj frazę do wyszukania.")
            return
        if not messagebox.askyesno("Zastąp",
                                    f"Zastąpić '{phrase}' → '{replace}'\nwe wszystkich skryptach?"):
            return
        import re as _re
        flags = 0 if self._zaw_case_var.get() else _re.IGNORECASE
        kat_filter = self._zaw_kat_var.get()
        total = 0; affected = 0
        for sc in self.skrypty:
            if kat_filter != "Wszystkie" and sc.get("kategoria") != kat_filter:
                continue
            kod = sc.get("kod", "")
            try:
                pat = phrase if self._zaw_regex_var.get() else _re.escape(phrase)
                new_kod, n = _re.subn(pat, replace, kod, flags=flags)
            except _re.error as ex:
                messagebox.showerror("Błąd regex", str(ex)); return
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
            messagebox.showinfo("Brak duplikatów", "Nie znaleziono duplikatów do usunięcia.")
            return
        if messagebox.askyesno("Usuń duplikaty", f"Usunąć {removed} duplikat(ów)?"):
            self.skrypty = kept
            self._update_count()
            self._refresh_lista()
            self._zaw_log_msg(f"Usunięto {removed} duplikatów.", "ok")

    def _zaw_mass_change_kat(self):
        src = self._zaw_mass_kat_src.get()
        dst = self._zaw_mass_kat_dst.get()
        if src == dst:
            messagebox.showinfo("Bez zmian", "Kategorie są identyczne.")
            return
        changed = 0
        for sc in self.skrypty:
            if sc.get("kategoria") == src:
                sc["kategoria"] = dst
                changed += 1
        self._zaw_log_msg(f"Zmieniono kategorię {src}→{dst} w {changed} skryptach.", "ok")
        self._refresh_lista()
        messagebox.showinfo("Zmieniono", f"Zaktualizowano {changed} skryptów.")

    def _zaw_mass_add_tag(self):
        kat = self._zaw_mass_tag_kat.get()
        tag = self._zaw_mass_tag_val.get().strip()
        if not tag:
            messagebox.showinfo("Brak tagu", "Wpisz tag do dodania.")
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
        messagebox.showinfo("Dodano tag", f"Tag '{tag}' dodany do {changed} skryptów.")

    def _zaw_export_zip(self):
        import zipfile, io
        if not self.skrypty:
            messagebox.showinfo("Brak skryptów", "Baza skryptów jest pusta.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", initialfile="skrypty.zip",
            filetypes=[("ZIP", "*.zip"), ("Wszystkie", "*.*")])
        if not path:
            return
        ext_map = {"Python": ".py", "Bash": ".sh", "PowerShell": ".ps1",
                   "JavaScript": ".js", "SQL": ".sql", "Other": ".txt"}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for sc in self.skrypty:
                kat = sc.get("kategoria", "Other")
                ext = ext_map.get(kat, ".txt")
                fname = f"{kat}/{sc.get('nazwa','skrypt')}{ext}"
                zf.writestr(fname, sc.get("kod", ""))
        self._zaw_log_msg(f"Eksport ZIP: {len(self.skrypty)} skryptów → {path}", "ok")
        messagebox.showinfo("Eksport ZIP", f"Zapisano {len(self.skrypty)} skryptów do:\n{path}")

    def _zaw_export_csv(self):
        import csv
        if not self.skrypty:
            messagebox.showinfo("Brak skryptów", "Baza skryptów jest pusta.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="skrypty.csv",
            filetypes=[("CSV", "*.csv"), ("Wszystkie", "*.*")])
        if not path:
            return
        cols = ["nazwa", "kategoria", "tagi", "opis", "kod"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for sc in self.skrypty:
                w.writerow({c: sc.get(c, "") for c in cols})
        self._zaw_log_msg(f"Eksport CSV: {len(self.skrypty)} skryptów → {path}", "ok")
        messagebox.showinfo("Eksport CSV", f"Zapisano:\n{path}")

    def _zaw_import_csv(self):
        import csv
        path = filedialog.askopenfilename(
            filetypes=[("CSV", "*.csv"), ("Wszystkie", "*.*")])
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
            messagebox.showinfo("Import CSV",
                                f"Dodane: {added}\nZaktualizowane: {updated}\nPominięte: {skipped}")
        except Exception as ex:
            messagebox.showerror("Błąd importu CSV", str(ex))
            self._zaw_log_msg(f"Błąd importu CSV: {ex}", "err")

    def _show_sub_zaawansowane(self):
        self.sub_frames["zaawansowane"].pack(fill="both", expand=True, padx=4, pady=4)

    # ── Import / Eksport listy skryptów ───────────────────────────────────────
    def _lista_importuj(self):
        path = filedialog.askopenfilename(
            title="Importuj skrypty",
            filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
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
            messagebox.showinfo("Import", msg)
        except Exception as e:
            messagebox.showerror("Błąd importu", str(e))

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
        dlg = tk.Toplevel(self)
        dlg.title("Konflikt importu")
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
            tk.Button(btns, text=txt, font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER, command=lambda v=v: pick(v)).pack(side="left", padx=3)
        tk.Checkbutton(dlg, text="zastosuj do wszystkich", variable=var,
                       onvalue="all", offvalue="", bg=BG_DARK, fg=FG_GRAY,
                       selectcolor=BG_INPUT, activebackground=BG_DARK,
                       activeforeground=FG_WHITE, font=FONT_UI).pack(padx=14, pady=(0, 10))
        self.wait_window(dlg)
        return result["v"]

    def _lista_eksportuj(self):
        if not self.skrypty:
            messagebox.showinfo("Brak skryptów", "Baza skryptów jest pusta.")
            return
        path = filedialog.asksaveasfilename(
            title="Eksportuj skrypty",
            defaultextension=".json", initialfile="baza_skryptow.json",
            filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
        if not path:
            return
        try:
            db_write(path, self.skrypty, backup_count=0)
            messagebox.showinfo("Eksport", f"Wyeksportowano {len(self.skrypty)} skrypt(ów) do:\n{path}")
        except Exception as e:
            messagebox.showerror("Błąd eksportu", str(e))

    def _refresh_lista(self):
        query = self.entry_search.get().lower().strip() if hasattr(self, "entry_search") else ""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, s in enumerate(self.skrypty):
            if query and query not in s["nazwa"].lower() \
                     and query not in s["kategoria"].lower() \
                     and query not in s["tagi"].lower():
                continue
            opis_skrot = s["opis"][:80] + ("…" if len(s["opis"]) > 80 else "")
            tag = "odd" if i % 2 == 0 else "even"
            self.tree.insert("", "end", iid=str(i),
                             values=(s["nazwa"], s["kategoria"], s["tagi"], opis_skrot),
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
            messagebox.showinfo("Brak wyboru", "Zaznacz skrypt z listy.")
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
            messagebox.showinfo("Brak wyboru", "Zaznacz skrypt do usunięcia.")
            return
        idx = int(sel[0])
        nazwa = self.skrypty[idx]["nazwa"]
        if messagebox.askyesno("Usuń", f"Usunąć skrypt '{nazwa}'?"):
            self.skrypty.pop(idx)
            self._refresh_lista()
            self._update_count()

    def _kopiuj_kod_z_listy(self, tree=None):
        """Kopiuj kod zaznaczonego skryptu z Treeview do schowka."""
        if tree is None:
            tree = getattr(self, "tree", None)
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz skrypt z listy.")
            return
        idx = int(sel[0])
        if idx < len(self.skrypty):
            self.clipboard_clear()
            self.clipboard_append(self.skrypty[idx]["kod"])
            messagebox.showinfo("Skopiowano", f"Kod skryptu '{self.skrypty[idx]['nazwa']}' skopiowany.")

    def _otworz_skrypt(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz skrypt do otwarcia.")
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
        tk.Label(hdr, text="Advanced Search Pro",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self.lbl_search_stats = tk.Label(hdr, text="Wynikow: -  |  Czas: -",
                                          font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY)
        self.lbl_search_stats.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        paned = tk.Frame(outer, bg=BG_DARK)
        paned.pack(fill="both", expand=True)

        left = tk.Frame(paned, bg=BG_PANEL, width=295)
        left.pack(side="left", fill="y", padx=(6, 0), pady=6)
        left.pack_propagate(False)

        def section(parent, title):
            tk.Frame(parent, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 2))
            tk.Label(parent, text=title, font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w", padx=8)

        tk.Label(left, text="Fraza / wyrazenie:", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=8, pady=(10, 2))
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
            tk.Checkbutton(opts_row, text=text, variable=var,
                           font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search).pack(anchor="w", pady=0)

        section(left, "Operator logiczny")
        op_row = tk.Frame(left, bg=BG_PANEL)
        op_row.pack(fill="x", padx=8, pady=4)
        self.var_logic = tk.StringVar(value="AND")
        for op in ("AND", "OR", "NOT"):
            tk.Radiobutton(op_row, text=op, variable=self.var_logic, value=op,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search).pack(side="left", padx=6)

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
            tk.Checkbutton(fields_frame, text=text, variable=var,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search).pack(anchor="w", pady=1)

        section(left, "Kategoria")
        cat_frame = tk.Frame(left, bg=BG_PANEL)
        cat_frame.pack(fill="x", padx=8, pady=4)
        self.var_cats = {}
        for cat in ["Wszystkie"] + CATEGORIES:
            v = tk.BooleanVar(value=True)
            self.var_cats[cat] = v
            tk.Checkbutton(cat_frame, text=cat, variable=v,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search).pack(anchor="w", pady=1)

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
        tk.Label(sort_row, text="Pole:", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
        self.var_sort_field = tk.StringVar(value="nazwa")
        ttk.Combobox(sort_row, textvariable=self.var_sort_field,
                     values=["nazwa", "kategoria", "tagi"],
                     font=FONT_UI, state="readonly", style="Dark.TCombobox",
                     width=10).pack(side="left", padx=4)
        self.var_sort_dir = tk.StringVar(value="ASC")
        for d in ("ASC", "DESC"):
            tk.Radiobutton(sort_row, text=d, variable=self.var_sort_dir, value=d,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT,
                           command=self._adv_search).pack(side="left", padx=3)
        self.var_sort_field.trace_add("write", lambda *_: self._adv_search())

        section(left, "Limit wynikow")
        limit_row = tk.Frame(left, bg=BG_PANEL)
        limit_row.pack(fill="x", padx=8, pady=4)
        self.var_limit = tk.StringVar(value="Wszystkie")
        ttk.Combobox(limit_row, textvariable=self.var_limit,
                     values=["Wszystkie", "5", "10", "20", "50"],
                     font=FONT_UI, state="readonly", style="Dark.TCombobox",
                     width=12).pack(side="left")
        self.var_limit.trace_add("write", lambda *_: self._adv_search())

        tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x", pady=(10, 4))
        btn_row = tk.Frame(left, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=8, pady=(0, 4))

        def sbtn(master, text, color, cmd):
            tk.Button(master, text=text, font=FONT_UI,
                      bg=color, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER,
                      activeforeground=FG_WHITE, command=cmd).pack(side="left", padx=2, pady=2)

        sbtn(btn_row, "Szukaj",        ACCENT_BLUE, self._adv_search)
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

        for j, (lbl, key) in enumerate([("Wyniki","wyniki"),
                                         ("Historia","historia"),
                                         ("Statystyki","statystyki")]):
            ib = tk.Button(inner_bar, text=lbl, font=FONT_UI,
                           bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                           fg=FG_WHITE       if j == 0 else FG_GRAY,
                           relief="flat", padx=12, pady=5, cursor="hand2",
                           bd=0, highlightthickness=0,
                           command=lambda j=j, k=key: _sel_inner(j, k))
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
            self.adv_tree.heading(col, text=col,
                                   command=lambda c=col: self._adv_sort_col(c))
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
        tk.Label(prev_row, text="Podglad kodu (dopasowanie podswietlone):",
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        tk.Button(prev_row, text="Otworz w edytorze",
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=8, pady=2, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._adv_open_in_editor).pack(side="right", padx=4)
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
        tk.Label(hist_top, text="Historia wyszukiwan",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(side="left")
        tk.Label(hist_top, text="(dwuklik = przywroc zapytanie)",
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=8)
        tk.Button(hist_top, text="Wyczysc historię",
                  font=FONT_UI, bg=BTN_DARK, fg="#e07070", relief="flat",
                  padx=8, pady=2, cursor="hand2",
                  command=self._adv_clear_history).pack(side="right")
        hist_cols = ("Fraza","Pola","Kategoria","Wynikow","Czas","Data")
        hist_vsb = tk.Scrollbar(hist_frame, orient="vertical",
                                 bg=BG_PANEL, troughcolor=BG_PANEL, width=10)
        self.hist_tree = ttk.Treeview(hist_frame, columns=hist_cols,
                                       show="headings", style="Adv.Treeview", height=14)
        for col, w in [("Fraza",160),("Pola",130),("Kategoria",90),
                       ("Wynikow",70),("Czas",70),("Data",130)]:
            self.hist_tree.heading(col, text=col)
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
        tk.Label(stat_top, text="Statystyki bazy skryptow",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(side="left")
        tk.Button(stat_top, text="Odswiez",
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=8, pady=2, cursor="hand2",
                  command=self._adv_refresh_stats).pack(side="right")
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
            terms = [t.lower() for t in terms]

        def match_term(text, term):
            haystack = text if case_sen else text.lower()
            if use_re:
                try:
                    return bool(re.search(term, haystack))
                except re.error:
                    return False
            if whole:
                return bool(re.search(r"\b" + re.escape(term) + r"\b", haystack))
            if fuzzy and len(term) >= 3:
                return term[:3] in haystack
            return term in haystack

        def matches(skrypt):
            fields = []
            if self.var_in_nazwa.get(): fields.append(skrypt.get("nazwa", ""))
            if self.var_in_kat.get():   fields.append(skrypt.get("kategoria", ""))
            if self.var_in_tagi.get():  fields.append(skrypt.get("tagi", ""))
            if self.var_in_opis.get():  fields.append(skrypt.get("opis", ""))
            if self.var_in_kod.get():   fields.append(skrypt.get("kod", ""))
            text = " ".join(fields)
            if not terms:
                return True, 100
            hits = [match_term(text, t) for t in terms]
            if logic == "AND":
                ok = all(hits)
            elif logic == "OR":
                ok = any(hits)
            else:
                ok = not any(hits)
            score = sum(hits) * 20 if ok else 0
            return ok, score

        sel_cats = {c for c, v in self.var_cats.items() if v.get() and c != "Wszystkie"}
        all_cats_on = self.var_cats.get("Wszystkie") and self.var_cats["Wszystkie"].get()

        results = []
        for s in self.skrypty:
            cat_ok = all_cats_on or (s.get("kategoria", "") in sel_cats)
            tag_ok = (tag_filt in s.get("tagi", "").lower()) if tag_filt else True
            ok, score = matches(s)
            if ok and cat_ok and tag_ok:
                results.append((score, s))

        sort_field = self.var_sort_field.get()
        sort_rev   = self.var_sort_dir.get() == "DESC"
        results.sort(key=lambda x: x[1].get(sort_field, "").lower(), reverse=sort_rev)

        limit_val = self.var_limit.get()
        if limit_val != "Wszystkie":
            results = results[:int(limit_val)]

        elapsed = (datetime.datetime.now() - t0).microseconds // 1000

        for row in self.adv_tree.get_children():
            self.adv_tree.delete(row)
        for i, (score, s) in enumerate(results):
            opis_s = s.get("opis","")
            opis_skrot = opis_s[:70] + ("..." if len(opis_s) > 70 else "")
            row_tag = "match" if score >= 80 else ("odd" if i % 2 == 0 else "even")
            self.adv_tree.insert("", "end", iid=str(i),
                                  values=(s.get("nazwa",""), s.get("kategoria",""),
                                          s.get("tagi",""), opis_skrot, f"{score}%"),
                                  tags=(row_tag,))

        fields_active = [n for n, v in [("nazwa", self.var_in_nazwa), ("kat.", self.var_in_kat),
                                         ("tagi", self.var_in_tagi),  ("opis", self.var_in_opis),
                                         ("kod",  self.var_in_kod)] if v.get()]
        self.lbl_search_stats.config(
            text=f"Wynikow: {len(results)} z {len(self.skrypty)}  |  Czas: {elapsed} ms")

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
        nazwa = self.adv_tree.item(sel[0])["values"][0]
        skrypt = next((s for s in self.skrypty if s["nazwa"] == nazwa), None)
        if not skrypt:
            return
        kod = skrypt.get("kod", "")
        preview = kod[:600] + ("..." if len(kod) > 600 else "")
        self.adv_preview.config(state="normal")
        self.adv_preview.delete("1.0", "end")
        self.adv_preview.insert("1.0", preview)
        query = self.adv_entry.get().strip()
        if query and not self.var_regex.get():
            q = query if self.var_case.get() else query.lower()
            hay = preview if self.var_case.get() else preview.lower()
            pos = 0
            while True:
                found = hay.find(q, pos)
                if found == -1:
                    break
                line = preview[:found].count("\n") + 1
                col  = found - preview[:found].rfind("\n") - 1
                s_idx = f"{line}.{col}"
                e_idx = f"{line}.{col + len(query)}"
                self.adv_preview.tag_add("highlight", s_idx, e_idx)
                pos = found + len(q)
        self.adv_preview.config(state="disabled")

    def _adv_open_in_editor(self):
        sel = self.adv_tree.selection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz skrypt z listy wynikow.")
            return
        nazwa = self.adv_tree.item(sel[0])["values"][0]
        skrypt = next((s for s in self.skrypty if s["nazwa"] == nazwa), None)
        if not skrypt:
            return
        self.entry_nazwa.delete(0, "end"); self.entry_nazwa.insert(0, skrypt["nazwa"])
        self.var_kat.set(skrypt["kategoria"])
        self.entry_tagi.delete(0, "end"); self.entry_tagi.insert(0, skrypt["tagi"])
        self.text_opis.delete("1.0", "end"); self.text_opis.insert("1.0", skrypt["opis"])
        self.text_opis.config(fg=FG_WHITE)
        self.text_kod.delete("1.0", "end"); self.text_kod.insert("1.0", skrypt["kod"])
        self._update_line_nums()
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
        self.var_limit.set("Wszystkie")
        self.var_sort_field.set("nazwa"); self.var_sort_dir.set("ASC")
        for row in self.adv_tree.get_children():
            self.adv_tree.delete(row)
        self.adv_preview.config(state="normal")
        self.adv_preview.delete("1.0", "end")
        self.adv_preview.config(state="disabled")
        self.lbl_search_stats.config(text="Wynikow: -  |  Czas: -")

    def _adv_copy_results(self):
        rows = ["	".join(str(v) for v in self.adv_tree.item(iid)["values"])
                for iid in self.adv_tree.get_children()]
        if rows:
            self.clipboard_clear(); self.clipboard_append("\n".join(rows))
            messagebox.showinfo("Skopiowano", f"Skopiowano {len(rows)} wierszy do schowka.")
        else:
            messagebox.showinfo("Brak wynikow", "Brak wynikow do skopiowania.")

    def _adv_export(self):
        rows = ["	".join(str(v) for v in self.adv_tree.item(iid)["values"])
                for iid in self.adv_tree.get_children()]
        if not rows:
            messagebox.showinfo("Brak wynikow", "Brak wynikow do eksportu."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Plik tekstowy","*.txt"),("CSV","*.csv")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("Nazwa	Kategoria	Tagi	Opis	Trafnosc\n" + "\n".join(rows))
            messagebox.showinfo("Eksport", f"Wyeksportowano {len(rows)} wierszy do:\n{path}")

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
        if messagebox.askyesno("Wyczysc", "Wyczyścić całą historię wyszukiwań?"):
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
        lines = ["=" * 44, "  BAZA SKRYPTOW - Statystyki", "=" * 44,
                 f"  Laczna liczba skryptow  : {total}",
                 f"  Laczna liczba linii kodu : {total_lines}",
                 f"  Wpisy historii wyszukiwan: {len(self.search_history)}",
                 "", "  Rozklad wg kategorii:", "  " + "-" * 42]
        for cat in CATEGORIES:
            count = by_cat.get(cat, 0)
            bar = chr(9608) * count + chr(9617) * max(0, 10 - count)
            pct = (count / total * 100) if total else 0
            lines.append(f"  {cat:<12} {bar}  {count:>3}  ({pct:.1f}%)")
        lines += ["", "  Ostatnio wyszukiwane:", "  " + "-" * 42]
        for h in self.search_history[:5]:
            lines.append(f"  [{h['data']}]  \"{h['fraza']}\"  -> {h['wynikow']} wynikow")
        if not self.search_history:
            lines.append("  (brak historii)")
        lines.append("=" * 44)
        self.stat_text.config(state="normal")
        self.stat_text.delete("1.0", "end")
        self.stat_text.insert("1.0", "\n".join(lines))
        self.stat_text.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # ZAKŁADKA: Moduły — 5 pod-zakładek
    # ══════════════════════════════════════════════════════════════════════════
    def _build_moduly_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["moduly"] = outer

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙ Moduły — Centrum Zarządzania",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self.lbl_mod_status = tk.Label(hdr, text="Status: gotowy",
                                        font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_mod_status.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        mod_sub_bar = tk.Frame(outer, bg=BG_PANEL)
        mod_sub_bar.pack(fill="x")

        mod_content = tk.Frame(outer, bg=BG_DARK)
        mod_content.pack(fill="both", expand=True)

        self._mod_btns   = []
        self._mod_frames = {}

        def sel_mod(idx, key):
            for j, b in enumerate(self._mod_btns):
                b.configure(bg=BG_SUBTAB_ACT if j == idx else BG_SUBTAB_INACT,
                             fg=FG_WHITE       if j == idx else FG_GRAY)
            for f in self._mod_frames.values():
                f.pack_forget()
            self._mod_frames[key].pack(fill="both", expand=True)

        mod_tabs = [
            ("📋 Info",           "info"),
            ("🔬 Diagnostyka",    "diag"),
            ("🔗 Łączenie funkcji","laczen"),
            ("⚡ Testy osiągów",  "testy"),
            ("🔧 Naprawa",        "naprawa"),
            ("🔌 Kreator Pluginów","plugin"),
        ]
        for j, (lbl, key) in enumerate(mod_tabs):
            b = tk.Button(mod_sub_bar, text=lbl, font=FONT_UI,
                          bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY,
                          relief="flat", padx=14, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda j=j, k=key: sel_mod(j, k))
            b.pack(side="left")
            self._mod_btns.append(b)

        # Buduj każdą pod-zakładkę
        self._build_mod_info(mod_content)
        self._build_mod_diag(mod_content)
        self._build_mod_laczen(mod_content)
        self._build_mod_testy(mod_content)
        self._build_mod_naprawa(mod_content)
        self._build_mod_plugin(mod_content)

        # pokaż pierwszą
        sel_mod(0, "info")

    def _show_moduly(self):
        self.main_frames["moduly"].pack(fill="both", expand=True)

    # ── helper: sekcja nagłówkowa ─────────────────────────────────────────────
    def _mod_section(self, parent, title):
        tk.Frame(parent, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 2))
        tk.Label(parent, text=title, font=FONT_BOLD, bg=BG_PANEL,
                 fg=ACCENT_BLUE).pack(anchor="w", padx=10)

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 1: INFO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_info(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["info"] = frame

        # górny pasek przycisków
        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        tk.Button(bar, text="🔄 Odśwież info", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._mod_refresh_info).pack(side="left", padx=2)
        tk.Button(bar, text="📋 Kopiuj raport", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._mod_copy_info).pack(side="left", padx=2)
        tk.Button(bar, text="💾 Eksportuj raport", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._mod_export_info).pack(side="left", padx=2)
        tk.Frame(bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=10, pady=4)
        tk.Button(bar, text="📥 Załaduj", font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("info")).pack(side="left", padx=2)
        tk.Button(bar, text="🔌 Odłącz", font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("info")).pack(side="left", padx=2)

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
        tk.Label(left_col, text="📦 Informacje o bazie skryptów",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 4))

        self.info_text = tk.Text(left_col, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                  relief="flat", state="disabled", wrap="word",
                                  highlightthickness=1, highlightbackground=BORDER_CLR)
        sc1 = tk.Scrollbar(left_col, orient="vertical", bg=BG_PANEL,
                            troughcolor=BG_PANEL, width=8, command=self.info_text.yview)
        sc1.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.info_text.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        self.info_text.config(yscrollcommand=sc1.set)

        # ─ Prawa kolumna: środowisko Python ──────────────────────────────────
        tk.Label(right_col, text="🐍 Środowisko Python",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 4))

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
            "  BAZA SKRYPTÓW — Pełny raport informacyjny",
            "=" * 46,
            f"  Wersja aplikacji    : 3.0",
            f"  Data / czas         : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "  ── Zawartość bazy ──────────────────────",
            f"  Łączna liczba skryptów : {total}",
            f"  Łączna liczba linii    : {lines_t}",
            f"  Unikalne tagi          : {len(tags_all)}",
            f"  Wpisy historii szukaj  : {len(self.search_history)}",
            "",
            "  ── Rozkład wg kategorii ────────────────",
        ]
        for cat in CATEGORIES:
            cnt = by_cat.get(cat, 0)
            bar = "█" * cnt + "░" * max(0, 12 - cnt)
            pct = (cnt / total * 100) if total else 0
            lines.append(f"  {cat:<12} {bar}  {cnt:>3}  ({pct:.1f}%)")

        if tags_all:
            lines += ["", "  ── Popularne tagi ──────────────────────"]
            for t in sorted(tags_all)[:20]:
                lines.append(f"  • {t}")

        lines += ["", "=" * 46]
        self._set_text(self.info_text, "\n".join(lines))

        env_lines = [
            "=" * 46,
            "  ŚRODOWISKO PYTHON",
            "=" * 46,
            f"  Python              : {sys.version.split()[0]}",
            f"  Platform            : {platform.system()} {platform.release()}",
            f"  Architektura        : {platform.machine()}",
            f"  Procesor            : {platform.processor() or 'n/d'}",
            f"  Plik wykonywalny    : {sys.executable}",
            f"  Kodowanie           : {sys.getdefaultencoding().upper()}",
            "",
            "  ── Zainstalowane moduły (stdlib) ───────",
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
        content = self.info_text.get("1.0", "end-1c") + "\n\n" + self.info_env_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Skopiowano", "Raport skopiowany do schowka.")

    def _mod_export_info(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Plik tekstowy", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            content = self.info_text.get("1.0", "end-1c") + "\n\n" + self.info_env_text.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo("Eksport", f"Raport zapisany:\n{path}")

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 2: DIAGNOSTYKA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_diag(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["diag"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        tk.Button(bar, text="▶ Uruchom diagnostykę", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._run_diag).pack(side="left", padx=2)
        tk.Button(bar, text="🧹 Wyczyść log", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=lambda: self._set_text(self.diag_text, "")).pack(side="left", padx=2)
        tk.Button(bar, text="💾 Zapisz log", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._diag_save_log).pack(side="left", padx=2)
        self.lbl_diag_ok = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_diag_ok.pack(side="right", padx=8)
        tk.Button(bar, text="🔌 Odłącz", font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("diag")).pack(side="right", padx=2)
        tk.Button(bar, text="📥 Załaduj", font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("diag")).pack(side="right", padx=2)
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
            tk.Checkbutton(chk_row, text=lbl, variable=v, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT).grid(row=i // 4, column=i % 4,
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
        self.diag_text.config(state="normal")
        self.diag_text.delete("1.0", "end")
        errors = 0
        warnings = 0

        def log(msg, tag=""):
            self.diag_text.insert("end", msg + "\n", tag)

        log("=" * 54, "head")
        log(f"  DIAGNOSTYKA — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "head")
        log(f"  Skryptów w bazie: {len(self.skrypty)}", "head")
        log("=" * 54, "head")

        # 1. Spójność danych
        if self.diag_checks["spojnosc"].get():
            log("\n[1] Spójność danych", "head")
            required = ["nazwa", "kategoria", "tagi", "opis", "kod"]
            for i, s in enumerate(self.skrypty):
                missing = [f for f in required if f not in s]
                if missing:
                    log(f"  ✘ Skrypt #{i} '{s.get('nazwa','?')}' — brak pól: {missing}", "error")
                    errors += 1
                else:
                    log(f"  ✔ Skrypt #{i} '{s['nazwa']}' — OK", "ok")

        # 2. Brakujące pola
        if self.diag_checks["pola"].get():
            log("\n[2] Brakujące / puste pola", "head")
            for i, s in enumerate(self.skrypty):
                empty = [f for f in ["nazwa", "kategoria", "kod"] if not s.get(f, "").strip()]
                if empty:
                    log(f"  ⚠ Skrypt #{i} '{s.get('nazwa','?')}' — puste: {empty}", "warn")
                    warnings += 1
                else:
                    log(f"  ✔ Skrypt #{i} '{s.get('nazwa','?')}' — wszystkie pola wypełnione", "ok")

        # 3. Duplikaty
        if self.diag_checks["duplikaty"].get():
            log("\n[3] Duplikaty nazw", "head")
            names = [s.get("nazwa", "") for s in self.skrypty]
            seen = set()
            dups = set()
            for n in names:
                if n in seen:
                    dups.add(n)
                seen.add(n)
            if dups:
                for d in dups:
                    log(f"  ✘ Duplikat: '{d}'", "error")
                    errors += 1
            else:
                log("  ✔ Brak duplikatów nazw", "ok")

        # 4. Puste skrypty
        if self.diag_checks["puste"].get():
            log("\n[4] Puste skrypty (bez kodu)", "head")
            any_empty = False
            for i, s in enumerate(self.skrypty):
                if not s.get("kod", "").strip():
                    log(f"  ⚠ Skrypt #{i} '{s.get('nazwa','?')}' — brak kodu!", "warn")
                    warnings += 1
                    any_empty = True
            if not any_empty:
                log("  ✔ Wszystkie skrypty mają kod", "ok")

        # 5. UTF-8
        if self.diag_checks["utf8"].get():
            log("\n[5] Kodowanie UTF-8", "head")
            for i, s in enumerate(self.skrypty):
                try:
                    s.get("kod", "").encode("utf-8")
                    log(f"  ✔ Skrypt #{i} '{s.get('nazwa','?')}' — UTF-8 OK", "ok")
                except UnicodeEncodeError as e:
                    log(f"  ✘ Skrypt #{i} '{s.get('nazwa','?')}' — błąd UTF-8: {e}", "error")
                    errors += 1

        # 6. Składnia Python
        if self.diag_checks["skladnia"].get():
            log("\n[6] Sprawdzanie składni Python", "head")
            for i, s in enumerate(self.skrypty):
                if s.get("kategoria") == "Python":
                    try:
                        ast.parse(s.get("kod", ""))
                        log(f"  ✔ '{s['nazwa']}' — składnia poprawna", "ok")
                    except SyntaxError as e:
                        log(f"  ✘ '{s['nazwa']}' — błąd składni linia {e.lineno}: {e.msg}", "error")
                        errors += 1

        # 7. Niebezpieczne wzorce
        if self.diag_checks["niebezp"].get():
            log("\n[7] Niebezpieczne wzorce kodu", "head")
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
                    log(f"  ⚠ '{s.get('nazwa','?')}' — wzorce: {', '.join(found)}", "warn")
                    warnings += 1
                else:
                    log(f"  ✔ '{s.get('nazwa','?')}' — brak niebezpiecznych wzorców", "ok")

        log(f"\n{'=' * 54}", "head")
        log(f"  PODSUMOWANIE: ✘ Błędy: {errors}  ⚠ Ostrzeżenia: {warnings}", "head")
        log("=" * 54, "head")
        self.lbl_diag_ok.config(
            text=f"✘ {errors} błędów  ⚠ {warnings} ostrzeżeń",
            fg="#e07070" if errors else ("#f0c050" if warnings else "#6dde84"))
        self.diag_text.config(state="disabled")

    def _diag_save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Log", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.diag_text.get("1.0", "end-1c"))
            messagebox.showinfo("Zapisano", f"Log zapisany:\n{path}")

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
        tk.Label(hdr, text="🔗 Łączenie modułów — załaduj pliki lub skrypty z bazy, ułóż kolejność, połącz",
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
        self.lbl_laczen_info = tk.Label(hdr, text="Modułów: 0 | Kolejka: 0",
                                         font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
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

        tk.Label(col1, text="📦 Dostępne moduły",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))

        # przyciski załaduj
        btn1 = tk.Frame(col1, bg=BG_PANEL)
        btn1.pack(fill="x", padx=6, pady=(0, 4))
        tk.Button(btn1, text="📂 Załaduj plik(i)", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._laczen_load_files).pack(side="left", padx=2)
        tk.Button(btn1, text="📋 Z bazy", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_load_from_base).pack(side="left", padx=2)

        # filtr modułów
        flt = tk.Frame(col1, bg=BG_PANEL)
        flt.pack(fill="x", padx=6, pady=(0, 2))
        tk.Label(flt, text="🔍", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
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
        tk.Button(btn1b, text="➕ Dodaj do kolejki", font=FONT_UI,
                  bg="#3a6040", fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#4a7850",
                  command=self._laczen_add_to_queue).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(btn1b, text="❌ Odłącz", font=FONT_UI,
                  bg="#603030", fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground="#804040",
                  command=self._laczen_detach).pack(side="left", padx=2)

        # ════════════════════════════
        # KOLUMNA 2: Kolejka łączenia
        # ════════════════════════════
        col2 = tk.Frame(body, bg=BG_PANEL, width=240,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        col2.pack(side="left", fill="y", padx=(0, 4))
        col2.pack_propagate(False)

        tk.Label(col2, text="🗂 Kolejka łączenia",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 2))
        tk.Label(col2, text="(dwuklik = usuń z kolejki)",
                 font=("Consolas", 7), bg=BG_PANEL, fg=FG_GRAY).pack(anchor="w", padx=10)

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
        tk.Button(btn2, text="⬆", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._laczen_queue_up).pack(side="left", padx=2)
        tk.Button(btn2, text="⬇", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._laczen_queue_down).pack(side="left", padx=2)
        tk.Button(btn2, text="🗑 Wyczyść", font=FONT_UI, bg="#603030", fg=FG_WHITE,
                  relief="flat", padx=6, pady=3, cursor="hand2",
                  activebackground="#804040",
                  command=self._laczen_queue_clear).pack(side="left", padx=2, fill="x", expand=True)

        # tryb łączenia
        tk.Frame(col2, bg=BORDER_CLR, height=1).pack(fill="x", pady=(6, 2))
        tk.Label(col2, text="Tryb łączenia:", font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w", padx=10, pady=(2, 2))
        self.var_laczen_mode = tk.StringVar(value="sekwencja")
        modes = [
            ("Sekwencja",  "sekwencja"),
            ("Funkcje",    "funkcje"),
            ("Pipeline",   "pipeline"),
            ("Klasa",      "klasa"),
        ]
        for lbl, val in modes:
            tk.Radiobutton(col2, text=lbl, variable=self.var_laczen_mode, value=val,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT).pack(anchor="w", padx=14)

        tk.Frame(col2, bg=BORDER_CLR, height=1).pack(fill="x", pady=(6, 2))
        tk.Label(col2, text="Nazwa wynikowego skryptu:",
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(anchor="w", padx=10)
        self.laczen_out_name = tk.Entry(col2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                         insertbackground=FG_WHITE, relief="flat",
                                         highlightthickness=1, highlightbackground=BORDER_CLR,
                                         highlightcolor=ACCENT_BLUE)
        self.laczen_out_name.insert(0, "polaczony_skrypt")
        self.laczen_out_name.pack(fill="x", padx=8, pady=4)

        tk.Button(col2, text="⚡ Połącz wszystkie w kolejce", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=8, pady=6,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._laczen_run).pack(padx=8, pady=(0, 8), fill="x")

        # ════════════════════════════
        # KOLUMNA 3: Podgląd wyniku
        # ════════════════════════════
        col3 = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        col3.pack(side="left", fill="both", expand=True)

        tk.Label(col3, text="📄 Podgląd połączonego kodu:",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 4))

        btn3 = tk.Frame(col3, bg=BG_PANEL)
        btn3.pack(fill="x", padx=8, pady=(0, 4))
        tk.Button(btn3, text="📋 Kopiuj", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_copy).pack(side="left", padx=2)
        tk.Button(btn3, text="💾 Zapisz w bazie", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_save_as_script).pack(side="left", padx=2)
        tk.Button(btn3, text="📁 Eksportuj .py", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_export).pack(side="left", padx=2)
        tk.Button(btn3, text="🔄 Odśwież", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._laczen_refresh_modules).pack(side="right", padx=2)

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
            text=f"Modułów: {len(self._laczen_modules)} | Kolejka: {len(self._laczen_queue)}")

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
            title="Wybierz pliki modułów (można zaznaczyć wiele)",
            filetypes=[
                ("Skrypty Python", "*.py"),
                ("Bash / Shell",   "*.sh"),
                ("PowerShell",     "*.ps1"),
                ("JavaScript",     "*.js"),
                ("SQL",            "*.sql"),
                ("Tekstowe",       "*.txt"),
                ("Wszystkie",      "*.*"),
            ])
        if not paths:
            return
        loaded = 0
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    kod = fh.read()
                name = os.path.basename(path)
                ext  = os.path.splitext(name)[1].lower()
                kat  = {".py": "Python", ".sh": "Bash", ".ps1": "PowerShell",
                        ".js": "JavaScript", ".sql": "SQL"}.get(ext, "Other")
                self._laczen_modules[name] = {
                    "nazwa": name, "kategoria": kat,
                    "opis": f"Załadowany z pliku: {path}",
                    "kod": kod, "zrodlo": "plik", "sciezka": path,
                }
                loaded += 1
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można wczytać:\n{path}\n{e}")
        self._laczen_refresh_modules()
        messagebox.showinfo("Załadowano", f"Załadowano {loaded} plik(ów) jako moduły.\n"
                                          f"Dwukliknij nazwę lub użyj 'Dodaj do kolejki'.")

    def _laczen_load_from_base(self):
        """Okno dialogowe: zaznacz skrypty z bazy i załaduj jako moduły."""
        if not self.skrypty:
            messagebox.showinfo("Brak skryptów", "Baza skryptów jest pusta.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Załaduj moduły z bazy skryptów")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("480x420")
        dlg.resizable(True, True)
        dlg.grab_set()

        tk.Label(dlg, text="Zaznacz skrypty do załadowania (Ctrl+klik = wiele):",
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(anchor="w", padx=10, pady=(10, 4))

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
                messagebox.showwarning("Brak wyboru", "Zaznacz przynajmniej jeden skrypt.", parent=dlg)
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
            messagebox.showinfo("Załadowano",
                                f"Załadowano {len(sel)} moduł(ów) z bazy.\n"
                                f"Teraz dodaj je do kolejki łączenia.")

        tk.Button(btn_row, text="✅ Załaduj zaznaczone", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=12, pady=5,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=zaladuj).pack(side="left", padx=4)
        tk.Button(btn_row, text="Anuluj", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=dlg.destroy).pack(side="left", padx=4)
        tk.Button(btn_row, text="Zaznacz wszystkie", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=lambda: lb.select_set(0, "end")).pack(side="right", padx=4)

    def _laczen_detach(self):
        """Odłącz zaznaczone moduły z listy dostępnych."""
        sel = self.laczen_mod_list.curselection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz moduł(y) do odłączenia.")
            return
        names = [self.laczen_mod_list.get(i).split(" ", 1)[1] for i in sel]
        if not messagebox.askyesno("Odłącz moduły",
                                    f"Odłączyć {len(names)} moduł(ów)?\n" + "\n".join(f"• {n}" for n in names)):
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
        info  = (f"Nazwa    : {m['nazwa']}\n"
                 f"Kategoria: {m['kategoria']}\n"
                 f"Źródło   : {m.get('zrodlo','?')}\n"
                 f"Linie    : {linie}\n"
                 f"Opis     : {m.get('opis','')[:60]}")
        self._set_text(self.laczen_mod_info, info)

    def _laczen_add_to_queue(self):
        """Dodaj zaznaczone moduły do kolejki łączenia."""
        sel = self.laczen_mod_list.curselection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz moduł(y) do dodania do kolejki.")
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
            messagebox.showinfo("Info", "Zaznaczone moduły są już w kolejce.")

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
        if self._laczen_queue and messagebox.askyesno("Wyczyść kolejkę", "Wyczyścić całą kolejkę?"):
            self._laczen_queue.clear()
            self._laczen_refresh_queue()

    def _laczen_run(self):
        if not self._laczen_queue:
            messagebox.showwarning("Pusta kolejka",
                                   "Dodaj przynajmniej jeden moduł do kolejki łączenia.")
            return
        missing = [n for n in self._laczen_queue if n not in self._laczen_modules]
        if missing:
            messagebox.showerror("Brakujące moduły",
                                  "Brakuje modułów:\n" + "\n".join(f"• {n}" for n in missing))
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
        messagebox.showinfo("Skopiowano", "Połączony kod skopiowany do schowka.")

    def _laczen_save_as_script(self):
        kod  = self.laczen_out_text.get("1.0", "end-1c")
        name = self.laczen_out_name.get().strip() or "polaczony_skrypt"
        if not kod.strip():
            messagebox.showwarning("Brak kodu", "Najpierw połącz skrypty.")
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
                messagebox.showinfo("Zapisano", f"Skrypt '{name}' zaktualizowany w bazie.")
                return
        self.skrypty.append(skrypt)
        self._rebuild_index()
        self._update_count()
        self._after_db_change()
        messagebox.showinfo("Zapisano", f"Skrypt '{name}' dodany do bazy.")

    def _laczen_export(self):
        kod = self.laczen_out_text.get("1.0", "end-1c")
        if not kod.strip():
            messagebox.showwarning("Brak kodu", "Najpierw połącz skrypty.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python", "*.py"), ("Tekstowy", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(kod)
            messagebox.showinfo("Eksport", f"Wyeksportowano:\n{path}")

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 4: TESTY OSIĄGÓW
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_testy(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["testy"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        tk.Button(bar, text="▶ Uruchom testy", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._run_testy).pack(side="left", padx=2)
        tk.Button(bar, text="🔄 Odśwież listę", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._testy_refresh).pack(side="left", padx=2)
        tk.Button(bar, text="📊 Eksportuj wyniki", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._testy_export).pack(side="left", padx=2)
        self.lbl_testy_status = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_testy_status.pack(side="right", padx=8)
        tk.Button(bar, text="🔌 Odłącz", font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("testy")).pack(side="right", padx=2)
        tk.Button(bar, text="📥 Załaduj", font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("testy")).pack(side="right", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # górna część: tabela wyników
        tk.Label(body, text="📊 Wyniki testów osiągów:",
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE).pack(anchor="w", pady=(0, 4))

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
            self.testy_tree.heading(col, text=col)
            self.testy_tree.column(col, width=w, minwidth=50)
        self.testy_tree.pack(fill="both", expand=True)
        self.testy_tree.tag_configure("A", foreground="#6dde84")
        self.testy_tree.tag_configure("B", foreground="#7ec8e3")
        self.testy_tree.tag_configure("C", foreground="#f0c050")
        self.testy_tree.tag_configure("D", foreground="#e07070")

        # dolna część: szczegóły
        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(6, 2))
        tk.Label(body, text="Szczegóły wybranego skryptu:",
                 font=FONT_BOLD, bg=BG_DARK, fg=FG_WHITE).pack(anchor="w")
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
        self._testy_refresh()
        if not self.skrypty:
            messagebox.showinfo("Brak skryptów", "Dodaj skrypty do bazy przed testami.")
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
                ocena, grade = "A — Prosta", "A"
            elif linie < 80 and zloz_cnt < 15:
                ocena, grade = "B — Dobra",  "B"
            elif linie < 200:
                ocena, grade = "C — Średnia", "C"
            else:
                ocena, grade = "D — Złożona", "D"

            tag = "odd" if i % 2 == 0 else "even"
            self.testy_tree.insert("", "end", iid=str(i),
                                   values=(s["nazwa"], s.get("kategoria","?"),
                                           linie, znaki, tokeny, zloz_cnt, ocena),
                                   tags=(grade,))
            self._testy_results.append({
                "nazwa": s["nazwa"], "linie": linie, "znaki": znaki,
                "tokeny": tokeny, "zlozonosc": zloz_cnt, "ocena": ocena, "kod": kod
            })

        self.lbl_testy_status.config(text=f"Przetestowano {len(self.skrypty)} skryptów",
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
            f"Skrypt   : {r['nazwa']}\n"
            f"Linie    : {r['linie']}\n"
            f"Znaki    : {r['znaki']}\n"
            f"Tokeny~  : {r['tokeny']}\n"
            f"Złożoność: {r['zlozonosc']} (if/for/while/def/class/try)\n"
            f"Ocena    : {r['ocena']}\n"
            f"\nSłowa kluczowe:\n" +
            "\n".join(f"  {k:<10} x{v}" for k, v in kw_counts.items())
        )
        self._set_text(self.testy_detail, detail)

    def _testy_export(self):
        if not self._testy_results:
            messagebox.showinfo("Brak danych", "Najpierw uruchom testy.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Raport", "*.txt"), ("CSV", "*.csv"), ("Wszystkie", "*.*")])
        if path:
            lines = ["Nazwa;Linie;Znaki;Tokeny;Złożoność;Ocena"]
            for r in self._testy_results:
                lines.append(f"{r['nazwa']};{r['linie']};{r['znaki']};{r['tokeny']};{r['zlozonosc']};{r['ocena']}")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            messagebox.showinfo("Eksport", f"Wyniki zapisane:\n{path}")

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 5: NAPRAWA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_naprawa(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["naprawa"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        tk.Button(bar, text="🔍 Znajdź problemy", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._naprawa_scan).pack(side="left", padx=2)
        tk.Button(bar, text="🔧 Napraw wszystkie", font=FONT_UI,
                  bg="#5a3080", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a40a0",
                  command=self._naprawa_fix_all).pack(side="left", padx=2)
        tk.Button(bar, text="✅ Napraw zaznaczony", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._naprawa_fix_selected).pack(side="left", padx=2)
        tk.Button(bar, text="💾 Zapisz raport", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._naprawa_save).pack(side="left", padx=2)
        self.lbl_naprawa_st = tk.Label(bar, text="", font=FONT_UI, bg=BG_PANEL, fg="#7ec8e3")
        self.lbl_naprawa_st.pack(side="right", padx=8)
        tk.Button(bar, text="🔌 Odłącz", font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("naprawa")).pack(side="right", padx=2)
        tk.Button(bar, text="📥 Załaduj", font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("naprawa")).pack(side="right", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # opcje naprawy
        opts = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        opts.pack(fill="x", pady=(0, 6))
        tk.Label(opts, text="Opcje automatycznej naprawy:",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(6, 2))
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
            tk.Checkbutton(chk_row, text=lbl, variable=v, font=FONT_UI,
                           bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT
                           ).grid(row=i // 3, column=i % 3, padx=12, pady=2, sticky="w")

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
            self.naprawa_tree.heading(col, text=col)
            self.naprawa_tree.column(col, width=w, minwidth=60)
        self.naprawa_tree.pack(fill="both", expand=True)
        self.naprawa_tree.tag_configure("high",   foreground="#e07070")
        self.naprawa_tree.tag_configure("medium", foreground="#f0c050")
        self.naprawa_tree.tag_configure("low",    foreground="#7ec8e3")
        self.naprawa_tree.tag_configure("fixed",  foreground="#6dde84")

        # log naprawy
        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(4, 2))
        tk.Label(body, text="Log naprawy:", font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE).pack(anchor="w")
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
                                             problem, priorytet, "Oczekuje"),
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
            text=f"Znaleziono {cnt} problemów",
            fg="#e07070" if cnt else "#6dde84")
        self._naprawa_log_add(
            f"Skan ukończony: {cnt} problemów w {len(self.skrypty)} skryptach.\n", "head")

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
            messagebox.showinfo("Brak danych", "Najpierw wykonaj skan.")
            return
        naprawiono = 0
        for issue in self._naprawa_issues:
            if self._naprawa_fix_one(issue):
                issue["status"] = "Naprawiono"
                self.naprawa_tree.item(issue["iid"],
                    values=(self.skrypty[issue["skrypt_idx"]].get("nazwa","?"),
                            issue["problem"], issue["priorytet"], "✔ Naprawiono"),
                    tags=("fixed",))
                naprawiono += 1
                self._naprawa_log_add(
                    f"  ✔ '{self.skrypty[issue['skrypt_idx']].get('nazwa','?')}' — {issue['problem']}\n", "ok")
        self._naprawa_log_add(f"Naprawiono {naprawiono} problemów.\n", "head")
        self.lbl_naprawa_st.config(text=f"Naprawiono {naprawiono}", fg="#6dde84")

    def _naprawa_fix_selected(self):
        sel = self.naprawa_tree.selection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz problem z listy.")
            return
        for iid in sel:
            issue = next((x for x in self._naprawa_issues if x["iid"] == iid), None)
            if issue and self._naprawa_fix_one(issue):
                issue["status"] = "Naprawiono"
                self.naprawa_tree.item(iid,
                    values=(self.skrypty[issue["skrypt_idx"]].get("nazwa","?"),
                            issue["problem"], issue["priorytet"], "✔ Naprawiono"),
                    tags=("fixed",))
                self._naprawa_log_add(
                    f"  ✔ '{self.skrypty[issue['skrypt_idx']].get('nazwa','?')}' — {issue['problem']}\n", "ok")

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
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Raport", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            lines = [f"RAPORT NAPRAWY — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]
            for issue in self._naprawa_issues:
                idx = issue["skrypt_idx"]
                n   = self.skrypty[idx].get("nazwa","?") if idx < len(self.skrypty) else "?"
                lines.append(f"[{issue['priorytet']}] {n} — {issue['problem']} — {issue['status']}")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            messagebox.showinfo("Zapisano", f"Raport naprawy zapisany:\n{path}")

    # ── helper ────────────────────────────────────────────────────────────────
    def _set_text(self, widget, content):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.config(state="disabled")

    # ── Wspólne pomocniki: Załaduj / Odłącz dla pod-zakładek Modułów ─────────
    def _mod_zaladuj(self, tab_key):
        path = filedialog.askopenfilename(
            title=f"Załaduj moduł — {tab_key}",
            filetypes=[("Python", "*.py"), ("Bash", "*.sh"),
                       ("PowerShell", "*.ps1"), ("JavaScript", "*.js"),
                       ("SQL", "*.sql"), ("Wszystkie", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                kod = fh.read()
            name = os.path.basename(path)
            # dodaj do bazy jako nowy skrypt jeśli nie istnieje
            existing = [s["nazwa"] for s in self.skrypty]
            if name not in existing:
                ext = os.path.splitext(name)[1].lower()
                kat = {".py": "Python", ".sh": "Bash", ".ps1": "PowerShell",
                       ".js": "JavaScript", ".sql": "SQL"}.get(ext, "Other")
                self.skrypty.append(sc_normalize({
                    "nazwa": name, "kategoria": kat,
                    "tagi": f"modul,{tab_key}",
                    "opis": f"Załadowany jako moduł z: {path}",
                    "kod": kod,
                }))
                self._rebuild_index()
                self._update_count()
                self._after_db_change()
                messagebox.showinfo("Załadowano",
                    f"Moduł '{name}' załadowany i dodany do bazy skryptów.")
            else:
                messagebox.showinfo("Załadowano",
                    f"Plik '{name}' już istnieje w bazie — pomięto duplikat.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def _mod_odlacz(self, tab_key):
        # Odłącz = usuń skrypty otagowane jako moduł tej zakładki
        candidates = [s for s in self.skrypty if tab_key in s.get("tagi", "")]
        if not candidates:
            messagebox.showinfo("Odłącz", f"Brak modułów oznaczonych tagiem '{tab_key}'.")
            return
        names = [s["nazwa"] for s in candidates]
        if messagebox.askyesno("Odłącz moduły",
                               f"Odłączyć {len(names)} moduł(ów)?\n" +
                               "\n".join(f"• {n}" for n in names[:10]) +
                               ("\n…" if len(names) > 10 else "")):
            self.skrypty = [s for s in self.skrypty if tab_key not in s.get("tagi", "")]
            self._update_count()
            messagebox.showinfo("Odłączono", f"Odłączono {len(names)} moduł(ów).")

    # ══════════════════════════════════════════════════════════════════════════
    # MOD 6: KREATOR PLUGINÓW
    # ══════════════════════════════════════════════════════════════════════════
    def _build_mod_plugin(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._mod_frames["plugin"] = frame

        # ── nagłówek ──────────────────────────────────────────────────────────
        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔌 Kreator Pluginów — generuj gotowy plugin z nowymi komendami",
                 font=("Consolas", 11, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self.lbl_plugin_status = tk.Label(hdr, text="Gotowy do generowania",
                                           font=FONT_UI, bg=BG_PANEL, fg="#6dde84")
        self.lbl_plugin_status.pack(side="right", padx=8)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # ════════════════
        # LEWA: formularz
        # ════════════════
        left = tk.Frame(body, bg=BG_PANEL, width=320,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="y", padx=(0, 5))
        left.pack_propagate(False)

        def section(txt):
            tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 2))
            tk.Label(left, text=txt, font=FONT_BOLD, bg=BG_PANEL,
                     fg=ACCENT_BLUE).pack(anchor="w", padx=10)

        # — Podstawowe info —
        tk.Label(left, text="📦 Informacje o pluginie",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(10, 4))

        def lbl_entry(parent, label, width=28):
            row = tk.Frame(parent, bg=BG_PANEL)
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=label, font=FONT_UI, bg=BG_PANEL,
                     fg=FG_GRAY, width=14, anchor="w").pack(side="left")
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
            tk.Radiobutton(left, text=lbl, variable=self.var_plugin_typ, value=val,
                           font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT).pack(anchor="w", padx=16)

        section("📋 Komendy / funkcje")
        tk.Label(left, text="Dodaj komendy (jedna per linia):",
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(anchor="w", padx=10, pady=(4, 2))
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
            tk.Checkbutton(chk_frame, text=lbl, variable=var, font=FONT_UI,
                           bg=BG_PANEL, fg=FG_GRAY,
                           activebackground=BG_PANEL, selectcolor=BG_INPUT).pack(anchor="w")

        tk.Frame(left, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 4))
        btn_gen = tk.Frame(left, bg=BG_PANEL)
        btn_gen.pack(fill="x", padx=10, pady=(0, 8))
        tk.Button(btn_gen, text="⚡ Generuj plugin", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=12, pady=6,
                  cursor="hand2", activebackground="#3a7bc8",
                  command=self._plugin_generuj).pack(fill="x", pady=2)
        tk.Button(btn_gen, text="📥 Załaduj", font=FONT_UI,
                  bg="#2e5a2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#3a7a3a",
                  command=lambda: self._mod_zaladuj("plugin")).pack(side="left", pady=2, fill="x", expand=True, padx=(0, 2))
        tk.Button(btn_gen, text="🔌 Odłącz", font=FONT_UI,
                  bg="#5a2e2e", fg=FG_WHITE, relief="flat", padx=10, pady=4,
                  cursor="hand2", activebackground="#7a3a3a",
                  command=lambda: self._mod_odlacz("plugin")).pack(side="left", pady=2, fill="x", expand=True, padx=(2, 0))

        # ══════════════════
        # PRAWA: podgląd + akcje
        # ══════════════════
        right = tk.Frame(body, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER_CLR)
        right.pack(side="left", fill="both", expand=True)

        top_r = tk.Frame(right, bg=BG_PANEL, pady=6, padx=8)
        top_r.pack(fill="x")
        tk.Label(top_r, text="📄 Wygenerowany kod pluginu:",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(side="left")

        act_bar = tk.Frame(right, bg=BG_PANEL, padx=8)
        act_bar.pack(fill="x")
        tk.Button(act_bar, text="💾 Zapisz w bazie", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_zapisz_w_bazie).pack(side="left", padx=2, pady=4)
        tk.Button(act_bar, text="📁 Eksportuj .py", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_eksportuj).pack(side="left", padx=2, pady=4)
        tk.Button(act_bar, text="📋 Kopiuj kod", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_kopiuj).pack(side="left", padx=2, pady=4)
        tk.Button(act_bar, text="🗑 Wyczyść", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=self._plugin_wyczysc).pack(side="left", padx=2, pady=4)
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
        self.lbl_plugin_lines.config(text=f"Linii kodu: {n}")

    def _plugin_generuj(self):
        nazwa   = self.plugin_nazwa.get().strip()
        autor   = self.plugin_autor.get().strip() or "Nieznany"
        wersja  = self.plugin_wersja.get().strip() or "1.0.0"
        opis    = self.plugin_opis_e.get().strip() or "Plugin wygenerowany przez Baza Skryptów"
        typ     = self.var_plugin_typ.get()
        komendy_raw = self.plugin_komendy.get("1.0", "end-1c").strip().splitlines()
        komendy = [k.strip() for k in komendy_raw if k.strip()]

        if not nazwa:
            messagebox.showwarning("Brak nazwy", "Podaj nazwę pluginu!")
            return
        if not komendy:
            messagebox.showwarning("Brak komend", "Dodaj przynajmniej jedną komendę.")
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
            text=f"✔ Plugin '{nazwa}' wygenerowany — {len(komendy)} komend(y)",
            fg="#6dde84")

    def _plugin_zapisz_w_bazie(self):
        nazwa = self.plugin_nazwa.get().strip()
        if not nazwa:
            messagebox.showwarning("Brak nazwy", "Podaj nazwę pluginu przed zapisem.")
            return
        kod = self.plugin_text.get("1.0", "end-1c")
        if not kod.strip():
            messagebox.showwarning("Brak kodu", "Wygeneruj najpierw plugin.")
            return
        for i, s in enumerate(self.skrypty):
            if s["nazwa"] == nazwa:
                self.skrypty[i]["kod"] = kod
                self.skrypty[i]["checksum"] = kod_checksum(kod)
                self.skrypty[i]["zmieniony"] = now_str()
                self._after_db_change()
                messagebox.showinfo("Zapisano", f"Plugin '{nazwa}' zaktualizowany w bazie.")
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
        messagebox.showinfo("Zapisano", f"Plugin '{nazwa}' dodany do bazy — gotowy do pracy!")

    def _plugin_eksportuj(self):
        nazwa = self.plugin_nazwa.get().strip() or "plugin"
        kod   = self.plugin_text.get("1.0", "end-1c")
        if not kod.strip():
            messagebox.showwarning("Brak kodu", "Wygeneruj najpierw plugin.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            initialfile=nazwa,
            filetypes=[("Python", "*.py"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(kod)
            messagebox.showinfo("Eksport", f"Plugin zapisany jako plik:\n{path}")

    def _plugin_kopiuj(self):
        self.clipboard_clear()
        self.clipboard_append(self.plugin_text.get("1.0", "end-1c"))
        messagebox.showinfo("Skopiowano", "Kod pluginu skopiowany do schowka.")

    def _plugin_wyczysc(self):
        self.plugin_text.delete("1.0", "end")
        self._plugin_update_lines()
        self.lbl_plugin_status.config(text="Gotowy do generowania", fg="#6dde84")

    def _build_narzedzia_frame(self):
        outer = tk.Frame(self.main_tab_content, bg=BG_DARK)
        self.main_frames["narzedzia"] = outer

        hdr = tk.Frame(outer, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔧 Narzędzia",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Label(hdr, text="Sebastian Januchowski · polsoft.ITS™ Group",
                 font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="right", padx=8)
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
        tk.Label(p1, text="📂 Operacje na plikach", font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w", padx=10, pady=(8, 4))
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
            tk.Button(p1, text=txt, font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2", anchor="w",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(fill="x", padx=8, pady=2)

        # Panel 2: Diagnostyka i Naprawa
        p2 = tk.Frame(top_paned, bg=BG_PANEL,
                      highlightthickness=1, highlightbackground=BORDER_CLR)
        top_paned.add(p2, stretch="always")
        tk.Label(p2, text="🔬 Diagnostyka i Naprawa", font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p2, bg=BORDER_CLR, height=1).pack(fill="x")
        for txt, cmd in [
            ("▶ Uruchom diagnostykę",  self._run_diag),
            ("🔧 Naprawa błędów",       self._naprawa_scan),
            ("📊 Statystyki bazy",      self._menu_statystyki),
            ("🔄 Odśwież widoki",       self._menu_odswiez),
            ("🗑 Wyczyść całą bazę…",   self._menu_wyczysc_baze),
        ]:
            tk.Button(p2, text=txt, font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2", anchor="w",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(fill="x", padx=8, pady=2)

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
        tk.Label(p3, text="🔌 Kreator i Moduły", font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p3, bg=BORDER_CLR, height=1).pack(fill="x")
        for txt, cmd in [
            ("🔌 Kreator Pluginów",      self._menu_pokaz_plugin),
            ("🔗 Łączenie modułów",      self._menu_pokaz_laczen),
            ("⚡ Testy osiągów",         self._run_testy),
            ("📋 Info o modułach",       lambda: self._menu_pokaz_mod("info")),
            ("🔄 Odśwież info modułów",  self._mod_refresh_info),
        ]:
            tk.Button(p3, text=txt, font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=5, cursor="hand2", anchor="w",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(fill="x", padx=8, pady=2)

        # Panel 4: Informacje o autorze
        p4 = tk.Frame(bot_paned, bg=BG_PANEL,
                      highlightthickness=1, highlightbackground=BORDER_CLR)
        bot_paned.add(p4, stretch="always")
        tk.Label(p4, text="👤 Informacje o autorze", font=FONT_BOLD,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w", padx=10, pady=(8, 4))
        tk.Frame(p4, bg=BORDER_CLR, height=1).pack(fill="x")
        author_info = [
            ("Autor",   "Sebastian Januchowski"),
            ("Firma",   "polsoft.ITS™ Group"),
            ("Web",     "www.polsoft.gt.tc"),
            ("GitHub",  "https://github.com/seb07uk"),
            ("E-mail",  "polsoft.its@fastservice.com"),
            ("Wersja",  "3.0"),
            ("Platforma", "Python 3 / Tkinter"),
        ]
        for label, value in author_info:
            row = tk.Frame(p4, bg=BG_PANEL)
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=f"{label}:", font=FONT_BOLD, bg=BG_PANEL,
                     fg=FG_GRAY, width=10, anchor="w").pack(side="left")
            tk.Label(row, text=value, font=FONT_UI, bg=BG_PANEL,
                     fg=FG_WHITE, anchor="w").pack(side="left", padx=4)

        tk.Frame(p4, bg=BORDER_CLR, height=1).pack(fill="x", pady=(8, 4))
        tk.Button(p4, text="ℹ O programie", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=5, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._menu_o_programie).pack(fill="x", padx=8, pady=2)

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
        tk.Label(hdr, text="🐍 VirtualEnv — Zarządzanie środowiskami Python",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self.venv_lbl_status = tk.Label(hdr, text="Gotowy", font=FONT_UI,
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

        venv_tabs = [
            ("📋 Lista envów",    "lista"),
            ("➕ Utwórz env",    "create"),
            ("📦 Pakiety",        "pakiety"),
            ("📄 Requirements",   "req"),
            ("⚙ Ustawienia",     "settings"),
            ("📟 Log / Terminal", "log"),
        ]
        for j, (lbl, key) in enumerate(venv_tabs):
            b = tk.Button(venv_sub_bar, text=lbl, font=FONT_UI,
                          bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY,
                          relief="flat", padx=14, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda j=j, k=key: sel_venv(j, k))
            b.pack(side="left")
            self._venv_btns.append(b)

        # store selector for later use
        self._venv_sel = sel_venv

        # Stan zarządzania envami
        self._venv_dir   = tk.StringVar(value=os.path.expanduser("~/.virtualenvs"))
        self._venv_list  = []  # [{name, path, python, active}]
        self._venv_active = None  # aktualnie wybrany env

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

    def _venv_run(self, cmd, success_msg="OK", error_prefix="Błąd"):
        """Uruchom polecenie subprocess, zaloguj wynik."""
        import subprocess
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
                self._venv_log(f"{error_prefix}: kod {result.returncode}", "error")
                self._venv_set_status(f"{error_prefix}!", "#e07070")
                return False
        except FileNotFoundError:
            self._venv_log(f"Nie znaleziono polecenia: {cmd[0]}", "error")
            self._venv_set_status("Błąd — brak polecenia", "#e07070")
            return False
        except subprocess.TimeoutExpired:
            self._venv_log("Przekroczono limit czasu (120s)", "error")
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
        self._venv_log(f"Znaleziono {len(self._venv_list)} środowisk w: {base}", "info")

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
        self._venv_set_status(f"Wybrano: {env['name']}")
        self._venv_fill_info(env)

    def _venv_fill_info(self, env):
        """Wypełnij panel informacyjny po wyborze enva."""
        import subprocess, sys
        if not hasattr(self, "venv_info_text"):
            return
        py = self._venv_python_in_env(env["path"])
        lines = [
            f"  Nazwa:   {env['name']}",
            f"  Ścieżka: {env['path']}",
            f"  Python:  {py}",
        ]
        # wersja pythona
        try:
            r = subprocess.run([py, "--version"], capture_output=True, text=True, timeout=5)
            ver = (r.stdout or r.stderr).strip()
            lines.append(f"  Wersja:  {ver}")
        except Exception:
            lines.append("  Wersja:  (nie można sprawdzić)")
        # rozmiar
        try:
            total = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, dn, fn in os.walk(env["path"]) for f in fn
            )
            lines.append(f"  Rozmiar: {total / 1024 / 1024:.1f} MB")
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
            tk.Button(bar, text=text, font=FONT_UI, bg=color, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(side="left", padx=3)

        btn("🔄 Odśwież",        self._venv_refresh_list)
        btn("➕ Utwórz nowy",    lambda: self._venv_sel(1, "create"), ACCENT_BLUE)
        btn("🗑 Usuń env",       self._venv_delete)
        btn("📋 Kopiuj ścieżkę", self._venv_copy_path)
        btn("📂 Otwórz folder",  self._venv_open_folder)

        tk.Frame(bar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=8, pady=3)
        tk.Label(bar, text="Katalog envów:", font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
        venv_dir_e = tk.Entry(bar, textvariable=self._venv_dir, font=FONT_MONO,
                              bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE,
                              relief="flat", highlightthickness=1,
                              highlightbackground=BORDER_CLR, highlightcolor=ACCENT_BLUE,
                              width=32)
        venv_dir_e.pack(side="left", padx=4)
        tk.Button(bar, text="📁", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._venv_browse_dir).pack(side="left")

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # split: lista po lewej, info po prawej
        body = tk.PanedWindow(frame, orient="horizontal", bg=BG_DARK,
                              sashwidth=6, sashrelief="flat", opaqueresize=True)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # lista
        left = tk.Frame(body, bg=BG_PANEL,
                        highlightthickness=1, highlightbackground=BORDER_CLR)
        body.add(left, width=260)

        tk.Label(left, text="🐍 Środowiska wirtualne", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 4))
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

        tk.Label(right, text="ℹ Informacje o środowisku", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_WHITE).pack(anchor="w", padx=10, pady=(8, 4))
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
            tk.Button(act_bar, text=text, font=FONT_UI, bg=color, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER,
                      command=cmd).pack(side="left", padx=3)

        abtn("📦 Pokaż pakiety",     self._venv_show_packages)
        abtn("⬆ Aktualizuj pip",    self._venv_upgrade_pip, "#2e5a2e")
        abtn("🗑 Usuń env",          self._venv_delete, "#603030")

    def _venv_browse_dir(self):
        d = filedialog.askdirectory(title="Wybierz katalog środowisk")
        if d:
            self._venv_dir.set(d)
            self._venv_refresh_list()

    def _venv_delete(self):
        import shutil
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak wyboru", "Wybierz środowisko z listy.")
            return
        if messagebox.askyesno("Usuń env",
                               f"Usunąć środowisko '{env['name']}'?\n{env['path']}\n\nTej operacji nie można cofnąć!"):
            try:
                shutil.rmtree(env["path"])
                self._venv_log(f"Usunięto: {env['name']}", "ok")
                self._venv_set_status(f"Usunięto: {env['name']}")
                self._venv_refresh_list()
            except Exception as e:
                self._venv_log(f"Błąd usuwania: {e}", "error")
                messagebox.showerror("Błąd", str(e))

    def _venv_copy_path(self):
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak wyboru", "Wybierz środowisko z listy.")
            return
        self.clipboard_clear()
        self.clipboard_append(env["path"])
        messagebox.showinfo("Skopiowano", f"Ścieżka skopiowana:\n{env['path']}")

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
            messagebox.showerror("Błąd", str(e))

    def _venv_show_packages(self):
        """Przełącz na zakładkę Pakiety i załaduj listę."""
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak wyboru", "Wybierz środowisko z listy.")
            return
        self._venv_active = env
        self._venv_sel(2, "pakiety")
        self._venv_load_packages()

    def _venv_upgrade_pip(self):
        env = self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak wyboru", "Wybierz środowisko z listy.")
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(f"Aktualizuję pip w: {env['name']}", "info")
        self.after(50, lambda: self._venv_run(
            [pip, "install", "--upgrade", "pip"],
            success_msg="pip zaktualizowany!"))

    # ── POD-ZAKŁADKA 2: Utwórz env ───────────────────────────────────────────
    def _build_venv_create(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["create"] = frame

        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="➕ Utwórz nowe środowisko wirtualne",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        def row(label, widget_factory):
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=5)
            tk.Label(r, text=label, font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=22, anchor="w").pack(side="left")
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
        tk.Label(dir_row, text="Katalog docelowy:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self.venv_new_dir = tk.Entry(dir_row, textvariable=self._venv_dir,
                                     font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                     insertbackground=FG_WHITE, relief="flat",
                                     highlightthickness=1, highlightbackground=BORDER_CLR,
                                     highlightcolor=ACCENT_BLUE)
        self.venv_new_dir.pack(side="left", fill="x", expand=True)
        tk.Button(dir_row, text="📁", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._venv_browse_dir).pack(side="left", padx=4)

        # Interpreter Pythona
        import sys
        py_row = tk.Frame(body, bg=BG_DARK)
        py_row.pack(fill="x", pady=5)
        tk.Label(py_row, text="Interpreter Python:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self.venv_new_python = tk.Entry(py_row, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                        insertbackground=FG_WHITE, relief="flat",
                                        highlightthickness=1, highlightbackground=BORDER_CLR,
                                        highlightcolor=ACCENT_BLUE)
        self.venv_new_python.insert(0, sys.executable)
        self.venv_new_python.pack(side="left", fill="x", expand=True)
        tk.Button(py_row, text="📁", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._venv_browse_python).pack(side="left", padx=4)

        # Opcje
        opts = tk.Frame(body, bg=BG_DARK)
        opts.pack(fill="x", pady=8)
        tk.Label(opts, text="Opcje:", font=FONT_BOLD, bg=BG_DARK,
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
            tk.Checkbutton(opts, text=text, variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT).pack(side="left", padx=10)

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=12)

        btn_row = tk.Frame(body, bg=BG_DARK)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="✅ Utwórz środowisko", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat",
                  padx=18, pady=8, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._venv_create).pack(side="left", padx=4)
        tk.Button(btn_row, text="🧹 Wyczyść formularz", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=lambda: (self.venv_new_name.delete(0, "end"),
                                   self.venv_create_progress.config(text=""))).pack(side="left", padx=4)

        self.venv_create_progress = tk.Label(body, text="", font=FONT_UI,
                                              bg=BG_DARK, fg="#6dde84")
        self.venv_create_progress.pack(anchor="w", pady=8)

    def _venv_browse_python(self):
        path = filedialog.askopenfilename(
            title="Wybierz interpreter Python",
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
            messagebox.showwarning("Brak nazwy", "Podaj nazwę środowiska.")
            return
        if not base:
            messagebox.showwarning("Brak katalogu", "Podaj katalog docelowy.")
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

        self.venv_create_progress.config(text=f"⏳ Tworzenie '{name}'…", fg="#f0c050")
        self._venv_sel(5, "log")
        self._venv_log(f"Tworzenie środowiska: {name}", "info")
        self._venv_log(f"Ścieżka: {env_path}", "info")

        def do_create():
            ok = self._venv_run(cmd, success_msg=f"Środowisko '{name}' utworzone!")
            if ok:
                self.venv_create_progress.config(text=f"✅ Środowisko '{name}' gotowe!", fg="#6dde84")
                self._venv_refresh_list()
                self._venv_sel(0, "lista")
            else:
                self.venv_create_progress.config(text=f"❌ Błąd tworzenia '{name}'", fg="#e07070")

        self.after(50, do_create)

    # ── POD-ZAKŁADKA 3: Pakiety ──────────────────────────────────────────────
    def _build_venv_pakiety(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["pakiety"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")

        self.venv_pkg_env_label = tk.Label(bar, text="— brak wybranego env —",
                                            font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE)
        self.venv_pkg_env_label.pack(side="left", padx=4)

        tk.Button(bar, text="🔄 Odśwież listę", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_load_packages).pack(side="right", padx=3)

        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Install bar
        inst_bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        inst_bar.pack(fill="x")
        tk.Label(inst_bar, text="Zainstaluj pakiet:", font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
        self.venv_pkg_install_e = tk.Entry(inst_bar, font=FONT_MONO, bg=BG_INPUT,
                                            fg=FG_WHITE, insertbackground=FG_WHITE,
                                            relief="flat", highlightthickness=1,
                                            highlightbackground=BORDER_CLR,
                                            highlightcolor=ACCENT_BLUE, width=30)
        self.venv_pkg_install_e.pack(side="left", padx=6)
        self.venv_pkg_install_e.bind("<Return>", lambda e: self._venv_install_pkg())
        tk.Button(inst_bar, text="⬇ Instaluj", font=FONT_UI, bg="#2e5a2e", fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#3a7a3a",
                  command=self._venv_install_pkg).pack(side="left", padx=3)
        tk.Button(inst_bar, text="⬆ Aktualizuj pip", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_upgrade_pip).pack(side="left", padx=3)
        tk.Button(inst_bar, text="🗑 Odinstaluj", font=FONT_UI, bg="#603030", fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#804040",
                  command=self._venv_uninstall_pkg).pack(side="right", padx=3)

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
            self.venv_pkg_tree.heading(col, text=col)
            self.venv_pkg_tree.column(col, width=w, minwidth=80)
        self.venv_pkg_tree.pack(fill="both", expand=True)
        self.venv_pkg_tree.tag_configure("odd",  background=BG_ROW_ODD)
        self.venv_pkg_tree.tag_configure("even", background=BG_ROW_EVEN)

        self.venv_pkg_count = tk.Label(frame, text="Pakietów: 0",
                                        font=FONT_UI, bg=BG_DARK, fg=FG_GRAY)
        self.venv_pkg_count.pack(anchor="w", padx=10, pady=2)

    def _venv_load_packages(self):
        import subprocess, json
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak env", "Najpierw wybierz środowisko z Listy envów.")
            return
        pip = self._venv_pip_in_env(env["path"])
        self.venv_pkg_env_label.config(text=f"🐍 {env['name']}")
        self._venv_log(f"Ładowanie pakietów z: {env['name']}", "info")
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
            self.venv_pkg_count.config(text=f"Pakietów: {len(pkgs)}")
            self._venv_log(f"Załadowano {len(pkgs)} pakietów.", "ok")
        except Exception as e:
            self._venv_log(f"Błąd ładowania pakietów: {e}", "error")

    def _venv_install_pkg(self):
        pkg = self.venv_pkg_install_e.get().strip()
        env = self._venv_active or self._venv_get_selected()
        if not pkg:
            messagebox.showwarning("Brak pakietu", "Wpisz nazwę pakietu.")
            return
        if not env:
            messagebox.showinfo("Brak env", "Wybierz środowisko z Listy envów.")
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(f"Instaluję: {pkg} w {env['name']}", "info")
        self.after(50, lambda: (
            self._venv_run([pip, "install", pkg],
                           success_msg=f"Zainstalowano: {pkg}"),
            self._venv_load_packages()
        ))

    def _venv_uninstall_pkg(self):
        sel = self.venv_pkg_tree.selection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Zaznacz pakiet z listy.")
            return
        pkg = self.venv_pkg_tree.item(sel[0])["values"][0]
        env = self._venv_active or self._venv_get_selected()
        if not env:
            return
        if not messagebox.askyesno("Odinstaluj", f"Odinstalować '{pkg}' z '{env['name']}'?"):
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(f"Odinstaluję: {pkg}", "info")
        self.after(50, lambda: (
            self._venv_run([pip, "uninstall", "-y", pkg],
                           success_msg=f"Odinstalowano: {pkg}"),
            self._venv_load_packages()
        ))

    # ── POD-ZAKŁADKA 4: Requirements ─────────────────────────────────────────
    def _build_venv_req(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["req"] = frame

        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📄 Requirements.txt — eksport i import zależności",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        tk.Button(bar, text="📤 Generuj requirements.txt",
                  font=FONT_UI, bg=ACCENT_BLUE, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._venv_generate_req).pack(side="left", padx=3)
        tk.Button(bar, text="💾 Zapisz do pliku…",
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_save_req).pack(side="left", padx=3)
        tk.Button(bar, text="📥 Instaluj z pliku…",
                  font=FONT_UI, bg="#2e5a2e", fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#3a7a3a",
                  command=self._venv_install_req).pack(side="left", padx=3)
        tk.Button(bar, text="📋 Kopiuj",
                  font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
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
            messagebox.showinfo("Brak env", "Wybierz środowisko z Listy envów.")
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_log(f"Generuję requirements dla: {env['name']}", "info")
        try:
            result = subprocess.run([pip, "freeze"], capture_output=True, text=True, timeout=30)
            self.venv_req_text.delete("1.0", "end")
            self.venv_req_text.insert("1.0", result.stdout)
            self._venv_log("requirements.txt wygenerowany.", "ok")
        except Exception as e:
            self._venv_log(f"Błąd: {e}", "error")

    def _venv_save_req(self):
        content = self.venv_req_text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showwarning("Brak zawartości", "Najpierw wygeneruj requirements.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="requirements.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self._venv_log(f"Zapisano: {path}", "ok")
            messagebox.showinfo("Zapisano", f"Plik zapisany:\n{path}")

    def _venv_install_req(self):
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak env", "Wybierz środowisko z Listy envów.")
            return
        path = filedialog.askopenfilename(
            title="Wybierz requirements.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if not path:
            return
        pip = self._venv_pip_in_env(env["path"])
        self._venv_sel(5, "log")
        self._venv_log(f"Instaluję z: {path}", "info")
        self.after(50, lambda: self._venv_run(
            [pip, "install", "-r", path],
            success_msg="Pakiety zainstalowane z requirements.txt!"))

    def _venv_copy_req(self):
        content = self.venv_req_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Skopiowano", "requirements.txt skopiowany do schowka.")

    # ── POD-ZAKŁADKA 5: Ustawienia ───────────────────────────────────────────
    def _build_venv_settings(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["settings"] = frame

        hdr = tk.Frame(frame, bg=BG_PANEL, pady=8, padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙ Ustawienia VirtualEnv",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        def section(title):
            tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=(14, 4))
            tk.Label(body, text=title, font=FONT_BOLD, bg=BG_DARK,
                     fg=ACCENT_BLUE).pack(anchor="w")

        section("📁 Domyślny katalog środowisk")
        dr = tk.Frame(body, bg=BG_DARK)
        dr.pack(fill="x", pady=4)
        tk.Entry(dr, textvariable=self._venv_dir, font=FONT_MONO, bg=BG_INPUT,
                 fg=FG_WHITE, insertbackground=FG_WHITE, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER_CLR,
                 highlightcolor=ACCENT_BLUE).pack(side="left", fill="x", expand=True)
        tk.Button(dr, text="📁 Przeglądaj", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._venv_browse_dir).pack(side="left", padx=6)

        section("🐍 Narzędzia")
        import sys, shutil
        for tool in ["venv", "virtualenv", "pipenv", "poetry", "conda"]:
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=2)
            found = shutil.which(tool) or (tool == "venv" and "built-in")
            color = "#6dde84" if found else "#e07070"
            icon  = "✔" if found else "✘"
            tk.Label(r, text=f"{icon} {tool}", font=FONT_BOLD, bg=BG_DARK,
                     fg=color, width=16, anchor="w").pack(side="left")
            tk.Label(r, text=str(found) if found else "nie znaleziono",
                     font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left", padx=8)

        section("ℹ Środowisko Python (bieżące)")
        import platform
        for label, val in [
            ("Python:", sys.version.split()[0]),
            ("Plik:",   sys.executable),
            ("Platforma:", f"{platform.system()} {platform.release()}"),
        ]:
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=14, anchor="w").pack(side="left")
            tk.Label(r, text=val, font=FONT_UI, bg=BG_DARK,
                     fg=FG_WHITE).pack(side="left", padx=4)

    # ── POD-ZAKŁADKA 6: Log / Terminal ───────────────────────────────────────
    def _build_venv_log(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._venv_frames["log"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=8)
        bar.pack(fill="x")
        tk.Label(bar, text="📟 Log operacji / output komend",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        tk.Button(bar, text="🧹 Wyczyść", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=lambda: (self.venv_log_text.config(state="normal"),
                                   self.venv_log_text.delete("1.0", "end"),
                                   self.venv_log_text.config(state="disabled"))
                  ).pack(side="right", padx=3)
        tk.Button(bar, text="💾 Zapisz log…", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._venv_save_log).pack(side="right", padx=3)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Wbudowany mini-terminal (pip polecenia)
        cmd_bar = tk.Frame(frame, bg=BG_PANEL, pady=5, padx=8)
        cmd_bar.pack(fill="x")
        tk.Label(cmd_bar, text="pip:", font=FONT_BOLD, bg=BG_PANEL,
                 fg=FG_GRAY).pack(side="left")
        self.venv_cmd_entry = tk.Entry(cmd_bar, font=FONT_MONO, bg=BG_INPUT,
                                        fg=FG_WHITE, insertbackground=FG_WHITE,
                                        relief="flat", highlightthickness=1,
                                        highlightbackground=BORDER_CLR,
                                        highlightcolor=ACCENT_BLUE)
        self.venv_cmd_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.venv_cmd_entry.bind("<Return>", lambda e: self._venv_run_pip_cmd())
        tk.Button(cmd_bar, text="▶ Uruchom", font=FONT_UI, bg=ACCENT_BLUE, fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._venv_run_pip_cmd).pack(side="left", padx=3)
        tk.Label(cmd_bar, text="(np. install numpy  |  list  |  show requests)",
                 font=("Consolas", 8), bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=8)
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

        self._venv_log("VirtualEnv Manager gotowy.", "ok")

    def _venv_run_pip_cmd(self):
        cmd_str = self.venv_cmd_entry.get().strip()
        if not cmd_str:
            return
        env = self._venv_active or self._venv_get_selected()
        if not env:
            messagebox.showinfo("Brak env", "Wybierz środowisko z Listy envów.")
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
            messagebox.showinfo("Zapisano", f"Log zapisany:\n{path}")

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
        tk.Label(hdr, text="💾 VDrive — Wirtualne nośniki danych",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self._vdrive_status_lbl = tk.Label(hdr, text="Gotowy", font=FONT_UI,
                                            bg=BG_PANEL, fg="#6dde84")
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

        self._vdrive_sel = sel_vd

        vd_tabs = [
            ("🖥 Panel nośników",  "panel"),
            ("➕ Utwórz nośnik",   "create"),
            ("⚙ Ustawienia",      "settings"),
            ("📋 Log",             "log"),
        ]
        for j, (lbl, key) in enumerate(vd_tabs):
            b = tk.Button(vd_sub_bar, text=lbl, font=FONT_UI,
                          bg=BG_SUBTAB_ACT if j == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if j == 0 else FG_GRAY,
                          relief="flat", padx=14, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda j=j, k=key: sel_vd(j, k))
            b.pack(side="left")
            self._vdrive_btns.append(b)

        # stan nośników: lista słowników
        self._vdrives = []  # [{id, typ, label, path, size_mb, mounted, drive_letter}]

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
        if hasattr(self, "_vdrive_status_lbl"):
            self._vdrive_status_lbl.config(text=msg, fg=color)

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
            ("🔄 Odśwież",        self._vdrive_refresh_panel),
            ("➕ Dodaj nośnik",   lambda: self._vdrive_sel(1, "create")),
            ("⏏ Odmontuj",        self._vdrive_unmount_selected),
            ("🗑 Usuń nośnik",    self._vdrive_delete_selected),
        ]:
            tk.Button(toolbar, text=txt, font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      activebackground=BTN_HOVER,
                      command=cmd).pack(side="left", padx=3)
        tk.Frame(toolbar, bg=BORDER_CLR, width=1).pack(side="left", fill="y", padx=8, pady=2)
        tk.Button(toolbar, text="▶ Montuj",  font=FONT_BOLD, bg=ACCENT_BLUE, fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._vdrive_mount_selected).pack(side="left", padx=3)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Legenda typów
        leg = tk.Frame(frame, bg=BG_PANEL, pady=4, padx=10)
        leg.pack(fill="x")
        tk.Label(leg, text="Typy nośników:", font=FONT_BOLD,
                 bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=(0, 10))
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
            tk.Label(fr, text=label, font=("Consolas", 8),
                     bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=2)
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        # Siatka nośników (canvas z ikonami + Treeview)
        split = tk.PanedWindow(frame, orient="horizontal", bg=BG_DARK,
                               sashwidth=6, sashrelief="flat")
        split.pack(fill="both", expand=True)

        # Lewa: ikony nośników (Canvas scrollable)
        left_wrap = tk.Frame(split, bg=BG_DARK, width=260)
        split.add(left_wrap, stretch="never")
        tk.Label(left_wrap, text="Nośniki", font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE).pack(anchor="w", padx=8, pady=(6, 2))
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
        tk.Label(right_wrap, text="Szczegóły nośników", font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_WHITE).pack(anchor="w", padx=8, pady=(6, 2))
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
            self._vdrive_tree.heading(col, text=col)
            self._vdrive_tree.column(col, width=widths.get(col, 100),
                                      minwidth=40, anchor="w")
        self._vdrive_tree.tag_configure("mounted",
                                         foreground="#6dde84")
        self._vdrive_tree.tag_configure("unmounted",
                                         foreground=FG_GRAY)
        self._vdrive_tree.bind("<<TreeviewSelect>>",
                               self._vdrive_on_tree_select)
        self._vdrive_tree.bind("<Double-1>",
                               lambda e: self._vdrive_mount_selected())

        # Dolny pasek informacyjny
        info_bar = tk.Frame(right_wrap, bg=BG_PANEL, pady=4, padx=8)
        info_bar.pack(fill="x", side="bottom")
        self._vdrive_info_lbl = tk.Label(info_bar, text="Wybierz nośnik aby zobaczyć szczegóły",
                                          font=FONT_UI, bg=BG_PANEL, fg=FG_GRAY,
                                          anchor="w")
        self._vdrive_info_lbl.pack(fill="x")

        # Wypełnij przykładowymi nośnikami na start
        self.after(150, self._vdrive_refresh_panel)

    # ── POD-ZAKŁADKA 2: Utwórz nośnik ────────────────────────────────────────
    def _build_vdrive_create(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["create"] = frame

        hdr2 = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        hdr2.pack(fill="x")
        tk.Label(hdr2, text="➕ Utwórz / Zarejestruj nowy nośnik",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        def row_label(text):
            tk.Label(body, text=text, font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=22, anchor="w").pack(side="left")

        def field_row(label, widget_factory):
            r = tk.Frame(body, bg=BG_DARK)
            r.pack(fill="x", pady=5)
            tk.Label(r, text=label, font=FONT_BOLD, bg=BG_DARK,
                     fg=FG_GRAY, width=22, anchor="w").pack(side="left")
            return r, widget_factory(r)

        # Typ nośnika
        r = tk.Frame(body, bg=BG_DARK)
        r.pack(fill="x", pady=5)
        tk.Label(r, text="Typ nośnika:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
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
        self._vdrive_type_var = tk.StringVar(value="VHD")
        type_frame = tk.Frame(r, bg=BG_DARK)
        type_frame.pack(side="left", fill="x", expand=True)
        self._vdrive_type_combo = ttk.Combobox(
            type_frame, textvariable=self._vdrive_type_var,
            values=[t[0] for t in DRIVE_TYPES],
            state="readonly", font=FONT_MONO, width=34)
        self._vdrive_type_combo.pack(side="left")
        self._vdrive_type_combo.set(DRIVE_TYPES[2][0])
        self._DRIVE_TYPES_MAP = {t[0]: t[1] for t in DRIVE_TYPES}
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
        self._vdrive_new_label.insert(0, "MójNosnik")

        # Plik / ścieżka
        r3 = tk.Frame(body, bg=BG_DARK)
        r3.pack(fill="x", pady=5)
        tk.Label(r3, text="Plik / ścieżka:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self._vdrive_new_path = tk.Entry(r3, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                          insertbackground=FG_WHITE, relief="flat",
                                          highlightthickness=1, highlightbackground=BORDER_CLR,
                                          highlightcolor=ACCENT_BLUE)
        self._vdrive_new_path.pack(side="left", fill="x", expand=True)
        tk.Button(r3, text="📁", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._vdrive_browse_path).pack(side="left", padx=4)

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
        tk.Label(r5, text="Litera dysku (Win):", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self._vdrive_new_letter = ttk.Combobox(
            r5, values=["(auto)"] + [f"{c}:" for c in "DEFGHIJKLMNOPQRSTUVWXYZ"],
            font=FONT_MONO, state="readonly", width=8)
        self._vdrive_new_letter.set("(auto)")
        self._vdrive_new_letter.pack(side="left")

        # System plików
        r6 = tk.Frame(body, bg=BG_DARK)
        r6.pack(fill="x", pady=5)
        tk.Label(r6, text="System plików:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self._vdrive_new_fs = ttk.Combobox(
            r6, values=["NTFS", "FAT32", "exFAT", "ext4", "ISO 9660", "(brak)"],
            font=FONT_MONO, state="readonly", width=14)
        self._vdrive_new_fs.set("NTFS")
        self._vdrive_new_fs.pack(side="left")

        # Opcje
        r7 = tk.Frame(body, bg=BG_DARK)
        r7.pack(fill="x", pady=8)
        tk.Label(r7, text="Opcje:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=22, anchor="w").pack(side="left")
        self._vdrive_opt_automount  = tk.BooleanVar(value=True)
        self._vdrive_opt_persistent = tk.BooleanVar(value=True)
        self._vdrive_opt_readonly   = tk.BooleanVar(value=False)
        self._vdrive_opt_compress   = tk.BooleanVar(value=False)
        for text, var in [
            ("Auto-montuj",        self._vdrive_opt_automount),
            ("Trwały (persistent)",self._vdrive_opt_persistent),
            ("Tylko do odczytu",   self._vdrive_opt_readonly),
            ("Kompresja",          self._vdrive_opt_compress),
        ]:
            tk.Checkbutton(r7, text=text, variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT).pack(side="left", padx=10)

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=12)

        # Przyciski akcji
        btn_row = tk.Frame(body, bg=BG_DARK)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="✅ Utwórz i zamontuj", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat",
                  padx=18, pady=8, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=self._vdrive_do_create).pack(side="left", padx=4)
        tk.Button(btn_row, text="📂 Tylko zarejestruj", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._vdrive_do_register).pack(side="left", padx=4)
        tk.Button(btn_row, text="🧹 Wyczyść", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._vdrive_clear_create_form).pack(side="left", padx=4)

        self._vdrive_create_status = tk.Label(body, text="", font=FONT_UI,
                                               bg=BG_DARK, fg="#6dde84")
        self._vdrive_create_status.pack(anchor="w", pady=8)

        # Info o narzędziach systemowych
        info_wrap = tk.Frame(body, bg=BG_PANEL, padx=12, pady=8)
        info_wrap.pack(fill="x", pady=(8, 0))
        tk.Label(info_wrap, text="ℹ Informacje o obsłudze nośników",
                 font=FONT_BOLD, bg=BG_PANEL, fg=ACCENT_BLUE).pack(anchor="w")
        info_lines = [
            "• VHD/VHDX  — Windows: diskpart / PowerShell New-VHD; Linux: qemu-img",
            "• ISO/CD/DVD — Windows: PowerShell Mount-DiskImage; Linux: mount -o loop",
            "• Blu-ray    — Windows: MakeMKV / ImgBurn; Linux: cdrecord / k3b",
            "• IMG/BIN    — Windows: OSFMount, ImDisk; Linux: mount -o loop",
            "• RAM Drive  — Windows: ImDisk / OSFMount; Linux: mount -t tmpfs",
            "• FDD (obraz)— Windows: WinImage; Linux: mount -t msdos / dosfsck",
        ]
        for line in info_lines:
            tk.Label(info_wrap, text=line, font=("Consolas", 8),
                     bg=BG_PANEL, fg=FG_GRAY, anchor="w").pack(fill="x")

    # ── POD-ZAKŁADKA 3: Ustawienia ────────────────────────────────────────────
    def _build_vdrive_settings(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["settings"] = frame

        hdr3 = tk.Frame(frame, bg=BG_PANEL, pady=6, padx=10)
        hdr3.pack(fill="x")
        tk.Label(hdr3, text="⚙ Ustawienia VDrive",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(side="left")
        tk.Frame(frame, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(frame, bg=BG_DARK, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        # Domyślny katalog
        r = tk.Frame(body, bg=BG_DARK)
        r.pack(fill="x", pady=5)
        tk.Label(r, text="Katalog obrazów:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w").pack(side="left")
        self._vdrive_images_dir = tk.Entry(r, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                            insertbackground=FG_WHITE, relief="flat",
                                            highlightthickness=1, highlightbackground=BORDER_CLR,
                                            highlightcolor=ACCENT_BLUE)
        self._vdrive_images_dir.insert(0, os.path.expanduser("~/VDriveImages"))
        self._vdrive_images_dir.pack(side="left", fill="x", expand=True)
        tk.Button(r, text="📁", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=lambda: (
                      self._vdrive_images_dir.delete(0, "end"),
                      self._vdrive_images_dir.insert(0,
                          filedialog.askdirectory() or
                          self._vdrive_images_dir.get())
                  )).pack(side="left", padx=4)

        # Narzędzie montowania (Windows/Linux)
        r2 = tk.Frame(body, bg=BG_DARK)
        r2.pack(fill="x", pady=5)
        tk.Label(r2, text="Narzędzie (Windows):", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w").pack(side="left")
        self._vdrive_tool_win = ttk.Combobox(
            r2, values=["diskpart (wbudowany)", "PowerShell Mount-DiskImage",
                        "ImDisk Toolkit", "OSFMount", "Arsenal Image Mounter"],
            font=FONT_MONO, state="readonly", width=34)
        self._vdrive_tool_win.set("PowerShell Mount-DiskImage")
        self._vdrive_tool_win.pack(side="left")

        r3 = tk.Frame(body, bg=BG_DARK)
        r3.pack(fill="x", pady=5)
        tk.Label(r3, text="Narzędzie (Linux):", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w").pack(side="left")
        self._vdrive_tool_lin = ttk.Combobox(
            r3, values=["mount (wbudowany)", "qemu-img + mount", "fuseiso",
                        "acetoneiso2", "gnome-disk-image-mounter"],
            font=FONT_MONO, state="readonly", width=34)
        self._vdrive_tool_lin.set("mount (wbudowany)")
        self._vdrive_tool_lin.pack(side="left")

        # Opcje globalne
        r4 = tk.Frame(body, bg=BG_DARK)
        r4.pack(fill="x", pady=10)
        tk.Label(r4, text="Opcje globalne:", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_GRAY, width=24, anchor="w").pack(side="left")
        self._vdrive_global_automount  = tk.BooleanVar(value=True)
        self._vdrive_global_notify     = tk.BooleanVar(value=True)
        self._vdrive_global_autostart  = tk.BooleanVar(value=False)
        for text, var in [
            ("Auto-montuj przy starcie", self._vdrive_global_automount),
            ("Powiadomienia",            self._vdrive_global_notify),
            ("Uruchom przy logowaniu",   self._vdrive_global_autostart),
        ]:
            tk.Checkbutton(r4, text=text, variable=var, font=FONT_UI,
                           bg=BG_DARK, fg=FG_WHITE, activebackground=BG_DARK,
                           selectcolor=BG_INPUT).pack(side="left", padx=10)

        tk.Frame(body, bg=BORDER_CLR, height=1).pack(fill="x", pady=12)

        tk.Button(body, text="💾 Zapisz ustawienia", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  activebackground="#3a7bc8",
                  command=lambda: messagebox.showinfo(
                      "Ustawienia", "Ustawienia VDrive zapisane.")).pack(anchor="w")

    # ── POD-ZAKŁADKA 4: Log ───────────────────────────────────────────────────
    def _build_vdrive_log(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._vdrive_frames["log"] = frame

        bar = tk.Frame(frame, bg=BG_PANEL, pady=5, padx=8)
        bar.pack(fill="x")
        tk.Label(bar, text="📋 Log operacji VDrive",
                 font=FONT_BOLD, bg=BG_PANEL, fg=FG_WHITE).pack(side="left")
        tk.Button(bar, text="🗑 Wyczyść log", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=lambda: (
                      self._vdrive_log_text.config(state="normal"),
                      self._vdrive_log_text.delete("1.0", "end"),
                      self._vdrive_log_text.config(state="disabled")
                  )).pack(side="right", padx=4)
        tk.Button(bar, text="💾 Zapisz log", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  activebackground=BTN_HOVER,
                  command=self._vdrive_save_log).pack(side="right", padx=4)
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
        self._vdrive_log("VDrive Manager gotowy.", "ok")

    # ── Akcje i helpery VDrive ────────────────────────────────────────────────
    def _vdrive_refresh_panel(self):
        """Odśwież listę i panel ikon nośników."""
        self._vdrive_rebuild_icons()
        self._vdrive_rebuild_tree()
        self._vdrive_log(f"Odświeżono panel. Nośników: {len(self._vdrives)}", "info")

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
            status_text  = f"● {drv['drive_letter']}" if drv["mounted"] else "○ odmontowany"
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
                        "✔ Zamontowany" if drv["mounted"] else "✗ Odmontowany",
                        drv["drive_letter"] or "—"),
                tags=(tag,))

    def _vdrive_icon_click(self, idx):
        children = self._vdrive_tree.get_children()
        if idx < len(children):
            self._vdrive_tree.selection_set(children[idx])
            self._vdrive_tree.focus(children[idx])

    def _vdrive_icon_dblclick(self, idx):
        self._vdrive_icon_click(idx)
        self._vdrive_mount_selected()

    def _vdrive_on_tree_select(self, event=None):
        sel = self._vdrive_tree.selection()
        if not sel:
            return
        children = self._vdrive_tree.get_children()
        idx = list(children).index(sel[0])
        if idx < len(self._vdrives):
            drv = self._vdrives[idx]
            info = (f"Typ: {drv['typ']}  |  Etykieta: {drv['label']}  |  "
                    f"Ścieżka: {drv['path'] or '—'}  |  "
                    f"Rozmiar: {drv['size_mb']} MB  |  "
                    f"Status: {'Zamontowany' if drv['mounted'] else 'Odmontowany'}  |  "
                    f"Litera: {drv['drive_letter'] or '—'}")
            self._vdrive_info_lbl.config(text=info, fg=FG_WHITE)

    def _vdrive_get_selected_idx(self):
        sel = self._vdrive_tree.selection()
        if not sel:
            return None
        children = list(self._vdrive_tree.get_children())
        if sel[0] in children:
            return children.index(sel[0])
        return None

    def _vdrive_mount_selected(self):
        idx = self._vdrive_get_selected_idx()
        if idx is None:
            messagebox.showinfo("Brak wyboru", "Zaznacz nośnik na liście.")
            return
        drv = self._vdrives[idx]
        if drv["mounted"]:
            messagebox.showinfo("Już zamontowany",
                                f"Nośnik '{drv['label']}' jest już zamontowany.")
            return
        # Sprawdź czy plik istnieje
        if drv["path"] and not os.path.exists(drv["path"]):
            messagebox.showwarning("Brak pliku",
                                   f"Plik nie istnieje:\n{drv['path']}")
            return
        # Symulacja montowania + generowanie komendy
        letter = drv["drive_letter"] or "D:"
        drv["mounted"] = True
        drv["drive_letter"] = letter
        self._vdrive_log(f"Montowanie: {drv['label']} ({drv['typ']}) → {letter}", "cmd")
        cmd = self._vdrive_build_mount_cmd(drv)
        self._vdrive_log(f"Komenda: {cmd}", "out")
        self._vdrive_log(f"✔ Zamontowano: {drv['label']} jako {letter}", "ok")
        self._vdrive_set_status(f"Zamontowano: {drv['label']}", "#6dde84")
        self._vdrive_refresh_panel()

    def _vdrive_unmount_selected(self):
        idx = self._vdrive_get_selected_idx()
        if idx is None:
            messagebox.showinfo("Brak wyboru", "Zaznacz nośnik na liście.")
            return
        drv = self._vdrives[idx]
        if not drv["mounted"]:
            messagebox.showinfo("Nie zamontowany",
                                f"Nośnik '{drv['label']}' nie jest zamontowany.")
            return
        drv["mounted"] = False
        self._vdrive_log(f"Odmontowano: {drv['label']}", "warn")
        self._vdrive_set_status(f"Odmontowano: {drv['label']}", "#f0c050")
        self._vdrive_refresh_panel()

    def _vdrive_delete_selected(self):
        idx = self._vdrive_get_selected_idx()
        if idx is None:
            messagebox.showinfo("Brak wyboru", "Zaznacz nośnik na liście.")
            return
        drv = self._vdrives[idx]
        if not messagebox.askyesno("Usuń nośnik",
                                    f"Usunąć nośnik '{drv['label']}' z listy?\n"
                                    "(plik na dysku nie zostanie usunięty)"):
            return
        self._vdrive_log(f"Usunięto z listy: {drv['label']}", "warn")
        self._vdrives.pop(idx)
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
        self._vdrive_create_icon_c.delete("all")
        self._vdrive_draw_icon(self._vdrive_create_icon_c, typ, 13, 13, mounted=True)

    def _vdrive_browse_path(self):
        sel = self._vdrive_type_var.get()
        typ = self._DRIVE_TYPES_MAP.get(sel, "HDD")
        if typ in ("ISO", "IMG", "BIN", "NRG", "MDF"):
            path = filedialog.askopenfilename(
                title="Wybierz plik obrazu",
                filetypes=[("Obrazy dysków",
                            "*.iso *.img *.bin *.nrg *.mdf *.vhd *.vhdx"),
                           ("Wszystkie", "*.*")])
        else:
            path = filedialog.askopenfilename(
                title="Wybierz plik VHD/VHDX",
                filetypes=[("VHD/VHDX", "*.vhd *.vhdx"),
                           ("Wszystkie", "*.*")])
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
        if letter == "(auto)":
            used = {d["drive_letter"] for d in self._vdrives}
            letter = next(
                (f"{c}:" for c in "DEFGHIJKLMNOPQRSTUVWXYZ"
                 if f"{c}:" not in used), "Z:")

        if not label:
            messagebox.showwarning("Brak etykiety", "Podaj etykietę nośnika.")
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
            "mounted":      self._vdrive_opt_automount.get(),
            "drive_letter": letter if self._vdrive_opt_automount.get() else "",
            "fs":           self._vdrive_new_fs.get(),
            "readonly":     self._vdrive_opt_readonly.get(),
            "persistent":   self._vdrive_opt_persistent.get(),
        }
        self._vdrives.append(drv)
        self._vdrive_create_status.config(
            text=f"✅ Nośnik '{label}' ({typ}) dodany.", fg="#6dde84")
        self._vdrive_log(f"Zarejestrowano nośnik: {label} ({typ}), ścieżka: {path or '—'}", "ok")
        cmd = self._vdrive_build_mount_cmd(drv)
        self._vdrive_log(f"Komenda montowania: {cmd}", "cmd")
        self._vdrive_set_status(f"Dodano: {label}", "#6dde84")
        self._vdrive_sel(0, "panel")
        self._vdrive_refresh_panel()

    def _vdrive_do_register(self):
        """Tylko rejestruje nośnik bez montowania."""
        self._vdrive_opt_automount.set(False)
        self._vdrive_do_create()
        self._vdrive_opt_automount.set(True)

    def _vdrive_clear_create_form(self):
        self._vdrive_new_label.delete(0, "end")
        self._vdrive_new_label.insert(0, "MójNosnik")
        self._vdrive_new_path.delete(0, "end")
        self._vdrive_new_size.delete(0, "end")
        self._vdrive_new_size.insert(0, "1024")
        self._vdrive_create_status.config(text="")

    def _vdrive_save_log(self):
        content = self._vdrive_log_text.get("1.0", "end-1c")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="vdrive_log.txt",
            filetypes=[("Text", "*.txt"), ("Wszystkie", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo("Zapisano", f"Log zapisany:\n{path}")

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

        self._db_sel_sub = _sel_db_sub

        for i, (label, key) in enumerate(db_sub_tabs):
            b = tk.Button(sub_bar, text=label, font=FONT_UI,
                          bg=BG_SUBTAB_ACT if i == 0 else BG_SUBTAB_INACT,
                          fg=FG_WHITE       if i == 0 else FG_GRAY,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          bd=0, highlightthickness=0,
                          command=lambda i=i, k=key: _sel_db_sub(i, k))
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

        tk.Label(pconn, text="🔌 Zarządzanie połączeniem z bazą danych",
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w", padx=12, pady=(10, 4))

        # wybór pliku
        row_path = tk.Frame(pconn, bg=BG_DARK)
        row_path.pack(fill="x", padx=12, pady=4)
        tk.Label(row_path, text="Plik bazy SQLite:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY, width=18, anchor="w").pack(side="left")
        tk.Entry(row_path, textvariable=self._db_path, font=FONT_MONO,
                 bg=BG_INPUT, fg=FG_WHITE, insertbackground=FG_WHITE,
                 relief="flat", highlightthickness=1, highlightbackground=BORDER_CLR,
                 highlightcolor=ACCENT_BLUE, width=44).pack(side="left", padx=(0, 6))
        tk.Button(row_path, text="📂 Przeglądaj…", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_browse_file).pack(side="left", padx=2)
        tk.Button(row_path, text="🆕 Nowa baza", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_new_file).pack(side="left", padx=2)

        # przyciski połączenia
        row_btns = tk.Frame(pconn, bg=BG_DARK)
        row_btns.pack(fill="x", padx=12, pady=6)
        self._db_btn_connect = tk.Button(row_btns, text="🟢 Połącz (Online)",
                  font=FONT_BOLD, bg="#2a5e2a", fg=FG_WHITE, relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  activebackground="#3a7e3a", activeforeground=FG_WHITE,
                  command=self._db_connect)
        self._db_btn_connect.pack(side="left", padx=(0, 6))
        self._db_btn_disconnect = tk.Button(row_btns, text="🔴 Rozłącz (Offline)",
                  font=FONT_BOLD, bg="#5e2a2a", fg=FG_WHITE, relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  activebackground="#7e3a3a", activeforeground=FG_WHITE,
                  state="disabled",
                  command=self._db_disconnect)
        self._db_btn_disconnect.pack(side="left", padx=(0, 6))
        tk.Button(row_btns, text="🔄 Test połączenia", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_test_conn).pack(side="left", padx=(0, 6))

        # panel informacji o połączeniu
        tk.Frame(pconn, bg=BORDER_CLR, height=1).pack(fill="x", padx=12, pady=6)
        tk.Label(pconn, text="ℹ Informacje o bazie:", font=FONT_BOLD,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w", padx=12)

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
            tk.Button(row_quick, text=txt, font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(side="left", padx=3)

        # ════════════════════════════════════════════════════════════════════
        # PANEL 2 — PLIKI BAZY DANYCH
        # ════════════════════════════════════════════════════════════════════
        pfiles = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_files"] = pfiles

        tk.Label(pfiles, text="📁 Pliki baz danych",
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w", padx=12, pady=(10, 4))

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
            tk.Button(fbar, text=txt, font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(side="left", padx=3)

        # drzewko plików
        tree_frame = tk.Frame(pfiles, bg=BG_DARK)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(6, 4))

        cols = ("Plik", "Rozmiar", "Ostatnia modyfikacja", "Ścieżka")
        self._db_files_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                            height=14, selectmode="browse")
        for c, w in zip(cols, (180, 90, 160, 360)):
            self._db_files_tree.heading(c, text=c)
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
            tk.Button(fbtm, text=txt, font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(side="left", padx=3)

        # ════════════════════════════════════════════════════════════════════
        # PANEL 3 — ZAPYTANIA SQL
        # ════════════════════════════════════════════════════════════════════
        pquery = tk.Frame(db_content, bg=BG_DARK)
        self._db_sub_frames["_db_show_query"] = pquery

        tk.Label(pquery, text="🔍 Edytor zapytań SQL",
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w", padx=12, pady=(10, 4))

        # edytor SQL
        sql_frame = tk.Frame(pquery, bg=BG_DARK)
        sql_frame.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(sql_frame, text="Zapytanie SQL:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w")
        self._db_sql_text = tk.Text(sql_frame, font=FONT_MONO, bg=BG_INPUT,
                                     fg="#c8d0f0", insertbackground=FG_WHITE,
                                     relief="flat", height=6,
                                     highlightthickness=1, highlightbackground=BORDER_CLR,
                                     highlightcolor=ACCENT_BLUE, wrap="none")
        self._db_sql_text.pack(fill="x", pady=(2, 0))

        # historia zapytań + szablony
        qbar = tk.Frame(pquery, bg=BG_PANEL, pady=5, padx=8)
        qbar.pack(fill="x")
        tk.Button(qbar, text="▶ Wykonaj (F9)", font=FONT_BOLD,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=12, pady=4,
                  cursor="hand2", activebackground="#3a7bc8", activeforeground=FG_WHITE,
                  command=self._db_run_query).pack(side="left", padx=(0, 6))
        tk.Button(qbar, text="🗑 Wyczyść", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=lambda: self._db_sql_text.delete("1.0", "end")).pack(side="left", padx=3)
        tk.Button(qbar, text="📋 Kopiuj wyniki", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_copy_results).pack(side="left", padx=3)
        tk.Button(qbar, text="💾 Eksportuj CSV", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_export_csv).pack(side="left", padx=3)

        # szablony SQL
        tk.Label(qbar, text=" | Szablony:", font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY).pack(side="left", padx=(10, 4))
        templates = [
            ("SELECT *",      "SELECT * FROM tabela LIMIT 100;"),
            ("CREATE TABLE",  "CREATE TABLE IF NOT EXISTS nowa_tabela (\n  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  nazwa TEXT NOT NULL,\n  wartosc TEXT\n);"),
            ("INSERT",        "INSERT INTO tabela (kolumna1, kolumna2) VALUES (?, ?);"),
            ("Tabele",        "SELECT name FROM sqlite_master WHERE type='table';"),
            ("Schemat",       "SELECT sql FROM sqlite_master WHERE type='table' AND name='tabela';"),
        ]
        for lbl, sql in templates:
            tk.Button(qbar, text=lbl, font=("Consolas", 8),
                      bg=BG_SUBTAB_INACT, fg=FG_GRAY, relief="flat", padx=6, pady=3,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=lambda s=sql: (self._db_sql_text.delete("1.0", "end"),
                                            self._db_sql_text.insert("1.0", s))
                      ).pack(side="left", padx=2)

        # wyniki
        tk.Label(pquery, text="Wyniki:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w", padx=12)
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

        tk.Label(pbrow, text="📊 Przeglądarka tabel",
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w", padx=12, pady=(10, 4))

        brow_top = tk.Frame(pbrow, bg=BG_DARK)
        brow_top.pack(fill="x", padx=12, pady=(0, 4))

        # lewa lista tabel
        left_col = tk.Frame(brow_top, bg=BG_DARK)
        left_col.pack(side="left", fill="y", padx=(0, 10))
        tk.Label(left_col, text="Tabele:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w")

        self._db_tables_lb = tk.Listbox(left_col, font=FONT_MONO, bg=BG_INPUT,
                                         fg=FG_WHITE, selectmode="browse",
                                         relief="flat", highlightthickness=1,
                                         highlightbackground=BORDER_CLR,
                                         highlightcolor=ACCENT_BLUE,
                                         selectbackground=BG_ROW_SEL,
                                         activestyle="none", width=22, height=18)
        self._db_tables_lb.pack(fill="y", expand=True)
        self._db_tables_lb.bind("<<ListboxSelect>>", lambda e: self._db_load_table())

        brow_btn_f = tk.Frame(left_col, bg=BG_DARK)
        brow_btn_f.pack(fill="x", pady=4)
        tk.Button(brow_btn_f, text="🔄 Odśwież", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_refresh_tables).pack(fill="x")

        # prawa: podgląd tabeli
        right_col = tk.Frame(brow_top, bg=BG_DARK)
        right_col.pack(side="left", fill="both", expand=True)

        brow_top2 = tk.Frame(right_col, bg=BG_PANEL, pady=4, padx=6)
        brow_top2.pack(fill="x")
        tk.Label(brow_top2, text="Wiersze:", font=FONT_UI,
                 bg=BG_PANEL, fg=FG_GRAY).pack(side="left")
        self._db_brow_limit = tk.Entry(brow_top2, font=FONT_MONO, bg=BG_INPUT,
                                        fg=FG_WHITE, insertbackground=FG_WHITE,
                                        relief="flat", width=6)
        self._db_brow_limit.insert(0, "500")
        self._db_brow_limit.pack(side="left", padx=4)
        tk.Button(brow_top2, text="▶ Załaduj", font=FONT_UI,
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground="#3a7bc8", activeforeground=FG_WHITE,
                  command=self._db_load_table).pack(side="left", padx=4)
        tk.Button(brow_top2, text="💾 Eksportuj CSV", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=3,
                  cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._db_export_table_csv).pack(side="left", padx=4)

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

        tk.Label(plog, text="📋 Log operacji bazodanowych",
                 font=FONT_BOLD, bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w", padx=12, pady=(10, 4))

        log_btn_f = tk.Frame(plog, bg=BG_PANEL, pady=5, padx=8)
        log_btn_f.pack(fill="x")
        for txt, cmd in [
            ("🗑 Wyczyść log", lambda: self._db_log_text.delete("1.0", "end")),
            ("💾 Zapisz log",  self._db_save_log),
            ("📋 Kopiuj log",  self._db_copy_log),
        ]:
            tk.Button(log_btn_f, text=txt, font=FONT_UI,
                      bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=8, pady=4,
                      cursor="hand2", activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                      command=cmd).pack(side="left", padx=3)

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

    def _db_connect(self):
        import sqlite3
        path = self._db_path.get().strip()
        if not path:
            messagebox.showwarning("Brak ścieżki", "Podaj ścieżkę do pliku bazy SQLite.")
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
            messagebox.showerror("Błąd połączenia", str(ex))

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
            messagebox.showinfo("Test", "Brak aktywnego połączenia.")
            return
        try:
            self._db_conn.execute("SELECT 1")
            messagebox.showinfo("Test połączenia", "✅ Połączenie aktywne i sprawne.")
            self._db_log("Test połączenia: OK", "ok")
        except Exception as ex:
            messagebox.showerror("Test połączenia", f"Błąd: {ex}")
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
            title="Wybierz plik bazy SQLite",
            filetypes=[("SQLite", "*.db *.sqlite *.sqlite3 *.s3db"),
                       ("Wszystkie", "*.*")])
        if path:
            self._db_path.set(path)
            self._db_log(f"Wybrany plik: {path}", "inf")

    def _db_new_file(self):
        import sqlite3
        path = filedialog.asksaveasfilename(
            title="Nowy plik bazy SQLite",
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
                messagebox.showerror("Błąd", str(ex))

    def _db_copy_path(self):
        path = self._db_path.get().strip()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)
            messagebox.showinfo("Skopiowano", "Ścieżka skopiowana do schowka.")

    def _db_scan_folder(self):
        folder = filedialog.askdirectory(title="Wybierz folder do skanowania")
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
        if messagebox.askyesno("Usuń plik", f"Usunąć plik bazy:\n{path}\n\nTej operacji nie można cofnąć!"):
            try:
                if self._db_online and self._db_path.get() == path:
                    self._db_disconnect()
                os.remove(path)
                self._db_log(f"Usunięto plik: {path}", "inf")
                self._db_refresh_files()
            except Exception as ex:
                messagebox.showerror("Błąd", str(ex))

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
            messagebox.showinfo("Eksport", f"Skopiowano do:\n{dst}")

    def _db_run_query(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning("Offline", "Najpierw połącz się z bazą danych.")
            return
        sql = self._db_sql_text.get("1.0", "end-1c").strip()
        if not sql:
            return
        self._db_query_hist.append(sql)
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
        messagebox.showinfo("Skopiowano", f"Skopiowano {len(rows)} wierszy.")

    def _db_export_csv(self):
        cols = self._db_result_tree["columns"]
        rows = [self._db_result_tree.item(r, "values") for r in self._db_result_tree.get_children()]
        if not rows:
            messagebox.showinfo("Brak danych", "Brak wyników do eksportu.")
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
            messagebox.showinfo("Eksport CSV", f"Zapisano:\n{path}")

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
            messagebox.showinfo("Eksport", f"Tabela '{table}' zapisana do:\n{path}")

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

    def _db_load_table(self):
        if not self._db_online or not self._db_conn:
            return
        sel = self._db_tables_lb.curselection()
        if not sel:
            return
        table = self._db_tables_lb.get(sel[0])
        try:
            limit = int(self._db_brow_limit.get())
        except ValueError:
            limit = 500
        try:
            cur = self._db_conn.cursor()
            cur.execute(f"SELECT * FROM [{table}] LIMIT {limit};")
            rows = cur.fetchall()
            cols = [d[0] for d in (cur.description or [])]
            self._db_brow_tree.delete(*self._db_brow_tree.get_children())
            self._db_brow_tree["columns"] = cols
            for c in cols:
                self._db_brow_tree.heading(c, text=c)
                self._db_brow_tree.column(c, width=max(90, len(c)*9), anchor="w")
            for i, row in enumerate(rows):
                tag = "odd" if i % 2 == 0 else "even"
                self._db_brow_tree.insert("", "end", values=row, tags=(tag,))
            self._db_brow_status.config(
                text=f"Tabela: {table}  |  {len(rows)} wierszy (limit: {limit})  |  {len(cols)} kolumn",
                fg="#6dde84")
            self._db_log(f"Załadowano tabelę '{table}': {len(rows)} wierszy.", "ok")
        except Exception as ex:
            self._db_log(f"Błąd ładowania tabeli '{table}': {ex}", "err")

    def _db_export_json(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning("Offline", "Najpierw połącz się z bazą.")
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
            messagebox.showinfo("Eksport JSON", f"Baza zapisana do:\n{path}")
        except Exception as ex:
            self._db_log(f"Błąd eksportu JSON: {ex}", "err")
            messagebox.showerror("Błąd eksportu", str(ex))

    def _db_import_json(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning("Offline", "Najpierw połącz się z bazą.")
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
                messagebox.showerror("Błąd", "Plik JSON powinien zawierać słownik tabel.")
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
            messagebox.showinfo("Import JSON", f"Zaimportowano {imported} wierszy.")
        except Exception as ex:
            self._db_log(f"Błąd importu JSON: {ex}", "err")
            messagebox.showerror("Błąd importu", str(ex))

    def _db_drop_all(self):
        if not self._db_online or not self._db_conn:
            messagebox.showwarning("Offline", "Najpierw połącz się z bazą.")
            return
        if not messagebox.askyesno("Wyczyść tabele",
                                    "Usunąć WSZYSTKIE tabele z bazy danych?\n"
                                    "Tej operacji nie można cofnąć!"):
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
            messagebox.showinfo("Zapisano", f"Log zapisany:\n{path}")

    def _db_copy_log(self):
        content = self._db_log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Skopiowano", "Log skopiowany do schowka.")

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
        self.lbl_count.config(text=f"Skryptów: {len(self.skrypty)}")
        if hasattr(self, "_runner_list"):
            self._runner_fill_list()

    # ══════════════════════════════════════════════════════════════════════════
    # JEDNOPLIKOWA BAZA — autoload, atomowy zapis, backup, autosave
    # ══════════════════════════════════════════════════════════════════════════
    def _autoload_db(self):
        """Wczytuje bazę z pliku przy starcie (jednoplikowa baza skryptów)."""
        path = getattr(self, "db_path", DB_FILE)
        if not path or not os.path.exists(path):
            self._rebuild_index()
            if hasattr(self, "_runner_fill_list"):
                self._runner_fill_list()
            return
        try:
            lista, notes = db_read(path)
            self.skrypty = lista
            self._rebuild_index()
            self._update_count()
            self._refresh_lista()
            if hasattr(self, "_runner_fill_list"):
                self._runner_fill_list()
            if notes:
                self._log_runner("Baza", " " + " | ".join(notes))
        except Exception as e:
            messagebox.showwarning(
                "Baza", f"Nie udało się wczytać bazy:\n{path}\n\n{e}\n\n"
                         "Kopia .bak zostanie użyta przy ręcznym otwarciu.")

    def save_db(self, path=None, save_as=False, silent=False):
        """Zapisuje całą bazę do stałego pliku JSON (atomowo + backup)."""
        path = path or getattr(self, "db_path", DB_FILE)
        if save_as:
            chosen = filedialog.asksaveasfilename(
                title="Zapisz bazę skryptów", defaultextension=".json",
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
            db_write(path, self.skrypty, backup_count=n_bak)
        except Exception as e:
            messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać bazy:\n{e}")
            return False
        self.db_path = path
        self._cfg["db_path"] = path
        cfg_save(self._cfg)
        self._last_save = now_str()
        if not silent:
            self._set_db_status(f"✓ Zapisano bazę: {os.path.basename(path)}")
        return True

    def _save_db(self, save_as=False):
        if self.save_db(save_as=save_as):
            messagebox.showinfo("Baza", f"Baza zapisana:\n{self.db_path}")

    def _after_db_change(self):
        """Wywoływane po zmianach w bazie — planuje autosave (odporny na klikanie)."""
        if str(self._cfg.get("autosave", "1")) != "1":
            return
        if getattr(self, "_autosave_pending", None):
            try:
                self.after_cancel(self._autosave_pending)
            except Exception:
                pass
        self._autosave_pending = self.after(1500, self._autosave_now)

    def _autosave_now(self):
        self._autosave_pending = None
        self.save_db(silent=True)

    def _open_db(self):
        path = filedialog.askopenfilename(
            title="Otwórz bazę skryptów",
            filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")])
        if not path:
            return
        try:
            lista, notes = db_read(path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można wczytać bazy:\n{e}")
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
        messagebox.showinfo("Baza", msg)

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
            messagebox.showerror("Błąd", str(e))

    def mainloop(self, n=0):
        """Pętla główna — dopiero po wejściu do niej działają after()/dialogi."""
        self._gui_ready = True
        return super().mainloop(n)

    def _on_close(self):
        """Zapis przy zamykaniu — autosave nie gubi ostatnich zmian."""
        if self.skrypty:
            self.save_db(silent=True)
        self.destroy()

    def _set_db_status(self, text):
        if hasattr(self, "lbl_db_status"):
            self.lbl_db_status.config(text=text)

    # ══════════════════════════════════════════════════════════════════════════
    # RUNNER — uruchamianie skryptów z panelu wyjścia
    # ══════════════════════════════════════════════════════════════════════════
    def _runner_env(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _runner_target(self):
        """Zwraca (rekord, kod, kategoria, nazwa) dla wybranego skryptu/formularza."""
        if getattr(self, "_runner_mode_edit", False) and hasattr(self, "text_kod"):
            kod = self.text_kod.get("1.0", "end-1c")
            nazwa = (self.entry_nazwa.get().strip() or "formularz")
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
        self._runner_start()

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
            messagebox.showinfo("Runner", "Zaznacz skrypt na liście.")
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
        dlg = tk.Toplevel(self)
        dlg.title("Uruchomienie kodu")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text="⚠  Uruchamiasz kod ze skryptu", font=("Consolas", 11, "bold"),
                 bg=BG_DARK, fg="#e0a020").pack(padx=16, pady=(14, 4))
        tk.Label(dlg, text=f"'{nazwa}'  —  kod zostanie wykonany lokalnie.",
                 font=FONT_UI, bg=BG_DARK, fg=FG_WHITE).pack(padx=16)
        tk.Label(dlg, text="Uruchamiaj tylko kod z zaufanego źródła.",
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(padx=16, pady=(2, 10))
        box = tk.Text(dlg, font=("Consolas", 8), bg=BG_PANEL, fg=FG_WHITE, height=8, width=70)
        box.insert("1.0", (kod or "")[:1200])
        box.config(state="disabled", relief="flat")
        box.pack(padx=16, fill="x")
        var = tk.BooleanVar(value=False)
        tk.Checkbutton(dlg, text="Nie pytaj ponownie dla tego skryptu", variable=var,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK).pack(padx=16, pady=6, anchor="w")
        res = {"ok": False}
        row = tk.Frame(dlg, bg=BG_DARK)
        row.pack(pady=(0, 14))

        def go():
            res["ok"] = True
            if var.get() and sc is not None:
                sc["zaufany"] = True
            dlg.destroy()

        tk.Button(row, text="▶ Uruchom", font=FONT_UI, bg="#2f6b3f", fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=go).pack(side="left", padx=6)
        tk.Button(row, text="Anuluj", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=dlg.destroy).pack(side="left", padx=6)
        self.wait_window(dlg)
        return res["ok"]

    def _runner_start(self):
        import subprocess
        import shlex
        if getattr(self, "_runner_proc", None) is not None:
            if self._runner_proc.poll() is None:
                if not messagebox.askyesno("Runner", "Proces wciąż działa. Zatrzymać go?"):
                    return
                self._runner_stop()
        sc, kod, kat, nazwa = self._runner_target()
        if not kod:
            self._log_runner("Runner", "Brak skryptu do uruchomienia.")
            return
        if not self._runner_check_trust(sc, kod, nazwa):
            return
        ok, info = runner_analyze(kod, kat, nazwa)
        if not ok:
            self._log_runner("Analiza", info)
            if getattr(self, "_gui_ready", True):
                messagebox.showerror("Analiza kodu", info)
            self._runner_current = {"sc": sc, "t0": datetime.datetime.now(), "info": info}
            self._runner_finished = False
            self._runner_finish(1)
            return
        args_raw = self._runner_entry_args.get().strip() if hasattr(self, "_runner_entry_args") else ""
        try:
            args = shlex.split(args_raw, posix=False)
        except ValueError:
            args = args_raw.split()
        interpreter = self._runner_venv_var.get().strip() if hasattr(self, "_runner_venv_var") else ""
        interpreter = "" if not interpreter or interpreter == "(domyślny)" else interpreter
        try:
            timeout = int(self._runner_entry_timeout.get() or 60)
        except ValueError:
            timeout = 60
        self._runner_workdir = tempfile.mkdtemp(prefix="bs_runner_")
        path = runner_save_temp(kod, kat, self._runner_workdir)
        self._runner_current = {"sc": sc, "path": path, "kat": kat, "nazwa": nazwa,
                                "t0": datetime.datetime.now(), "info": info,
                                "workdir": self._runner_workdir}
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
                                                     env=self._runner_env(), creationflags=flags)
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
                    cmd, cwd=self._runner_workdir, env=self._runner_env(),
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
            # krótka chwila na dopłynięcie reszty wyjścia z wątku czytającego
            self._runner_after_id = self.after(300, lambda: self._runner_watchdog(timeout, t0))
            return
        elapsed = (datetime.datetime.now() - t0).total_seconds()
        if timeout and elapsed > timeout:
            self._log_runner("Timeout", f"Przekroczono {timeout}s — zatrzymuję proces.")
            try:
                proc.kill()
            except Exception:
                pass
            self._runner_finish(-9)
            return
        left = f"{max(0, int(timeout - elapsed))}s" if timeout else "∞"
        if hasattr(self, "_runner_lbl_time"):
            self._runner_lbl_time.config(text=f"● działa  pozostało: {left}")
        self._runner_after_id = self.after(300, lambda: self._runner_watchdog(timeout, t0))

    def _runner_finish(self, rc):
        if getattr(self, "_runner_finished", False):
            return
        self._runner_finished = True
        cur = getattr(self, "_runner_current", None) or {}
        dt = (datetime.datetime.now() - cur.get("t0", datetime.datetime.now())).total_seconds()
        ok = (rc == 0)
        self._runner_set_busy(False)
        self._log_runner("Koniec", f"kod wyjścia={rc}  czas={dt:.2f}s  " + ("OK" if ok else "BŁĄD"),
                         "ok" if ok else "err")
        sc = cur.get("sc")
        if isinstance(sc, dict):
            sc["uruchomien"] = int(sc.get("uruchomien") or 0) + 1
            sc["ostatni_run"] = now_str()
            sc["ostatni_wynik"] = "OK" if ok else f"błąd({rc})"
            sc["ostatni_czas_ms"] = int(dt * 1000)
            self._after_db_change()
        if self._runner_proc is not None and self._runner_proc.poll() is None:
            try:
                self._runner_proc.kill()
            except Exception:
                pass
        if hasattr(self, "_runner_lbl_time"):
            self._runner_lbl_time.config(text="● gotowy")
        # posprzątaj katalog roboczy procesu
        wd = cur.get("workdir")
        if wd and os.path.isdir(wd):
            try:
                import shutil
                shutil.rmtree(wd, ignore_errors=True)
            except Exception:
                pass

    def _runner_run_sql(self, kod):
        """SQL uruchamiane na aktywnym połączeniu z zakładki Baza Danych."""
        conn = getattr(self, "_db_conn", None)
        online = getattr(self, "_db_online", False)
        if not online or conn is None:
            self._log_runner("SQL", "Brak aktywnego połączenia — podłącz bazę w zakładce Baza Danych.")
            messagebox.showwarning("SQL", "Najpierw połącz się z bazą w zakładce 'Baza Danych'.")
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

    def _runner_stop(self):
        proc = getattr(self, "_runner_proc", None)
        if proc is None or proc.poll() is not None:
            self._log_runner("Runner", "Brak działającego procesu.")
            return
        try:
            proc.kill()
        except Exception as e:
            self._log_runner("Stop", str(e), "err")
        self._log_runner("Stop", "Proces zatrzymany przez użytkownika.", "err")
        self._runner_finish(-1)

    def _runner_send_stdin(self):
        proc = getattr(self, "_runner_proc", None)
        if proc is None or proc.stdin is None:
            return
        line = self._runner_entry_stdin.get()
        try:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            self._log_runner(">", line)
            self._runner_entry_stdin.delete(0, "end")
        except Exception as e:
            self._log_runner("stdin", str(e), "err")

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

    def _log_runner(self, tag, text, level=""):
        if not hasattr(self, "_runner_out"):
            return
        for w in (self._runner_out, getattr(self, "_runner_out_sub", None)):
            if w is None:
                continue
            w.config(state="normal")
            if tag:
                w.insert("end", f"[{tag}] ", "tag")
            w.insert("end", (text or "") + "\n", level or "")
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
            messagebox.showinfo("Runner", f"Zapisano:\n{path}")

    def _runner_export_bat(self):
        """Zapisuje skrypt jako gotowy plik do uruchomienia poza aplikacją."""
        sc, kod, kat, nazwa = self._runner_target()
        if not kod:
            messagebox.showinfo("Runner", "Najpierw wybierz skrypt.")
            return
        ext = {"PowerShell": ".ps1", "Bash": ".sh"}.get(kat, ".bat")
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=re.sub(r"[^\w.-]+", "_", nazwa or "skrypt") + ext,
            filetypes=[(f"Plik {ext}", f"*{ext}"), ("Wszystkie", "*.*")])
        if not path:
            return
        base = os.path.splitext(path)[0]
        try:
            if ext == ".ps1":
                with open(path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
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
                    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
                        fh.write("@echo off\r\n" + line + "\r\npause\r\n")
            messagebox.showinfo("Runner", f"Zapisano:\n{path}")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def _runner_load_form(self):
        """Wczytuje kod z formularza 'Nowy skrypt' do runnera."""
        self._runner_mode_edit = True
        nm = (self.entry_nazwa.get().strip() if hasattr(self, "entry_nazwa") else "") or "(bez nazwy)"
        kat = self.var_kat.get() if hasattr(self, "var_kat") else ""
        label = f"formularz: {nm}  [{kat}]"
        if hasattr(self, "_runner_lbl_target"):
            self._runner_lbl_target.config(text=label)
        if hasattr(self, "_runner_lbl_target2"):
            self._runner_lbl_target2.config(text=label)

    def _runner_fill_list(self):
        if not hasattr(self, "_runner_list"):
            return
        self._runner_list.delete(0, "end")
        for s in self.skrypty:
            runs = int(s.get("uruchomien") or 0)
            self._runner_list.insert("end", f"{s.get('nazwa','?')}  [{s.get('kategoria','?')}]" +
                                             (f"  ×{runs}" if runs else ""))

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
        self._runner_lbl_target.config(text=f"{sc.get('nazwa')}  [{sc.get('kategoria')}]")
        if hasattr(self, "_runner_lbl_target2"):
            self._runner_lbl_target2.config(text=f"{sc.get('nazwa')}  [{sc.get('kategoria')}]")
        self._runner_out.config(state="normal")
        self._runner_out.delete("1.0", "end")
        self._runner_out.insert("end", f"// {sc.get('nazwa')} [{sc.get('kategoria')}]\n", "tag")
        self._runner_out.insert("end", (sc.get("kod") or "")[:3000], "")
        self._runner_out.config(state="disabled")
        self._runner_mirror_content(getattr(self, "_runner_out_sub", None))

    def _menu_pokaz_runner(self):
        self._sel_main(8, self._show_runner)

    def _show_runner(self):
        self.main_frames["runner"].pack(fill="both", expand=True)
        self._runner_fill_list()

    def _menu_ustawienia_runner(self):
        dlg = tk.Toplevel(self)
        dlg.title("Runner — ustawienia")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text="Interpreter (pusty = domyślny)", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w", padx=14, pady=(12, 0))
        e_int = tk.Entry(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                         insertbackground=FG_WHITE, relief="flat", width=60)
        e_int.insert(0, self._cfg.get("interpreter", ""))
        e_int.pack(padx=14, pady=(2, 8))
        tk.Label(dlg, text="Timeout [s] (0 = brak)", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w", padx=14)
        e_to = tk.Entry(dlg, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                        insertbackground=FG_WHITE, relief="flat", width=10)
        e_to.insert(0, self._cfg.get("timeout", "60"))
        e_to.pack(anchor="w", padx=14, pady=(2, 8))
        v_auto = tk.BooleanVar(value=str(self._cfg.get("autosave", "1")) == "1")
        tk.Checkbutton(dlg, text="Autosave bazy po zmianach", variable=v_auto,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK).pack(anchor="w", padx=14, pady=2)
        v_con = tk.BooleanVar(value=str(self._cfg.get("runner_console", "0")) == "1")
        tk.Checkbutton(dlg, text="Domyślnie uruchamiaj w nowej konsoli", variable=v_con,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK).pack(anchor="w", padx=14, pady=2)
        tk.Label(dlg, text="Kopie zapasowe (.bak)", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack(anchor="w", padx=14, pady=(8, 0))
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
        tk.Button(row, text="Zapisz", font=FONT_UI, bg=ACCENT_BLUE, fg=FG_WHITE,
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  command=save).pack(side="left", padx=4)
        tk.Button(row, text="Anuluj", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE,
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
        tk.Label(hdr, text="▶ Runner — uruchamianie skryptów",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self._runner_lbl_time = tk.Label(hdr, text="● gotowy", font=FONT_UI,
                                         bg=BG_PANEL, fg="#6dde84")
        self._runner_lbl_time.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        body = tk.Frame(outer, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        self._runner_build_body(body)

        # Wspólny panel wyjścia — w zakładce Skrypty → Runner oraz w zakładce Runner
        self._runner_main_frame = tk.Frame(self.sub_content, bg=BG_DARK)
        inner = tk.Frame(self._runner_main_frame, bg=BG_DARK)
        inner.pack(fill="both", expand=True, padx=10, pady=8)
        bar = tk.Frame(inner, bg=BG_DARK)
        bar.pack(fill="x")
        self._runner_lbl_target2 = tk.Label(bar, text="kod z formularza / wybrany skrypt",
                                            font=FONT_BOLD, bg=BG_DARK, fg="#e0c040", anchor="w")
        self._runner_lbl_target2.pack(side="left")
        tk.Button(bar, text="▶ Uruchom (F9)", font=FONT_UI, bg="#2f6b3f", fg=FG_WHITE,
                  relief="flat", padx=12, pady=4, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_start).pack(side="right", padx=3)
        tk.Button(bar, text="■ Stop", font=FONT_UI, bg="#603030", fg=FG_WHITE,
                  relief="flat", padx=10, pady=4, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_stop).pack(side="right", padx=3)
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
        top = tk.Frame(workdir, bg=BG_DARK)
        top.pack(fill="x")

        # lewa — lista skryptów
        left = tk.Frame(top, bg=BG_PANEL, highlightthickness=1,
                        highlightbackground=BORDER_CLR)
        left.pack(side="left", fill="both", padx=(0, 8))
        tk.Label(left, text="Skrypty", font=FONT_BOLD, bg=BG_PANEL,
                 fg=FG_WHITE).pack(anchor="w", padx=8, pady=(6, 2))
        self._runner_list = tk.Listbox(left, font=FONT_UI, bg=BG_INPUT, fg=FG_WHITE,
                                       selectbackground=BG_ROW_SEL, relief="flat",
                                       height=12, width=40, activestyle="none")
        self._runner_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._runner_list.bind("<<ListboxSelect>>", self._runner_pick)
        self._runner_fill_list()

        # prawa — opcje uruchomienia
        right = tk.Frame(top, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._runner_lbl_target = tk.Label(right, text="wybierz skrypt lub kod z formularza",
                                           font=FONT_BOLD, bg=BG_DARK, fg="#e0c040",
                                           anchor="w")
        self._runner_lbl_target.pack(fill="x")
        row1 = tk.Frame(right, bg=BG_DARK)
        row1.pack(fill="x", pady=(6, 2))
        tk.Label(row1, text="Interpreter:", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._runner_venv_var = tk.StringVar(value=self._cfg.get("interpreter") or "(domyślny)")
        self._runner_venv_cb = ttk.Combobox(row1, textvariable=self._runner_venv_var,
                                            font=FONT_UI, style="Dark.TCombobox", width=36)
        self._runner_venv_cb["values"] = self._runner_interpreter_choices()
        self._runner_venv_cb.pack(side="left", padx=6)
        tk.Button(row1, text="…", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=6, pady=2, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_pick_interpreter).pack(side="left")

        self._runner_interp2 = tk.Entry(right, font=FONT_MONO, bg=BG_INPUT, fg=FG_GRAY,
                                        relief="flat", highlightthickness=1,
                                        highlightbackground=BORDER_CLR, width=40)

        row2 = tk.Frame(right, bg=BG_DARK)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Argumenty:", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._runner_entry_args = tk.Entry(row2, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                           insertbackground=FG_WHITE, relief="flat",
                                           highlightthickness=1, highlightbackground=BORDER_CLR)
        self._runner_entry_args.pack(side="left", fill="x", expand=True, padx=6)

        row3 = tk.Frame(right, bg=BG_DARK)
        row3.pack(fill="x", pady=2)
        tk.Label(row3, text="Timeout [s]:", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._runner_entry_timeout = tk.Entry(row3, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                              insertbackground=FG_WHITE, relief="flat",
                                              highlightthickness=1, highlightbackground=BORDER_CLR,
                                              width=8)
        self._runner_entry_timeout.insert(0, self._cfg.get("timeout", "60"))
        self._runner_entry_timeout.pack(side="left", padx=6)
        self._runner_console_var = tk.BooleanVar(value=str(self._cfg.get("runner_console", "0")) == "1")
        tk.Checkbutton(row3, text="Nowa konsola", variable=self._runner_console_var,
                       bg=BG_DARK, fg=FG_GRAY, selectcolor=BG_INPUT, font=FONT_UI,
                       activebackground=BG_DARK).pack(side="left", padx=10)

        row4 = tk.Frame(right, bg=BG_DARK)
        row4.pack(fill="x", pady=(8, 4))

        def rbtn(text, color, cmd, attr=None, state="normal"):
            b = tk.Button(row4, text=text, font=FONT_UI, bg=color, fg=FG_WHITE,
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                          command=cmd, state=state)
            b.pack(side="left", padx=3)
            if attr:
                setattr(self, attr, b)

        rbtn("▶ Uruchom  (F9)", "#2f6b3f", self._runner_start, "_runner_btn_run")
        rbtn("▶ W nowej konsoli", BTN_DARK, lambda: self._runner_start_new_console(), "_runner_btn_run_nc")
        rbtn("■ Zatrzymaj", "#603030", self._runner_stop, "_runner_btn_stop", "disabled")
        rbtn("✕ Wyczyść", BTN_DARK, self._runner_clear)
        rbtn("💾 Eksport wyjścia", BTN_DARK, self._runner_export_out)
        rbtn("📄 .bat/.ps1", BTN_DARK, self._runner_export_bat)

        row5 = tk.Frame(right, bg=BG_DARK)
        row5.pack(fill="x", pady=(0, 4))
        tk.Label(row5, text="stdin:", font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(side="left")
        self._runner_entry_stdin = tk.Entry(row5, font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                                            insertbackground=FG_WHITE, relief="flat",
                                            highlightthickness=1, highlightbackground=BORDER_CLR)
        self._runner_entry_stdin.pack(side="left", fill="x", expand=True, padx=6)
        self._runner_entry_stdin.bind("<Return>", lambda e: self._runner_send_stdin())
        tk.Button(row5, text="Wyślij", font=FONT_UI, bg=BTN_DARK, fg=FG_WHITE, relief="flat",
                  padx=8, pady=2, cursor="hand2", activebackground=BTN_HOVER,
                  command=self._runner_send_stdin).pack(side="left")

        # konsola
        tk.Label(workdir, text="Wyjście", font=FONT_BOLD, bg=BG_DARK,
                 fg=FG_WHITE, anchor="w").pack(fill="x", pady=(8, 2))
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

    def _runner_start_new_console(self):
        self._runner_force_new_console = True
        self._runner_start()

    def _runner_interpreter_choices(self):
        """Lista interpreterów: domyślny + wykryte venv/python."""
        vals = ["(domyślny)"]
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
        for exe in ("node", "pwsh"):
            found = _sh.which(exe)
            if found and found not in vals:
                vals.append(found)
        gb = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Git", "bin", "bash.exe")
        if os.path.exists(gb) and gb not in vals:
            vals.append(gb)
        return vals

    def _runner_pick_interpreter(self):
        path = filedialog.askopenfilename(
            title="Wybierz interpreter",
            filetypes=[("Python", "python*.exe python*"), ("Wszystkie", "*.*")])
        if path:
            self._runner_venv_var.set(path)

    # ── dolny pasek ───────────────────────────────────────────────────────────
    def _build_bottom_bar(self, parent):
        bar = tk.Frame(parent, bg=BG_DARK, pady=6)
        bar.pack(fill="x", side="bottom", padx=8)

        def btn(master, text, color=BTN_DARK, cmd=None):
            tk.Button(master, text=text, font=FONT_UI,
                      bg=color, fg=FG_WHITE, relief="flat", padx=10, pady=5,
                      cursor="hand2", activebackground=BTN_HOVER,
                      activeforeground=FG_WHITE, command=cmd
                      ).pack(side="left", padx=3)

        btn(bar, "💾 Zapisz",          color=ACCENT_BLUE, cmd=self._zapisz)
        btn(bar, "▶ Uruchom (F9)",     color="#2f6b3f",   cmd=self._runner_run_form)
        btn(bar, "🗑 Wyczyść",                             cmd=self._wyczysc)
        btn(bar, "📋 Kopiuj Kod",                          cmd=self._kopiuj_kod)
        btn(bar, "📂 Wczytaj plik",                        cmd=self._wczytaj_plik)

        # ── Pasek stanu: linia / kolumna / znaki / słowa ──────────────────────
        self._status_lbl = tk.Label(bar, text="Ln 1  Col 1  |  0 zn  0 słów",
                                    font=("Consolas", 8), bg=BG_DARK, fg=FG_GRAY,
                                    anchor="w", padx=10)
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
                messagebox.showwarning("Brak nazwy", "Podaj nazwę skryptu!")
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
            if s.get("nazwa") == nazwa:
                target = i
                break
        if target is not None:
            old = self.skrypty[target]
            data["id"] = old.get("id") or uuid.uuid4().hex
            data["utworzony"] = old.get("utworzony") or now
            for k in ("uruchomien", "ostatni_run", "ostatni_wynik",
                      "ostatni_czas_ms", "zaufany"):
                if k in old:
                    data[k] = old[k]
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
            messagebox.showinfo("Zapisano", akcja)
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
            self._status_lbl.config(text="Ln 1  Col 1  |  0 zn  0 słów")

    def _kopiuj_kod(self):
        self.clipboard_clear()
        self.clipboard_append(self.text_kod.get("1.0", "end-1c"))
        messagebox.showinfo("Skopiowano", "Kod skopiowany do schowka.")

    def _wczytaj_plik(self):
        path = filedialog.askopenfilename(
            filetypes=[("Skrypty", "*.py *.sh *.ps1 *.js *.sql *.txt"),
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
            kat_map = {".py": "Python", ".sh": "Bash", ".ps1": "PowerShell",
                       ".js": "JavaScript", ".sql": "SQL"}
            if ext in kat_map:
                self.var_kat.set(kat_map[ext])
            # Podświetl składnię
            self._highlighter.highlight(self.text_kod, self.var_kat.get())

    # Rozszerzenie pliku → kategoria skryptu
    _EXT_KAT = {".py": "Python", ".sh": "Bash", ".ps1": "PowerShell",
                ".js": "JavaScript", ".sql": "SQL"}
    _SKRYPT_EXT = tuple(_EXT_KAT.keys()) + (".txt",)

    def _importuj_plik_skryptu(self):
        """Importuje pojedynczy plik skryptu jako nowy wpis w bazie."""
        path = filedialog.askopenfilename(
            title="Importuj plik skryptu",
            filetypes=[("Skrypty", "*.py *.sh *.ps1 *.js *.sql *.txt"),
                       ("Wszystkie pliki", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Błąd importu", str(e))
            return
        nazwa = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        kategoria = self._EXT_KAT.get(ext, "Other")
        existing = [x["nazwa"] for x in self.skrypty]
        if nazwa in existing:
            if not messagebox.askyesno(
                    "Skrypt istnieje",
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
        messagebox.showinfo("Import", f"Plik '{nazwa}' {akcja} do bazy.")

    def _importuj_katalog(self):
        """Importuje wszystkie pliki skryptów z wybranego katalogu."""
        folder = filedialog.askdirectory(title="Importuj cały katalog")
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
                "Import",
                "Nie znaleziono plików skryptów w wybranym katalogu.\n"
                "Obsługiwane rozszerzenia: " + ", ".join(self._SKRYPT_EXT))
            return
        if not messagebox.askyesno(
                "Import katalogu",
                f"Znaleziono {len(znalezione)} plików skryptów w:\n{folder}\n\n"
                "Zaimportować je do bazy?"):
            return
        dodane, nadpisane, pominiete = 0, 0, 0
        for full in znalezione:
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                pominiete += 1
                continue
            nazwa = os.path.basename(full)
            ext = os.path.splitext(full)[1].lower()
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
            "Import katalogu",
            f"Zaimportowano z:\n{folder}\n\n"
            f"Dodano: {dodane}\nNadpisano: {nadpisane}\nPominięto: {pominiete}")

    def _eksportuj(self, ext):
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=[(f"Plik .{ext}", f"*.{ext}")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_kod.get("1.0", "end-1c"))
            messagebox.showinfo("Eksport", f"Wyeksportowano do:\n{path}")


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
        tk.Label(hdr, text="🖥 Terminal",
                 font=("Consolas", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE).pack(side="left")
        self._terminal_status_lbl = tk.Label(hdr, text="Gotowy", font=FONT_UI,
                                              bg=BG_PANEL, fg="#6dde84")
        self._terminal_status_lbl.pack(side="right", padx=8)
        tk.Frame(outer, bg=BORDER_CLR, height=1).pack(fill="x")

        # ── Środek — info + przycisk ──────────────────────────────────────────
        center = tk.Frame(outer, bg=BG_DARK)
        center.pack(fill="both", expand=True)

        info_frame = tk.Frame(center, bg=BG_DARK)
        info_frame.place(relx=0.5, rely=0.4, anchor="center")

        tk.Label(info_frame, text="🖥", font=("Consolas", 48),
                 bg=BG_DARK, fg=ACCENT_BLUE).pack(pady=(0, 10))

        tk.Label(info_frame,
                 text="Terminal otwiera się w osobnym oknie systemowym.",
                 font=("Consolas", 11), bg=BG_DARK, fg=FG_WHITE).pack()
        tk.Label(info_frame,
                 text="Możesz go uruchomić ponownie w dowolnym momencie.",
                 font=FONT_UI, bg=BG_DARK, fg=FG_GRAY).pack(pady=(4, 20))

        tk.Label(info_frame, text="Skrypt:", font=FONT_UI,
                 bg=BG_DARK, fg=FG_GRAY).pack()

        self._terminal_script_var = tk.StringVar()
        try:
            import inspect as _inspect
            _self_dir = os.path.dirname(os.path.abspath(_inspect.getfile(self.__class__)))
        except Exception:
            _self_dir = os.getcwd()
        self._terminal_script_var.set(os.path.join(_self_dir, "terminal.py"))

        entry_frame = tk.Frame(info_frame, bg=BG_DARK)
        entry_frame.pack(fill="x", pady=(4, 16))

        tk.Entry(entry_frame, textvariable=self._terminal_script_var,
                 font=FONT_MONO, bg=BG_INPUT, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER_CLR,
                 width=50).pack(side="left", padx=(0, 4))

        def _browse():
            path = filedialog.askopenfilename(
                filetypes=[("Python", "*.py"), ("Wszystkie", "*.*")])
            if path:
                self._terminal_script_var.set(path)

        tk.Button(entry_frame, text="📂", font=FONT_UI,
                  bg=BTN_DARK, fg=FG_WHITE, relief="flat", padx=6, pady=4,
                  cursor="hand2", activebackground=BTN_HOVER,
                  command=_browse).pack(side="left")

        tk.Button(info_frame,
                  text="▶  Otwórz Terminal",
                  font=("Consolas", 12, "bold"),
                  bg=ACCENT_BLUE, fg=FG_WHITE, relief="flat",
                  padx=24, pady=10, cursor="hand2",
                  activebackground=BTN_HOVER, activeforeground=FG_WHITE,
                  command=self._terminal_launch).pack()

        self._terminal_proc = None

    def _terminal_launch(self):
        import sys, subprocess, os as _os

        script = self._terminal_script_var.get().strip()
        if not _os.path.isfile(script):
            messagebox.showerror("Błąd", f"Nie znaleziono pliku:\n{script}")
            return

        # Jeśli poprzedni proces jeszcze żyje — nie otwieraj drugiego
        if self._terminal_proc and self._terminal_proc.poll() is None:
            messagebox.showinfo("Terminal", "Terminal już działa w osobnym oknie.")
            return

        try:
            if sys.platform == "win32":
                # Windows: cmd /k python terminal.py — zostaje otwarte po zakończeniu
                self._terminal_proc = subprocess.Popen(
                    ["cmd", "/k", sys.executable, script],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            elif sys.platform == "darwin":
                # macOS: otwórz Terminal.app
                apple_script = (
                    'tell application "Terminal" to do script '
                    f'"{sys.executable} \\"{script}\\""'
                )
                self._terminal_proc = subprocess.Popen(
                    ["osascript", "-e", apple_script])
            else:
                # Linux: próbuj kolejno popularne emulatory
                for term in ("x-terminal-emulator", "gnome-terminal",
                             "xfce4-terminal", "konsole", "xterm"):
                    if _os.popen(f"which {term} 2>/dev/null").read().strip():
                        if term == "gnome-terminal":
                            self._terminal_proc = subprocess.Popen(
                                [term, "--", sys.executable, script])
                        else:
                            self._terminal_proc = subprocess.Popen(
                                [term, "-e", f"{sys.executable} {script}"])
                        break
                else:
                    messagebox.showerror(
                        "Błąd",
                        "Nie znaleziono emulatora terminala.\n"
                        "Zainstaluj xterm:  sudo apt install xterm")
                    return

            self._terminal_status_lbl.config(text="Uruchomiony ✓", fg="#6dde84")

        except Exception as ex:
            messagebox.showerror("Błąd uruchomienia", str(ex))
            self._terminal_status_lbl.config(text="Błąd", fg="#e06c75")

    def _show_terminal(self):
        self.main_frames["terminal"].pack(fill="both", expand=True)
        # Auto-uruchom przy pierwszym wejściu
        if not hasattr(self, "_terminal_opened_once"):
            self._terminal_opened_once = True
            self.after(100, self._terminal_launch)


if __name__ == "__main__":
    import argparse

    def _cli_main(argv=None):
        """Tryb wiersza poleceń: lista, eksport, import, uruchomienie skryptu, GUI."""
        p = argparse.ArgumentParser(
            prog="baza_skryptow.py",
            description="Baza Skryptów v%s — jednoplikowa baza + runner skryptów." % APP_VER,
            epilog="Bez argumentów uruchamia GUI. Przykłady:\n"
                   "  python baza_skryptow.py --list\n"
                   "  python baza_skryptow.py --backup backup.json\n"
                   "  python baza_skryptow.py --run \"Skrypt A\" --timeout 30\n"
                   "  python baza_skryptow.py --headless --export out.json")
        p.add_argument("--db", default="", help="ścieżka pliku bazy (domyślnie baza_skryptow.json)")
        p.add_argument("--list", action="store_true", help="wypisz skrypty z bazy")
        p.add_argument("--export", metavar="PLIK", help="zapisz kopię bazy do pliku JSON")
        p.add_argument("--import", metavar="PLIK", dest="import_",
                       help="scal skrypty z pliku JSON do bazy")
        p.add_argument("--backup", metavar="PLIK", help="kopia zapasowa bazy (alias --export)")
        p.add_argument("--run", metavar="NAZWA", help="uruchom skrypt z bazy po nazwie")
        p.add_argument("--timeout", type=int, default=None, help="timeout uruchomienia [s]")
        p.add_argument("--args", default="", help="argumenty dla uruchamianego skryptu")
        p.add_argument("--headless", action="store_true", help="nie otwieraj GUI")
        p.add_argument("--gui-runner", action="store_true", help="otwórz GUI na zakładce Runner")
        p.add_argument("--version", action="version", version=f"Baza Skryptów v{APP_VER} (schema {DB_SCHEMA})")
        opts = p.parse_args(argv)

        cfg = cfg_load()
        db_path = os.path.abspath(opts.db) if opts.db else (cfg.get("db_path") or DB_FILE)
        if not os.path.exists(db_path):
            if opts.headless or opts.run or opts.list or opts.export or opts.import_:
                lista = []
            else:
                lista = None
        elif os.path.exists(db_path):
            try:
                lista, notes = db_read(db_path)
                for n in notes:
                    print("[baza]", n, file=sys.stderr)
            except Exception as e:
                print(f"[błąd] nie można wczytać bazy {db_path}: {e}", file=sys.stderr)
                return 2
        else:
            lista = []

        if opts.list:
            for sc in lista or []:
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
            db_write(target, lista or [], backup_count=0)
            print(f"Zapisano {len(lista or [])} skrypt(ów) → {target}")

        if opts.run:
            sc = next((s for s in (lista or []) if s.get("nazwa") == opts.run), None)
            if sc is None:
                print(f"[błąd] nie znaleziono skryptu '{opts.run}' (użyj --list)", file=sys.stderr)
                return 1
            import shlex, subprocess, time
            kat = sc.get("kategoria", "Other")
            workdir = tempfile.mkdtemp(prefix="bs_cli_")
            path = runner_save_temp(sc.get("kod", ""), kat, workdir)
            interpreter = cfg.get("interpreter") or ""
            if kat == "Python" and interpreter and not os.path.exists(interpreter):
                interpreter = ""
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

        if opts.export or opts.backup or opts.import_ or opts.list or opts.run or opts.headless:
            return 0

        app = BazaSkryptow(start_runner=opts.gui_runner)
        app.mainloop()
        return 0

    sys.exit(_cli_main())
