from __future__ import annotations

from pathlib import Path

from shared import storage
from shared.config import reset_config_cache


def test_bank_path_defaults_to_config_db_path(monkeypatch):
    monkeypatch.delenv("SQLITE_PATH", raising=False)
    reset_config_cache()
    storage.set_bank_db_path(None)
    try:
        assert storage.get_bank_db_path() == Path("data/questions.db")
    finally:
        storage.set_bank_db_path(None)
        reset_config_cache()


def test_bank_override_wins(tmp_path):
    bank = tmp_path / "bank.db"
    storage.set_bank_db_path(bank)
    try:
        assert storage.get_bank_db_path() == bank
    finally:
        storage.set_bank_db_path(None)


def test_connect_bank_opens_the_bank_path(tmp_path):
    bank = tmp_path / "bank.db"
    storage.set_bank_db_path(bank)
    try:
        with storage.connect_bank() as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
        assert bank.exists()
        with storage.connect_bank() as conn:
            assert conn.execute("SELECT x FROM t").fetchone()["x"] == 1
    finally:
        storage.set_bank_db_path(None)
