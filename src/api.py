"""Token-protected REST API for running trusted scripts from a database."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

MAX_OUTPUT_CHARS = 64_000
MAX_ACTIVE_RUNS = 4
MAX_STORED_JOBS = 256
MAX_ARGS = 32
MAX_ARG_CHARS = 4096


class RunRequest(BaseModel):
    script_id: str = Field(min_length=1, max_length=128)
    args: List[str] = Field(default_factory=list, max_length=MAX_ARGS)
    timeout: int = Field(default=60, ge=1, le=3600)

    @field_validator("args")
    @classmethod
    def validate_args(cls, args: List[str]) -> List[str]:
        if any(len(arg) > MAX_ARG_CHARS for arg in args):
            raise ValueError(f"Each argument must be at most {MAX_ARG_CHARS} characters")
        return args


def _read_scripts(db_path: Path) -> List[Dict[str, Any]]:
    from baza_skryptow import db_read

    if not db_path.exists():
        return []
    scripts, _ = db_read(db_path)
    return scripts


def _execute_script(
    script: Dict[str, Any], args: List[str], timeout: int,
    cancel_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    from baza_skryptow import cfg_load, runner_cmd, runner_kill_tree, runner_save_temp

    category = str(script.get("kategoria") or "Other")
    settings = cfg_load()
    interpreter = settings.get("interpreter") or ""
    if category == "Python" and interpreter and not os.path.exists(interpreter):
        interpreter = ""

    with tempfile.TemporaryDirectory(prefix="bs_api_") as workdir:
        path = runner_save_temp(str(script.get("kod") or ""), category, workdir, interpreter)
        command = runner_cmd(category, path, args, interpreter)
        if not command:
            raise ValueError(f"No runner is configured for category {category!r}")
        options: Dict[str, Any] = {}
        if os.name != "nt":
            options["start_new_session"] = True
        proc = subprocess.Popen(
            command,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            **options,
        )
        deadline = time.monotonic() + timeout
        while True:
            if cancel_event is not None and cancel_event.is_set():
                runner_kill_tree(proc)
                cancelled = True
                suffix = "Run cancelled by request"
            elif time.monotonic() >= deadline:
                runner_kill_tree(proc)
                cancelled = False
                suffix = f"Timed out after {timeout} seconds"
            else:
                try:
                    stdout, stderr = proc.communicate(
                        timeout=min(0.1, max(0.01, deadline - time.monotonic())))
                    return {
                        "returncode": proc.returncode,
                        "stdout": stdout[-MAX_OUTPUT_CHARS:],
                        "stderr": stderr[-MAX_OUTPUT_CHARS:],
                    }
                except subprocess.TimeoutExpired:
                    continue

            try:
                stdout, stderr = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            result = {
                "returncode": -2 if cancelled else -1,
                "stdout": (stdout or "")[-MAX_OUTPUT_CHARS:],
                "stderr": ((stderr or "") + f"\n{suffix}")[-MAX_OUTPUT_CHARS:],
            }
            if cancelled:
                result["cancelled"] = True
            return result


def _validate_webhook_url(webhook_url: Optional[str]) -> None:
    if not webhook_url:
        return
    parsed = urlsplit(webhook_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Webhook URL must be an HTTPS URL without embedded credentials")


def _send_webhook(url: str, token: str, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(token.encode("utf-8"), body, hashlib.sha256).hexdigest()
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-CodeMate-Signature": f"sha256={signature}",
        },
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        response.read(1024)


def create_app(
    db_path: Path | str,
    token: str,
    webhook_url: Optional[str] = None,
    executor: Optional[Callable[[Dict[str, Any], List[str], int], Dict[str, Any]]] = None,
) -> FastAPI:
    """Create an API app; the token must be a high-entropy secret of 32+ chars."""
    token = str(token or "")
    if len(token) < 32:
        raise ValueError("API token must contain at least 32 characters")
    _validate_webhook_url(webhook_url)
    database = Path(db_path).expanduser().resolve()
    run_script = executor or _execute_script

    app = FastAPI(title="CodeMate API", version="1.0.0",
                  docs_url=None, redoc_url=None, openapi_url=None)
    jobs: Dict[str, Dict[str, Any]] = {}
    cancel_events: Dict[str, threading.Event] = {}
    lock = threading.Lock()
    active_runs = 0

    def authenticate(authorization: Optional[str] = Header(default=None)) -> None:
        expected = f"Bearer {token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def finish_job(run_id: str, script: Dict[str, Any], request: RunRequest) -> None:
        nonlocal active_runs
        cancel_event = cancel_events[run_id]
        try:
            current = next(
                (item for item in _read_scripts(database)
                 if item.get("id") == script.get("id") and not item.get("usuniety")),
                None,
            )
            if current is None or not current.get("zaufany"):
                raise ValueError("Script is missing or is no longer trusted")
            if executor is None:
                result = _execute_script(
                    current, request.args, request.timeout, cancel_event)
            else:
                result = run_script(current, request.args, request.timeout)
            returncode = int(result.get("returncode", 1))
            finished = {
                "id": run_id,
                "script_id": current["id"],
                "status": ("cancelled" if result.get("cancelled") else
                           "succeeded" if returncode == 0 else "failed"),
                "returncode": returncode,
                "stdout": str(result.get("stdout") or "")[-MAX_OUTPUT_CHARS:],
                "stderr": str(result.get("stderr") or "")[-MAX_OUTPUT_CHARS:],
            }
        except Exception as exc:
            logging.exception("API run %s failed", run_id)
            finished = {
                "id": run_id,
                "script_id": script.get("id"),
                "status": "cancelled" if cancel_event.is_set() else "failed",
                "returncode": -2 if cancel_event.is_set() else None,
                "stdout": "",
                "stderr": str(exc)[:MAX_OUTPUT_CHARS],
            }
        with lock:
            if cancel_event.is_set():
                finished["status"] = "cancelled"
                finished["returncode"] = -2
            jobs[run_id].update(finished)
            active_runs -= 1
            cancel_events.pop(run_id, None)
        if webhook_url:
            try:
                _send_webhook(webhook_url, token, {
                    "id": run_id,
                    "script_id": finished["script_id"],
                    "status": finished["status"],
                    "returncode": finished["returncode"],
                })
            except Exception:
                logging.exception("Webhook delivery failed for API run %s", run_id)

    @app.get("/health", dependencies=[Depends(authenticate)])
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/scripts", dependencies=[Depends(authenticate)])
    def list_scripts() -> List[Dict[str, Any]]:
        try:
            scripts = _read_scripts(database)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database could not be read") from exc
        return [
            {"id": script["id"], "name": script["nazwa"], "category": script["kategoria"]}
            for script in scripts
            if script.get("zaufany") and not script.get("usuniety")
        ]

    @app.post("/runs", status_code=status.HTTP_202_ACCEPTED,
              dependencies=[Depends(authenticate)])
    def start_run(request: RunRequest) -> Dict[str, str]:
        nonlocal active_runs
        try:
            scripts = _read_scripts(database)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database could not be read") from exc
        script = next(
            (item for item in scripts if item.get("id") == request.script_id
             and not item.get("usuniety")),
            None,
        )
        if script is None:
            raise HTTPException(status_code=404, detail="Script not found")
        if not script.get("zaufany"):
            raise HTTPException(status_code=403, detail="Script is not trusted")
        with lock:
            if active_runs >= MAX_ACTIVE_RUNS:
                raise HTTPException(status_code=429, detail="Too many active runs")
            while len(jobs) >= MAX_STORED_JOBS:
                oldest_finished = next(
                    (job_id for job_id, job in jobs.items()
                     if job.get("status") not in ("running", "cancelling")),
                    None,
                )
                if oldest_finished is None:
                    raise HTTPException(status_code=429, detail="Run history is full")
                del jobs[oldest_finished]
            active_runs += 1
            run_id = uuid.uuid4().hex
            jobs[run_id] = {
                "id": run_id,
                "script_id": script["id"],
                "status": "running",
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
            cancel_events[run_id] = threading.Event()
        thread = threading.Thread(
            target=finish_job, args=(run_id, script, request), daemon=True,
            name=f"api-run-{run_id[:8]}",
        )
        thread.start()
        return {"id": run_id, "status": "running"}

    @app.get("/runs/{run_id}", dependencies=[Depends(authenticate)])
    def get_run(run_id: str) -> Dict[str, Any]:
        with lock:
            job = jobs.get(run_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Run not found")
            return dict(job)

    @app.delete("/runs/{run_id}", status_code=status.HTTP_202_ACCEPTED,
                dependencies=[Depends(authenticate)])
    def cancel_run(run_id: str) -> Dict[str, str]:
        with lock:
            job = jobs.get(run_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Run not found")
            if job["status"] == "cancelling":
                return {"id": run_id, "status": "cancelling"}
            if job["status"] != "running":
                raise HTTPException(status_code=409, detail="Run is already finished")
            cancel_events[run_id].set()
            job["status"] = "cancelling"
            return {"id": run_id, "status": "cancelling"}

    return app


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CodeMate REST API")
    parser.add_argument("--db", default="", help="database JSON path")
    parser.add_argument("--host", default="127.0.0.1", help="bind address")
    parser.add_argument("--port", type=int, default=8765, help="listen port")
    args = parser.parse_args(argv)
    token = os.environ.get("CODEMATE_API_TOKEN", "")
    if len(token) < 32:
        parser.error("set CODEMATE_API_TOKEN to a random secret of at least 32 characters")
    try:
        import uvicorn
    except ImportError as exc:
        parser.error(f"uvicorn is required to serve the API: {exc}")
    app_dir = Path(__file__).resolve().parent.parent
    if args.db:
        db_path = Path(args.db)
    else:
        from baza_skryptow import cfg_load
        db_path = Path(cfg_load().get("db_path") or app_dir / "baza_skryptow.json")
    webhook_url = os.environ.get("CODEMATE_API_WEBHOOK_URL") or None
    uvicorn.run(create_app(db_path, token, webhook_url), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())