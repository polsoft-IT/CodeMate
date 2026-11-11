Instalacja
===========

Wymagania
---------

* Python 3.8 lub nowszy
* Tkinter (zazwyczaj wbudowany w Python)

Instalacja z zaleznosciami
--------------------------

Zainstaluj wymagane pakiety:

.. code-block:: bash

   pip install -r requirements.txt

Instalacja
-----------

Uruchom aplikacje:

.. code-block:: bash

   python baza_skryptow.py

Pierwsze uruchomienie
---------------------

Przy pierwszym uruchomieniu aplikacja automatycznie:

1. Utworzy plik bazy danych ``baza_skryptow.json``
2. Utworzy plik konfiguracyjny ``baza_skryptow.cfg``
3. Zainicjalizuje repozytorium Git (jesli Git jest dostepny)
4. Zaladuje pluginy z katalogu ``plugins/``

Opcjonalne zaleznosci
---------------------

**Pygments** (dla podswietlania skladni):

.. code-block:: bash

   pip install pygments

**REST API** (opcjonalne):

.. code-block:: bash

   pip install fastapi uvicorn httpx

**Eksport do .exe** (Windows, opcjonalne):

.. code-block:: bash

   pip install pyinstaller

**Sphinx** (dla budowania dokumentacji):

.. code-block:: bash

   pip install sphinx sphinx-rtd-theme

Budowanie dokumentacji
-----------------------

.. code-block:: bash

   cd docs
   make html

Dokumentacja bedzie dostepna w ``docs/_build/html/index.html``.
