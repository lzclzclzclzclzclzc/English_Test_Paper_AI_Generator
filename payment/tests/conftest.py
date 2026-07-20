import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """mock 模式 + 假用户 + 临时库;清掉 settings 缓存与支付客户端单例。"""
    monkeypatch.setenv("MOCK_PAY", "true")
    monkeypatch.setenv("PAYMENT_DEV_FAKE_USER", "tester")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    from app.config import get_settings

    get_settings.cache_clear()

    import app.alipay_client as alipay_client

    alipay_client._client = None

    from app.db import init_db

    init_db()
    yield
    get_settings.cache_clear()
    alipay_client._client = None


@pytest.fixture()
def client(env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
