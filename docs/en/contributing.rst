Contributing
============
Development requirements
------------------------
* Python 3.8+
* pip
* Git (optional)

Environment setup
-----------------
1. Clone the repository:

.. code-block:: bash

   git clone <repository-url>
   cd "CodeMate v3.0"

2. Create a virtual environment:

.. code-block:: bash

   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac

3. Install dependencies:

.. code-block:: bash

   pip install -r requirements.txt

Running tests
-------------
Run all tests:

.. code-block:: bash

   pytest

Run tests with coverage:

.. code-block:: bash

   pytest --cov=src --cov-report=html

Type checking
-------------
Run mypy:

.. code-block:: bash

   mypy src/

Building the documentation
--------------------------

.. code-block:: bash

   cd docs
   make html

Code formatting
---------------
The project uses PEP 8 compliant formatting. We recommend using black:

.. code-block:: bash

   pip install black
   black baza_skryptow.py src/

Reporting bugs
--------------
Report bugs on GitHub Issues including:
1. Problem description
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Application version
6. Operating system
7. Python version

Submitting pull requests
------------------------
1. Fork the repository
2. Create a feature branch (``git checkout -b feature/AmazingFeature``)
3. Commit changes (``git commit -m 'Add some AmazingFeature'``)
4. Push to the branch (``git push origin feature/AmazingFeature``)
5. Open a Pull Request

Commit conventions
------------------
Use the following conventions:
* ``[ADD]`` - new feature
* ``[FIX]`` - bug fix
* ``[REF]`` - refactoring
* ``[DOC]`` - documentation update
* ``[TEST]`` - adding tests
* ``[STYLE]`` - formatting changes

Example:

.. code-block:: bash

   git commit -m "[ADD] Add Git integration"

License
-------
CodeMate is distributed as **freeware**: it is free for personal and
commercial use. Redistribution is permitted as long as the original package
remains unmodified.
