# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: git_integration.py
# Opis:  Integracja z Git dla wersjonowania skryptów w CodeMate
# ──────────────────────────────────────────────────────────────────────────────

import subprocess
import logging
import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Wykrywanie wykonywalnego git ─────────────────────────────────────────────
# Windows: instalator Git for Windows często nie dopisuje się do PATH bieżącej
# sesji (np. po instalacji przez winget bez ponownego logowania). Wtedy komenda
# "git" kończy się FileNotFoundError, choć git jest zainstalowany. Dlatego
# szukamy binarki w znanych lokalizacjach i cache'ujemy wynik.

_GIT_FALLBACK_DIRS = (
    r"C:\Program Files\Git\cmd",
    r"C:\Program Files\Git\bin",
    r"C:\Program Files (x86)\Git\cmd",
    r"C:\Program Files (x86)\Git\bin",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd"),
)

_git_exe_cache: Optional[str] = None


def find_git() -> Optional[str]:
    """Zwraca pełną ścieżkę do git.exe lub None, gdy git nie jest dostępny.

    Najpierw PATH (shutil.which), potem znane lokalizacje instalacji
    Git for Windows. Wynik jest cache'owany na czas życia procesu.
    """
    global _git_exe_cache
    if _git_exe_cache is not None:
        return _git_exe_cache or None
    found = shutil.which("git")
    if not found:
        for directory in _GIT_FALLBACK_DIRS:
            candidate = os.path.join(directory, "git.exe")
            if os.path.isfile(candidate):
                found = candidate
                break
    _git_exe_cache = found or ""
    if not found:
        logger.warning("Git not found in PATH nor common install locations")
    return found or None

# Na Windows ukrywa okno konsoli przy uruchamianiu ``git`` (brak mrugania).
_SUBPROCESS_NO_WINDOW = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
)


class GitIntegration:
    """
    Klasa do zarządzania wersjonowaniem skryptów przy użyciu Git.

    Funkcjonalności:
    - Automatyczne commity przy zapisie skryptów
    - Zarządzanie branchami
    - Porównywanie wersji (diff)
    - Pobieranie historii zmian
    - Synchronizacja ze zdalnym repozytorium
    """

    # Limit czasu komend Git (sekundy). Zapobiega zawieszeniu UI, gdy np.
    # push/pull czeka na wprowadzenie poświadczeń w oknie credential managera.
    COMMAND_TIMEOUT = 30

    def __init__(self, repo_path: Path, auto_commit: bool = True):
        """
        Inicjalizuje integrację Git.

        Args:
            repo_path: Ścieżka do repozytorium Git.
            auto_commit: Czy automatycznie commitować zmiany.
        """
        self.repo_path = Path(repo_path)
        self.auto_commit = auto_commit
        self.last_error = ""
        self._initialized = self._check_git_repo()

    def _check_git_repo(self) -> bool:
        """Sprawdza czy katalog jest repozytorium Git."""
        git_exe = find_git()
        if not git_exe:
            return False
        try:
            result = subprocess.run(
                [git_exe, "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                creationflags=_SUBPROCESS_NO_WINDOW
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _run_git_command(self, command: List[str]) -> Tuple[bool, str]:
        """
        Wykonuje komendę Git i zwraca wynik.

        Args:
            command: Lista argumentów komendy Git.

        Returns:
            Tuple[bool, str]: (sukces, output/error message)
        """
        git_exe = find_git()
        if not git_exe:
            logger.error("Git is not installed or not in PATH")
            return False, "Git is not installed"
        try:
            result = subprocess.run(
                [git_exe] + command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
                timeout=self.COMMAND_TIMEOUT,
                creationflags=_SUBPROCESS_NO_WINDOW
            )
            return True, result.stdout.rstrip("\r\n")
        except subprocess.TimeoutExpired:
            error_msg = (f"Git command timed out after "
                         f"{self.COMMAND_TIMEOUT}s: {' '.join(command)}")
            logger.error(error_msg)
            return False, error_msg
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Git command failed: {' '.join(command)} - {error_msg}")
            return False, error_msg
        except FileNotFoundError:
            logger.error("Git is not installed or not in PATH")
            return False, "Git is not installed"

    def is_available(self) -> bool:
        """Zwraca czy Git jest dostępny i repozytorium jest zainicjalizowane."""
        return self._initialized

    def init_repo(self) -> bool:
        """
        Inicjalizuje nowe repozytorium Git.

        Returns:
            bool: Czy inicjalizacja się powiodła.
        """
        success, _ = self._run_git_command(["init"])
        if success:
            self._initialized = True
            logger.info(f"Initialized Git repository at {self.repo_path}")
        return success

    def add_file(self, file_path: Path) -> bool:
        """
        Dodaje plik do staging area.

        Args:
            file_path: Ścieżka do pliku.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False
        try:
            rel_path = Path(file_path).resolve().relative_to(
                self.repo_path.resolve())
        except (ValueError, OSError):
            self.last_error = "File is outside the Git repository"
            return False
        success, _ = self._run_git_command(["add", str(rel_path)])
        return success

    def unstage_file(self, file_path: Path) -> bool:
        """Remove a file from the index without changing its working-tree contents."""
        if not self._initialized:
            self.last_error = "Git repository is unavailable"
            return False
        file_path = Path(file_path).resolve()
        try:
            rel_path = file_path.relative_to(self.repo_path.resolve())
        except ValueError:
            self.last_error = "File is outside the Git repository"
            return False
        success, output = self._run_git_command(["reset", "--", str(rel_path)])
        self.last_error = "" if success else output
        return success

    def restore_worktree_file(self, file_path: Path) -> bool:
        """Discard unstaged edits for one tracked file, preserving its index version."""
        if not self._initialized:
            self.last_error = "Git repository is unavailable"
            return False
        file_path = Path(file_path).resolve()
        try:
            rel_path = file_path.relative_to(self.repo_path.resolve())
        except ValueError:
            self.last_error = "File is outside the Git repository"
            return False
        success, output = self._run_git_command(
            ["restore", "--worktree", "--", str(rel_path)])
        self.last_error = "" if success else output
        return success

    def commit(self, message: str, author: str = "CodeMate") -> bool:
        """
        Tworzy commit.

        Args:
            message: Wiadomość commita.
            author: Autor commita.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False
        success, _ = self._run_git_command([
            "commit",
            "-m", message,
            "--author", f"{author} <codemate@local>"
        ])
        return success

    def commit_script_change(self, script_id: str, script_name: str,
                            change_type: str = "update") -> bool:
        """
        Automatycznie commituje zmianę w skrypcie.

        Args:
            script_id: ID skryptu.
            script_name: Nazwa skryptu.
            change_type: Typ zmiany (create, update, delete).

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self.auto_commit or not self._initialized:
            return False

        db_file = self.repo_path / "baza_skryptow.json"
        if not db_file.exists():
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"[{change_type.upper()}] {script_name} (ID: {script_id}) - {timestamp}"

        if self.add_file(db_file):
            return self.commit(message)
        return False

    def get_branches(self) -> List[str]:
        """
        Pobiera listę branchów.

        Returns:
            List[str]: Lista nazw branchów.
        """
        if not self._initialized:
            return []
        success, output = self._run_git_command(["branch", "--format=%(refname:short)"])
        if success:
            return output.split("\n") if output else []
        return []

    def get_current_branch(self) -> Optional[str]:
        """
        Pobiera nazwę aktualnego brancha.

        Returns:
            Optional[str]: Nazwa brancha lub None.
        """
        if not self._initialized:
            return None
        success, output = self._run_git_command(["branch", "--show-current"])
        return output if success else None

    def create_branch(self, branch_name: str) -> bool:
        """
        Tworzy nowy branch.

        Args:
            branch_name: Nazwa nowego brancha.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False
        success, _ = self._run_git_command(["branch", branch_name])
        return success

    def checkout_branch(self, branch_name: str) -> bool:
        """
        Przełącza na branch.

        Args:
            branch_name: Nazwa brancha.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False
        success, _ = self._run_git_command(["checkout", branch_name])
        return success

    def get_history(self, file_path: Optional[Path] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
        """
        Pobiera historię commitów.

        Args:
            file_path: Opcjonalna ścieżka do pliku (dla filtrowania).
            limit: Maksymalna liczba commitów.

        Returns:
            List[Dict[str, Any]]: Lista commitów z metadanymi.
        """
        if not self._initialized:
            return []

        command = ["log", f"-{limit}", "--format=%H|%an|%ai|%s"]
        if file_path:
            try:
                rel_path = Path(file_path).resolve().relative_to(
                    self.repo_path.resolve())
            except (ValueError, OSError):
                self.last_error = "File is outside the Git repository"
                return []
            command.append(str(rel_path))

        success, output = self._run_git_command(command)
        if not success:
            return []

        commits = []
        for line in output.split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                })
        return commits

    def get_diff(self, commit_hash1: str, commit_hash2: Optional[str] = None,
                file_path: Optional[Path] = None) -> str:
        """
        Pobiera diff między dwoma commitami.

        Args:
            commit_hash1: Hash pierwszego commita.
            commit_hash2: Hash drugiego commita (None = porównaj z working directory).
            file_path: Opcjonalna ścieżka do pliku.

        Returns:
            str: Diff output.
        """
        if not self._initialized:
            return ""

        command = ["diff"]
        if commit_hash2:
            command.extend([commit_hash1, commit_hash2])
        else:
            command.append(commit_hash1)

        if file_path:
            try:
                rel_path = Path(file_path).resolve().relative_to(
                    self.repo_path.resolve())
            except (ValueError, OSError):
                self.last_error = "File is outside the Git repository"
                return ""
            command.append("--")
            command.append(str(rel_path))

        success, output = self._run_git_command(command)
        return output if success else ""

    def get_commit_diff(self, commit_hash: str) -> str:
        """Returns a commit's patch, including the initial commit's files."""
        if not self._initialized or not re.fullmatch(r"[0-9a-fA-F]{4,64}", commit_hash or ""):
            return ""
        success, output = self._run_git_command([
            "show", "--root", "--format=fuller", "--stat", "--patch", commit_hash])
        return output if success else ""

    def get_file_at_commit(self, file_path: Path, commit_hash: str) -> Optional[str]:
        """
        Pobiera zawartość pliku z konkretnego commita.

        Args:
            file_path: Ścieżka do pliku.
            commit_hash: Hash commita.

        Returns:
            Optional[str]: Zawartość pliku lub None.
        """
        if not self._initialized:
            return None

        try:
            rel_path = Path(file_path).resolve().relative_to(
                self.repo_path.resolve())
        except (ValueError, OSError):
            return None
        success, output = self._run_git_command(["show", f"{commit_hash}:{rel_path}"])
        return output if success else None

    def restore_file(self, file_path: Path, commit_hash: str) -> bool:
        """
        Przywraca plik z konkretnego commita.

        Args:
            file_path: Ścieżka do pliku.
            commit_hash: Hash commita.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False

        try:
            rel_path = Path(file_path).resolve().relative_to(
                self.repo_path.resolve())
        except (ValueError, OSError):
            self.last_error = "File is outside the Git repository"
            return False
        success, _ = self._run_git_command(["checkout", commit_hash, "--", str(rel_path)])
        return success

    def add_remote(self, name: str, url: str) -> bool:
        """
        Dodaje zdalne repozytorium.

        Args:
            name: Nazwa remote (np. "origin").
            url: URL repozytorium.

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False
        success, _ = self._run_git_command(["remote", "add", name, url])
        return success

    def set_remote(self, name: str, url: str) -> bool:
        """Add or update a named remote without invoking a shell."""
        if not self._initialized or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name or ""):
            self.last_error = "Invalid remote name or repository is unavailable"
            return False
        if not url or url.startswith("-") or "\n" in url or "\r" in url:
            self.last_error = "Remote URL is empty or invalid"
            return False
        exists, _ = self._run_git_command(["remote", "get-url", name])
        command = ["remote", "set-url", name, url] if exists else ["remote", "add", name, url]
        success, output = self._run_git_command(command)
        self.last_error = "" if success else output
        return success

    def sync_file(self, file_path: Path, remote: str = "origin",
                  branch: Optional[str] = None) -> bool:
        """Commit one file locally and push; rejected pushes preserve local commits."""
        if not self._initialized:
            self.last_error = "Git repository is unavailable"
            return False
        file_path = Path(file_path).resolve()
        try:
            file_path.relative_to(self.repo_path.resolve())
        except ValueError:
            self.last_error = "File is outside the Git repository"
            return False
        branch = branch or self.get_current_branch()
        if not branch:
            self.last_error = "Current branch is unavailable"
            return False
        if not self.add_file(file_path):
            self.last_error = "Could not stage database file"
            return False
        relative = str(file_path.relative_to(self.repo_path.resolve()))
        has_staged_change, staged_output = self._run_git_command(
            ["diff", "--cached", "--name-only", "--", relative])
        if not has_staged_change:
            self.last_error = staged_output
            return False
        if staged_output:
            success, output = self._run_git_command([
                "commit", "--only", "-m", f"[SYNC] {file_path.name}", "--", relative])
            if not success:
                self.last_error = output
                return False
        success, output = self._run_git_command(["push", remote, branch])
        self.last_error = "" if success else output
        return success

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """
        Wypycha zmiany do zdalnego repozytorium.

        Args:
            remote: Nazwa remote.
            branch: Nazwa brancha (None = aktualny branch).

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False

        if branch is None:
            branch = self.get_current_branch()

        if not branch:
            return False

        success, _ = self._run_git_command(["push", remote, branch])
        return success

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """
        Pobiera zmiany ze zdalnego repozytorium.

        Args:
            remote: Nazwa remote.
            branch: Nazwa brancha (None = aktualny branch).

        Returns:
            bool: Czy operacja się powiodła.
        """
        if not self._initialized:
            return False

        if branch is None:
            branch = self.get_current_branch()

        if not branch:
            return False

        success, output = self._run_git_command(["pull", "--ff-only", remote, branch])
        self.last_error = "" if success else output
        return success

    def status(self) -> Dict[str, Any]:
        """
        Pobiera status repozytorium.

        Returns:
            Dict[str, Any]: Status repozytorium (branch, modified, staged, etc.)
        """
        if not self._initialized:
            return {}

        status: Dict[str, Any] = {
            "branch": self.get_current_branch(),
            "modified": [],
            "staged": [],
            "untracked": []
        }

        success, output = self._run_git_command(["status", "--porcelain"])
        if not success:
            return status

        for line in output.split("\n"):
            if not line:
                continue
            if len(line) >= 2:
                index_status, worktree_status = line[0], line[1]
                file = line[3:].strip() if len(line) > 2 else ""
                if not file:
                    file = line[2:].strip()
                if index_status in "MADRCU":
                    status["staged"].append(file)
                if worktree_status in "MADRCU":
                    status["modified"].append(file)
                if index_status == "?" and worktree_status == "?":
                    status["untracked"].append(file)

        return status
