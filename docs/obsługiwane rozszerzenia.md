# Obsługiwane rozszerzenia skryptów — CodeMate v4.0

Lista rozszerzeń plików skryptów obsługiwanych przez aplikację (import, edycja,
podświetlanie składni, uruchamianie i eksport). Źródło: `RUNNER_EXT`, `EXT_KAT`
oraz `CATEGORIES` w [baza_skryptow.py](baza_skryptow.py).

> Ta sama lista jest dostępna w aplikacji: **Pomoc → Obsługiwane skrypty i pliki**
> (okno grupuje pozycje w: *Skrypty systemowe Windows*, *Skrypty języków
> programowania* oraz *Pliki danych i znaczników*; źródło: `OBSL_GRUPY`).

## Rozszerzenia skryptów

| Rozszerzenie | Kategoria | Runner / interpreter | Opis |
| ------------ | --------- | -------------------- | ---- |
| `.py`   | Python     | `python -u` (domyślnie `sys.executable`, opcjonalnie venv) | Skrypty Python. Pełna obsługa: podświetlanie składni, autouzupełnianie, linter, runner i historia wersji. |
| `.sh`   | Bash       | Git Bash `bash` (auto-wykrywanie w `Program Files\Git\bin`) | Skrypty powłoki Bash / shell. Uruchamiane przez Git Bash (nie przez WSL `bash.exe`). |
| `.ps1`  | PowerShell | `powershell -NoProfile` (lub `pwsh`) z `-ExecutionPolicy Bypass` | Skrypty Windows PowerShell. Obsługa `-File` oraz `-NoProfile`. |
| `.js`   | JavaScript | `node` | Skrypty JavaScript uruchamiane przez Node.js. |
| `.bat`  | Batch      | `cmd.exe /c` | Skrypty wsadowe systemu Windows. Uruchamiane bezpośrednio przez `cmd`. |
| `.cmd`  | Batch      | `cmd.exe /c` | Wariant skryptu wsadowego — traktowany identycznie jak `.bat` (ta sama kategoria `Batch`). |
| `.vbs`  | VBScript   | `cscript.exe //nologo` | Skrypty VBScript uruchamiane przez host Windows Script Host w trybie konsolowym. |
| `.java` | Java       | `javac` → `java -cp` (przez launcher `.bat`) | Źródła Java kompilowane (`javac`) i uruchamiane (`java`). Nazwa pliku tymczasowego = nazwa klasy głównej. |
| `.jar`  | JAR        | `java -jar` | Archiwa JAR uruchamiane przez `java -jar`. Zawartość binarna przechowywana w bazie jako **base64** (pole `kod`). |
| `.c`, `.h` | C      | `gcc`/`clang` → `program.exe` (przez launcher `.bat`/`.sh`) | Źródła C kompilowane (`gcc -std=c11`, fallback `clang`) i uruchamiane. |
| `.cpp`, `.cc`, `.cxx`, `.c++`, `.hpp`, `.hh`, `.hxx` | C++ | `g++`/`clang++` → `program.exe` (przez launcher `.bat`/`.sh`) | Źródła C++ kompilowane (`g++ -std=c++17`, fallback `clang++`) i uruchamiane. |
| `.rb`   | Ruby       | `ruby` | Skrypty Ruby uruchamiane przez `ruby`. |
| `.pl`   | Perl       | `perl` | Skrypty Perl uruchamiane przez `perl`. |
| `.php`  | PHP        | `php` | Skrypty PHP uruchamiane przez CLI `php`. |
| `.wsf`  | WSF        | `cscript.exe //nologo` | Windows Script File (XML z elementem `<job>`); uruchamiany przez Windows Script Host. |
| `.hta`  | HTA        | `mshta.exe` | HTML Application uruchamiana przez Microsoft HTML Application Host. |
| `.html` | HTML       | `cmd /c start` (przeglądarka) | Dokument HTML otwierany w domyślnej przeglądarce. Wariant `.htm` = ta sama kategoria. |
| `.css`  | CSS        | — (bez runnera procesu) | Arkusze stylów CSS. Podświetlanie i edycja; bez uruchamiania. |
| `.json` | JSON       | — (bez runnera procesu) | Dokumenty JSON. Walidacja składni przy uruchomieniu (`runner_analyze`); bez uruchamiania procesu. |
| `.md`   | Markdown   | — (bez runnera procesu) | Dokumenty Markdown. Podświetlanie i edycja; bez uruchamiania. Wariant `.markdown` = ta sama kategoria. |
| `.sql`  | SQL        | — (bez runnera procesu) | Zapytania / skrypty SQL. Podświetlanie i narzędzia SQL; wykonywanie przez zakładkę **Baza Danych** (SQLite). |
| `.txt`  | Other      | — (bez runnera procesu) | Skrypty niesklasyfikowane / notatki / inny tekst. Zapisywane i przechowywane, ale bez uruchamiania. |

## Uwagi

- **Wykrywanie kategorii** odbywa się po rozszerzeniu pliku przy imporcie
  (`EXT_KAT`): `.py → Python`, `.sh → Bash`, `.ps1 → PowerShell`,
  `.js → JavaScript`, `.bat`/`.cmd → Batch`, `.vbs → VBScript`,
  `.java → Java`, `.jar → JAR`, `.c`/`.h → C`,
  `.cpp`/`.cc`/`.cxx`/`.c++`/`.hpp`/`.hh`/`.hxx → C++`,
  `.rb → Ruby`, `.pl → Perl`, `.php → PHP`,
  `.wsf → WSF`, `.hta → HTA`, `.html`/`.htm → HTML`, `.css → CSS`,
  `.json → JSON`, `.md`/`.markdown → Markdown`, `.sql → SQL`;
  nierozpoznane trafiają do `Other`.
- **Pliki binarne** (`.jar`) nie są odczytywane jako tekst — przy imporcie są
  kodowane do base64 (`jar_base64`), a przy eksporcie/uruchomieniu dekodowane
  (`jar_bytes`). Lista `BIN_EXT` zawiera `.jar`.
- **Filtr importu** w oknach wyboru plików:
  `*.py *.sh *.ps1 *.js *.bat *.cmd *.vbs *.java *.jar *.c *.h *.cpp *.cc *.cxx
  *.c++ *.hpp *.hh *.hxx *.rb *.pl *.php *.wsf *.hta *.html *.htm *.css *.json
  *.md *.sql *.txt`.
- **Runner** (`runner_cmd`) buduje polecenie dla Python, PowerShell, Bash,
  JavaScript, Batch, VBScript, Java, JAR, C, C++, Ruby, Perl, PHP, WSF, HTA
  oraz HTML;
  dla SQL, CSS, JSON, Markdown i Other zwraca brak runnera. Java uruchamiana
  jest przez tymczasowy launcher `run_java.bat` (kompilacja `javac` + `java -cp`),
  tworzony obok pliku źródłowego. HTML otwierany jest w domyślnej przeglądarce
  (`cmd /c start`).
- **JDK (Java/JAR):** ścieżki `java`/`javac` rozwiązywane są przez `_java_tool`
  w kolejności: wskazany interpreter → sąsiad w `bin` → `JAVA_HOME\bin` → PATH.
  Przed uruchomieniem `runner_analyze` ostrzega, gdy brakuje `javac`/`java`
  (np. zainstalowany tylko JRE). Archiwa JAR: `Main-Class` czytane jest z
  `META-INF/MANIFEST.MF`; uruchomienie z flagami kodowania UTF-8.
- **Kodowanie plików tymczasowych:** Batch — UTF-8 z wrapperem `run_batch.bat`
  (`chcp 65001`, przekazanie `%errorlevel%`); VBScript — ASCII w UTF-8, znaki
  spoza ASCII w UTF-16 LE z BOM (wymóg Windows Script Host); Java — `javac -encoding UTF-8`;
  C/C++ — launcher `run_c.bat`/`run_c.sh` kompiluje `gcc -O2 -std=c11` /
  `g++ -O2 -std=c++17` (fallback `clang`/`clang++`) i uruchamia `skrypt.exe`
  z argumentami użytkownika. `_c_tool` wybiera kompilator (wskazany
  interpreter → PATH → clang); `runner_analyze` ostrzega, gdy brak kompilatora.
- **Rozpoznawanie błędów:** `runner_parse_error` obsługuje Python, PowerShell,
  JavaScript, Bash, Java, C, C++, Batch, VBScript, WSF, Ruby, Perl oraz PHP.
- **Podświetlanie składni** (`_CATEGORY_LEXER`, Pygments): python, bash,
  powershell, javascript, batch, vbscript, java, c, cpp, ruby, perl, php,
  xml (WSF), html (HTA/HTML), css, json, markdown, sql, text.
- **Linter** (analiza statyczna, `lint_code`) działa dla kategorii: Python
  (ruff → pyflakes → AST), JSON (`json.loads`), HTML/HTA oraz CSS (heurystyka
  domknięć), a także PHP/Ruby/Perl (`php -l` / `ruby -c` / `perl -c`, gdy
  interpreter jest dostępny). Pozostałe kategorie są pomijane. Wykryte błędy
  blokujące powodują ostrzeżenie przed uruchomieniem skryptu.
- **Autouzupełnianie:** Python korzysta ze słów kluczowych, wbudowanych funkcji
  i symboli z kodu; pozostałe kategorie ze słowników `AUTO_KEYWORDS`
  (Ruby, Perl, PHP, HTML, CSS, JSON, Markdown, HTA, WSF).
- **Preflight interpreterów:** `runner_analyze` ostrzega, gdy brakuje
  interpretera w PATH (np. `ruby`, `perl`, `php`, `cscript`, `mshta`), jeszcze
  przed uruchomieniem skryptu.
- **Ikony i kolory kategorii:** `KAT_ICON` i `KAT_COLOR` (`kat_label`) dodają
  emoji oraz akcent kolorystyczny w liście skryptów, drzewie szablonów i
  filtrach kategorii.
- **Szablony kodu** dostępne są dla wszystkich kategorii z kodem tekstowym
  (Python, Bash, PowerShell, JavaScript, SQL, Batch, VBScript, Java, Ruby, Perl,
  PHP, WSF, HTA, HTML, CSS, JSON, Markdown).
