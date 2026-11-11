# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: starter_snippets.py
# Opis:  Zestaw startowy snippetów — wczytywany przy pierwszym uruchomieniu,
#        gdy plik baza_skryptow.snippety.json jeszcze nie istnieje.
# Wersja: 1.0
# Autor:  Sebastian Januchowski · polsoft.ITS™ Group
# ──────────────────────────────────────────────────────────────────────────────
from typing import Any, Dict, List, Union

STARTER_SNIPPETS: List[Dict[str, Union[str, Any]]] = [
    # ── Python ───────────────────────────────────────────────────────────────
    {
        "nazwa": "Py — execution time measurement",
        "kategoria": "Python",
        "tagi": "time timer benchmark",
        "tresc": (
            "import time\n\nstart = time.perf_counter()\n# ...code to measure...\n"
            "elapsed = time.perf_counter() - start\nprint(f'Time: {elapsed:.4f} s')\n"
        ),
    },
    {
        "nazwa": "Py — reading CLI arguments",
        "kategoria": "Python",
        "tagi": "argv cli arguments",
        "tresc": (
            "import sys\n\nif len(sys.argv) < 2:\n    print('Usage: script.py <argument>')\n"
            "    sys.exit(1)\n\nargument = sys.argv[1]\nprint(f'Given: {argument}')\n"
        ),
    },
    {
        "nazwa": "Py — iterating over a directory",
        "kategoria": "Python",
        "tagi": "path files directory glob",
        "tresc": (
            "from pathlib import Path\n\nfor file in Path('.').rglob('*.py'):\n"
            "    print(f'{file} — {file.stat().st_size} B')\n"
        ),
    },
    {
        "nazwa": "Py — HTTP request with retry",
        "kategoria": "Python",
        "tagi": "requests http retry",
        "tresc": (
            "import time\nimport requests\n\nurl = 'https://api.example.com/data'\n"
            "for attempt in range(1, 4):\n    try:\n        r = requests.get(url, timeout=10)\n"
            "        r.raise_for_status()\n        print(r.json())\n        break\n"
            "    except requests.RequestException as e:\n"
            "        print(f'Attempt {attempt} failed: {e}')\n        time.sleep(2 ** attempt)\n"
        ),
    },
    {
        "nazwa": "Py — dictionary with default key",
        "kategoria": "Python",
        "tagi": "defaultdict dictionary",
        "tresc": (
            "from collections import defaultdict\n\ngroups = defaultdict(list)\n"
            "for item in data:\n    groups[item['key']].append(item)\n\n"
            "for key, values in groups.items():\n    print(key, len(values))\n"
        ),
    },
    # ── Bash ─────────────────────────────────────────────────────────────────
    {
        "nazwa": "Bash — directory backup with date",
        "kategoria": "Bash",
        "tagi": "backup copy tar date",
        "tresc": (
            "#!/usr/bin/env bash\nset -euo pipefail\n\nSRC=\"./data\"\n"
            "DEST=\"./backup\"\nNAME=\"backup_$(date +%Y%m%d_%H%M%S).tar.gz\"\n\n"
            "mkdir -p \"$DEST\"\ntar -czf \"$DEST/$NAME\" -C \"$SRC\" .\n"
            "echo \"Created: $DEST/$NAME\"\n"
        ),
    },
    {
        "nazwa": "Bash — check if a file exists",
        "kategoria": "Bash",
        "tagi": "file exists condition",
        "tresc": (
            "#!/usr/bin/env bash\nFILE=\"$1\"\n\nif [[ -f \"$FILE\" ]]; then\n"
            "    echo \"File exists: $FILE\"\nelif [[ -d \"$FILE\" ]]; then\n"
            "    echo \"Directory exists: $FILE\"\nelse\n    echo \"Not found: $FILE\"\n"
            "    exit 1\nfi\n"
        ),
    },
    {
        "nazwa": "Bash — download a page with curl",
        "kategoria": "Bash",
        "tagi": "curl http download",
        "tresc": (
            "#!/usr/bin/env bash\nURL=\"https://example.com\"\nOUT=\"page.html\"\n\n"
            "curl -fsSL --retry 3 -o \"$OUT\" \"$URL\" \\\n"
            "    && echo \"Saved: $OUT\" \\\n    || { echo 'Download error'; exit 1; }\n"
        ),
    },
    # ── PowerShell ───────────────────────────────────────────────────────────
    {
        "nazwa": "PS — list of running processes",
        "kategoria": "PowerShell",
        "tagi": "processes get-process",
        "tresc": (
            "Get-Process | Sort-Object CPU -Descending |\n"
            "    Select-Object -First 10 Name, Id, CPU, WorkingSet64 |\n"
            "    Format-Table -AutoSize\n"
        ),
    },
    {
        "nazwa": "PS — check free disk space",
        "kategoria": "PowerShell",
        "tagi": "disk space drive",
        "tresc": (
            "Get-PSDrive -PSProvider FileSystem |\n"
            "    Select-Object Name, @{n='Free [GB]';e={[math]::Round($_.Free/1GB, 2)}},\n"
            "                    @{n='Used [GB]';e={[math]::Round($_.Used/1GB, 2)}} |\n"
            "    Format-Table -AutoSize\n"
        ),
    },
    {
        "nazwa": "PS — export AD users to CSV",
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
        "nazwa": "JS — fetch with error handling",
        "kategoria": "JavaScript",
        "tagi": "fetch http async",
        "tresc": (
            "async function fetchData(url) {\n  try {\n    const res = await fetch(url);\n"
            "    if (!res.ok) throw new Error(`HTTP ${res.status}`);\n"
            "    return await res.json();\n  } catch (err) {\n"
            "    console.error('Error:', err.message);\n    return null;\n  }\n}\n\n"
            "fetchData('https://api.example.com/data').then(console.log);\n"
        ),
    },
    {
        "nazwa": "JS — function debounce",
        "kategoria": "JavaScript",
        "tagi": "debounce delay events",
        "tresc": (
            "function debounce(fn, ms = 300) {\n  let timer;\n"
            "  return (...args) => {\n    clearTimeout(timer);\n"
            "    timer = setTimeout(() => fn(...args), ms);\n  };\n}\n\n"
            "// usage:\n// window.addEventListener('resize', debounce(() => console.log('resize')))\n"
        ),
    },
    # ── Batch ────────────────────────────────────────────────────────────────
    {
        "nazwa": "BAT — copy files with log",
        "kategoria": "Batch",
        "tagi": "copy robocopy log",
        "tresc": (
            "@echo off\nsetlocal\n\nset SRC=C:\\data\nset DST=D:\\backup\n"
            "set LOG=%DST%\\copy.log\n\nrobocopy \"%SRC%\" \"%DST%\" /MIR /NFL /NDL \\\n"
            "  /LOG:\"%LOG%\"\necho Done, log: %LOG%\n"
        ),
    },
    {
        "nazwa": "BAT — ping connectivity check",
        "kategoria": "Batch",
        "tagi": "ping network",
        "tresc": (
            "@echo off\nset HOST=%1\nif \"%HOST%\"==\"\" set HOST=8.8.8.8\n\n"
            "ping -n 4 %HOST% >nul\nif %errorlevel%==0 (\n    echo %HOST% — reply OK\n"
            ") else (\n    echo %HOST% — NO reply\n    exit /b 1\n)\n"
        ),
    },
    # ── SQL ──────────────────────────────────────────────────────────────────
    {
        "nazwa": "SQL — top 10 rows from a table",
        "kategoria": "SQL",
        "tagi": "select top limit",
        "tresc": (
            "-- SQLite / PostgreSQL\nSELECT *\nFROM table_name\nORDER BY id DESC\n"
            "LIMIT 10;\n\n-- SQL Server\nSELECT TOP 10 *\nFROM table_name\n"
            "ORDER BY id DESC;\n"
        ),
    },
    {
        "nazwa": "SQL — create a table with an index",
        "kategoria": "SQL",
        "tagi": "create table index",
        "tresc": (
            "CREATE TABLE IF NOT EXISTS customers (\n    id      INTEGER PRIMARY KEY,\n"
            "    name    TEXT NOT NULL,\n    email   TEXT UNIQUE,\n"
            "    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\n"
            "CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);\n"
        ),
    },
    {
        "nazwa": "SQL — grouping and aggregation",
        "kategoria": "SQL",
        "tagi": "group by count sum",
        "tresc": (
            "SELECT category,\n       COUNT(*)          AS count,\n"
            "       SUM(value)        AS total,\n       AVG(value)        AS average\n"
            "FROM orders\nGROUP BY category\nHAVING COUNT(*) > 1\n"
            "ORDER BY total DESC;\n"
        ),
    },
    # ── HTML ─────────────────────────────────────────────────────────────────
    {
        "nazwa": "HTML — HTML5 page skeleton",
        "kategoria": "HTML",
        "tagi": "skeleton html5 boilerplate",
        "tresc": (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Page title</title>\n</head>\n<body>\n  <h1>Heading</h1>\n"
            "  <p>Page content.</p>\n</body>\n</html>\n"
        ),
    },
]


def starter_items() -> List[Dict[str, str]]:
    """Zwraca kopię zestawu startowego (gotową do snippet_normalize)."""
    return [dict(item) for item in STARTER_SNIPPETS]
