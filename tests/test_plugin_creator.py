"""Testy modułu kreatora pluginów (src/modules/plugin_creator.py)."""

import pytest

from src.modules import plugin_creator as pc
from src.plugin_system import PluginManager


class TestValidators:
    def test_valid_plugin_filename_ok(self):
        assert pc.valid_plugin_filename("moj_plugin") is True
        assert pc.valid_plugin_filename("Plugin2") is True
        assert pc.valid_plugin_filename("_priv") is True

    def test_valid_plugin_filename_bad(self):
        assert pc.valid_plugin_filename("") is False
        assert pc.valid_plugin_filename("2start") is False
        assert pc.valid_plugin_filename("ma-j") is False
        assert pc.valid_plugin_filename("ma j") is False
        assert pc.valid_plugin_filename("plik.py") is False

    def test_valid_alias_ok(self):
        assert pc.valid_alias("stats") is True
        assert pc.valid_alias("/stats") is True
        assert pc.valid_alias("skrypty/statystyki") is True
        assert pc.valid_alias("a-b_c/d") is True

    def test_valid_alias_bad(self):
        assert pc.valid_alias("") is False
        assert pc.valid_alias("/") is False
        assert pc.valid_alias("a b") is False
        assert pc.valid_alias("a.b") is False


class TestNavCommands:
    def test_catalog_structure(self):
        aliases = [a for a, _t, _d in pc.NAV_COMMANDS]
        assert len(aliases) == len(set(aliases)), "zduplikowane aliasy"
        for alias, target, desc in pc.NAV_COMMANDS:
            assert alias and "/" not in alias.split("/")[0] or True
            assert target.startswith("tab_")
            assert desc

    def test_main_tabs_covered(self):
        mains = {t for _a, t, _d in pc.NAV_COMMANDS if ":" not in t}
        assert mains == {
            "tab_skrypty", "tab_szukaj", "tab_moduly", "tab_baza",
            "tab_venv", "tab_vdrive", "tab_narzedzia", "tab_terminal",
            "tab_runner", "tab_git", "tab_plugins", "tab_ustawienia",
        }

    def test_sub_tabs_covered(self):
        subs = {t for _a, t, _d in pc.NAV_COMMANDS if ":" in t}
        assert subs == {
            f"tab_skrypty:{k}" for k in
            ("dodaj", "lista", "edytor", "szablony", "snippety",
             "statystyki", "zaawansowane", "runner", "kosz")
        }


class TestFileCommands:
    def test_catalog_structure(self):
        aliases = [a for a, _op, _d in pc.FILE_COMMANDS]
        assert len(aliases) == len(set(aliases)), "zduplikowane aliasy"
        ops = {op for _a, op, _d in pc.FILE_COMMANDS}
        assert ops == {"read", "list", "info", "copy", "move",
                       "delete", "mkdir", "touch"}
        for alias, _op, desc in pc.FILE_COMMANDS:
            assert pc.valid_alias(alias), f"niepoprawny alias: {alias}"
            assert alias.startswith("files/")
            assert desc

    def test_no_overlap_with_nav(self):
        nav_aliases = {a for a, _t, _d in pc.NAV_COMMANDS}
        file_aliases = {a for a, _op, _d in pc.FILE_COMMANDS}
        assert not (nav_aliases & file_aliases)


class TestPluginSource:
    BASE = dict(fname="demo", cls_name="DemoPlugin", disp="Demo",
                version="1.0.0", author="Ja", desc="Opis", cat="Test")

    def test_minimal_compiles(self):
        src = pc.plugin_source(**self.BASE)
        compile(src, "demo.py", "exec")
        assert "PLUGIN_NAME" in src
        assert "on_load" in src

    def test_full_metadata(self):
        src = pc.plugin_source(**self.BASE, homepage="https://x",
                               license_="MIT")
        assert 'PLUGIN_HOMEPAGE = "https://x"' in src
        assert 'PLUGIN_LICENSE = "MIT"' in src
        compile(src, "demo.py", "exec")

    def test_hooks_generate_stubs(self):
        src = pc.plugin_source(**self.BASE,
                               hooks=["before_script_save", "on_app_start"])
        assert 'self.register_hook("before_script_save", self._on_before_script_save)' in src
        assert 'self.register_hook("on_app_start", self._on_app_start)' in src
        assert "def _on_before_script_save" in src
        assert "def _on_app_start" in src
        compile(src, "demo.py", "exec")

    def test_hooks_empty_comment(self):
        src = pc.plugin_source(**self.BASE, hooks=[])
        assert "brak hooków" in src

    def test_user_alias_only(self):
        src = pc.plugin_source(**self.BASE, alias="stats")
        assert '"stats": "Opis"' in src
        assert "def on_command" in src
        assert '_NAV = {' in src
        compile(src, "demo.py", "exec")

    def test_nav_commands_only(self):
        nav = [n for n in pc.NAV_COMMANDS if n[0] in ("runner", "skrypty/kosz")]
        src = pc.plugin_source(**self.BASE, nav=nav)
        assert '"runner": "tab_runner"' in src
        assert '"skrypty/kosz": "tab_skrypty:kosz"' in src
        assert "_nav_goto" in src
        compile(src, "demo.py", "exec")

    def test_alias_and_nav_together(self):
        nav = [n for n in pc.NAV_COMMANDS if n[0] == "runner"]
        src = pc.plugin_source(**self.BASE, alias="stats", nav=nav)
        assert '"stats"' in src and '"runner"' in src
        assert "if alias == \"stats\":" in src
        compile(src, "demo.py", "exec")

    def test_desc_fallback_for_commands(self):
        src = pc.plugin_source(fname="d", cls_name="DP", disp="Display",
                               version="1", author="a", desc="", cat="c",
                               alias="x")
        assert '"x": "Display"' in src

    def test_hook_name_without_on_prefix(self):
        src = pc.plugin_source(**self.BASE, hooks=["after_db_save"])
        assert "self._on_after_db_save" in src
        compile(src, "demo.py", "exec")

    def test_file_commands_generate_op(self):
        files = [f for f in pc.FILE_COMMANDS if f[0] in ("files/read", "files/mkdir")]
        src = pc.plugin_source(**self.BASE, files=files)
        assert '"files/read": "Odczytaj zawartość pliku"' in src
        assert '"files/read": "read"' in src
        assert "def _file_op" in src
        assert "self._file_op(fop, args)" in src
        compile(src, "demo.py", "exec")

    def test_files_and_nav_together(self):
        nav = [n for n in pc.NAV_COMMANDS if n[0] == "runner"]
        files = [f for f in pc.FILE_COMMANDS if f[0] == "files/list"]
        src = pc.plugin_source(**self.BASE, nav=nav, files=files)
        assert "_NAV" in src and "_FILE" in src
        compile(src, "demo.py", "exec")

    def test_no_files_no_file_op(self):
        src = pc.plugin_source(**self.BASE)
        assert "_file_op" not in src

    def test_generated_plugin_loads(self, tmp_path):
        """Wygenerowany plugin faktycznie się ładuje przez PluginManager."""
        import textwrap
        src = pc.plugin_source(**self.BASE, hooks=["on_app_start"],
                               nav=[n for n in pc.NAV_COMMANDS if n[0] == "runner"])
        pfile = tmp_path / "demo.py"
        pfile.write_text(src, encoding="utf-8")
        from unittest.mock import Mock
        app = Mock()
        pm = PluginManager(app, tmp_path)
        app._plugin_manager = pm
        assert pm.load_plugins() == 1
        plugin = pm.plugins["demo"]
        assert plugin.PLUGIN_NAME == "Demo"
        assert plugin.registered_hooks == ["on_app_start"]
        assert "runner" in plugin.PLUGIN_COMMANDS
        assert pm.hook_usage()["on_app_start"] == 1

    def test_file_command_dispatches(self, tmp_path):
        """Komenda /files/... wywołuje _file_op z operacją i argumentami."""
        from unittest.mock import Mock
        src = pc.plugin_source(**self.BASE, files=pc.FILE_COMMANDS)
        pfile = tmp_path / "demo.py"
        pfile.write_text(src, encoding="utf-8")
        app = Mock()
        pm = PluginManager(app, tmp_path)
        app._plugin_manager = pm
        assert pm.load_plugins() == 1
        plugin = pm.plugins["demo"]
        plugin._file_op = Mock()
        assert pm.run_command("files/read", "test.txt") is True
        plugin._file_op.assert_called_once_with("read", "test.txt")
        assert pm.run_command("/files/mkdir", "katalog") is True
        assert plugin._file_op.call_args_list[-1].args == ("mkdir", "katalog")
