# 墨卷 · 中考英语 AI 练习系统

面向**中考英语**的 AI 出题与练习系统。你用一句话说出想练什么（"来 10 道现在完成时的单选"、"帮我制定 7 天学习计划"），系统就从题库检索、由 AI 加工，生成一份能直接在浏览器作答的试卷；交卷后自动判分、给出逐题解析，还能围绕错题定向再练、按薄弱考点制定学习计划。

选择**中考英语**原因：纯文字题目，不涉及图片。

> **状态**：核心链路已跑通——AI 学习助手对话出题、做题判分、错题巩固、学习计划、掌握度画像、会员订阅均可用。

---

## 用户能做什么

登录后（默认演示账号 `demo / demo123`），顶部导航有六个入口：

| 页面 | 你能做的事 |
|------|-----------|
| **学习助手**（首页） | 和 AI 对话：说一句话让它出题、查某个考点的例题、或制定学习计划。出题完成后点「开始做题」直接进入试卷 |
| **错题复习** | 做错的题会自动收进错题本，可勾选若干题让 AI 出一份针对性巩固卷，也可以按最近 N 天的答题记录出综合复习卷 |
| **学习计划** | 让 AI 根据你的历史正确率排出未来几天的每日练习，每天一份针对薄弱考点的卷子，点进去就能练 |
| **我的试卷** | 生成过的卷都在这里。没做完的随时接着做，做过的点进去直接看**上次的作答结果**（对错、你的答案 vs 正确答案、解析），也能一键重做 |
| **掌握度** | 按知识点展示你的掌握程度（Wilson 分数），颜色标出薄弱点 |
| **会员** | 扫码开通会员（支付宝沙盒 / 离线演示模式），解锁错题巩固、综合复习、不限量 AI 解析等功能 |

**做题体验**：交卷后每题标 ✓/✗，卷面右上角盖"对/总"红章；点每题下方「查看解析」由 AI 讲解——**答错的题会专门解释你选的那个选项为什么错**。

---

## 项目愿景

一句话：**LLM 只做"意图理解、题目加工、解析生成"，题库和判对错交给确定性代码，中间用向量检索把两者串起来。**

- 用户输入自然语言 → 结构化请求
- RAG 从本地题库检索候选题
- LLM 按推断出的改题尺度加工（原题 / 轻改 / 完全新出）
- 用户在浏览器作答 → 后端做规范化字符串比较判对错
- 错题、历史答题记录 → 掌握度画像 → 下一份试卷更有针对性

---

## 覆盖范围

| 覆盖 | 不覆盖 |
|------|--------|
| 单项选择、词性转换、改写句子 | 阅读理解、作文 |
| 纯文本题目 | 含图片的题目 |
| AI 对话出题 / 错题巩固 / 学习计划 | 多用户高并发 |
| 用户名+密码本地登录 + 会员订阅 | OAuth/SSO/邮箱验证 |
| 后端持久化试卷、答题、掌握度 | 分布式部署、多进程 session 共享 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              浏览器（React + Vite）                       │
│  学习助手(AI对话)   错题复习   学习计划   我的试卷   掌握度   会员          │
│  ────────────     出题/判分/解析/重做 · 错题巩固 · 每日计划 · 掌握度画像    │
└─────────────────────────┬────────────────────────────────────────────────┘
                          │ HTTP + Cookie
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        FastAPI 后端（backend/）                           │
│  ─────────────────────────────────────────────────────────────────────   │
│  /api/auth/*       注册、登录、登出、当前用户                              │
│  /api/agent/*      AI 学习助手对话、生成/实施学习计划                       │
│  /api/papers/*     生成、重出、读取、列表                                  │
│  /api/solutions    按需生成单题解析（含"为何选错"）                        │
│  /api/attempts     提交答题 + 判对错 + 落库 + 按试卷取历史结果             │
│  /api/users/me/mastery  掌握度画像                                         │
│                                                                          │
│  职责：鉴权、试卷持久化、答题记录、规范化字符串判对错、错误统一封装        │
└──────────┬───────────────────┬──────────────────┬────────────────────────┘
           │                   │                  │
           │ 加载 skill+工具    │ 函数调用          │ 读写
           ▼                   ▼                  ▼
┌────────────────────┐ ┌──────────────────┐ ┌──────────────────────────────┐
│  agent/（学习助手）  │ │ AI Engine        │ │       shared/（共享层）      │
│  ────────────────  │ │ (ai_engine/)     │ │  ─────────────────────────── │
│  单 Agent + skill   │ │  Parser          │ │  schemas.py   pydantic 契约  │
│  (markdown) + 工具  │ │  Retriever       │ │  storage.py   SQLite+Chroma  │
│  · 出题             │ │  Reviser         │ │  embedding.py Qwen 4B（本地）│
│  · 查例题           │ │  Solutioner      │ │  llm/deepseek.py DeepSeek    │
│  · 制定/实施学习计划 │ │  Analyzer        │ │  config.py    AppConfig      │
│  (OpenAI Agents SDK)│ │  纯函数、无状态   │ │  唯一的跨子系统边界           │
└────────────────────┘ └──────────────────┘ └──────────────────────────────┘
                                                    │
                                                    ▼
                                     ┌──────────────────────────┐
                                     │  SQLite  +  ChromaDB     │
                                     │  ─────────────────────── │
                                     │  questions               │
                                     │  knowledge_points        │
                                     │  question_kp_map         │
                                     │  users / sessions        │
                                     │  papers                  │
                                     │  attempts / attempt_items│
                                     │  chroma/ (向量)           │
                                     └──────────────────────────┘
                                                    ▲
                                                    │ 只写（离线）
                                     ┌──────────────────────────┐
                                     │  ingestion/（题库摄入）    │
                                     │  EPUB → md → 章节树 →     │
                                     │  ★人工审核知识点树 →       │
                                     │  LLM 抽题 → Loader        │
                                     └──────────────────────────┘
```

---

## 本地启动

### 环境要求

- Python 3.11+
- Node.js 18+
- `.env` 文件放在项目根目录（见下方模板）

### `.env` 配置模板

```env
LLM_API_KEY=your_deepseek_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
BACKEND_ENV=development
```

### 首次初始化（只需跑一次）

```bash
# 初始化数据库表结构
PYTHONIOENCODING=utf-8 python -m backend.cli init-db

# 创建测试用户（用户名 demo，密码 demo123）
PYTHONIOENCODING=utf-8 python -m backend.cli create-user --username demo --password demo123

# 注入演示答题记录（用于学习计划功能）
PYTHONIOENCODING=utf-8 python agent/seed_demo.py --user demo
```

### 每次启动（三个终端分别运行）

**终端 1 — 主后端（端口 8000）**
```bash
PYTHONIOENCODING=utf-8 python -m backend.cli serve --reload
```

**终端 2 — 支付服务（端口 8001）**
```bash
cd payment
python -m uvicorn app.main:app --port 8001 --reload
```

**终端 3 — 前端开发服务器（端口 5173）**
```bash
cd frontend
npm install   # 首次需要
npm run dev
```

浏览器打开 [http://localhost:5173](http://localhost:5173)，用 `demo / demo123` 登录。

> **Windows PowerShell** 设置环境变量方式不同：
> ```powershell
> $env:PYTHONIOENCODING="utf-8"; python -m backend.cli serve --reload
> ```

---

## 生产环境运行

生产形态用 **Caddy 反向代理**统一入口:Caddy 直接提供前端静态产物(`frontend/dist`,SPA 路由回退),并把 `/api/*` 转发到主后端(`:8000`)、`/payapi/*` 转发到支付服务(`:8001`)。浏览器只访问 Caddy,天然同源,无需 CORS。后端与支付都退化为纯 API 进程。与本地开发的区别:`BACKEND_ENV=production`(httpOnly + **Secure** + SameSite=strict Cookie、关闭 CORS、不挂测试端点)、不带 `--reload`、前端跑 `build` 而非 `dev`。

仓库根目录已提供 [`Caddyfile`](./Caddyfile)。

> ⚠️ **必须走 HTTPS**:`BACKEND_ENV=production` 下 session cookie 带 `Secure` 标志(`backend/auth/session.py`),纯 HTTP 浏览器不会回传 → **登录后立刻掉登录态**。Caddy 站点地址用 `localhost` 会自动启用本地 HTTPS(见下),`https://localhost` 下 Secure cookie 正常工作。只想本机快速自测又不想装本地 CA,可改用上面「本地启动」的开发模式(`BACKEND_ENV=development` + Vite dev,走 http://localhost:5173)。

> ⚠️ **上线前务必先读下方「生产部署注意事项」**:会员校验默认 fail-open、演示账号、限流等几处必须调整,否则有安全/计费风险。

### 0. 安装 Caddy(Windows)

```bash
winget install CaddyServer.Caddy      # 或:choco install caddy
caddy version                          # 验证(新装后需重开终端让 PATH 生效)
```
其他系统见 https://caddyserver.com/docs/install 。

### 1. `.env`(生产)

```env
LLM_API_KEY=your_deepseek_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
BACKEND_ENV=production
```
Caddy 直接服务静态产物,因此**不需要** `BACKEND_STATIC_DIR`。payment 的 `.env` 另见 [`payment/README.md`](./payment/README.md)(真实收单需 `MOCK_PAY=false` + 沙盒/正式密钥)。

### 2. 构建前端

```bash
cd frontend
npm ci
npm run build          # 产物在 frontend/dist（Caddy 从这里提供）
cd ..
```
> 每次改前端都要重新 `npm run build`;Caddy 无需重启(直接读磁盘上的新文件),仅后端/支付改了才重启对应进程。**浏览器记得硬刷新(Ctrl+F5)**。

### 3. 初始化 & 首个管理员（新库只需一次）

```bash
# 表结构（含 role/status 列的迁移会自动应用）
PYTHONIOENCODING=utf-8 python -m backend.cli init-db

# 创建你的账号，并提升为管理员（管理后台 /admin 的唯一入口）
PYTHONIOENCODING=utf-8 python -m backend.cli create-user --username <admin_user> --password <strong_password>
PYTHONIOENCODING=utf-8 python -m backend.cli promote-admin --username <admin_user>

# 部署就绪自检（校验 production 模式、LLM key、题库/向量库）
PYTHONIOENCODING=utf-8 python -m backend.cli deploy-check
```

> 注:`deploy-check` 仍会检查 `backend/static/index.html` 是否存在(它假设后端自挂静态)。用 Caddy 直服方案时这一项会是 `false`——静态由 Caddy 提供,可忽略该项,以能正常访问 `https://localhost/` 为准。

### 4. 启动服务（三个进程 / 三个终端）

**终端 1 — 主后端（纯 API，:8000）**
```bash
PYTHONIOENCODING=utf-8 BACKEND_ENV=production \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**终端 2 — 支付服务（:8001）**
```bash
cd payment
PYTHONIOENCODING=utf-8 python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**终端 3 — Caddy（仓库根目录，读 `Caddyfile`）**
```bash
caddy trust     # 首次:安装本地 CA，让浏览器信任 localhost 证书
caddy run       # 前台运行
```

浏览器打开 **https://localhost**,用上面创建的管理员账号登录——侧栏会出现「管理后台」入口（`/admin`）。

> **局域网 / 其他设备访问**:Caddy 的本地 CA 只被本机信任,别的设备打开 `https://<你的IP>` 会提示证书不受信。要么在各设备导入/信任该 CA,要么直接上**公网域名**——把 `Caddyfile` 里的 `localhost` 换成你的域名,Caddy 会自动申请 Let's Encrypt 证书(需 80/443 可从公网访问)。
>
> **备选拓扑**:也可让后端自己挂静态(设 `BACKEND_STATIC_DIR=frontend/dist`,后端在 `/` 提供 SPA),Caddy 只把 `/payapi/*` 转发到 `:8001`、其余转发到 `:8000`。本项目默认推荐上面的「Caddy 直服静态」方案(少一层转发)。多核可给 uvicorn 加 `--workers N`(session 存 SQLite,单机多 worker 共享同一库文件即可;跨机部署不在本项目范围)。

---

## 生产部署注意事项

本项目当前为本地开发 / 演示配置，部署到生产环境前**必须**调整以下几处，否则存在安全或计费风险：

### 1. 会员校验目前"失败即放行"（fail-open）

为方便本地联调（支付服务常不启动），`frontend/src/hooks/useMembership.ts` 现在的逻辑是：
```ts
const isMember = query.isError || query.data?.active === true
```
即支付服务返回错误（宕机 / 网络异常 / 404）时，**默认把用户当作会员**，解锁错题巩固、综合复习、不限量 AI 解析等所有付费功能。

- **为什么这么写**：本地开发时支付服务（`payment/`，端口 8001）往往没启动，若默认锁定，学习助手/错题巩固等功能全部不可用，无法联调。
- **生产环境必须改回"失败即锁定"（fail-closed）**：把上面一行改为
  ```ts
  const isMember = query.data?.active === true
  ```
  并可将"出错解锁"的行为限制在开发模式下（`import.meta.env.DEV`）。否则一旦支付服务异常，全体用户免费获得会员权益，付费墙形同虚设。

### 2. 其他建议

- `/api/agent/chat`、`/api/agent/extract-plan` 目前无限流，生产环境应加 `rate_limiter`（`extract-plan` 会按天数循环出卷，需限制天数上限）。
- `.env` 中的 `LLM_API_KEY` 等密钥不要提交到仓库；演示账号 `demo / demo123` 应在生产环境禁用或改密。

---

## 子系统

按依赖顺序：

### 1. `ingestion/` — 题库摄入（离线）

从 EPUB 教辅书构建题库。六阶段管线 + 一次人工审核关卡：

1. `epub_to_md` — 脚本转换（无 LLM）
2. `chapter_splitter` — 按标题层级切树（无 LLM）
3. `knowledge_tree_builder` — LLM 归并出**两级知识点树**（一级=题型、二级=具体考点）
4. **★ 人工审核** `knowledge_tree_draft.json` → 固化为 `knowledge_tree.json`
5. `question_extractor` — LLM 逐章节结构化抽题
6. `loader` — 双写 SQLite + Chroma，`(book, chapter, stem_hash)` 幂等

题库入库后此子系统不再运行；AI Engine 只读。

详见 [`docs/question-bank-ingestion-design.md`](./docs/question-bank-ingestion-design.md)（Spec A）。

### 2. `ai_engine/` — AI 引擎

纯函数、无状态。五个模块：

| 模块 | 职责 |
|------|------|
| **Parser** | `user_query` → `GenerateRequest`；`revision_intensity` 由 LLM 从自然语言推断（不暴露给用户面板） |
| **Retriever** | 属性硬过滤（SQL）+ 语义向量检索（Chroma，取 Top-M 与硬过滤集在 Python 端求交） |
| **Reviser** | 三档改题：`original`（拷贝）/ `light`（保留结构改词汇）/ `fresh`（按 KP+难度新出题）；三层防御 + fallback |
| **Solutioner** | 单题按需生成解析；答错时额外解释用户所选选项为何错误（每次实时调 LLM，不缓存） |
| **Analyzer** | 用 Wilson score lower bound 计算 KP 掌握度，输出薄弱点画像 |

**关键设计**：
- 无 Verifier（答案唯一，LLM 直接产出新答案 + 后端字符串判等）
- Pipeline 单向无回路，任何一步抛异常都在后端层转 HTTP 错误
- LLM 通过 `instructor` 实现"JSON Mode + pydantic 校验 + 校验失败反馈重试"

详见 [`docs/ai-engine-design.md`](./docs/ai-engine-design.md)（Spec B）。

### 3. `backend/` — FastAPI 后端

11 个 HTTP 端点，把 AI Engine 封装为浏览器可用的接口。

- **鉴权**：用户名+密码 + bcrypt + SQLite session + httpOnly Cookie
- **持久化**：`papers` 表存整份 `Paper` 的 JSON（AI Engine 依然保持无状态，后端负责持久化）
- **判对错**：`backend/services/grading.py` 做规范化字符串比较（小写、trim、空白折叠、末尾标点忽略）
- **错误体统一**：`{ error_code, message, detail, trace_id }`；11 个稳定 `error_code` 供前端精确分派
- **速率限制**：软限制 `/papers/generate` 30/min、`/solutions` 60/min（个人项目、防意外循环）

详见 [`docs/backend-design.md`](./docs/backend-design.md)（Spec C）。

### 4. `agent/` — AI 学习助手

学习助手页背后的对话式 Agent（基于 OpenAI Agents SDK + DeepSeek）。采用**单 Agent + skill-as-markdown** 设计：技能写成 markdown（`agent/skills/*.md`）在启动时注入系统提示，Agent 按需调用工具完成任务。

- **工具**：`get_user_history`（按知识点汇总做题记录）、`get_example_questions`（题库随机取例题）、`generate_paper`（调 AI Engine 出卷并落库）、`implement_study_plan`（把自然语言计划解析成结构化的每日安排并逐日出卷）
- **两段式学习计划**：先用自然语言给出计划；用户说"帮我实施"时才调 `implement_study_plan` 真正生成每日试卷
- `user_id` 由后端从登录态注入，不经用户输入

### 5. `frontend/` — React + Vite 前端

产品名「墨卷」。登录后是六个功能页（详见开头「用户能做什么」）：

- **学习助手**（`/`）— 多轮对话 UI，Markdown 渲染（支持表格），出题后给「开始做题」入口
- **错题复习**（`/review`）— 本地错题本 + 错题巩固 / 综合复习两个出卷入口
- **学习计划**（`/study-plan`）— 每日卡片，逐日进入练习
- **我的试卷**（`/papers`、`/papers/:id`）— 列表 + 做题/复盘页；已交卷的直接回放上次结果，可重做，可从错题一键组巩固卷
- **掌握度**（`/mastery`）— 知识点树 + Wilson 分数条形 + 颜色标记
- **会员**（`/membership`）— 扫码订阅

技术栈：Vite + React + TypeScript + shadcn/ui + TanStack Query + React Router。所有 HTTP 走一个 `apiFetch` 薄封装；`ApiError` 按 `error_code` 分派处理（401 跳登录、429 toast、其它显 message）。

功能结构详见 [`docs/frontend-design.md`](./docs/frontend-design.md)（Spec D）；视觉规范（色板、字体、卷面语言、组件样式）详见 [`docs/frontend-visual-spec.md`](./docs/frontend-visual-spec.md)（Spec F）。

> **附加子系统:`payment/`(模拟支付)** — 独立 FastAPI 小服务(:8001),接支付宝**沙盒**当面付扫码,提供会员订阅(月/季/年)的下单、扫码、轮询查单与会员顺延;登录态通过转发 cookie 到主后端 `/api/auth/me` 校验,另有完全离线的 `MOCK_PAY` 演示模式。详见 [`payment/README.md`](./payment/README.md)。

### 6. `tests/`、`tests_e2e/` — 测试

四层测试结构：

| 层 | 范围 | 工具 | LLM |
|----|------|------|-----|
| L1 单元 | 单函数 | pytest / Vitest | mock |
| L2 后端集成 | FastAPI + SQLite + AI Engine | pytest + TestClient | monkeypatch |
| L3 前端组件 | 单组件 | Vitest + testing-library + msw | msw 返 fixture |
| L4 e2e | 真浏览器 → 全链路 | Playwright | 脚本化 client |

一个共享的 `ScriptedDeepSeekClient` 在 L2 与 L4 复用；e2e 通过测试专用端点 `/api/test/llm-scripts` 注入脚本。每晚跑一次 `live-smoke`（真 DeepSeek）探测契约漂移。

详见 [`docs/testing-design.md`](./docs/testing-design.md)（Spec E）。

---

## 关键技术选型

| 领域 | 选型 | 理由 |
|------|------|------|
| LLM | DeepSeek API（OpenAI 兼容） | 中文能力强、成本低；`instructor` 库支持成熟 |
| Embedding | Qwen Embedding 4B（本地） | 离线稳定，中文语义好；CI 用 fake 向量 |
| 关系存储 | SQLite | 单文件、无运维；个人项目量级足够 |
| 向量存储 | ChromaDB（持久化模式） | 本地无服务；`where` metadata 过滤 + Python 求交 |
| 结构化 LLM 输出 | `instructor` + JSON Mode + pydantic + 重试 | 三层防御，避免自研 200 行解析代码 |
| 后端 | FastAPI | pydantic 契约天然复用；OpenAPI 免费 |
| 前端 | Vite + React + shadcn/ui | AI 生成代码模板成熟；shadcn 组件质量高且可拷贝 |
| 部署 | 前后端合并（FastAPI StaticFiles 挂 `dist/`） | 单进程、单端口、零 CORS |

---

## 目录结构

```
English_Test_Paper_AI_Generator/
├── README.md                  # 本文件
├── docs/                      # 6 份设计 spec
│   ├── question-bank-ingestion-design.md  # Spec A
│   ├── ai-engine-design.md                # Spec B
│   ├── backend-design.md                  # Spec C
│   ├── frontend-design.md                 # Spec D
│   ├── testing-design.md                  # Spec E
│   └── frontend-visual-spec.md            # Spec F
│
├── shared/                    # 跨子系统共享层（唯一的依赖交汇点）
│   ├── schemas.py             # 全部 pydantic 契约
│   ├── storage.py             # SQLite + Chroma 门面
│   ├── embedding.py           # Qwen 4B 单例
│   ├── llm/deepseek.py        # DeepSeek 客户端 + instructor
│   └── config.py              # AppConfig
│
├── ingestion/                 # 子系统 1：题库摄入（Spec A）
├── ai_engine/                 # 子系统 2：AI 引擎（Spec B）
├── backend/                   # 子系统 3：FastAPI 后端（Spec C）
├── agent/                     # 子系统 4：AI 学习助手（Agents SDK + skills）
├── frontend/                  # 子系统 5：React 前端（Spec D）
├── payment/                   # 附加：模拟支付服务（:8001）
├── tests/ tests_e2e/          # 子系统 6：单元 / 集成 / 跨系统 e2e（Spec E）
│
└── data/                      # 运行时产物（gitignored）
    ├── raw_md/                # EPUB 转出的 md
    ├── chapters/              # 章节树 JSON
    ├── kb/knowledge_tree.json # 审核后的知识点树
    ├── extracted/             # LLM 抽出的题目 JSON
    ├── questions.db           # SQLite 主库
    ├── chroma/                # Chroma 向量持久化
    └── llm_traces/            # LLM 调用观测
```

---

## 里程碑

| ID | 目标 | 依赖 |
|----|------|------|
| M1 | Ingestion 全流程跑通，一本书完整入库 | — |
| M2 | AI Engine 五个模块 + Pipeline | M1 |
| M3 | LLM 观测 + CLI + Golden set 首跑 | M2 |
| M4 | AI Engine 端到端 CLI 验收 | M3 |
| M5 | Backend MVP（11 端点 + 鉴权 + 持久化 + 集成测试） | M4 |
| M6 | Frontend MVP（三页 + 组件测试） | M5 |
| M7 | Cross-system e2e（10 用例 + CI 分层 + live-smoke） | M6 |

## 核心原则

贯穿所有 spec 的几条硬约束：

1. **`shared/` 是唯一的跨子系统依赖交汇点**——`ingestion`/`ai_engine`/`backend` 之间不直接互相 import
2. **AI Engine 无状态**——一切持久化在后端层；`generate_paper` 是纯函数
3. **数据契约 pydantic 定义一次，全体复用**——契约变更 = 一次跨 spec 同步（有明确清单）
4. **知识点 id 一旦入库不变**——改 id 意味着级联重算所有引用，第一版不支持
5. **改题不改 `question_type` / `knowledge_point_ids` / `difficulty`**——否则答题记录的 KP 归属会错乱
6. **判对错永远是纯字符串比较，不调 LLM**——答案唯一无歧义（用户已确认）
7. **测试专用端点只在 test env 挂载**——生产构建永不暴露 `/api/test/*`
