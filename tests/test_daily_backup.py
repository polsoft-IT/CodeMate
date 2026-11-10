# ── Testy dziennego backupu bazy (daily_backup) ───────────────────────────────
import datetime
import json

import pytest

import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "bs", os.path.join(_ROOT, "baza_skryptow.py"))
bs = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("bs", bs)
_SPEC.loader.exec_module(bs)


def _make_db(tmp_path, nazwa="baza_skryptow.json"):
    db = tmp_path / nazwa
    db.write_text(json.dumps({"schema": 2, "skrypty": []}), encoding="utf-8")
    return db


class TestDailyBackup:
    def test_creates_backup_with_today_stamp(self, tmp_path):
        db = _make_db(tmp_path)
        target = bs.daily_backup(db, keep=7)
        assert target is not None
        stamp = datetime.date.today().isoformat()
        assert target.name == f"baza_skryptow.{stamp}.json"
        assert target.parent.name == "backups"
        assert json.loads(target.read_text(encoding="utf-8"))["schema"] == 2

    def test_second_call_same_day_returns_none(self, tmp_path):
        db = _make_db(tmp_path)
        assert bs.daily_backup(db, keep=7) is not None
        # dzisiejsza już istnieje — drugie wywołanie nic nie tworzy
        assert bs.daily_backup(db, keep=7) is None

    def test_missing_db_returns_none(self, tmp_path):
        assert bs.daily_backup(tmp_path / "nie_ma.json") is None

    def test_rotation_keeps_newest(self, tmp_path):
        db = _make_db(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        # 3 stare kopie o różnych datach (najstarsze pierwsze)
        old = sorted(
            backup_dir / f"baza_skryptow.{d}.json"
            for d in ("2020-01-0%d" % i for i in (1, 2, 3)))
        for i, p in enumerate(old, 1):
            p.write_text(f"old-{i}", encoding="utf-8")
        target = bs.daily_backup(db, keep=2)
        assert target is not None
        remaining = sorted(p.name for p in backup_dir.glob("baza_skryptow.*.json"))
        # keep=2 → zostają najnowsza stara (01-03) + dzisiejsza
        assert len(remaining) == 2
        assert remaining[0] == "baza_skryptow.2020-01-03.json"
        assert remaining[1].endswith(f"{datetime.date.today().isoformat()}.json")

    def test_keep_zero_keeps_only_today(self, tmp_path):
        db = _make_db(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "baza_skryptow.2019-05-05.json").write_text("x", encoding="utf-8")
        assert bs.daily_backup(db, keep=0) is not None
        names = [p.name for p in backup_dir.glob("baza_skryptow.*.json")]
        assert len(names) == 1
        assert datetime.date.today().isoformat() in names[0]
