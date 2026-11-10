# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: launcher.py
# Opis:  Małe okno GUI (tkinter) z czterema przyciskami:
#        Run    — uruchamia CodeMate (baza_skryptow.py), jak run.bat
#        Test   — uruchamia testy pytest, jak run_test.bat
#        About  — okno popup "About"
#        Quit   — zamyka okno
# Wersja: 1.0.0
# Autor:  Sebastian Januchowski · polsoft.ITS™ Group
# ──────────────────────────────────────────────────────────────────────────────
import base64
import ctypes
import datetime
import html
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(APP_DIR, "src", "pic", "logo.png")
ICON_DIR = os.path.join(APP_DIR, "src", "pic", "icons")
VENV_PYTHONW = os.path.join(APP_DIR, ".venv", "Scripts", "pythonw.exe")
VENV_PYTHON = os.path.join(APP_DIR, ".venv", "Scripts", "python.exe")

# ── Kolory / czcionki (spójne z CodeMate) ────────────────────────────────────
BG_DARK = "#eef1f7"
BG_PANEL = "#ffffff"
BG_BTN = "#dde3ee"
BG_BTN_HOVER = "#cfd7e8"
ACCENT = "#2f6cb0"
FG_TEXT = "#20293a"
FG_GRAY = "#6b7280"
FONT = ("Consolas", 11)


def pythonw() -> str:
    """Zwraca pythonw z .venv lub systemowy."""
    return VENV_PYTHONW if os.path.isfile(VENV_PYTHONW) else "pythonw"


def python() -> str:
    """Zwraca python z .venv lub systemowy."""
    return VENV_PYTHON if os.path.isfile(VENV_PYTHON) else sys.executable


# ── Efekt Aero Glass ──────────────────────────────────────────────────────────
def _apply_glass() -> None:
    """Przezroczyste tło BG_DARK + blur Acrylic (Windows 10 1809+).

    Obszary w kolorze BG_DARK stają się przezroczyste, a DWM rozmywa
    to, co jest za oknem. Na innych systemach zostaje zwykłe tło.
    """
    try:
        root.attributes("-transparentcolor", BG_DARK)
    except tk.TclError:
        return
    try:
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint),
                        ("AnimationId", ctypes.c_int)]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [("Attribution", ctypes.c_void_p),
                        ("AccentPolicy", ctypes.c_void_p)]

        accent = ACCENT_POLICY()
        accent.AccentState = 4                  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2                  # obramowanie z obu stron
        accent.GradientColor = 0x99F7F1EE       # ABGR — jasny tint BG_DARK

        data = WINCOMPATTRDATA()
        data.Attribution = 19                   # WCA_ACCENT_POLICY
        data.AccentPolicy = ctypes.cast(
            ctypes.pointer(accent), ctypes.c_void_p)
        hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
        ctypes.windll.user32.SetWindowCompositionAttribute(
            hwnd, ctypes.byref(data))
    except Exception:
        pass                                    # brak wsparcia — zostaje tylko alpha-key


def run_app() -> None:
    """Uruchamia program jak run.bat (bez okna konsoli)."""
    if not os.path.isfile(os.path.join(APP_DIR, "baza_skryptow.py")):
        messagebox.showerror("Error", "baza_skryptow.py not found!")
        return
    subprocess.Popen([pythonw(), "baza_skryptow.py"], cwd=APP_DIR)


def run_tests() -> None:
    """Uruchamia testy jak run_test.bat — w tle, wynik w okienku."""
    log_win = tk.Toplevel(root)
    log_win.title("Running tests…")
    log_win.configure(bg=BG_PANEL)
    log_win.geometry("560x320")
    log_win.overrideredirect(True)      # okno bez titlebara

    # górny pasek z tytułem i przyciskiem zamknięcia
    bar = tk.Frame(log_win, bg=BG_DARK, padx=8, pady=4)
    bar.pack(fill="x")
    bar_title = tk.Label(bar, text="Test output",
                         font=("Consolas", 10, "bold"),
                         bg=BG_DARK, fg=FG_GRAY)
    bar_title.pack(side="left")
    tk.Button(bar, text="✕", font=("Consolas", 10, "bold"), bg=BG_BTN,
              fg=FG_TEXT, relief="flat", width=3, bd=0, cursor="hand2",
              activebackground=BG_BTN_HOVER, activeforeground=FG_TEXT,
              command=log_win.destroy).pack(side="right")
    for _w in (bar, bar_title):
        _w.bind("<Button-1>", _drag_start)
        _w.bind("<B1-Motion>", _drag_move)
    log_win.bind("<Escape>", lambda e: log_win.destroy())

    txt = tk.Text(log_win, font=("Consolas", 9), bg=BG_PANEL, fg=FG_TEXT,
                  relief="flat", wrap="none", width=128, height=22,
                  padx=6, pady=4)
    txt.pack(fill="both", expand=True, padx=4, pady=4)
    sb = tk.Scrollbar(log_win, orient="vertical", command=txt.yview)
    txt.config(yscrollcommand=sb.set)
    # scrollbar po prawej (pod Text w siatce packing)
    sb.pack(side="right", fill="y", before=txt)
    txt.tag_configure("green", foreground="#1a7f37")
    txt.tag_configure("red", foreground="#cf222e")
    txt.tag_configure("yellow", foreground="#9a6700")
    txt.tag_configure("summary", foreground=FG_GRAY)
    txt.insert("end", "⏳ Running tests — this may take a minute…\n\n")
    txt.see("end")

    def size_to_content() -> None:
        """Dopasuj okno idealnie do rozmiaru tekstu (kolumny × wiersze)."""
        try:
            log_win.update_idletasks()
            # szerokość wg najdłuższej linii w buforze + zapas na szerokie znaki
            lines = txt.get("1.0", "end").splitlines()
            longest = max((len(l) for l in lines), default=80)
            cols = max(txt["width"], longest + 6)
            txt.config(width=cols)
            log_win.update_idletasks()
            w = txt.winfo_reqwidth() + 2 * 4 + 18  # tekst + padx + scrollbar
            h = txt.winfo_reqheight() + 2 * 4 + bar.winfo_reqheight()
            # ogranicz do 92% szerokości ekranu
            max_w = int(root.winfo_screenwidth() * 0.92)
            max_h = int(root.winfo_screenheight() * 0.85)
            w = max(w, 720)
            w, h = min(w, max_w), min(h, max_h)
            x = (root.winfo_screenwidth() - w) // 2
            y = (root.winfo_screenheight() - h) // 2
            log_win.geometry(f"{w}x{h}+{x}+{y}")
        except tk.TclError:
            pass                                # okno już zamknięte

    size_to_content()
    # dopasuj ponownie po pierwszych liniach (gdy treść dłuższa niż startowa)
    _resize_count = [0]

    def resize_check() -> None:
        if _resize_count[0] < 3:
            _resize_count[0] += 1
            size_to_content()
            root.after(300, resize_check)

    summary_re = re.compile(
        r"^[\d,]+ [\w ,+-]+ in [\d.]+s$")

    def _ins(text: str, tag: str | None) -> None:
        txt.insert("end", text, tag) if tag else txt.insert("end", text)

    def append(line: str, tag: str | None = None) -> None:
        """Wstawia linię; fragmenty [xx%] maluje na żółto, resztę tagiem."""
        try:
            pos = 0
            for m in re.finditer(r"\[\s*\d+%\]", line):
                if m.start() > pos:
                    _ins(line[pos:m.start()], tag)
                _ins(m.group(0), "yellow")
                pos = m.end()
            _ins(line[pos:], tag)
            txt.see("end")
        except tk.TclError:
            pass                                # okno już zamknięte

    def line_tag(line: str) -> str | None:
        """Zwraca tag koloru dla wybranych linii pytest."""
        if "test session starts" in line:
            return "green"
        # podsumowanie np. "593 passed in 33.93s" / "1 failed, 2 passed in 0.10s"
        stripped = line.strip("= ").strip()
        if summary_re.match(stripped) and re.search(r"\b(passed|failed|error)\b",
                                                  stripped):
            return "summary"
        return None

    def worker() -> None:
        # strumieniowanie: czytamy stdout linia po linii i pokazujemy na żywo
        proc = subprocess.Popen(
            [python(), "-X", "utf8", "-m", "pytest", "tests/",
             "-q", "--no-cov", "--rootdir=.", "-v", "--tb=line"],
            cwd=APP_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        rc = 1
        try:
            for line in proc.stdout:            # blokuje do nadejścia linii
                line = line.rstrip()
                if line:
                    root.after(0, lambda l=line: append(
                        l + "\n", line_tag(l)))
            proc.wait(timeout=60)
            rc = proc.returncode
        except Exception as e:
            root.after(0, lambda err=e: append(
                f"\nError: {err}\n", "red"))

        def finish() -> None:
            try:
                append("\n" + ("─" * 96) + "\n")
                size_to_content()
                if rc == 0:
                    log_win.title("Tests — OK")
                    txt.tag_configure("summary", foreground="#1a7f37")
                    append("✔ All tests passed.\n", "green")
                else:
                    log_win.title(f"Tests — FAILED (code {rc})")
                    txt.tag_configure("summary", foreground="#cf222e")
                    append(f"✘ Tests failed (exit code {rc}).\n", "red")
            except tk.TclError:
                pass                            # okno już zamknięte

        try:
            root.after(0, finish)
        except RuntimeError:
            pass

    threading.Thread(target=worker, daemon=True).start()
    resize_check()
    log_win.lift()


# tłumaczenie etykiet --stats (print_stats ma zaszyte polskie napisy)
_STATS_EN = {
    "skryptów": "scripts",
    "w koszu": "in trash",
    "linii kodu": "lines of code",
    "uruchomień": "runs",
    "zaufanych": "trusted",
    "z historią wersji": "with version history",
    "plany harmonogramu": "schedule plans",
    "kategorie": "categories",
    "top tagi": "top tags",
}


def _format_stats(out: str) -> str:
    """Formatuje wyjście --stats: każda statystyka w osobnym wierszu,
    etykiety wyrównane do lewej, wartości w jednej pionowej kolumnie."""
    lines = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        # segmenty statystyk rozdzielone 3+ spacjami, np.
        # "skryptów: 0   w koszu: 0   linii kodu: 0"
        segs = [s.strip() for s in re.split(r"\s{3,}", stripped) if s.strip()]
        pairs = []
        for s in segs:
            lab, sep, val = s.partition(":")
            # etykieta musi zaczynać się literą — odrzuca nagłówki
            # typu "== CodeMate — C:\..." i notatki "[baza] ..."
            if sep and val.strip() and re.match(r"^\w", lab.strip()):
                lab = _STATS_EN.get(lab.strip(), lab.strip())
                val = val.strip().replace("aktywne", "active")
                pairs.append((lab, val))
            else:
                pairs = None
                break
        if pairs:
            for lab, val in pairs:
                lines.append(f"{lab + ':':<26}{val}")
        elif stripped.rstrip(":") in _STATS_EN:
            # nagłówki sekcji — po angielsku, od lewej
            lines.append(_STATS_EN[stripped.rstrip(":")] + ":")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def show_stats() -> None:
    """Przycisk Stats — statystyki bazy skryptów (--stats programu głównego)."""
    win = tk.Toplevel(root)
    win.title("CodeMate — Statistics")
    win.configure(bg=BG_PANEL)
    win.geometry("640x420")
    win.overrideredirect(True)          # okno bez titlebara

    # górny pasek z tytułem i przyciskiem zamknięcia
    bar = tk.Frame(win, bg=BG_DARK, padx=8, pady=4)
    bar.pack(fill="x")
    bar_title = tk.Label(bar, text="Scripts — statistics",
                         font=("Consolas", 10, "bold"),
                         bg=BG_DARK, fg=FG_GRAY)
    bar_title.pack(side="left")
    tk.Button(bar, text="✕", font=("Consolas", 10, "bold"), bg=BG_BTN,
              fg=FG_TEXT, relief="flat", width=3, bd=0, cursor="hand2",
              activebackground=BG_BTN_HOVER, activeforeground=FG_TEXT,
              command=win.destroy).pack(side="right")
    for _w in (bar, bar_title):
        _w.bind("<Button-1>", _drag_start)
        _w.bind("<B1-Motion>", _drag_move)
    win.bind("<Escape>", lambda e: win.destroy())

    txt = tk.Text(win, font=("Consolas", 10), bg=BG_PANEL, fg=FG_TEXT,
                  relief="flat", wrap="none", padx=10, pady=8)
    txt.pack(fill="both", expand=True, padx=4, pady=4)
    txt.insert("end", "⏳ Loading statistics…\n")
    txt.tag_configure("h", font=("Consolas", 16, "bold"),
                      foreground=ACCENT, justify="center")
    txt.tag_configure("hs", font=("Consolas", 10),
                      foreground=FG_TEXT, justify="center")
    txt.tag_configure("path", font=("Consolas", 9),
                      foreground=FG_GRAY, justify="center")

    # znak wodny — logo w prawym dolnym rogu
    try:
        wm_img = tk.PhotoImage(file=LOGO_PATH).subsample(4)   # ~85 px
        wm = tk.Label(win, image=wm_img, bg=BG_PANEL)
        wm.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")
        wm.image = wm_img                     # referencja — bez GC
    except tk.TclError:
        pass                                  # brak pliku — bez znaku

    def worker() -> None:
        try:
            proc = subprocess.run(
                [python(), "-X", "utf8", "baza_skryptow.py", "--stats"],
                cwd=APP_DIR, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30)
            out = (proc.stdout or "") + (proc.stderr or "")
        except Exception as err:
            out = f"Error: {err}\n"

        def fill() -> None:
            try:
                txt.delete("1.0", "end")
                body = _format_stats(out)
                lines = body.split("\n")
                if lines and lines[0].startswith("=="):
                    # nagłówek: CodeMate (pogrubiony) + statistic + ścieżka bazy
                    path = (lines[0].split("—", 1)[-1].strip()
                            if "—" in lines[0] else "")
                    txt.insert("end", "CodeMate\n", "h")
                    txt.insert("end", "statistic\n", "hs")
                    txt.insert("end", path + "\n\n", "path")
                    txt.insert("end", "\n".join(lines[1:]))
                else:
                    txt.insert("end", body)
                txt.see("end")
            except tk.TclError:
                pass                            # okno już zamknięte

        try:
            root.after(0, fill)
        except RuntimeError:
            pass

    threading.Thread(target=worker, daemon=True).start()
    win.lift()


# ── Raport HTML ───────────────────────────────────────────────────────────────

def _logo_data_uri() -> str:
    """Logo jako data URI (base64) do osadzenia w raporcie HTML."""
    try:
        with open(LOGO_PATH, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(
                f.read()).decode()
    except OSError:
        return ""


def _build_report_html(output: str, rc: int) -> str:
    """Buduje raport HTML z surowego wyjścia pytest."""
    e = html.escape
    tests = []                                   # [(nazwa, status)]
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    duration = "—"

    test_re = re.compile(
        r"^(?P<name>\S+::\S+)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|"
        r"XFAIL|XPASS)\b")
    log_lines = []
    for raw in output.splitlines():
        line = raw.strip()
        m = test_re.match(line)
        if m:
            tests.append((m.group("name"), m.group("status")))
        # linia podsumowania np. "1 failed, 592 passed in 33.93s"
        s = line.strip("= ").strip()
        is_summary = bool(re.match(r"^[\d,]+ [\w ,+-]+ in [\d.]+s$", s))
        if is_summary:
            for n, word in re.findall(r"([\d,]+)\s+(\w+)", s):
                w = word.rstrip("s")
                if w in counts:
                    counts[w] += int(n.replace(",", ""))
            dm = re.search(r"in ([\d.]+)s", s)
            if dm:
                duration = dm.group(1) + "s"
            cls = ("log-bad" if re.search(r"\b(failed|error)\b", s)
                   else "log-ok")
            log_lines.append(f'<span class="{cls}">{e(raw)}</span>')
        else:
            log_lines.append(e(raw))
    log_html = "\n".join(log_lines)

    total = len(tests) or sum(counts.values())
    pct = round(100 * counts["passed"] / total) if total else 0
    ok = rc == 0
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    badge_cls = {"PASSED": "pass", "FAILED": "fail", "ERROR": "fail",
                 "SKIPPED": "skip"}
    rows = "".join(
        f'<tr><td class="name">{e(name)}</td>'
        f'<td><span class="badge {badge_cls.get(st, "skip")}">{e(st)}</span>'
        f"</td></tr>"
        for name, st in tests)

    cards = "".join(
        f'<div class="card"><div class="num {cls}">{val}</div>'
        f'<div class="lbl">{lbl}</div></div>'
        for cls, lbl, val in (
            ("green", "Passed", counts["passed"]),
            ("red", "Failed", counts["failed"]),
            ("red", "Errors", counts["error"]),
            ("yellow", "Skipped", counts["skipped"]),
            ("", "Total", total),
            ("", "Duration", duration),
        ))

    verdict = ("✔  ALL TESTS PASSED" if ok
               else f"✘  TESTS FAILED (exit code {rc})")
    vcls = "ok" if ok else "bad"

    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="" '
                 'style="height:34px;vertical-align:-8px;'
                 'margin-right:10px;">' if logo_uri else "◈ ")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>CodeMate — Test Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ background:#10141f; color:#c8d0f0; font-family:Consolas,monospace;
         padding:32px; }}
  .wrap {{ max-width:1100px; margin:0 auto; }}
  h1 {{ color:#3a7bc8; font-size:26px; }}
  .sub {{ color:#8a8fa8; margin:6px 0 24px; }}
  .verdict {{ display:inline-block; padding:10px 22px; border-radius:8px;
             font-weight:bold; font-size:18px; margin-bottom:24px; }}
  .verdict.ok {{ background:#3fb95022; color:#3fb950; border:1px solid #3fb95055; }}
  .verdict.bad {{ background:#f8514922; color:#f85149; border:1px solid #f8514955; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
           gap:14px; margin-bottom:28px; }}
  .card {{ background:#181d2c; border:1px solid #232941; border-radius:10px;
          padding:16px; text-align:center; }}
  .num {{ font-size:26px; font-weight:bold; }}
  .num.green {{ color:#3fb950; }} .num.red {{ color:#f85149; }}
  .num.yellow {{ color:#d29922; }}
  .lbl {{ color:#8a8fa8; font-size:11px; margin-top:4px; text-transform:uppercase; }}
  .bar {{ height:10px; background:#232941; border-radius:6px; overflow:hidden;
         margin-bottom:28px; }}
  .bar > div {{ height:100%; background:linear-gradient(90deg,#3fb950,#56d364);
               width:{pct}%; }}
  table {{ width:100%; border-collapse:collapse; background:#181d2c;
          border:1px solid #232941; border-radius:10px; overflow:hidden; }}
  th {{ background:#232941; color:#8a8fa8; text-align:left; padding:10px 14px;
       font-size:11px; text-transform:uppercase; }}
  td {{ padding:8px 14px; border-top:1px solid #232941; font-size:13px; }}
  td.name {{ color:#e6e9f5; }}
  .badge {{ padding:3px 10px; border-radius:12px; font-size:11px;
           font-weight:bold; }}
  .badge.pass {{ background:#3fb95022; color:#3fb950; }}
  .badge.fail {{ background:#f8514922; color:#f85149; }}
  .badge.skip {{ background:#d2992222; color:#d29922; }}
  details {{ margin-top:24px; }}
  summary {{ cursor:pointer; color:#8a8fa8; padding:8px 0; }}
  pre {{ background:#0b0e18; border:1px solid #232941; border-radius:10px;
        padding:16px; overflow-x:auto; font-size:12px; line-height:1.5;
        white-space:pre-wrap; word-break:break-all; }}
  .log-ok {{ color:#3fb950; font-weight:bold; }}
  .log-bad {{ color:#f85149; font-weight:bold; }}
</style></head><body><div class="wrap">
  <h1>{logo_html}CodeMate — Test Report</h1>
  <div class="sub">Generated: {e(stamp)} &nbsp;·&nbsp; pytest tests/ -v</div>
  <div class="verdict {vcls}">{verdict}</div>
  <div class="cards">{cards}</div>
  <div class="bar"><div></div></div>
  <table><thead><tr><th>Test</th><th>Status</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <details><summary>Full pytest log</summary>
  <pre>{log_html}</pre></details>
  <div style="text-align:center; color:#8a8fa8; font-size:12px;
              margin-top:32px; padding-bottom:8px;">
    Sebastian Januchowski ⌁ polsoft.ITS™ Group
  </div>
</div></body></html>"""


def _write_report(output: str, rc: int) -> str:
    """Zapisuje raport HTML do katalogu reports/ i zwraca ścieżkę."""
    report_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(report_dir, f"test_report_{stamp}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_build_report_html(output, rc))
    return path


_SPINNER = "|/-\\"
_spinner = {"i": 0, "active": False}


def _spin_report_btn() -> None:
    """Animuje spinner na przycisku Report co ~120 ms."""
    if not _spinner["active"]:
        return
    ch = _SPINNER[_spinner["i"] % len(_SPINNER)]
    _spinner["i"] += 1
    report_btn.config(text=f"{ch}  Report")
    root.after(120, _spin_report_btn)


def _reset_report_btn() -> None:
    _spinner["active"] = False
    report_btn.config(state="normal", text="Report")


def generate_report() -> None:
    """Przycisk Report — generuje raport HTML z testów."""
    _spinner["active"] = True
    report_btn.config(state="disabled")
    _spin_report_btn()
    threading.Thread(target=_report_worker, daemon=True).start()


def _dialog_button(parent: tk.Widget, text: str, cmd,
                   color: str = BG_BTN) -> tk.Button:
    """Przycisk w stylu launchera (hover + flat)."""
    b = tk.Button(parent, text=text, font=FONT, bg=color, fg=FG_TEXT,
                  relief="flat", padx=14, pady=7, cursor="hand2", bd=0,
                  activebackground=BG_BTN_HOVER, activeforeground=FG_TEXT,
                  command=cmd)
    b.bind("<Enter>", lambda e, w=b: w.config(bg=BG_BTN_HOVER))
    b.bind("<Leave>", lambda e, w=b: w.config(bg=color))
    return b


def show_report_dialog(path: str | None = None,
                       error: str | None = None) -> None:
    """Stylizowane okno potwierdzenia wygenerowania raportu."""
    ok = error is None
    win = tk.Toplevel(root)
    win.title("Test report — OK" if ok else "Test report — Error")
    win.configure(bg=BG_DARK)
    win.resizable(False, False)
    win.overrideredirect(True)          # okno bez titlebara
    win.attributes("-topmost", True)    # na wierzchu — okno informacyjne
    win.bind("<Escape>", lambda e: win.destroy())

    # ── nagłówek ──
    head = tk.Frame(win, bg=BG_PANEL, padx=20, pady=14)
    head.pack(fill="x")
    tk.Label(head, text=("◈  Report ready" if ok else "✕  Report failed"),
             font=("Consolas", 14, "bold"), bg=BG_PANEL,
             fg=ACCENT if ok else "#cf222e").pack(anchor="w")
    tk.Label(head, text=("HTML report generated successfully" if ok
                         else "Could not generate the report"),
             font=("Consolas", 9), bg=BG_PANEL, fg=FG_GRAY).pack(
                 anchor="w", pady=(2, 0))

    # ── treść ──
    body = tk.Frame(win, bg=BG_DARK, padx=20, pady=14)
    body.pack(fill="both")

    if ok:
        tk.Label(body, text="Raport gotowy:", font=("Consolas", 10, "bold"),
                 bg=BG_DARK, fg=FG_TEXT).pack(anchor="w")
        tk.Label(body, text=path, font=("Consolas", 9), bg=BG_DARK,
                 fg=FG_GRAY, wraplength=460, justify="left").pack(
                     anchor="w", pady=(2, 12))
    else:
        tk.Label(body, text=str(error), font=("Consolas", 9), bg=BG_DARK,
                 fg="#cf222e", wraplength=460, justify="left").pack(
                     anchor="w", pady=(0, 12))

    # ── przyciski ──
    btns = tk.Frame(body, bg=BG_DARK)
    btns.pack(fill="x")
    if ok:
        b = _dialog_button(btns, "🌐  Open report",
                           lambda: os.startfile(path))
        b.pack(side="left", expand=True, fill="x", padx=(0, 6))
    _dialog_button(btns, "✕  Close", win.destroy).pack(
        side="left", expand=True, fill="x",
        padx=(6, 0) if ok else 0)

    _make_draggable(win)

    # wyśrodkowanie względem głównego okna
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = root.winfo_rootx() + (root.winfo_width() - w) // 2
    y = root.winfo_rooty() + (root.winfo_height() - h) // 2
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def _report_worker() -> None:
    """Wątek: uruchamia pytest, zapisuje raport i pokazuje podsumowanie."""
    try:
        proc = subprocess.run(
            [python(), "-X", "utf8", "-m", "pytest", "tests/",
             "-q", "--no-cov", "--rootdir=.", "-v", "--tb=line"],
            cwd=APP_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        output = (proc.stdout or "") + (proc.stderr or "")
        path = _write_report(output, proc.returncode)
        root.after(0, lambda p=path: show_report_dialog(path=p))
    except Exception as err:
        root.after(0, lambda e=err: show_report_dialog(error=str(e)))
    finally:
        root.after(0, _reset_report_btn)


def show_about() -> None:
    """Okno About w stylu CodeMate."""
    win = tk.Toplevel(root)
    win.title("About CodeMate")
    win.configure(bg=BG_DARK)
    win.resizable(False, False)
    win.overrideredirect(True)          # okno bez titlebara
    win.bind("<Escape>", lambda e: win.destroy())

    # ── nagłówek ──
    head = tk.Frame(win, bg=BG_PANEL, padx=24, pady=16)
    head.pack(fill="x")
    tk.Label(head, text="◈  CodeMate", font=("Consolas", 18, "bold"),
             bg=BG_PANEL, fg=ACCENT).pack(anchor="w")
    tk.Label(head, text="Script Database — Launcher", font=("Consolas", 10),
             bg=BG_PANEL, fg=FG_GRAY).pack(anchor="w", pady=(2, 0))

    # ── treść ──
    body = tk.Frame(win, bg=BG_DARK, padx=24, pady=16)
    body.pack(fill="both")

    for key, val in (("Version", "4.0"),
                     ("Platform", "Python 3 / Tkinter"),
                     ("Encoding", "UTF-8")):
        row = tk.Frame(body, bg=BG_DARK)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=key, font=("Consolas", 10), bg=BG_DARK,
                 fg=FG_GRAY, width=9, anchor="w").pack(side="left")
        tk.Label(row, text=val, font=("Consolas", 10), bg=BG_DARK,
                 fg=FG_TEXT, anchor="w").pack(side="left")

    tk.Frame(body, bg=BG_PANEL, height=1).pack(fill="x", pady=14)

    tk.Label(body, text="Author:   Sebastian Januchowski",
             font=("Consolas", 10), bg=BG_DARK, fg=FG_TEXT).pack(anchor="w")
    tk.Label(body, text="Company:  polsoft.ITS™ Group",
             font=("Consolas", 10), bg=BG_DARK, fg=FG_GRAY).pack(anchor="w",
                                                              pady=(2, 12))

    btn = tk.Button(body, text="✕  Close", font=FONT, bg=BG_BTN, fg=FG_TEXT,
                    relief="flat", padx=18, pady=8, cursor="hand2", bd=0,
                    activebackground=BG_BTN_HOVER, activeforeground=FG_TEXT,
                    command=win.destroy)
    btn.pack(fill="x")
    btn.bind("<Enter>", lambda e: btn.config(bg=BG_BTN_HOVER))
    btn.bind("<Leave>", lambda e: btn.config(bg=BG_BTN))

    _make_draggable(win)

    # wyśrodkowanie względem głównego okna
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = root.winfo_rootx() + (root.winfo_width() - w) // 2
    y = root.winfo_rooty() + (root.winfo_height() - h) // 2
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.lift()


root = tk.Tk()
root.title("CodeMate Launcher")
root.configure(bg=BG_DARK)
root.resizable(False, False)
root.overrideredirect(True)          # okno bez titlebara

header = tk.Frame(root, bg=BG_PANEL, pady=10)
header.pack(fill="x")

try:
    logo_img = tk.PhotoImage(file=LOGO_PATH)
    logo_img = logo_img.subsample(5)        # 340 px → ~68 px
    header_logo = tk.Label(header, image=logo_img, bg=BG_PANEL)
    header_logo.pack()
except tk.TclError:
    header_logo = None                      # brak pliku — bez logo

header_title = tk.Label(header, text="CodeMate",
                        font=("Consolas", 16, "bold"),
                        bg=BG_PANEL, fg=ACCENT)
header_title.pack()
header_sub = tk.Label(header, text="Launcher", font=("Consolas", 9),
                      bg=BG_PANEL, fg=FG_GRAY)
header_sub.pack()

btn_frame = tk.Frame(root, bg=BG_DARK, padx=20, pady=16)
btn_frame.pack(fill="both", expand=True)


# ── Ikonki przycisków ─────────────────────────────────────────────────────────
button_icons = {}
for _name in ("run", "test", "report", "stats", "about", "quit"):
    _p = os.path.join(ICON_DIR, _name + ".png")
    if os.path.isfile(_p):
        try:
            button_icons[_name] = tk.PhotoImage(file=_p)
        except tk.TclError:
            pass


def make_button(text: str, cmd, color=BG_BTN, padx=0,
                icon: str | None = None) -> None:
    kw = {"image": button_icons[icon], "compound": "left"} \
        if icon in button_icons else {}
    b = tk.Button(btn_frame, text=text, font=FONT, bg=color, fg=FG_TEXT,
                  relief="flat", padx=14, pady=8, cursor="hand2", bd=0,
                  anchor="w",
                  activebackground=BG_BTN_HOVER, activeforeground=FG_TEXT,
                  command=cmd, **kw)
    b.pack(fill="x", pady=4, padx=padx)
    b.bind("<Enter>", lambda e, w=b: w.config(bg=BG_BTN_HOVER))
    b.bind("<Leave>", lambda e, w=b: w.config(bg=color))
    return b


make_button("Run", run_app, ACCENT, icon="run")
make_button("Test", run_tests, icon="test")
report_btn = make_button("Report", generate_report, icon="report")
make_button("Stats", show_stats, icon="stats")
make_button("About", show_about, icon="about")
make_button("Quit", root.destroy, icon="quit")

footer = tk.Label(root, text="polsoft.ITS™ Group", font=("Consolas", 8),
                  bg=BG_DARK, fg=FG_GRAY, pady=6)
footer.pack(fill="x")


# ── Przeciąganie okien (brak titlebara) ───────────────────────────────────────
def _drag_start(event: tk.Event) -> None:
    top = event.widget.winfo_toplevel()
    top._drag_x = event.x_root - top.winfo_x()
    top._drag_y = event.y_root - top.winfo_y()


def _drag_move(event: tk.Event) -> None:
    top = event.widget.winfo_toplevel()
    top.geometry(f"+{event.x_root - top._drag_x}"
                 f"+{event.y_root - top._drag_y}")


def _make_draggable(widget: tk.Widget) -> None:
    """Binduje przeciąganie okna na widget i jego dzieci (bez przycisków)."""
    def bind_one(w: tk.Widget) -> None:
        w.bind("<Button-1>", _drag_start)
        w.bind("<B1-Motion>", _drag_move)

    bind_one(widget)
    for ch in widget.winfo_children():
        if not isinstance(ch, tk.Button):
            bind_one(ch)
            for g in ch.winfo_children():
                if not isinstance(g, tk.Button):
                    bind_one(g)


for _w in (header, header_logo, header_title, header_sub, btn_frame, footer):
    if _w is None:
        continue
    _w.bind("<Button-1>", _drag_start)
    _w.bind("<B1-Motion>", _drag_move)

# wyśrodkowanie okna
root.update_idletasks()
w, h = root.winfo_width(), root.winfo_height()
root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}"
              f"+{(root.winfo_screenheight() - h) // 2}")

_apply_glass()

root.mainloop()
