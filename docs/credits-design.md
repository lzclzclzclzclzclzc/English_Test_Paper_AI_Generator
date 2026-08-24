# 积分与支付设计（Spec P · 2026-08-23）

> 取代 2026-07 的「会员订阅 + 独立支付服务（payment/ :8001）」方案。
> 本文是积分账本、价目表、扣费点、支付合并与迁移的唯一事实来源；
> 代码：`backend/services/credits/`、`backend/services/payment/`、`backend/api/credits.py`、
> `backend/api/payment.py`、`shared/storage.py` `MIGRATION_CREDITS_AND_ORDERS`。

## 0. 结论先行

- **纯积分制**：不再有会员。所有出卷 / AI 操作按价目表扣积分；做题、判分、错题本、
  掌握度、学情报告、打印、背单词、手动建脑图免费。
- **注册赠送 + 每日赠送**：注册送 `CREDITS_SIGNUP_BONUS`（默认 300，不过期），
  每天送 `CREDITS_DAILY_GRANT`（默认 30，当日有效、不累积；Asia/Shanghai 日界）。
- **支付合并进主后端**：原 `payment/` 独立服务删除；订单表、支付宝 SDK 封装、
  积分包都在主后端；支付成功 = 同一进程内 CAS + 账本入账，不再有跨服务回调 / 对账。
- **服务端强制**：扣费在后端每个付费端点里原子完成；前端只展示余额 / 价格、
  做本地预检和 402 → 充值引导。原先前端 localStorage 的「每天 3 次」配额与
  fail-open 的会员判断全部删除。

## 1. 数据模型（`data/app.db`，迁移 `20260823_001_credits_and_orders`）

| 表 | 关键列 | 说明 |
|---|---|---|
| `credit_accounts` | `user_id PK` · `balance` · `daily_balance` · `daily_date` · `updated_at` | 每用户一行。`balance` = 付费 / 赠送余额（不过期）；`daily_balance` = 今日赠送剩余；`daily_date` 与今天不同即**惰性重置**为 `daily_grant` |
| `credit_ledger` | `id` · `user_id` · `delta` · `bucket(daily\|balance)` · `balance_after` · `kind` · `action` · `ref_type` · `ref_id` · `note` · `created_at` | 只追加。**唯一索引 `(kind, ref_type, ref_id, bucket) WHERE ref_id IS NOT NULL`** 是所有幂等的根：同一订单只入账一次、同一次扣费只记一次、同一次退款只退一次 |
| `orders` | `out_trade_no PK` · `user_id` · `pack_id` · `amount_cents` · `credits` · `status` · `channel` · `qr_code` · `pay_url` · `alipay_trade_no` · `created_at` · `expires_at` · `paid_at` | 原 `payment.db.orders` 搬入；`plan_id` → `pack_id`，多了该包对应的 `credits` |

`kind` 取值：`signup_bonus` / `daily_grant` / `purchase` / `spend` / `refund` / `admin_adjust` / `migrate_membership`。

账户**惰性建立**：第一次被读到（余额接口 / 任何扣费 / admin 查看）时建行，同时写入
注册赠送（`ref=('user', user_id)`，幂等）与今日赠送——所以积分上线前已存在的老用户
第一次触达也会拿到同一笔注册赠送，不需要批量脚本。

## 2. 账本语义（`backend/services/credits/ledger.py`）

- **扣费顺序**：先 `daily` 后 `balance`。`charge()` 在 `BEGIN IMMEDIATE` 事务里读余额 →
  判断 → 写流水 → 更新账户；不足抛 `InsufficientCreditsError`（**HTTP 402 `credits.insufficient`**，
  `detail={required, available, action}`，production 下也保留 detail 供前端展示）。
- **幂等**：`charge(ref_type, ref_id)` 同 ref 重复调用返回既有收据（`duplicate=True`）。
- **退款**：`refund(ref)` 把该 ref 的 `spend` 行按原桶退回（一次性，再次调用返回 0）。
  管线 / LLM 在扣费后失败一律退款（papers / solutions / writing / agent / 计划出卷）。
- **入账**：`grant(amount, kind, ref)` 进 `balance` 桶；`amount` 可为负（管理员扣减），
  下限 0；带 ref 时幂等。
- **每日赠送**不单独记「过期」流水：次日第一次触达直接把 `daily_balance` 重置为满额并记一条
  新的 `daily_grant`（`ref=('day', f'{user_id}:{YYYY-MM-DD}')`）。

## 3. 价目表（`backend/services/credits/pricing.py`，前端通过 `GET /api/credits/prices` 下发，不硬编码）

| action | 价格 | 扣费点 | 备注 |
|---|---|---|---|
| `generate_original` | 5 + 1 / 题 | `POST /api/papers/generate` | 只 1 次 Parser LLM |
| `generate_light` | 5 + 3 / 题 | 同上 | 每题 1 次 LLM |
| `generate_fresh` | 5 + 4 / 题 | 同上（含 mode=review / remediation、主题出卷、整卷模拟、每日一练） | |
| `revise_paper` | 5 + 4 / 题 | `POST /api/papers/revise`（新增限流，与 generate 同桶） | |
| `solution` | 5 / 次 | `POST /api/solutions` | 每次 1 次 LLM；前端 query 缓存住不重复扣 |
| `writing_grade` | 20 / 篇 | `POST /api/writing/grade`（按篇数一次性扣） | 结果全量返回，不再分会员字段 |
| `agent_message` | 2 / 条 | `POST /api/agent/chat`（新增限流 `RATE_LIMIT_AGENT_PER_MIN`） | 助手工具里触发的出卷 / 计划按 `generate_*` 价另扣，余额不足以工具文本返回让模型转述 |
| 免费 | — | 做题判分、错题本、掌握度、学情报告、学生卷 / 教师版打印、背单词、手动脑图、计划查看 | 纯 SQL |

出卷价格取决于 **Parser 解析出的 `revision_intensity × total_questions`**，请求时（自然语言）
算不出——所以 `ai_engine.pipeline.generate_paper / revise_paper` 增加了 `on_request(req)` 回调：
Parser 之后、检索 / 改题之前调用，后端在回调里扣费（`credits.PaperCharge`），
抛 402 即终止管线；之后任何异常由调用方 `refund()`。扣费结果写进 `Paper.metadata`
（`credits_charged` / `credits_action` / `credits_balance_after` / `credits_daily_after`），
讲解 / 批改 / 助手响应体则带 `credits: {cost, balance_after, daily_after}`。

## 4. 支付（`backend/services/payment/`，原 payment/ 服务）

- **积分包**（`packs.py`，硬编码）：`starter ¥9.9 → 1000`、`standard ¥25 → 3000`、`annual ¥88 → 12000`。
- **订单状态机** `CREATED → PAID | EXPIRED | CLOSED`；二维码有效期 `PAYMENT_ORDER_TTL_SECONDS`
  （默认 300），过期在轮询时惰性判定，无后台任务。
- **支付成功**：`mark_order_paid()` 用单事务 CAS（`UPDATE … WHERE status='CREATED'`）
  只赢一次 → `credits.grant(kind=purchase, ref=('order', out_trade_no))`；入账又靠账本唯一 ref 兜底。
  两段之间崩溃的极端情况由 `reconcile_paid_orders()` 补（admin `POST /api/admin/orders/reconcile`、
  CLI `reconcile-orders`）。
- **通道**：`qr`（当面付 `alipay.trade.precreate`，沙箱版支付宝 App 扫码）/ `web`（电脑网站支付
  `alipay.trade.page.pay`，桌面浏览器收银台）。本地无公网，不用异步通知，**全靠前端轮询 +
  服务端 `alipay.trade.query`**。
- **离线 mock**：`PAYMENT_MOCK=true`（默认）不连支付宝，`POST /api/payment/dev/simulate-paid/{no}`
  模拟买家付款（仅 mock 挂载）。
- **真实沙盒**：`PAYMENT_MOCK=false` + `ALIPAY_APPID` / `ALIPAY_GATEWAY`（新版
  `https://openapi-sandbox.dl.alipaydev.com/gateway.do`）/ 两把 PEM 放 `keys/`
  （`keys/*.pem` 已 gitignore；沙盒控制台的单行 base64 要补 PEM 头尾）/ `PAY_RETURN_URL`。
  沙箱账号在 https://open.alipay.com/develop/sandbox/app。

### 4.1 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/credits/me` | `{balance, daily_balance, daily_grant, total, spent_total}` |
| GET | `/api/credits/prices` | 价目表 + `signup_bonus` / `daily_grant` |
| GET | `/api/credits/ledger?limit&offset` | 流水（新→旧） |
| GET | `/api/payment/config` | `{mock_pay}`（前端据此选 qr / web 通道） |
| GET | `/api/payment/packs` | 积分包 |
| POST | `/api/payment/orders` | `{pack_id, channel}` → 201 `OrderOut`（qr 返 `qr_code`，web 返 `pay_url`） |
| GET | `/api/payment/orders` | 我的订单 |
| GET | `/api/payment/orders/{no}` | **轮询**：惰性过期 + 查单同步 |
| POST | `/api/payment/orders/{no}/cancel` | 关单；已支付 409 `payment.order_not_cancelable` |
| POST | `/api/payment/dev/simulate-paid/{no}` | 仅 mock |
| GET | `/api/admin/credits?q` / `/api/admin/credits/{user_id}` | 账户列表 / 详情 + 流水 |
| POST | `/api/admin/credits/{user_id}/adjust` / `/api/admin/credits/adjust` | `{delta, note}`（按 id / 按用户名），写审计 `adjust_credits` |
| GET | `/api/admin/orders` / `/api/admin/stats/revenue` | 本地查（不再跨服务） |
| POST | `/api/admin/orders/reconcile` | 对账补入 |

错误码：`credits.insufficient`(402) · `payment.pack_not_found`(404) · `payment.order_not_found`(404) ·
`payment.order_not_cancelable`(409) · `payment.upstream_error`(502)。

## 5. 前端（`frontend/src`）

- `hooks/useCredits.ts`：余额 + 价目表共享缓存（`['credits','me']` / `['credits','prices']`）；
  `price(action, units)`、`canAfford(cost)`、`invalidateCredits()`（出卷 / 讲解 / 批改 / 聊天成功、
  充值成功后调用）。
- `components/CreditsDialog.tsx`：`openCreditsDialog({required, available})` 全局入口 +
  `<CreditsDialogHost/>`（挂在 AppLayout）；`lib/errors.ts` 收到 402 即弹。取代 `UpgradeDialog`。
- `components/CreditHint.tsx`：CTA 旁「≈ N 积分」（价来自价目表，余额不够转橙红）。
- `hooks/useGeneratePaper.ts`：`guard(estimatedCost)` 只做本地预检（能算出价的页面：专项 /
  自选 / 整卷 / 每日 / 主题），一句话出卷不预检交给 402。
- 页面：`/credits`（原 `/membership`，路由重定向）= 余额三格 + 积分包 + 价目 + 流水；
  admin `/admin/credits`（原 `/admin/memberships`）= 账户搜索 / 调整 / 流水；订单页改本地接口。
- 删除：`lib/quota.ts`、`hooks/useMembership.ts`、`MemberPill`、所有 `memberLocked` /
  `ORIGINAL_LOCK_REASON` / `MODE_LOCK_REASONS`、作文批改遮罩、学情报告升级卡、`/payapi` 代理。
- 营销页 `lib/pricing.ts` 改为积分包 / 价目的静态镜像（匿名展示用；改价须同步）。

## 6. 迁移与运维

- `python -m backend.cli migrate-payment-db --src payment/data/payment.db`：把旧独立服务的
  `orders` 原样导入（plan→pack 映射；历史 PAID 订单写 0 积分 `purchase` 占位防对账重发），
  仍在有效期的会员按 **1000 积分 / 30 天** 折算剩余天数入账（`migrate_membership`，按用户幂等）。
  旧库里 `dev-` 前缀的假用户跳过。
- `python -m backend.cli reconcile-orders`：PAID 订单缺 purchase 流水则补入账。
- 环境变量见 `.env.example`「支付 / 积分」段；`.claude/launch.json` / `Caddyfile` 不再有 :8001。

## 7. 不做的事

不做订阅 / 会员并存；不做积分过期（仅每日赠送当日有效）；不做支付宝异步通知（仍轮询）；
不做退款到支付宝；价目数字是起点，全部集中在 `pricing.py` + `CreditsConfig`。
