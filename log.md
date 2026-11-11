# Log zmian — CodeMate

Dziennik zmian kategoryzowany **według wersji oprogramowania**.
Każda wersja grupuje zmiany; wpisy w obrębie wersji są w kolejności chronologicznej.

Format wpisu: `RRRR-MM-DD — zakres (Faza/poz.) — opis`.

## v3.9 (w toku)

### 2026-11-06 — Zmiana nazwy programu na CodeMate
- Zmieniono nazwę produktu we wszystkich plikach: `Baza Skryptów` /
  `BazaSkryptow` / `BAZA_*` → `CodeMate` — nagłówek okna, okno „O programie",
  `--version`, tytuł API, autor commitów Git, sygnatura webhooka
  (`X-CodeMate-Signature`), zmienne środowiskowe (`CODEMATE_API_TOKEN`,
  `CODEMATE_API_WEBHOOK_URL`, prefiks `CODEMATE_` w konfiguracji),
  `KEYRING_SERVICE`, `User-Agent` marketplace, dokumentacja i testy.
- Zmieniono nazwę klasy głównej `BazaSkryptow` → `CodeMate` (wraz ze wszystkimi
  odwołaniami w testach i self-check AST).
- Poprawiono baner nagłówka (`header_title`) — zawierał „Baza  Skryptów"
  z podwójnymi spacjami, co umknęło pierwszej zamianie; teraz
  `CodeMate  v{ver}` w obu językach.
- **Bez zmian:** nazwy plików i danych (`baza_skryptow.py`, `baza_skryptow.json`,
  `.cfg`, `.log`, `.sekrety.json`, `.snippety.json`) oraz rozszerzenie `.bsdb` —
  zachowują kompatybilność z istniezącymi danymi użytkownika.
- **Weryfikacja:** `--version` → `CodeMate v3.9 (schema 2)`, `--self-check`
  OK, `pytest` — **500 testów, 100% zaliczone**.

### 2026-11-06 — Bump wersji na 3.9
- Ustawiono bieżącą wersję aplikacji (`APP_VER`), nagłówka okna, okna
  „O programie”, dokumentacji Sphinx i plików w `dokuments/` na `3.9`.
- Zresetowano `log.md` — nowy dziennik zmian dla wersji 3.9.

### 2026-11-06 — Obsługa C i C++
- Nowe kategorie **C** i **C++**: mapy `CATEGORIES`, `_CATEGORY_LEXER`
  (Pygments `c`/`cpp`), `KAT_ICON`/`KAT_COLOR`, `RUNNER_EXT`, `EXT_KAT`
  (`.c`/`.h` → C; `.cpp`/`.cc`/`.cxx`/`.c++`/`.hpp`/`.hh`/`.hxx` → C++),
  wpisy w `OBSL_GRUPY` i filtrach importu/modułów.
- Runner: `runner_save_temp` zapisuje `skrypt.c`/`skrypt.cpp` i tworzy
  launcher `run_c.bat` (Windows) / `run_c.sh` (POSIX) — kompilacja
  `gcc -O2 -std=c11` / `g++ -O2 -std=c++17` (fallback `clang`/`clang++`,
  wybór przez `_c_tool` z uwzględnieniem interpretera) i uruchomienie
  programu z argumentami użytkownika.
- `runner_analyze` sprawdza obecność `main()` i ostrzega o braku
  kompilatora w PATH; `runner_parse_error` parsuje błędy `gcc`/`clang`
  (`plik:linia:kol: error:`).
- Słowa kluczowe autouzupełniania `AUTO_KEYWORDS` dla C i C++.
- Testy: `TestCCategories`, `TestCRunnerCmd`, `TestCRunnerSaveTemp`,
  `TestCRunnerAnalyze`, `TestCParseError` w `tests/test_runner_languages.py`;
  dokumentacja `dokuments/obsługiwane rozszerzenia.md`.

### 2026-11-06 — Pod-zakładki w Ustawieniach i Personalizacja listy skryptów
- Zakładka **Ustawienia** podzielona na pod-zakładki **⚙ Ogólne**
  (baza danych, runner, język, Git, pluginy, kosz, powiadomienia) i
  **🎨 Personalizacja** (wygląd ogólny + wygląd listy skryptów).
- Nowa sekcja **Wygląd listy skryptów**: naprzemienne kolory wierszy,
  kolory wiersza nieparzystego/parzystego i zaznaczenia (puste = motyw),
  wysokość wiersza (16–64 px), rozmiar czcionki listy (7–20 pt).
- Lista skryptów ma własny styl `ScriptList.Treeview`; `_apply_list_appearance()`
  stosuje ustawienia na żywo (podgląd), po zapisie, zmianie motywu i czcionki.
- Nowe klucze konfiguracji: `list_alt_rows`, `list_bg_odd`, `list_bg_even`,
  `list_sel_bg`, `list_row_height`, `list_font_size` — dodane do `CFG_KEYS`
  i modelu `AppConfig` (src/config.py).
- Przyciski Zapisz/Przywróć domyślne przeniesione do stopki wspólnej dla
  obu pod-zakładek; każda pod-zakładka ma własny przewijany formularz.
- Tłumaczenia EN dla nowych etykiet; dokumentacja w `docs/usage.rst`.
- **Wybór koloru czcionki:** obok comboboxa czcionki w Personalizacji
  dodano przycisk 🎨 otwierający systemowy wybór koloru; kolor zapisuje
  się w `fg_text` i nadpisuje `FG_TEXT` + `FG_WHITE` w palecie motywu,
  więc obejmuje tekst edytorów, list i etykiet.

### 2026-11-06 — Pełna obsługa kółka myszy we wszystkich widgetach
- **Uogólnienie przewijania:** stary handler `_vscroll_smart`/`_hscroll`/
  `_scroll_parent` opierał się na `isinstance` (tylko `Text`/`Listbox`/
  `Treeview`/`Canvas`) i nie przenosił zdarzenia dalej po osiągnięciu края.
  Zastąpiono je generycznym `_scroll_axis(widget, axis, units)` — duck-typing
  (`yview`/`yview_scroll`, `xview`/`xview_scroll`) pokrywa każdy przewijany
  widget, w tym `Entry`/`Spinbox`/`Combobox` w poziomie.
- **Łańcuch hierarchii + propagacja:** kółko przewija najbliższy przewijany
  widget od kursora w górę przez przodków; gdy pozycja się nie zmienia
  (widget na krańcu zakresu), zdarzenie propaguje do kontenera — działa też
  nad dziećmi wewnątrz przewijanych `Canvas`.
- **Shift/Alt + kółko:** poziome przewijanie z fallbackiem na pionowe, gdy
  w łańcuchu brak przewijanego w poziomie.
- **Pan środkowym przyciskiem:** `_pan_scroll` używa tego samego łańcucha —
  działa na każdym przewijanym widżecie i obu osiach jednocześnie.
- **Testy:** [tests/test_startup_lazy_tabs.py](tests/test_startup_lazy_tabs.py)
  — zaktualizowane testy handlera + nowe: fallback pionowy, `_scroll_axis`
  na prawdziwych widgetach Tk (Canvas z dziećmi).
- **Dokumentacja:** sekcja „Obsługa myszy" w [docs/usage.rst](docs/usage.rst).
- **Weryfikacja:** test dymny na żywych widgetach Tk (Canvas+etykiety,
  Text, propagacja z krótkiego Text, Shift na Entry/Text) + `pytest` —
  **500 testów, 100% zaliczone**.

### 2026-11-06 — Środowisko testowe na Pythonie 3.14 + pokrycie testami modułów src/
- **Naprawa środowiska:** `.venv` działało na Pythonie 3.15.0a8 (stary alfa) —
  `pytest` nie startował (`anyio`: `NameError: sentinel`, `pydantic_core` i
  `coverage.tracer`: niezgodny ABI). Utworzono nowe `.venv` na Pythonie 3.14.4
  i zainstalowano `requirements.txt` od nowa; stare środowisko zachowano jako
  `.venv.broken-315`.
- **Nowe testy:** 102 testy podnoszące pokrycie najsłabszych modułów —
  [tests/test_plugin_system.py](tests/test_plugin_system.py) (ładowanie pluginów
  z plików, błędy `on_load`/`on_unload`/`on_enable`/`on_disable`, hooki),
  [tests/test_secrets.py](tests/test_secrets.py) (plik klucza, keyring,
  degradacja bez `cryptography`, błędy zapisu),
  [tests/test_git_integration.py](tests/test_git_integration.py) (wszystkie
  ścieżki `_initialized=False`, błędy komend, `sync_file`, `set_remote`,
  `status`), [tests/test_api.py](tests/test_api.py) (`_execute_script` z
  fałszywym `Popen`, timeout/anulowanie, `finish_job`, endpointy, `main()`).
- **Wynik pokrycia `src/`:** 81% → **97%**; `plugin_system.py` i
  `git_integration.py` 100%, `api.py` i `secrets.py` 99% (pozostałe linie to
  `os.chmod` nie-Windows i strażnik `__main__`).
- **Weryfikacja:** `pytest` — **498 testów, 100% zaliczone**.

### 2026-11-06 — Tłumaczenia chmurek/powiadomień i angielski jako domyślny język
- **Naprawiono nieprzetłumaczone komunikaty:** tooltipy (chmurki) wszystkich
  widgetów, powiadomienia gestów (toast: eksport/import bazy, zakładki,
  odświeżenie), toast zoomu czcionki oraz etykiety stanu/przycisku harmonogramu
  — wcześniej miały zaszyte polskie napisy. Teraz `_tooltip_show` i
  `_show_gesture_toast` tłumaczą tekst w momencie wyświetlenia (`_tr`),
  a zoom używa klucza `_t("toast_font_size")`; dodano ~30 pozycji do
  `MENU_EN`/`_EN_KEYED` w `src/lang/en.py`.
- **Angielski jako język domyślny:** `_UI_LANG`, `CFG_KEYS["language"]`,
  `AppConfig.language` (w tym `from_dict` i walidator fallbacku) oraz
  fallback `_set_lang` ustawiono na `"en"`. Polski pozostaje dostępnym
  językiem źródłowym; zapisany wybór użytkownika jest respektowany.
- **Testy:** zaktualizowano oczekiwania domyślnego języka w
  `tests/test_i18n.py` i `tests/test_config.py`; dodano testy pokrywające
  tłumaczenia tooltipów/toastów/harmonogramu; w dwóch testach ustawiono
  `_set_lang("pl")` jawnie (niezależność od kolejności).
- **Weryfikacja:** `pytest` — **521 testów, 100% zaliczone**;
  `--self-check` OK; `--version` → `CodeMate v3.9 (schema 2)`.

### 2026-11-06 — Stopka z podpisem w raporcie pokrycia HTML
- Dodano `conftest.py` z hookiem `pytest_terminal_summary` (trylast), który
  po raporcie `--cov-report=html` dopisuje na dole każdego `htmlcov/*.html`
  wyśrodkowany napis „ Sebastian Januchowski ⌁ polsoft.ITS™ Dev"
  (wewnątrz `<footer>`, pod linią atrybucji coverage.py).

### 2026-11-06 — Pokrycie src/ 100%
- Dodano testy na pozostałe niepokryte gałęzie: walidatory `AppConfig`
  (backup_count/timeout/font_size), obsługa błędów `load_from_file`,
  wszystkie ścieżki błędów `exe_export.build_executable` (brak interpretera,
  brak PyInstallera, timeout, brak artefaktu, ikona .ico), walidacje
  `plugin_marketplace` (rozmiar odpowiedzi, kształt katalogu, wpisy, checksumy,
  manifest) oraz `vdrive` (zły schema, niepoprawny id dysku, settings nie-dict).
- Oznaczono `# pragma: no cover` linie zależne od platformy:
  `sys.exit(main())` w `api.py` i `os.chmod` POSIX w `secrets.py`.
- **Wynik:** `src/` — **100%** (1069 statementów, 0 niepokrytych);
  `pytest` — **543 testów, 100% zaliczone**.

### 2026-11-06 — Naprawa martwych przycisków w panelu Diagnostyka i Naprawa
- **Przyczyna:** zakładki główne ładują się leniwie (`_main_tabs_built`).
  Przyciski w zakładce Narzędzia (Diagnostyka, Naprawa, Testy, Odśwież)
  oraz pozycje menu wołały metody korzystające z widżetów zakładki Moduły,
  która mogła nie istnieć — wyjątek `AttributeError` w callback Tkintera
  nie daje żadnej widocznej reakcji w GUI.
- **Fix:** dodano `_ensure_moduly_built()` (buduje zakładkę Moduły bez
  przełączania) oraz nawigację `_menu_pokaz_mod()` przed uruchomieniem
  `_run_diag`, `_naprawa_scan`, `_run_testy` — wyniki i tak trafiają do
  odpowiednich pod-zakładek Modułów, więc przycisk przenosi tam użytkownika.
- `_mod_refresh_info`, `_diag_save_log`, `_naprawa_save`,
  `_mod_copy_info`, `_mod_export_info`, `_testy_export` dostają
  `_ensure_moduly_built()` — naprawia też pozycje menu
  „Diagnostyka bazy", „Naprawa bazy", „Odśwież widok" (F5),
  „Odśwież info o modułach" i „Informacje o środowisku".
- **Testy:** autouse fixture w `conftest.py` resetuje `_UI_LANG` na `en`
  po każdym teście (izolacja i18n między plikami testów).
- **Weryfikacja:** `pytest` — **543 testów, 100% zaliczone**;
  pokrycie `src/` 100%.

### 2026-11-06 — Minimalny rozmiar okna dopasowany do polskiego UI
- Dodano `CodeMate._update_minsize()` — mierzy `winfo_reqwidth/reqheight`
  przy języku **PL** (najszerszy), więc minimalny rozmiar okna jest taki
  sam w obu językach, a treść nie jest ucina. Rozmiar tylko rośnie
  (`_min_w/_min_h`), by nigdy nie spaść poniżej największego wymaganego.
- Wywoływane automatycznie przy każdej zmianie widocznej treści:
  zakładki główne i pod-zakładki (Skrypty, Szukaj, Moduły, Baza, Venv,
  VDrive, Runner, Ustawienia), przełącznik języka (`_retranslate_ui`)
  oraz start aplikacji. Jeśli okno jest mniejsze od minimum — jest
  powiększane do wymaganego rozmiaru.
- Przy okazji naprawiono rekurencję: `_build_moduly_frame` woła
  `_mod_refresh_info` w trakcie budowy, co przy `_ensure_moduly_built`
  powodowało nieskończoną rekursję — dodano strażnika `_moduly_building`
  i rozdzielono budowę na `_build_moduly_frame_inner`.
- **Weryfikacja:** `pytest` — **543 testów, 100% zaliczone**;
  test dymny GUI: minsize rośnie do 1242×703 po otwarciu Modułów,
  diagnostyka/naprawa/testy działają.

### 2026-11-06 — Optymalizacja przełączania zakładek (usunięcie zacinań)
- **Przyczyna:** `_update_minsize()` przy każdym kliknięciu w pod-zakładkę
  wykonywał dwa pełne przebiegi `_retranslate_ui` (przełączenie na PL
  i z powrotem) + `update_idletasks` — setki milisekund na klik.
- **Fix:** podział na tryb tani i drogi —
  `_update_minsize()` mierzy tylko bieżący język (koszt ~0 ms po
  pierwszym wywołaniu); `_update_minsize(force_pl=True)` z pełnym
  pomiarem PL uruchamia się tylko przy zmianie języka i pierwszym
  zbudowaniu zakładki (raz na zakładkę). Minimalny rozmiar wciąż
  pokrywa polski UI — po wejściu w PL dokłada się dokładny pomiar
  widocznej treści.
- Zmieniono sygnaturę `_update_minsize(force_pl=False)`; w `_sel_main`
  i `_sel_sub` `force_pl` ustawiane tylko gdy faktycznie budowano
  zakładkę (`built_now`).
- **Weryfikacja:** `pytest` — **543 testów, 100% zaliczone**;
  pomiar czasu: tani tryb ~0 ms, pełny ~460 ms (tylko raz na zakładkę).

### 2026-11-06 — Wycofanie przełączania języka przy zmianie zakładek
- **Problem:** `_update_minsize(force_pl=True)` wywoływany przy pierwszym
  otwarciu każdej zakładki wykonywał dwa pełne `_retranslate_ui`
  (PL → pomiar → powrót) — wielokrotne, widoczne migotanie języka
  i duże opóźnienia przy przełączaniu zakładek.
- **Fix:** `_update_minsize()` mierzy wyłącznie bieżący język — zero
  przełączeń języka w trakcie nawigacji. Polski (najszerszy) wymiar
  pokrywany jest przez `_update_minsize_boot_pl()` wołane **raz**
  w `__init__` przed `mainloop` (niewidoczne dla użytkownika);
  `_min_w/_min_h` trzymają running max, więc minsize nigdy nie
  spada poniżej polskiego wymiaru dla obu języków.
- **Weryfikacja:** `pytest` — **543 testów, 100% zaliczone**;
  smoke test: wszystkie 12 zakładek głównych i 9 pod-zakładek
  Skryptów przełączają się bez błędów.

### 2026-11-06 — Zakładka Statystyki: zwarta siatka 3×1
- Przestawiono panele statystyk: kolumna środkowa zawiera teraz
  **Najczęstsze tagi (top 15)** u góry i **Największe skrypty (top 10)**
  pod spodem; **Najczęściej uruchamiane — runner** zajmuje prawą
  kolumnę na tej samej wysokości co pozostałe trzy panele.
- Usunięto pełnoszerokościowy dolny pas „Most run" — zakładka ma
  standardową wysokość okna (jeden rząd trzech równych kolumn:
  kategorie | tagi+największe | runner).
- Nazwy widgetów (`_stat_tag_text`, `_stat_size_text`, `_stat_run_text`)
  bez zmian — `_stat_refresh` i eksport raportu działają jak poprzednio.

### 2026-11-06 — Korekta układu Statystyk: siatka 2×2
- Poprawiono interpretację: zamiast 3 kolumny + stack w środku, panele
  statystyk tworzą siatkę **2×2** — górny rząd: Skrypty wg kategorii |
  Najczęstsze tagi; dolny rząd: Najczęściej uruchamiane — runner |
  Największe skrypty (pod tagami, ta sama prawa kolumna).
- Wszystkie 4 panele identycznej wielkości (`expand` w obu osiach,
  wspólne `_stat_panel`/`_stat_text`) — standardowy rozmiar okna,
  „Most run" nie jest już pełnoszerokościowy.
- Wymagana szerokość zakładki spadła ~1786 → ~1198 px.

### 2026-11-06 — Kontrast przycisków w jasnym motywie
- Problem: przyciski akcji miały zaszyte ciemne kolory tła
  (`#603030`, `#2f6b3f`, `#2a5e2a`, `#5e2a2a`, `#4a90d9`…), które nie
  podlegały mapowaniu motywów — w motywie **jasnym** `fg=FG_WHITE`
  staje się ciemny, więc napis był ciemny na ciemnym tle (np. przycisk
  „✕ Opróżnij kosz" w Statystykach i Koszu).
- Rozwiązanie: nowe klucze palety w `src/theme.py` — `BTN_OK`,
  `BTN_OK_HOVER`, `BTN_ERR`, `BTN_ERR_HOVER`, `BTN_ACCENT` — z pastelowymi
  wariantami dla motywu jasnego (jasne tło + ciemny napis) i nasyconymi
  dla ciemnego/kontrastowego. Wszystkie przyciski używają teraz tych
  globalnych kolorów zamiast literalów — dodanie klucza do presetu
  automatycznie naprawia istniejące widżety przy przełączaniu motywu.
- Zmieniono ~50 miejsc: Statystyki, Kosz, Edytor, Runner, Baza danych,
  Venv, Pluginy, Harmonogram, menu (podświetlenie pozycji), szukanie.
- Weryfikacja na żywym GUI: w motywie jasnym „Empty trash" ma tło
  `#dfe3ec` i napis `#c0392b`; w ciemnym `#2e3248` / `#e07070`.
- `pytest`: 543 testów, pokrycie `src/` 100%.

### 2026-11-06 — Przyciski w motywie jasnym: głębsze tło
- Warianty jasne kluczy `BTN_*` przyciemniono i nasycono
  (`BTN_DARK #dfe3ec→#cfd5e2`, `BTN_OK #cdeccd→#a8d4ab`,
  `BTN_ERR #ffd6d6→#eeb3b3`, `BTN_ACCENT #bcd4f6→#9cbdf0`;
  hover odpowiednio ciemniejsze) — przyciski są wyraźnie oddzielone
  od tła paneli i wyglądają na „uniesione".

### 2026-11-06 — Rozbudowa zakładki Pluginy
- **Nowe funkcje UI:** wyszukiwarka/plugin filter, kolumna „Hooki",
  kolorowy status (zielony=włączony/szary=wyłączony), podwójny klik =
  szczegóły, pasek statusu z liczbą błędów ładowania.
- **Nowe przyciski:** Przeładuj (reload pluginu z pliku bez restartu),
  Usuń (kasuje plik .py + wyładowuje), Folder (otwiera katalog
  `plugins/`), Hooki (okno z listą hooków, opisami i licznikami
  callbacków + błędy ładowania).
- **Szczegóły pluginu** to teraz okno (nie messagebox): metadane, ścieżka
  pliku, zarejestrowane hooki, opis + akcje (Przeładuj/Otwórz plik/Usuń).
- **Trwałość stanu:** wyłączone pluginy zapisują się w configu
  (`plugins_disabled`, CSV) i są wyłączane automatycznie po starcie.
- **`src/plugin_system.py`:** `load_errors` (lista błędów per plik),
  `_load_plugin_file` (refaktor), `reload_plugin`, `get_plugin_path`,
  `hook_usage`, `BasePlugin.registered_hooks`.
- **Podpięte hooki, które wcześniej nie były wywoływane:**
  `before_script_run`/`after_script_run` (Runner), `before_db_load`/
  `after_db_load` (autoload + otwieranie bazy), `before_db_save`/
  `after_db_save` (save_db), `on_app_start`/`on_app_close`.
- Tłumaczenia EN dla nowych etykiet; `pytest`: 552 testów, `src/` 100%.

### 2026-11-06 — Przykładowy plugin + kreator pluginów
- **`plugins/event_logger.py`** — przykładowy plugin pokazujący użycie
  **wszystkich** hooków: skrypty (zapis/uruchomienie), baza danych
  (load/save), cykl życia aplikacji. Poprawiono sygnatury handlerów do
  realnych argumentów wywoływanych hooków i dodano guard przed
  podwójnym handlerem FileHandler przy reloadzie.
- **Kreator pluginów** — nowy przycisk „＋ Nowy" w zakładce Pluginy:
  dialog z polami (nazwa pliku, nazwa, kategoria, opis) generuje
  `plugins/<nazwa>.py` z gotowego szablonu `BasePlugin` (z komentarzami
  dostępnnych hooków), waliduje nazwę pliku, od razu ładuje plugin
  i zaznacza go na liście.
- Tłumaczenia EN dla etykiet kreatora; `pytest`: 552 testów, `src/` 100%.

### 2026-11-06 — Pluginy: wyłączanie/włączanie naprawdę wyłącza hooki
- **Fix:** wcześniej `disable_plugin`/`unload_plugin` ustawiały tylko
  flagę `enabled` — zarejestrowane callbacki hooków **nadal się
  wywoływały** (plugin „wyłączony" pracował dalej).
- `BasePlugin` śledzi teraz pary `(hook, callback)` w
  `_hook_callbacks`; `PluginManager._unregister_plugin` usuwa je ze
  wszystkich hooków przy wyłączeniu i wyładowaniu, a `enable_plugin`
  rejestruje je ponownie. `PluginHook.register` deduplikuje callbacki
  (bez podwójnych wywołań po wielokrotnym enable).
- `unload_plugin` czyści też wpis w `_plugin_files`.
- 5 nowych testów cyklu życia hooków; `pytest`: 557 testów, `src/` 100%.

### 2026-11-06 — Kreator pluginów: metadane, hooki, aliasy komend
- **Rozbudowany kreator „＋ Nowy"**: pola wersja, autor, strona
  domowa, licencja, **alias komendy** (np. `/stats`) oraz **checklista
  hooków** — wybrane hooki dostają automatycznie wygenerowane
  `register_hook` w `on_load` i gotowe stub-metody `_on_*` z opisem
  i `TODO`.
- **System komend/aliasów pluginów** (`plugin_system.py`):
  plugin deklaruje `PLUGIN_COMMANDS = {alias: opis}` i implementuje
  `on_command(alias, args)`; `PluginManager.plugin_commands()` zbiera
  aliasy włączonych pluginów, `run_command(alias, args)` je wykonuje.
- **Nowe okno „? Komendy"** w zakładce Pluginy — help aliasów
  (odpowiednik `/?`): lista komend z pluginem i opisem, pole argumentów
  i przycisk Uruchom. Szczegóły pluginu pokazują też jego komendy.
- Walidacja aliasu (litery/cyfry/_/-/, opcjonalny prefiks `/`).
- 7 nowych testów `plugin_commands`/`run_command`; `pytest`: 564
  testów, `src/` 100%.

### 2026-11-06 — Komendy nawigacyjne dla pluginów
- **`_nav_goto(target)`** — publiczne API nawigacji w aplikacji:
  `"tab_<klucz>"` dla zakładek głównych i `"tab_skrypty:<pod>"` dla
  pod-zakładek Skryptów. Komendy zakładek zapisane w
  `_main_tab_cmds`/`_sub_tab_cmds`.
- **Kreator pluginów:** nowa checklista **„Komendy nawigacji"** —
  21 aliasów (`/skrypty`, `/runner`, `/skrypty/statystyki`, `/kosz`…)
  z przyciskami **Zaznacz/Odznacz wszystkie**. Wybrane aliasy są
  dopisywane do `PLUGIN_COMMANDS` generowanego pluginu, a
  `on_command` dispatchuje je przez `_nav_goto` — plugin może
  natychmiast przenosić użytkownika po UI.
- Aliasy hierarchiczne (`/skrypty/statystyki`) — brak kolizji
  między zakładką główną a podzakładką.
- `pytest`: 564 testów, `src/` 100%.

### 2026-11-06 — Kreator pluginów wydzielony do src/modules/
- Nowy moduł **`src/modules/plugin_creator.py`** — rozszerzenie
  możliwości kreatora: walidatory (`valid_plugin_filename`,
  `valid_alias` — alias zezwala teraz też na `/` wewnątrz), katalog
  `NAV_COMMANDS` (21 aliasów nawigacji) i generator `plugin_source`.
- `baza_skryptow.py` deleguje do modułu (import w try/except ze
  wskaźnikiem `_CREATOR_AVAILABLE`); zakładka Pluginy używa
  walidatorów i katalogu z modułu — kod główny schudł o ~100 linii.
- 17 nowych testów (`tests/test_plugin_creator.py`) — walidatory,
  struktura katalogu, kompilacja i **faktyczne ładowanie** wygenerowanego
  pluginu przez `PluginManager`.
- `pytest`: 581 testów, `src/` 100% (w tym nowy moduł).

### 2026-11-06 — Uzupełnienie tłumaczeń PL↔EN (pełny audyt UI)
- **AST audit** `baza_skryptow.py`: wszystkie literały `text=`/`title=`
  w widgetach Tk (wcześniej ~74 nieprzetłumaczone: przyciski, etykiety,
  checkboxy w zakładkach Venv/Baza/VDrive/Runner/Harmonogram/Ustawienia)
  owrapnięte we `_trw()` — rejestr `_i18n_live` daje tłumaczenie
  **na żywo** przy przełączaniu PL↔EN.
- Nowe helpery **`_trc()`/`_cb_canon()`** + rejestr `_i18n_combos`:
  comboboxy z kanonicznymi wartościami PL (`global`/`skrypt`,
  `Wszystkie`+kategorie, `nazwa`/`kategoria`/`tagi`, limity) pokazują
  wartości przetłumaczone, a logika czyta kanoniczną wartość —
  dane/zapisy (sekrety, filtry, sortowanie) zostają nietknięte.
- Tytuły dialogów plikowych (`askopenfilename`/`asksaveasfilename`/
  `askdirectory`) i `simpledialog` owrapnięte w `_tr()`.
- `src/lang/en.py`: +~170 wpisów MENU (etykiety widgetów, komunikaty
  messagebox, tytuły dialogów, kreator pluginów); `Wszystkie` → `All`.
- `pytest`: 587 testów, `src/` 100%.

### 2026-11-06 — Ustawienia: sekcja Baza danych w jednym poziomym pasku
- Trzy opcje DB (plik bazy + przycisk „Otwórz folder", kopie zapasowe,
  autosave) umieszczone w jednym rzędzie `db_bar` (pack) — wcześniej
  zajmowały 3 osobne wiersze siatki.
- Etykiety zarejestrowane w `_ust_i18n` — tłumaczą się na żywo PL↔EN.
- `pytest`: 587 testów, `src/` 100%.

### 2026-11-06 — Ustawienia: Git i pozostałe sekcje w poziomych paskach
- Sekcja **Git**: obie opcje (integracja + auto-commit) w jednym pasku
  z pionowym separatorem — analogicznie do Bazy danych.
- Sekcje **Pluginy**, **Kosz**, **Powiadomienia**: etykieta + kontrolka
  w jednym wierszu (wcześniej 2 wiersze na opcję).
- Wszystkie etykiety w `_ust_i18n` — tłumaczenia na żywo.
- `pytest`: 587 testów, `src/` 100%.

# ── Rejestr zmian (2026-11-07) ────────────────────────────────────────────────
# AutoCompleter (baza_skryptow.py):
#   * dopasowanie substring — gdy nic nie zaczyna się od prefiksu, listowane
#     są nazwy zawierające prefiks w środku (fallback w AutoCompleter.popup).
#   * podpowiedzi metod/atrybutów po kropce ("obj."): AutoCompleter.ATTRS
#     (metody str/list/dict/set/tuple), wnioskowanie typów z przypisań
#     literałów (_infer_types), atrybuty self.* (_collect_self_attrs)
#     oraz symbole modułów standardowych (PY_MODULE_ATTRS: os, sys, json,
#     re, math, random, time, datetime, pathlib, subprocess, tkinter,
#     sqlite3, shutil, typing).
#   * auto-popup: wpisanie prefiksu o długości >= AUTO_OPEN_LEN (3) otwiera
#     okno podpowiedzi bez Ctrl+Space (AutoCompleter._on_key).
# i18n:
#   * _missing_en.json (79) i _missing2.json (71) zweryfikowane — wszystkie
#     teksty mają już tłumaczenia EN w src/lang/en.py; braki: 0.
# Weryfikacja: pytest 587 passed, 0 failed (100% pokrycia src/).
# Do pełnej weryfikacji zainstalowano: Python 3.14.4 (venv wskazywał na
#   nieistniejący katalog) oraz Git 2.56 (winget) — testy git_integration
#   wymagają git w PATH.

# ── Rejestr zmian (2026-11-07, kont.) — zawieszanie zakładki Git ─────────────
# Przyczyna: zakładka Git wykonywała synchronicznie (w wątku UI) wiele komend
#   subprocess git (status/branch/log -50), a push/pull mogły wisieć bez
#   ograniczeń (brak timeoutu — np. okno poświadczeń). Na tej maszynie każde
#   wywołanie git = 60–140 ms, więc UI zamierało na sekundy.
# Naprawy:
#   * src/git_integration.py: COMMAND_TIMEOUT = 30 s na subprocess.run +
#     obsługa subprocess.TimeoutExpired (timeout dla push/pull/credential).
#   * baza_skryptow.py: _git_refresh() asynchroniczne — status/branches/
#     history w wątku tła (threading), wynik aplikowany przez self.after()
#     w wątku UI; ochrona przed nieaktualnymi wynikami (_git_refresh_seq);
#     wskaźnik "sprawdzanie…" w podsumowaniu.
#   * _git_show_change(): używa buforowanego _git_last_untracked zamiast
#     ponownego wywołania git status przy każdym kliknięciu.
#   * _git_apply_refresh(): nowa metoda aplikująca wynik w wątku UI.
# Weryfikacja: pytest 587 passed (git_integration 99% — brak tylko gałęzi
#   FileNotFoundError), self_check: 0 problemów, składnia OK.
# ── Rejestr zmian (2026-11-07, kont.) — wykrywanie Git poza PATH ──────────────
# Problem: 4 testy integracyjne git_integration fail (FileNotFoundError) —
#   Git 2.56 zainstalowany w C:\Program Files\Git\cmd, ale brak wpisu w PATH
#   bieżącej sesji (typowe po instalacji winget bez ponownego logowania).
#   Dotyczyło też samej aplikacji: zakładka Git deklarowała "Git is not installed".
# Naprawy:
#   * src/git_integration.py: nowa funkcja find_git() — shutil.which("git"),
#     a gdy nie znajdzie, przeszukuje znane lokalizacje instalacji Git for
#     Windows (Program Files / Program Files (x86) / LocalAppData, cmd i bin);
#     wynik cache'owany na czas życia procesu. _check_git_repo() i
#     _run_git_command() używają find_git() zamiast gołego "git".
#   * tests/test_git_integration.py: _real_git() używa find_git() i wywołuje
#     pytest.skip(), gdy git nieobecny (przenośność CI/maszyn bez gita).
# Weryfikacja: pytest 593 passed, 0 failed; self-check: 0 problemów.
# ── Rejestr zmian (2026-11-07, kont.) — Runner: naprawa brakujących funkcji ──
# Problem: menu Run → "Harmonogram — plany…" wywoływało self._runner_show_pane,
#   który istnieje dopiero po zbudowaniu panelu Runner (lazy tabs) — click na
#   świeżym starcie rzucał AttributeError. Ponadto "Uruchom w nowej konsoli"
#   (Ctrl+F9) ignorował parametr new_console w _runner_run_form — uruchamiał
#   zawsze w tej samej konsoli.
# Naprawy:
#   * baza_skryptow.py: nowa metoda CodeMate._runner_open_pane(key) — otwiera
#     zakładkę Runner, buduje panel na żądanie (lazy) i po budowie przełącza
#     pod-zakładkę (run/hist/plan/stats); retry co 120 ms aż panel gotowy.
#   * menu Run: "Harmonogram — plany…" → self._runner_open_pane("plan").
#   * _runner_run_form(): parametr new_console jest teraz respektowany
#     (wywołuje _runner_start_new_console()).
# Weryfikacja: pytest 593 passed, 0 failed; self-check: 0 problemów.
# ── Rejestr zmian (2026-11-07, kont.) — Runner: poprawki niezawodności ────────
# Audyt Runnera (wywołania vs definicje): poza naprawionymi wcześniej
#   _runner_open_pane / new_console brak dalszych brakujących funkcji
#   (_vdrive_sel/_venv_sel to atrybuty ustawiane w builderych — prawidłowo).
# Naprawy niezawodności:
#   * _runner_stop(): po ubiciu procesu zamyka stdin — wątek pump nie wisiał
#     na otwartym pipe; płynniejsze zamknięcie przebiegu.
#   * _runner_send_stdin(): wcześniejsze sprawdzenie proc.poll() — wysłanie do
#     martwego procesu nie rzucało, teraz czytelny komunikat "Brak działającego
#     procesu"; OSError/ValueError (zamknięty strumień) obsługiwane bez śladu
#     dead-code; pole czyszczone tylko po udanym wysłaniu.
# Weryfikacja: pytest 593 passed, 0 failed; self-check: 0 problemów.
# ── Rejestr zmian (2026-11-07, kont.) — pokrycie git_integration 97% → 100% ──
# Nowe klasy testowe w tests/test_git_integration.py (60 → 79 testów):
#   * TestFindGit — find_git(): ścieżka z fallbacku, brak wszędzie (cache),
#     preferencja PATH.
#   * TestGitCommandFailures — brak gita, TimeoutExpired, FileNotFoundError
#     w _run_git_command / _check_git_repo.
#   * TestMoreGitMethods — get_branches/get_history (z plikiem, linie
#     niepoparsowane, błąd), get_diff (warianty 1/2 hashy ± plik, błąd),
#     get_commit_diff (błędny hash), get_file_at_commit, restore_file,
#     add_remote/set_remote (walidacje), status (błąd, linia 2-znakowa,
#     porcelain fallback).
#   * TestSyncAndRemote — sync_file (branch niedostępny, staging fail, brak
#     zmian w index, commit fail przed push), push/pull bez brancha i bez
#     inicjalizacji, pull z last_error, status po błędzie.
# Wynik: src/git_integration.py 100% pokrycia; pytest 593 passed (bez zmiany
#   liczby — testy w tym samym pliku), 0 failed.
# ── Rejestr zmian (2026-11-07, kont.) — Runner: opcje znowu widoczne ─────────
# Problem zgłoszony przez użytkownika: w zakładce Runner nie widać opcji
#   uruchomienia (Interpreter / Argumenty / Timeout / przyciski / ENV / stdin).
# Przyczyna: w _runner_build_body() panel wyjścia (_runner_build_bottom,
#   pack expand=True) był pakowany PRZED sekcją opcji (top) — przy oknie
#   1024x700 opcje lądowały poniżej widocznej wysokości (Frame bez scrollbar).
#   Wrażenie "zniknięcia funkcji" — nic nie zostało usunięte (diff vs git potwierdza).
# Naprawa: sekcja opcji (top: lista skryptów + interpreter/args/timeout/przyciski)
#   pakowana przed panel wyjścia; _runner_build_bottom wywoływane na końcu
#   buildera, więc expand=True dostaje wyjście i wypełnia resztę miejsca.
# Weryfikacja: składnia OK, pytest 593 passed, self-check 0 problemów.
