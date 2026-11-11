User Manual
===========

Basic operations
----------------

Creating a new script
~~~~~~~~~~~~~~~~~~~~~

1. Select the **Scripts** tab

2. Click **+ New script**

3. Fill in the form:

   - Script name

   - Category (Python, Bash, PowerShell, JavaScript, SQL)

   - Tags (optional)

   - Description (optional)

   - Script code

4. Click **Save**

Editing a script
~~~~~~~~~~~~~~~~

1. Select the **Scripts** tab

2. Click **Script list**

3. Pick a script from the list

4. Click **Script editor**

5. Edit the code

6. Click **Save** (Ctrl+S)

Running a script
~~~~~~~~~~~~~~~~

1. Pick a script from the list

2. Click the **Runner** tab

3. Configure arguments (optional)

4. Click **Run**

Mouse support
~~~~~~~~~~~~~

- **Mouse wheel** - vertical scrolling of every scrollable widget

  (editors, lists, tables, canvases). When a widget is at the edge of its

  range, scrolling passes to the nearest scrollable container - it also

  works over children inside scrollable frames.

- **Shift/Alt + wheel** - horizontal scrolling; if nothing scrolls

  horizontally, it scrolls vertically instead.

- **Ctrl + wheel** - zoom editor fonts in/out.

- **Middle button + drag** - pan the contents of scrollable widgets.

Scheduler
---------

Setting a schedule
~~~~~~~~~~~~~~~~~~

1. Select a script

2. In the **Advanced** section set the schedule:

   - Active: enable/disable

   - Every N minutes: how often to run

   - At time: which hour to run at

3. Save the script

Git integration
---------------

Automatic commits
~~~~~~~~~~~~~~~~~

The application automatically commits changes to Git:

- On every database save

- On every script change

Managing Git
~~~~~~~~~~~~

1. Select the **Git** tab

2. In the **Changes** tab select one or more files:

   - **Stage selected** adds the selected files to the staging area

   - **Unstage selected** removes them from staging without discarding worktree changes

   - **Discard worktree...** after confirmation restores the selected tracked files to the staged version; untracked files are skipped

   - **Commit staged...** creates a commit containing only the changes staged

3. In the **History** tab pick a commit to see its diff.

4. Use the remaining buttons:

   - **Refresh** - re-read status, history and branches

   - **Push** - push changes to the remote repository

   - **Pull** - fetch changes from the remote repository

   - **Remote...** - add or change the repository URL

   - **Sync database** - commit the database and push the current branch

   - **Auto push after save** - enable automatic push after a local database commit

5. Choose a branch from the list; **New branch...** creates and switches to a new branch.

Pull uses ``--ff-only``: diverged histories report a conflict without an automatic

merge. Resolve it in Git and sync again. Set the remote before syncing;

configure credentials in Git Credential Manager, not in the URL.

Plugin system
-------------

Installing a plugin
~~~~~~~~~~~~~~~~~~~

1. Place the plugin file in the ``plugins/`` directory

2. The plugin must inherit from ``BasePlugin``

3. Restart the application

Managing plugins
~~~~~~~~~~~~~~~~

1. Select the ** Plugins** tab

2. See the list of loaded plugins

3. Use the **Refresh**, **Enable/Disable**, **Details** and **Marketplace** buttons.

   The Marketplace fetches the HTTPS catalog and lets you install, update and remove

   managed plugins; installation requires confirmation.

The catalog is JSON with ``api_version: 1`` and a ``plugins`` list; each entry contains ``name``,

``version``, ``url`` (HTTPS), ``sha256`` and a matching ``api_version``. Example:

.. code-block:: json

    {"api_version": 1, "plugins": [{

       "name": "example", "version": "1.0.0",

       "url": "https://example.test/example.py",

       "sha256": "<64-char SHA-256>", "api_version": 1,

       "description": "Example plugin"

    }]}

Writing your own plugin
~~~~~~~~~~~~~~~~~~~~~~~

Example plugin:

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

Save as ``plugins/my_plugin.py``.

Export to .exe
--------------

Select a Python script in the Editor and click **Export to .exe**. The wizard

lets you choose the target folder, onefile/onedir mode, an `.ico` icon and console.

The default location is ``~/VDriveImages/Exports``. Requires PyInstaller

(``pip install pyinstaller``); building runs in the background and the window shows

progress and a log. Categories other than Python are not exported.

VDrive tab
----------

In the **Create media** sub-tab, add an entry as media with an automatically

assigned drive letter, or choose **Register without letter**. The list, paths, options

and settings are saved to ``vdrive_state.json`` next to the application and restored

on the next start. Unknown mount state is reset to unmounted after restart. Changes

to general settings are saved with the **Save settings** button.

Select a media entry and click ** Copy command** (or double-click the entry)

to copy the suggested command to the clipboard. VDrive does not run system commands

and does not mount/unmount media by itself; review the copied command before manual

use. Labels, forms, media type lists, messages and the log follow the app's PL/EN

language.

Database tab
------------

1. Open the **Database** tab and pick an SQLite file in the **Connection** sub-tab.

2. Click **Connect (Online)** to show database info and the list of tables.

3. In the **SQL queries** sub-tab type a query and choose **Execute (F9)**.

   The last 20 unique queries are available in the **Query history** list;

   select an entry to restore it into the editor.

4. Use the **Browser** sub-tab to view a table page by page. Set the row limit,

   then navigate with **Previous** / **Next**; the status bar shows the range

   and total row count. CSV export covers the currently displayed page.

   SQLite files can be browsed, scanned and copied in the **Database files** sub-tab.

Settings tab
------------

Centralized configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Select the **Settings** tab  the form is split into sub-tabs:

   ** General**

   - **Database** - database file, backups, autosave

   - **Runner** - interpreter, timeout, arguments, console

   - **Interface language** - PL / EN (changes apply immediately)

   - **Git** - integration and automatic database commits

   - **Plugins** - load plugins at startup

   - **Trash** - permanent deletion after X days (0 = never)

   - **Notifications** - notification after a scheduled task

   **Personalization**

   - **Appearance** - theme, font (with a color picker button next to the

     combobox), size, tab and text colors. The font color setting applies

     to text in editors, lists and other fields  useful e.g. with a light

     background.

   - **Script list appearance** - alternating row colors, odd/even and

     selection row colors (empty field = theme color), row height (1664 px)

     and list font size (720 pt)

2. Click **Save settings** (or **Restore defaults**)

Font family and editor size are previewed immediately while editing. Custom tab,

text and script list colors apply when the field loses focus.

Saving persists settings, and restoring defaults updates the preview without

a restart.

Changing the interface language
-------------------------------

- Click the ** EN** / ** PL** switch in the window header, or use the

  **Interface language** section in the Settings tab.

- The choice is stored in the configuration and applied immediately across the UI.

- The default language (for new installations) is **English**; Polish remains a

  fully supported source language of the interface.

Snippet library
---------------

Adding and inserting a snippet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Select the **Scripts** tab  the ** Snippets** sub-tab

2. Click ** New**, fill in name, category, tags and content

3. Click ** Save**

4. Select a snippet and click ** Insert into editor** (at the cursor)

   or ** Copy**

Placeholders
~~~~~~~~~~~~

In snippet content you can use ``${name}`` markers  when inserting,

the application asks for values and substitutes them into the code.

Trash
-----

- Scripts deleted with a soft delete go to the ** Trash** sub-tab.

- They can be **restored** or permanently deleted.

- The automatic deletion rule after X days is configurable in the

  Settings tab (**Trash** section).

- Trash item count and size are visible in the ** Statistics** sub-tab.

REST API
--------

The API service runs separately from the GUI. It requires a high-entropy token

(at least 32 characters) in the ``CODEMATE_API_TOKEN`` environment variable. By default

it listens only on ``127.0.0.1:8765``:

.. code-block:: powershell

    $env:CODEMATE_API_TOKEN = "generate-a-random-secret-of-at-least-32-chars"

    python -m src.api

You can supply a different database and port: ``python -m src.api --db path\database.json --port 8765``.

A ``--host`` address other than localhost exposes the ability to run scripts on the

network; use it only behind a trusted TLS proxy and protect the token.

All endpoints require the ``Authorization: Bearer <token>`` header.

``GET /health`` checks availability, ``GET /scripts`` returns only active, trusted

scripts, ``POST /runs`` accepts ``script_id``, a list of arguments and an optional

timeout (13600 s), and ``GET /runs/{id}`` returns the status and limited process

output. ``DELETE /runs/{id}`` cancels an active job; the initial response has status

``cancelling``, and after the process ends the status changes to ``cancelled``.

Repeated requests during cancellation are safe; a finished job cannot be cancelled

(HTTP 409). The API keeps at most the 256 most recent jobs; the oldest finished

entries are removed when new jobs are accepted, and active ones are never removed.

The API does not accept code or arbitrary commands. Execution is available only for

scripts marked as trusted.

An optional webhook is configured via ``CODEMATE_API_WEBHOOK_URL``. Only HTTPS URLs

are allowed; after a job finishes a payload with the status (without process output)

is sent with an HMAC-SHA256-signed ``X-CodeMate-Signature`` header.

Autocomplete in the editor
--------------------------

- Press **Ctrl+Space** in the code editor to invoke suggestions

  (variables, functions, classes, imports, keywords, built-in functions).

- Navigation: ** / **, accept: **Enter** or **Tab**, close: **Esc**.

