"""
Test weryfikujący zapis wszystkich skryptów do jednego pliku bazy danych.
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from baza_skryptow import db_wrap, db_write, db_read, sc_normalize


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture dostarczający tymczasową ścieżkę do bazy danych."""
    return tmp_path / "test_single_file_db.json"


def test_multiple_scripts_to_single_file(temp_db_path):
    """
    Test weryfikujący, że wiele skryptów można zapisać do jednego pliku JSON.
    """
    # Utwórz przykładowe skrypty
    scripts = []
    for i in range(10):
        script = {
            "id": f"script-{i}",
            "nazwa": f"Script {i}",
            "kategoria": "Python",
            "tagi": f"tag{i}",
            "opis": f"Description for script {i}",
            "kod": f"print('Script {i}')",
            "utworzony": "2024-01-01 00:00:00",
            "zmieniony": "2024-01-01 00:00:00",
            "uruchomien": i,
        }
        scripts.append(sc_normalize(script))

    # Zapisz wszystkie skrypty do jednego pliku
    db_write(temp_db_path, scripts, backup_count=0)

    # Sprawdź czy plik istnieje
    assert temp_db_path.exists()

    # Odczytaj i sprawdź strukturę
    with open(temp_db_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Sprawdź strukturę
    assert "schema" in data
    assert "app" in data
    assert "exported" in data
    assert "skrypty" in data
    assert isinstance(data["skrypty"], list)

    # Sprawdź czy wszystkie skrypty są w pliku
    assert len(data["skrypty"]) == 10

    # Sprawdź czy każdy skrypt ma wymagane pola
    for script in data["skrypty"]:
        assert "id" in script
        assert "nazwa" in script
        assert "kategoria" in script
        assert "kod" in script


def test_large_database_compression(tmp_path):
    """
    Test weryfikujący kompresję dla dużych baz danych.
    """
    # Utwórz dużą bazę (powyżej BIG_DB_THRESHOLD = 1_000_000 znaków)
    scripts = []
    large_code = "print('x')\n" * 100000  # ~1.1M znaków

    for i in range(5):
        script = {
            "id": f"large-script-{i}",
            "nazwa": f"Large Script {i}",
            "kategoria": "Python",
            "kod": large_code,
        }
        scripts.append(sc_normalize(script))

    # Zapisz
    db_path = tmp_path / "large_db.json"
    db_write(db_path, scripts, backup_count=0)

    # Sprawdź czy plik istnieje
    assert db_path.exists()

    # Odczytaj z funkcji db_read
    loaded_scripts, notes = db_read(db_path)

    # Sprawdź czy wszystkie skrypty zostały odzyskane
    assert len(loaded_scripts) == 5
    assert loaded_scripts[0]["nazwa"] == "Large Script 0"


def test_single_file_persistence(temp_db_path):
    """
    Test weryfikujący, że dane są trwałe po zapisie i odczycie.
    """
    # Utwórz skrypty z różnymi typami danych
    scripts = [
        sc_normalize({
            "id": "1",
            "nazwa": "Python Script",
            "kategoria": "Python",
            "kod": "print('Python')",
            "tagi": "python,test",
            "uruchomien": 10,
        }),
        sc_normalize({
            "id": "2",
            "nazwa": "Bash Script",
            "kategoria": "Bash",
            "kod": "echo 'Bash'",
            "tagi": "bash,shell",
            "uruchomien": 5,
        }),
        sc_normalize({
            "id": "3",
            "nazwa": "SQL Script",
            "kategoria": "SQL",
            "kod": "SELECT * FROM table;",
            "tagi": "sql,database",
            "uruchomien": 2,
        }),
    ]

    # Zapisz
    db_write(temp_db_path, scripts, backup_count=0)

    # Odczytaj
    loaded_scripts, _ = db_read(temp_db_path)

    # Sprawdź czy dane są identyczne
    assert len(loaded_scripts) == 3

    # Porównaj kluczowe pola
    original_ids = {s["id"] for s in scripts}
    loaded_ids = {s["id"] for s in loaded_scripts}
    assert original_ids == loaded_ids

    # Sprawdź zawartość kodu
    for original, loaded in zip(scripts, loaded_scripts):
        assert original["nazwa"] == loaded["nazwa"]
        assert original["kategoria"] == loaded["kategoria"]
        assert original["kod"] == loaded["kod"]
        assert original["tagi"] == loaded["tagi"]


def test_single_file_with_versions(temp_db_path):
    """
    Test weryfikujący zapis skryptów z historią wersji.
    """
    from baza_skryptow import sc_add_version

    # Utwórz skrypt z historią wersji
    script = sc_normalize({
        "id": "versioned-script",
        "nazwa": "Versioned Script",
        "kategoria": "Python",
        "kod": "print('v1')",
    })

    # Dodaj kilka wersji
    script["kod"] = "print('v2')"
    sc_add_version(script, autor="edit1")
    script["kod"] = "print('v3')"
    sc_add_version(script, autor="edit2")

    # Zapisz
    db_write(temp_db_path, [script], backup_count=0)

    # Odczytaj
    loaded_scripts, _ = db_read(temp_db_path)

    # Sprawdź czy historia wersji została zachowana
    assert len(loaded_scripts) == 1
    assert "wersje" in loaded_scripts[0]
    assert len(loaded_scripts[0]["wersje"]) >= 2


def test_single_file_backup_rotation(tmp_path):
    """
    Test weryfikujący rotację kopii zapasowych.
    """
    db_path = tmp_path / "backup_test.json"
    scripts = [sc_normalize({"id": "1", "nazwa": "Test", "kategoria": "Python"})]

    # Pierwszy zapis
    db_write(db_path, scripts, backup_count=3)

    # Drugi zapis
    scripts[0]["nazwa"] = "Test v2"
    db_write(db_path, scripts, backup_count=3)

    # Sprawdź czy istnieje kopia zapasowa
    backup_path = db_path.with_suffix(".json.bak")
    assert backup_path.exists()

    # Odczytaj kopię zapasową
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    # Sprawdź czy w kopii jest stara wersja
    assert backup_data["skrypty"][0]["nazwa"] == "Test"
