# Spec G：管理后台设计

**创建日期**：2026-08-01
**项目根目录**：`C:\Users\I779318\Desktop\CSS\English_Test_Paper_AI_Generator`
**范围**：管理员后台（管理员管理其他用户）——用户列表/详情、统计看板与数据可视化、手动会员管理、用户操作（封禁/重置密码/设为管理员）。不单开服务：主后端加一组 `/api/admin/*` 接口，payment 服务加一组 `/payapi/admin/*` 接口，前端在同一个 React 应用里加 `/admin` 路由。
**依赖**：
- [`./backend-design.md`](./backend-design.md)（Spec C：后端结构、鉴权、`shared/storage`、错误体、CLI）
- [`./frontend-design.md`](./frontend-design.md)（Spec D：前端结构、路由、`api/client`）
- [`./frontend-visual-spec.md`](./frontend-visual-spec.md)（Spec F：「墨卷」视觉规范 —— 管理后台的视觉表现遵循本文）
- [`../payment/README.md`](../payment/README.md)（payment 子系统：订单/会员、`payment.db`、`AuthUser`）
- 本 spec **撤销** Spec C § 12 中"不实现权限系统"这条非目标，见 § 0.3
**引用约定**：本文形如 "Spec C §X"、"Spec F §Y" 指向对应文档章节

---

## 0. 范围与产出

### 0.1 本 spec 定义

- 权限地基：`users` 表 `role`（user/admin）与 `status`（active/banned）两列，走现有 migration 机制
- 后端守卫：`require_admin` 依赖 + `AuthorizationError`（403）；`current_user` 增加封禁检查
- 主后端接口：`/api/admin/users*`（列表/详情/改 role/重置密码/封禁-解封）、`/api/admin/stats/*`（概览/时序）
- payment 接口：payment 侧 `require_admin`；`/payapi/admin/memberships*`（列表/详情/grant/revoke）、`/payapi/admin/orders`；抽出可复用的 `extend_membership`
- CLI：`promote-admin` bootstrap 首个管理员
- 契约变更：`User` 加 `role`；`/api/auth/me` 返回带 `role`
- 前端：`User.role` 类型、`RequireAdmin` 守卫、`/admin` 路由组（概览/用户/会员/订单）、导航按 role 显隐、`api/admin.ts`、Recharts 图表
- 测试策略（后端 pytest、payment pytest、前端 vitest）

### 0.2 本 spec 不定义（非目标）

- ❌ 细粒度多角色（只有 `user` / `admin` 两级；未来若需"客服/只读"再扩 `role` 取值）
- ❌ 密码找回 / 邮箱验证（无邮箱字段，沿用 Spec C）
- ❌ 退款流程（订单只读展示，不实现退款；PAID 订单在 payment 侧本就终态）
- ❌ 审计日志 / 操作留痕（首版不做；危险操作靠二次确认）
- ❌ 管理员为他人生成试卷（Spec C § 16 已排除，本 spec 仍不做）
- ❌ 单独部署的管理服务（明确挂在现有后端，理由见 § 1.2）

### 0.3 撤销既有决策

| 原决策 | 本 spec 如何改 |
|---|---|
| Spec C § 12：**不实现权限系统（用户之间无差异，除资源归属）** | 本 spec 引入 `users.role`（user/admin）+ `require_admin` 守卫 + 管理后台。用户之间自此有权限差异。**需在 Spec C § 12 移除该条**，并在 § 0.3 之类的撤销表登记（照 Spec C 撤销 Spec A/B "无认证" 的先例）。 |

落地时需同步编辑（本 spec 与代码一起改，specs 追踪实现）：
- `docs/backend-design.md` § 12 删去"❌ 不实现权限系统"一条，加一句指向本 Spec G。
- `docs/backend-design.md` 用户体系/端点章节补 `/api/admin/*` 与 `User.role` 字段的指引（或明确"详见 Spec G"）。
- `docs/frontend-design.md` 路由/鉴权章节补 `/admin` 路由与 `RequireAdmin`（或"详见 Spec G"）。

---

## 1. 架构决策

### 1.1 权限模型：数据库 `role` 列（工业标准）

管理员身份存在数据库 `users.role`，而非配置白名单。理由：
- **加减管理员不用重启服务**——白名单在环境变量里，改一次要重启；`role` 列在后台点一下即可。
- **单一权威源**——主后端数据库是唯一真相；payment 服务信任主后端 `/api/auth/me` 返回的 `role`，两边无需各自维护名单。
- **可扩展**——未来加"客服/只读"角色只是多几个 `role` 取值，不改架构。

登录用的是 Spec C 的 **Cookie Session** 机制：`role` 天然跟着 session 走（每次请求经 `current_user` 从数据库读出当前用户，含 `role`），无需额外传递或签发。

### 1.2 服务形态：不单开管理服务

管理接口挂在**现有主后端**（`/api/admin/*`，端口 8000）与**现有 payment 服务**（`/payapi/admin/*`，端口 8001），前端在同一个 React 应用加 `/admin` 路由。

**为什么不单开一个管理服务**：单开会重复一套认证、被迫跨服务远程读主后端数据、多一个进程要部署维护；而隔离收益在本项目规模下用不上。工业界只有在"管理后台需内网物理隔离 / 功能庞大到需独立团队与发布节奏 / 用完全不同技术栈"时才单开——本项目远未到此门槛。

**为什么会员走 payment 侧新接口**：会员/订单数据本就在 payment 的 `payment.db`（独立服务，涉及支付宝密钥的安全边界，是既有的、正当的服务拆分）。管理员改会员这个动作因此走 payment 新增的 admin 接口，不是为了单开管理服务。

### 1.3 安全原则

- **后端守卫是唯一防线**：每个 `/api/admin/*` 与 `/payapi/admin/*` 都挂 `require_admin`，逐请求校验 `role`。
- **前端只负责显隐**：`/admin` 路由与导航入口按 `role` 显隐，纯体验层。非管理员即使手敲 `/admin` 硬闯，任何操作都会被后端 403 拦下。
- **危险操作二次确认**：封禁、重置密码、改 role、取消会员，前端统一走确认弹窗。
- **防自锁**：管理员不能改自己的 role、不能封自己。

---

## 2. 数据模型变更

两列都通过 `shared/storage.py` 现有的 `_apply_migrations` 清单机制增量添加（幂等：`schema_migrations` 记录已应用的 migration id）。老数据自动取默认值。

### 2.1 `users.role`

```sql
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'
```
- 取值：`user` / `admin`。
- migration id 形如 `add_users_role`。

### 2.2 `users.status`

```sql
ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
```
- 取值：`active` / `banned`。
- migration id 形如 `add_users_status`。

### 2.3 契约（`backend/schemas.py` 的 `User` / `UserRecord`）

```python
class User(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"] = "user"
    status: Literal["active", "banned"] = "active"
```
- `UserRecord(User)` 仍额外携带 `password_hash`（内部）。
- `storage.create_user` / `get_user_by_id` / `get_user_by_username` / `_row_to_user_record` 一并带上 `role` / `status`。
- 属跨边界契约变更，按 CLAUDE.md 约定同步各 spec。

### 2.4 会员数据（不变）

payment 的 `memberships` 表**不加 tier**（沿用现状：买任何套餐只顺延一个 `expires_at`，`active` 由 `expires_at > now` 派生）。管理员手动开通同样只顺延 `expires_at`。

---

## 3. 后端守卫与错误（`backend/`）

### 3.1 `AuthorizationError`（`backend/errors.py`）

新增（目前无 403 类）：
```python
class AuthorizationError(BackendError):
    error_code = "auth.forbidden"
    http_status = 403
    message = "无权访问"
```

### 3.2 `current_user` 增加封禁检查（`backend/deps.py`）

在解析出用户后追加：`status == "banned"` → 抛 `AuthorizationError`。这样封禁用户即便持有有效 session 也无法访问任何受保护接口。

### 3.3 `require_admin` 依赖（`backend/deps.py`）

```python
async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise AuthorizationError()
    return user
```
所有 `/api/admin/*` 端点以 `user: User = Depends(require_admin)` 保护。

---

## 4. 主后端接口（`backend/api/admin.py`）

新建 `backend/api/admin.py`，在 `backend/main.py` 注册（前缀 `/api/admin`，tag `admin`）。全部挂 `require_admin`。

### 4.1 用户管理

| 方法 | 路径 | 作用 | 关键行为 |
|---|---|---|---|
| GET | `/api/admin/users?q=&limit=&offset=` | 用户列表 | 按用户名模糊搜索 `q`；分页；返回 id/username/created_at/role/status + 试卷数 + 做题数（attempts 计数） |
| GET | `/api/admin/users/{user_id}` | 用户详情 | 基础信息 + 试卷数 + 做题正确率 + 掌握度概览（复用 `build_mastery_profile`）+ 会员到期（拼装自 payment，见 § 5.4） |
| POST | `/api/admin/users/{user_id}/role` | 改 role | body `{"role":"admin"\|"user"}`；**禁止改自己**（`user_id == 当前 admin.id` → 400/403）；改为 `user` 时是"取消管理员" |
| POST | `/api/admin/users/{user_id}/reset-password` | 重置密码 | body `{"new_password":...}`（复用 `UserCredentials` 的 password 校验规则）；`hash_password` 重新哈希写入；**清除该用户所有 session**（强制重登） |
| POST | `/api/admin/users/{user_id}/ban` | 封禁 | `status='banned'` + 删除该用户所有 session；**禁止封自己** |
| POST | `/api/admin/users/{user_id}/unban` | 解封 | `status='active'` |

对应新增 `storage` 辅助：`list_users(q, limit, offset)`、`count_users(q)`、`get_user_admin_detail(user_id)`（或组合现有查询）、`set_user_role`、`set_user_status`、`update_password_hash`、`delete_sessions_by_user(user_id)`。

### 4.2 统计看板

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/admin/stats/overview` | 聚合：`total_users`、`new_users_today`、`active_members`（需向 payment 查，见 § 5.4）、`total_papers`、`total_attempts` |
| GET | `/api/admin/stats/timeseries?days=30` | 每日序列：`users_by_day`（按 `users.created_at`）、`papers_by_day`（按 `papers.generated_at`），供前端画折线图 |

`active_members` 若 payment 不可用则返回 `null`，前端显示"暂不可用"，不阻塞其余指标。

### 4.3 whoami

不新增 whoami 接口。`/api/auth/me` 已带 `role`（§ 2.3），前端据此判断是否 admin。

---

## 5. payment 接口（`payment/app/admin_routes.py`）

新建 `payment/app/admin_routes.py`，在 `payment/app/main.py` 注册（前缀 `/payapi/admin`）。全部挂 payment 侧 `require_admin`。

### 5.1 payment 侧 `require_admin`

payment 的 `AuthUser` 已携带 `username`；扩展为携带 `role`：`get_current_user` 从主后端 `/api/auth/me` 的返回里读 `role`（§ 2.3 已保证 `/me` 带 role），填入 `AuthUser`。新增依赖：
```python
async def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if getattr(user, "role", "user") != "admin":
        raise PaymentError(403, "auth.forbidden", "无权访问")
    return user
```
> 本地联调的 `PAYMENT_DEV_FAKE_USER` 分支需相应给假用户一个 role（可由新环境变量控制，默认 `user`），以便在无主后端时也能测 admin 路径。

### 5.2 端点

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/payapi/admin/memberships?q=&limit=&offset=` | 会员列表（user_id、expires_at、active 派生） |
| GET | `/payapi/admin/memberships/{user_id}` | 单用户会员详情 |
| POST | `/payapi/admin/memberships/{user_id}/grant` | 手动开通/延长：body `{"days": 30}` 或 `{"plan_id":"monthly"}`（映射到套餐天数） |
| POST | `/payapi/admin/memberships/{user_id}/revoke` | 取消会员：`expires_at` 设为当前时刻（即刻失效） |
| GET | `/payapi/admin/orders?status=&limit=&offset=` | 订单列表（只读，便于对账/排查） |

### 5.3 复用 `extend_membership`

把 `service.mark_order_paid` 里的会员顺延逻辑抽成可复用函数：
```python
def extend_membership(conn, user_id: str, days: int, now) -> str:
    # base = max(当前 expires_at, now)；new = base + days；UPSERT memberships
```
`mark_order_paid`（支付成功）与 admin `grant`（手动开通）都调用它，保证行为一致：`base = max(当前到期, now) + N 天`。幂等性由 `mark_order_paid` 的 CAS（CREATED→PAID 只成功一次）继续保证——重复支付通知不重复加时长；admin `grant` 是显式操作，按传入 days 直接顺延。

### 5.4 主后端 → payment 的跨服务拼装

主后端 `/api/admin/users/{id}` 与 `/api/admin/stats/overview` 需要会员信息：
- 主后端内部以 httpx 调用 payment 的 `/payapi/admin/memberships/{id}`（或列表），**转发当前 admin 的 session cookie**（payment 侧 `require_admin` 会据此校验调用者也是 admin）。
- payment 不可用时：详情页会员字段返回 `null`/"暂不可用"，`active_members` 返回 `null`，均不阻塞主流程（沿用 payment 既有的"上游不可用"降级风格）。

---

## 6. CLI：bootstrap 首个管理员（`backend/cli.py`）

数据库初始所有人都是 `user`。用命令行提升首个管理员（此时后台还没有 admin 能在界面里操作）：
```bash
python -m backend.cli promote-admin --username okarin
```
- 新增子命令 `promote-admin`，参数 `--username`；调用 `storage.set_user_role(user_id, "admin")`（先按 username 查 id）。
- 用户不存在时返回非 0 并打印提示。
- 之后该管理员登录后台，即可在界面里提升/取消其他人的 role（§ 4.1）。

---

## 7. 前端（`frontend/`，同应用 `/admin` 路由）

### 7.1 类型与鉴权信号

- `frontend/src/types/api.ts` 的 `User` 加 `role: 'user' | 'admin'`（以及 `status` 若前端需展示）。
- `getMe` 返回自动带上；`useAuth()` 的 `data` 即含 `role`。
- 便捷判断：`const isAdmin = user?.role === 'admin'`。

### 7.2 `RequireAdmin` 守卫（新组件）

套在 `RequireAuth` 之内：
```
RequireAuth（已登录?）
  └─ RequireAdmin（role === 'admin'?）
       ├─ 是 → 渲染 /admin/* 页面
       └─ 否 → <Navigate to="/" replace/>
```
`isLoading` 时显示骨架（复用 `RequireAuth` 的加载态风格）。

### 7.3 路由（`frontend/src/routes.tsx`）

在受保护块内加一组（可用嵌套布局路由承载左侧子导航）：
```
/admin             → 概览看板（默认）
/admin/users       → 用户列表
/admin/users/:id   → 用户详情
/admin/memberships → 会员管理
/admin/orders      → 订单列表
```
每个 `/admin/*` 元素外层包 `RequireAdmin`。

### 7.4 导航入口（`frontend/src/components/AppNav.tsx`）

仅当 `isAdmin` 时渲染"管理后台"入口；普通用户看不到。

### 7.5 页面（遵循 Spec F「墨卷」视觉规范）

- **后台布局**：沿用 `AppLayout` 整体框架；`/admin` 下用**左侧竖向子导航 + 右侧内容区**。卡片/表格/按钮沿用 shadcn + 现有设计 token（`bg-sheet` / `border-line` / `ink-wash`，6px 圆角，衬线页头 `font-serif`）。表格样式对齐 MembershipPage/PapersPage 现有模式（`rounded-md border border-line bg-sheet`，表头 `bg-ink-wash/60`，`text-[13px]`）。
- **概览看板**：一排指标卡（总用户/今日新增/活跃会员/试卷总数）+ 两张折线图（每日新增用户、每日生成试卷）。**遵守 PRODUCT.md 禁令**——不做"黑底霓虹、密集指标"的冷监控风；用墨卷暖白纸面 + 藏青（`--ink`）线条，图表克制留白。
- **用户列表**：搜索框 + 分页表格（用户名/注册时间/role/status/试卷数）；行内操作（详情/封禁·解封/重置密码/设为管理员·取消）。危险操作走二次确认弹窗（复用现有 `components/ui/dialog`）。
- **用户详情**：基础信息 + 做题正确率/掌握度概览 + 会员到期（拼装自 payment）+ 操作区。
- **会员管理**：会员列表 + "手动开通 N 天 / 取消"（带确认）。
- **订单列表**：只读表格，按状态筛选。

### 7.6 API 客户端（`frontend/src/api/admin.ts`）

- 复用 `api/client.ts` 的 `apiFetch`（→`/api`）和 `payFetch`（→`/payapi`）：用户/统计走 `apiFetch`，会员/订单走 `payFetch`。
- 403（`auth.forbidden`）统一提示"无权访问"。
- 列表接口用 TanStack Query；变更接口用 mutation + 成功后失效相关 query。

### 7.7 图表库

引入 **Recharts**（React 生态主流、shadcn 图表文档采用），按需只用折线图组件。加入 `frontend/package.json` 依赖。

---

## 8. 测试策略

遵循 CLAUDE.md：pytest 运行，Windows 前缀 `PYTHONIOENCODING=utf-8`，不 `python <file>.py`。

### 8.1 后端（pytest）

- **migration 幂等**：`init_db` 跑两次不炸；老用户默认 `role='user'` / `status='active'`。
- **守卫**：`require_admin` —— 普通用户 403、管理员放行、未登录 401；`current_user` —— banned 用户持有效 session 仍 403。
- **用户操作**：改 role（禁改自己）、重置密码后能用新密码登录且旧 session 被清、封禁后该用户请求 403 且 session 清空、解封恢复。
- **统计**：构造若干用户/试卷/attempt，断言 overview 计数与 timeseries 分桶正确。

### 8.2 payment（pytest）

- **admin 守卫**：`/payapi/admin/*` 非 admin 403（用 `PAYMENT_DEV_FAKE_USER` + role 环境变量构造 admin/非 admin）。
- **`extend_membership`**：抽取后 `mark_order_paid` 与手动 `grant` 都走它，`max(当前到期, now)+N 天` 结果一致；`mark_order_paid` 幂等（重复 CREATED→PAID 只加一次）。
- **grant/revoke**：grant 顺延、revoke 即刻失效（`active` 派生为 false）。

### 8.3 前端（vitest）

- `RequireAdmin`：admin 放行 / 非 admin 重定向到 `/`。
- 导航入口按 `role` 显隐。
- `api/admin.ts` 的 base URL 分流（用户/统计→`/api`，会员/订单→`/payapi`）与 403 提示。

---

## 9. 落地顺序（供实现计划参考）

1. **地基**：migration（role/status）→ `User` 契约 → `storage` 读写带字段 → `/api/auth/me` 带 role。
2. **守卫**：`AuthorizationError` → `current_user` 封禁检查 → `require_admin`。
3. **CLI**：`promote-admin`（有了它才能造出第一个 admin 跑后续测试）。
4. **主后端接口**：users* → stats*（含 storage 辅助）。
5. **payment**：`AuthUser` 带 role → payment `require_admin` → 抽 `extend_membership` → admin_routes（memberships*/orders）。
6. **跨服务拼装**：主后端详情/overview 调 payment。
7. **前端**：类型 → `RequireAdmin` → 路由 → 导航显隐 → `api/admin.ts` → 各页面 → Recharts 图表。
8. **测试**：三处测试补齐。
9. **文档同步**：撤销 Spec C § 12、交叉引用（§ 0.3）。
