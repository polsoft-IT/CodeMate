"""Build standalone Windows executables from Python script records."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional


def build_executable(
    script: Dict[str, str],
    output_dir: Path | str,
    onefile: bool = True,
    icon: Optional[Path | str] = None,
    console: bool = True,
    timeout: int = 900,
) -> Dict[str, str]:
    """Build an executable with PyInstaller and return artifact path and log."""
    if script.get("kategoria") != "Python":
        raise ValueError("Only Python scripts can be exported to .exe")
    if not shutil.which(sys.executable):
        raise RuntimeError("The selected Python interpreter is unavailable")
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    icon_path = Path(icon).expanduser().resolve() if icon else None
    if icon_path and (not icon_path.is_file() or icon_path.suffix.lower() != ".ico"):
        raise ValueError("Icon must be an existing .ico file")
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(script.get("nazwa") or "script")).strip("_-")
    name = name[:80] or "script"

    with tempfile.TemporaryDirectory(prefix="bs_pyinstaller_") as temporary:
        work = Path(temporary)
        source = work / f"{name}.py"
        source.write_text(str(script.get("kod") or ""), encoding="utf-8")
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--name", name, "--distpath", str(destination),
            "--workpath", str(work / "build"), "--specpath", str(work),
        ]
        command.append("--onefile" if onefile else "--onedir")
        command.append("--console" if console else "--windowed")
        if icon_path:
            command.extend(["--icon", str(icon_path)])
        command.append(str(source))
        try:
            result = subprocess.run(
                command, cwd=work, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, shell=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("PyInstaller is not installed; install it with pip install pyinstaller") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"PyInstaller exceeded {timeout} seconds") from exc
        log = (result.stdout or "") + (result.stderr or "")
        if result.returncode:
            raise RuntimeError(log[-32_000:] or f"PyInstaller exited with {result.returncode}")
        artifact = destination / (name + (".exe" if onefile else ""))
        if not artifact.exists():
            raise RuntimeError(f"PyInstaller succeeded but artifact was not found: {artifact}")
        return {"path": str(artifact), "log": log[-32_000:]}