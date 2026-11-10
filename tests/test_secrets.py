"""
Testy menedżera sekretów (poz. 9 planu działania).

Sprawdzają szyfrowanie Fernet, CRUD, trwałość oraz rozwiązywanie zmiennych
środowiskowych (zakres globalny i per-skrypt).
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cryptography.fernet import Fernet

from src.secrets import (
    ZAKRESY,
    SecretsStore,
    env_name_valid,
    secret_normalize,
)


@pytest.fixture
def store(tmp_path):
    key = Fernet.generate_key()
    return SecretsStore(tmp_path / "sekrety.json", key=key, use_keyring=False)


class TestHelpers:
    """Funkcje pomocnicze i normalizacja."""

    def test_env_name_valid_ok(self):
        assert env_name_valid("API_KEY")
        assert env_name_valid("_x1")
        assert env_name_valid("Token2")

    def test_env_name_valid_bad(self):
        assert not env_name_valid("1BAD")
        assert not env_name_valid("BAD-NAME")
        assert not env_name_valid("has space")
        assert not env_name_valid("")
        assert not env_name_valid(None)

    def test_normalize_defaults(self):
        rec = secret_normalize({})
        assert rec["zakres"] == "global"
        assert rec["nazwa"] == ""
        assert rec["id"]
        assert rec["zmieniony"]

    def test_normalize_bad_scope(self):
        assert secret_normalize({"zakres": "cos"})["zakres"] == "global"

    def test_zakresy(self):
        assert ZAKRESY == ("global", "skrypt")


class TestCRUD:
    """Dodawanie, odczyt, aktualizacja i usuwanie sekretów."""

    def test_available(self, store):
        assert store.available() is True

    def test_set_and_reveal(self, store):
        ok, _ = store.set("API_KEY", "tajne-123")
        assert ok
        rec = store.sekrety[0]
        assert store.get_value(rec["id"]) == "tajne-123"

    def test_value_is_encrypted_on_disk(self, store):
        store.set("API_KEY", "tajne-123")
        raw = store.path.read_text(encoding="utf-8")
        assert "tajne-123" not in raw
        assert "API_KEY" in raw  # nazwa pozostaje jawna

    def test_invalid_name_rejected(self, store):
        ok, msg = store.set("zła nazwa", "x")
        assert ok is False
        assert store.sekrety == []

    def test_skrypt_scope_requires_script(self, store):
        ok, _ = store.set("TOKEN", "x", zakres="skrypt", skrypt="")
        assert ok is False
        assert store.sekrety == []

    def test_set_updates_existing(self, store):
        store.set("API_KEY", "v1")
        store.set("API_KEY", "v2")
        assert len(store.sekrety) == 1
        assert store.get_value(store.sekrety[0]["id"]) == "v2"

    def test_same_name_different_scope_separate(self, store):
        store.set("TOKEN", "g")
        store.set("TOKEN", "s", zakres="skrypt", skrypt="skrypt_a")
        assert len(store.sekrety) == 2

    def test_delete(self, store):
        store.set("API_KEY", "x")
        sid = store.sekrety[0]["id"]
        assert store.delete(sid) is True
        assert store.sekrety == []
        assert store.delete("nieistnieje") is False

    def test_get_value_missing(self, store):
        assert store.get_value("brak") is None


class TestPersistence:
    """Trwałość i odporność na błędy klucza."""

    def test_roundtrip(self, tmp_path):
        key = Fernet.generate_key()
        path = tmp_path / "sekrety.json"
        s1 = SecretsStore(path, key=key, use_keyring=False)
        s1.set("API_KEY", "tajne")
        s2 = SecretsStore(path, key=key, use_keyring=False)
        assert s2.get_value(s2.sekrety[0]["id"]) == "tajne"

    def test_wrong_key_cannot_decrypt(self, tmp_path):
        path = tmp_path / "sekrety.json"
        s1 = SecretsStore(path, key=Fernet.generate_key(), use_keyring=False)
        s1.set("API_KEY", "tajne")
        s2 = SecretsStore(path, key=Fernet.generate_key(), use_keyring=False)
        assert s2.get_value(s2.sekrety[0]["id"]) is None

    def test_missing_file_is_empty(self, tmp_path):
        s = SecretsStore(tmp_path / "brak.json", key=Fernet.generate_key(),
                         use_keyring=False)
        assert s.sekrety == []

    def test_corrupt_file_is_empty(self, tmp_path):
        p = tmp_path / "sekrety.json"
        p.write_text("{nie-json", encoding="utf-8")
        s = SecretsStore(p, key=Fernet.generate_key(), use_keyring=False)
        assert s.sekrety == []


class TestResolveEnv:
    """Wstrzykiwanie jako zmienne środowiskowe."""

    def test_global_always_injected(self, store):
        store.set("API_KEY", "abc")
        assert store.resolve_env("dowolny") == {"API_KEY": "abc"}

    def test_script_scope_only_for_matching(self, store):
        store.set("TOKEN", "s", zakres="skrypt", skrypt="skrypt_a")
        assert store.resolve_env("skrypt_a") == {"TOKEN": "s"}
        assert store.resolve_env("skrypt_b") == {}

    def test_script_overrides_global(self, store):
        store.set("TOKEN", "globalny")
        store.set("TOKEN", "lokalny", zakres="skrypt", skrypt="skrypt_a")
        assert store.resolve_env("skrypt_a") == {"TOKEN": "lokalny"}
        assert store.resolve_env("skrypt_b") == {"TOKEN": "globalny"}

    def test_undecryptable_skipped(self, tmp_path):
        path = tmp_path / "sekrety.json"
        s1 = SecretsStore(path, key=Fernet.generate_key(), use_keyring=False)
        s1.set("API_KEY", "abc")
        s2 = SecretsStore(path, key=Fernet.generate_key(), use_keyring=False)
        assert s2.resolve_env() == {}


class TestKeyManagement:
    """Zarządzanie kluczem szyfrującym (plik klucza, keyring)."""

    def test_key_file_roundtrip(self, tmp_path):
        """Bez podanego klucza generowany jest klucz i zapisywany do pliku .key."""
        path = tmp_path / "sekrety.json"
        s1 = SecretsStore(path, use_keyring=False)
        ok, _ = s1.set("API_KEY", "tajne")
        assert ok

        key_file = path.with_suffix(path.suffix + ".key")
        assert key_file.exists()
        assert key_file.read_bytes().strip()

        # Nowy store bez klucza odczytuje klucz z pliku i odszyfrowuje sekrety.
        s2 = SecretsStore(path, use_keyring=False)
        assert s2.get_value(s2.sekrety[0]["id"]) == "tajne"

    def test_read_key_missing_returns_none(self, tmp_path):
        """Brak pliku klucza — _read_key zwraca None."""
        s = SecretsStore(tmp_path / "sekrety.json", use_keyring=False)
        assert s._read_key() is None

    def test_write_key_creates_file(self, tmp_path):
        """_write_key zapisuje klucz do pliku .key."""
        s = SecretsStore(tmp_path / "sekrety.json", use_keyring=False)
        key = Fernet.generate_key()
        s._write_key(key)
        assert s._key_path().read_bytes().strip() == key

    def test_keyring_read_and_write(self, tmp_path):
        """Gdy keyring jest dostępny, klucz jest czytany i zapisywany tam."""
        fake_keyring = Mock()
        fake_keyring.get_password.return_value = None

        with patch("src.secrets._HAS_KEYRING", True), \
             patch("src.secrets.keyring", fake_keyring):
            s = SecretsStore(tmp_path / "sekrety.json")
            assert s.keyring_available() is True
            ok, _ = s.set("API_KEY", "tajne")
            assert ok
            fake_keyring.set_password.assert_called_once()

            # Odczyt klucza z keyringu
            fake_keyring.get_password.return_value = s._key.decode()
            s2 = SecretsStore(tmp_path / "sekrety2.json")
            assert s2._read_key() == s._key

    def test_keyring_get_password_empty_falls_back_to_file(self, tmp_path):
        """Pusty klucz w keyringu — fallback do pliku klucza."""
        fake_keyring = Mock()
        fake_keyring.get_password.return_value = ""
        path = tmp_path / "sekrety.json"

        with patch("src.secrets._HAS_KEYRING", True), \
             patch("src.secrets.keyring", fake_keyring):
            s = SecretsStore(path, use_keyring=False)
            key = Fernet.generate_key()
            s._write_key(key)
            # use_keyring=False — czyta tylko plik
            s2 = SecretsStore(path, use_keyring=False)
            assert s2._read_key() == key


class TestEdgeCases:
    """Przypadki brzegowe: brak kryptografii, błędy zapisu, zły zakres."""

    def test_no_crypto_disables_set_and_get(self, tmp_path):
        """Bez biblioteki cryptography set/get_value zwracają porażkę/None."""
        path = tmp_path / "sekrety.json"
        with patch("src.secrets._HAS_CRYPTO", False):
            s = SecretsStore(path, use_keyring=False)
            assert s.available() is False
            ok, msg = s.set("API_KEY", "x")
            assert ok is False
            assert "cryptography" in msg

            # Rekord z wartoscia, ale bez mozliwosci deszyfrowania
            s.sekrety.append(secret_normalize({"nazwa": "A", "wartosc": "tok"}))
            assert s.get_value(s.sekrety[0]["id"]) is None

    def test_save_oserror_logged(self, tmp_path, caplog):
        """Błąd zapisu (brak katalogu) jest łapany i logowany."""
        import logging

        s = SecretsStore(tmp_path / "nie_ma_katalogu" / "sekrety.json",
                         key=Fernet.generate_key(), use_keyring=False)
        with caplog.at_level(logging.ERROR):
            s.set("API_KEY", "x")
        assert "Błąd zapisu sekretów" in caplog.text

    def test_load_non_list_data(self, tmp_path):
        """Plik JSON z danymi niebędącymi listą daje pustą listę sekretów."""
        p = tmp_path / "sekrety.json"
        p.write_text('{"sekrety": "to-nie-lista"}', encoding="utf-8")
        s = SecretsStore(p, key=Fernet.generate_key(), use_keyring=False)
        assert s.sekrety == []

        p.write_text('"zwykly-string"', encoding="utf-8")
        s2 = SecretsStore(p, key=Fernet.generate_key(), use_keyring=False)
        assert s2.sekrety == []

    def test_invalid_scope_falls_back_to_global(self, store):
        """Nieznany zakres jest normalizowany do 'global'."""
        ok, _ = store.set("API_KEY", "x", zakres="nieznany")
        assert ok
        assert store.sekrety[0]["zakres"] == "global"

    def test_ensure_fernet_uses_stored_key(self, tmp_path):
        """Gdy _fernet nie został utworzony w __init__, _ensure_fernet buduje go z _key."""
        key = Fernet.generate_key()
        with patch("src.secrets._HAS_CRYPTO", False):
            s = SecretsStore(tmp_path / "sekrety.json", key=key,
                             use_keyring=False)
            assert s._fernet is None
        # po przywróceniu _HAS_CRYPTO set() powinien zbudować Fernet z zapisanego klucza
        ok, _ = s.set("API_KEY", "x")
        assert ok
        assert s.get_value(s.sekrety[0]["id"]) == "x"
