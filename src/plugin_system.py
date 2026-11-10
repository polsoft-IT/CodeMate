# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: plugin_system.py
# Opis:  System pluginów dla CodeMate
# ──────────────────────────────────────────────────────────────────────────────

import logging
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PluginHook:
    """Hook dla zdarzeń w aplikacji."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._callbacks: List[Callable[..., Any]] = []

    def register(self, callback: Callable[..., Any]) -> None:
        """Rejestruje callback dla hooka (bez duplikatów)."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        """Wywołuje wszystkie zarejestrowane callbacki."""
        for callback in self._callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook {self.name} callback failed: {e}")

    def clear(self) -> None:
        """Czyści wszystkie callbacki."""
        self._callbacks.clear()


class BasePlugin(ABC):
    """
    Bazowa klasa dla wszystkich pluginów.

    Każdy plugin musi dziedziczyć po tej klasie i implementować wymagane metody.
    """

    # Metadane pluginu (override w podklasie)
    PLUGIN_NAME: str = "Base Plugin"
    PLUGIN_VERSION: str = "1.0.0"
    PLUGIN_AUTHOR: str = "Unknown"
    PLUGIN_DESCRIPTION: str = "Base plugin description"
    PLUGIN_CATEGORY: str = "General"

    def __init__(self, app: Any) -> None:
        """
        Inicjalizuje plugin.

        Args:
            app: Instancja głównej aplikacji CodeMate.
        """
        self.app = app
        self.enabled = True
        self._hooks_registered = False
        self.registered_hooks: List[str] = []
        self._hook_callbacks: List[Tuple[str, Callable[..., Any]]] = []

    @abstractmethod
    def on_load(self) -> None:
        """
        Wywoływane przy ładowaniu pluginu.
        Tutaj należy zarejestrować hooki i zainicjalizować zasoby.
        """
        pass

    @abstractmethod
    def on_unload(self) -> None:
        """
        Wywoływane przy wyładowaniu pluginu.
        Tutaj należy wyczyścić zasoby i wyrejestrować hooki.
        """
        pass

    def on_enable(self) -> None:
        """Wywoływane przy włączeniu pluginu."""
        self.enabled = True

    def on_disable(self) -> None:
        """Wywoływane przy wyłączeniu pluginu."""
        self.enabled = False

    def get_info(self) -> Dict[str, str]:
        """Zwraca metadane pluginu."""
        return {
            "name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "author": self.PLUGIN_AUTHOR,
            "description": self.PLUGIN_DESCRIPTION,
            "category": self.PLUGIN_CATEGORY,
            "enabled": str(self.enabled),
        }

    def register_hook(self, hook_name: str, callback: Callable[..., Any]) -> None:
        """
        Rejestruje callback dla hooka w aplikacji.

        Args:
            hook_name: Nazwa hooka.
            callback: Funkcja callback.
        """
        pair = (hook_name, callback)
        if pair not in self._hook_callbacks:
            self._hook_callbacks.append(pair)
        if hook_name not in self.registered_hooks:
            self.registered_hooks.append(hook_name)
        if hasattr(self.app, '_plugin_manager'):
            self.app._plugin_manager.register_hook(hook_name, callback)

    def trigger_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """
        Wywołuje hook w aplikacji.

        Args:
            hook_name: Nazwa hooka.
            *args: Argumenty pozycyjne.
            **kwargs: Argumenty nazwane.
        """
        if hasattr(self.app, '_plugin_manager'):
            self.app._plugin_manager.trigger_hook(hook_name, *args, **kwargs)


class PluginManager:
    """
    Menedżer pluginów - zarządza ładowaniem, wyładowywaniem i hookami.
    """

    # Dostępne hooki
    HOOKS = {
        "before_script_save": "Wywoływane przed zapisem skryptu",
        "after_script_save": "Wywoływane po zapisie skryptu",
        "before_script_run": "Wywoływane przed uruchomieniem skryptu",
        "after_script_run": "Wywoływane po uruchomieniu skryptu",
        "before_db_load": "Wywoływane przed wczytaniem bazy",
        "after_db_load": "Wywoływane po wczytaniu bazy",
        "before_db_save": "Wywoływane przed zapisem bazy",
        "after_db_save": "Wywoływane po zapisie bazy",
        "on_app_start": "Wywoływane przy starcie aplikacji",
        "on_app_close": "Wywoływane przy zamknięciu aplikacji",
    }

    def __init__(self, app: Any, plugins_dir: Optional[Path] = None) -> None:
        """
        Inicjalizuje menedżer pluginów.

        Args:
            app: Instancja głównej aplikacji.
            plugins_dir: Katalog z pluginami (domyślnie ./plugins).
        """
        self.app = app
        self.plugins_dir = plugins_dir or (Path(__file__).parent.parent / "plugins")
        self.plugins_dir.mkdir(exist_ok=True)

        self.plugins: Dict[str, BasePlugin] = {}
        self.hooks: Dict[str, PluginHook] = {}
        self.load_errors: List[str] = []
        self._plugin_files: Dict[str, Path] = {}

        # Inicjalizuj hooki
        for hook_name, description in self.HOOKS.items():
            self.hooks[hook_name] = PluginHook(hook_name, description)

        logger.info(f"PluginManager initialized with plugins dir: {self.plugins_dir}")

    def load_plugins(self) -> int:
        """
        Ładuje wszystkie pluginy z katalogu plugins.

        Returns:
            int: Liczba załadowanych pluginów.
        """
        loaded_count = 0
        self.load_errors.clear()
        self._plugin_files.clear()

        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            if self._load_plugin_file(plugin_file):
                loaded_count += 1

        return loaded_count

    def _load_plugin_file(self, plugin_file: Path) -> bool:
        """Ładuje pojedynczy plik pluginu. Zwraca True przy sukcesie."""
        try:
            plugin_name = plugin_file.stem
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_name}", plugin_file
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("nie udało się utworzyć specyfikacji modułu")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Znajdź klasy dziedziczące po BasePlugin
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                    plugin_instance = obj(self.app)
                    plugin_instance.on_load()
                    self.plugins[plugin_name] = plugin_instance
                    self._plugin_files[plugin_name] = plugin_file
                    logger.info(f"Loaded plugin: {plugin_name}")
                    return True
            self.load_errors.append(f"{plugin_file.name}: brak klasy BasePlugin")
            logger.warning(f"No BasePlugin subclass found in {plugin_file}")
            return False

        except Exception as e:
            self.load_errors.append(f"{plugin_file.name}: {e}")
            logger.error(f"Failed to load plugin {plugin_file}: {e}")
            return False

    def reload_plugin(self, plugin_name: str) -> bool:
        """Przeładowuje plugin z pliku (bez restartu aplikacji).

        Args:
            plugin_name: Nazwa pluginu (stem pliku .py).

        Returns:
            bool: Czy przeładowanie się powiodło.
        """
        path = self._plugin_files.get(plugin_name)
        if path is None or not path.exists():
            self.unload_plugin(plugin_name)
            self._plugin_files.pop(plugin_name, None)
            return False
        self.unload_plugin(plugin_name)
        return self._load_plugin_file(path)

    def get_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """Zwraca ścieżkę pliku pluginu (jeśli znana)."""
        return self._plugin_files.get(plugin_name)

    def hook_usage(self) -> Dict[str, int]:
        """Zwraca liczbę zarejestrowanych callbacków dla każdego hooka."""
        return {name: len(hook._callbacks) for name, hook in self.hooks.items()}

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Wyładowuje plugin.

        Args:
            plugin_name: Nazwa pluginu.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if plugin_name not in self.plugins:
            return False

        try:
            plugin = self.plugins[plugin_name]
            plugin.on_unload()
            self._unregister_plugin(plugin)
            del self.plugins[plugin_name]
            self._plugin_files.pop(plugin_name, None)
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    def enable_plugin(self, plugin_name: str) -> bool:
        """
        Włącza plugin.

        Args:
            plugin_name: Nazwa pluginu.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if plugin_name not in self.plugins:
            return False

        try:
            plugin = self.plugins[plugin_name]
            plugin.on_enable()
            for hook_name, callback in getattr(plugin, "_hook_callbacks", []):
                self.register_hook(hook_name, callback)
            logger.info(f"Enabled plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable plugin {plugin_name}: {e}")
            return False

    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Wyłącza plugin.

        Args:
            plugin_name: Nazwa pluginu.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if plugin_name not in self.plugins:
            return False

        try:
            plugin = self.plugins[plugin_name]
            plugin.on_disable()
            self._unregister_plugin(plugin)
            logger.info(f"Disabled plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_name}: {e}")
            return False

    def _unregister_plugin(self, plugin: BasePlugin) -> None:
        """Usuwa wszystkie callbacki pluginu ze wszystkich hooków."""
        for hook_name, callback in getattr(plugin, "_hook_callbacks", []):
            hook = self.hooks.get(hook_name)
            if hook and callback in hook._callbacks:
                hook._callbacks.remove(callback)

    def register_hook(self, hook_name: str, callback: Callable[..., Any]) -> None:
        """
        Rejestruje callback dla hooka.

        Args:
            hook_name: Nazwa hooka.
            callback: Funkcja callback.
        """
        if hook_name in self.hooks:
            self.hooks[hook_name].register(callback)
        else:
            logger.warning(f"Unknown hook: {hook_name}")

    def trigger_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """
        Wywołuje hook.

        Args:
            hook_name: Nazwa hooka.
            *args: Argumenty pozycyjne.
            **kwargs: Argumenty nazwane.
        """
        if hook_name in self.hooks:
            self.hooks[hook_name].trigger(*args, **kwargs)
        else:
            logger.warning(f"Unknown hook: {hook_name}")

    def get_plugins(self) -> List[Dict[str, str]]:
        """
        Zwraca listę informacji o wszystkich pluginach.

        Returns:
            List[Dict[str, str]]: Lista metadanych pluginów.
        """
        return [plugin.get_info() for plugin in self.plugins.values()]

    def get_hooks(self) -> Dict[str, str]:
        """
        Zwraca listę dostępnych hooków.

        Returns:
            Dict[str, str]: Słownik nazwa: opis hooków.
        """
        return {name: hook.description for name, hook in self.hooks.items()}

    def plugin_commands(self) -> Dict[str, Dict[str, str]]:
        """Zwraca komendy/aliasy zdefiniowane przez włączone pluginy.

        Plugin deklaruje ``PLUGIN_COMMANDS = {"alias": "opis"}``;
        implementuje ``on_command(alias, args)`` do obsługi.

        Returns:
            Dict[str, Dict[str, str]]: alias -> {"plugin", "description"}.
        """
        cmds: Dict[str, Dict[str, str]] = {}
        for name, plugin in self.plugins.items():
            if not getattr(plugin, "enabled", True):
                continue
            for alias, desc in getattr(plugin, "PLUGIN_COMMANDS", {}).items():
                cmds[str(alias)] = {"plugin": name, "description": str(desc)}
        return cmds

    def run_command(self, alias: str, args: str = "") -> bool:
        """Wywołuje komendę pluginu po aliasie.

        Args:
            alias: Alias komendy (klucz z ``PLUGIN_COMMANDS``).
            args: Argumenty tekstowe dla komendy.

        Returns:
            bool: True gdy komenda została znaleziona i wywołana.
        """
        alias = alias.lstrip("/")
        for plugin in self.plugins.values():
            if not getattr(plugin, "enabled", True):
                continue
            commands = getattr(plugin, "PLUGIN_COMMANDS", {})
            if alias in commands and hasattr(plugin, "on_command"):
                try:
                    plugin.on_command(alias, args)
                except Exception as e:
                    logger.error(f"Plugin command {alias} failed: {e}")
                return True
        return False
