"""
Testy dla warstwy i18n (tłumaczenia PL/EN) oraz pola `language` w konfiguracji.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from baza_skryptow import _t, _set_lang, _tr, TRANSLATIONS, MENU_EN, UI_LANGS
from src.config import AppConfig


class TestTranslations:
    """Testy silnika tłumaczeń."""

    def teardown_method(self):
        """Przywraca domyślny język EN po każdym teście."""
        _set_lang("en")

    def test_t_en_default(self):
        assert bs._UI_LANG == "en"
        assert _t("tab_skrypty") == "Scripts"

    def test_t_pl_source_language(self):
        _set_lang("pl")
        assert _t("tab_skrypty") == "Skrypty"

    def test_t_switch_to_en(self):
        assert _t("tab_skrypty") == "Scripts"
        assert _t("tab_baza") == "Database"

    def test_t_format_params(self):
        _set_lang("pl")
        assert _t("header_count", n=7) == "Skryptów: 7"
        _set_lang("en")
        assert _t("header_count", n=7) == "Scripts: 7"

    def test_t_missing_key_returns_key(self):
        assert _t("nie_ma_takiego_klucza") == "nie_ma_takiego_klucza"

    def test_t_bad_format_does_not_raise(self):
        # Brak parametru {ver} nie może przerwać działania.
        assert isinstance(_t("app_title"), str)

    def test_set_lang_invalid_falls_back_to_en(self):
        assert _set_lang("xx") == "en"
        assert bs._UI_LANG == "en"

    def test_translations_have_all_langs(self):
        for key, entry in TRANSLATIONS.items():
            for lang in UI_LANGS:
                assert lang in entry, f"Brak '{lang}' dla klucza '{key}'"

    def test_tab_keys_match_main_tabs(self):
        # Klucze zakładek użyte w UI muszą istnieć w słowniku tłumaczeń.
        for key in ("tab_skrypty", "tab_szukaj", "tab_moduly", "tab_baza",
                    "tab_venv", "tab_vdrive", "tab_narzedzia", "tab_terminal",
                    "tab_runner", "tab_git", "tab_plugins"):
            assert key in TRANSLATIONS


class TestMenuTranslations:
    """Testy tłumaczeń tekstowych menu (_tr / MENU_EN)."""

    def teardown_method(self):
        """Przywraca domyślny język EN po każdym teście."""
        _set_lang("en")

    def test_tr_pl_returns_input(self):
        _set_lang("pl")
        assert _tr("Plik") == "Plik"

    def test_tr_en_known_key(self):
        _set_lang("en")
        assert _tr("Plik") == "File"
        assert _tr("Baza danych") == "Database"

    def test_tr_en_unknown_key_falls_back(self):
        _set_lang("en")
        assert _tr("Nieznana etykieta") == "Nieznana etykieta"

    def test_menu_en_values_non_empty(self):
        for key, val in MENU_EN.items():
            assert key and val, f"Puste tłumaczenie dla '{key}'"

    def test_required_menu_labels_present(self):
        # Kluczowe etykiety menu muszą mieć tłumaczenie EN.
        for label in ("Plik", "Skrypty", "Biblioteka", "Baza danych",
                      "Narzędzia", "Widok", "Ustawienia", "Pomoc",
                      "Nowy skrypt", "Kopiuj kod", "O programie"):
            assert label in MENU_EN, f"Brak tłumaczenia dla '{label}'"

    def test_git_tab_labels_and_statuses_translated(self):
        labels = (
            "Commit…", "Push", "Pull", "Remote…", "Synchronizuj bazę",
            "Commit staged…", "Stage selected", "Unstage selected", "Discard worktree…",
            "Auto push po zapisie", "Branch:",
            "Przełącz", "Nowy branch…", "Zmiany", "Stan", "Commit", "Autor",
            "Wiadomość", "Git niedostępny",
            "Git nie jest dostępny lub repozytorium nie zostało zainicjalizowane.",
            "w indeksie", "zmieniony", "nowy", "zmienionych", "nowych",
            "(brak brancha)", "Working tree czyste.",
            "Brak commitów do wyświetlenia.",
            "Brak diffu dla tego commita.", "Nie udało się przełączyć brancha.",
            "Nowy plik (nieśledzony)",
            "Dodaj plik do repozytorium przed podglądem diffu.",
            "Brak diffu dla", "Przełącz branch",
            "Przełączyć z '{current}' na '{branch}'?", "Nie udało się utworzyć brancha.",
            "Nieprawidłowa nazwa brancha.", "Nazwa brancha:",
            "Zaznacz pliki do dodania do stage.",
            "Zaznacz pliki do usunięcia ze stage.",
            "Nie udało się dodać wszystkich zaznaczonych plików do stage.",
            "Nie udało się usunąć wszystkich zaznaczonych plików ze stage.",
            "Zaznacz pliki, których zmiany robocze chcesz odrzucić.",
            "Brak zaznaczonych śledzonych plików ze zmianami roboczymi do odrzucenia.",
            "Odrzuć zmiany robocze",
            "Odrzucić zmiany robocze w {count} plikach?\n"
            "Treść zostanie przywrócona do wersji staged; zmiany staged pozostaną.\n\n{files}",
            "Nie udało się odrzucić zmian dla wszystkich plików.",
            "GitHub:  https://github.com/polsoft-IT",
            "E-mail:  polsoft.its@mail.com",
        )
        for label in labels:
            assert label in MENU_EN, f"Brak tłumaczenia dla '{label}'"

        _set_lang("en")
        assert _tr("Zmiany") == "Changes"
        assert _tr("Working tree czyste.") == "Working tree clean."

    def test_vdrive_labels_and_statuses_translated(self):
        labels = (
            "Gotowy", "🖥 Panel nośników", "➕ Utwórz nośnik", "⚙ Ustawienia",
            "📋 Log", "➕ Dodaj nośnik", "🗑 Usuń nośnik", "Typ", "Etykieta",
            "Plik / ścieżka", "Rozmiar", "Status", "Litera", "(auto)", "(brak)",
            "💾 FDD — Dyskietka 3.5″", "📦 VHDX — Rozszerzony VHD",
            "Etykieta (nazwa):", "Rozmiar (MB):", "Litera dysku (Win):",
            "Opcje globalne:", "Auto-montuj przy starcie", "Uruchom przy logowaniu",
            "✅ Zarejestruj nośnik", "📂 Zarejestruj bez litery",
            "Wybierz nośnik aby zobaczyć szczegóły", "Zaznacz nośnik na liście.",
            "Polecenie skopiowane; nie zostało wykonane",
            "Usunąć nośnik '{label}' z listy?\n(plik na dysku nie zostanie usunięty)",
            "Typ: {type}  |  Etykieta: {label}  |  Ścieżka: {path}  |  Rozmiar: {size} MB  |  Status: {status}  |  Litera: {letter}",
        )
        for label in labels:
            assert label in MENU_EN, f"Brak tłumaczenia VDrive dla '{label}'"

        _set_lang("en")
        assert _tr("🖥 Panel nośników") == "🖥 Media panel"
        assert _tr("Ustawienia VDrive zapisane.") == "VDrive settings saved."
        assert _tr("Dodano: {label}").format(label="Archive") == "Added: Archive"

    def test_tooltips_and_toasts_translated_to_en(self):
        # Chmurki (tooltipy) i powiadomienia gestów muszą mieć tłumaczenia EN.
        labels = (
            "Skrypty - dodawaj, edytuj, przegladaj",
            "Wyszukiwarka - live search",
            "Moduly systemowe - diagnostyka",
            "Baza danych - SQLite",
            "Srodowiska wirtualne - venv + pip",
            "Narzedzia",
            "Nazwa skryptu - wymagane\nRamka: zielona=nowy  pomaranczowa=aktualizacja  czerwona=puste",
            "Tagi oddzielone przecinkami\nnp: python, petla, plik",
            "Live search - nazwa / kategoria / tagi / kod\nEnter = potwierdz",
            "Krotki opis skryptu",
            "Edytor kodu\nCtrl+Scroll=zoom  Srodkowy=pan\nPrawy klik=menu (komentuj, wcinaj, znajdz...)",
            "Lista skryptow\nPrawy klik=menu  Ctrl+A=zaznacz wszystko\nSrodkowy=pan  Ctrl+scroll=zoom",
            "Wyniki wyszukiwania - dwuklik=edytuj",
            "Historia wyszukiwan - dwuklik=przywroc",
            "Eksport bazy", "Import bazy", "Lista skryptow",
            "Nastepna zakladka", "Poprzednia zakladka", "Odswiezone",
            "■ Zatrzymaj harmonogram", "● harmonogram działa", "○ harmonogram zatrzymany",
        )
        _set_lang("en")
        for label in labels:
            assert label in MENU_EN, f"Brak tłumaczenia tooltip/toast dla '{label}'"
            translated = _tr(label)
            assert translated != label, f"Brak tłumaczenia EN dla '{label}'"

    def test_zoom_toast_key_translated(self):
        assert _t("toast_font_size", size=12) == "Font: 12 pt"

    def test_vdrive_controls_retranslate_live(self):
        class FakeControl:
            def __init__(self, value=""):
                self.value = value
                self.options = {}

            def configure(self, **options):
                self.options.update(options)

            config = configure

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        heading = FakeControl("🖥 Panel nośników")
        type_combo = FakeControl("📦 VHD — Virtual Hard Disk")
        fs_combo = FakeControl("NTFS")
        auto_letter = FakeControl("(auto)")
        tool_win = FakeControl("diskpart (wbudowany)")
        tool_lin = FakeControl("mount (wbudowany)")
        status = FakeControl()
        create_status = FakeControl()
        type_options = [
            ("💾 FDD — Dyskietka 3.5″", "FDD"),
            ("📦 VHD — Virtual Hard Disk", "VHD"),
        ]
        fs_options = ["NTFS", "(brak)"]
        tool_win_options = ["diskpart (wbudowany)", "PowerShell Mount-DiskImage"]
        tool_lin_options = ["mount (wbudowany)", "qemu-img + mount"]
        app = SimpleNamespace(
            title=lambda *_args: None,
            _build_menu=lambda: None,
            _i18n_live=[(heading, "🖥 Panel nośników")],
            _i18n_headings=[],
            _main_btns=[],
            _main_tab_keys=[],
            _vdrive_type_combo=type_combo,
            _vdrive_type_options=type_options,
            _vdrive_selected_type="VHD",
            _vdrive_type_var=FakeControl(type_combo.get()),
            _vdrive_new_letter=auto_letter,
            _vdrive_new_fs=fs_combo,
            _vdrive_fs_values=fs_options,
            _vdrive_auto_letter_label="(auto)",
            _vdrive_tool_win=tool_win,
            _vdrive_tool_lin=tool_lin,
            _vdrive_tool_win_options=tool_win_options,
            _vdrive_tool_lin_options=tool_lin_options,
            _vdrive_tool_win_map={"diskpart (wbudowany)": "diskpart (wbudowany)"},
            _vdrive_tool_lin_map={"mount (wbudowany)": "mount (wbudowany)"},
            _vdrive_status_source="Polecenie skopiowane; nie zostało wykonane",
            _vdrive_status_lbl=status,
            _vdrive_create_status_source="✅ Nośnik '{label}' ({type}) dodany.",
            _vdrive_create_status_args={"label": "Archive", "type": "VHD"},
            _vdrive_create_status=create_status,
            _vdrive_refresh_localized_options=lambda: bs.CodeMate._vdrive_refresh_localized_options(app),
            _update_minsize=lambda *a, **k: None,
        )

        _set_lang("en")
        try:
            bs.CodeMate._retranslate_ui(app)
        finally:
            _set_lang("pl")

        assert heading.options["text"] == "🖥 Media panel"
        assert "📦 VHD — Virtual Hard Disk" in type_combo.options["values"]
        assert type_combo.value == "📦 VHD — Virtual Hard Disk"
        assert "diskpart (built-in)" in tool_win.options["values"]
        assert tool_win.value == "diskpart (built-in)"
        assert "(none)" in fs_combo.options["values"]
        assert auto_letter.value == "(auto)"
        assert status.options["text"] == "Command copied; it was not executed"
        assert create_status.options["text"] == "✅ Added VHD media 'Archive'."


class TestConfigLanguage:
    """Testy pola `language` w modelu konfiguracji."""

    def test_default_language_is_en(self):
        assert AppConfig().language == "en"

    def test_to_dict_contains_language(self):
        cfg = AppConfig()
        cfg.language = "en"
        assert cfg.to_dict()["language"] == "en"

    def test_from_dict_roundtrip(self):
        cfg = AppConfig.from_dict({"language": "en"})
        assert cfg.language == "en"

    def test_from_dict_missing_defaults_to_en(self):
        assert AppConfig.from_dict({}).language == "en"

    def test_invalid_language_normalized_to_en(self):
        assert AppConfig.from_dict({"language": "de"}).language == "en"
