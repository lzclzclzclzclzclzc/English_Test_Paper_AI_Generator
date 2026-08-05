from __future__ import annotations

from pathlib import Path

from shared.config import get_config, reset_config_cache


def test_app_db_path_defaults_to_data_app_db(monkeypatch):
    monkeypatch.delenv("APP_DB_PATH", raising=False)
    reset_config_cache()
    try:
        assert get_config().app_db_path == Path("data/app.db")
    finally:
        reset_config_cache()


def test_app_db_path_honours_env_override(monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", "/tmp/custom-app.db")
    reset_config_cache()
    try:
        assert get_config().app_db_path == Path("/tmp/custom-app.db")
    finally:
        reset_config_cache()


def test_db_path_still_bank_and_independent(monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", "/tmp/bank.db")
    monkeypatch.setenv("APP_DB_PATH", "/tmp/app.db")
    reset_config_cache()
    try:
        cfg = get_config()
        assert cfg.db_path == Path("/tmp/bank.db")
        assert cfg.app_db_path == Path("/tmp/app.db")
    finally:
        reset_config_cache()
