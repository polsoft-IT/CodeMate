"""
Testy dla systemu pluginów.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.plugin_system import BasePlugin, PluginManager, PluginHook


class TestPluginHook:
    """Testy klasy PluginHook."""

    def test_hook_creation(self):
        """Test tworzenia hooka."""
        hook = PluginHook("test_hook", "Test description")

        assert hook.name == "test_hook"
        assert hook.description == "Test description"
        assert len(hook._callbacks) == 0

    def test_hook_register(self):
        """Test rejestrowania callbacka."""
        hook = PluginHook("test_hook")
        callback = Mock()

        hook.register(callback)

        assert len(hook._callbacks) == 1

    def test_hook_trigger(self):
        """Test wywoływania hooka."""
        hook = PluginHook("test_hook")
        callback = Mock()

        hook.register(callback)
        hook.trigger("arg1", kwarg="value")

        callback.assert_called_once_with("arg1", kwarg="value")

    def test_hook_trigger_multiple_callbacks(self):
        """Test wywoływania hooka z wieloma callbackami."""
        hook = PluginHook("test_hook")
        callback1 = Mock()
        callback2 = Mock()

        hook.register(callback1)
        hook.register(callback2)
        hook.trigger()

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_hook_clear(self):
        """Test czyszczenia callbacków."""
        hook = PluginHook("test_hook")
        hook.register(Mock())

        hook.clear()

        assert len(hook._callbacks) == 0

    def test_hook_trigger_callback_exception(self, caplog):
        """Test że wyjątek w callbacku nie przerywa pozostałych callbacków."""
        import logging

        hook = PluginHook("test_hook")
        failing = Mock(side_effect=RuntimeError("boom"))
        working = Mock()
        hook.register(failing)
        hook.register(working)

        with caplog.at_level(logging.ERROR):
            hook.trigger()

        working.assert_called_once()
        assert "callback failed" in caplog.text


class DummyPlugin(BasePlugin):
    """Przykładowy plugin do testów."""

    PLUGIN_NAME = "Dummy Plugin"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "Test Author"
    PLUGIN_DESCRIPTION = "Test plugin"
    PLUGIN_CATEGORY = "Test"

    def on_load(self):
        self.loaded = True

    def on_unload(self):
        self.loaded = False


class TestBasePlugin:
    """Testy klasy BasePlugin."""

    def test_plugin_initialization(self):
        """Test inicjalizacji pluginu."""
        app = Mock()
        plugin = DummyPlugin(app)

        assert plugin.app == app
        assert plugin.enabled is True
        assert plugin._hooks_registered is False

    def test_plugin_on_load(self):
        """Test metody on_load."""
        app = Mock()
        plugin = DummyPlugin(app)

        plugin.on_load()

        assert plugin.loaded is True

    def test_plugin_on_unload(self):
        """Test metody on_unload."""
        app = Mock()
        plugin = DummyPlugin(app)
        plugin.on_load()

        plugin.on_unload()

        assert plugin.loaded is False

    def test_plugin_on_enable(self):
        """Test metody on_enable."""
        app = Mock()
        plugin = DummyPlugin(app)
        plugin.enabled = False

        plugin.on_enable()

        assert plugin.enabled is True

    def test_plugin_on_disable(self):
        """Test metody on_disable."""
        app = Mock()
        plugin = DummyPlugin(app)

        plugin.on_disable()

        assert plugin.enabled is False

    def test_plugin_get_info(self):
        """Test pobierania informacji o pluginie."""
        app = Mock()
        plugin = DummyPlugin(app)

        info = plugin.get_info()

        assert info["name"] == "Dummy Plugin"
        assert info["version"] == "1.0.0"
        assert info["author"] == "Test Author"
        assert info["description"] == "Test plugin"
        assert info["category"] == "Test"
        assert info["enabled"] == "True"

    def test_plugin_register_hook(self):
        """Test rejestrowania hooka."""
        app = Mock()
        app._plugin_manager = Mock()
        plugin = DummyPlugin(app)

        callback = Mock()
        plugin.register_hook("test_hook", callback)

        app._plugin_manager.register_hook.assert_called_once_with("test_hook", callback)

    def test_plugin_trigger_hook(self):
        """Test wywoływania hooka."""
        app = Mock()
        app._plugin_manager = Mock()
        plugin = DummyPlugin(app)

        plugin.trigger_hook("test_hook", "arg1")

        app._plugin_manager.trigger_hook.assert_called_once_with("test_hook", "arg1")

    def test_plugin_hook_methods_without_plugin_manager(self):
        """Test rejestracji i wywołania hooka gdy aplikacja nie ma plugin managera."""
        app = Mock(spec=[])  # brak atrybutu _plugin_manager
        plugin = DummyPlugin(app)
        callback = Mock()

        plugin.register_hook("test_hook", callback)
        plugin.trigger_hook("test_hook", "arg1")

        callback.assert_not_called()

    def test_base_plugin_abstract_method_bodies(self):
        """Test domyślnych (abstrakcyjnych) implementacji on_load/on_unload."""
        app = Mock()
        plugin = DummyPlugin(app)

        # Wywołanie bezpośrednie bazowych implementacji (pomija override w DummyPlugin)
        BasePlugin.on_load(plugin)
        BasePlugin.on_unload(plugin)


class TestPluginManager:
    """Testy klasy PluginManager."""

    @pytest.fixture
    def temp_plugins_dir(self, tmp_path):
        """Fixture dostarczający tymczasowy katalog pluginów."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        return plugins_dir

    @pytest.fixture
    def plugin_manager(self, temp_plugins_dir):
        """Fixture dostarczający instancję PluginManager."""
        app = Mock()
        return PluginManager(app, temp_plugins_dir)

    def test_plugin_manager_initialization(self, plugin_manager, temp_plugins_dir):
        """Test inicjalizacji PluginManager."""
        assert plugin_manager.app is not None
        assert plugin_manager.plugins_dir == temp_plugins_dir
        assert len(plugin_manager.plugins) == 0
        assert len(plugin_manager.hooks) == len(PluginManager.HOOKS)

    def test_plugin_manager_hooks_initialization(self, plugin_manager):
        """Test inicjalizacji hooków."""
        for hook_name in PluginManager.HOOKS:
            assert hook_name in plugin_manager.hooks
            assert isinstance(plugin_manager.hooks[hook_name], PluginHook)

    def test_plugin_manager_register_hook(self, plugin_manager):
        """Test rejestrowania hooka."""
        callback = Mock()

        plugin_manager.register_hook("before_script_save", callback)

        assert len(plugin_manager.hooks["before_script_save"]._callbacks) == 1

    def test_plugin_manager_trigger_hook(self, plugin_manager):
        """Test wywoływania hooka."""
        callback = Mock()
        plugin_manager.register_hook("before_script_save", callback)

        plugin_manager.trigger_hook("before_script_save", "arg1")

        callback.assert_called_once_with("arg1")

    def test_plugin_manager_trigger_unknown_hook(self, plugin_manager):
        """Test wywoływania nieistniejącego hooka."""
        # Nie powinno rzucić wyjątku
        plugin_manager.trigger_hook("unknown_hook")

    def test_plugin_manager_register_unknown_hook(self, plugin_manager):
        """Test rejestrowania callbacka dla nieistniejącego hooka."""
        callback = Mock()

        plugin_manager.register_hook("unknown_hook", callback)

        # Callback nie powinien być zarejestrowany
        assert len(plugin_manager.hooks.get("unknown_hook", PluginHook("dummy"))._callbacks) == 0

    def test_plugin_manager_enable_plugin(self, plugin_manager):
        """Test włączania pluginu."""
        plugin = DummyPlugin(plugin_manager.app)
        plugin_manager.plugins["dummy"] = plugin
        plugin.enabled = False

        result = plugin_manager.enable_plugin("dummy")

        assert result is True
        assert plugin.enabled is True

    def test_plugin_manager_disable_plugin(self, plugin_manager):
        """Test wyłączania pluginu."""
        plugin = DummyPlugin(plugin_manager.app)
        plugin_manager.plugins["dummy"] = plugin

        result = plugin_manager.disable_plugin("dummy")

        assert result is True
        assert plugin.enabled is False

    def test_plugin_manager_unload_plugin(self, plugin_manager):
        """Test wyładowania pluginu."""
        plugin = DummyPlugin(plugin_manager.app)
        plugin.on_load()
        plugin_manager.plugins["dummy"] = plugin

        result = plugin_manager.unload_plugin("dummy")

        assert result is True
        assert "dummy" not in plugin_manager.plugins

    def test_plugin_manager_get_plugins(self, plugin_manager):
        """Test pobierania listy pluginów."""
        plugin1 = DummyPlugin(plugin_manager.app)
        plugin2 = DummyPlugin(plugin_manager.app)
        plugin2.PLUGIN_NAME = "Second Plugin"

        plugin_manager.plugins["plugin1"] = plugin1
        plugin_manager.plugins["plugin2"] = plugin2

        plugins_info = plugin_manager.get_plugins()

        assert len(plugins_info) == 2
        assert plugins_info[0]["name"] == "Dummy Plugin"
        assert plugins_info[1]["name"] == "Second Plugin"

    def test_plugin_manager_get_hooks(self, plugin_manager):
        """Test pobierania listy hooków."""
        hooks = plugin_manager.get_hooks()

        assert len(hooks) == len(PluginManager.HOOKS)
        assert "before_script_save" in hooks
        assert "after_script_save" in hooks

    # ── load_plugins ──────────────────────────────────────────────────────

    _PLUGIN_SOURCE = '''\
from src.plugin_system import BasePlugin


class FilePlugin(BasePlugin):
    PLUGIN_NAME = "File Plugin"

    def on_load(self):
        self.loaded = True

    def on_unload(self):
        self.loaded = False
'''

    def _write_plugin(self, plugins_dir: Path, filename: str, source: str) -> None:
        (plugins_dir / filename).write_text(source, encoding="utf-8")

    def test_load_plugins_loads_valid_plugin(self, plugin_manager, temp_plugins_dir):
        """Test ładowania poprawnego pliku pluginu."""
        self._write_plugin(temp_plugins_dir, "my_plugin.py", self._PLUGIN_SOURCE)
        self._write_plugin(temp_plugins_dir, "_private.py", self._PLUGIN_SOURCE)
        self._write_plugin(temp_plugins_dir, "empty.py", "X = 1\n")
        self._write_plugin(temp_plugins_dir, "broken.py", "raise RuntimeError('nope')\n")

        count = plugin_manager.load_plugins()

        assert count == 1
        assert "my_plugin" in plugin_manager.plugins
        assert plugin_manager.plugins["my_plugin"].loaded is True
        assert "_private" not in plugin_manager.plugins
        assert "empty" not in plugin_manager.plugins
        assert "broken" not in plugin_manager.plugins

    def test_load_plugins_returns_zero_when_empty(self, plugin_manager):
        """Test ładowania gdy katalog jest pusty."""
        assert plugin_manager.load_plugins() == 0

    def test_load_plugins_spec_none(self, plugin_manager, temp_plugins_dir):
        """Test pomijania pliku gdy nie da się utworzyć spec modułu."""
        self._write_plugin(temp_plugins_dir, "no_spec.py", "X = 1\n")

        with patch("src.plugin_system.importlib.util.spec_from_file_location", return_value=None):
            count = plugin_manager.load_plugins()

        assert count == 0
        assert "no_spec" not in plugin_manager.plugins

    def test_load_plugins_spec_loader_none(self, plugin_manager, temp_plugins_dir):
        """Test pomijania pliku gdy spec nie ma loadera."""
        self._write_plugin(temp_plugins_dir, "no_loader.py", "X = 1\n")
        spec = Mock()
        spec.loader = None

        with patch("src.plugin_system.importlib.util.spec_from_file_location", return_value=spec):
            count = plugin_manager.load_plugins()

        assert count == 0
        assert "no_loader" not in plugin_manager.plugins

    def test_load_plugins_plugin_on_load_raises(self, plugin_manager, temp_plugins_dir, caplog):
        """Test że błąd w on_load pluginu jest łapany i logowany."""
        source = self._PLUGIN_SOURCE.replace(
            "self.loaded = True", "raise RuntimeError('load fail')"
        )
        self._write_plugin(temp_plugins_dir, "bad_load.py", source)

        import logging

        with caplog.at_level(logging.ERROR):
            count = plugin_manager.load_plugins()

        assert count == 0
        assert "bad_load" not in plugin_manager.plugins
        assert "Failed to load plugin" in caplog.text

    # ── unload / enable / disable — ścieżki błędów ────────────────────────

    def test_unload_plugin_not_found(self, plugin_manager):
        assert plugin_manager.unload_plugin("missing") is False

    def test_enable_plugin_not_found(self, plugin_manager):
        assert plugin_manager.enable_plugin("missing") is False

    def test_disable_plugin_not_found(self, plugin_manager):
        assert plugin_manager.disable_plugin("missing") is False

    def test_unload_plugin_on_unload_raises(self, plugin_manager, caplog):
        """Test że wyjątek w on_unload jest łapany."""

        class BadUnloadPlugin(DummyPlugin):
            def on_unload(self):
                raise RuntimeError("unload fail")

        plugin_manager.plugins["bad"] = BadUnloadPlugin(plugin_manager.app)

        import logging

        with caplog.at_level(logging.ERROR):
            result = plugin_manager.unload_plugin("bad")

        assert result is False
        assert "bad" in plugin_manager.plugins
        assert "Failed to unload plugin" in caplog.text

    def test_enable_plugin_on_enable_raises(self, plugin_manager, caplog):
        """Test że wyjątek w on_enable jest łapany."""

        class BadEnablePlugin(DummyPlugin):
            def on_enable(self):
                raise RuntimeError("enable fail")

        plugin_manager.plugins["bad"] = BadEnablePlugin(plugin_manager.app)

        import logging

        with caplog.at_level(logging.ERROR):
            result = plugin_manager.enable_plugin("bad")

        assert result is False
        assert "Failed to enable plugin" in caplog.text

    def test_disable_plugin_on_disable_raises(self, plugin_manager, caplog):
        """Test że wyjątek w on_disable jest łapany."""

        class BadDisablePlugin(DummyPlugin):
            def on_disable(self):
                raise RuntimeError("disable fail")

        plugin_manager.plugins["bad"] = BadDisablePlugin(plugin_manager.app)

        import logging

        with caplog.at_level(logging.ERROR):
            result = plugin_manager.disable_plugin("bad")

        assert result is False
        assert "Failed to disable plugin" in caplog.text


class TestPluginManagerExtensions:
    """Testy rozszerzeń PluginManager: błędy ładowania, reload, hooki."""

    @pytest.fixture
    def temp_plugins_dir(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        return plugins_dir

    @pytest.fixture
    def plugin_manager(self, temp_plugins_dir):
        return PluginManager(Mock(), temp_plugins_dir)

    _SRC = '''\
from src.plugin_system import BasePlugin


class P(BasePlugin):
    PLUGIN_NAME = "P"
    def on_load(self):
        pass
    def on_unload(self):
        pass
'''

    def test_load_errors_collected(self, plugin_manager, temp_plugins_dir):
        (temp_plugins_dir / "ok.py").write_text(self._SRC, encoding="utf-8")
        (temp_plugins_dir / "empty.py").write_text("X = 1\n", encoding="utf-8")
        (temp_plugins_dir / "broken.py").write_text("raise RuntimeError('x')\n",
                                                   encoding="utf-8")

        count = plugin_manager.load_plugins()

        assert count == 1
        errs = plugin_manager.load_errors
        assert any("empty.py" in e for e in errs)
        assert any("broken.py" in e for e in errs)

    def test_load_errors_cleared_on_reload_all(self, plugin_manager, temp_plugins_dir):
        (temp_plugins_dir / "broken.py").write_text("raise RuntimeError('x')\n",
                                                   encoding="utf-8")
        plugin_manager.load_plugins()
        assert plugin_manager.load_errors
        plugin_manager.load_plugins()
        # drugi przebieg — plik nadal błędny, ale lista nie rośnie w nieskończoność
        assert len(plugin_manager.load_errors) == 1

    def test_reload_plugin_success(self, plugin_manager, temp_plugins_dir):
        (temp_plugins_dir / "p.py").write_text(self._SRC, encoding="utf-8")
        plugin_manager.load_plugins()
        assert "p" in plugin_manager.plugins

        assert plugin_manager.reload_plugin("p") is True
        assert "p" in plugin_manager.plugins

    def test_reload_plugin_missing(self, plugin_manager):
        assert plugin_manager.reload_plugin("nope") is False

    def test_reload_plugin_file_deleted(self, plugin_manager, temp_plugins_dir):
        path = temp_plugins_dir / "p.py"
        path.write_text(self._SRC, encoding="utf-8")
        plugin_manager.load_plugins()
        path.unlink()
        assert plugin_manager.reload_plugin("p") is False
        assert "p" not in plugin_manager.plugins

    def test_reload_plugin_broken_file(self, plugin_manager, temp_plugins_dir):
        path = temp_plugins_dir / "p.py"
        path.write_text(self._SRC, encoding="utf-8")
        plugin_manager.load_plugins()
        path.write_text("raise RuntimeError('now broken')\n", encoding="utf-8")
        assert plugin_manager.reload_plugin("p") is False
        assert "p" not in plugin_manager.plugins
        assert plugin_manager.load_errors

    def test_get_plugin_path(self, plugin_manager, temp_plugins_dir):
        path = temp_plugins_dir / "p.py"
        path.write_text(self._SRC, encoding="utf-8")
        plugin_manager.load_plugins()
        assert plugin_manager.get_plugin_path("p") == path
        assert plugin_manager.get_plugin_path("missing") is None

    def test_hook_usage(self, plugin_manager):
        usage = plugin_manager.hook_usage()
        assert set(usage) == set(PluginManager.HOOKS)
        assert all(v == 0 for v in usage.values())
        plugin_manager.register_hook("on_app_start", Mock())
        assert plugin_manager.hook_usage()["on_app_start"] == 1

    def test_registered_hooks_tracking(self, plugin_manager):
        plugin = Mock()
        plugin.registered_hooks = []
        # BasePlugin.register_hook dopisuje nazwę hooka do listy
        app = plugin_manager.app
        app._plugin_manager = plugin_manager
        class P(BasePlugin):
            def on_load(self): pass
            def on_unload(self): pass
        p = P(app)
        p.register_hook("on_app_start", Mock())
        p.register_hook("on_app_start", Mock())
        p.register_hook("after_db_save", Mock())
        assert p.registered_hooks == ["on_app_start", "after_db_save"]


class TestPluginHookLifecycle:
    """Testy wyrejestrowywania callbacków przy disable/unload pluginu."""

    @pytest.fixture
    def plugin_manager(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        app = Mock()
        pm = PluginManager(app, plugins_dir)
        app._plugin_manager = pm
        return pm

    def _make_plugin(self, pm):
        class P(BasePlugin):
            def on_load(self): pass
            def on_unload(self): pass
        p = P(pm.app)
        return p

    def test_disable_plugin_unregisters_callbacks(self, plugin_manager):
        pm = plugin_manager
        p = self._make_plugin(pm)
        cb = Mock()
        p.register_hook("on_app_start", cb)
        pm.plugins["p"] = p
        assert pm.hook_usage()["on_app_start"] == 1

        assert pm.disable_plugin("p") is True
        assert pm.hook_usage()["on_app_start"] == 0
        pm.hooks["on_app_start"].trigger()
        cb.assert_not_called()

    def test_enable_plugin_reregisters_callbacks(self, plugin_manager):
        pm = plugin_manager
        p = self._make_plugin(pm)
        cb = Mock()
        p.register_hook("on_app_start", cb)
        p.register_hook("after_db_save", cb)
        pm.plugins["p"] = p
        pm.disable_plugin("p")
        assert pm.hook_usage()["on_app_start"] == 0

        assert pm.enable_plugin("p") is True
        assert pm.hook_usage()["on_app_start"] == 1
        assert pm.hook_usage()["after_db_save"] == 1
        # enable dwa razy — bez duplikatów
        pm.enable_plugin("p")
        assert pm.hook_usage()["on_app_start"] == 1

    def test_unload_plugin_unregisters_callbacks(self, plugin_manager):
        pm = plugin_manager
        p = self._make_plugin(pm)
        cb = Mock()
        p.register_hook("before_db_save", cb)
        pm.plugins["p"] = p
        pm._plugin_files["p"] = pm.plugins_dir / "p.py"

        assert pm.unload_plugin("p") is True
        assert pm.hook_usage()["before_db_save"] == 0
        assert "p" not in pm._plugin_files

    def test_unregister_plugin_unknown_hook_and_missing_callback(self, plugin_manager):
        pm = plugin_manager
        p = self._make_plugin(pm)
        # hook nieistniejący + callback nieobecny w hooku — brak błędu
        p._hook_callbacks = [("no_such_hook", Mock()), ("on_app_start", Mock())]
        pm._unregister_plugin(p)  # nie powinno rzucać

    def test_hook_register_dedupes_callbacks(self):
        hook = PluginHook("h")
        cb = Mock()
        hook.register(cb)
        hook.register(cb)
        assert len(hook._callbacks) == 1


class TestPluginCommands:
    """Testy komend/aliasów pluginów (PLUGIN_COMMANDS + on_command)."""

    @pytest.fixture
    def plugin_manager(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        app = Mock()
        pm = PluginManager(app, plugins_dir)
        app._plugin_manager = pm
        return pm

    def _plugin(self, pm, commands=None, with_handler=True):
        class P(BasePlugin):
            PLUGIN_COMMANDS = commands or {}
            def on_load(self): pass
            def on_unload(self): pass
            if with_handler:
                def on_command(self, alias, args=""):
                    self.called = (alias, args)
        return P(pm.app)

    def test_plugin_commands_collects_enabled(self, plugin_manager):
        pm = plugin_manager
        p = self._plugin(pm, {"stats": "Statystyki"})
        pm.plugins["p1"] = p
        p2 = self._plugin(pm)  # bez komend
        pm.plugins["p2"] = p2
        cmds = pm.plugin_commands()
        assert cmds == {"stats": {"plugin": "p1", "description": "Statystyki"}}

    def test_plugin_commands_skips_disabled(self, plugin_manager):
        pm = plugin_manager
        p = self._plugin(pm, {"x": "X"})
        p.enabled = False
        pm.plugins["p"] = p
        assert pm.plugin_commands() == {}

    def test_run_command_success(self, plugin_manager):
        pm = plugin_manager
        p = self._plugin(pm, {"stats": "S"})
        pm.plugins["p"] = p
        assert pm.run_command("stats", "tryb=1") is True
        assert p.called == ("stats", "tryb=1")

    def test_run_command_unknown_alias(self, plugin_manager):
        pm = plugin_manager
        pm.plugins["p"] = self._plugin(pm, {"stats": "S"})
        assert pm.run_command("nope") is False

    def test_run_command_no_handler(self, plugin_manager):
        pm = plugin_manager
        pm.plugins["p"] = self._plugin(pm, {"stats": "S"}, with_handler=False)
        assert pm.run_command("stats") is False

    def test_run_command_disabled_plugin_skipped(self, plugin_manager):
        pm = plugin_manager
        p = self._plugin(pm, {"stats": "S"})
        p.enabled = False
        pm.plugins["p"] = p
        assert pm.run_command("stats") is False

    def test_run_command_handler_exception_logged(self, plugin_manager, caplog):
        pm = plugin_manager
        class P(BasePlugin):
            PLUGIN_COMMANDS = {"bad": "B"}
            def on_load(self): pass
            def on_unload(self): pass
            def on_command(self, alias, args=""):
                raise RuntimeError("boom")
        pm.plugins["p"] = P(pm.app)
        import logging
        with caplog.at_level(logging.ERROR):
            assert pm.run_command("bad") is True
        assert "command bad failed" in caplog.text
