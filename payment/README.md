# 支付子系统(支付宝沙盒 · 扫码 / 网页收银台)

独立的 FastAPI 小服务(默认 `:8001`),为墨卷提供**会员订阅**的模拟支付,两种通道:

- **qr(当面付扫码)**:`alipay.trade.precreate` → 前端渲染二维码 → 沙箱版支付宝
  App(仅 Android)扫码付款
- **web(电脑网站支付)**:`alipay.trade.page.pay` → 新标签页打开沙盒网页收银台,
  用沙箱**买家账号 + 支付密码**在桌面浏览器直接付款,**不需要手机**

两种通道支付后都由前端轮询、服务端 `alipay.trade.query` 查单确认 → 会员有效期顺延。
前端自动选通道:mock 模式走扫码弹窗(带模拟支付按钮),真实沙盒模式走网页收银台。

本地无公网地址,因此**不使用异步通知(notify_url)**,支付结果完全依赖轮询查单。
若将来部署到有公网的环境,可在 `alipay_client.py` 的 `AliPay(app_notify_url=...)`
处接入异步通知作为补充。

## 快速开始(离线 mock 模式,无需支付宝账号)

```bash
cd payment
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # 默认 MOCK_PAY=true
# .env 里设 PAYMENT_DEV_FAKE_USER=harry(不跑主后端时必设)
.venv/bin/uvicorn app.main:app --port 8001 --reload
```

另开终端起前端:`cd frontend && npm run dev`,访问 http://localhost:5173/membership 。
mock 模式下二维码是假码,弹窗里会出现「模拟支付成功(离线模式)」按钮,点击即完成支付。

## 接入真实支付宝沙盒

1. 用真实支付宝账号登录 https://open.alipay.com → 控制台 → **沙箱**
   (直达:https://open.alipay.com/develop/sandbox/app)。
2. 复制沙箱应用的 **APPID**(形如 `9021000xxxxxxxx`)→ `.env` 的 `ALIPAY_APPID`。
3. 开发信息 → 接口加签方式 → **系统默认密钥 → 公钥模式** → 查看:
   - **应用私钥** → 存为 `keys/app_private_key.pem`
   - **支付宝公钥**(注意不是"应用公钥")→ 存为 `keys/alipay_public_key.pem`
4. 沙箱账号页记下**买家账号**、登录密码、支付密码(付款时用)。
5. `.env` 设 `MOCK_PAY=false`,重启服务。
6. (可选,仅 Android)沙箱工具页下载**沙箱版支付宝 App**,用买家账号登录,
   即可走扫码通道;没有 Android 就用网页收银台通道,无需此步。

### 密钥格式说明

沙盒控制台展示的密钥是单行 base64,需要补上 PEM 框(base64 正文按 64 字符换行为佳):

```
-----BEGIN RSA PRIVATE KEY-----
<应用私钥 base64>
-----END RSA PRIVATE KEY-----
```

```
-----BEGIN PUBLIC KEY-----
<支付宝公钥 base64>
-----END PUBLIC KEY-----
```

### 网关地址

新版沙盒网关为 `https://openapi-sandbox.dl.alipaydev.com/gateway.do`(已写在
`.env.example`)。SDK `debug=True` 默认指向的旧域名 `openapi.alipaydev.com` 已废弃,
代码里会用 `.env` 的 `ALIPAY_GATEWAY` 覆盖;若支付宝再次迁移域名,改 `.env` 即可。

## 登录态

除 `/payapi/health` 外的接口都需要登录。服务本身不管账号,而是把请求里的
`session_id` cookie 转发到主后端 `GET /api/auth/me` 校验(30 秒缓存)。

本地联调若不跑主后端,在 `.env` 设 `PAYMENT_DEV_FAKE_USER=<任意名字>`,
所有请求会被视为该用户,完全跳过主后端。

## API

约定与主后端一致:成功直接返回数据;失败返回
`{error_code, message, detail, trace_id}`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/payapi/health` | 存活 + 当前模式 |
| GET | `/payapi/plans` | 套餐列表(月 ¥9.9 / 季 ¥25 / 年 ¥88,硬编码) |
| GET | `/payapi/membership/me` | 当前会员状态 `{user_id, expires_at, active}` |
| POST | `/payapi/orders` | 建单,body `{"plan_id": "monthly", "channel": "qr"\|"web"}`(默认 qr),201;qr 返回 `qr_code`,web 返回 `pay_url` |
| GET | `/payapi/orders/{out_trade_no}` | **轮询端点**:惰性过期 + 向支付宝查单同步 |
| POST | `/payapi/orders/{out_trade_no}/cancel` | 关单;已支付返回 409 |
| POST | `/payapi/dev/simulate-paid/{out_trade_no}` | 仅 `MOCK_PAY=true` 时注册 |

错误码:`payment.plan_not_found`、`payment.order_not_found`、
`payment.order_not_cancelable`、`payment.upstream_error`、
`payment.auth_upstream_unavailable`,复用 `auth.unauthorized`、`request.invalid`。

Swagger:http://localhost:8001/payapi/docs

## 设计要点

- **订单**:`orders` 表,状态机 `CREATED → PAID | EXPIRED | CLOSED`,二维码有效期
  `ORDER_TTL_SECONDS`(默认 5 分钟),过期在轮询时惰性判定,无后台任务。
- **幂等**:支付成功用单事务 CAS(`UPDATE ... WHERE status='CREATED'`)保证
  `CREATED→PAID` 只发生一次,只有赢得转移的调用才顺延会员;
  重复的 TRADE_SUCCESS/模拟支付不会重复加时长。
- **会员顺延**:从 `max(now, 当前到期日)` 加套餐天数;已过期则从现在起算。
- **存储**:SQLite(`data/payment.db`,WAL),标准库 `sqlite3`,金额以"分"存整数。

## 测试

```bash
cd payment && .venv/bin/python -m pytest
```

覆盖:三种顺延基准(首购/未到期续费/过期续费)、重复支付幂等、二维码过期、
关单规则、错误体结构、订单归属校验。测试全程 mock 模式 + 临时库,不碰网络。
