# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: config.py
# Opis:  Model konfiguracji z walidacją pydantic
# ──────────────────────────────────────────────────────────────────────────────

from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Model konfiguracji aplikacji z walidacją pydantic.

    Obsługuje wczytywanie z pliku, zmiennych środowiskowych i wartości domyślne.
    """

    # Ścieżka do bazy danych
    db_path: Optional[str] = Field(
        default="",
        description="Ścieżka do pliku bazy danych (puste = domyślna)"
    )

    # Automatyczne zapisywanie
    autosave: bool = Field(
        default=True,
        description="Czy automatycznie zapisywać zmiany"
    )

    # Liczba kopii zapasowych
    backup_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Liczba kopii zapasowych do zachowania (0-10)"
    )

    # Interpreter Python
    interpreter: Optional[str] = Field(
        default="",
        description="Ścieżka do interpretera Python (puste = sys.executable)"
    )

    # Timeout dla runnera
    timeout: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Timeout dla runnera w sekundach (1-3600)"
    )

    # Argumenty runnera
    runner_args: str = Field(
        default="",
        description="Dodatkowe argumenty dla runnera"
    )

    # Uruchamianie w nowej konsoli
    runner_console: bool = Field(
        default=False,
        description="Czy uruchamiać skrypty w nowej konsoli"
    )

    # Kolory UI
    bg_tab_act: Optional[str] = Field(
        default="",
        description="Kolor aktywnego zadładki (puste = domyślny)"
    )

    bg_tab_inact: Optional[str] = Field(
        default="",
        description="Kolor nieaktywnej zakładki (puste = domyślny)"
    )

    fg_text: Optional[str] = Field(
        default="",
        description="Kolor tekstu (puste = domyślny)"
    )

    # Czcionka
    font_family: str = Field(
        default="Consolas",
        description="Rodzina czcionki"
    )

    font_size: int = Field(
        default=10,
        ge=7,
        le=28,
        description="Rozmiar czcionki (7-28)"
    )

    # Motyw interfejsu
    theme: str = Field(
        default="ciemny",
        description="Motyw interfejsu: 'ciemny', 'jasny' lub 'kontrastowy'"
    )

    # Język interfejsu
    language: str = Field(
        default="en",
        description="Język interfejsu: 'pl' lub 'en'"
    )

    # Git integration
    git_enabled: bool = Field(
        default=True,
        description="Czy włączyć integrację Git"
    )

    git_auto_commit: bool = Field(
        default=True,
        description="Czy automatycznie commitować zmiany"
    )

    git_auto_push: bool = Field(
        default=False,
        description="Czy wypychać commit bazy do Git remote po zapisie"
    )

    # Plugin system
    plugins_enabled: bool = Field(
        default=True,
        description="Czy włączyć system pluginów"
    )

    # Kosz — automatyczne trwałe usuwanie po N dniach (0 = wyłączone)
    trash_days: int = Field(
        default=0,
        ge=0,
        le=365,
        description="Trwale usuń elementy kosza starsze niż N dni (0 = nigdy)"
    )

    # Powiadomienia systemowe po zadaniach harmonogramu
    notify_enabled: bool = Field(
        default=True,
        description="Czy powiadamiać (toast) po zakończeniu zadania harmonogramu"
    )

    # Wygląd listy skryptów
    list_alt_rows: bool = Field(
        default=True,
        description="Naprzemienne kolory wierszy listy skryptów"
    )

    list_bg_odd: Optional[str] = Field(
        default="",
        description="Kolor nieparzystego wiersza (puste = motyw)"
    )

    list_bg_even: Optional[str] = Field(
        default="",
        description="Kolor parzystego wiersza (puste = motyw)"
    )

    list_sel_bg: Optional[str] = Field(
        default="",
        description="Kolor zaznaczonego wiersza (puste = motyw)"
    )

    list_row_height: int = Field(
        default=24,
        ge=16,
        le=64,
        description="Wysokość wiersza listy skryptów w pikselach (16-64)"
    )

    list_font_size: int = Field(
        default=10,
        ge=7,
        le=20,
        description="Rozmiar czcionki listy skryptów (7-20)"
    )

    model_config = SettingsConfigDict(
        env_prefix="CODEMATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator('backup_count')
    @classmethod
    def validate_backup_count(cls, v: int) -> int:
        """Waliduje liczbę kopii zapasowych."""
        if v < 0:
            raise ValueError('backup_count musi być nieujemne')
        if v > 10:
            raise ValueError('backup_count nie może być większe niż 10')
        return v

    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Waliduje timeout."""
        if v < 1:
            raise ValueError('timeout musi być co najmniej 1 sekunda')
        if v > 3600:
            raise ValueError('timeout nie może być większy niż 3600 sekund')
        return v

    @field_validator('font_size')
    @classmethod
    def validate_font_size(cls, v: int) -> int:
        """Waliduje rozmiar czcionki."""
        if v < 7:
            raise ValueError('font_size musi być co najmniej 7')
        if v > 28:
            raise ValueError('font_size nie może być większy niż 28')
        return v

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Normalizuje język interfejsu do 'pl' lub 'en'."""
        return v if v in ("pl", "en") else "en"

    @field_validator('theme')
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Normalizuje motyw interfejsu do znanych presetów."""
        return v if v in ("ciemny", "jasny", "kontrastowy") else "ciemny"

    def to_dict(self) -> Dict[str, str]:
        """
        Konwertuje konfigurację na słownik kompatybilny z starym formatem.

        Returns:
            dict: Słownik z wartościami konfiguracyjnymi.
        """
        return {
            "db_path": self.db_path or "",
            "autosave": "1" if self.autosave else "0",
            "backup_count": str(self.backup_count),
            "interpreter": self.interpreter or "",
            "timeout": str(self.timeout),
            "runner_args": self.runner_args,
            "runner_console": "1" if self.runner_console else "0",
            "bg_tab_act": self.bg_tab_act or "",
            "bg_tab_inact": self.bg_tab_inact or "",
            "fg_text": self.fg_text or "",
            "font_family": self.font_family,
            "font_size": str(self.font_size),
            "theme": self.theme,
            "language": self.language,
            "git_enabled": "1" if self.git_enabled else "0",
            "git_auto_commit": "1" if self.git_auto_commit else "0",
            "git_auto_push": "1" if self.git_auto_push else "0",
            "plugins_enabled": "1" if self.plugins_enabled else "0",
            "trash_days": str(self.trash_days),
            "notify_enabled": "1" if self.notify_enabled else "0",
            "list_alt_rows": "1" if self.list_alt_rows else "0",
            "list_bg_odd": self.list_bg_odd or "",
            "list_bg_even": self.list_bg_even or "",
            "list_sel_bg": self.list_sel_bg or "",
            "list_row_height": str(self.list_row_height),
            "list_font_size": str(self.list_font_size),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """
        Wczytuje konfigurację ze słownika (stary format).

        Args:
            data: Słownik z konfiguracją.

        Returns:
            AppConfig: Instancja konfiguracji.
        """
        return cls(
            db_path=data.get("db_path", ""),
            autosave=data.get("autosave", "1") == "1",
            backup_count=int(data.get("backup_count", "3")),
            interpreter=data.get("interpreter", ""),
            timeout=int(data.get("timeout", "60")),
            runner_args=data.get("runner_args", ""),
            runner_console=data.get("runner_console", "0") == "1",
            bg_tab_act=data.get("bg_tab_act", ""),
            bg_tab_inact=data.get("bg_tab_inact", ""),
            fg_text=data.get("fg_text", ""),
            font_family=data.get("font_family", "Consolas"),
            font_size=int(data.get("font_size", "10")),
            theme=data.get("theme", "ciemny"),
            language=data.get("language", "en"),
            git_enabled=str(data.get("git_enabled", "1")) == "1",
            git_auto_commit=str(data.get("git_auto_commit", "1")) == "1",
            git_auto_push=str(data.get("git_auto_push", "0")) == "1",
            plugins_enabled=str(data.get("plugins_enabled", "1")) == "1",
            trash_days=int(data.get("trash_days", "0") or 0),
            notify_enabled=str(data.get("notify_enabled", "1")) == "1",
            list_alt_rows=str(data.get("list_alt_rows", "1")) == "1",
            list_bg_odd=data.get("list_bg_odd", "") or "",
            list_bg_even=data.get("list_bg_even", "") or "",
            list_sel_bg=data.get("list_sel_bg", "") or "",
            list_row_height=int(data.get("list_row_height", "24") or 24),
            list_font_size=int(data.get("list_font_size", "10") or 10),
        )

    def save_to_file(self, path: Path) -> None:
        """
        Zapisuje konfigurację do pliku (stary format .cfg dla kompatybilności).

        Args:
            path: Ścieżka do pliku konfiguracyjnego.
        """
        import configparser

        cp = configparser.ConfigParser()
        cp.add_section("baza")

        for key, value in self.to_dict().items():
            cp.set("baza", key, value)

        tmp = path.with_suffix(".cfg.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            cp.write(fh)
        Path(tmp).replace(path)

    @classmethod
    def load_from_file(cls, path: Path) -> 'AppConfig':
        """
        Wczytuje konfigurację z pliku (stary format .cfg).

        Args:
            path: Ścieżka do pliku konfiguracyjnego.

        Returns:
            AppConfig: Instancja konfiguracji.
        """
        import configparser

        cp = configparser.ConfigParser()
        try:
            cp.read(str(path), encoding="utf-8")
        except Exception:
            return cls()

        data = {}
        if cp.has_section("baza"):
            for key in cls.model_fields:
                if cp.has_option("baza", key):
                    data[key] = cp.get("baza", key)

        return cls.from_dict(data)
