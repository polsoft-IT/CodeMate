Współpraca
===========

Wymagania deweloperskie
-----------------------

* Python 3.8+
* pip
* Git (opcjonalnie)

Konfiguracja środowiska
-----------------------

1. Sklonuj repozytorium:

.. code-block:: bash

   git clone <repository-url>
   cd "CodeMate v3.0"

2. Utwórz środowisko wirtualne:

.. code-block:: bash

   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac

3. Zainstaluj zależności:

.. code-block:: bash

   pip install -r requirements.txt

Uruchamianie testów
-------------------

Uruchom wszystkie testy:

.. code-block:: bash

   pytest

Uruchom testy z coverage:

.. code-block:: bash

   pytest --cov=src --cov-report=html

Sprawdzanie typów
-----------------

Uruchom mypy:

.. code-block:: bash

   mypy src/

Budowanie dokumentacji
----------------------

.. code-block:: bash

   cd docs
   make html

Formatowanie kodu
------------------

Projekt używa formatowania zgodnego z PEP 8. Zalecamy użycie black:

.. code-block:: bash

   pip install black
   black baza_skryptow.py src/

Zgłaszanie błędów
-----------------

Zgłoś błędy na GitHub Issues włączając:

1. Opis problemu
2. Kroki do reprodukcji
3. Oczekiwane zachowanie
4. Aktualne zachowanie
5. Wersję aplikacji
6. System operacyjny
7. Wersję Python

Przesyłanie pull requestów
---------------------------

1. Forknij repozytorium
2. Utwórz branch dla funkcji (``git checkout -b feature/AmazingFeature``)
3. Commituj zmiany (``git commit -m 'Add some AmazingFeature'``)
4. Push do brancha (``git push origin feature/AmazingFeature``)
5. Otwórz Pull Request

Konwencje commitów
-------------------

Używaj następujących konwencji:

* ``[ADD]`` - dodanie nowej funkcji
* ``[FIX]`` - naprawienie błędu
* ``[REF]`` - refaktoryzacja
* ``[DOC]`` - aktualizacja dokumentacji
* ``[TEST]`` - dodanie testów
* ``[STYLE]`` - zmiany formatowania kodu

Przykład:

.. code-block:: bash

   git commit -m "[ADD] Add Git integration"

Licencja
--------

Projekt jest dostępny na licencji określonej w pliku LICENSE.
