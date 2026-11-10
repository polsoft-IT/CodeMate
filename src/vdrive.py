"""Persistence helpers for the VDrive registry and preferences."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = 1


def default_vdrive_state() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "drives": [],
        "settings": {
            "images_dir": str(Path.home() / "VDriveImages"),
            "tool_win": "PowerShell Mount-DiskImage",
            "tool_lin": "mount (wbudowany)",
            "global_automount": True,
            "global_notify": True,
            "global_autostart": False,
        },
    }


def _normalize_drive(value: Any, index: int) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    label = str(value.get("label", "")).strip()
    if not label:
        return None
    try:
        size_mb = max(0, int(value.get("size_mb", 0)))
    except (TypeError, ValueError):
        size_mb = 0
    drive_id = value.get("id", index)
    if not isinstance(drive_id, (int, str)):
        drive_id = index
    return {
        "id": drive_id,
        "typ": str(value.get("typ", "HDD")).strip().upper() or "HDD",
        "label": label,
        "path": str(value.get("path", "")).strip(),
        "size_mb": size_mb,
        "mounted": False,
        "drive_letter": str(value.get("drive_letter", "")).strip(),
        "fs": str(value.get("fs", "(brak)")).strip(),
        "readonly": bool(value.get("readonly", False)),
        "persistent": bool(value.get("persistent", False)),
        "compress": bool(value.get("compress", False)),
    }


def _normalize_settings(value: Any) -> Dict[str, Any]:
    settings: Dict[str, Any] = dict(default_vdrive_state()["settings"])
    if not isinstance(value, dict):
        return settings
    for key in ("images_dir", "tool_win", "tool_lin"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            settings[key] = candidate.strip()
    for key in ("global_automount", "global_notify", "global_autostart"):
        candidate = value.get(key)
        if isinstance(candidate, bool):
            settings[key] = candidate
    return settings


def load_vdrive_state(path: str | Path) -> Dict[str, Any]:
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_vdrive_state()
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
        return default_vdrive_state()
    drives: List[Dict[str, Any]] = []
    raw_drives = data.get("drives", [])
    if isinstance(raw_drives, list):
        for index, value in enumerate(raw_drives):
            drive = _normalize_drive(value, index)
            if drive is not None:
                drives.append(drive)
    return {
        "schema": SCHEMA_VERSION,
        "drives": drives,
        "settings": _normalize_settings(data.get("settings")),
    }


def save_vdrive_state(path: str | Path, drives: List[Dict[str, Any]],
                      settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized_drives = []
    for index, value in enumerate(drives):
        drive = _normalize_drive(value, index)
        if drive is not None:
            normalized_drives.append(drive)
    state = {
        "schema": SCHEMA_VERSION,
        "drives": normalized_drives,
        "settings": _normalize_settings(settings),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return state