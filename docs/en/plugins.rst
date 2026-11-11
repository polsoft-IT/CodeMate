Plugin documentation
====================
Introduction
------------
The plugin system allows extending CodeMate's functionality without modifying the main code.

BasePlugin
----------
Every plugin must inherit from the ``BasePlugin`` class:

.. autoclass:: src.plugin_system.BasePlugin
   :members:
   :undoc-members:
   :show-inheritance:

Methods to implement
~~~~~~~~~~~~~~~~~~~~
``on_load()``
  Called when the plugin is loaded. Register hooks and initialize resources here.
``on_unload()``
  Called when the plugin is unloaded. Clean up resources here.
``on_enable()``
  Called when the plugin is enabled.
``on_disable()``
  Called when the plugin is disabled.

Available hooks
---------------
``before_script_save``
  Called before a script is saved.
``after_script_save``
  Called after a script is saved.
``before_script_run``
  Called before a script is run.
``after_script_run``
  Called after a script is run.
``before_db_load``
  Called before the database is loaded.
``after_db_load``
  Called after the database is loaded.
``before_db_save``
  Called before the database is saved.
``after_db_save``
  Called after the database is saved.
``on_app_start``
  Called when the application starts.
``on_app_close``
  Called when the application closes.

Example plugin
--------------

Example skeleton of a working plugin:

.. code-block:: python

   from src.plugin_system import BasePlugin

   class EventLogger(BasePlugin):
       PLUGIN_NAME = "Event Logger"
       PLUGIN_VERSION = "1.0.0"

       def on_load(self):
           self.register_hook("after_script_save", self.log)

       def log(self, script_data):
           print("script saved:", script_data)
