# Spec C：FastAPI 后端设计

**创建日期**：2026-07-07
**项目根目录**：`C:\Users\I779318\Desktop\CSS\English_Test_Paper_AI_Generator`
**范围**：FastAPI 后端子系统（`backend/`）—— 用 HTTP 把 AI Engine + 题库封装成前端可用的接口；含鉴权、试卷持久化、答题记录、判对错
**依赖**：
- [`./question-bank-ingestion-design.md`](./question-bank-ingestion-design.md)（Spec A：数据契约、SQLite、`shared/`）
- [`./ai-engine-design.md`](./ai-engine-design.md)（Spec B：AI Engine 五个公开函数）
- 本 spec 撤销 Spec A/B 中两条决策，见 § 0.3
**引用约定**：本文形如 "Spec A §X"、"Spec B §Y" 指向对应文档章节

---

## 0. 范围与产出

### 0.1 本 spec 定义

- FastAPI 后端 (`backend/`) 项目结构与依赖
- 完整的 HTTP 端点契约（鉴权、试卷生成/修改、答题上报/判对错、掌握度、单题解析）
- 试卷持久化（新增 `papers` 表）
- 用户体系（用户名+密码+bcrypt+Cookie Session）
- 全局错误处理（统一错误体 + `error_code`）
- CORS 与静态文件代理（部署形态 C：开发分开、部署合并）
- 后端 CLI 与开发调试
- 后端集成测试策略（本 spec 定义，跨系统 e2e 在 Spec E）

### 0.2 本 spec 不定义

- 前端（见 Spec D）
- 跨子系统测试策略（e2e / CI 编排，见 Spec E）
- AI Engine 内部逻辑（见 Spec B）
- 题库入库流程（见 Spec A）

### 0.3 对 Spec A/B 决策的撤销

**本 spec 撤销以下两条 Spec A/B 中的决策**，在里程碑 M5 完成后需一次性同步更新 Spec A/B 文本（见 § 14）：

| Spec 原决策 | 本 spec 撤销后 |
|---|---|
| Spec A § 9 / Spec B § 15：**不实现用户注册/登录/鉴权** | 本 spec 实现"用户名+密码+bcrypt+Cookie Session"最小鉴权体系 |
| Spec A § 1.6 / Spec B § 1.2 / § 15：**不实现试卷持久化** | 本 spec 新增 `papers` 表，后端持久化每次生成的试卷（AI Engine 内部依然无状态） |

**关键澄清**：**AI Engine 的无状态原则不变**。持久化的责任在**后端层**——FastAPI 拿到 AI Engine 返回的 `Paper` 后写库；`revise_paper` 时后端从库读出完整 `Paper` 喂给 AI Engine。边界依然清晰：**AI Engine 是纯函数，后端负责持久化**。

---

## 1. 整体架构与请求生命周期

### 1.1 部署形态（C：开发分开 + 部署合并）

**开发期**：
```
[浏览器 http://localhost:5173]
     │
     │  /api/*  → 相对路径请求
     ▼
[Vite dev server :5173]  ─(proxy /api/*)→  [FastAPI :8000]
     │                                          │
     │  静态资源 / HMR                          │  API + 数据库
     ▼                                          ▼
  React 源码热更新                          SQLite + ChromaDB
```

Vite 的 `vite.config.ts` 配 `server.proxy = { "/api": "http://localhost:8000" }`。前端所有请求都写 `/api/xxx` 相对路径。

**部署期**：
```
npm run build → dist/  ─mount─►  [FastAPI :8000]
                                     │  /            → StaticFiles(dist/)
                                     │  /api/*       → API 路由
                                     │  /assets/*    → dist/assets/*
                                     │
                                     ▼
                                浏览器一次访问
```

FastAPI 用 `StaticFiles(directory="dist", html=True)` 挂载在 `/`，`/api/*` 是 API 路由（前缀优先）。前端代码零改动。

### 1.2 请求生命周期

以"生成试卷"为例：

```
浏览器
   │  POST /api/papers/generate  { user_query: "...", mode: "fresh" }  + Cookie: session_id=...
   ▼
FastAPI 依赖注入链
   │  ↳ 依赖 1：从 cookie 解 session → current_user (User pydantic)
   │  ↳ 依赖 2：从请求 body 解析 → GeneratePaperRequest (pydantic)
   ▼
路由处理器（backend/api/papers.py::generate_paper_endpoint）
   │  ↳ 调 ai_engine.generate_paper(user_query, mode, user_id=current_user.id, ...)
   │       → Paper 对象
   │  ↳ 调 backend/services/paper_store.py::save(paper, user_id) → paper 写入 SQLite
   ▼
FastAPI 序列化
   │  ↳ 返回 Paper（pydantic 模型，Spec A § 2.3）自动序列化为 JSON
   ▼
浏览器（前端 TanStack Query 缓存 Paper 到内存）
```

**关键设计**：
- **AI Engine 完全无感知 HTTP**——后端处理器只做"参数装配 + 调 AI Engine + 持久化 + 返回"
- **Pydantic 模型直接双向序列化**——因数据契约用 pydantic 定义（Spec A § 2），FastAPI 天然支持
- **持久化在 AI Engine 返回之后**——保持 AI Engine 无状态

### 1.3 目录结构

```
backend/
├── __init__.py
├── main.py                     # FastAPI app 入口 + StaticFiles 挂载
├── config.py                   # backend 特有配置（session_secret 等），复用 shared/config.py
├── deps.py                     # 依赖注入：DB session、current_user、rate limit hooks
├── errors.py                   # 统一错误体 + 异常处理器
├── auth/
│   ├── __init__.py
│   ├── models.py               # User pydantic 模型
│   ├── password.py             # bcrypt 封装
│   ├── session.py              # session_id 生成、cookie 处理、SessionStore
│   └── routes.py               # /auth/register /auth/login /auth/logout /auth/me
├── api/
│   ├── __init__.py
│   ├── papers.py               # /papers/generate /papers/revise /papers/{id} /papers
│   ├── solutions.py            # /solutions
│   ├── attempts.py             # /attempts
│   └── mastery.py              # /users/me/mastery
├── services/
│   ├── __init__.py
│   ├── paper_store.py          # papers 表 CRUD
│   ├── attempt_store.py        # attempts / attempt_items 写入 + 判对错
│   ├── user_store.py           # users 表 CRUD
│   └── grading.py              # 规范化字符串比较（无 LLM）
├── static/                     # 部署时软链接或复制 frontend/dist；开发时空
└── cli.py                      # 开发调试命令（启动、创建管理员、初始化 DB）
```

`shared/` 保持不变（Spec A § 5），新增 `shared/schemas.py` 内的 `User`、`Session`、`GeneratePaperRequest` 等契约类型（下节详述）。

### 1.4 与 AI Engine / 题库的依赖方向

```
frontend/  ──HTTP──►  backend/  ──function call──►  ai_engine/  ──►  shared/
                          │                              │
                          └──────────►  shared/  ◄───────┘
                                  (storage, schemas, config, llm)
```

- 后端**只调 AI Engine 的 5 个公开函数**（Spec B § 12.4）+ `shared/storage.py` 的读写方法
- 后端**不直接调 LLM**——生成解析类逻辑都走 AI Engine
- 后端**不提供独立的判对错 HTTP 端点**——判对错逻辑只在 `POST /api/attempts` 内部执行；`backend/services/grading.py` 是内部函数
- 后端**是新增子系统**，不修改 `ai_engine/` 或 `ingestion/`（除撤销的两条决策带来的字段/表新增）

---

## 2. 共享契约扩展（`shared/schemas.py` 新增）

以下类型追加到 Spec A § 2 的契约中：

### 2.1 用户

```python
class User(BaseModel):
    id: str                          # UUID hex
    username: str                    # 3-32 字符，字母数字下划线
    created_at: datetime

class UserCredentials(BaseModel):
    """注册/登录用；密码明文只在请求瞬时存在，绝不入库。"""
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)

class Session(BaseModel):
    """`storage.get_session` 返回类型；不对前端暴露。"""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
```

### 2.2 后端请求体

```python
class GeneratePaperRequest(BaseModel):
    """POST /api/papers/generate 的 body。"""
    user_query: str = Field(min_length=1, max_length=2000)
    mode: Literal["fresh", "remediation", "review"] = "fresh"
    wrong_items: list[WrongItemRef] | None = None       # remediation 时可选
    review_window_days: int | None = None                # review 时可选
    # 无 revision_intensity：由 LLM 从 user_query 推断（见 Spec B § 3.4）
    # 无 user_id：由后端从 session 注入

class RevisePaperRequest(BaseModel):
    """POST /api/papers/revise 的 body。"""
    paper_id: str                                        # 从库读取 current_paper
    user_instruction: str = Field(min_length=1, max_length=2000)

class SolutionRequest(BaseModel):
    """POST /api/solutions 的 body。"""
    # 前端持有整个 PaperItem，把 question + 溯源信息发过来
    question: RevisedQuestion
    source_question_id: str
    revision_mode: Literal["fresh", "light", "original"]

class GradeSubmissionRequest(BaseModel):
    """POST /api/attempts 的 body：前端提交一份完整答题。"""
    paper_id: str
    items: list[GradeSubmissionItem]
    # user_id 由后端从 session 注入
    # answered_at 由后端 datetime.now() 生成

class GradeSubmissionItem(BaseModel):
    """答题记录 + 用户答案（后端判对错后落库）。"""
    index: int                                           # 对应 PaperItem.index
    user_answer: str | list[str] | dict[str, str]        # 单空字符串、多空顺序数组或 blankN 字典
```

### 2.3 后端响应体

```python
class GradeSubmissionResponse(BaseModel):
    """/api/attempts 返回：整份判分结果。"""
    attempt_id: str
    items: list[GradeResultItem]

class GradeResultItem(BaseModel):
    index: int
    user_answer: str | list[str] | dict[str, str]
    correct_answer: str | list[dict[str, list[str]]]    # 对齐题库 answer_json
    is_correct: bool

class SolutionResponse(BaseModel):
    solution: str

class PaperListResponse(BaseModel):
    """GET /api/papers 返回：当前用户历史试卷列表（不含题面，避免响应过大）。"""
    items: list[PaperListItem]

class PaperListItem(BaseModel):
    paper_id: str
    title: str
    generated_at: datetime
    total_questions: int
    total_score: int
    submitted: bool                                     # 是否已提交答题
```

### 2.4 统一错误体

```python
class ErrorResponse(BaseModel):
    error_code: str                    # 稳定的机器可读代码，见 § 6.2
    message: str                       # 中文人类可读消息（面向终端用户）
    detail: dict[str, Any] | None = None  # 可选调试字段（生产环境可关闭）
    trace_id: str                      # UUID，便于查后端日志
```

---

## 3. 数据库扩展

### 3.1 新增表（追加到 Spec A § 3.7 的 SQL）

```sql
-- 用户
CREATE TABLE users (
    id            TEXT PRIMARY KEY,     -- UUID hex
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,        -- bcrypt hash（含 salt 与 cost）
    created_at    TIMESTAMP NOT NULL
);
CREATE INDEX idx_users_username ON users(username);

-- 会话（简单实现；未来若换 JWT 可弃）
CREATE TABLE sessions (
    session_id  TEXT PRIMARY KEY,       -- 密码学安全随机 32 字节 hex
    user_id     TEXT NOT NULL REFERENCES users(id),
    created_at  TIMESTAMP NOT NULL,
    expires_at  TIMESTAMP NOT NULL      -- 默认 30 天，滑动过期见 § 4.3
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- 试卷持久化
CREATE TABLE papers (
    paper_id     TEXT PRIMARY KEY,      -- AI Engine 生成的 UUID hex（沿用 Paper.paper_id）
    user_id      TEXT NOT NULL REFERENCES users(id),
    title        TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    payload_json TEXT NOT NULL,         -- 完整 Paper 序列化（含 request, items, metadata 等）
    submitted    INTEGER NOT NULL DEFAULT 0,  -- 0/1；是否已提交答题
    submitted_at TIMESTAMP                     -- 提交时间；未提交为 NULL
);
CREATE INDEX idx_papers_user ON papers(user_id);
CREATE INDEX idx_papers_generated ON papers(generated_at);

-- 轻量迁移记录
CREATE TABLE schema_migrations (
    id         TEXT PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL
);
```

**关于 `papers.payload_json`**：整个 `Paper` 对象直接 JSON 序列化存一个 TEXT 字段。理由：
- `Paper` 是复合嵌套结构（items → RevisedQuestion → options 等），拆表工作量大且没有查询需求（前端只按 `paper_id` 单点读）
- SQLite 的 TEXT 无长度限制，一份中考试卷预计 5-50 KB
- 未来若真需要按题内容检索历史，仍可现建 view / 关联表

**幂等性**：`paper_id` 由 AI Engine 生成的 UUID hex；理论上冲突概率为 0，无需额外去重。

**迁移约定**：后端使用 `schema_migrations` 表记录已应用迁移；所有后续 schema 演进必须进入 `shared/storage.py` 的有序迁移列表，不能只散落在 `CREATE TABLE IF NOT EXISTS` 或临时修补逻辑中。

### 3.2 `attempts` 表的补充索引

对 Spec A § 3.7 的 `attempts` 表添加：

```sql
CREATE INDEX idx_att_paper ON attempts(paper_id);   -- 判断"这份试卷是否已提交过"
```

**决策**：一份 paper 允许被同一用户提交多次（比如"再做一遍"）。`papers.submitted` 只标记"至少提交过一次"，`attempts` 表记完整历史。查询"这份试卷做过几遍"通过 `SELECT COUNT(*) FROM attempts WHERE paper_id = ?`。

### 3.3 `shared/storage.py` 需要新增的方法

```python
# 用户
def create_user(username: str, password_hash: str) -> User: ...
def get_user_by_username(username: str) -> User | None: ...
def get_user_by_id(user_id: str) -> User | None: ...

# 会话
def create_session(user_id: str, ttl_days: int = 30) -> str: ...   # 返回 session_id
def get_session(session_id: str) -> Session | None: ...            # 顺便惰性清理过期
def delete_session(session_id: str) -> None: ...
def slide_session(session_id: str, ttl_days: int = 30) -> None: ... # 每次活动延期

# 试卷
def save_paper(paper: Paper, user_id: str) -> None: ...
def get_paper(paper_id: str, user_id: str) -> Paper | None: ...    # user_id 用于权限校验
def list_papers(user_id: str, limit: int = 100, offset: int = 0) -> list[PaperListItem]: ...
def mark_paper_submitted(paper_id: str) -> None: ...

# 答题（后端 spec 补齐 Spec A § 3.10 的方法）
def write_attempt(attempt: Attempt) -> str: ...                    # 返回 attempt_id

# 题库读取（真实 SQLite 题库由 Spec A 产出）
def list_knowledge_points() -> list[KnowledgePoint]: ...
def get_question(question_id: str) -> Question | None: ...
def list_questions(
    question_type: str | None = None,
    knowledge_point_ids: list[str] | None = None,
    chapter_l2: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Question]: ...
def write_question_solution(question_id: str, solution: str) -> bool: ...
```

所有函数在 `shared/storage.py`——**存储层依然统一在 shared，两个子系统共用**。

---

## 4. 鉴权（`backend/auth/`）

### 4.1 密码存储

**bcrypt** 通过 `passlib` 库。cost factor 默认 12（在现代 CPU 上约 0.3 秒/次，符合 OWASP 建议）。

```python
# backend/auth/password.py
from passlib.hash import bcrypt

def hash_password(plaintext: str) -> str:
    return bcrypt.using(rounds=12).hash(plaintext)

def verify_password(plaintext: str, hashed: str) -> bool:
    return bcrypt.verify(plaintext, hashed)
```

### 4.2 Session 存储

Session 存 SQLite（§ 3.1 的 `sessions` 表）。**不使用第三方 session middleware**（如 `starlette-session`）——SQLite 存 session 简单直观、和其他表在一起、备份统一。

**session_id 生成**：`secrets.token_hex(32)` → 64 字符 hex，密码学安全。

**cookie 配置**：
```python
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,       # JS 不可读，防 XSS
    samesite="lax",      # 防 CSRF；表单提交也允许
    secure=False,        # 开发时；生产改 True（HTTPS）
    max_age=30 * 24 * 3600,  # 30 天
    path="/",
)
```

**生产开关**：`secure=True` / `samesite="strict"` 由 `AppConfig.env == "production"` 决定。

### 4.3 Session 过期与滑动

- **TTL**：30 天，写入 `sessions.expires_at`
- **滑动**：每次通过 session 认证成功后，把 `expires_at` 延期到 `now + 30 天`（更新一行 SQL，成本可忽略）
- **过期清理**：`get_session` 里检查 `expires_at < now` → 删除该行并返回 None；无需后台任务

### 4.4 依赖注入 `current_user`

```python
# backend/deps.py

async def current_user(
    session_id: str | None = Cookie(default=None, alias="session_id"),
) -> User:
    if not session_id:
        raise AuthenticationError("no session")
    session = storage.get_session(session_id)
    if not session:
        raise AuthenticationError("session invalid or expired")
    user = storage.get_user_by_id(session.user_id)
    if not user:
        # 极端情况：会话尚在但用户已删；作为异常处理
        storage.delete_session(session_id)
        raise AuthenticationError("user gone")
    storage.slide_session(session_id)   # 滑动过期
    return user
```

**所有受保护路由**通过 `user: User = Depends(current_user)` 拿到当前用户。**未通过 = 401 响应**（见 § 6）。

### 4.5 路由

```
POST /api/auth/register      body: UserCredentials         → User + 自动登录
POST /api/auth/login         body: UserCredentials         → User + 设置 cookie
POST /api/auth/logout                                       → 204 + 清 cookie + 删 session
GET  /api/auth/me                                           → User（当前登录用户）
```

**注册流程**：
1. 校验 `username` pattern / `password` 长度（pydantic 已做）
2. `get_user_by_username` 查重 → 冲突 409
3. `hash_password` → `create_user`
4. `create_session` → 设 cookie
5. 返回 `User`

**登录流程**：
1. `get_user_by_username` → 无则 401（**不区分"用户不存在"与"密码错"**，防用户名枚举）
2. `verify_password` → 失败 401
3. `create_session` → 设 cookie
4. 返回 `User`

### 4.6 免鉴权路由

只有以下路由不需要 `current_user` 依赖：

- `POST /api/auth/register`
- `POST /api/auth/login`
- 所有 `/`、`/assets/*` 静态文件路径
- OpenAPI 文档：`/docs`、`/openapi.json`

其他所有 `/api/*` 路由都强制鉴权。

---

## 5. HTTP 端点契约

### 5.1 总览

| Method | Path | 请求体 | 响应体 | 简述 |
|---|---|---|---|---|
| POST | `/api/auth/register` | `UserCredentials` | `User` | 注册并自动登录 |
| POST | `/api/auth/login` | `UserCredentials` | `User` | 登录 |
| POST | `/api/auth/logout` | — | 204 | 登出 |
| GET | `/api/auth/me` | — | `User` | 当前用户 |
| POST | `/api/papers/generate` | `GeneratePaperRequest` | `Paper` | 生成试卷（三 mode） |
| POST | `/api/papers/revise` | `RevisePaperRequest` | `Paper` | Review 迭代 |
| GET | `/api/papers/{paper_id}` | — | `Paper` | 读单份试卷 |
| GET | `/api/papers` | — | `PaperListResponse` | 历史试卷列表 |
| POST | `/api/solutions` | `SolutionRequest` | `SolutionResponse` | 单题按需解析 |
| POST | `/api/attempts` | `GradeSubmissionRequest` | `GradeSubmissionResponse` | 提交答题 + 判对错 + 写库 |
| GET | `/api/users/me/mastery` | — | `MasteryProfile` | 掌握度画像 |

### 5.2 关键端点细节

#### `POST /api/papers/generate`

```
Body:
  {
    "user_query": "来 10 道现在完成时的单选，中等难度",
    "mode": "fresh"
  }

内部：
  1. 依赖注入 → current_user
  2. 从 body 解 GeneratePaperRequest
  3. 调 ai_engine.generate_paper(
         user_query=body.user_query,
         mode=body.mode,
         wrong_items=body.wrong_items,
         user_id=current_user.id,
         review_window_days=body.review_window_days,
     ) → Paper
  4. storage.save_paper(paper, current_user.id)
  5. return paper

响应：
  200 OK Paper JSON
```

`revision_intensity` **不在请求体里**——由 AI Engine 内的 Parser 从 `user_query` 推断（Spec B § 3.4）。

#### `POST /api/papers/revise`

```
Body:
  { "paper_id": "abc123", "user_instruction": "把前三道改成简单一点的" }

内部：
  1. current_user
  2. current_paper = storage.get_paper(paper_id, current_user.id) → 404 if None
  3. new_paper = ai_engine.revise_paper(current_paper, user_instruction)
  4. storage.save_paper(new_paper, current_user.id)   # 新的 paper_id
  5. return new_paper
```

**权限**：`get_paper(paper_id, user_id)` 内部校验 `user_id` 匹配，不匹配返回 None → 端点 404。**不使用"未授权"（403）**——防止 paper_id 枚举。

#### `POST /api/attempts`（提交答题 + 判对错）

```
Body:
  {
    "paper_id": "abc123",
    "items": [
      { "index": 1, "user_answer": "B" },
      { "index": 2, "user_answer": "written" },
      { "index": 3, "user_answer": { "blank1": "so", "blank2": "that" } }
    ]
  }

内部：
  1. current_user
  2. paper = storage.get_paper(paper_id, current_user.id) → 404 if None
  3. 逐题判对错：
     - 找到 paper.items[i] 对应的 PaperItem
     - 用 grading.compare(user_answer, paper_item.question.answer, question_type)
     - 结果得 GradeResultItem
  4. 构造 Attempt 对象（含 kps_json 冗余，Spec A § 3.7 决策）
  5. storage.write_attempt(attempt)
  6. storage.mark_paper_submitted(paper_id)
  7. return GradeSubmissionResponse
```

**判对错规则**（`backend/services/grading.py`）：

```python
AnswerValue = str | list[dict[str, list[str]]]
UserAnswerValue = str | list[str] | dict[str, str]

def compare(user_answer: UserAnswerValue, correct_answer: AnswerValue, question_type: str) -> bool:
    if isinstance(correct_answer, list):
        # word_form / sentence_rewriting:
        # 用户答案归一化为 blankN -> value，再命中 answer_json 中任一候选组合
        return compare_blank_answers(user_answer, correct_answer)
    if question_type == "single_choice":
        return user_answer.strip().upper() == correct_answer.strip().upper()
    return normalize(user_answer) == normalize(correct_answer)

def normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)                  # 多空白折叠
    s = re.sub(r"[.!?,;:]+$", "", s)            # 末尾标点忽略
    return s
```

对应 Spec A § 1.6 / § 2.2 的判等约定。真实题库的 `answer_json` 规则是：单选题为单字母字符串；词性转换/句子改写为 `list[dict]` 候选组合，每个 `blankN` 的 value 是可接受答案列表。后端判分不使用 `difficulty`，因为 Spec A 已删除该字段。

#### `POST /api/solutions`

```
Body: SolutionRequest（含 question + source_question_id + revision_mode）

内部：
  1. current_user（登录才能生成，防滥用）
  2. solution = ai_engine.generate_solution(
         q=body.question,
         source_question_id=body.source_question_id,
         revision_mode=body.revision_mode,
     )
  3. return SolutionResponse(solution=solution)
```

**关键**：Solutioner 内部会判断"命中缓存 / 写回题库"（Spec B § 6.2），后端不参与这个决策。

#### `GET /api/users/me/mastery`

```
Query: window_days=30 (可选)

内部：
  1. current_user
  2. profile = ai_engine.build_profile(current_user.id, window_days)
  3. return profile
```

### 5.3 URL 前缀约定

- 所有 API 走 `/api/` 前缀
- 部署时 FastAPI 顶层挂两个 router：
  - `app.include_router(api_router, prefix="/api")`
  - `app.mount("/", StaticFiles(directory="static", html=True))`（放最后作为 catch-all）
- **顺序重要**：FastAPI 路由匹配是"先注册先匹配"，`/api/*` 必须先注册

### 5.4 OpenAPI 文档

FastAPI 自带 `/docs`（Swagger UI）和 `/openapi.json`。生产环境可通过 `AppConfig.env` 控制是否禁用。

### 5.5 测试专用端点（`/api/test/*`）

**用途**：为 Spec E 的 e2e 提供 LLM 脚本注入与 DB 观测能力。**仅在 `AppConfig.backend.env == "test"` 或环境变量 `LLM_CLIENT_MODE=scripted` 时挂载**；生产构建不引入相关 router。

| Method | Path | 用途 |
|---|---|---|
| POST | `/api/test/llm-scripts` | 重置脚本化 LLM client 的队列（Spec E § 3.4） |
| GET | `/api/test/db-inspect` | 只读查询指定表（Spec E § 4.4） |

**实现约束**：
- Router 定义在 `backend/api/_test.py`，`main.py` 用 `if config.backend.env == "test": app.include_router(test_router, prefix="/api/test")` 挂载。
- 不做鉴权（仅 test 环境挂）。
- 生产环境即使代码文件存在，路由也不注册——`/api/test/*` 返回 404。

---

## 6. 统一错误处理

### 6.1 异常层次

```python
# backend/errors.py

class BackendError(Exception):
    """所有后端业务异常的基类。"""
    error_code: str = "unknown"
    http_status: int = 500
    message: str = "服务器内部错误"

class AuthenticationError(BackendError):
    error_code = "auth.unauthorized"
    http_status = 401
    message = "未登录或会话已过期"

class UsernameConflictError(BackendError):
    error_code = "auth.username_conflict"
    http_status = 409
    message = "用户名已被占用"

class InvalidCredentialsError(BackendError):
    error_code = "auth.invalid_credentials"
    http_status = 401
    message = "用户名或密码错误"

class ResourceNotFoundError(BackendError):
    error_code = "resource.not_found"
    http_status = 404
    message = "资源不存在"

class ValidationError(BackendError):
    """透传 pydantic ValidationError 为统一错误。"""
    error_code = "request.invalid"
    http_status = 422
    message = "请求参数错误"
```

**AI Engine 异常映射**：

| AI Engine 异常（Spec B） | HTTP | error_code |
|---|---|---|
| `ParserError` | 400 | `ai.parser_failed` |
| `RetrieverError`（无候选） | 422 | `ai.no_candidate` |
| `ReviserError`（全 fallback） | 500 | `ai.reviser_failed` |
| `SolutionerError` | 500 | `ai.solutioner_failed` |
| `LLMError`（网络/超时） | 502 | `ai.llm_upstream` |
| 其他 `AIEngineError` | 500 | `ai.internal` |

### 6.2 稳定的 error_code 清单

前端会用 `error_code` 精确 toast。清单必须稳定（改动等于 API breaking change）：

```
auth.unauthorized             未登录/会话过期
auth.username_conflict        用户名冲突
auth.invalid_credentials      用户名或密码错
resource.not_found            资源不存在（试卷/题目等，不区分具体子类）
request.invalid               请求体校验失败
rate.exceeded                 超出请求速率限制
ai.parser_failed              AI 无法理解请求
ai.no_candidate               题库中找不到匹配的题
ai.reviser_failed             AI 改题全部失败
ai.solutioner_failed          AI 解析生成失败
ai.llm_upstream               LLM 服务上游异常
ai.internal                   AI Engine 内部异常
server.internal               服务器内部错误（兜底）
```

### 6.3 异常处理器

```python
# backend/errors.py

@app.exception_handler(BackendError)
def handle_backend_error(request: Request, exc: BackendError) -> JSONResponse:
    trace_id = uuid4().hex
    logger.error(f"[{trace_id}] {type(exc).__name__}: {exc}", exc_info=True)
    body = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        detail=None if is_production() else {"exception": str(exc)},
        trace_id=trace_id,
    )
    return JSONResponse(status_code=exc.http_status, content=body.model_dump())

@app.exception_handler(AIEngineError)
def handle_ai_engine_error(request: Request, exc: AIEngineError) -> JSONResponse:
    # 映射到对应 BackendError（见 § 6.1 表）
    mapped = _map_ai_error(exc)
    return handle_backend_error(request, mapped)

@app.exception_handler(RequestValidationError)     # 来自 fastapi.exceptions
def handle_validation_error(...) -> JSONResponse:
    # 转 BackendError.ValidationError，透传 pydantic 的字段错误进 detail
    ...

@app.exception_handler(Exception)
def handle_unexpected(...) -> JSONResponse:
    # 兜底：500 + server.internal + 记详细日志
    ...
```

**开发环境 detail 里含堆栈；生产环境 detail=None**。`trace_id` 都返回，便于用户报 bug 时提供。

---

## 7. 速率限制 & 中间件

### 7.1 速率限制

**本 spec 不实现严格速率限制**——个人项目，前端唯一入口，滥用风险低。但保留一个**软限制**防止意外循环：

- 每 user_id **每分钟最多 30 次 `/papers/generate`**
- 每 user_id **每分钟最多 60 次 `/solutions`**

在 `backend/deps.py` 中用轻量内存桶实现；桶按 `(user_id, kind)` 计数，窗口为 1 分钟。提供 `check_rate_limit()`、`prune_rate_limits()`、`reset_rate_limits()` 三个入口，分别用于路由依赖、长进程清理和测试隔离。**内存实现**（进程重启计数清零，且多 worker 不共享），够用。

超限返回 `429 Too Many Requests`，`error_code=rate.exceeded`。

### 7.2 请求日志中间件

一个简单的中间件记录每次请求：`method / path / status / duration_ms / user_id / trace_id`（若已产生）。写入结构化 JSON 日志（stdout 即可，未来上日志收集）。

### 7.3 CORS

**部署形态 C 下不需要 CORS**（同源）。**但开发期为了以防前端跑在 5173 时误发跨源请求**，加一个宽松 CORS 配置：

```python
if config.env == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,     # cookie 必需
        allow_methods=["*"],
        allow_headers=["*"],
    )
# 生产环境不加 CORSMiddleware
```

Vite 代理配好后其实用不到，但作为 double-safety 保留。

---

## 8. 配置

`shared/config.py`（Spec A § 6）中的 `AppConfig` 追加：

```python
class BackendConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    env: Literal["development", "production", "test"] = "development"
    session_ttl_days: int = 30
    bcrypt_rounds: int = 12
    static_dir: Path = Path("backend/static")     # 部署时软链或复制 frontend/dist 到此
    rate_limit_generate_per_min: int = 30
    rate_limit_solutions_per_min: int = 60

class AppConfig(BaseModel):
    llm: LLMConfig
    storage: StorageConfig
    embedding: EmbeddingConfig
    backend: BackendConfig                         # ★ 新增
    llm_trace_full: bool = False
```

`.env` 新增：
```
BACKEND_ENV=development
BACKEND_PORT=8000
```

无 `SESSION_SECRET` 需要——session_id 本身是随机 hex，不需要签名（因为它是不透明 token，不含用户信息）。

---

## 9. 后端 CLI

```bash
# 启动开发服务器（热重载）
python -m backend.cli serve --reload

# 启动生产服务器
python -m backend.cli serve --port 8000

# 初始化数据库（创建 users / sessions / papers 表；不影响 questions / attempts）
python -m backend.cli init-db

# 创建用户（开发调试用）
python -m backend.cli create-user --username demo --password demo123

# 清理过期 session（可选，get_session 已惰性清理，此命令用于批量清）
python -m backend.cli cleanup-sessions

# 一键 smoke：注册 → 登录 → 生成试卷 → 提交答题 → 看掌握度
python -m backend.cli smoke
```

CLI 底层就是调本 spec 定义的 `backend/services/` 与 `backend/api/` 函数，绕开 HTTP 层。方便 dev。

---

## 10. 后端集成测试策略

本 spec 只讲**后端集成测试**（FastAPI TestClient + mock LLM + 内存 SQLite）。跨系统 e2e 见 Spec E。

### 10.1 测试目录

```
tests/integration/backend/
├── conftest.py                     # 共用 fixture
├── test_auth.py                    # 注册/登录/logout/me
├── test_papers.py                  # generate/revise/get/list
├── test_solutions.py
├── test_attempts.py                # 提交 + 判对错 + 落库
├── test_mastery.py
└── test_errors.py                  # 各种错误分支
```

### 10.2 `conftest.py` 关键 fixture

```python
@pytest.fixture
def client(mock_llm, memory_db, monkeypatch):
    """FastAPI TestClient，LLM 通过 monkeypatch 替换 shared.llm.deepseek 的单例入口。"""
    monkeypatch.setattr("shared.llm.deepseek.get_client", lambda: mock_llm)
    with TestClient(app) as c:
        yield c

@pytest.fixture
def memory_db(tmp_path):
    """临时 SQLite 文件（TestClient 内需要真实文件路径而非 :memory:）+ init schema。
    通过 monkeypatch 覆盖 shared.storage 的连接目标。"""
    ...

@pytest.fixture
def mock_llm():
    """FakeLLMClient（Spec A § 4 定义）。"""
    ...

@pytest.fixture
def logged_in_client(client):
    """已注册并登录一个 demo 用户，返回带 cookie 的 client。"""
    client.post("/api/auth/register", json={"username": "demo", "password": "demo123"})
    return client
```

**关于 LLM mock 的注入方式**：不用 FastAPI 的 `dependency_overrides`——因为 AI Engine 内部通过 `from shared.llm.deepseek import get_client` 拿单例，不走 `Depends()`。用 pytest 的 `monkeypatch` 替换模块级函数是最直接的做法。storage 层同理。

### 10.3 关键断言维度

- **auth**：注册后 cookie 被设；登录后 `/auth/me` 可取；logout 后 cookie 被清；无 cookie 访问受保护路由 → 401 + `auth.unauthorized`
- **papers**：
  - 未登录访问 → 401
  - 登录后生成 → 200 + Paper JSON + 数据库有对应记录
  - 用户 A 无法读用户 B 的 paper → 404（不是 403）
  - `revise_paper` 生成新 `paper_id`，老的仍存在
- **attempts**：
  - 提交答题后 `attempts` + `attempt_items` 都有记录
  - 判对错逻辑正确（含大小写、空白、末尾标点、多空候选组合）
  - 重复提交同一 paper → 允许（记多条 attempts）
- **mastery**：
  - 无答题记录 → 返回空 profile（不 500）
  - 有若干 attempts 后返回合理的 weak_kps
- **errors**：
  - AI Engine 抛 `ParserError` → 400 + `ai.parser_failed`
  - LLMError → 502 + `ai.llm_upstream`
  - 请求 body 缺字段 → 422 + `request.invalid` + `detail` 含字段名
  - 未捕获异常 → 500 + `server.internal` + `trace_id` 出现在日志

### 10.4 与 e2e 的边界

**后端集成测试不使用真实浏览器**（这是 e2e 的事）。所有 HTTP 交互通过 FastAPI TestClient 完成，只到"HTTP 层"，不涉及前端 JS。

---

## 11. 部署与运维

### 11.1 部署命令

```bash
# 1. 构建前端
cd frontend && npm run build

# 2. 把 frontend/dist 拷贝或软链到 backend/static
ln -sfn ../frontend/dist backend/static     # Unix
# 或 Windows: mklink /D backend\static ..\frontend\dist

# 3. 启动
python -m backend.cli serve --port 8000 --env production
```

用户访问 http://localhost:8000。

### 11.2 未来若需要真部署

- **容器化**：Dockerfile 分两阶段（Node build + Python runtime），单镜像
- **反向代理**：nginx 前置终结 TLS，proxy_pass 到 FastAPI
- **数据卷**：`data/` 目录挂载出来（SQLite 文件 + Chroma 目录 + LLM traces）

**本 spec 不实现容器化 / 反向代理**——留待未来。

---

## 12. 明确的非目标（本 spec 范围外）

- ❌ 不实现 OAuth / SSO / 第三方登录
- ❌ 不实现密码找回 / 邮箱验证（无邮箱字段）
- ❌ 不实现权限系统（用户之间无差异，除资源归属）
- ❌ 不实现多语言（错误消息只有中文）
- ❌ 不实现 API 版本化（`/api/v1/*`）——未来若真需要版本再引入
- ❌ 不实现分页（历史试卷若真的爆到 >1000 份，加简单 limit/offset）
- ❌ 不实现 WebSocket / SSE（生成试卷是同步返回，不做流式）
- ❌ 不实现容器化 / CI/CD / 反向代理（部署留给未来）
- ❌ 不实现 Redis / 分布式 session（SQLite session 足够）

---

## 13. 已识别的开放问题

1. **试卷软删除 vs 硬删除**：目前 `papers` 永不删。若用户界面提供"删除历史试卷"，是硬删还是加 `deleted_at` 软删？留给未来
2. **`papers.payload_json` 迁移**：若 `Paper` schema 演进（比如新增字段），旧记录读出来 pydantic 校验会失败——第一版先按"schema 稳定"假设，若变更则加迁移脚本或 pydantic `Config.extra="ignore"`
3. **rate limit 存内存**：多进程部署时不共享，若未来用 gunicorn 多 worker，切 Redis 或用 SQLite 存计数
4. **session 存 SQLite 的写放大**：每次请求都要 UPDATE `sessions` 一行做滑动，SQLite 写事务。数万用户量级前无问题；有则考虑分离 session 存储
5. **`GradeSubmissionResponse` 是否包含解析**：目前只返回对错。前端"看解析"要单独调 `/api/solutions`。若前端体验发现"一次调完更好"，未来加 `include_solutions=true` 查询参数

---

## 14. 对 Spec A/B 的同步更新计划

本 spec 落地后需一次性同步更新 Spec A/B（见 Task #13）：

**Spec A 修改**：
- § 1.6 / § 2.2 是当前判分依据：单选字符串；填空/改写使用 `answer_json` 多空候选组合
- § 1.7 明确删除 `difficulty`，后端契约和 `attempt_items` 写入均不得依赖该字段
- § 9 移除"不实现用户注册/登录/鉴权"
- § 3.8 追加 `users` / `sessions` / `papers` 表结构（引用本 spec § 3.1），并保留 Spec A 已建好的 `attempts` / `attempt_items`
- § 10 或 § 11 增加"新增交互：后端持久化试卷、鉴权"的说明

**Spec B 修改**：
- § 1.2 保留"AI Engine 无状态"（正确，本 spec 未改这个）
- § 12.3 段落里 "AI Engine 不涉及的端点：`POST /users/{id}/attempts`" 改为"由 backend spec 定义"
- § 15 移除"不实现用户注册/登录/鉴权""不实现试卷持久化"
- § 17 保留所有 AI Engine 侧不变量——本 spec 未撤销任何 AI Engine 侧的性质

**更新时机**：Spec C 通过 review 后立即执行；不等 D/E 完成——避免 D/E 引用到过时决策。

---

## 15. 里程碑（M5：后端）

前置：Spec A 的 M1 完成、Spec B 的 M2/M3/M4 完成（AI Engine 可用）。

1. `shared/schemas.py` 追加本 spec § 2 契约类型
2. `shared/storage.py` 追加本 spec § 3.3 方法
3. SQLite migration：新增 `users` / `sessions` / `papers` 表
4. `backend/errors.py` + 统一错误处理器
5. `backend/auth/`：password + session + routes + `current_user` 依赖
6. `backend/services/`：paper_store、attempt_store、grading、user_store
7. `backend/api/`：papers、solutions、attempts、mastery、grading（内部）
8. `backend/main.py`：FastAPI app + 中间件 + StaticFiles
9. `backend/cli.py`：serve / init-db / create-user / smoke
10. 后端集成测试（本 spec § 10）
11. **同步更新 Spec A/B**（Task #13）
12. 端到端 smoke：CLI 命令 `smoke` 走通完整流程

M5 完成后进入 Spec D（前端）实现阶段。

---

## 16. 附录：核心不变量速查（后端相关）

Spec A § 12、Spec B § 17 已定义的不变量继续生效。后端补充：

1. **AI Engine 完全无 HTTP 感知**：`backend/services/ai_gateway.py` 是后端唯一 import `ai_engine.*` 的地方；`backend/api/` 只依赖 gateway
2. **`paper_id` 由 AI Engine 生成，后端沿用**（不重新生成）
3. **`user_id` 只从 session 注入**——请求体永远不传 `user_id`（除非未来支持"管理员为他人生成"，明确超出本 spec）
4. **未登录访问受保护路由 → 401 `auth.unauthorized`**，不 302 跳转（前端拦截 401 自跳登录页）
5. **判对错不调 LLM**：`backend/services/grading.py` 是确定性比较（Spec A § 1.6 / § 2.2 判等约定），支持单选字符串和 `answer_json` 多空候选组合
6. **paper 权限校验隐含在 storage 层**：`storage.get_paper(paper_id, user_id)` 内部匹配 user_id；上层无需重复校验
7. **答题记录 `kps_json` 由后端在写入时冗余填充**：从 `paper.items[i].question.knowledge_point_ids` 抄写（Spec A § 3.8 冗余存储的落地方）。**该字段虽在 `RevisedQuestion` 上，但由 Spec A 不变量保证——`knowledge_point_ids` 在改题过程中永不修改——因此抄改后题等价于抄原题。后续维护者请勿改成 "从 `source_question_id` 反查原题"，两者结果相同但多一次 SQL 读**。
8. **后端不得重新引入 `difficulty`**：真实题库 schema 已删除该字段，`attempt_items` 也不保存 difficulty。
