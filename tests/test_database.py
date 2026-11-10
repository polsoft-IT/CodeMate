"""
Testy dla funkcji bazy danych.
"""

import json
import sqlite3
import pytest
from pathlib import Path
from typing import Dict, Any

# Importujemy funkcje z głównego pliku (w rzeczywistości należałoby refaktoryzować)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from baza_skryptow import (
    CodeMate,
    db_wrap, db_to_list, db_read, db_write,
    sc_normalize, kod_checksum, now_str,
    DB_SCHEMA, CATEGORIES
)


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture dostarczający tymczasową ścieżkę do bazy danych."""
    return tmp_path / "test_db.json"


@pytest.fixture
def sample_script():
    """Fixture dostarczający przykładowy skrypt."""
    return {
        "id": "test-id-123",
        "nazwa": "Test Script",
        "kategoria": "Python",
        "tagi": "test,demo",
        "opis": "Test description",
        "kod": "print('Hello, World!')",
        "utworzony": "2024-01-01 00:00:00",
        "zmieniony": "2024-01-01 00:00:00",
        "uruchomien": 0,
    }


class TestDatabaseFunctions:
    """Testy funkcji bazy danych."""

    def test_db_wrap(self, sample_script):
        """Test opakowywania danych w strukturę bazy."""
        scripts = [sample_script]
        wrapped = db_wrap(scripts)

        assert wrapped["schema"] == DB_SCHEMA
        assert "app" in wrapped
        assert "exported" in wrapped
        assert len(wrapped["skrypty"]) == 1
        assert wrapped["skrypty"][0]["nazwa"] == "Test Script"

    def test_db_to_list_v2(self, sample_script):
        """Test migracji z formatu v2."""
        data = {
            "schema": 2,
            "skrypty": [sample_script]
        }
        scripts, normalized = db_to_list(data)

        assert len(scripts) == 1
        assert scripts[0]["nazwa"] == "Test Script"
        assert isinstance(normalized, int)

    def test_db_to_list_v1(self, sample_script):
        """Test migracji z formatu v1 (lista)."""
        data = [sample_script]
        scripts, normalized = db_to_list(data)

        assert len(scripts) == 1
        assert scripts[0]["nazwa"] == "Test Script"

    def test_db_to_list_v0(self, sample_script):
        """Test migracji z formatu v0 (dict bez schema)."""
        data = {"skrypty": [sample_script]}
        scripts, normalized = db_to_list(data)

        assert len(scripts) == 1
        assert scripts[0]["nazwa"] == "Test Script"

    def test_db_to_list_invalid_format(self):
        """Test błędnego formatu danych."""
        with pytest.raises(ValueError):
            db_to_list("invalid string")

    def test_db_write_and_read(self, temp_db_path, sample_script):
        """Test zapisu i odczytu bazy danych."""
        scripts = [sample_script]

        # Zapisz
        written_path = db_write(temp_db_path, scripts, backup_count=0)
        assert written_path.exists()

        # Odczytaj
        loaded_scripts, notes = db_read(temp_db_path)
        assert len(loaded_scripts) == 1
        assert loaded_scripts[0]["nazwa"] == "Test Script"

    def test_db_write_with_backup(self, temp_db_path, sample_script):
        """Test zapisu z kopią zapasową."""
        scripts = [sample_script]

        # Pierwszy zapis
        db_write(temp_db_path, scripts, backup_count=2)

        # Drugi zapis
        sample_script["nazwa"] = "Updated Script"
        db_write(temp_db_path, scripts, backup_count=2)

        # Sprawdź czy istnieje kopia zapasowa
        backup_path = temp_db_path.with_suffix(".json.bak")
        assert backup_path.exists()


class TestDatabaseQueryHistory:
    def test_record_query_keeps_recent_unique_entries(self):
        class FakeCombo:
            def configure(self, **kwargs):
                self.values = kwargs["values"]

        class FakeVar:
            def set(self, value):
                self.value = value

        from types import SimpleNamespace

        app = SimpleNamespace(
            _db_query_hist=[],
            _db_query_history_combo=FakeCombo(),
            _db_history_var=FakeVar(),
        )
        for index in range(21):
            CodeMate._db_record_query(app, f"SELECT {index}")
        CodeMate._db_record_query(app, "SELECT 10")

        assert len(app._db_query_hist) == 20
        assert app._db_query_hist[0] == "SELECT 10"
        assert len(set(app._db_query_hist)) == 20
        assert app._db_query_history_combo.values == app._db_query_hist
        assert app._db_history_var.value == "SELECT 10"

    def test_restore_query_replaces_editor_contents(self):
        class FakeVar:
            def get(self):
                return "SELECT * FROM scripts;"

        class FakeText:
            def __init__(self):
                self.calls = []

            def delete(self, start, end):
                self.calls.append(("delete", start, end))

            def insert(self, start, value):
                self.calls.append(("insert", start, value))

        from types import SimpleNamespace

        editor = FakeText()
        app = SimpleNamespace(_db_history_var=FakeVar(), _db_sql_text=editor)

        assert CodeMate._db_restore_query(app) == "break"
        assert editor.calls == [
            ("delete", "1.0", "end"),
            ("insert", "1.0", "SELECT * FROM scripts;"),
        ]


class TestDatabaseTablePages:
    def test_fetch_page_uses_offset_and_quotes_table_name(self):
        connection = sqlite3.connect(":memory:")
        connection.execute('CREATE TABLE "odd""name" (id INTEGER, value TEXT)')
        connection.executemany(
            'INSERT INTO "odd""name" VALUES (?, ?)',
            [(index, f"row-{index}") for index in range(5)],
        )

        columns, rows, total = CodeMate._db_fetch_table_page(
            connection, 'odd"name', limit=2, offset=2)

        assert columns == ["id", "value"]
        assert rows == [(2, "row-2"), (3, "row-3")]
        assert total == 5
        connection.close()

    def test_fetch_page_clamps_limit_and_offset(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE records (id INTEGER)")
        connection.executemany("INSERT INTO records VALUES (?)", [(1,), (2,)])

        _, rows, total = CodeMate._db_fetch_table_page(
            connection, "records", limit=0, offset=-3)

        assert rows == [(1,)]
        assert total == 2
        connection.close()


class TestScriptNormalization:
    """Testy normalizacji skryptów."""

    def test_sc_normalize_full_script(self, sample_script):
        """Test normalizacji pełnego skryptu."""
        normalized = sc_normalize(sample_script)

        assert normalized["nazwa"] == "Test Script"
        assert normalized["kategoria"] == "Python"
        assert normalized["id"] == "test-id-123"
        assert "checksum" in normalized
        assert "wersje" in normalized

    def test_sc_normalize_minimal_script(self):
        """Test normalizacji minimalnego skryptu."""
        minimal = {"nazwa": "Minimal"}
        normalized = sc_normalize(minimal)

        assert normalized["nazwa"] == "Minimal"
        assert normalized["id"]  # ID powinno być wygenerowane
        assert normalized["kategoria"] == "Other"  # domyślna kategoria
        assert normalized["kod"] == ""  # domyślny kod
        assert normalized["tagi"] == ""  # domyślne tagi

    def test_sc_normalize_invalid_category(self):
        """Test normalizacji z nieprawidłową kategorią."""
        script = {"nazwa": "Test", "kategoria": "InvalidCategory"}
        normalized = sc_normalize(script)

        assert normalized["kategoria"] == "Other"  # powinno być domyślne

    def test_sc_normalize_tags_list(self):
        """Test normalizacji tagów jako listy."""
        script = {"nazwa": "Test", "tagi": ["tag1", "tag2"]}
        normalized = sc_normalize(script)

        assert normalized["tagi"] == "tag1, tag2"  # powinno być scalone

    def test_sc_normalize_missing_fields(self):
        """Test normalizacji z brakującymi polami."""
        script = {}
        normalized = sc_normalize(script)

        assert normalized["nazwa"] == "bez-nazwy"
        assert normalized["kategoria"] == "Other"
        assert normalized["kod"] == ""
        assert normalized["opis"] == ""
        assert normalized["uruchomien"] == 0


class TestUtilityFunctions:
    """Testy funkcji narzędziowych."""

    def test_kod_checksum(self):
        """Test generowania checksumu kodu."""
        code = "print('Hello')"
        checksum1 = kod_checksum(code)
        checksum2 = kod_checksum(code)

        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA-256 = 64 znaków hex

    def test_kod_checksum_different_code(self):
        """Test że różny kod daje różny checksum."""
        checksum1 = kod_checksum("print('Hello')")
        checksum2 = kod_checksum("print('World')")

        assert checksum1 != checksum2

    def test_kod_checksum_empty_code(self):
        """Test checksumu dla pustego kodu."""
        checksum = kod_checksum("")
        assert len(checksum) == 64

    def test_kod_checksum_none_code(self):
        """Test checksumu dla None."""
        checksum = kod_checksum(None)
        assert len(checksum) == 64

    def test_now_str(self):
        """Test formatowania timestamp."""
        timestamp = now_str()
        assert isinstance(timestamp, str)
        assert len(timestamp) == 19  # YYYY-MM-DD HH:MM:SS
        assert timestamp[4] == "-"
        assert timestamp[7] == "-"
        assert timestamp[10] == " "
