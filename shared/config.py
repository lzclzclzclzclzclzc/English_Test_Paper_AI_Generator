"""Application configuration management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseModel):
    env: Literal["development", "production", "test"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    session_ttl_days: int = 30
    bcrypt_rounds: int = 12
    static_dir: Path = Path("backend/static")
    frontend_origin: str = "http://localhost:5173"
    rate_limit_generate_per_min: int = 30
    rate_limit_solutions_per_min: int = 60
    rate_limit_writing_per_min: int = 10
    rate_limit_agent_per_min: int = 20


class CreditsConfig(BaseModel):
    """积分赠送规则（docs/credits-design.md §2）。价目表在 backend/services/credits/pricing.py。"""

    signup_bonus: int = 300      # 注册一次性赠送（进 balance，不过期）
    daily_grant: int = 30        # 每日赠送（当日有效，不累积；Asia/Shanghai 日界）


class PaymentConfig(BaseModel):
    """支付宝沙盒 / 离线 mock（原 payment/ 独立服务的配置，2026-08 合并进主后端）。"""

    mock_pay: bool = True
    order_ttl_seconds: int = 300
    alipay_appid: str = ""
    alipay_gateway: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    # 网页收银台(channel=web)支付完成后跳回的页面
    pay_return_url: str = "http://localhost:5173/credits"
    alipay_app_private_key_path: Path = Path("keys/app_private_key.pem")
    alipay_public_key_path: Path = Path("keys/alipay_public_key.pem")


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    db_path: Path = Path("data/questions.db")
    app_db_path: Path = Path("data/app.db")
    chroma_path: Path = Path("data/chroma")
    kb_tree_path: Path = Path("data/kb/knowledge_tree.json")
    chapters_dir: Path = Path("data/chapters")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.scnet.cn/api/llm/v1"
    llm_model: str = "DeepSeek-V4-Flash"
    llm_max_concurrency: int = 4
    llm_max_retries: int = 3

    max_questions_per_paper: int = 50
    backend: BackendConfig = BackendConfig()
    credits: CreditsConfig = CreditsConfig()
    payment: PaymentConfig = PaymentConfig()


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Global singleton configuration."""
    global _config
    if _config is None:
        config = AppConfig()
        _config = config.model_copy(
            update={
                "db_path": Path(os.getenv("SQLITE_PATH", config.db_path)),
                "app_db_path": Path(os.getenv("APP_DB_PATH", config.app_db_path)),
                "chroma_path": Path(os.getenv("CHROMA_PATH", config.chroma_path)),
                "backend": config.backend.model_copy(
                    update={
                        "env": os.getenv("BACKEND_ENV", config.backend.env),
                        "host": os.getenv("BACKEND_HOST", config.backend.host),
                        "port": int(os.getenv("BACKEND_PORT", config.backend.port)),
                        "session_ttl_days": int(os.getenv("SESSION_TTL_DAYS", config.backend.session_ttl_days)),
                        "bcrypt_rounds": int(os.getenv("BCRYPT_ROUNDS", config.backend.bcrypt_rounds)),
                        "static_dir": Path(os.getenv("BACKEND_STATIC_DIR", config.backend.static_dir)),
                        "frontend_origin": os.getenv("FRONTEND_ORIGIN", config.backend.frontend_origin),
                        "rate_limit_generate_per_min": int(
                            os.getenv("RATE_LIMIT_GENERATE_PER_MIN", config.backend.rate_limit_generate_per_min)
                        ),
                        "rate_limit_solutions_per_min": int(
                            os.getenv("RATE_LIMIT_SOLUTIONS_PER_MIN", config.backend.rate_limit_solutions_per_min)
                        ),
                        "rate_limit_agent_per_min": int(
                            os.getenv("RATE_LIMIT_AGENT_PER_MIN", config.backend.rate_limit_agent_per_min)
                        ),
                    }
                ),
                "credits": config.credits.model_copy(
                    update={
                        "signup_bonus": int(os.getenv("CREDITS_SIGNUP_BONUS", config.credits.signup_bonus)),
                        "daily_grant": int(os.getenv("CREDITS_DAILY_GRANT", config.credits.daily_grant)),
                    }
                ),
                "payment": config.payment.model_copy(
                    update={
                        "mock_pay": _env_bool("PAYMENT_MOCK", config.payment.mock_pay),
                        "order_ttl_seconds": int(os.getenv("PAYMENT_ORDER_TTL_SECONDS", config.payment.order_ttl_seconds)),
                        "alipay_appid": os.getenv("ALIPAY_APPID", config.payment.alipay_appid),
                        "alipay_gateway": os.getenv("ALIPAY_GATEWAY", config.payment.alipay_gateway),
                        "pay_return_url": os.getenv("PAY_RETURN_URL", config.payment.pay_return_url),
                        "alipay_app_private_key_path": Path(
                            os.getenv("ALIPAY_APP_PRIVATE_KEY_PATH", config.payment.alipay_app_private_key_path)
                        ),
                        "alipay_public_key_path": Path(
                            os.getenv("ALIPAY_PUBLIC_KEY_PATH", config.payment.alipay_public_key_path)
                        ),
                    }
                ),
            }
        )
    return _config


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def reset_config_cache() -> None:
    global _config
    _config = None
