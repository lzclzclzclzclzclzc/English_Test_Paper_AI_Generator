import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import get_settings

_DDL = """
CREATE TABLE IF NOT EXISTS orders (
  out_trade_no    TEXT PRIMARY KEY,
  user_id         TEXT NOT NULL,
  plan_id         TEXT NOT NULL,
  amount_cents    INTEGER NOT NULL,
  status          TEXT NOT NULL DEFAULT 'CREATED',
  qr_code         TEXT,
  alipay_trade_no TEXT,
  created_at      TEXT NOT NULL,
  expires_at      TEXT NOT NULL,
  paid_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS memberships (
  user_id    TEXT PRIMARY KEY,
  expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    """每次调用新连接,退出时提交(异常则回滚),即一个连接即一个事务。"""
    path = Path(get_settings().db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_DDL)
        # 增量列(老库升级):channel 支付通道,pay_url 网页收银台链接
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
        if "channel" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN channel TEXT NOT NULL DEFAULT 'qr'")
        if "pay_url" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN pay_url TEXT")
