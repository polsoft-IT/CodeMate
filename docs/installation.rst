Instalacja
===========

Wymagania
---------

* Python 3.8 lub nowszy
* Tkinter (zazwyczaj wbudowany w Python)

Instalacja z zależnościami
--------------------------

Zainstaluj wymagane pakiety:

.. code-block:: bash

   pip install -r requirements.txt

Instalacja
-----------

Uruchom aplikację:

.. code-block:: bash

   python baza_skryptow.py

Pierwsze uruchomienie
---------------------

Przy pierwszym uruchomieniu aplikacja automatycznie:

1. Utworzy plik bazy danych ``baza_skryptow.json``
2. Utworzy plik konfiguracyjny ``baza_skryptow.cfg``
3. Zainicjalizuje repozytorium Git (jeśli Git jest dostępny)
4. Załaduje pluginy z katalogu ``plugins/``

Opcjonalne zależności
---------------------

**Pygments** (dla podświetlania składni):

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

Dokumentacja będzie dostępna w ``docs/_build/html/index.html``.
