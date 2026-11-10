import os
import queue
import locale
import shlex
import signal
import subprocess
import threading
import shutil
import tkinter as tk
from tkinter import ttk

MAX_OUTPUT_LINES = 12000
MAX_OUTPUT_BATCH = 262144
OUTPUT_POLL_INTERVAL_MS = 20


def _shell_command():
    if os.name == "nt":
        powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
        if powershell:
            return [powershell, "-NoLogo", "-NoProfile"], "PowerShell"
        return [os.environ.get("COMSPEC", "cmd.exe"), "/Q"], "Command Prompt"

    shell = os.environ.get("SHELL") or "/bin/sh"
    return [shell, "-i"], os.path.basename(shell)


def _open_shell(cwd=None):
    command, name = _shell_command()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    process = subprocess.Popen(
        command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, bufsize=0, creationflags=flags)
    return process, name


def _resolve_path(cwd, value):
    value = value.strip().strip("\"'") or "~"
    value = os.path.expandvars(os.path.expanduser(value))
    if not os.path.isabs(value):
        value = os.path.join(cwd, value)
    return os.path.abspath(value)


class TerminalWidget(tk.Frame):
    """Samodzielna sesja powloki z widokiem Tkinter."""

    def __init__(self, master, on_plugin_command=None, tr=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_plugin_command = on_plugin_command
        self._tr = tr or (lambda s: s)
        self.configure(bg="#1e2130")
        self.cwd = os.getcwd()
        self._output_queue = queue.Queue(maxsize=256)
        self._process = None
        self._ui_thread_id = threading.get_ident()
        self._encoding = locale.getpreferredencoding(False)
        self._history = []
        self._history_index = 0
        self._aliases = {"?": "help"}
        self._previous_cwd = None
        self._shell_name = ""

        toolbar = tk.Frame(self, bg="#252839", padx=8, pady=6)
        toolbar.pack(fill="x")
        self._status_label = tk.Label(
            toolbar, text=self._tr("Uruchamianie powloki..."), anchor="w",
            bg="#252839", fg="#8aafcf")
        self._status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(toolbar, text=self._tr("Wyczysc"), command=self.clear).pack(side="right", padx=(6, 0))
        ttk.Button(toolbar, text=self._tr("Nowa sesja"), command=self.restart).pack(side="right", padx=(0, 6))
        self._stop_button = ttk.Button(toolbar, text=self._tr("Zakoncz"), command=self.stop)
        self._stop_button.pack(side="right")

        self.output = tk.Text(
            self, bg="#171923", fg="#d9e0ee", insertbackground="#d9e0ee",
            font=("Consolas", 10), wrap="none", state="disabled",
            relief="flat", padx=10, pady=8)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.output.yview)
        horizontal_scrollbar = ttk.Scrollbar(
            self, orient="horizontal", command=self.output.xview)
        self.output.configure(
            yscrollcommand=scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        horizontal_scrollbar.pack(side="bottom", fill="x")
        self.output.pack(fill="both", expand=True)
        self.output.tag_configure("prompt", foreground="#6dde84")
        self.output.tag_configure("error", foreground="#e06c75")
        self.output.tag_configure(
            "help_title", foreground="#82c7ff",
            font=("Consolas", 12, "bold"), spacing1=5, spacing3=3)
        self.output.tag_configure(
            "help_section", foreground="#6dde84",
            font=("Consolas", 10, "bold"), spacing1=8, spacing3=2)
        self.output.tag_configure(
            "help_command", foreground="#f2cc8f",
            font=("Consolas", 9, "bold"))
        self.output.tag_configure(
            "help_column_header", foreground="#82c7ff",
            font=("Consolas", 9, "bold"))
        self.output.tag_configure("help_description", foreground="#b9c3d6")
        self.output.tag_configure("help_rule", foreground="#3a8b9e")
        self.output.tag_configure("help_note", foreground="#8aafcf", spacing1=5)

        self.command = tk.Entry(
            self, bg="#252839", fg="#e0e4f0", insertbackground="#e0e4f0",
            font=("Consolas", 10), relief="flat")
        self.command.pack(fill="x", padx=8, pady=8, ipady=6)
        self.command.bind("<Return>", self._submit_event)
        self.command.bind("<Up>", self._history_up)
        self.command.bind("<Down>", self._history_down)
        self.command.bind("<Control-c>", self._interrupt)
        self.command.focus_set()

        self._start_shell()
        self.after(OUTPUT_POLL_INTERVAL_MS, self._drain_output)

    def _write(self, text, tag=None):
        if not text:
            return
        if threading.get_ident() != self._ui_thread_id:
            self._output_queue.put(("message", None, (text, tag)))
            return
        self._insert_segments(((text, tag),))

    def _insert_segments(self, segments):
        segments = [(text, tag) for text, tag in segments if text]
        if not segments:
            return
        self.output.configure(state="normal")
        for text, tag in segments:
            self.output.insert("end", text, tag)
        line_count = int(self.output.index("end-1c").split(".", 1)[0])
        if line_count > MAX_OUTPUT_LINES:
            lines_to_remove = line_count - MAX_OUTPUT_LINES
            self.output.delete("1.0", f"{lines_to_remove + 1}.0")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _submit_event(self, _event=None):
        self.run_command()
        return "break"

    def run_command(self):
        text = self.command.get().strip()
        self.command.delete(0, "end")
        if not text:
            return
        self._history.append(text)
        self._history_index = len(self._history)
        self._write(f"> {text}\n", "prompt")

        expanded = self._expand_aliases(text)
        if expanded != text:
            self._write(f"  {expanded}\n", "prompt")
        command, _, arguments = expanded.partition(" ")
        command = command.lower()

        if expanded.startswith("/"):
            if self._on_plugin_command is not None:
                alias, _, plugin_args = expanded[1:].partition(" ")
                if self._on_plugin_command(alias.strip(), plugin_args.strip()):
                    self._write("  OK\n")
                    return
            self._write(f"Unknown plugin command: {expanded}\n", "error")
            return

        if command == "help":
            self._show_help(arguments.strip())
            return
        if command == "alias":
            self._handle_alias(arguments.strip())
            return
        if command == "unalias":
            self._handle_unalias(arguments.strip())
            return
        if command in ("clear", "cls"):
            self.clear()
            return
        if self._handle_file_operation(command, arguments.strip()):
            return
        if self._handle_navigation(command, arguments.strip()):
            return

        if self._process is None or self._process.stdin is None:
            self._write(self._tr("Brak aktywnej powloki. Uruchom nowa sesje.") + "\n", "error")
            return

        self._send_shell_command(expanded)

    def _send_shell_command(self, command):
        try:
            if self._process is None or self._process.stdin is None:
                self._write(self._tr("Brak aktywnej powloki. Uruchom nowa sesje.") + "\n", "error")
                return False
            self._process.stdin.write((command + "\n").encode(self._encoding, errors="replace"))
            self._process.stdin.flush()
            return True
        except Exception as exc:
            self._write(self._tr("Blad zapisu do powloki") + f": {exc}\n", "error")
            return False

    def _handle_navigation(self, command, arguments):
        if command == "pwd":
            self._write(f"{self.cwd}\n")
            return True
        if command in ("ls", "dir"):
            target = _resolve_path(self.cwd, arguments) if arguments else self.cwd
            threading.Thread(
                target=self._list_directory, args=(target,), daemon=True).start()
            return True
        if command not in ("cd", "up", "home", ".."):
            return False

        if command in ("up", ".."):
            target = os.path.dirname(self.cwd)
        elif command == "home" or arguments in ("", "~"):
            target = os.path.expanduser("~")
        elif arguments == "-":
            target = self._previous_cwd
            if target is None:
                self._write("No previous directory.\n", "error")
                return True
        else:
            target = _resolve_path(self.cwd, arguments)
        self._change_directory(target)
        return True

    def _change_directory(self, target):
        target = os.path.abspath(target)
        if not os.path.isdir(target):
            self._write(f"Directory not found: {target}\n", "error")
            return

        quoted_path = target.replace("'", "''")
        if self._shell_name == "PowerShell":
            command = f"Set-Location -LiteralPath '{quoted_path}'"
        elif self._shell_name == "Command Prompt":
            command = f'cd /d "{target}"'
        else:
            command = f"cd -- {shlex.quote(target)}"
        if not self._send_shell_command(command):
            return

        self._previous_cwd, self.cwd = self.cwd, target
        self._status_label.configure(text=f"{self._tr('Sesja')}: {self._shell_name} | {self.cwd}")

    def _list_directory(self, target):
        if not os.path.isdir(target):
            self._write(f"Directory not found: {target}\n", "error")
            return
        try:
            entries = sorted(
                os.scandir(target),
                key=lambda entry: (not entry.is_dir(), entry.name.casefold()))
        except OSError as exc:
            self._write(f"Cannot list directory: {exc}\n", "error")
            return
        lines = [f"{target}\n"]
        for entry in entries:
            prefix = "[DIR]  " if entry.is_dir() else "       "
            lines.append(f"{prefix}{entry.name}\n")
        self._write("".join(lines))

    def _handle_file_operation(self, command, arguments):
        operations = {
            "cat": "read", "type": "read", "touch": "touch",
            "mkdir": "mkdir", "cp": "copy", "copy": "copy",
            "mv": "move", "move": "move", "rename": "move",
            "rm": "remove", "del": "remove", "rmdir": "rmdir",
        }
        operation = operations.get(command)
        if operation is None:
            return False

        try:
            paths = shlex.split(arguments, posix=os.name != "nt")
            paths = [path.strip("\"'") for path in paths]
        except ValueError as exc:
            self._write(f"Invalid arguments: {exc}\n", "error")
            return True
        threading.Thread(
            target=self._run_file_operation,
            args=(operation, paths), daemon=True).start()
        return True

    def _run_file_operation(self, operation, paths):
        try:
            if operation == "read":
                self._file_read(paths)
            elif operation == "touch":
                self._file_touch(paths)
            elif operation == "mkdir":
                self._file_mkdir(paths)
            elif operation == "copy":
                self._file_copy(paths)
            elif operation == "move":
                self._file_move(paths)
            elif operation == "remove":
                self._file_remove(paths)
            else:
                self._file_rmdir(paths)
        except (ValueError, OSError) as exc:
            self._write(f"File operation failed: {exc}\n", "error")

    def _file_read(self, paths):
        if not paths:
            self._write("Usage: cat FILE [FILE ...]\n", "error")
            return
        for value in paths:
            path = _resolve_path(self.cwd, value)
            if not os.path.isfile(path):
                self._write(f"Not a file: {path}\n", "error")
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as stream:
                while chunk := stream.read(32768):
                    self._write(chunk)
                self._write("\n")

    def _file_touch(self, paths):
        if not paths:
            self._write("Usage: touch FILE [FILE ...]\n", "error")
            return
        for value in paths:
            path = _resolve_path(self.cwd, value)
            with open(path, "a", encoding="utf-8"):
                os.utime(path, None)
            self._write(f"Created or updated: {path}\n")

    def _file_mkdir(self, paths):
        parents = "-p" in paths or "--parents" in paths
        targets = [path for path in paths if path not in ("-p", "--parents")]
        if not targets:
            self._write("Usage: mkdir [-p] DIRECTORY [DIRECTORY ...]\n", "error")
            return
        for value in targets:
            path = _resolve_path(self.cwd, value)
            if parents:
                os.makedirs(path, exist_ok=True)
            else:
                os.mkdir(path)
            self._write(f"Directory created: {path}\n")

    def _file_copy(self, paths):
        if len(paths) != 2:
            self._write("Usage: cp SOURCE DESTINATION\n", "error")
            return
        source, destination = (_resolve_path(self.cwd, value) for value in paths)
        if not os.path.exists(source):
            raise FileNotFoundError(source)
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source.rstrip(os.sep)))
        if os.path.isdir(source):
            try:
                copies_into_source = os.path.commonpath((source, destination)) == source
            except ValueError:
                copies_into_source = False
            if copies_into_source:
                raise ValueError("Cannot copy a directory into itself.")
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        self._write(f"Copied to: {destination}\n")

    def _file_move(self, paths):
        if len(paths) != 2:
            self._write("Usage: mv SOURCE DESTINATION\n", "error")
            return
        source, destination = (_resolve_path(self.cwd, value) for value in paths)
        if not os.path.exists(source):
            raise FileNotFoundError(source)
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source.rstrip(os.sep)))
        result = shutil.move(source, destination)
        self._write(f"Moved to: {result}\n")

    def _file_remove(self, paths, recursive=False):
        recursive = recursive or "-r" in paths or "-R" in paths
        force = "-f" in paths
        targets = [value for value in paths if value not in ("-r", "-R", "-f")]
        if not targets:
            self._write("Usage: rm [-r] FILE_OR_DIRECTORY [ ... ]\n", "error")
            return
        for value in targets:
            path = _resolve_path(self.cwd, value)
            if not os.path.lexists(path):
                if not force:
                    self._write(f"Not found: {path}\n", "error")
                continue
            if os.path.abspath(path) == os.path.abspath(self.cwd):
                raise ValueError("Refusing to remove the current directory.")
            if os.path.isdir(path) and not os.path.islink(path):
                if not recursive:
                    raise IsADirectoryError(f"Use rm -r to remove directory: {path}")
                shutil.rmtree(path)
            else:
                os.remove(path)
            self._write(f"Removed: {path}\n")

    def _file_rmdir(self, paths):
        if not paths:
            self._write("Usage: rmdir DIRECTORY [DIRECTORY ...]\n", "error")
            return
        for value in paths:
            path = _resolve_path(self.cwd, value)
            os.rmdir(path)
            self._write(f"Directory removed: {path}\n")

    def _expand_aliases(self, text):
        expanded = text
        for _ in range(16):
            name, separator, arguments = expanded.partition(" ")
            replacement = self._aliases.get(name)
            if replacement is None:
                break
            expanded = replacement + (f" {arguments}" if separator else "")
        return expanded

    def _show_help(self, topic=""):
        self._write("\n  TERMINAL HELP\n", "help_title")
        self._write("  " + "=" * 62 + "\n", "help_rule")
        if topic.lower() == "alias":
            self._write_help_section("ALIASES", [
                ("alias", "list defined aliases"),
                ("alias NAME=COMMAND", "create or replace an alias"),
                ("unalias NAME", "remove an alias"),
            ])
            self._write("\n  Example: alias ll=Get-ChildItem -Force\n", "help_note")
            return
        self._write_help_section("GENERAL", [
            ("help [TOPIC]", "show command help"),
            ("?", "shortcut for help"),
            ("clear, cls", "clear terminal output"),
        ])
        self._write_help_section("NAVIGATION", [
            ("cd [PATH]", "change directory; no path opens home"),
            ("cd -", "return to the previous directory"),
            ("up", "move to the parent directory"),
            ("home", "move to the home directory"),
            ("pwd", "show the current directory"),
            ("ls [PATH], dir [PATH]", "list directory contents"),
        ])
        self._write_help_section("FILE OPERATIONS", [
            ("cat FILE, type FILE", "display file contents"),
            ("touch FILE", "create file or update its timestamp"),
            ("mkdir [-p] DIR", "create directory; -p creates parents"),
            ("cp SOURCE DEST", "copy a file or directory"),
            ("mv SOURCE DEST", "move or rename a file or directory"),
            ("rm [-r] PATH", "delete file; -r also removes directories"),
            ("del FILE, rmdir DIR", "delete file or empty directory"),
        ])
        self._write_help_section("ALIASES", [
            ("alias", "list defined aliases"),
            ("alias NAME=COMMAND", "create or replace an alias"),
            ("unalias NAME", "remove an alias"),
        ])
        self._write("\n  Shell commands are passed to the active session. Use Up/Down for history.\n", "help_note")
        if self._on_plugin_command is not None:
            self._write("  Plugin commands: type /alias args (e.g. /files/read file.txt).\n", "help_note")

    def _write_help_section(self, title, entries):
        self._write(f"\n  {title}\n", "help_section")
        self._write(f"  {'COMMAND':<26} | DESCRIPTION\n", "help_column_header")
        self._write("  " + "-" * 26 + "-+-" + "-" * 42 + "\n", "help_rule")
        for command, description in entries:
            self._write(f"  {command:<26}", "help_command")
            self._write(" | ", "help_rule")
            self._write(f"{description}\n", "help_description")

    def _handle_alias(self, specification):
        if not specification:
            if len(self._aliases) == 1:
                self._write("No user aliases defined.\n")
                return
            for name, command in sorted(self._aliases.items()):
                self._write(f"{name}={command}\n")
            return

        if "=" in specification:
            name, _, command = specification.partition("=")
        else:
            name, separator, command = specification.partition(" ")
            if not separator:
                self._write("Usage: alias NAME=COMMAND\n", "error")
                return
        name = name.strip()
        command = command.strip()
        if not name.isidentifier() or name in ("help", "alias", "unalias", "?"):
            self._write("Alias name must be an identifier and cannot override a terminal command.\n", "error")
            return
        if not command:
            self._write("Alias command cannot be empty.\n", "error")
            return
        self._aliases[name] = command
        self._write(f"Alias set: {name}={command}\n")

    def _handle_unalias(self, name):
        if not name:
            self._write("Usage: unalias NAME\n", "error")
            return
        if name not in self._aliases or name == "?":
            self._write(f"Alias not found: {name}\n", "error")
            return
        del self._aliases[name]
        self._write(f"Alias removed: {name}\n")

    def _start_shell(self):
        try:
            self._process, name = _open_shell(self.cwd)
        except Exception as exc:
            self._status_label.configure(text=self._tr("Nie mozna uruchomic powloki"), fg="#e06c75")
            self._write(self._tr("Blad uruchomienia powloki") + f": {exc}\n", "error")
            return
        self._shell_name = name
        self._status_label.configure(text=f"{self._tr('Sesja')}: {name} | {self.cwd}", fg="#6dde84")
        threading.Thread(target=self._read_output, args=(self._process,), daemon=True).start()

    def _read_output(self, process):
        try:
            while True:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                self._output_queue.put(("output", process, chunk.decode(self._encoding, errors="replace")))
        except (OSError, ValueError):
            pass
        self._output_queue.put(("done", process, process.wait()))

    def _drain_output(self):
        output_segments = []
        output_size = 0
        completed = []
        try:
            while output_size < MAX_OUTPUT_BATCH:
                kind, process, value = self._output_queue.get_nowait()
                if kind == "output":
                    if process is self._process:
                        output_segments.append((value, None))
                        output_size += len(value)
                elif kind == "message":
                    output_segments.append(value)
                    output_size += len(value[0])
                elif process is self._process:
                    completed.append((process, value))
        except queue.Empty:
            pass
        if output_segments:
            self._insert_segments(output_segments)
        for process, exit_code in completed:
            if process is self._process:
                self._process = None
                self._status_label.configure(text="Sesja zakonczona", fg="#e06c75")
                self._stop_button.configure(state="disabled")
                self._write(f"\n[Sesja zakonczona, kod: {exit_code}]\n", "error")
        self.after(OUTPUT_POLL_INTERVAL_MS, self._drain_output)

    def stop(self):
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            self._status_label.configure(text="Zamykanie sesji...", fg="#e0c36a")

    def destroy(self):
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
        super().destroy()

    def restart(self):
        self.stop()
        self.after(150, self._start_shell)

    def clear(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.command.focus_set()

    def _interrupt(self, _event=None):
        """Ctrl+C — przerywa bieżącą komendę, nie całą sesję powłoki.

        Wysyła Ctrl+C (^C) do aktywnej powłoki i wypisuje marker przerwania.
        Dopiero gdy sesja jest nieczuła (brak procesu/stdin) przechodzi
        na twarde zatrzymanie (stop()).
        """
        process = self._process
        if process is not None and process.poll() is None:
            if process.stdin is not None:
                try:
                    # Ctrl+C rozumieją cmd.exe/PowerShell/bash interpretując ^C
                    # jako SIGINT dla bieżącego procesu potomnego.
                    process.stdin.write(b"\x03")
                    process.stdin.flush()
                    self._write("^C\n", "error")
                    return "break"
                except Exception:
                    pass
            if os.name == "nt" and hasattr(signal, "CTRL_BREAK_EVENT"):
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                    self._write("^C\n", "error")
                    return "break"
                except Exception:
                    pass
        self.stop()
        return "break"

    def _history_up(self, _event=None):
        if self._history:
            self._history_index = max(0, self._history_index - 1)
            self._replace_command(self._history[self._history_index])
        return "break"

    def _history_down(self, _event=None):
        if self._history:
            self._history_index = min(len(self._history), self._history_index + 1)
            value = self._history[self._history_index] if self._history_index < len(self._history) else ""
            self._replace_command(value)
        return "break"

    def _replace_command(self, value):
        self.command.delete(0, "end")
        self.command.insert(0, value)


def main():
    root = tk.Tk()
    root.title("Terminal")
    root.geometry("900x600")
    TerminalWidget(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()