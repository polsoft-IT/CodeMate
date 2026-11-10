import sys
import subprocess
import threading
import time
import hashlib
import hmac
import json
from pathlib import Path
from io import BytesIO

from fastapi import HTTPException
from pydantic import ValidationError
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from src import api

TOKEN = "test-token-with-more-than-thirty-two-characters"


def _database(path: Path) -> None:
    bs.db_write(path, [
        {"id": "trusted", "nazwa": "Trusted", "kategoria": "Python",
         "kod": "print('ok')", "zaufany": True},
        {"id": "untrusted", "nazwa": "Untrusted", "kategoria": "Python",
         "kod": "print('no')", "zaufany": False},
        {"id": "deleted", "nazwa": "Deleted", "kategoria": "Python",
         "kod": "", "zaufany": True, "usuniety": "2026-01-01"},
    ], backup_count=0)


def _handler(app, path, method="GET"):
    route = next(route for route in app.routes if getattr(route, "path", None) == path
                 and method in getattr(route, "methods", set()))
    return route.endpoint


def _auth(app, authorization=None):
    route = next(route for route in app.routes if getattr(route, "path", None) == "/health")
    route.dependant.dependencies[0].call(authorization)


def _wait_for_job(app, run_id):
    get_run = _handler(app, "/runs/{run_id}")
    for _ in range(200):
        result = get_run(run_id)
        if result["status"] not in ("running", "cancelling"):
            return result
        time.sleep(0.01)
    raise AssertionError("API job did not finish in time")


class TestApiSecurity:
    def test_requires_strong_token_at_startup(self, tmp_path):
        try:
            api.create_app(tmp_path / "db.json", "weak")
        except ValueError as exc:
            assert "32 characters" in str(exc)
        else:
            raise AssertionError("weak token was accepted")

    def test_rejects_non_https_webhook(self, tmp_path):
        try:
            api.create_app(tmp_path / "db.json", TOKEN, webhook_url="http://example.test/hook")
        except ValueError as exc:
            assert "HTTPS" in str(exc)
        else:
            raise AssertionError("insecure webhook was accepted")

    def test_webhook_uses_hmac_signature(self, monkeypatch):
        captured = {}

        class Response(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()

        def fake_open(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response(b"ok")

        monkeypatch.setattr(api, "urlopen", fake_open)
        payload = {"id": "run-1", "status": "succeeded"}
        api._send_webhook("https://example.test/hook", TOKEN, payload)
        request = captured["request"]
        signature = hmac.new(TOKEN.encode(), request.data, hashlib.sha256).hexdigest()
        assert request.get_header("X-codemate-signature") == f"sha256={signature}"
        assert json.loads(request.data) == payload
        assert captured["timeout"] == 5

    def test_authentication_required(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        app = api.create_app(database, TOKEN)
        authenticate = next(route for route in app.routes if route.path == "/health").dependant.dependencies[0].call
        for authorization in (None, "Bearer wrong"):
            try:
                authenticate(authorization)
            except HTTPException as exc:
                assert exc.status_code == 401
            else:
                raise AssertionError("unauthenticated request was accepted")
        authenticate(f"Bearer {TOKEN}")

    def test_webhook_payload_is_signed_without_output(self, tmp_path, monkeypatch):
        _database(tmp_path / "db.json")
        sent = threading.Event()
        received = {}

        def fake_send(url, token, payload):
            received.update(url=url, token=token, payload=payload)
            sent.set()

        monkeypatch.setattr(api, "_send_webhook", fake_send)
        app = api.create_app(
            tmp_path / "db.json", TOKEN, webhook_url="https://example.test/hook",
            executor=lambda *_: {"returncode": 0, "stdout": "private output", "stderr": ""},
        )
        _auth(app, f"Bearer {TOKEN}")
        started = _handler(app, "/runs", "POST")(api.RunRequest(script_id="trusted"))
        assert sent.wait(2)
        assert started["status"] == "running"
        assert received["payload"]["status"] == "succeeded"
        assert "stdout" not in received["payload"]


class TestApiRuns:
    def test_lists_only_trusted_live_scripts(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        app = api.create_app(database, TOKEN)
        _auth(app, f"Bearer {TOKEN}")
        assert [script["id"] for script in _handler(app, "/scripts")()] == ["trusted"]

    def test_rejects_untrusted_and_missing_scripts(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        app = api.create_app(database, TOKEN)
        start_run = _handler(app, "/runs", "POST")
        for script_id, expected in (("untrusted", 403), ("missing", 404)):
            try:
                start_run(api.RunRequest(script_id=script_id))
            except HTTPException as exc:
                assert exc.status_code == expected
            else:
                raise AssertionError(f"script {script_id!r} was unexpectedly accepted")

    def test_returns_run_status_and_output(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        called = threading.Event()
        received = {}

        def execute(script, args, timeout):
            received.update(script=script, args=args, timeout=timeout)
            called.set()
            return {"returncode": 0, "stdout": "done", "stderr": ""}

        app = api.create_app(database, executor=execute, token=TOKEN)
        started = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted", args=["a b"]))
        assert called.wait(2)
        run = _wait_for_job(app, started["id"])
        assert run["status"] == "succeeded"
        assert run["stdout"] == "done"
        assert received["args"] == ["a b"]
        assert received["timeout"] == 60

    def test_limits_timeout_and_argument_count(self, tmp_path):
        _database(tmp_path / "db.json")
        with pytest.raises(ValidationError):
            api.RunRequest(script_id="trusted", timeout=3601)
        with pytest.raises(ValidationError):
            api.RunRequest(script_id="trusted", args=["x"] * 33)

    def test_unknown_run_returns_404(self, tmp_path):
        app = api.create_app(tmp_path / "db.json", TOKEN)
        try:
            _handler(app, "/runs/{run_id}")("unknown")
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("unknown run was unexpectedly found")

    def test_completed_job_history_is_bounded(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setattr(api, "MAX_STORED_JOBS", 2)
        app = api.create_app(
            database, TOKEN,
            executor=lambda *_: {"returncode": 0, "stdout": "done", "stderr": ""},
        )
        start_run = _handler(app, "/runs", "POST")
        get_run = _handler(app, "/runs/{run_id}")
        run_ids = []
        for _ in range(3):
            started = start_run(api.RunRequest(script_id="trusted"))
            run_ids.append(started["id"])
            assert _wait_for_job(app, started["id"])["status"] == "succeeded"

        with pytest.raises(HTTPException) as exc_info:
            get_run(run_ids[0])
        assert exc_info.value.status_code == 404
        assert get_run(run_ids[1])["status"] == "succeeded"
        assert get_run(run_ids[2])["status"] == "succeeded"

    def test_retention_never_evicts_running_jobs(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setattr(api, "MAX_STORED_JOBS", 2)
        started_event = threading.Event()
        release_event = threading.Event()
        calls = 0

        def execute(*_):
            nonlocal calls
            calls += 1
            if calls == 1:
                started_event.set()
                assert release_event.wait(2)
            return {"returncode": 0, "stdout": "done", "stderr": ""}

        app = api.create_app(database, TOKEN, executor=execute)
        start_run = _handler(app, "/runs", "POST")
        get_run = _handler(app, "/runs/{run_id}")
        running_id = start_run(api.RunRequest(script_id="trusted"))["id"]
        assert started_event.wait(2)
        completed_id = start_run(api.RunRequest(script_id="trusted"))["id"]
        assert _wait_for_job(app, completed_id)["status"] == "succeeded"
        newest_id = start_run(api.RunRequest(script_id="trusted"))["id"]
        assert get_run(running_id)["status"] == "running"
        assert _wait_for_job(app, newest_id)["status"] == "succeeded"
        release_event.set()
        assert _wait_for_job(app, running_id)["status"] == "succeeded"

    def test_cancel_endpoint_marks_job_cancelled(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        started_event = threading.Event()
        release_event = threading.Event()

        def execute(*_):
            started_event.set()
            assert release_event.wait(2)
            return {"returncode": 0, "stdout": "done", "stderr": ""}

        app = api.create_app(database, TOKEN, executor=execute)
        start_run = _handler(app, "/runs", "POST")
        cancel_run = _handler(app, "/runs/{run_id}", "DELETE")
        run_id = start_run(api.RunRequest(script_id="trusted"))["id"]
        assert started_event.wait(2)
        assert cancel_run(run_id) == {"id": run_id, "status": "cancelling"}
        assert cancel_run(run_id) == {"id": run_id, "status": "cancelling"}
        release_event.set()
        assert _wait_for_job(app, run_id)["status"] == "cancelled"

    def test_cancel_endpoint_rejects_finished_job(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        app = api.create_app(
            database, TOKEN,
            executor=lambda *_: {"returncode": 0, "stdout": "done", "stderr": ""},
        )
        start_run = _handler(app, "/runs", "POST")
        cancel_run = _handler(app, "/runs/{run_id}", "DELETE")
        run_id = start_run(api.RunRequest(script_id="trusted"))["id"]
        assert _wait_for_job(app, run_id)["status"] == "succeeded"
        with pytest.raises(HTTPException) as exc_info:
            cancel_run(run_id)
        assert exc_info.value.status_code == 409

    def test_cancels_real_python_process(self, tmp_path):
        marker = tmp_path / "started.txt"
        script = {
            "kategoria": "Python",
            "kod": ("from pathlib import Path\nimport sys, time\n"
                    "Path(sys.argv[1]).write_text('started')\n"
                    "print('ready', flush=True)\n"
                    "time.sleep(30)\n"),
        }
        cancel_event = threading.Event()
        result = {}
        worker = threading.Thread(
            target=lambda: result.update(
                api._execute_script(script, [str(marker)], 10, cancel_event)),
            daemon=True,
        )
        worker.start()
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), "child process did not start"
        cancel_event.set()
        worker.join(timeout=5)
        assert not worker.is_alive(), "cancelled child process did not exit"
        assert result["cancelled"] is True
        assert result["returncode"] == -2
        assert "ready" in result["stdout"]


class _FakeProc:
    """Minimalny zamiennik subprocess.Popen dla testów _execute_script."""

    def __init__(self, communicate_results=(), returncode=0, timeout_forever=False):
        self._results = list(communicate_results)
        self.returncode = returncode
        self.pid = 424242
        self.killed = False
        self.timeout_forever = timeout_forever

    def poll(self):
        return self.returncode

    def communicate(self, timeout=None):
        if self.killed:
            return ("po-kill-out", "po-kill-err")
        if self.timeout_forever:
            raise subprocess.TimeoutExpired("cmd", timeout)
        effect = self._results.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    def kill(self):
        self.killed = True


class TestApiHelpers:
    """Pomocnicze funkcje api: walidacja, odczyt bazy, webhook."""

    def test_read_scripts_missing_db_returns_empty(self, tmp_path):
        assert api._read_scripts(tmp_path / "nie_ma.json") == []

    def test_run_request_rejects_too_long_argument(self):
        with pytest.raises(ValidationError):
            api.RunRequest(script_id="x", args=["a" * (api.MAX_ARG_CHARS + 1)])

    def test_webhook_url_none_is_ok(self):
        api._validate_webhook_url(None)
        api._validate_webhook_url("")

    def test_webhook_url_without_hostname_rejected(self):
        with pytest.raises(ValueError):
            api._validate_webhook_url("https://")

    def test_webhook_url_with_credentials_rejected(self):
        with pytest.raises(ValueError):
            api._validate_webhook_url("https://user:pass@example.test/hook")

    def test_webhook_url_http_rejected(self):
        with pytest.raises(ValueError):
            api._validate_webhook_url("http://example.test/hook")


class TestExecuteScript:
    """_execute_script: timeout, anulowanie, błędy runnera."""

    def _patch_runner(self, monkeypatch, proc, command=("fake", "cmd")):
        import subprocess as sp
        import baza_skryptow as bs

        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return proc

        monkeypatch.setattr(sp, "Popen", fake_popen)
        monkeypatch.setattr(bs, "runner_save_temp", lambda *a, **k: "fake_path")
        monkeypatch.setattr(bs, "runner_cmd", lambda *a, **k: list(command))
        monkeypatch.setattr(bs, "cfg_load", lambda: {})
        monkeypatch.setattr(bs, "runner_kill_tree", lambda p: None)
        return captured

    def test_successful_run_returns_output(self, monkeypatch):
        proc = _FakeProc([("stdout-data", "stderr-data")], returncode=0)
        self._patch_runner(monkeypatch, proc)
        script = {"kategoria": "Python", "kod": "print(1)"}
        result = api._execute_script(script, ["a"], 5)
        assert result == {"returncode": 0, "stdout": "stdout-data",
                          "stderr": "stderr-data"}

    def test_unknown_category_raises(self, monkeypatch):
        import baza_skryptow as bs
        monkeypatch.setattr(bs, "cfg_load", lambda: {})
        monkeypatch.setattr(bs, "runner_save_temp", lambda *a, **k: "p")
        monkeypatch.setattr(bs, "runner_cmd", lambda *a, **k: None)
        with pytest.raises(ValueError, match="No runner"):
            api._execute_script({"kategoria": "Nieznany", "kod": ""}, [], 5)

    def test_missing_interpreter_path_is_cleared(self, monkeypatch):
        """Nieistniejący interpreter z konfiguracji jest ignorowany."""
        import baza_skryptow as bs
        seen = {}

        def fake_cmd(kategoria, path, args, interpreter):
            seen["interpreter"] = interpreter
            return None  # → ValueError, ale interpreter już sprawdzony

        monkeypatch.setattr(bs, "cfg_load",
                            lambda: {"interpreter": "Z:\\nie_ma\\python.exe"})
        monkeypatch.setattr(bs, "runner_save_temp", lambda *a, **k: "p")
        monkeypatch.setattr(bs, "runner_cmd", fake_cmd)
        with pytest.raises(ValueError):
            api._execute_script({"kategoria": "Python", "kod": ""}, [], 5)
        assert seen["interpreter"] == ""

    def test_non_windows_gets_new_session(self, monkeypatch):
        """Na nie-Windows do Popen dodawany jest start_new_session."""
        proc = _FakeProc([("ok", "")], returncode=0)
        captured = self._patch_runner(monkeypatch, proc)
        monkeypatch.setattr(api.os, "name", "posix")
        api._execute_script({"kategoria": "Python", "kod": ""}, [], 5)
        assert captured["kwargs"].get("start_new_session") is True

    def test_timeout_kills_process(self, monkeypatch):
        """Przekroczenie timeout zabija proces i zwraca -1."""
        proc = _FakeProc(returncode=-1, timeout_forever=True)
        self._patch_runner(monkeypatch, proc)
        result = api._execute_script({"kategoria": "Python", "kod": ""}, [], 1)
        assert result["returncode"] == -1
        assert "Timed out after 1 seconds" in result["stderr"]
        assert "cancelled" not in result

    def test_cancel_event_marks_cancelled(self, monkeypatch):
        """Ustawiony cancel_event kończy uruchomienie jako cancelled."""
        proc = _FakeProc(timeout_forever=True)
        self._patch_runner(monkeypatch, proc)
        cancel_event = threading.Event()
        cancel_event.set()
        result = api._execute_script(
            {"kategoria": "Python", "kod": ""}, [], 30, cancel_event)
        assert result["returncode"] == -2
        assert result["cancelled"] is True
        assert "cancelled by request" in result["stderr"].lower()

    def test_slow_communicate_kill_fallback(self, monkeypatch):
        """Gdy communicate(timeout=2) też timeoutuje, proces jest zabijany."""
        # kill_tree jest no-op → drugie timeoutowanie komunikacji → proc.kill()
        proc = _FakeProc(returncode=-1, timeout_forever=True)
        self._patch_runner(monkeypatch, proc)
        result = api._execute_script({"kategoria": "Python", "kod": ""}, [], 1)
        assert proc.killed is True
        assert result["returncode"] == -1
        assert "Timed out" in result["stderr"]


class TestFinishJob:
    """Ścieżki finish_job: zaufanie, wyjątki, webhook."""

    def _sequential_read_scripts(self, monkeypatch, second_result):
        """Pierwsze wywołanie _read_scripts zwraca prawdziwą bazę, kolejne — podaną."""
        real_read = api._read_scripts
        calls = {"n": 0}

        def fake_read(path):
            calls["n"] += 1
            if calls["n"] == 1:
                return real_read(path)
            return second_result

        monkeypatch.setattr(api, "_read_scripts", fake_read)

    def test_script_untrusted_at_finish_fails(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        untrusted = [{"id": "trusted", "nazwa": "T", "kategoria": "Python",
                      "kod": "x", "zaufany": False}]
        self._sequential_read_scripts(monkeypatch, untrusted)
        app = api.create_app(
            database, TOKEN,
            executor=lambda *_: {"returncode": 0, "stdout": "", "stderr": ""},
        )
        run_id = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted"))["id"]
        run = _wait_for_job(app, run_id)
        assert run["status"] == "failed"
        assert "trusted" in run["stderr"].lower()

    def test_script_deleted_at_finish_fails(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        self._sequential_read_scripts(monkeypatch, [])
        app = api.create_app(
            database, TOKEN,
            executor=lambda *_: {"returncode": 0, "stdout": "", "stderr": ""},
        )
        run_id = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted"))["id"]
        run = _wait_for_job(app, run_id)
        assert run["status"] == "failed"

    def test_executor_without_custom_runs_real_path(self, tmp_path, monkeypatch):
        """Bez executor finish_job woła _execute_script."""
        database = tmp_path / "db.json"
        _database(database)
        calls = []

        def fake_execute(script, args, timeout, cancel_event=None):
            calls.append((script["id"], args, timeout))
            return {"returncode": 0, "stdout": "real", "stderr": ""}

        monkeypatch.setattr(api, "_execute_script", fake_execute)
        app = api.create_app(database, TOKEN)
        _auth(app, f"Bearer {TOKEN}")
        run_id = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted", args=["x"]))["id"]
        run = _wait_for_job(app, run_id)
        assert run["status"] == "succeeded"
        assert run["stdout"] == "real"
        assert calls == [("trusted", ["x"], 60)]

    def test_executor_exception_marks_failed(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)

        def boom(*_):
            raise RuntimeError("executor exploded")

        app = api.create_app(database, TOKEN, executor=boom)
        run_id = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted"))["id"]
        run = _wait_for_job(app, run_id)
        assert run["status"] == "failed"
        assert "executor exploded" in run["stderr"]

    def test_failed_run_returncode(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        app = api.create_app(
            database, TOKEN,
            executor=lambda *_: {"returncode": 3, "stdout": "", "stderr": "bad"},
        )
        run_id = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted"))["id"]
        run = _wait_for_job(app, run_id)
        assert run["status"] == "failed"
        assert run["returncode"] == 3

    def test_webhook_failure_is_logged_not_raised(self, tmp_path, monkeypatch, caplog):
        import logging

        database = tmp_path / "db.json"
        _database(database)

        def boom_webhook(*_):
            raise RuntimeError("webhook down")

        monkeypatch.setattr(api, "_send_webhook", boom_webhook)
        app = api.create_app(
            database, TOKEN, webhook_url="https://example.test/hook",
            executor=lambda *_: {"returncode": 0, "stdout": "", "stderr": ""},
        )
        run_id = _handler(app, "/runs", "POST")(
            api.RunRequest(script_id="trusted"))["id"]
        run = _wait_for_job(app, run_id)
        assert run["status"] == "succeeded"


class TestApiEndpoints:
    """Endpointy: health, błędy bazy, limity, cancel."""

    def test_health_endpoint(self, tmp_path):
        app = api.create_app(tmp_path / "db.json", TOKEN)
        assert _handler(app, "/health")() == {"status": "ok"}

    def test_list_scripts_db_error_503(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setattr(api, "_read_scripts",
                            lambda p: (_ for _ in ()).throw(RuntimeError("db gone")))
        app = api.create_app(database, TOKEN)
        with pytest.raises(HTTPException) as exc_info:
            _handler(app, "/scripts")()
        assert exc_info.value.status_code == 503

    def test_start_run_db_error_503(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setattr(api, "_read_scripts",
                            lambda p: (_ for _ in ()).throw(RuntimeError("db gone")))
        app = api.create_app(database, TOKEN)
        with pytest.raises(HTTPException) as exc_info:
            _handler(app, "/runs", "POST")(api.RunRequest(script_id="trusted"))
        assert exc_info.value.status_code == 503

    def test_active_runs_limit_429(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setattr(api, "MAX_ACTIVE_RUNS", 0)
        app = api.create_app(database, TOKEN)
        with pytest.raises(HTTPException) as exc_info:
            _handler(app, "/runs", "POST")(api.RunRequest(script_id="trusted"))
        assert exc_info.value.status_code == 429

    def test_run_history_full_429(self, tmp_path, monkeypatch):
        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setattr(api, "MAX_STORED_JOBS", 0)
        app = api.create_app(database, TOKEN)
        with pytest.raises(HTTPException) as exc_info:
            _handler(app, "/runs", "POST")(api.RunRequest(script_id="trusted"))
        assert exc_info.value.status_code == 429
        assert "history" in exc_info.value.detail.lower()

    def test_cancel_unknown_run_404(self, tmp_path):
        app = api.create_app(tmp_path / "db.json", TOKEN)
        with pytest.raises(HTTPException) as exc_info:
            _handler(app, "/runs/{run_id}", "DELETE")("missing")
        assert exc_info.value.status_code == 404

    def test_cancel_already_cancelling(self, tmp_path):
        database = tmp_path / "db.json"
        _database(database)
        release = threading.Event()
        app = api.create_app(
            database, TOKEN,
            executor=lambda *_: (release.wait(5), {"returncode": 0, "stdout": "", "stderr": ""})[1],
        )
        start_run = _handler(app, "/runs", "POST")
        cancel_run = _handler(app, "/runs/{run_id}", "DELETE")
        run_id = start_run(api.RunRequest(script_id="trusted"))["id"]
        time.sleep(0.05)
        assert cancel_run(run_id) == {"id": run_id, "status": "cancelling"}
        # drugi cancel na job w stanie "cancelling" zwraca ten sam status
        assert cancel_run(run_id) == {"id": run_id, "status": "cancelling"}
        release.set()
        assert _wait_for_job(app, run_id)["status"] == "cancelled"


class TestApiMain:
    """Funkcja main() (CLI)."""

    def test_main_requires_token(self, monkeypatch):
        monkeypatch.delenv("CODEMATE_API_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            api.main(["--db", "x.json"])

    def test_main_runs_uvicorn(self, tmp_path, monkeypatch):
        import uvicorn

        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setenv("CODEMATE_API_TOKEN", TOKEN)
        monkeypatch.setenv("CODEMATE_API_WEBHOOK_URL", "https://example.test/hook")
        captured = {}
        monkeypatch.setattr(uvicorn, "run",
                            lambda app, **kw: captured.update(app=app, **kw))
        result = api.main(["--db", str(database), "--host", "0.0.0.0", "--port", "9999"])
        assert result == 0
        assert captured["host"] == "0.0.0.0"
        assert captured["port"] == 9999

    def test_main_db_from_config(self, tmp_path, monkeypatch):
        import uvicorn
        import baza_skryptow as bs

        database = tmp_path / "db.json"
        _database(database)
        monkeypatch.setenv("CODEMATE_API_TOKEN", TOKEN)
        monkeypatch.delenv("CODEMATE_API_WEBHOOK_URL", raising=False)
        monkeypatch.setattr(bs, "cfg_load", lambda: {"db_path": str(database)})
        monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
        result = api.main([])
        assert result == 0

    def test_main_uvicorn_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEMATE_API_TOKEN", TOKEN)
        monkeypatch.setitem(sys.modules, "uvicorn", None)
        with pytest.raises(SystemExit):
            api.main(["--db", str(tmp_path / "db.json")])