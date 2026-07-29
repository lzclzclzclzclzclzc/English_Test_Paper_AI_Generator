from datetime import datetime, timezone
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mock_pay: bool = True
    payment_dev_fake_user: str = ""
    main_backend_url: str = "http://localhost:8000"

    db_path: str = "data/payment.db"
    order_ttl_seconds: int = 300

    alipay_appid: str = ""
    alipay_gateway: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    # 网页收银台(channel=web)支付完成后跳回的页面
    pay_return_url: str = "http://localhost:5173/membership"
    alipay_app_private_key_path: str = "keys/app_private_key.pem"
    alipay_public_key_path: str = "keys/alipay_public_key.pem"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return format_iso(utcnow())


def format_iso(dt: datetime) -> str:
    """统一为秒精度的 ...Z 格式,保证同格式字符串可直接按字典序比较。"""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
