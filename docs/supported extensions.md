# Supported script extensions — CodeMate v4.0

List of script file extensions supported by the application (import, editing,
syntax highlighting, running and export). Source: `RUNNER_EXT`, `EXT_KAT`
and `CATEGORIES` in [baza_skryptow.py](baza_skryptow.py).

> The same list is available in the application: **Help → Supported scripts and files**
> (the window groups entries into *Windows system scripts*, *Programming
> language scripts* and *Data and markup files*; source: `OBSL_GRUPY`).

## Script extensions

| Extension | Category | Runner / interpreter | Description |
| --------- | -------- | -------------------- | ----------- |
| `.py`   | Python     | `python -u` (defaults to `sys.executable`, optionally a venv) | Python scripts. Fully supported: syntax highlighting, autocomplete, linting, runner and version history. |
| `.sh`   | Bash       | Git Bash `bash` (auto-detected in `Program Files\Git\bin`) | Bash / shell scripts. Executed via Git Bash (not WSL `bash.exe`). |
| `.ps1`  | PowerShell | `powershell -NoProfile` (or `pwsh`) with `-ExecutionPolicy Bypass` | Windows PowerShell scripts. Supports `-File` and `-NoProfile`. |
| `.js`   | JavaScript | `node` | JavaScript scripts executed by Node.js. |
| `.bat`  | Batch      | `cmd.exe /c` | Windows batch scripts. Executed directly by `cmd`. |
| `.cmd`  | Batch      | `cmd.exe /c` | Batch script variant — treated identically to `.bat` (same `Batch` category). |
| `.vbs`  | VBScript   | `cscript.exe //nologo` | VBScript scripts executed by Windows Script Host in console mode. |
| `.java` | Java       | `javac` → `java -cp` (via a `.bat` launcher) | Java sources compiled (`javac`) and executed (`java`). Temp file name = main class name. |
| `.jar`  | JAR        | `java -jar` | JAR archives executed via `java -jar`. Binary content stored in the database as **base64** (the `kod` field). |
| `.c`, `.h` | C      | `gcc`/`clang` → `program.exe` (via a `.bat`/`.sh` launcher) | C sources compiled (`gcc -std=c11`, fallback `clang`) and executed. |
| `.cpp`, `.cc`, `.cxx`, `.c++`, `.hpp`, `.hh`, `.hxx` | C++ | `g++`/`clang++` → `program.exe` (via a `.bat`/`.sh` launcher) | C++ sources compiled (`g++ -std=c++17`, fallback `clang++`) and executed. |
| `.rb`   | Ruby       | `ruby` | Ruby scripts executed by `ruby`. |
| `.pl`   | Perl       | `perl` | Perl scripts executed by `perl`. |
| `.php`  | PHP        | `php` | PHP scripts executed by the CLI `php`. |
| `.wsf`  | WSF        | `cscript.exe //nologo` | Windows Script File (XML with a `<job>` element); executed by Windows Script Host. |
| `.hta`  | HTA        | `mshta.exe` | HTML Application executed by the Microsoft HTML Application Host. |
| `.html` | HTML       | `cmd /c start` (browser) | HTML document opened in the default browser. The `.htm` variant = same category. |
| `.css`  | CSS        | — (no process runner) | CSS stylesheets. Highlighting and editing; cannot be executed. |
| `.json` | JSON       | — (no process runner) | JSON documents. Syntax validation on run (`runner_analyze`); no process execution. |
| `.md`   | Markdown   | — (no process runner) | Markdown documents. Highlighting and editing; cannot be executed. The `.markdown` variant = same category. |
| `.sql`  | SQL        | — (no process runner) | SQL queries / scripts. Highlighting and SQL tools; executed via the **Database** tab (SQLite). |
| `.txt`  | Other      | — (no process runner) | Unclassified scripts / notes / other text. Saved and stored, but not executed. |

## Notes

- **Category detection** is based on the file extension at import time
  (`EXT_KAT`): `.py → Python`, `.sh → Bash`, `.ps1 → PowerShell`,
  `.js → JavaScript`, `.bat`/`.cmd → Batch`, `.vbs → VBScript`,
  `.java → Java`, `.jar → JAR`, `.c`/`.h → C`,
  `.cpp`/`.cc`/`.cxx`/`.c++`/`.hpp`/`.hh`/`.hxx → C++`,
  `.rb → Ruby`, `.pl → Perl`, `.php → PHP`,
  `.wsf → WSF`, `.hta → HTA`, `.html`/`.htm → HTML`, `.css → CSS`,
  `.json → JSON`, `.md`/`.markdown → Markdown`, `.sql → SQL`;
  unrecognized files fall into `Other`.
- **Binary files** (`.jar`) are not read as text — on import they are
  encoded to base64 (`jar_base64`), and decoded on export/run
  (`jar_bytes`). The `BIN_EXT` list contains `.jar`.
- **Import filter** in the file selection dialogs:
  `*.py *.sh *.ps1 *.js *.bat *.cmd *.vbs *.java *.jar *.c *.h *.cpp *.cc *.cxx
  *.c++ *.hpp *.hh *.hxx *.rb *.pl *.php *.wsf *.hta *.html *.htm *.css *.json
  *.md *.sql *.txt`.
- **Runner** (`runner_cmd`) builds the command for Python, PowerShell, Bash,
  JavaScript, Batch, VBScript, Java, JAR, C, C++, Ruby, Perl, PHP, WSF, HTA
  and HTML;
  for SQL, CSS, JSON, Markdown and Other it returns no runner. Java is executed
  through a temporary `run_java.bat` launcher (`javac` compilation +
  `java -cp`) created next to the source file. HTML is opened in the default
  browser (`cmd /c start`).
- **JDK (Java/JAR):** the `java`/`javac` paths are resolved by `_java_tool`
  in the order: configured interpreter → sibling in `bin` → `JAVA_HOME\bin` → PATH.
  Before running, `runner_analyze` warns when `javac`/`java` is missing
  (e.g. only a JRE is installed). For JAR archives the `Main-Class` is read
  from `META-INF/MANIFEST.MF`; execution uses UTF-8 encoding flags.
- **Temp file encoding:** Batch — UTF-8 with a `run_batch.bat` wrapper
  (`chcp 65001`, forwarding `%errorlevel%`); VBScript — ASCII within UTF-8, non-ASCII characters in UTF-16 LE with BOM (a Windows Script Host requirement); Java — `javac -encoding UTF-8`;
  C/C++ — a `run_c.bat`/`run_c.sh` launcher compiles `gcc -O2 -std=c11` /
  `g++ -O2 -std=c++17` (fallback `clang`/`clang++`) and executes `skrypt.exe`
  with the user's arguments. `_c_tool` selects the compiler (configured
  interpreter → PATH → clang); `runner_analyze` warns when no compiler is found.
- **Error recognition:** `runner_parse_error` handles Python, PowerShell,
  JavaScript, Bash, Java, C, C++, Batch, VBScript, WSF, Ruby, Perl and PHP.
- **Syntax highlighting** (`_CATEGORY_LEXER`, Pygments): python, bash,
  powershell, javascript, batch, vbscript, java, c, cpp, ruby, perl, php,
  xml (WSF), html (HTA/HTML), css, json, markdown, sql, text.
- **Linter** (static analysis, `lint_code`) runs for the categories: Python
  (ruff → pyflakes → AST), JSON (`json.loads`), HTML/HTA and CSS (brace-closure
  heuristics), plus PHP/Ruby/Perl (`php -l` / `ruby -c` / `perl -c`, when the
  interpreter is available). Other categories are skipped. Detected blocking
  errors trigger a warning before the script is executed.
- **Autocomplete:** Python uses keywords, builtins and symbols from the code;
  other categories use the `AUTO_KEYWORDS` dictionaries
  (Ruby, Perl, PHP, HTML, CSS, JSON, Markdown, HTA, WSF).
- **Interpreter preflight:** `runner_analyze` warns when an interpreter is
  missing from PATH (e.g. `ruby`, `perl`, `php`, `cscript`, `mshta`), before
  the script is executed.
- **Category icons and colors:** `KAT_ICON` and `KAT_COLOR` (`kat_label`) add
  emoji and color accents in the script list, template tree and category
  filters.
- **Code templates** are available for all categories with textual code
  (Python, Bash, PowerShell, JavaScript, SQL, Batch, VBScript, Java, Ruby, Perl,
  PHP, WSF, HTA, HTML, CSS, JSON, Markdown).
