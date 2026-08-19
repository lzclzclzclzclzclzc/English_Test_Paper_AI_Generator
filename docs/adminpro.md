# Spec H：管理后台增强设计（Admin Pro）

**创建日期**：2026-08-16
**状态**：设计稿，未实现（分支 `feature/adminpro`）
**范围**：Spec G（[`./admin-design.md`](./admin-design.md)）管理后台的功能增强——列表分页与列补全、用户维度深挖（最近试卷/做题记录）、题库只读统计与浏览、收入统计、会员到期预警、管理操作审计日志、系统健康。不改变 Spec G 的权限模型与服务形态。
**依赖**：
- [`./admin-design.md`](./admin-design.md)（Spec G：`/api/admin/*` 结构、`require_admin`、payment 聚合转发——本文全部沿用）
- [`./backend-design.md`](./backend-design.md)（Spec C：`shared/storage`、migration 机制、错误体）
- [`./question-bank-ingestion-design.md`](./question-bank-ingestion-design.md)（题库 `data/questions.db` 的结构：题型/知识点/章节）
- [`../payment/README.md`](../payment/README.md)（`payment.db` 的 orders/memberships）

**现状基线**（已实现，来自 Spec G）：
概览看板（4 指标 + 2 折线图）、用户列表/详情（封禁/解封/重置密码/改角色/学习画像）、
订单列表（状态筛选）、会员管理（按用户名/按行开通、取消）、做题分析
（趋势/薄弱考点/分题型准确率）。后端 17 个端点集中在 `backend/api/admin.py`。

---

## 0. 范围与产出

### 0.1 本 spec 定义

- **A 组·现状补全**：列表分页控件、订单"支付时间"列、用户列表"做题数"列与排序/状态筛选、概览页补指标（总做题数/封禁用户数/累计收入）
- **B 组·用户深挖**：用户详情页"最近试卷"与"最近做题记录"两个列表
- **C 组·题库管理（只读）**：题库统计页（按题型/知识点/章节的数量分布）、题目浏览页（检索 + 分页 + 答案折叠）
- **D 组·运营与系统**：收入统计（按日/按套餐）、会员到期预警（7 天内到期）、管理操作审计日志（新表 + 记录点 + 浏览页）、系统健康状态页（payment/LLM/题库/数据库探活）
- **配套**：`payment_base_url` 配置项（顺带解决 Spec G § 0.2.1 遗留的硬编码问题）

### 0.2 本 spec 不定义（非目标）

- ❌ 退款流程（沿用 Spec G § 0.2）
- ❌ 题库编辑/增删改——`data/questions.db` 保持只读，题目录入只走 ingestion 管道
- ❌ 细粒度多角色（沿用 Spec G，仍只有 user/admin）
- ❌ 公告/站内消息推送系统
- ❌ 用户错题本逐题浏览（数据在 `attempt_items`，首版只在"最近做题记录"里展示对错统计，不做逐题回看）
- ❌ 两库 JOIN——题库统计（C 组）只查 `questions.db`，用户统计只查 `app.db`，与既定架构一致

### 0.3 撤销既有决策

| 原决策 | 本 spec 如何改 |
|---|---|
| Spec G § 0.2：**审计日志 / 操作留痕（首版不做；危险操作靠二次确认）** | 本 spec D3 引入 `admin_audit_logs` 表，记录全部敏感管理操作（改角色/重置密码/封禁/解封/开通/取消会员）。二次确认保留，审计作为事后追溯补充。落地时需在 `admin-design.md` § 0.2 该条加指向本节的备注 |
| Spec G § 0.2.1：**`_payment_base()` 硬编码 `http://localhost:8001`** | 本 spec D4 顺带引入 `shared/config.py` 的 `payment_base_url` 配置项，替换硬编码 |

---

## 1. 功能总览与优先级

| 组 | 功能 | 优先级 | 主要改动面 | 依赖 |
|---|---|---|---|---|
| A1 | 列表分页（用户/订单/会员） | P0 | 前端 | 后端已支持 `limit/offset/total` |
| A2 | 订单"支付时间"列 | P0 | 前端 | `AdminOrderItem.paid_at` 已返回 |
| A3 | 用户列表"做题数"列 + 排序 + 状态筛选 | P0 | 前端 + 后端排序参数 | `AdminUserListItem.attempt_count` 已返回 |
| A4 | 概览页补指标 | P0 | 前端 + 后端补 2 项 | `total_attempts` 已返回 |
| C1 | 题库统计页 | P1 | 后端新端点 + 前端新页 | 只读 `questions.db` |
| C2 | 题目浏览页 | P1 | 后端新端点 + 前端新页 | 只读 `questions.db` |
| B1 | 用户详情·最近试卷 | P1 | 后端新端点 + 前端 | `papers` 表 |
| B2 | 用户详情·最近做题记录 | P1 | 后端新端点 + 前端 | `attempts`/`attempt_items` |
| D1 | 收入统计 | P2 | payment 新端点 + 转发 + 前端 | PAID 订单 |
| D2 | 会员到期预警 | P2 | payment 筛选参数 + 前端 | `expires_at` |
| D3 | 审计日志 | P2 | 新表 + 记录点 + 端点 + 前端 | 撤销 Spec G 非目标 |
| D4 | 系统健康 | P2 | 端点 + 前端 + 配置项 | httpx 探活 |

**落地顺序建议**：A（P0，最快见效）→ C（业务价值最高：题库是本项目核心资产）→ B → D。

---

## 2. A 组：现状补全（P0）

共同点：后端大部分数据已在响应里，只是前端没用；成本最低、见效最快。

### 2.1 A1 分页控件

**现状问题**：`/api/admin/users|orders|memberships` 均支持 `limit/offset` 且 users/memberships 返回 `total`，但三个前端页面均无分页 UI，默认只显示前 50 条，之后的数据不可见。

**设计**：

- 新建通用组件 `frontend/src/components/admin/Pagination.tsx`：`{page, pageSize, total, onChange}`，上一页/下一页 + 页码指示（`第 N / M 页`）；沿用 shadcn 按钮样式，表格底部居中。
- 三个页面接入：page state → `limit=50, offset=(page-1)*50` 传给现有 `listUsers/listOrders/listMemberships`。
- 搜索/筛选条件变化时 `setPage(1)` 重置。
- **后端补一处**：`/api/admin/orders` 当前不返回 `total`（payment 侧转发时丢弃）。payment 的 `/payapi/admin/orders` 增加 `total` 返回（`COUNT` 同条件查询），主后端透传，`AdminOrderListView` 加 `total: int`。

### 2.2 A2 订单"支付时间"列

`AdminOrderItem.paid_at` 已返回（`backend/schemas.py`），`AdminOrdersPage` 表格在"创建时间"后加一列"支付时间"：`paid_at ? 格式化 : '—'`。纯前端。

### 2.3 A3 用户列表增强

- **补列**：表格加"做题数"列（`AdminUserListItem.attempt_count` 已返回，未展示）。
- **排序**：后端 `list_users` 增加 `sort` 参数，取值 `created_at | paper_count | attempt_count`（默认 `created_at DESC`）；`paper_count/attempt_count` 排序在 SQL 里按子查询 COUNT 排序。前端表头可点击切换排序。
- **状态筛选**：`list_users` 增加 `status` 参数（空/`active`/`banned`），`count_users` 同步；前端加下拉（全部/正常/已封禁）。

### 2.4 A4 概览页补指标

指标卡从 4 个扩到 7 个（两行网格）：

| 指标 | 来源 | 改动 |
|---|---|---|
| 总做题数 | `AdminOverview.total_attempts`（后端已返回） | 纯前端 |
| 封禁用户数 | `storage.admin_counts()` 增查 `COUNT(*) WHERE status='banned'` → `AdminOverview.banned_users` | 后端 +1 字段 |
| 累计收入（元） | payment 侧新增（见 D1），overview 转发 PAID 订单 `SUM(amount_cents)` | 后端转发 +1 字段 `total_revenue_cents: int | None`；payment 不可用时 `null`，前端显示"暂不可用"（与 `active_members` 同降级风格） |

---

## 3. B 组：用户维度深挖（P1）

用户详情页目前只有计数（试卷数/做题数/正确率），看不到具体内容。补两个只读列表。

### 3.1 B1 最近试卷

新端点：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/users/{user_id}/papers?limit=10` | 该用户最近生成的试卷列表：`{items: [{id, title, generated_at, question_count}]}` |

- `storage` 新增 `list_user_papers(user_id, limit)`：查 `papers` 表按 `generated_at DESC`；`question_count` 从 `questions_json` 长度或现有 paper 结构取。
- 前端：详情页"学习画像"上方加"最近试卷"卡片（表格：标题/题数/时间），仅展示不做跳转（管理端不进入答题视图）。

### 3.2 B2 最近做题记录

新端点：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/users/{user_id}/attempts?limit=10` | 该用户最近答题记录：`{items: [{attempt_id, paper_title, answered_at, item_total, item_correct, correct_rate}]}` |

- `storage` 新增 `list_user_attempt_summary(user_id, limit)`：`attempts JOIN attempt_items` 聚合每场的题目数/正确数，按 `answered_at DESC`。
- 前端：详情页加"最近做题"卡片（表格：试卷/答题时间/正确率）。
- 复用 `_require_target` 校验用户存在；两卡片加载失败各自降级显示"加载失败 + 重试"，不阻塞页面。

---

## 4. C 组：题库管理·只读（P1）

**动机**：题库（`data/questions.db`）是本系统生成试卷的核心资产，但管理端目前完全看不到它——题量是否充足、哪些知识点缺题，只能查数据库才知道。

**架构约束**：`questions.db` 只读，与 `app.db` 不 JOIN、不写。查询经 `ai_engine/question_repo.py` 现有连接层访问（如需，在其中加只读统计/检索函数），端点仍挂在 `backend/api/admin.py`（`require_admin` 保护）。

### 4.1 C1 题库统计页

路由 `/admin/questionbank`，端点：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/questionbank/stats` | 三组分布：`by_type`（各题型数量）、`by_knowledge_point`（各知识点数量，带 level1/level2 分组）、`by_chapter`（各章节数量） |

- 前端：三张柱状图/条形图（Recharts，沿用做题分析页的图表卡片风格）+ 顶部指标卡（题目总数、题型数、覆盖知识点数）。
- 知识点名称用 `data/kb/knowledge_tree.json` 的中文名（前端已有 `prettifyKp`）。
- **运营价值**：直观暴露"某知识点题量不足"，指导补题（走 ingestion 管道）。

### 4.2 C2 题目浏览页

路由 `/admin/questionbank/questions`，端点：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/questionbank/questions?type=&kp=&chapter=&q=&limit=20&offset=` | 题目检索：`{items: [{question_id, question_type, chapter, knowledge_point_ids, stem_preview}], total}` |

- `q` 对题干（stem）做 `LIKE` 模糊匹配；`stem_preview` 截断前 80 字符。
- 前端：筛选栏（题型下拉/知识点下拉/关键词输入）+ 分页表格（复用 A1 分页组件）。
- **行展开看详情**：点击行展开完整题干 + 选项 + 答案（答案默认折叠，点"显示答案"展开——避免管理员扫屏时误视答案）。可加 `GET .../questions/{question_id}` 单题端点，或列表响应即带完整题干由前端折叠。

---

## 5. D 组：运营与系统（P2）

### 5.1 D1 收入统计

- payment 侧新端点 `GET /payapi/admin/stats/revenue?days=30`：
  - `revenue_by_day`：PAID 订单按 `paid_at` 分日 `SUM(amount_cents)`；
  - `by_plan`：PAID 订单按 `plan_id` 分组（销量 + 金额）。
- 主后端 `GET /api/admin/stats/revenue?days=30` 薄转发（同 orders 模式，转发 cookie）。
- 前端：订单页顶部加"累计收入/近 30 天收入"指标卡 + 按日收入折线图、套餐分布条形图（可折叠区块，不挤占订单表空间）。

### 5.2 D2 会员到期预警

- payment `/payapi/admin/memberships` 增加可选参数 `expiring_within_days=7`（`active=1 AND expires_at BETWEEN now AND now+7d`）。
- 主后端转发透传该参数。
- 前端会员页加筛选 tab：`全部 | 有效 | 7 天内到期`；"7 天内到期"行到期时间列标红，便于运营提前提醒续费。

### 5.3 D3 审计日志

**新表**（`app.db`，经 `_apply_migrations` 机制，migration id 形如 `20260816_001_admin_audit_logs`）：

```sql
CREATE TABLE admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id TEXT NOT NULL,          -- 操作者（管理员）
    action TEXT NOT NULL,                 -- set_role / reset_password / ban / unban / grant_membership / revoke_membership
    target_user_id TEXT,                  -- 被操作用户（均为人对人操作，恒有值）
    detail_json TEXT,                     -- {"role":"admin"} / {"days":30} / {"new_password":"***"}（密码不落明文）
    created_at TEXT NOT NULL
);
CREATE INDEX idx_audit_created ON admin_audit_logs(created_at DESC);
CREATE INDEX idx_audit_actor ON admin_audit_logs(actor_user_id);
```

**记录点**（`backend/api/admin.py` 各写操作端点成功路径后追加一行写入；`storage.record_admin_action(actor_id, action, target_id, detail)`）：

| 端点 | action |
|---|---|
| POST `/users/{id}/role` | `set_role` |
| POST `/users/{id}/reset-password` | `reset_password`（detail 只记 `{"result":"ok"}`） |
| POST `/users/{id}/ban` / `unban` | `ban` / `unban` |
| POST `/memberships/grant`、`/memberships/{id}/grant`、`/memberships/{id}/revoke` | `grant_membership` / `revoke_membership`（记 `{"days":N}`） |

> membership 操作物理执行在 payment 侧，但调用入口在主后端聚合端点——在**主后端转发成功后**记录，无需 payment 回调。

**浏览**：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/audit?actor=&action=&limit=50&offset=` | 日志列表（JOIN users 补 actor/target 用户名），按时间倒序分页 |

前端路由 `/admin/audit`：筛选栏（操作者/动作类型）+ 分页表格（时间/操作者/动作/对象/详情）。detail_json 中的 `days`/`role` 以标签展示。

### 5.4 D4 系统健康

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/system/health` | 各依赖探活：`{payment: ok|down, llm: ok|down, question_bank: {total_questions}, app_db_size_kb}` |

- `payment`：httpx GET `/payapi/health`（payment 侧若无 health 端点则补一个轻量 echo），超时 2s，失败即 `down`（复用 `trust_env=False` 风格）。
- `llm`：对配置的 `LLM_BASE_URL` 发轻量 HEAD/GET 探活（不发真实补全请求，只验证可达 + 鉴权不炸）。
- `question_bank`：`questions.db` 题目总数。
- 前端 `/admin/system` 或概览页可折叠区块：一行状态徽标（正常绿/异常红），点击展开详情。payment 探活结果可同时解释概览页"活跃会员/累计收入"为何显示"暂不可用"。
- **配套配置**：`shared/config.py` 增 `payment_base_url`（默认 `http://localhost:8001`），`admin.py` 的 `_payment_base()` 改读配置——解决 Spec G § 0.2.1 遗留项。

---

## 6. 前端路由与导航汇总

`frontend/src/routes.tsx` 新增（均包 `RequireAdmin`）：

```
/admin/questionbank            → 题库统计（C1）
/admin/questionbank/questions  → 题目浏览（C2）
/admin/audit                   → 审计日志（D3）
```

系统健康（D4）并入概览页折叠区块，不单开路由。`AdminLayout` 侧导航补"题库"与"审计"入口。

---

## 7. 测试策略

遵循 CLAUDE.md：pytest / vitest，Windows 前缀 `PYTHONIOENCODING=utf-8`。

### 7.1 后端（pytest）

- **分页/排序/筛选（A1/A3）**：`list_users` 的 `sort`/`status` 参数 SQL 正确性；orders 转发透传 `total`。
- **新端点守卫**：`/questionbank/*`、`/users/{id}/papers|attempts`、`/audit`、`/system/health` 非 admin 一律 403。
- **B 组**：构造用户 + 试卷 + attempts，断言最近列表的排序与聚合数字。
- **C 组**：对测试题库断言分组计数总和 = 总题数；`q` 模糊匹配、分页 total 正确；确认全程只读（无写连接）。
- **D3**：每个写操作端点成功后 `admin_audit_logs` 恰好多一行且字段正确；重置密码的 detail 不含明文密码；`/audit` 筛选与分页正确。

### 7.2 payment（pytest）

- revenue 分日/分套餐聚合只计 PAID；`expiring_within_days` 边界（恰好 7 天、已过期不含）。
- `/payapi/health` 200。

### 7.3 前端（vitest）

- `Pagination` 组件：页码计算、边界禁用、`onChange` 触发。
- 订单页渲染 `paid_at` 列；概览页 7 指标卡与降级显示（payment 挂 → "暂不可用"）。
- 题库页筛选联动重置分页；审计页动作类型映射展示。

---

## 8. 落地顺序（供实现计划参考）

1. **A 组**（P0）：后端 `list_users` 排序/筛选 + orders `total` → `Pagination` 组件 → 三页接入 → 订单列/用户列/概览指标补全。
2. **C 组**：`question_repo` 只读统计/检索函数 → 两个 questionbank 端点 → 两个前端页 + 路由/导航。
3. **B 组**：`storage` 两个列表函数 → 端点 → 详情页两张卡片。
4. **D 组**：审计日志表 migration → 各写端点埋点 → `/audit` 端点与页面；payment revenue/expiring 参数 → 转发与前端；`payment_base_url` 配置 → `/system/health` → 概览折叠区块。
5. **文档同步**：`admin-design.md` § 0.2 审计日志条目与 § 0.2.1 硬编码条目加"已由 Spec H 撤销/解决"备注。
