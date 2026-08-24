"""支付宝沙盒当面付 / 网页收银台客户端（原 payment/app/alipay_client.py，2026-08 合并进主后端）。"""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend.errors import PaymentUpstreamError
from shared.config import get_config


@dataclass(frozen=True)
class QueryResult:
    paid: bool = False
    closed: bool = False
    trade_no: str | None = None


class PayClient(Protocol):
    def precreate(self, out_trade_no: str, amount_cents: int, subject: str) -> str:
        """当面付下单,返回 qr_code 内容。"""
        ...

    def page_pay_url(self, out_trade_no: str, amount_cents: int, subject: str) -> str:
        """电脑网站支付下单,返回可在桌面浏览器打开的收银台 URL。"""
        ...

    def query(self, out_trade_no: str) -> QueryResult: ...


class MockAlipayClient:
    """离线模式:不发网络请求。支付只能通过 dev/simulate-paid 端点推进。"""

    def precreate(self, out_trade_no: str, amount_cents: int, subject: str) -> str:
        return f"MOCK|{out_trade_no}"

    def page_pay_url(self, out_trade_no: str, amount_cents: int, subject: str) -> str:
        return f"MOCK|{out_trade_no}"

    def query(self, out_trade_no: str) -> QueryResult:
        return QueryResult()


class RealAlipayClient:
    """支付宝沙盒当面付。SDK 为同步实现,调用方应走线程池(sync 路由)。"""

    def __init__(self) -> None:
        from alipay import AliPay  # 延迟导入,mock 模式无需安装齐全依赖

        settings = get_config().payment
        self._client = AliPay(
            appid=settings.alipay_appid,
            app_notify_url=None,  # 本地无公网,仅轮询 trade.query,不做异步通知
            app_private_key_string=Path(settings.alipay_app_private_key_path).read_text(),
            alipay_public_key_string=Path(settings.alipay_public_key_path).read_text(),
            sign_type="RSA2",
            debug=True,
        )
        # SDK debug 模式默认指向已废弃的旧沙盒域名,必须覆盖为新版网关
        self._client._gateway = settings.alipay_gateway

    def precreate(self, out_trade_no: str, amount_cents: int, subject: str) -> str:
        ttl_minutes = max(1, get_config().payment.order_ttl_seconds // 60)
        resp = self._client.api_alipay_trade_precreate(
            out_trade_no=out_trade_no,
            total_amount=f"{amount_cents / 100:.2f}",
            subject=subject,
            timeout_express=f"{ttl_minutes}m",
        )
        if resp.get("code") != "10000":
            raise PaymentUpstreamError(f"支付宝下单失败: {resp.get('sub_msg') or resp.get('msg')}")
        return resp["qr_code"]

    def page_pay_url(self, out_trade_no: str, amount_cents: int, subject: str) -> str:
        settings = get_config().payment
        ttl_minutes = max(1, settings.order_ttl_seconds // 60)
        # page_pay 返回已签名的 query string,拼在网关后即为收银台 URL
        order_string = self._client.api_alipay_trade_page_pay(
            out_trade_no=out_trade_no,
            total_amount=f"{amount_cents / 100:.2f}",
            subject=subject,
            return_url=settings.pay_return_url,
            timeout_express=f"{ttl_minutes}m",
        )
        return f"{settings.alipay_gateway}?{order_string}"

    def query(self, out_trade_no: str) -> QueryResult:
        resp = self._client.api_alipay_trade_query(out_trade_no=out_trade_no)
        code = resp.get("code")
        if code == "40004":
            # ACQ.TRADE_NOT_EXIST:买家尚未扫码,支付宝侧还没有这笔交易
            return QueryResult()
        if code != "10000":
            raise PaymentUpstreamError(f"支付宝查单失败: {resp.get('sub_msg') or resp.get('msg')}")
        status = resp.get("trade_status")
        if status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return QueryResult(paid=True, trade_no=resp.get("trade_no"))
        if status == "TRADE_CLOSED":
            return QueryResult(closed=True)
        return QueryResult()  # WAIT_BUYER_PAY


_client: PayClient | None = None


def get_pay_client() -> PayClient:
    global _client
    if _client is None:
        _client = MockAlipayClient() if get_config().payment.mock_pay else RealAlipayClient()
    return _client


def reset_pay_client() -> None:
    """测试 / 改配置后重建客户端。"""
    global _client
    _client = None
