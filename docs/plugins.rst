Dokumentacja pluginów
=====================

Wprowadzenie
------------

System pluginów pozwala rozszerzać funkcjonalność CodeMate bez modyfikowania kodu głównego.

BasePlugin
----------

Każdy plugin musi dziedziczyć po klasie ``BasePlugin``:

.. autoclass:: src.plugin_system.BasePlugin
   :members:
   :undoc-members:
   :show-inheritance:

Metody do implementacji
~~~~~~~~~~~~~~~~~~~~~~~~

``on_load()``
  Wywoływane przy ładowaniu pluginu. Tutaj rejestruj hooki i inicjalizuj zasoby.

``on_unload()``
  Wywoływane przy wyładowaniu pluginu. Tutaj czyść zasoby.

``on_enable()``
  Wywoływane przy włączeniu pluginu.

``on_disable()``
  Wywoływane przy wyłączeniu pluginu.

Dostępne hooki
--------------

``before_script_save``
  Wywoływany przed zapisem skryptu.

``after_script_save``
  Wywoływany po zapisie skryptu.

``before_script_run``
  Wywoływany przed uruchomieniem skryptu.

``after_script_run``
  Wywoływany po uruchomieniu skryptu.

``before_db_load``
  Wywoływany przed wczytaniem bazy.

``after_db_load``
  Wywoływany po wczytaniu bazy.

``before_db_save``
  Wywoływany przed zapisem bazy.

``after_db_save``
  Wywoływany po zapisie bazy.

``on_app_start``
  Wywoływany przy starcie aplikacji.

``on_app_close``
  Wywoływany przy zamknięciu aplikacji.

Przykładowy plugin
-------------------

.. literalinclude:: ../plugins/event_logger.py
   :language: python
   :lines: 1-
