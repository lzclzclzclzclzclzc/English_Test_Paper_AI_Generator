# 中考英语 AI 试卷生成系统

> 学生用一句话（如「来 10 道现在完成时的单选」）描述需求，系统从**真实中考题库**检索匹配题目，
> 按需用 LLM 加工/补齐，返回一份可在浏览器内直接作答、后端确定性判分的完整试卷；
> 错题、历史与掌握度沉淀为学情画像，让下一份卷更有针对性。

**核心原则**：LLM 只负责「意图理解 / 题目改写 / 解析生成」，**题库与判分是确定性代码**，
向量检索（RAG）在两者之间搭桥。所有跨子系统的数据结构以 `shared/schemas.py` 为唯一真源。

---

## 目录

- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [仓库结构](#仓库结构)
- [本地开发](#本地开发)
- [生产环境部署](#生产环境部署)
  - [部署拓扑](#部署拓扑)
  - [前置条件](#0-前置条件)
  - [1. 获取代码与数据](#1-获取代码与数据)
  - [2. 下载嵌入模型](#2-下载嵌入模型)
  - [3. 安装 Python 依赖](#3-安装-python-依赖)
  - [4. 配置环境变量 .env](#4-配置环境变量-env)
  - [5. 初始化数据库与账号](#5-初始化数据库与账号)
  - [6. 构建前端静态产物](#6-构建前端静态产物)
  - [7. 启动后端](#7-启动后端)
  - [8. 启动 Caddy（反向代理 + 静态托管 + HTTPS）](#8-启动-caddy反向代理--静态托管--https)
  - [9. 部署自检](#9-部署自检)
  - [支付模式：mock 与支付宝沙盒](#支付模式mock-与支付宝沙盒)
  - [方案 B：不用 Caddy，后端自托管前端](#方案-b不用-caddy后端自托管前端)
- [环境变量参考](#环境变量参考)
- [运维命令速查](#运维命令速查)
- [测试](#测试)
- [重建题库（离线，一次性）](#重建题库离线一次性)

---

## 系统架构

按依赖顺序划分为 5 个子系统：

| 目录 | 职责 | 运行期是否需要 |
|------|------|----------------|
| `ingestion/` | **离线**：EPUB → 题库（SQLite + ChromaDB）、词表构建 | 否（产物已随仓库提供） |
| `shared/` | 跨子系统契约：`schemas.py`（唯一真源）、`storage.py`、`config.py`、`llm/deepseek.py` | 是 |
| `ai_engine/` | Parser / Retriever / Reviser / Solutioner / Analyzer / WritingGrader + `pipeline.py` | 是 |
| `backend/` | FastAPI 后端（13 组路由、鉴权、持久化、判分、**积分账本 + 支付宝沙盒支付**） | 是 |
| `frontend/` | React + Vite 单页应用（21 个用户页 + 10 个管理页） | 构建期需要；产物由 Caddy 托管 |
| `agent/` | 学习助手 Coach（OpenAI Agents SDK，跑在 DeepSeek 上），后端 `POST /api/agent/chat` 调用 | 是（学习助手功能） |

**生成流水线**（`ai_engine/pipeline.py`）：意图解析 → 混合检索（SQL 硬过滤 + 向量重排）→ 缺口改写/补题 →
解析生成 → 学情分析 / 作文批改。向量检索只覆盖 3 类自由形题（`single_choice` / `word_form` /
`sentence_rewriting`，见 `shared/schemas.py::VECTOR_INDEXED_QUESTION_TYPES`）；其余题型走 SQL。

**数据存储**（三个 SQLite 文件，按归属拆分，互不 JOIN）：

| 文件 | 内容 | 是否入库 git | 何时创建 |
|------|------|--------------|----------|
| `data/questions.db` | 只读题库（1428 题 / 10 题型 / 56 知识点） | ✅ 已提交 | 离线构建，随仓库分发 |
| `data/chroma/` | ChromaDB 向量库（`questions` 集合，2560 维） | ✅ 已提交 | 离线构建，随仓库分发 |
| `data/app.db` | 用户 / 会话 / 试卷 / 作答 / 掌握度 / 词汇 / **积分账本 / 订单** / 审计日志 | ❌ gitignored | 首次 `init-db` 或首次访问时自建 |
| `data/agent_sessions.db` | 学习助手对话历史 | ❌ gitignored | 学习助手首次使用时自建 |

---

## 技术栈

- **后端**：Python ≥ 3.11、FastAPI、Uvicorn（单进程 ASGI）、Pydantic v2、pydantic-settings、
  会话 Cookie 鉴权（bcrypt 哈希，非 JWT）。
- **AI**：`openai` SDK + `instructor`（结构化 JSON 输出）访问 DeepSeek 兼容端点；
  `chromadb` 向量库；`sentence-transformers` 加载本地 **Qwen3-Embedding-4B**（CUDA→CPU 自动降级）；
  学习助手用 **OpenAI Agents SDK**（`openai-agents`）。
- **前端**：React 19 + Vite + TypeScript（严格模式）、React Router 7、TanStack Query、
  Tailwind CSS v4 + shadcn/ui、Recharts、markmap（思维导图）、react-hook-form + zod。
- **支付**：积分制。默认离线 mock；可切支付宝沙盒（`python-alipay-sdk`）。
- **反向代理**：Caddy（自动 HTTPS + SPA 回退 + 同源反代 `/api`）。

---

## 仓库结构

```
.
├── backend/          FastAPI 后端（main.py = ASGI 入口, cli.py = 运维命令）
│   ├── main.py       create_app() → app = backend.main:app
│   ├── cli.py        python -m backend.cli <serve|init-db|...>
│   ├── api/          路由组：health/auth/papers/solutions/attempts/writing/
│   │                 mastery/agent/knowledge_points/admin/vocabulary/credits/payment
│   ├── auth/         会话与密码（生产下 Secure cookie）
│   ├── services/     credits/（积分账本+计费）, payment/（支付宝沙盒+订单）
│   └── static/       内置一份 SPA 产物（可被 BACKEND_STATIC_DIR 覆盖）
├── ai_engine/        pipeline.py + retriever/reviser/solutioner/analyzer/...
├── shared/           schemas.py（契约真源）/ config.py / storage.py / llm/deepseek.py
├── agent/            学习助手 Coach（coach.py / tools.py / skills/*.md）
├── ingestion/        离线建库 CLI（epub→md→split→kp→sqlite→vec）
├── frontend/         React + Vite（npm run build → frontend/dist）
├── data/             questions.db + chroma/（入库）；app.db 等运行期自建（gitignored）
├── models/           Qwen3-Embedding-4B/（~7.6 GB，gitignored，需自行下载）
├── docs/             各子系统设计规范（与实现保持同步）
├── Caddyfile         生产反向代理配置
├── .env.example      环境变量样例
└── pyproject.toml    仅声明离线建库依赖（serving 依赖见下文）
```

---

## 本地开发

```bash
# 1) 后端（终端 A）：默认 development，:8000
PYTHONIOENCODING=utf-8 python -m backend.cli init-db
PYTHONIOENCODING=utf-8 python -m backend.cli serve --reload

# 2) 前端（终端 B）：:5173，/api 自动代理到 :8000（见 vite.config.ts）
cd frontend && npm install && npm run dev
```

开发模式下后端启用 CORS（`FRONTEND_ORIGIN`，默认 `http://localhost:5173`），会话 Cookie 不带 `Secure`，
纯 HTTP 即可登录。浏览器访问 `http://localhost:5173`。

> Windows 上运行任何 Python 命令请前缀 `PYTHONIOENCODING=utf-8`，否则中文输出乱码。

---

## 生产环境部署

### 部署拓扑

```
浏览器 ──HTTPS──> Caddy(:443)
                    ├─ /api/*  ──reverse_proxy──> Uvicorn 后端 (127.0.0.1:8000)
                    └─ /*      ──静态文件──────────> frontend/dist（SPA，找不到回退 index.html）
```

**为什么必须走 HTTPS**：`BACKEND_ENV=production` 时会话 Cookie 带 `Secure` 标志
（`backend/auth/session.py`），纯 HTTP 浏览器不回传该 Cookie，会「登录后立刻掉登录态」。
Caddy 对 `localhost` 自动签发本地证书，对公网域名自动申请 Let's Encrypt。浏览器只与 Caddy 通信，
天然同源，**无需 CORS**（生产模式后端不挂 CORS 中间件）。

> ⚠️ 后端是**单进程**运行：限流窗口、配置/支付客户端单例都是进程内状态，**不要加 `--workers`**（多进程不共享这些状态）。

---

### 0. 前置条件

- **Python ≥ 3.11**（开发机实测 3.13）。GPU 可选——无 CUDA 时嵌入模型自动降级到 CPU。
- **Node.js**（建议 20/22 LTS，配套 `npm`）——仅构建前端时需要。
- **Caddy 2**（[下载](https://caddyserver.com/download)）。
- 一个 **DeepSeek 兼容** LLM API Key（默认端点 `https://api.scnet.cn/api/llm/v1`，模型 `DeepSeek-V4-Flash`）。
- 磁盘 ≥ 10 GB（嵌入模型约 7.6 GB）。

### 1. 获取代码与数据

```bash
git clone https://github.com/lzclzclzclzclzclzc/English_Test_Paper_AI_Generator.git && cd English_Test_Paper_AI_Generator
```

题库 `data/questions.db` 与向量库 `data/chroma/` **已随仓库提交**，无需重建即可直接服务。

### 2. 下载嵌入模型

将 **Qwen3-Embedding-4B** 放到 `models/Qwen3-Embedding-4B/`（该目录 gitignored，需自行下载）：

```bash
# 例：用 huggingface-cli（或任意方式）下载到指定目录
huggingface-cli download Qwen/Qwen3-Embedding-4B --local-dir models/Qwen3-Embedding-4B
```

> 该模型只在**语义检索路径**（请求含自由文本主题时）**惰性加载**；纯配额请求（如「10 道单选」）
> 走 SQL 随机路径，完全不加载模型。若暂不部署语义检索，可先跳过——但 `deploy-check` 的向量库校验仍会通过（校验的是 `data/chroma/`，不是模型）。

### 3. 安装 Python 依赖

> 本项目**没有 requirements.txt**：`pyproject.toml` 只声明了离线建库依赖。
> 以下是运行期（serving）所需的完整依赖，建议在虚拟环境中安装，并按需固化为你自己的 `requirements.txt`。

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows bash；Linux: source .venv/bin/activate

# 让 backend / ai_engine / shared 可被 import（可编辑安装本仓库）
pip install -e .

# —— 运行期核心依赖（后端 + AI 引擎 + 学习助手）——
pip install fastapi uvicorn pydantic pydantic-settings bcrypt httpx \
            openai instructor jinja2 chromadb torch sentence-transformers openai-agents

# —— 仅「真实支付宝沙盒」模式需要（默认 mock 模式不需要）——
pip install python-alipay-sdk
```

依赖用途对照：

| 包 | 用途 |
|----|------|
| `fastapi` / `uvicorn` | Web 框架 / ASGI 服务器 |
| `pydantic` / `pydantic-settings` | 数据契约 / `.env` 配置加载 |
| `bcrypt` | 密码哈希（会话 Cookie 鉴权） |
| `httpx` | 后端出站 HTTP |
| `openai` / `instructor` | 访问 DeepSeek 端点 / 结构化 JSON 输出 |
| `openai-agents` | 学习助手 Coach（OpenAI Agents SDK） |
| `jinja2` | Prompt 模板 |
| `chromadb` | 向量库客户端 |
| `torch` / `sentence-transformers` | 加载 Qwen 嵌入模型（含 `transformers`/`numpy` 传递依赖） |
| `python-alipay-sdk` | 支付宝沙盒（仅 `PAYMENT_MOCK=false` 时惰性导入） |

> **CPU-only 部署**：如需省显存/带宽，可先装 CPU 版 torch（`pip install torch --index-url https://download.pytorch.org/whl/cpu`）再装其余依赖。

### 4. 配置环境变量 .env

在仓库根目录创建 `.env`（参考 `.env.example`）。生产最小集：

```dotenv
# —— 环境 & 鉴权 ——
BACKEND_ENV=production          # 关键：启用 Secure cookie、关闭 CORS
BACKEND_HOST=127.0.0.1          # 仅经 Caddy 暴露，绑本地回环即可
BACKEND_PORT=8000

# —— LLM（必填 API Key）——
LLM_API_KEY=sk-your-real-key
LLM_BASE_URL=https://api.scnet.cn/api/llm/v1
LLM_MODEL=DeepSeek-V4-Flash

# —— 支付 / 积分 ——
PAYMENT_MOCK=true               # 默认离线 mock；接真实沙盒见下文
CREDITS_SIGNUP_BONUS=300        # 注册一次性赠送（不过期）
CREDITS_DAILY_GRANT=30          # 每日赠送（当日有效）
```

`.env` 已被 gitignore；密钥类文件（`keys/*.pem`）也不入库。完整变量见 [环境变量参考](#环境变量参考)。

### 5. 初始化数据库与账号

```bash
# 创建/迁移 data/app.db（用户/会话/试卷/积分/订单等）
PYTHONIOENCODING=utf-8 python -m backend.cli init-db

# 建一个管理员账号（先建用户，再提权）
PYTHONIOENCODING=utf-8 python -m backend.cli create-user --username admin --password '强密码'
PYTHONIOENCODING=utf-8 python -m backend.cli promote-admin --username admin

# 灌入词汇表（背单词功能所需，写进 data/app.db）
PYTHONIOENCODING=utf-8 python -m backend.cli seed-vocabulary
```

> 若从旧版独立支付服务迁移，可一次性执行 `python -m backend.cli migrate-payment-db`（把旧
> `payment/data/payment.db` 的订单与会员剩余天数折算为积分并入 `data/app.db`）。全新部署无需此步。

### 6. 构建前端静态产物

```bash
cd frontend
npm ci                # 有 package-lock.json，用 ci 保证可复现
npm run build         # tsc -b（严格类型检查）+ vite build → frontend/dist
cd ..
```

产物落在 `frontend/dist/`。前端不读任何 `VITE_*` 变量，API 一律走同源相对路径 `/api/*`
（`frontend/src/api/client.ts`），因此**同一份产物在任意域名/端口下都能用**——由 Caddy 保证同源。

### 7. 启动后端

```bash
# 读取 .env（其中 BACKEND_ENV=production），监听回环 :8000
PYTHONIOENCODING=utf-8 python -m backend.cli serve --host 127.0.0.1 --port 8000
```

等价于 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`。
生产建议用进程守护（systemd / nssm / supervisor 等）拉起该命令并设 `Restart=always`；本仓库未内置守护配置。

> `serve` 的 `--host/--port` 取自命令行参数，**不读** `BACKEND_HOST/BACKEND_PORT`——如需改端口请在命令行显式指定，同时同步修改 `Caddyfile` 的 `reverse_proxy` 目标。

### 8. 启动 Caddy（反向代理 + 静态托管 + HTTPS）

仓库根目录已带 `Caddyfile`（站点为 `localhost`；公网部署把 `localhost` 换成你的域名即可自动签发 Let's Encrypt）。

```bash
caddy trust     # 首次：安装本地 CA，让浏览器信任 localhost 证书（公网域名可跳过）
caddy run       # 前台运行，读取当前目录 Caddyfile
```

然后访问 **https://localhost**（或你的域名）。Caddy 把 `/api/*` 反代到 `:8000`，其余路径按 SPA 从
`frontend/dist` 提供并回退 `index.html`（使 `/admin/users` 等前端路由刷新不 404）。

### 9. 部署自检

```bash
PYTHONIOENCODING=utf-8 BACKEND_ENV=production python -m backend.cli deploy-check
```

它校验：`BACKEND_ENV==production`、`LLM_API_KEY` 非空、`static_dir/index.html` 存在，以及就绪检查
（SQLite / 核心表 / 题库 / 向量库）。全绿返回 0，否则退出码 2 并打印哪一项未就绪。
运行期健康检查端点：`GET /api/health/ready`。

---

### 支付模式：mock 与支付宝沙盒

- **离线 mock（默认，`PAYMENT_MOCK=true`）**：不连支付宝。会额外挂载开发端点
  `POST /api/payment/dev/simulate-paid/{out_trade_no}` 模拟买家付款——用于本地/演示环境跑通积分充值闭环。
- **真实支付宝沙盒（`PAYMENT_MOCK=false`）**：需另装 `python-alipay-sdk`，并配置：

  ```dotenv
  PAYMENT_MOCK=false
  ALIPAY_APPID=你的沙盒AppId
  ALIPAY_GATEWAY=https://openapi-sandbox.dl.alipaydev.com/gateway.do
  ALIPAY_APP_PRIVATE_KEY_PATH=keys/app_private_key.pem     # 放 keys/，已 gitignore
  ALIPAY_PUBLIC_KEY_PATH=keys/alipay_public_key.pem
  PAY_RETURN_URL=https://你的域名/credits                  # 网页收银台支付完成跳回页
  ```

  支持当面付（扫码）与电脑网站支付；无公网回调，靠 `trade.query` 轮询确认。
  真实模式下**不挂载** `dev/simulate-paid`。可用 `python -m backend.cli reconcile-orders` 对账补账。

---

### 方案 B：不用 Caddy，后端自托管前端

后端本身可在 `static_dir` 存在时把它挂到 `/`（SPA 回退已开启）。因此可让后端直接服务前端产物：

```bash
BACKEND_STATIC_DIR=frontend/dist BACKEND_ENV=production \
  PYTHONIOENCODING=utf-8 python -m backend.cli serve --host 0.0.0.0 --port 8000
```

**代价与注意**：这样只有一个 HTTP 端口、没有 TLS 终结。而 `BACKEND_ENV=production` 会给 Cookie 打
`Secure`，纯 HTTP 下浏览器不回传 → 掉登录态。所以方案 B 要么前面仍需一层 TLS（Nginx/Caddy/云 LB），
要么把 `BACKEND_ENV` 设为非 production（但那样会重新开启 CORS 且 Cookie 不再 `Secure`，不建议对公网）。
**生产推荐方案 A（Caddy）**；方案 B 更适合内网演示。仓库 `backend/static/` 内置了一份 SPA 产物，
故不设 `BACKEND_STATIC_DIR` 时后端也能直接起一个可用界面（可能非最新前端，正式部署请用 `npm run build` 的 `frontend/dist`）。

---

## 环境变量参考

由 `shared/config.py` 读取，`.env`（UTF-8）或进程环境均可。

| 变量 | 默认 | 说明 |
|------|------|------|
| `BACKEND_ENV` | `development` | `development` / `production` / `test`；决定 CORS 与 Cookie `Secure` |
| `BACKEND_HOST` | `127.0.0.1` | 配置项（**注意**：`serve` 命令实际取命令行 `--host`，不读此项） |
| `BACKEND_PORT` | `8000` | 同上，`serve` 取 `--port` |
| `SESSION_TTL_DAYS` | `30` | 会话/Cookie 有效期 |
| `BCRYPT_ROUNDS` | `12` | bcrypt 代价因子 |
| `BACKEND_STATIC_DIR` | `backend/static` | 挂到 `/` 的 SPA 目录；置为 `frontend/dist` 可自托管前端 |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS 允许来源（仅 dev/test 生效） |
| `LLM_API_KEY` | `""` | **必填**（LLM 调用与学习助手都用它） |
| `LLM_BASE_URL` | `https://api.scnet.cn/api/llm/v1` | LLM 端点（OpenAI 兼容） |
| `LLM_MODEL` | `DeepSeek-V4-Flash` | 模型名 |
| `LLM_MAX_CONCURRENCY` | `4` | LLM 并发上限 |
| `LLM_MAX_RETRIES` | `3` | 结构化输出重试次数 |
| `SQLITE_PATH` | `data/questions.db` | 只读题库路径 |
| `APP_DB_PATH` | `data/app.db` | 用户/业务库路径 |
| `CHROMA_PATH` | `data/chroma` | 向量库路径 |
| `PAYMENT_MOCK` | `true` | 离线 mock 支付；`false` 走真实沙盒 |
| `PAYMENT_ORDER_TTL_SECONDS` | `300` | 订单有效期 |
| `ALIPAY_APPID` / `ALIPAY_GATEWAY` | 空 / 沙盒网关 | 支付宝沙盒配置 |
| `ALIPAY_APP_PRIVATE_KEY_PATH` | `keys/app_private_key.pem` | 应用私钥 PEM（gitignore） |
| `ALIPAY_PUBLIC_KEY_PATH` | `keys/alipay_public_key.pem` | 支付宝公钥 PEM（gitignore） |
| `PAY_RETURN_URL` | `http://localhost:5173/credits` | 网页收银台完成跳回页 |
| `CREDITS_SIGNUP_BONUS` | `300` | 注册一次性赠送积分（不过期） |
| `CREDITS_DAILY_GRANT` | `30` | 每日赠送积分（当日有效，Asia/Shanghai 日界） |
| `RATE_LIMIT_GENERATE_PER_MIN` | `30` | 出卷限流 |
| `RATE_LIMIT_SOLUTIONS_PER_MIN` | `60` | 解析限流 |
| `RATE_LIMIT_AGENT_PER_MIN` | `20` | 学习助手限流 |

> 说明：`LLM_MAX_CONCURRENCY` / `LLM_MAX_RETRIES` / `RATE_LIMIT_WRITING_PER_MIN` 等字段存在于配置对象中，
> 但部分未在 `get_config()` 里显式接入环境变量覆盖（以代码为准）。上表列出的是可靠可用的部署开关。

---

## 运维命令速查

```bash
python -m backend.cli serve [--host H] [--port P] [--reload]   # 启动后端（uvicorn）
python -m backend.cli init-db                                  # 创建/迁移 data/app.db
python -m backend.cli create-user --username U --password P    # 建用户
python -m backend.cli promote-admin --username U               # 提权为管理员
python -m backend.cli seed-vocabulary [--file <json>]          # 灌词汇表
python -m backend.cli cleanup-sessions                         # 清理过期会话
python -m backend.cli deploy-check                             # 生产就绪自检
python -m backend.cli smoke                                    # 内存端到端冒烟（mock LLM）
python -m backend.cli migrate-payment-db [--src <db>]          # 迁移旧支付库（一次性）
python -m backend.cli reconcile-orders                         # 订单对账补账
```

---

## 测试

```bash
# 后端 / AI 引擎（用 pytest，切勿 python <file>.py，会破坏 import ai_engine）
pip install pytest pytest-cov
PYTHONIOENCODING=utf-8 python -m pytest tests/ -v

# 前端
cd frontend && npm run test        # vitest
npm run lint                       # oxlint
```

> 标记 `integration` 的用例需真实 LLM Key 与 SQLite；快速冒烟可用 `python -m backend.cli smoke`（LLM 被 mock）。

---

## 重建题库（离线，一次性）

题库与向量库已入库，正常部署**无需**重建。仅在新增题源时才跑，且需 Qwen 模型与离线依赖
（`typer ebooklib html2text beautifulsoup4`，加 `chromadb sentence-transformers`）：

```bash
python -m ingestion.cli epub-to-md <epub> --slug <book_slug>   # 1. EPUB→Markdown
python -m ingestion.cli split <book_slug>                       # 2. 解析为题目 JSON
python -m ingestion.cli apply-kp                                # 3b. 挂知识点
python -m ingestion.cli assign-ids                              # 3c. 分配题号
python -m ingestion.cli build-sqlite                            # 4. → data/questions.db
python -m ingestion.cli build-vec                               # 5. → data/chroma/
```

> ⚠️ `data/chapters/*.json` 是「脚本产物 + 约百处手工修补」的稳态，**切勿重跑 `split` 覆盖**，否则会丢失修补。详见 `docs/question-bank-ingestion-design.md`。

---

## 设计文档

各子系统规范在 `docs/`（与实现保持同步）：`ai-engine-design.md`、`backend-design.md`、
`frontend-design.md`、`frontend-visual-spec.md`、`credits-design.md`、`agent-design.md`、
`vocabulary-design.md`、`admin-design.md` 及各题型子规范等。
