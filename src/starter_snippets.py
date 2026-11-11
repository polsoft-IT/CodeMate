# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: starter_snippets.py
# Opis:  Zestaw startowy snippetów — wczytywany przy pierwszym uruchomieniu,
#        gdy plik baza_skryptow.snippety.json jeszcze nie istnieje.
# Wersja: 1.0.0
# Autor:  Sebastian Januchowski · polsoft.ITS™ Group
# ──────────────────────────────────────────────────────────────────────────────
from typing import Any, Dict, List, Union

STARTER_SNIPPETS: List[Dict[str, Union[str, Any]]] = [
    # ── Python ───────────────────────────────────────────────────────────────
    {
        "nazwa": "Py — pomiar czasu wykonania",
        "kategoria": "Python",
        "tagi": "czas timer benchmark",
        "tresc": (
            "import time\n\nstart = time.perf_counter()\n# ...kod do zmierzenia...\n"
            "elapsed = time.perf_counter() - start\nprint(f'Czas: {elapsed:.4f} s')\n"
        ),
    },
    {
        "nazwa": "Py — odczyt argumentów CLI",
        "kategoria": "Python",
        "tagi": "argv cli argumenty",
        "tresc": (
            "import sys\n\nif len(sys.argv) < 2:\n    print('Użycie: skrypt.py <argument>')\n"
            "    sys.exit(1)\n\nargument = sys.argv[1]\nprint(f'Podano: {argument}')\n"
        ),
    },
    {
        "nazwa": "Py — iterowanie po katalogu",
        "kategoria": "Python",
        "tagi": "path pliki katalog glob",
        "tresc": (
            "from pathlib import Path\n\nfor plik in Path('.').rglob('*.py'):\n"
            "    print(f'{plik} — {plik.stat().st_size} B')\n"
        ),
    },
    {
        "nazwa": "Py — zapytanie HTTP z retry",
        "kategoria": "Python",
        "tagi": "requests http retry ponawianie",
        "tresc": (
            "import time\nimport requests\n\nurl = 'https://api.example.com/data'\n"
            "for próba in range(1, 4):\n    try:\n        r = requests.get(url, timeout=10)\n"
            "        r.raise_for_status()\n        print(r.json())\n        break\n"
            "    except requests.RequestException as e:\n"
            "        print(f'Próba {próba} nieudana: {e}')\n        time.sleep(2 ** próba)\n"
        ),
    },
    {
        "nazwa": "Py — słownik z kluczem domyślnym",
        "kategoria": "Python",
        "tagi": "defaultdict słownik",
        "tresc": (
            "from collections import defaultdict\n\ngrupy = defaultdict(list)\n"
            "for element in dane:\n    grupy[element['klucz']].append(element)\n\n"
            "for klucz, wartosci in grupy.items():\n    print(klucz, len(wartosci))\n"
        ),
    },
    # ── Bash ─────────────────────────────────────────────────────────────────
    {
        "nazwa": "Bash — backup katalogu z datą",
        "kategoria": "Bash",
        "tagi": "backup kopia tar data",
        "tresc": (
            "#!/usr/bin/env bash\nset -euo pipefail\n\nSRC=\"./dane\"\n"
            "DEST=\"./backup\"\nNAZWA=\"backup_$(date +%Y%m%d_%H%M%S).tar.gz\"\n\n"
            "mkdir -p \"$DEST\"\ntar -czf \"$DEST/$NAZWA\" -C \"$SRC\" .\n"
            "echo \"Utworzono: $DEST/$NAZWA\"\n"
        ),
    },
    {
        "nazwa": "Bash — sprawdzenie czy plik istnieje",
        "kategoria": "Bash",
        "tagi": "plik istnienie warunek",
        "tresc": (
            "#!/usr/bin/env bash\nPLIK=\"$1\"\n\nif [[ -f \"$PLIK\" ]]; then\n"
            "    echo \"Plik istnieje: $PLIK\"\nelif [[ -d \"$PLIK\" ]]; then\n"
            "    echo \"Katalog istnieje: $PLIK\"\nelse\n    echo \"Nie znaleziono: $PLIK\"\n"
            "    exit 1\nfi\n"
        ),
    },
    {
        "nazwa": "Bash — pobranie strony przez curl",
        "kategoria": "Bash",
        "tagi": "curl http pobieranie",
        "tresc": (
            "#!/usr/bin/env bash\nURL=\"https://example.com\"\nOUT=\"strona.html\"\n\n"
            "curl -fsSL --retry 3 -o \"$OUT\" \"$URL\" \\\n"
            "    && echo \"Zapisano: $OUT\" \\\n    || { echo 'Błąd pobierania'; exit 1; }\n"
        ),
    },
    # ── PowerShell ───────────────────────────────────────────────────────────
    {
        "nazwa": "PS — lista uruchomionych procesów",
        "kategoria": "PowerShell",
        "tagi": "procesy get-process",
        "tresc": (
            "Get-Process | Sort-Object CPU -Descending |\n"
            "    Select-Object -First 10 Name, Id, CPU, WorkingSet64 |\n"
            "    Format-Table -AutoSize\n"
        ),
    },
    {
        "nazwa": "PS — sprawdzenie wolnego miejsca na dysku",
        "kategoria": "PowerShell",
        "tagi": "dysk miejsce disk",
        "tresc": (
            "Get-PSDrive -PSProvider FileSystem |\n"
            "    Select-Object Name, @{n='Wolne [GB]';e={[math]::Round($_.Free/1GB, 2)}},\n"
            "                    @{n='Zajęte [GB]';e={[math]::Round($_.Used/1GB, 2)}} |\n"
            "    Format-Table -AutoSize\n"
        ),
    },
    {
        "nazwa": "PS — eksport użytkowników AD do CSV",
        "kategoria": "PowerShell",
        "tagi": "ad active directory csv",
        "tresc": (
            "Import-Module ActiveDirectory\n\n"
            "Get-ADUser -Filter * -Properties DisplayName, Mail, Enabled |\n"
            "    Select-Object SamAccountName, DisplayName, Mail, Enabled |\n"
            "    Export-Csv -Path 'users.csv' -Encoding UTF8 -NoTypeInformation\n"
        ),
    },
    # ── JavaScript ───────────────────────────────────────────────────────────
    {
        "nazwa": "JS — fetch z obsługą błędów",
        "kategoria": "JavaScript",
        "tagi": "fetch http async",
        "tresc": (
            "async function pobierz(url) {\n  try {\n    const res = await fetch(url);\n"
            "    if (!res.ok) throw new Error(`HTTP ${res.status}`);\n"
            "    return await res.json();\n  } catch (err) {\n"
            "    console.error('Błąd:', err.message);\n    return null;\n  }\n}\n\n"
            "pobierz('https://api.example.com/data').then(console.log);\n"
        ),
    },
    {
        "nazwa": "JS — debounce funkcji",
        "kategoria": "JavaScript",
        "tagi": "debounce opóźnienie eventy",
        "tresc": (
            "function debounce(fn, ms = 300) {\n  let timer;\n"
            "  return (...args) => {\n    clearTimeout(timer);\n"
            "    timer = setTimeout(() => fn(...args), ms);\n  };\n}\n\n"
            "// użycie:\n// window.addEventListener('resize', debounce(() => console.log('resize')))\n"
        ),
    },
    # ── Batch ────────────────────────────────────────────────────────────────
    {
        "nazwa": "BAT — kopia plików z logiem",
        "kategoria": "Batch",
        "tagi": "kopia robocopy log",
        "tresc": (
            "@echo off\nsetlocal\n\nset SRC=C:\\dane\nset DST=D:\\backup\n"
            "set LOG=%DST%\\kopia.log\n\nrobocopy \"%SRC%\" \"%DST%\" /MIR /NFL /NDL \\\n"
            "  /LOG:\"%LOG%\"\necho Zakończono, log: %LOG%\n"
        ),
    },
    {
        "nazwa": "BAT — sprawdzenie łączności ping",
        "kategoria": "Batch",
        "tagi": "ping sieć",
        "tresc": (
            "@echo off\nset HOST=%1\nif \"%HOST%\"==\"\" set HOST=8.8.8.8\n\n"
            "ping -n 4 %HOST% >nul\nif %errorlevel%==0 (\n    echo %HOST% — odpowiedź OK\n"
            ") else (\n    echo %HOST% — BRAK odpowiedzi\n    exit /b 1\n)\n"
        ),
    },
    # ── SQL ──────────────────────────────────────────────────────────────────
    {
        "nazwa": "SQL — top 10 wierszy z tabeli",
        "kategoria": "SQL",
        "tagi": "select top limit",
        "tresc": (
            "-- SQLite / PostgreSQL\nSELECT *\nFROM nazwa_tabeli\nORDER BY id DESC\n"
            "LIMIT 10;\n\n-- SQL Server\nSELECT TOP 10 *\nFROM nazwa_tabeli\n"
            "ORDER BY id DESC;\n"
        ),
    },
    {
        "nazwa": "SQL — tworzenie tabeli z indeksem",
        "kategoria": "SQL",
        "tagi": "create table indeks",
        "tresc": (
            "CREATE TABLE IF NOT EXISTS klienci (\n    id      INTEGER PRIMARY KEY,\n"
            "    nazwa   TEXT NOT NULL,\n    email   TEXT UNIQUE,\n"
            "    utworzono TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\n"
            "CREATE INDEX IF NOT EXISTS idx_klienci_nazwa ON klienci(nazwa);\n"
        ),
    },
    {
        "nazwa": "SQL — grupowanie i agregacja",
        "kategoria": "SQL",
        "tagi": "group by count suma",
        "tresc": (
            "SELECT kategoria,\n       COUNT(*)          AS liczba,\n"
            "       SUM(wartosc)      AS suma,\n       AVG(wartosc)      AS srednia\n"
            "FROM zamowienia\nGROUP BY kategoria\nHAVING COUNT(*) > 1\n"
            "ORDER BY suma DESC;\n"
        ),
    },
    # ── HTML ─────────────────────────────────────────────────────────────────
    {
        "nazwa": "HTML — szkielet strony HTML5",
        "kategoria": "HTML",
        "tagi": "szkielet html5 boilerplate",
        "tresc": (
            "<!DOCTYPE html>\n<html lang=\"pl\">\n<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Tytuł strony</title>\n</head>\n<body>\n  <h1>Nagłówek</h1>\n"
            "  <p>Treść strony.</p>\n</body>\n</html>\n"
        ),
    },
]


def starter_items() -> List[Dict[str, str]]:
    """Zwraca kopię zestawu startowego (gotową do snippet_normalize)."""
    return [dict(item) for item in STARTER_SNIPPETS]
