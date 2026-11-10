# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł:   src/modules/plugin_creator.py
# Opis:    Kreator pluginów CodeMate — generowanie szablonów, walidacja,
#          katalog komend nawigacyjnych
# ──────────────────────────────────────────────────────────────────────────────
"""Kreator pluginów — logika wydzielona z kodu głównego.

Moduł dostarcza funkcje używane przez zakładkę Pluginy
(``_plugins_new`` w ``baza_skryptow.py``):

- :func:`valid_plugin_filename` / :func:`valid_alias` — walidacja pól formularza,
- :data:`NAV_COMMANDS` — katalog aliasów nawigacyjnych (``/runner``,
  ``/skrypty/statystyki`` …) mapowanych na ``app._nav_goto``,
- :func:`plugin_source` — generator kodu źródłowego pluginu
  (metadane, hooki, komendy).
"""

from typing import Iterable, List, Sequence, Tuple

from src.plugin_system import PluginManager

# ── Walidacja ─────────────────────────────────────────────────────────────────


def valid_plugin_filename(name: str) -> bool:
    """Zwraca True gdy ``name`` jest bezpieczną nazwą pliku pluginu.

    Dozwolone: litery, cyfry i ``_``; nie może zaczynać się od cyfry.
    """
    return (bool(name)
            and name.replace("_", "").isalnum()
            and not name[0].isdigit())


def valid_alias(alias: str) -> bool:
    """Zwraca True gdy ``alias`` jest poprawnym aliasem komendy.

    Dozwolone: litery, cyfry, ``_``, ``-`` i ``/`` (ścieżki
    hierarchiczne); opcjonalny prefiks ``/`` jest ignorowany.
    """
    a = alias.lstrip("/")
    return bool(a) and a.replace("/", "").replace("_", "").replace("-", "").isalnum()


# ── Katalog komend nawigacyjnych ──────────────────────────────────────────────
# (alias, target _nav_goto, opis po polsku)
NAV_COMMANDS: Tuple[Tuple[str, str, str], ...] = (
    ("skrypty",          "tab_skrypty",             "Zakładka: Skrypty"),
    ("szukaj",           "tab_szukaj",              "Zakładka: Szukaj"),
    ("moduly",           "tab_moduly",              "Zakładka: Moduły"),
    ("baza",             "tab_baza",                "Zakładka: Baza danych"),
    ("venv",             "tab_venv",                "Zakładka: Venv"),
    ("vdrive",           "tab_vdrive",              "Zakładka: VDrive"),
    ("narzedzia",        "tab_narzedzia",           "Zakładka: Narzędzia"),
    ("terminal",         "tab_terminal",            "Zakładka: Terminal"),
    ("runner",           "tab_runner",              "Zakładka: Runner"),
    ("git",              "tab_git",                 "Zakładka: Git"),
    ("pluginy",          "tab_plugins",             "Zakładka: Pluginy"),
    ("ustawienia",       "tab_ustawienia",          "Zakładka: Ustawienia"),
    ("skrypty/nowy",     "tab_skrypty:dodaj",       "Skrypty: Nowy skrypt"),
    ("skrypty/lista",    "tab_skrypty:lista",       "Skrypty: Lista skryptów"),
    ("skrypty/edytor",   "tab_skrypty:edytor",      "Skrypty: Edytor"),
    ("skrypty/szablony", "tab_skrypty:szablony",    "Skrypty: Szablony"),
    ("skrypty/snippety", "tab_skrypty:snippety",    "Skrypty: Snippety"),
    ("skrypty/statystyki", "tab_skrypty:statystyki","Skrypty: Statystyki"),
    ("skrypty/zaawansowane", "tab_skrypty:zaawansowane", "Skrypty: Zaawansowane"),
    ("skrypty/runner",   "tab_skrypty:runner",      "Skrypty: Runner"),
    ("skrypty/kosz",     "tab_skrypty:kosz",        "Skrypty: Kosz"),
)


# ── Katalog komend plikowych ─────────────────────────────────────────────────
# (alias, operacja, opis po polsku) — aliasy /files/... obsługiwane w pluginie
# przez wygenerowaną metodę ``_file_op``; działają też z terminala po /
FILE_COMMANDS: Tuple[Tuple[str, str, str], ...] = (
    ("files/read",   "read",   "Odczytaj zawartość pliku"),
    ("files/list",   "list",   "Lista plików w katalogu"),
    ("files/info",   "info",   "Informacje o pliku (rozmiar, data)"),
    ("files/copy",   "copy",   "Kopiuj plik lub katalog"),
    ("files/move",   "move",   "Przenieś plik lub katalog"),
    ("files/delete", "delete", "Usuń plik lub katalog"),
    ("files/mkdir",  "mkdir",  "Utwórz katalog"),
    ("files/touch",  "touch",  "Utwórz pusty plik"),
)


# ── Generator kodu pluginu ────────────────────────────────────────────────────

# Metoda ``_file_op`` doklejana do generowanego pluginu, gdy wybrano komendy
# z FILE_COMMANDS. Ścieżki są rozwiązywane względem katalogu terminala
# (``app._terminal_widget.cwd``), a wyniki pokazywane w oknach messagebox.
_FILE_OP_METHOD = '''    def _file_op(self, op, args):
        """Wykonuje operację plikową — args to ścieżki."""
        import datetime
        import os
        import shutil
        from tkinter import messagebox

        base = getattr(getattr(self.app, "_terminal_widget", None),
                       "cwd", None) or os.getcwd()

        def _p(v):
            return v if os.path.isabs(v) else os.path.join(base, v)

        parts = args.split()
        try:
            if op == "read":
                if not parts:
                    raise ValueError("Użycie: /files/read PLIK [PLIK ...]")
                out = []
                for v in parts:
                    p = _p(v)
                    if not os.path.isfile(p):
                        raise FileNotFoundError(p)
                    with open(p, "r", encoding="utf-8",
                              errors="replace") as fh:
                        out.append(fh.read())
                messagebox.showinfo(
                    self.PLUGIN_NAME, "\\n".join(out)[:4000] or "(pusty plik)",
                    parent=self.app)
            elif op == "list":
                if not parts:
                    parts = ["."]
                lines = []
                for v in parts:
                    p = _p(v)
                    if not os.path.isdir(p):
                        raise NotADirectoryError(p)
                    lines.append(p)
                    for name in sorted(os.listdir(p)):
                        full = os.path.join(p, name)
                        tag = "  [DIR]  " if os.path.isdir(full) else "         "
                        lines.append(tag + name)
                messagebox.showinfo(
                    self.PLUGIN_NAME, "\\n".join(lines)[:4000], parent=self.app)
            elif op == "info":
                if len(parts) != 1:
                    raise ValueError("Użycie: /files/info PLIK")
                p = _p(parts[0])
                if not os.path.exists(p):
                    raise FileNotFoundError(p)
                st = os.stat(p)
                stamp = datetime.datetime.fromtimestamp(
                    st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                kind = "katalog" if os.path.isdir(p) else "plik"
                messagebox.showinfo(
                    self.PLUGIN_NAME,
                    f"Ścieżka: {p}\\nTyp: {kind}\\nRozmiar: {st.st_size} B\\n"
                    f"Modyfikacja: {stamp}", parent=self.app)
            elif op == "copy":
                if len(parts) != 2:
                    raise ValueError("Użycie: /files/copy ŹRÓDŁO CEL")
                src, dst = _p(parts[0]), _p(parts[1])
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
                messagebox.showinfo(
                    self.PLUGIN_NAME, f"Skopiowano: {dst}", parent=self.app)
            elif op == "move":
                if len(parts) != 2:
                    raise ValueError("Użycie: /files/move ŹRÓDŁO CEL")
                dst = shutil.move(_p(parts[0]), _p(parts[1]))
                messagebox.showinfo(
                    self.PLUGIN_NAME, f"Przeniesiono: {dst}", parent=self.app)
            elif op == "delete":
                if not parts:
                    raise ValueError("Użycie: /files/delete PLIK [PLIK ...]")
                listing = "\\n".join(_p(v) for v in parts)
                if not messagebox.askyesno(
                        self.PLUGIN_NAME, f"Usunąć?\\n{listing}",
                        parent=self.app):
                    return
                for v in parts:
                    p = _p(v)
                    if os.path.isdir(p) and not os.path.islink(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
                messagebox.showinfo(
                    self.PLUGIN_NAME, "Usunięto.", parent=self.app)
            elif op == "mkdir":
                if not parts:
                    raise ValueError("Użycie: /files/mkdir KATALOG [KATALOG ...]")
                for v in parts:
                    os.makedirs(_p(v), exist_ok=True)
                messagebox.showinfo(
                    self.PLUGIN_NAME, "Katalog(i) utworzony(e).", parent=self.app)
            elif op == "touch":
                if not parts:
                    raise ValueError("Użycie: /files/touch PLIK [PLIK ...]")
                for v in parts:
                    p = _p(v)
                    with open(p, "a", encoding="utf-8"):
                        pass
                    os.utime(p, None)
                messagebox.showinfo(
                    self.PLUGIN_NAME, "Plik(i) utworzony(e).", parent=self.app)
        except Exception as exc:
            messagebox.showerror(self.PLUGIN_NAME, str(exc), parent=self.app)'''


def plugin_source(fname: str, cls_name: str, disp: str, version: str,
                  author: str, desc: str, cat: str,
                  homepage: str = "", license_: str = "", alias: str = "",
                  hooks: Iterable[str] = (), nav: Iterable[Tuple[str, str, str]] = (),
                  files: Iterable[Tuple[str, str, str]] = ()
                  ) -> str:
    """Generuje kod źródłowy pluginu z wybranych opcji kreatora.

    Args:
        fname: Nazwa pliku (bez ``.py``).
        cls_name: Nazwa klasy pluginu.
        disp: Wyświetlana nazwa pluginu.
        version: Wersja pluginu.
        author: Autor.
        desc: Opis pluginu.
        cat: Kategoria.
        homepage: Opcjonalna strona domowa.
        license_: Opcjonalna licencja.
        alias: Opcjonalny alias komendy użytkownika (bez ``/``).
        hooks: Wybrane hooki do wygenerowania stubów.
        nav: Wybrane komendy nawigacyjne ``(alias, target, opis)``.
        files: Wybrane komendy plikowe ``(alias, operacja, opis)``.

    Returns:
        str: Kod źródłowy pliku ``.py`` pluginu.
    """
    hooks = list(hooks or [])
    nav = list(nav or [])
    files = list(files or [])

    def _hname(h: str) -> str:
        short = h[3:] if h.startswith("on_") else h
        return f"_on_{short}"

    reg = "\n".join(
        f'        self.register_hook("{h}", self.{_hname(h)})' for h in hooks
    ) or "        # brak hooków — dodaj self.register_hook(...) w on_load"
    stubs = "\n\n".join(
        f'    def {_hname(h)}(self, *args, **kwargs):\n'
        f'        """Hook `{h}` — {PluginManager.HOOKS.get(h, "")}."""\n'
        f'        # TODO: implementacja\n        pass'
        for h in hooks)

    # ── komendy: alias użytkownika + nawigacja + operacje plikowe ───────────
    cmd_entries: List[Tuple[str, str]] = ([(a, d) for a, _t, d in nav]
                                          + [(a, d) for a, _op, d in files])
    if alias:
        cmd_entries.append((alias, desc or disp))

    commands_block = ""
    on_command_block = ""
    file_method_block = ""
    if cmd_entries:
        cmds_dict = ",\n".join(f'        "{a}": "{d}"' for a, d in cmd_entries)
        nav_map = ",\n".join(f'        "{a}": "{t}"' for a, t, _d in nav)
        file_map = ",\n".join(f'        "{a}": "{op}"' for a, op, _d in files)
        nav_dispatch = (
            f'        _NAV = {{\n{nav_map}\n        }}\n'
            f'        target = _NAV.get(alias)\n'
            f'        if target:\n'
            f'            self.app._nav_goto(target)\n'
            f'            return\n')
        file_dispatch = (
            f'        _FILE = {{\n{file_map}\n        }}\n'
            f'        fop = _FILE.get(alias)\n'
            f'        if fop:\n'
            f'            self._file_op(fop, args)\n'
            f'            return\n') if files else ""
        user_branch = ""
        if alias:
            user_branch = (
                f'        if alias == "{alias}":\n'
                f'            # TODO: akcja dla aliasu "{alias}" — args to argumenty komendy\n'
                f'            pass\n            return\n')
        on_command_block = (
            f'\n    def on_command(self, cmd_alias, args=""):\n'
            f'        """Dispatch komend pluginu (aliasy /... )."""\n'
            f'        alias = cmd_alias.lstrip("/")\n'
            f'{nav_dispatch}{file_dispatch}{user_branch}')
        commands_block = (
            f'\n    PLUGIN_COMMANDS = {{\n{cmds_dict}\n    }}\n')
    if files:
        file_method_block = "\n" + _FILE_OP_METHOD

    meta = ""
    if homepage:
        meta += f'    PLUGIN_HOMEPAGE = "{homepage}"\n'
    if license_:
        meta += f'    PLUGIN_LICENSE = "{license_}"\n'

    return f'''\
# ── Metadane ──────────────────────────────────────────────────────────────────
# Plugin: {fname}.py — wygenerowany przez kreator CodeMate
# ──────────────────────────────────────────────────────────────────────────────

from src.plugin_system import BasePlugin


class {cls_name}(BasePlugin):
    """{desc or disp}"""

    PLUGIN_NAME = "{disp}"
    PLUGIN_VERSION = "{version}"
    PLUGIN_AUTHOR = "{author}"
    PLUGIN_DESCRIPTION = "{desc or disp}"
    PLUGIN_CATEGORY = "{cat}"
{meta}{commands_block}{on_command_block}{file_method_block}
    def on_load(self):
        """Rejestruj hooki i inicjalizuj zasoby pluginu."""
{reg}

    def on_unload(self):
        """Wyczyść zasoby i wyrejestruj hooki."""
        pass
{("\n" + stubs) if stubs else ""}
'''
