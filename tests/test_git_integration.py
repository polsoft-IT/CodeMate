"""
Testy dla integracji Git.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from src.git_integration import GitIntegration


@pytest.fixture
def temp_repo_path(tmp_path):
    """Fixture dostarczający tymczasowe repozytorium Git."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return repo_path


@pytest.fixture
def git_integration(temp_repo_path):
    """Fixture dostarczający instancję GitIntegration."""
    return GitIntegration(temp_repo_path, auto_commit=False)


class TestGitIntegration:
    """Testy klasy GitIntegration."""

    def test_init(self, temp_repo_path):
        """Test inicjalizacji GitIntegration."""
        git = GitIntegration(temp_repo_path, auto_commit=True)

        assert git.repo_path == temp_repo_path
        assert git.auto_commit is True
        assert git._initialized is False  # repozytorium nie istnieje

    def test_check_git_repo_not_initialized(self, git_integration):
        """Test sprawdzania czy katalog nie jest repozytorium Git."""
        assert git_integration._check_git_repo() is False

    @patch('subprocess.run')
    def test_init_repo(self, mock_run, git_integration):
        """Test inicjalizacji repozytorium."""
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.init_repo()

        assert result is True
        assert git_integration._initialized is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_add_file(self, mock_run, git_integration, temp_repo_path):
        """Test dodawania pliku do staging area."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        test_file = temp_repo_path / "test.txt"
        test_file.touch()

        result = git_integration.add_file(test_file)

        assert result is True
        mock_run.assert_called_once()

    def test_unstage_file_preserves_path_scope(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        file_path = temp_repo_path / "src" / "app.py"
        commands = []
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda command: commands.append(command) or (True, ""))

        assert git_integration.unstage_file(file_path)
        assert commands == [["reset", "--", "src\\app.py"]]
        assert git_integration.last_error == ""

    def test_unstage_file_refuses_external_path(self, git_integration, tmp_path, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda _command: pytest.fail("external path must not run a Git command"))

        assert not git_integration.unstage_file(tmp_path / "outside.txt")
        assert "outside" in git_integration.last_error

    def test_restore_worktree_file_preserves_index_version(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        file_path = temp_repo_path / "src" / "app.py"
        commands = []
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda command: commands.append(command) or (True, ""))

        assert git_integration.restore_worktree_file(file_path)
        assert commands == [["restore", "--worktree", "--", "src\\app.py"]]
        assert git_integration.last_error == ""

    def test_restore_worktree_file_refuses_external_path(self, git_integration, tmp_path, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda _command: pytest.fail("external path must not run a Git command"))

        assert not git_integration.restore_worktree_file(tmp_path / "outside.txt")
        assert "outside" in git_integration.last_error

    @patch('subprocess.run')
    def test_commit(self, mock_run, git_integration):
        """Test tworzenia commita."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.commit("Test commit")

        assert result is True
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_commit_script_change(self, mock_run, git_integration, temp_repo_path):
        """Test automatycznego commitu zmiany skryptu."""
        git_integration._initialized = True
        git_integration.auto_commit = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        db_file = temp_repo_path / "baza_skryptow.json"
        db_file.touch()

        result = git_integration.commit_script_change(
            script_id="test-id",
            script_name="Test Script",
            change_type="update"
        )

        assert result is True

    def test_commit_script_change_disabled(self, git_integration):
        """Test że commit nie jest wykonywany gdy auto_commit=False."""
        git_integration.auto_commit = False

        result = git_integration.commit_script_change(
            script_id="test-id",
            script_name="Test Script"
        )

        assert result is False

    @patch('subprocess.run')
    def test_get_branches(self, mock_run, git_integration):
        """Test pobierania listy branchów."""
        git_integration._initialized = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="main\nfeature/test"
        )

        branches = git_integration.get_branches()

        assert len(branches) == 2
        assert "main" in branches
        assert "feature/test" in branches

    @patch('subprocess.run')
    def test_get_current_branch(self, mock_run, git_integration):
        """Test pobierania aktualnego brancha."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="main")

        branch = git_integration.get_current_branch()

        assert branch == "main"

    @patch('subprocess.run')
    def test_create_branch(self, mock_run, git_integration):
        """Test tworzenia nowego brancha."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.create_branch("feature/new")

        assert result is True

    @patch('subprocess.run')
    def test_checkout_branch(self, mock_run, git_integration):
        """Test przełączania brancha."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.checkout_branch("feature/new")

        assert result is True

    @patch('subprocess.run')
    def test_get_history(self, mock_run, git_integration):
        """Test pobierania historii commitów."""
        git_integration._initialized = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123|Author|2024-01-01 00:00:00|Test commit\n"
        )

        history = git_integration.get_history(limit=10)

        assert len(history) == 1
        assert history[0]["hash"] == "abc123"
        assert history[0]["author"] == "Author"
        assert history[0]["message"] == "Test commit"

    @patch('subprocess.run')
    def test_get_diff(self, mock_run, git_integration):
        """Test pobierania diffa."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="diff output")

        diff = git_integration.get_diff("abc123", "def456")

        assert diff == "diff output"

    def test_get_commit_diff_includes_root_commits(self, git_integration, monkeypatch):
        git_integration._initialized = True
        commands = []
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda command: commands.append(command) or (True, "commit diff"))

        assert git_integration.get_commit_diff("a1b2c3d4") == "commit diff"
        assert commands == [[
            "show", "--root", "--format=fuller", "--stat", "--patch", "a1b2c3d4"]]

    def test_get_commit_diff_rejects_non_hash(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda _command: pytest.fail("invalid hash must not run a Git command"))

        assert git_integration.get_commit_diff("HEAD; status") == ""

    @patch('subprocess.run')
    def test_get_file_at_commit(self, mock_run, git_integration, temp_repo_path):
        """Test pobierania pliku z konkretnego commita."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="file content")

        test_file = temp_repo_path / "test.txt"
        content = git_integration.get_file_at_commit(test_file, "abc123")

        assert content == "file content"

    @patch('subprocess.run')
    def test_restore_file(self, mock_run, git_integration, temp_repo_path):
        """Test przywracania pliku z commita."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        test_file = temp_repo_path / "test.txt"
        result = git_integration.restore_file(test_file, "abc123")

        assert result is True

    @patch('subprocess.run')
    def test_add_remote(self, mock_run, git_integration):
        """Test dodawania zdalnego repozytorium."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.add_remote("origin", "https://github.com/test/repo.git")

        assert result is True

    @patch('subprocess.run')
    def test_push(self, mock_run, git_integration):
        """Test push do zdalnego repozytorium."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.push("origin", "main")

        assert result is True

    @patch('subprocess.run')
    def test_pull(self, mock_run, git_integration):
        """Test pull ze zdalnego repozytorium."""
        git_integration._initialized = True
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_integration.pull("origin", "main")

        assert result is True
        assert "--ff-only" in mock_run.call_args[0][0]

    def test_set_remote_adds_missing_remote(self, git_integration, monkeypatch):
        git_integration._initialized = True
        commands = []

        def run(command):
            commands.append(command)
            return (False, "missing") if command[:2] == ["remote", "get-url"] else (True, "")

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        assert git_integration.set_remote("origin", "https://example.test/repo.git")
        assert commands[-1] == ["remote", "add", "origin", "https://example.test/repo.git"]

    def test_sync_file_stages_commits_and_pushes(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        database = temp_repo_path / "baza.json"
        database.touch()
        actions = []
        monkeypatch.setattr(git_integration, "add_file", lambda path: actions.append(("add", path)) or True)
        monkeypatch.setattr(git_integration, "commit", lambda message: actions.append(("commit", message)) or True)
        def git_command(command):
            actions.append(("git", command))
            return True, "baza.json" if command[0:3] == ["diff", "--cached", "--name-only"] else ""

        monkeypatch.setattr(git_integration, "_run_git_command", git_command)
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        assert git_integration.sync_file(database)
        assert [action[0] for action in actions] == ["add", "git", "git", "git"]
        assert actions[2][1][:3] == ["commit", "--only", "-m"]
        assert actions[-1][1] == ["push", "origin", "main"]

    def test_sync_file_refuses_external_path(self, git_integration, tmp_path):
        git_integration._initialized = True
        assert not git_integration.sync_file(tmp_path / "outside.json")
        assert "outside" in git_integration.last_error

    @patch('subprocess.run')
    def test_status(self, mock_run, git_integration):
        """Test statusu repozytorium."""
        git_integration._initialized = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" M file1.txt\n M file2.txt\n?? newfile.txt"
        )

        status = git_integration.status()

        assert status["branch"] is not None
        assert len(status["modified"]) == 2
        assert status["staged"] == []
        assert len(status["untracked"]) == 1

    def test_status_separates_index_and_worktree_changes(self, git_integration, monkeypatch):
        git_integration._initialized = True
        commands = []

        def run(command):
            commands.append(command)
            if command == ["branch", "--show-current"]:
                return True, "main"
            return True, "M  staged.txt\n M working.txt\nMM both.txt\n?? new.txt"

        monkeypatch.setattr(git_integration, "_run_git_command", run)

        status = git_integration.status()

        assert status["staged"] == ["staged.txt", "both.txt"]
        assert status["modified"] == ["working.txt", "both.txt"]
        assert status["untracked"] == ["new.txt"]


class TestUninitializedPaths:
    """Wszystkie metody powinny bezpiecznie zwracać błąd, gdy repo nie jest zainicjalizowane."""

    def test_is_available_false(self, git_integration):
        assert git_integration.is_available() is False

    def test_add_file_not_initialized(self, git_integration, temp_repo_path):
        assert git_integration.add_file(temp_repo_path / "f.txt") is False

    def test_unstage_file_not_initialized(self, git_integration, temp_repo_path):
        assert git_integration.unstage_file(temp_repo_path / "f.txt") is False
        assert git_integration.last_error == "Git repository is unavailable"

    def test_restore_worktree_file_not_initialized(self, git_integration, temp_repo_path):
        assert git_integration.restore_worktree_file(temp_repo_path / "f.txt") is False
        assert git_integration.last_error == "Git repository is unavailable"

    def test_commit_not_initialized(self, git_integration):
        assert git_integration.commit("msg") is False

    def test_commit_script_change_no_db_file(self, git_integration, temp_repo_path):
        git_integration._initialized = True
        git_integration.auto_commit = True
        # brak baza_skryptow.json w repo
        assert git_integration.commit_script_change("id", "name") is False

    def test_status_empty_line_and_untracked(self, git_integration, monkeypatch):
        """Linie puste / krótkie w porcelain są pomijane (linie 561/566)."""
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (True, "\n?? x.txt") if cmd[0] == "status" else (True, "main"))
        st = git_integration.status()
        assert st["untracked"] == ["x.txt"]
        assert st["staged"] == []

    def test_status_two_char_line_fallback(self, git_integration, monkeypatch):
        """Linia 2-znakowa (file puste przez [3:]) używa fallbacku line[2:] (linia 566)."""
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (True, "??") if cmd[0] == "status" else (True, "main"))
        st = git_integration.status()
        assert "" in st["untracked"]

    def test_commit_script_change_add_fails_returns_false(self, git_integration, temp_repo_path, monkeypatch):
        """Nieudany add_file → commit_script_change zwraca False (linia 256)."""
        git_integration._initialized = True
        git_integration.auto_commit = True
        (git_integration.repo_path / "baza_skryptow.json").touch()
        monkeypatch.setattr(git_integration, "add_file", lambda p: False)
        assert git_integration.commit_script_change("id", "name") is False

    def test_get_branches_not_initialized(self, git_integration):
        assert git_integration.get_branches() == []

    def test_get_current_branch_not_initialized(self, git_integration):
        assert git_integration.get_current_branch() is None

    def test_create_branch_not_initialized(self, git_integration):
        assert git_integration.create_branch("x") is False

    def test_checkout_branch_not_initialized(self, git_integration):
        assert git_integration.checkout_branch("x") is False

    def test_get_history_not_initialized(self, git_integration):
        assert git_integration.get_history() == []

    def test_get_diff_not_initialized(self, git_integration):
        assert git_integration.get_diff("abc") == ""

    def test_get_file_at_commit_not_initialized(self, git_integration, temp_repo_path):
        assert git_integration.get_file_at_commit(temp_repo_path / "f", "abc") is None

    def test_restore_file_not_initialized(self, git_integration, temp_repo_path):
        assert git_integration.restore_file(temp_repo_path / "f", "abc") is False

    def test_add_remote_not_initialized(self, git_integration):
        assert git_integration.add_remote("origin", "url") is False

    def test_set_remote_not_initialized(self, git_integration):
        assert git_integration.set_remote("origin", "https://x") is False
        assert "unavailable" in git_integration.last_error

    def test_sync_file_not_initialized(self, git_integration, temp_repo_path):
        assert git_integration.sync_file(temp_repo_path / "f") is False
        assert git_integration.last_error == "Git repository is unavailable"

    def test_push_not_initialized(self, git_integration):
        assert git_integration.push() is False

    def test_pull_not_initialized(self, git_integration):
        assert git_integration.pull() is False

    def test_status_not_initialized(self, git_integration):
        assert git_integration.status() == {}


class TestGitCommandFailures:
    """Błędy wykonania komend Git i nietypowe wyniki."""

    def test_run_git_command_git_not_installed(self, git_integration):
        with patch('subprocess.run', side_effect=FileNotFoundError):
            success, output = git_integration._run_git_command(["status"])
        assert success is False
        assert output == "Git is not installed"

    def test_run_git_command_called_process_error(self, git_integration):
        error = subprocess.CalledProcessError(1, ["git"], stderr="fatal: nope")
        with patch('subprocess.run', side_effect=error):
            success, output = git_integration._run_git_command(["status"])
        assert success is False
        assert output == "fatal: nope"

    def test_check_git_repo_git_not_installed(self, temp_repo_path):
        with patch('subprocess.run', side_effect=FileNotFoundError):
            git = GitIntegration(temp_repo_path)
        assert git._initialized is False

    def test_get_branches_command_failure(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (False, "err"))
        assert git_integration.get_branches() == []

    def test_get_branches_empty_output(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (True, ""))
        assert git_integration.get_branches() == []

    def test_get_current_branch_failure(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (False, "err"))
        assert git_integration.get_current_branch() is None

    def test_commit_script_change_add_file_fails(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        git_integration.auto_commit = True
        (temp_repo_path / "baza_skryptow.json").touch()
        monkeypatch.setattr(git_integration, "add_file", lambda p: False)
        assert git_integration.commit_script_change("id", "name") is False

    def test_commit_script_change_commit_fails(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        git_integration.auto_commit = True
        (temp_repo_path / "baza_skryptow.json").touch()
        monkeypatch.setattr(git_integration, "commit", lambda *a, **k: False)
        assert git_integration.commit_script_change("id", "name") is False

    def test_get_history_with_file_path(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        commands = []

        def run(command):
            commands.append(command)
            return True, "h1|A|2024-01-01|msg\n\nbadline\nh2|B|2024-01-02|msg2"

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        history = git_integration.get_history(file_path=temp_repo_path / "f.txt", limit=5)

        assert commands[0][-1] == "f.txt"
        assert commands[0][1] == "-5"
        assert len(history) == 2
        assert history[0]["hash"] == "h1"
        assert history[1]["message"] == "msg2"

    def test_get_history_command_failure(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (False, "err"))
        assert git_integration.get_history() == []

    def test_get_diff_single_commit(self, git_integration, monkeypatch):
        git_integration._initialized = True
        commands = []
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda command: commands.append(command) or (True, "diff"))
        assert git_integration.get_diff("abc123") == "diff"
        assert commands == [["diff", "abc123"]]

    def test_get_diff_with_file_path(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        commands = []
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda command: commands.append(command) or (True, "diff"))
        git_integration.get_diff("abc", file_path=temp_repo_path / "dir" / "f.txt")
        assert commands == [["diff", "abc", "--", str(Path("dir") / "f.txt")]]

    def test_get_diff_command_failure(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (False, "err"))
        assert git_integration.get_diff("abc", "def") == ""

    def test_set_remote_invalid_name(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda _cmd: pytest.fail("invalid name must not run Git"))
        assert git_integration.set_remote("zła nazwa!", "https://x") is False
        assert "Invalid remote" in git_integration.last_error

    def test_set_remote_invalid_url(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(
            git_integration, "_run_git_command",
            lambda _cmd: pytest.fail("invalid url must not run Git"))
        assert git_integration.set_remote("origin", "-evil\nflag") is False
        assert "URL" in git_integration.last_error

    def test_set_remote_updates_existing(self, git_integration, monkeypatch):
        git_integration._initialized = True
        commands = []

        def run(command):
            commands.append(command)
            return (True, "https://old") if command[:2] == ["remote", "get-url"] else (True, "")

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        assert git_integration.set_remote("origin", "https://new")
        assert commands[-1] == ["remote", "set-url", "origin", "https://new"]
        assert git_integration.last_error == ""

    def test_set_remote_command_failure(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (False, "err"))
        assert git_integration.set_remote("origin", "https://x") is False
        assert git_integration.last_error == "err"

    def test_push_uses_current_branch_when_none(self, git_integration, monkeypatch):
        git_integration._initialized = True
        commands = []

        def run(command):
            commands.append(command)
            return (True, "main") if command == ["branch", "--show-current"] else (True, "")

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        assert git_integration.push()
        assert commands[-1] == ["push", "origin", "main"]

    def test_push_no_branch(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: None)
        assert git_integration.push() is False

    def test_pull_no_branch(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "")
        assert git_integration.pull() is False

    def test_pull_command_failure_sets_last_error(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command", lambda cmd: (False, "pull err"))
        assert git_integration.pull("origin", "main") is False
        assert git_integration.last_error == "pull err"

    def test_sync_file_no_branch(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: None)
        f = temp_repo_path / "baza.json"
        f.touch()
        assert git_integration.sync_file(f) is False
        assert "branch" in git_integration.last_error.lower()

    def test_sync_file_add_file_fails(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "add_file", lambda p: False)
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        f = temp_repo_path / "baza.json"
        f.touch()
        assert git_integration.sync_file(f) is False
        assert "stage" in git_integration.last_error.lower()

    def test_sync_file_no_staged_change(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "add_file", lambda p: True)
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")

        def run(command):
            # diff --cached kończy się niepowodzeniem = brak staged zmian
            if command[0:3] == ["diff", "--cached", "--name-only"]:
                return False, ""
            return True, ""

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        f = temp_repo_path / "baza.json"
        f.touch()
        assert git_integration.sync_file(f) is False
        assert git_integration.last_error == ""

    def test_sync_file_commit_fails(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True

        def run(command):
            if command[0:3] == ["diff", "--cached", "--name-only"]:
                return True, "baza.json"
            if command[0] == "commit":
                return False, "commit err"
            return True, ""

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        monkeypatch.setattr(git_integration, "add_file", lambda p: True)
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        f = temp_repo_path / "baza.json"
        f.touch()
        assert git_integration.sync_file(f) is False
        assert git_integration.last_error == "commit err"

    def test_sync_file_push_fails(self, git_integration, temp_repo_path, monkeypatch):
        git_integration._initialized = True

        def run(command):
            if command[0:3] == ["diff", "--cached", "--name-only"]:
                return True, ""
            if command[0] == "push":
                return False, "push err"
            return True, ""

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        monkeypatch.setattr(git_integration, "add_file", lambda p: True)
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        f = temp_repo_path / "baza.json"
        f.touch()
        assert git_integration.sync_file(f) is False
        assert git_integration.last_error == "push err"

    def test_status_command_failure(self, git_integration, monkeypatch):
        git_integration._initialized = True

        def run(command):
            if command == ["branch", "--show-current"]:
                return True, "main"
            return False, "status err"

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        status = git_integration.status()
        assert status["branch"] == "main"
        assert status["modified"] == []

    def test_status_skips_empty_and_short_lines(self, git_integration, monkeypatch):
        git_integration._initialized = True

        def run(command):
            if command == ["branch", "--show-current"]:
                return True, "main"
            # pusta linia, linia 2-znakowa i zwykły wpis
            return True, "\nM \n M real.txt"

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        status = git_integration.status()
        # linia "M " (2 znaki) daje pustą nazwę pliku przez fallback line[2:]
        assert status["staged"] == [""]
        assert status["modified"] == ["real.txt"]
        assert status["untracked"] == []


def _real_git(repo_path, *args):
    from src.git_integration import find_git
    git_exe = find_git()
    if not git_exe:
        pytest.skip("git not available on this machine")
    return subprocess.run(
        [git_exe, *args], cwd=repo_path, capture_output=True, text=True, check=True)


def _configure_real_repo(repo_path):
    _real_git(repo_path, "config", "user.name", "Integration Test")
    _real_git(repo_path, "config", "user.email", "integration@example.invalid")


@pytest.mark.integration
def test_unstage_file_preserves_working_tree_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _real_git(repo, "init", "--initial-branch=main")
    _configure_real_repo(repo)
    _real_git(repo, "add", "tracked.txt")
    _real_git(repo, "commit", "-m", "initial")

    tracked.write_text("working change\n", encoding="utf-8")
    git = GitIntegration(repo, auto_commit=False)
    assert git.add_file(tracked)
    assert git.status()["staged"] == ["tracked.txt"]

    assert git.unstage_file(tracked)
    status = git.status()
    assert status["staged"] == []
    assert status["modified"] == ["tracked.txt"]
    assert tracked.read_text(encoding="utf-8") == "working change\n"


@pytest.mark.integration
def test_restore_worktree_file_keeps_staged_version(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _real_git(repo, "init", "--initial-branch=main")
    _configure_real_repo(repo)
    _real_git(repo, "add", "tracked.txt")
    _real_git(repo, "commit", "-m", "initial")

    tracked.write_text("staged version\n", encoding="utf-8")
    _real_git(repo, "add", "tracked.txt")
    tracked.write_text("unstaged version\n", encoding="utf-8")
    git = GitIntegration(repo, auto_commit=False)

    assert git.restore_worktree_file(tracked)
    status = git.status()
    assert status["staged"] == ["tracked.txt"]
    assert status["modified"] == []
    assert tracked.read_text(encoding="utf-8") == "staged version\n"


@pytest.mark.integration
@pytest.mark.slow
def test_sync_file_pushes_only_database_to_real_remote(tmp_path):
    bare = tmp_path / "remote.git"
    local = tmp_path / "local"
    local.mkdir()
    database = local / "baza_skryptow.json"
    database.write_text("version 1\n", encoding="utf-8")
    _real_git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))
    _real_git(local, "init", "--initial-branch=main")
    _configure_real_repo(local)
    _real_git(local, "add", "baza_skryptow.json")
    _real_git(local, "commit", "-m", "initial database")
    _real_git(local, "remote", "add", "origin", str(bare))
    _real_git(local, "push", "-u", "origin", "main")

    unrelated = local / "unrelated.txt"
    unrelated.write_text("keep staged locally\n", encoding="utf-8")
    _real_git(local, "add", "unrelated.txt")
    database.write_text("version 2\n", encoding="utf-8")

    integration = GitIntegration(local, auto_commit=False)
    assert integration.sync_file(database)
    remote_database = _real_git(
        bare, "--git-dir", str(bare), "show", "main:baza_skryptow.json")
    assert remote_database.stdout == "version 2\n"
    remote_files = _real_git(bare, "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main")
    assert "unrelated.txt" not in remote_files.stdout.splitlines()
    assert _real_git(local, "diff", "--cached", "--name-only").stdout.strip() == "unrelated.txt"


@pytest.mark.integration
@pytest.mark.slow
def test_pull_fast_forward_and_divergence_preserve_local_commit(tmp_path):
    bare = tmp_path / "remote.git"
    local = tmp_path / "local"
    peer = tmp_path / "peer"
    local.mkdir()
    database = local / "baza_skryptow.json"
    database.write_text("base\n", encoding="utf-8")
    _real_git(tmp_path, "init", "--bare", "--initial-branch=main", str(bare))
    _real_git(local, "init", "--initial-branch=main")
    _configure_real_repo(local)
    _real_git(local, "add", "baza_skryptow.json")
    _real_git(local, "commit", "-m", "base")
    _real_git(local, "remote", "add", "origin", str(bare))
    _real_git(local, "push", "-u", "origin", "main")
    _real_git(tmp_path, "clone", str(bare), str(peer))
    _configure_real_repo(peer)

    peer_database = peer / "baza_skryptow.json"
    peer_database.write_text("fast forward\n", encoding="utf-8")
    _real_git(peer, "commit", "-am", "remote fast-forward")
    _real_git(peer, "push", "origin", "main")

    integration = GitIntegration(local, auto_commit=False)
    assert integration.pull()
    assert database.read_text(encoding="utf-8") == "fast forward\n"

    database.write_text("local divergent commit\n", encoding="utf-8")
    _real_git(local, "commit", "-am", "local change")
    local_head = _real_git(local, "rev-parse", "HEAD").stdout.strip()
    peer_database.write_text("remote divergent commit\n", encoding="utf-8")
    _real_git(peer, "commit", "-am", "remote change")
    _real_git(peer, "push", "origin", "main")

    assert not integration.pull()
    assert integration.last_error
    assert _real_git(local, "rev-parse", "HEAD").stdout.strip() == local_head
    assert database.read_text(encoding="utf-8") == "local divergent commit\n"

class TestFindGit:
    """Testy wykrywania wykonywalnego git (find_git / fallback PATH)."""

    def setup_method(self):
        """Reset cache między testami (moduł cache'uje wynik)."""
        import src.git_integration as gi
        gi._git_exe_cache = None

    def teardown_method(self):
        import src.git_integration as gi
        gi._git_exe_cache = None

    def test_find_git_returns_path_on_this_machine(self, monkeypatch):
        import src.git_integration as gi
        monkeypatch.setattr(gi.shutil, "which", lambda name: None)
        monkeypatch.setattr(gi.os.path, "isfile",
                            lambda p: p.endswith("git.exe"))
        result = gi.find_git()
        assert result is not None
        assert result.endswith("git.exe")
        # drugie wywołanie korzysta z cache (ta sama wartość)
        assert gi.find_git() == result

    def test_find_git_none_when_nowhere(self, monkeypatch):
        import src.git_integration as gi
        monkeypatch.setattr(gi.shutil, "which", lambda name: None)
        monkeypatch.setattr(gi.os.path, "isfile", lambda p: False)
        assert gi.find_git() is None
        assert gi.find_git() is None  # cache również pusty

    def test_find_git_prefers_path(self, monkeypatch):
        import src.git_integration as gi
        monkeypatch.setattr(gi.shutil, "which", lambda name: "C:\\Portable\\git.exe")
        assert gi.find_git() == "C:\\Portable\\git.exe"


class TestGitCommandFailures:
    """Obsługa błędów _run_git_command: brak gita i timeout."""

    def test_run_command_without_git(self, git_integration, monkeypatch):
        import src.git_integration as gi
        git_integration._initialized = True
        monkeypatch.setattr(gi, "find_git", lambda: None)
        ok, msg = git_integration._run_git_command(["status"])
        assert ok is False
        assert "not installed" in msg

    def test_run_command_timeout(self, git_integration, monkeypatch):
        import src.git_integration as gi
        git_integration._initialized = True
        monkeypatch.setattr(gi, "find_git", lambda: "git")

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="git", timeout=30)

        monkeypatch.setattr(gi.subprocess, "run", raise_timeout)
        ok, msg = git_integration._run_git_command(["push"])
        assert ok is False
        assert "timed out" in msg

    def test_run_command_file_not_found(self, git_integration, monkeypatch):
        """Git zniknął między wykryciem a wywołaniem — czytelny komunikat."""
        import src.git_integration as gi
        git_integration._initialized = True
        monkeypatch.setattr(gi, "find_git", lambda: "git")

        def raise_not_found(*args, **kwargs):
            raise FileNotFoundError("git.exe")

        monkeypatch.setattr(gi.subprocess, "run", raise_not_found)
        ok, msg = git_integration._run_git_command(["status"])
        assert ok is False
        assert "not installed" in msg

    def test_check_git_repo_without_git(self, git_integration, monkeypatch):
        import src.git_integration as gi
        monkeypatch.setattr(gi, "find_git", lambda: None)
        assert git_integration._check_git_repo() is False

class TestMoreGitMethods:
    """Uzupełniające testy: branche, diff, log, remote — błędy i warianty."""

    def test_get_branches_failure_returns_empty(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (False, "boom"))
        assert git_integration.get_branches() == []

    def test_get_history_with_file_and_unparsed_lines(self, git_integration, monkeypatch, temp_repo_path):
        git_integration._initialized = True
        out = "abc|me|2026-01-01 10:00:00 +0100|msg ok\n\nshort-line"
        captured = {}

        def run(command):
            captured["cmd"] = command
            return True, out

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        commits = git_integration.get_history(
            temp_repo_path / "b.json", limit=5)
        assert captured["cmd"][1] == "-5"
        assert captured["cmd"][-1].endswith("b.json")
        assert commits == [{"hash": "abc", "author": "me",
                            "date": "2026-01-01 10:00:00 +0100",
                            "message": "msg ok"}]

    def test_get_history_failure_returns_empty(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (False, "err"))
        assert git_integration.get_history(None) == []

    def test_get_diff_variants(self, git_integration, monkeypatch, temp_repo_path):
        git_integration._initialized = True
        captured = {}

        def run(command):
            captured["cmd"] = list(command)
            return True, "diff-text"

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        # dwa hashe + plik
        out = git_integration.get_diff("aaa", "bbb", temp_repo_path / "x.py")
        assert out == "diff-text"
        assert captured["cmd"] == ["diff", "aaa", "bbb", "--", "x.py"]
        # jeden hash, bez pliku
        git_integration.get_diff("aaa")
        assert captured["cmd"] == ["diff", "aaa"]
        # nieinicjalizowane
        git_integration._initialized = False
        assert git_integration.get_diff("aaa") == ""

    def test_get_diff_failure_returns_empty(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (False, ""))
        assert git_integration.get_diff("aaa") == ""

    def test_get_commit_diff_invalid_hash(self, git_integration):
        git_integration._initialized = True
        assert git_integration.get_commit_diff("not-a-hash!") == ""

    def test_get_file_at_commit_failure(self, git_integration, monkeypatch, temp_repo_path):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (False, ""))
        assert git_integration.get_file_at_commit(
            temp_repo_path / "a.py", "abc123") is None

    def test_restore_file(self, git_integration, monkeypatch, temp_repo_path):
        git_integration._initialized = True
        captured = {}
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: captured.update(cmd=cmd) or (True, ""))
        assert git_integration.restore_file(temp_repo_path / "a.py", "abc")
        assert captured["cmd"] == ["checkout", "abc", "--", "a.py"]
        git_integration._initialized = False
        assert git_integration.restore_file(temp_repo_path / "a.py", "abc") is False

    def test_set_remote_invalid_inputs(self, git_integration):
        git_integration._initialized = True
        assert not git_integration.set_remote("bad name!", "https://x")
        assert not git_integration.set_remote("origin", "-dash-start")
        assert not git_integration.set_remote("origin", "line\nbreak")
        assert not git_integration.set_remote("origin", "")
        git_integration._initialized = False
        assert not git_integration.set_remote("origin", "https://x")

    def test_add_remote_not_initialized(self, git_integration):
        assert git_integration.add_remote("origin", "https://x") is False

class TestSyncAndRemote:
    """Gałęzie sync_file / push / pull / status — ścieżki błędów."""

    def test_sync_file_branch_unavailable(self, git_integration, monkeypatch):
        git_integration._initialized = True
        f = git_integration.repo_path / "b.json"
        f.touch()
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: None)
        assert not git_integration.sync_file(f)
        assert "branch" in git_integration.last_error

    def test_sync_file_staging_fails(self, git_integration, monkeypatch):
        git_integration._initialized = True
        f = git_integration.repo_path / "b.json"
        f.touch()
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        monkeypatch.setattr(git_integration, "add_file", lambda p: False)
        assert not git_integration.sync_file(f)
        assert "stage" in git_integration.last_error

    def test_sync_file_no_staged_change(self, git_integration, monkeypatch):
        git_integration._initialized = True
        f = git_integration.repo_path / "b.json"
        f.touch()
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        monkeypatch.setattr(git_integration, "add_file", lambda p: True)

        def run(cmd):
            if cmd[0] == "diff":
                return False, "diff-err"
            return True, ""

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        assert not git_integration.sync_file(f)
        assert git_integration.last_error == "diff-err"

    def test_sync_file_commit_fails_but_push_skipped(self, git_integration, monkeypatch):
        git_integration._initialized = True
        f = git_integration.repo_path / "b.json"
        f.touch()
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")
        monkeypatch.setattr(git_integration, "add_file", lambda p: True)
        calls = []

        def run(cmd):
            calls.append(cmd[0])
            if cmd[0] == "commit":
                return False, "commit-err"
            return True, "x" if cmd[0] == "diff" else ""

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        assert not git_integration.sync_file(f)
        assert "push" not in calls

    def test_push_pull_branch_unavailable_and_not_initialized(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: None)
        assert git_integration.push() is False
        assert git_integration.pull() is False
        git_integration._initialized = False
        assert git_integration.push("origin", "main") is False
        assert git_integration.pull("origin", "main") is False

    def test_pull_sets_last_error(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "main")

        def run(cmd):
            return (False, "conflict") if cmd[0] == "pull" else (True, "")

        monkeypatch.setattr(git_integration, "_run_git_command", run)
        assert git_integration.pull() is False
        assert git_integration.last_error == "conflict"

    def test_status_failure_returns_branch_only(self, git_integration, monkeypatch):
        git_integration._initialized = True
        monkeypatch.setattr(git_integration, "get_current_branch", lambda: "dev")
        monkeypatch.setattr(git_integration, "_run_git_command",
                            lambda cmd: (False, "boom") if cmd[0] == "status" else (True, ""))
        st = git_integration.status()
        assert st["branch"] == "dev"
        assert st["modified"] == []

    def test_status_not_initialized(self, git_integration):
        assert git_integration.status() == {}
