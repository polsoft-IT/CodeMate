Installation
============
Requirements
------------
* Python 3.8 or newer
* Tkinter (usually bundled with Python)

Installing dependencies
-----------------------
Install the required packages:

.. code-block:: bash

   pip install -r requirements.txt

Running the application
-----------------------
Start the application:

.. code-block:: bash

   python baza_skryptow.py

First launch
------------
On first launch the application automatically:

1. Creates the database file ``baza_skryptow.json``
2. Creates the configuration file ``baza_skryptow.cfg``
3. Initializes a Git repository (if Git is available)
4. Loads plugins from the ``plugins/`` directory

Optional dependencies
---------------------
**Pygments** (for syntax highlighting):

.. code-block:: bash

   pip install pygments

**REST API** (optional):

.. code-block:: bash

   pip install fastapi uvicorn httpx

**Export to .exe** (Windows, optional):

.. code-block:: bash

   pip install pyinstaller

**Sphinx** (for building the documentation):

.. code-block:: bash

   pip install sphinx sphinx-rtd-theme

Building the documentation
--------------------------

.. code-block:: bash

   cd docs
   make html

The documentation will be available at ``docs/_build/html/index.html``.
