Podręcznik użytkownika
======================

Podstawowe operacje
--------------------

Tworzenie nowego skryptu
~~~~~~~~~~~~~~~~~~~~~~~~

1. Wybierz zakładkę **Skrypty**
2. Kliknij **+ Nowy skrypt**
3. Wypełnij formularz:
   - Nazwa skryptu
   - Kategoria (Python, Bash, PowerShell, JavaScript, SQL)
   - Tagi (opcjonalnie)
   - Opis (opcjonalnie)
   - Kod skryptu
4. Kliknij **Zapisz**

Edycja skryptu
~~~~~~~~~~~~~~

1. Wybierz zakładkę **Skrypty**
2. Kliknij **Lista skryptów**
3. Wybierz skrypt z listy
4. Kliknij **Edytor skryptów**
5. Edytuj kod
6. Kliknij **Zapisz** (Ctrl+S)

Uruchamianie skryptu
~~~~~~~~~~~~~~~~~~~~

1. Wybierz skrypt z listy
2. Kliknij **▶ Runner**
3. Skonfiguruj argumenty (opcjonalnie)
4. Kliknij **Uruchom**

Obsługa myszy
~~~~~~~~~~~~~

- **Kółko myszy** — pionowe przewijanie każdego przewijanego widżetu
  (edytory, listy, tabele, kanwy). Gdy widżet jest na krańcu zakresu,
  przewijanie przechodzi do najbliższego przewijanego kontenera —
  działa też nad dziećmi wewnątrz przewijanych ram.
- **Shift/Alt + kółko** — przewijanie poziome; gdy brak przewijanego
  w poziomie, wykonuje się pionowe.
- **Ctrl + kółko** — powiększanie/zmniejszanie czcionki edytorów.
- **Środkowy przycisk + przeciąganie** — przesuwanie (pan) zawartości
  przewijanych widżetów.

Harmonogram
-----------

Ustawienie harmonogramu
~~~~~~~~~~~~~~~~~~~~~~~~

1. Wybierz skrypt
2. W sekcji **Zaawansowane** ustaw harmonogram:
   - Aktywny: włącz/wyłącz
   - Co minut: co ile minut uruchamiać
   - O godzinie: o której godzinie uruchamiać
3. Zapisz skrypt

Integracja Git
--------------

Automatyczne commity
~~~~~~~~~~~~~~~~~~~~~

Aplikacja automatycznie commituje zmiany do Git:

- Przy każdym zapisie bazy danych
- Przy każdej zmianie skryptu

Zarządzanie Git
~~~~~~~~~~~~~~~

1. Wybierz zakładkę **📚 Git**
2. W zakładce **Zmiany** zaznacz jeden lub kilka plików:
   - **Stage selected** dodaje zaznaczone pliki do staging
   - **Unstage selected** usuwa je ze staging, nie kasując zmian roboczych
   - **Discard worktree…** po potwierdzeniu przywraca zaznaczone śledzone pliki do wersji staged; pliki untracked są pomijane
   - **Commit staged…** tworzy commit wyłącznie ze zmian przygotowanych w staging
3. W zakładce **Historia** wybierz commit, aby zobaczyć jego diff.
4. Użyj pozostałych przycisków:
   - **Odśwież** - odczytaj ponownie status, historię i branche
   - **Push** - wypchnij zmiany do zdalnego repozytorium
   - **Pull** - pobierz zmiany ze zdalnego repozytorium
   - **Remote…** - dodaj lub zmień adres repozytorium
   - **Synchronizuj bazę** - commituj bazę i wypchnij bieżący branch
   - **Auto push po zapisie** - włącz automatyczny push po lokalnym commicie bazy
5. Branch wybieraj z listy; **Nowy branch…** tworzy i przełącza na nowy branch.

Pull używa ``--ff-only``: rozbieżne historie zgłaszają konflikt bez automatycznego
merge. Rozwiąż go w Git i ponów synchronizację. Ustaw remote przed synchronizacją;
poświadczenia skonfiguruj w Git Credential Manager, nie w adresie URL.

System pluginów
---------------

Instalacja pluginu
~~~~~~~~~~~~~~~~~~~

1. Umieść plik pluginu w katalogu ``plugins/``
2. Plugin musi dziedziczyć po ``BasePlugin``
3. Zrestartuj aplikację

Zarządzanie pluginami
~~~~~~~~~~~~~~~~~~~~~~

1. Wybierz zakładkę **🔌 Plugins**
2. Zobacz listę załadowanych pluginów
3. Użyj przycisków **Odśwież**, **Włącz/Wyłącz**, **Szczegóły** i **Marketplace**.
   Marketplace pobiera katalog HTTPS, pozwala instalować, aktualizować i usuwać
   zarządzane pluginy; instalacja wymaga potwierdzenia.

Katalog to JSON z ``api_version: 1`` i listą ``plugins``; każdy wpis zawiera ``name``,
``version``, ``url`` (HTTPS), ``sha256`` oraz zgodny ``api_version``. Przykład:

.. code-block:: json

    {"api_version": 1, "plugins": [{
       "name": "example", "version": "1.0.0",
       "url": "https://example.test/example.py",
       "sha256": "<64 znaki SHA-256>", "api_version": 1,
       "description": "Example plugin"
    }]}

Tworzenie własnego pluginu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Przykładowy plugin:

.. code-block:: python

   from src.plugin_system import BasePlugin

   class MyPlugin(BasePlugin):
       PLUGIN_NAME = "My Plugin"
       PLUGIN_VERSION = "1.0.0"
       PLUGIN_AUTHOR = "Your Name"
       PLUGIN_DESCRIPTION = "My custom plugin"
       PLUGIN_CATEGORY = "Custom"

       def on_load(self):
           self.register_hook("before_script_save", self.my_hook)

       def on_unload(self):
           pass

       def my_hook(self, script_data):
           print(f"Saving script: {script_data['nazwa']}")

Zapisz jako ``plugins/my_plugin.py``.

Eksport do .exe
---------------

Wybierz skrypt Python w Edytorze i kliknij **📦 Eksportuj do .exe**. Kreator
pozwala wybrać folder docelowy, tryb onefile/onedir, ikonę `.ico` i konsolę.
Domyślna lokalizacja to ``~/VDriveImages/Exports``. Wymaga PyInstaller
(``pip install pyinstaller``); budowanie działa w tle, a okno pokazuje postęp
i log. Inne kategorie niż Python nie są eksportowane.

Zakładka VDrive
---------------

W pod-zakładce **Utwórz nośnik** dodaj wpis jako nośnik z automatycznie
przypisaną literą lub wybierz **Zarejestruj bez litery**. Lista, ścieżki, opcje
i ustawienia są zapisywane do ``vdrive_state.json`` obok aplikacji i odtwarzane
przy kolejnym starcie. Nieznany stan montowania jest po restarcie resetowany do
odmontowanego. Zmiany ustawień ogólnych zapisuje przycisk **💾 Zapisz ustawienia**.

Wybierz nośnik i kliknij **📋 Kopiuj polecenie** (albo dwukrotnie kliknij wpis),
aby skopiować sugerowane polecenie do schowka. VDrive nie uruchamia poleceń
systemowych ani nie montuje/odmontowuje nośników samodzielnie; skopiowane
polecenie należy sprawdzić przed ręcznym użyciem. Etykiety, formularze, listy
typów nośników, komunikaty i log podążają za językiem PL/EN aplikacji.

Zakładka Baza danych
--------------------

1. Otwórz zakładkę **Baza** i wybierz plik SQLite w pod-zakładce **Połączenie**.
2. Kliknij **Połącz (Online)**, aby wyświetlić informacje o bazie i listę tabel.
3. W pod-zakładce **Zapytania SQL** wpisz zapytanie i wybierz **▶ Wykonaj (F9)**.
   Ostatnie 20 unikalnych zapytań jest dostępnych na liście **Historia zapytań**;
   wybierz wpis, aby przywrócić go do edytora.
4. Użyj pod-zakładki **Przeglądarka**, aby wyświetlić tabelę stronami. Ustaw limit
   wierszy, a następnie przechodź przyciskami **◀ Poprzednia** / **Następna ▶**;
   pasek stanu pokazuje zakres i łączną liczbę wierszy. Eksport CSV obejmuje
   aktualnie wyświetloną stronę.
   Pliki SQLite można przeglądać, skanować i kopiować w pod-zakładce **Pliki bazy**.

Zakładka Ustawienia
-------------------

Scentralizowana konfiguracja
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Wybierz zakładkę **Ustawienia** — formularz jest podzielony na pod-zakładki:

   **⚙ Ogólne**
   - **Baza danych** - plik bazy, kopie zapasowe, autosave
   - **Runner** - interpreter, limit czasu, argumenty, konsola
   - **Język interfejsu** - PL / EN (zmiana działa natychmiast)
   - **Git** - integracja oraz automatyczne commity bazy
   - **Pluginy** - ładowanie pluginów przy starcie
   - **Kosz** - trwałe usuwanie po X dniach (0 = nigdy)
   - **Powiadomienia** - powiadomienie po zadaniu harmonogramu

   **🎨 Personalizacja**

   - **Wygląd** - motyw, czcionka (z przyciskiem wyboru koloru obok
     comboboxa), rozmiar, kolory zakładek i tekstu. Kolor czcionki
     (ustawienie **Kolor czcionki**) dotyczy tekstu w edytorach, listach
     i pozostałych polach — przydaje się np. przy jasnym tle.
   - **Wygląd listy skryptów** - naprzemienne kolory wierszy, kolory
     wiersza nieparzystego/parzystego i zaznaczenia (puste pole = kolor
     z motywu), wysokość wiersza (16–64 px) i rozmiar czcionki listy
     (7–20 pt)

2. Kliknij **💾 Zapisz ustawienia** (lub **Przywróć domyślne**)

Rodzina czcionki i rozmiar edytora są podglądane od razu podczas edycji. Własne
kolory zakładek, tekstu i listy skryptów stosują się po opuszczeniu pola.
Zapis utrwala ustawienia, a przywrócenie domyślnych aktualizuje podgląd bez
restartu.

Zmiana języka interfejsu
------------------------

- Kliknij przełącznik **● EN** / **● PL** w nagłówku okna lub użyj sekcji
  **Język interfejsu** w zakładce Ustawienia.
- Wybór jest zapisywany w konfiguracji i stosowany od razu w całym UI.
- Językiem domyślnym (dla nowych instalacji) jest **angielski**; polski pozostaje
  pełnoprawnym językiem źródłowym interfejsu.

Biblioteka snippetów
--------------------

Dodawanie i wstawianie snippetu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Wybierz zakładkę **Skrypty** → pod-zakładkę **📚 Snippety**
2. Kliknij **➕ Nowy**, wypełnij nazwę, kategorię, tagi i treść
3. Kliknij **💾 Zapisz**
4. Zaznacz snippet i kliknij **➕ Wstaw do edytora** (w miejscu kursora)
   lub **📋 Kopiuj**

Placeholdery
~~~~~~~~~~~~

W treści snippetu można użyć znaczników ``${nazwa}`` — przy wstawianiu
aplikacja zapyta o wartości i podstawi je w kodzie.

Kosz
----

- Skrypty usuwane miękkim usunięciem trafiają do pod-zakładki **🗑 Kosz**.
- Można je **przywrócić** lub usunąć trwale.
- Reguła automatycznego usuwania po X dniach jest konfigurowalna w
  zakładce Ustawienia (sekcja **Kosz**).
- Liczba i rozmiar elementów kosza są widoczne w pod-zakładce
  **📊 Statystyki**.

REST API
--------

Serwis API uruchamia się osobno od GUI. Wymaga tokenu o wysokiej entropii
(minimum 32 znaki) w zmiennej środowiskowej ``CODEMATE_API_TOKEN``. Domyślnie
nasłuchuje wyłącznie na ``127.0.0.1:8765``:

.. code-block:: powershell

    $env:CODEMATE_API_TOKEN = "wygeneruj-losowy-sekret-minimum-32-znaki"
    python -m src.api

Można podać inną bazę i port: ``python -m src.api --db ścieżka\baza.json --port 8765``.
Adres ``--host`` inny niż localhost udostępnia możliwość uruchamiania skryptów
w sieci; używaj go tylko za zaufanym TLS proxy i chroń token.

Wszystkie endpointy wymagają nagłówka ``Authorization: Bearer <token>``.
``GET /health`` sprawdza dostępność, ``GET /scripts`` zwraca wyłącznie aktywne,
zaufane skrypty, ``POST /runs`` przyjmuje ``script_id``, listę argumentów i
opcjonalny timeout (1–3600 s), a ``GET /runs/{id}`` zwraca status oraz ograniczone
wyjście procesu. ``DELETE /runs/{id}`` anuluje aktywne zadanie; odpowiedź początkowa
ma status ``cancelling``, a po zakończeniu procesu status zmienia się na
``cancelled``. Ponowne żądanie podczas anulowania jest bezpieczne; zakończonego
zadania nie można anulować (HTTP 409). API zachowuje maksymalnie 256 ostatnich
zadań; najstarsze zakończone wpisy są usuwane przy przyjęciu nowych zadań, a
aktywne nie są usuwane. API nie przyjmuje kodu ani dowolnych poleceń. Uruchomienie
jest dostępne tylko dla skryptów oznaczonych jako zaufane.

Opcjonalny webhook konfiguruje się przez ``CODEMATE_API_WEBHOOK_URL``. Dozwolone są
wyłącznie adresy HTTPS; po zakończeniu zadania wysyłany jest podpisany nagłówkiem
HMAC-SHA256 ``X-CodeMate-Signature`` payload ze statusem (bez wyjścia procesu).

Autouzupełnianie w edytorze
---------------------------

- Wciśnij **Ctrl+Space** w edytorze kodu, aby wywołać podpowiedzi
  (zmienne, funkcje, klasy, importy, słowa kluczowe, wbudowane funkcje).
- Nawigacja: **↑ / ↓**, akceptacja: **Enter** lub **Tab**, zamknięcie: **Esc**.

