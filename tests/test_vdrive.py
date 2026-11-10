import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from baza_skryptow import CodeMate
from src.vdrive import default_vdrive_state, load_vdrive_state, save_vdrive_state


def test_vdrive_state_round_trip_preserves_drives_and_settings(tmp_path):
    path = tmp_path / "vdrive_state.json"
    drives = [{
        "id": 4,
        "typ": "VHDX",
        "label": "Work disk",
        "path": "images/work.vhdx",
        "size_mb": 2048,
        "mounted": True,
        "drive_letter": "R:",
        "fs": "NTFS",
        "readonly": True,
        "persistent": True,
        "compress": True,
    }]
    settings = {
        "images_dir": "D:/Images",
        "tool_win": "diskpart (wbudowany)",
        "tool_lin": "qemu-img + mount",
        "global_automount": False,
        "global_notify": False,
        "global_autostart": True,
    }

    saved = save_vdrive_state(path, drives, settings)
    loaded = load_vdrive_state(path)

    assert saved["drives"][0]["mounted"] is False
    assert loaded["drives"][0]["label"] == "Work disk"
    assert loaded["drives"][0]["drive_letter"] == "R:"
    assert loaded["drives"][0]["readonly"] is True
    assert loaded["drives"][0]["compress"] is True
    assert loaded["drives"][0]["mounted"] is False
    assert loaded["settings"] == settings
    assert not path.with_name(path.name + ".tmp").exists()


def test_corrupt_state_file_uses_defaults(tmp_path):
    path = tmp_path / "vdrive_state.json"
    path.write_text("{invalid", encoding="utf-8")

    assert load_vdrive_state(path) == default_vdrive_state()


def test_state_with_wrong_schema_or_shape_uses_defaults(tmp_path):
    path = tmp_path / "vdrive_state.json"
    path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_vdrive_state(path) == default_vdrive_state()
    path.write_text(json.dumps({"schema": 999, "drives": []}), encoding="utf-8")
    assert load_vdrive_state(path) == default_vdrive_state()


def test_load_normalizes_bad_drive_id_and_non_dict_settings(tmp_path):
    path = tmp_path / "vdrive_state.json"
    path.write_text(json.dumps({
        "schema": 1,
        "drives": [{"id": {"bad": "type"}, "label": "disk"}],
        "settings": "not-a-dict",
    }), encoding="utf-8")

    state = load_vdrive_state(path)

    assert state["drives"][0]["id"] == 0
    assert state["settings"] == default_vdrive_state()["settings"]


def test_load_skips_invalid_drives_and_normalizes_settings(tmp_path):
    path = tmp_path / "vdrive_state.json"
    path.write_text(json.dumps({
        "schema": 1,
        "drives": [None, {"label": "  "}, {"label": "disk", "size_mb": "bad"}],
        "settings": {"global_notify": "false", "images_dir": "  /data  "},
    }), encoding="utf-8")

    state = load_vdrive_state(path)

    assert len(state["drives"]) == 1
    assert state["drives"][0]["size_mb"] == 0
    assert state["settings"]["images_dir"] == "/data"
    assert state["settings"]["global_notify"] is True


def test_vdrive_ui_persist_hook_saves_current_state(tmp_path, monkeypatch):
    state_path = tmp_path / "vdrive_state.json"
    captured = {}
    settings = {"images_dir": "D:/Images"}

    def fake_save(path, drives, saved_settings):
        captured.update(path=path, drives=drives, settings=saved_settings)
        return {"schema": 1, "drives": drives, "settings": saved_settings}

    monkeypatch.setattr(bs, "VDRIVE_STATE_FILE", state_path)
    monkeypatch.setattr(bs, "save_vdrive_state", fake_save)
    app = SimpleNamespace(
        _vdrives=[{"label": "Archive"}],
        _vdrive_collect_settings=lambda: settings,
        _vdrive_log=lambda *_args: None,
    )

    assert CodeMate._vdrive_persist_state(app)
    assert captured == {
        "path": state_path,
        "drives": app._vdrives,
        "settings": settings,
    }
    assert app._vdrive_settings == settings


def test_copy_mount_command_does_not_claim_drive_is_mounted(monkeypatch):
    calls = []
    drive = {"label": "Archive", "path": "", "mounted": False}
    app = SimpleNamespace(
        _vdrive_get_selected_idx=lambda: 0,
        _vdrives=[drive],
        _vdrive_build_mount_cmd=lambda _drive: "mount-command --safe",
        clipboard_clear=lambda: calls.append(("clear",)),
        clipboard_append=lambda value: calls.append(("append", value)),
        _vdrive_log=lambda message, tag: calls.append(("log", message, tag)),
        _vdrive_set_status=lambda message, color: calls.append(("status", message, color)),
    )

    bs._set_lang("pl")
    CodeMate._vdrive_copy_mount_command(app)

    assert drive["mounted"] is False
    assert calls[0:2] == [("clear",), ("append", "mount-command --safe")]
    assert calls[-1][0] == "status"
    assert "nie zostało wykonane" in calls[-1][1]