import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import exe_export


def test_build_executable_uses_safe_pyinstaller_arguments(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        output = Path(command[command.index("--distpath") + 1])
        (output / "My_script.exe").write_bytes(b"exe")
        return SimpleNamespace(returncode=0, stdout="build ok", stderr="")

    monkeypatch.setattr(exe_export.subprocess, "run", fake_run)
    result = exe_export.build_executable(
        {"nazwa": "My script", "kategoria": "Python", "kod": "print(1)"},
        tmp_path, onefile=True, console=False,
    )
    assert Path(result["path"]).read_bytes() == b"exe"
    assert result["log"] == "build ok"
    assert "--onefile" in captured["command"]
    assert "--windowed" in captured["command"]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["timeout"] == 900


def test_rejects_non_python_script(tmp_path):
    with pytest.raises(ValueError, match="Only Python"):
        exe_export.build_executable({"kategoria": "Bash"}, tmp_path)


def test_rejects_missing_or_non_ico_icon(tmp_path):
    script = {"nazwa": "x", "kategoria": "Python", "kod": ""}
    with pytest.raises(ValueError, match=".ico"):
        exe_export.build_executable(script, tmp_path, icon=tmp_path / "missing.ico")
    text_icon = tmp_path / "icon.png"
    text_icon.write_bytes(b"x")
    with pytest.raises(ValueError, match=".ico"):
        exe_export.build_executable(script, tmp_path, icon=text_icon)


def test_reports_pyinstaller_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(exe_export.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout="", stderr="failed"))
    with pytest.raises(RuntimeError, match="failed"):
        exe_export.build_executable(
            {"nazwa": "x", "kategoria": "Python", "kod": ""}, tmp_path)


def test_rejects_unavailable_interpreter(tmp_path, monkeypatch):
    monkeypatch.setattr(exe_export.shutil, "which", lambda _exe: None)
    with pytest.raises(RuntimeError, match="interpreter"):
        exe_export.build_executable(
            {"nazwa": "x", "kategoria": "Python", "kod": ""}, tmp_path)


def test_valid_ico_icon_is_passed_to_pyinstaller(tmp_path, monkeypatch):
    icon = tmp_path / "icon.ico"
    icon.write_bytes(b"ico")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        output = Path(command[command.index("--distpath") + 1])
        (output / "x.exe").write_bytes(b"exe")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(exe_export.subprocess, "run", fake_run)
    exe_export.build_executable(
        {"nazwa": "x", "kategoria": "Python", "kod": ""}, tmp_path, icon=icon)
    assert "--icon" in captured["command"]


def test_pyinstaller_binary_missing(tmp_path, monkeypatch):
    def raise_fnf(*args, **kwargs):
        raise FileNotFoundError("pyinstaller not found")

    monkeypatch.setattr(exe_export.subprocess, "run", raise_fnf)
    with pytest.raises(RuntimeError, match="PyInstaller is not installed"):
        exe_export.build_executable(
            {"nazwa": "x", "kategoria": "Python", "kod": ""}, tmp_path)


def test_pyinstaller_timeout(tmp_path, monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pyinstaller", timeout=1)

    monkeypatch.setattr(exe_export.subprocess, "run", raise_timeout)
    with pytest.raises(TimeoutError, match="exceeded"):
        exe_export.build_executable(
            {"nazwa": "x", "kategoria": "Python", "kod": ""}, tmp_path, timeout=5)


def test_missing_build_artifact_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(exe_export.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    with pytest.raises(RuntimeError, match="artifact was not found"):
        exe_export.build_executable(
            {"nazwa": "x", "kategoria": "Python", "kod": ""}, tmp_path)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="Windows executable export")
def test_builds_and_runs_onefile_executable(tmp_path):
    result = exe_export.build_executable(
        {
            "nazwa": "integration sample",
            "kategoria": "Python",
            "kod": "import sys\nprint('export-ok:' + sys.argv[1])\n",
        },
        tmp_path,
        onefile=True,
        console=True,
        timeout=900,
    )

    artifact = Path(result["path"])
    assert artifact.is_file()
    execution = subprocess.run(
        [str(artifact), "verified"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    assert "export-ok:verified" in execution.stdout
