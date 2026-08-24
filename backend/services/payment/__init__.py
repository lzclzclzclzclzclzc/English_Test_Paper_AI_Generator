"""支付子系统（支付宝沙盒 mock / 真实）—— 2026-08 自独立服务 payment/ 合并进主后端。

orders.py  订单状态机 + 支付成功入账（调 services.credits）
packs.py   积分包定价
alipay_client.py  支付宝 SDK 封装（mock / real）
"""
