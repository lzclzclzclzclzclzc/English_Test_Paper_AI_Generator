# 墨卷 · 中考英语 AI 练习系统

面向**中考英语**的 AI 出题与练习系统。你用一句话说出想练什么（"来 10 道现在完成时的单选"、"帮我制定 7 天学习计划"），系统就从题库检索、由 AI 加工，生成一份能直接在浏览器作答的试卷；交卷后自动判分、给出逐题解析，还能围绕错题定向再练、按薄弱考点制定学习计划。

选择**中考英语**原因：纯文字题目，不涉及图片。

> **状态**：核心链路已跑通——AI 学习助手对话出题、做题判分、错题巩固、学习计划、掌握度画像、积分充值均可用。

---

## 用户能做什么

登录后（默认演示账号 `demo / demo123`），`/` 是营销首页、工作台在 `/home`；左侧导航分四组（练习 / 出卷 / 助手 / 复盘）。主要能做的事：

| 页面 | 你能做的事 |
|------|-----------|
| **出卷**（一句话 / 主题 / 自选 / 整卷模拟） | 用一句话或结构化面板出卷；题型专项练习覆盖全部 10 题型（含作文），按语法/听力/阅读分色；整卷模拟支持限时 |
| **学习助手** | 和 AI 对话：说一句话让它出题、查某个考点的例题、或制定学习计划。出题完成后点「开始做题」直接进入试卷 |
| **背单词** | 间隔重复（SM-2）记忆中考词汇：每日新词 + 到期复习 + 当日重试队列，拼写作答后自评认识/模糊/忘了，另有背词进度画像 |
| **错题复习** | 做错的题会自动收进错题本，可勾选若干题让 AI 出一份针对性巩固卷，也可以按最近 N 天的答题记录出综合复习卷 |
| **学习计划** | 让 AI 根据你的历史正确率排出未来几天的每日练习，每天一份针对薄弱考点的卷子，点进去就能练 |
| **我的试卷** | 生成过的卷都在这里。没做完的随时接着做，做过的点进去直接看**上次的作答结果**（对错、你的答案 vs 正确答案、解析），也能一键重做 |
| **掌握度 / 学情报告** | 按知识点展示你的掌握程度（Wilson 分数），颜色标出薄弱点；学情报告打印友好 |
| **积分** | 注册送积分、每天再送一笔；出卷 / 讲解 / 批改 / 助手按次扣积分，扫码充值积分包（支付宝沙盒 / 离线演示模式） |

> 管理员账号登录后左侧多出「管理后台」（`/admin`）：用户管理、做题分析看板、积分与订单。

**做题体验**：交卷后每题标 ✓/✗，卷面右上角盖"对/总"红章；点每题下方「查看解析」由 AI 讲解——**答错的题会专门解释你选的那个选项为什么错**。作文交卷后给出内容/语言/组织三维评分与修改范文。

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
| 单项选择、词性转换、改写句子、听力（选择/判断/填词）、阅读理解、完形填空、阅读首字母填空、英语作文（共 10 题型） | 含图片的题目 |
| 背单词（间隔重复 SM-2） | 口语 / 手写识别 |
| 纯文本题目 | 多用户高并发 |
| AI 对话出题 / 错题巩固 / 学习计划 | 分布式部署、多进程 session 共享 |
| 用户名+密码本地登录 + 积分充值 | OAuth/SSO/邮箱验证 |
| 后端持久化试卷、答题、掌握度 | — |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              浏览器（React + Vite）                       │
│  学习助手(AI对话)   错题复习   学习计划   我的试卷   掌握度   积分          │
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
│  /api/writing/*    英语作文批改评分（内容/语言/组织三维度）                │
│  /api/vocabulary/* 间隔重复背单词（今日卡片 / 评分 / 进度 / 设置）         │
│  /api/users/me/mastery  掌握度画像                                         │
│  /api/admin/*      管理后台（用户 / 统计分析 / 积分 / 订单，需 admin）     │
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
                                     │  两个 SQLite + ChromaDB  │
                                     │  ─────────────────────── │
                                     │  questions.db（只读题库） │
                                     │   questions              │
                                     │   knowledge_points       │
                                     │   question_kp_map        │
                                     │   chroma/ (3 类题型向量)  │
                                     │  ──────────────────────  │
                                     │  app.db（用户数据,忽略） │
                                     │   users / sessions       │
                                     │   papers                 │
                                     │   attempts / attempt_items│
                                     │   study_plans            │
                                     │   writing_grade_results  │
                                     │   vocabulary_*（7 表）    │
                                     └──────────────────────────┘
                                                    ▲
                                                    │ 只写（离线）
                                     ┌──────────────────────────┐
                                     │  ingestion/（题库摄入）    │
                                     │  EPUB → md → 章节树 →     │
                                     │  ★人工审核知识点树 →       │
                                     │  脚本抽题 → Loader        │
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

**终端 2 — 前端开发服务器（端口 5173）**
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

生产形态用 **Caddy 反向代理**统一入口:Caddy 直接提供前端静态产物(`frontend/dist`,SPA 路由回退),并把 `/api/*` 转发到主后端(`:8000`,含积分 / 支付)。浏览器只访问 Caddy,天然同源,无需 CORS。后端退化为纯 API 进程。与本地开发的区别:`BACKEND_ENV=production`(httpOnly + **Secure** + SameSite=strict Cookie、关闭 CORS、不挂测试端点)、不带 `--reload`、前端跑 `build` 而非 `dev`。

仓库根目录已提供 [`Caddyfile`](./Caddyfile)。

> ⚠️ **必须走 HTTPS**:`BACKEND_ENV=production` 下 session cookie 带 `Secure` 标志(`backend/auth/session.py`),纯 HTTP 浏览器不会回传 → **登录后立刻掉登录态**。Caddy 站点地址用 `localhost` 会自动启用本地 HTTPS(见下),`https://localhost` 下 Secure cookie 正常工作。只想本机快速自测又不想装本地 CA,可改用上面「本地启动」的开发模式(`BACKEND_ENV=development` + Vite dev,走 http://localhost:5173)。

> ⚠️ **上线前务必先读下方「生产部署注意事项」**:`PAYMENT_MOCK`、演示账号、限流、价目等几处必须确认,否则有安全/计费风险。

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
Caddy 直接服务静态产物,因此**不需要** `BACKEND_STATIC_DIR`。真实收单需 `.env` 里 `PAYMENT_MOCK=false` + 沙盒/正式密钥(见 `docs/credits-design.md` § 4)。

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

> 支付 / 积分 2026-08-23 起在主后端内（`/api/payment`、`/api/credits`），不再有独立的 :8001 服务；
> 真实支付宝沙盒需在 `.env` 设 `PAYMENT_MOCK=false` + `ALIPAY_*`（见 `.env.example`、`docs/credits-design.md`）。

**终端 2 — Caddy（仓库根目录，读 `Caddyfile`）**
```bash
caddy trust     # 首次:安装本地 CA，让浏览器信任 localhost 证书
caddy run       # 前台运行
```

浏览器打开 **https://localhost**,用上面创建的管理员账号登录——侧栏会出现「管理后台」入口（`/admin`）。

> **局域网 / 其他设备访问**:Caddy 的本地 CA 只被本机信任,别的设备打开 `https://<你的IP>` 会提示证书不受信。要么在各设备导入/信任该 CA,要么直接上**公网域名**——把 `Caddyfile` 里的 `localhost` 换成你的域名,Caddy 会自动申请 Let's Encrypt 证书(需 80/443 可从公网访问)。
>
> **备选拓扑**:也可让后端自己挂静态(设 `BACKEND_STATIC_DIR=frontend/dist`,后端在 `/` 提供 SPA),Caddy 把全部请求转发到 `:8000`。本项目默认推荐上面的「Caddy 直服静态」方案(少一层转发)。多核可给 uvicorn 加 `--workers N`(session 存 SQLite,单机多 worker 共享同一库文件即可;跨机部署不在本项目范围)。

---

## 生产部署注意事项

本项目当前为本地开发 / 演示配置，部署到生产环境前**必须**调整以下几处，否则存在安全或计费风险：

### 1. 付费墙（2026-08-23 起已为服务端积分制）

旧版「前端 localStorage 配额 + 会员校验失败即放行」已整体删除：所有出卷 / AI 操作在后端按价目表
原子扣积分（`backend/services/credits`，余额不足 402 `credits.insufficient`），订单与支付宝沙盒
逻辑在主后端 `backend/services/payment`。上线前请确认 `.env` 里 `PAYMENT_MOCK=false`（否则
`/api/payment/dev/simulate-paid` 会被挂载，任何登录用户都能零元「支付」）、`ALIPAY_*` 与 `keys/*.pem`
就位，并按需调整 `CREDITS_SIGNUP_BONUS` / `CREDITS_DAILY_GRANT` 与
`backend/services/credits/pricing.py` 的价目。详见 `docs/credits-design.md`。

### 2. 其他建议

- `/api/agent/chat` 已加限流（`RATE_LIMIT_AGENT_PER_MIN`，默认 20）并按条扣积分；助手工具里出卷 / 学习计划按出卷价另扣，余额不足即停。
- `.env` 中的 `LLM_API_KEY` 等密钥不要提交到仓库；演示账号 `demo / demo123` 应在生产环境禁用或改密。

---

## 子系统

按依赖顺序：

### 1. `ingestion/` — 题库摄入（离线）

从 EPUB 教辅书构建题库。脚本 + 一次人工审核关卡（**ingestion 阶段不调用 LLM**——原设计的 LLM 抽题/归并已被脚本+人工取代）：

1. `epub_to_md` — 脚本转换
2. `chapter_splitter` — 按标题层级切树
3. **★ 人工归并知识点树** → 固化为 `knowledge_tree.json`
4. `apply-kp` / `assign-ids` — 回填知识点、分配全库稳定 id
5. `build-sqlite` — 写入 `data/questions.db`（bank-only）
6. `build-vec` — 3 类自由题型写入 Chroma（`single_choice`/`word_form`/`sentence_rewriting`）

另有背单词词表构建脚本（`build_vocabulary_wordlist.py` / `build_merged_vocabulary.py`），产出词表种子导入 `data/app.db`，详见 [`docs/vocabulary-design.md`](./docs/vocabulary-design.md)。

题库入库后此子系统不再运行；AI Engine 只读。

详见 [`docs/question-bank-ingestion-design.md`](./docs/question-bank-ingestion-design.md)（Spec A）。

### 2. `ai_engine/` — AI 引擎

纯函数、无状态。核心五模块 + 作文批改：

| 模块 | 职责 |
|------|------|
| **Parser** | `user_query` → `GenerateRequest`；`revision_intensity` 由 LLM 从自然语言推断（不暴露给用户面板） |
| **Retriever** | 属性硬过滤（SQL）+ 语义向量检索（Chroma，取 Top-M 与硬过滤集在 Python 端求交） |
| **Reviser** | 三档改题：`original`（拷贝）/ `light`（保留结构改词汇）/ `fresh`（按 KP 新出题）；三层防御 + fallback |
| **Solutioner** | 单题按需生成解析；答错时额外解释用户所选选项为何错误（每次实时调 LLM，不缓存） |
| **Analyzer** | 用 Wilson score lower bound 计算 KP 掌握度，输出薄弱点画像（含全站画像 `build_site_profile`，供管理后台分析） |
| **WritingGrader** | 英语作文三维批改（内容 8 / 语言 8 / 组织 4，共 20 分）+ 修改范文；`ai_engine/writing_grader.py`，由 `/api/writing/grade` 调用 |

**关键设计**：
- 无 Verifier（答案唯一，LLM 直接产出新答案 + 后端字符串判等）
- Pipeline 单向无回路，任何一步抛异常都在后端层转 HTTP 错误
- LLM 通过 `instructor` 实现"JSON Mode + pydantic 校验 + 校验失败反馈重试"

详见 [`docs/ai-engine-design.md`](./docs/ai-engine-design.md)（Spec B）。

### 3. `backend/` — FastAPI 后端

11 组路由（含 writing / vocabulary / admin），把 AI Engine 与各功能封装为浏览器可用的接口。

- **鉴权**：用户名+密码 + bcrypt + SQLite session + httpOnly Cookie；用户含 `role`/`status`（管理后台需 `role=admin`）
- **持久化**：`papers` 表存整份 `Paper` 的 JSON（AI Engine 依然保持无状态，后端负责持久化）；用户数据在 `data/app.db`
- **判对错**：`backend/services/grading.py` 做规范化字符串比较（小写、trim、空白折叠、末尾标点忽略）
- **错误体统一**：`{ error_code, message, detail, trace_id }`；稳定 `error_code` 供前端精确分派
- **速率限制**：软限制 `/papers/generate`、`/papers/revise` 30/min、`/solutions` 60/min、`/writing/grade` 10/min、`/agent/chat` 20/min（个人项目、防意外循环）
- **积分与支付**：每个出卷 / AI 端点按 `backend/services/credits/pricing.py` 扣积分（先扣今日赠送再扣余额，失败退回，402 `credits.insufficient`）；积分包购买走 `/api/payment/*`（支付宝沙盒 / 离线 mock），账本与订单在 `data/app.db`。详见 [`docs/credits-design.md`](./docs/credits-design.md)（Spec P）

详见 [`docs/backend-design.md`](./docs/backend-design.md)（Spec C）。

### 4. `agent/` — AI 学习助手

学习助手页背后的对话式 Agent（基于 OpenAI Agents SDK + DeepSeek）。采用**单 Agent + skill-as-markdown** 设计：技能写成 markdown（`agent/skills/*.md`）在启动时注入系统提示，Agent 按需调用工具完成任务。

- **工具**：`get_user_history`（按知识点汇总做题记录）、`get_example_questions`（题库随机取例题）、`generate_paper`（调 AI Engine 出卷并落库）、`implement_study_plan`（把自然语言计划解析成结构化的每日安排并逐日出卷）
- **两段式学习计划**：先用自然语言给出计划；用户说"帮我实施"时才调 `implement_study_plan` 真正生成每日试卷
- `user_id` 由后端从登录态注入，不经用户输入

### 5. `frontend/` — React + Vite 前端

产品名「墨卷」。`/` 是营销首页，登录后工作台在 `/home`；侧边栏分四组（练习 / 出卷 / 助手 / 复盘）共 21 个用户页 + 7 个管理页。主要页面：

- **工作台**（`/home`）— 登录后主入口
- **一句话出卷 / 主题出卷 / 自选组卷 / 整卷模拟**（`/generate`、`/themes`、`/practice/custom`、`/mock`）
- **题型专项练习**（`/practice`、`/practice/:slug`）— 一模板 10 配置（含作文），按语法/听力/阅读分色
- **每日一练**（`/daily`）
- **学习助手**（`/assistant`）— 多轮对话 UI，Markdown 渲染，出题后给「开始做题」入口
- **背单词 / 背词进度**（`/vocabulary`、`/vocabulary/progress`）— 间隔重复 SM-2
- **错题复习**（`/review`）— 本地错题本 + 错题巩固 / 综合复习出卷入口
- **学习计划**（`/study-plan`）— 每日卡片，逐日进入练习
- **我的试卷**（`/papers`、`/papers/:id`）— 列表 + 做题/复盘页；已交卷直接回放，可重做
- **掌握度 / 学情报告**（`/mastery`、`/report`）— 知识点树 + Wilson 分数
- **会员 / 设置**（`/membership`、`/settings`）
- **管理后台**（`/admin/*`）— 概览 / 分析 / 用户 / 会员 / 订单（需 admin）

做题页支持全部 10 题型（选择/填空/听力/阅读/首字母/作文），作文交卷后展示三维批改分数与范文。

技术栈：Vite + React + TypeScript + shadcn/ui + TanStack Query + React Router。所有 HTTP 走一个 `apiFetch` 薄封装；`ApiError` 按 `error_code` 分派处理（401 跳登录、429 toast、其它显 message）。

功能结构详见 [`docs/frontend-design.md`](./docs/frontend-design.md)（Spec D）；视觉规范（色板、字体、卷面语言、组件样式）详见 [`docs/frontend-visual-spec.md`](./docs/frontend-visual-spec.md)（Spec F）。

> **积分 / 充值**（2026-08-23 起）：`/credits` 页展示余额（注册赠送 + 每日赠送）、积分包、价目与流水；每个付费 CTA 旁标「≈ N 积分」，余额不足统一弹充值引导。原独立 `payment/` 服务已并入主后端，详见 [`docs/credits-design.md`](./docs/credits-design.md)。

### 6. `tests/`、`tests_e2e/` — 测试

四层测试结构：

| 层 | 范围 | 工具 | LLM |
|----|------|------|-----|
| L1 单元 | 单函数 | pytest / Vitest | mock |
| L2 后端集成 | FastAPI + SQLite + AI Engine | pytest + TestClient | monkeypatch |
| L3 前端组件 | 单组件 | Vitest + testing-library + msw | msw 返 fixture |
| L4 e2e | 真浏览器 → 全链路 | Playwright | 脚本化 client |

一个共享的 `ScriptedDeepSeekClient` 在 L2 与 L4 复用；e2e 通过测试专用端点 `/api/test/llm-scripts` 注入脚本。每晚跑一次 `live-smoke`（真 DeepSeek）探测契约漂移。

> 现状：L1/L2 已落地（`tests/` 下 pytest + Vitest 单元/集成），根目录另有 `test_writing_e2e.py` 等即席脚本；L4 Playwright e2e（`tests_e2e/`、`ScriptedDeepSeekClient`、`LLM_CLIENT_MODE`、CI 分层）是 Spec E 的目标设计，**尚未实现**，`/api/test/llm-scripts` 目前为占位（返回 noop）。

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
| 部署 | 生产用 Caddy 直服前端静态 + 反代 `/api`（开发用 Vite dev） | 同源零 CORS；少一层转发 |

---

## 目录结构

```
English_Test_Paper_AI_Generator/
├── README.md                  # 本文件
├── docs/                      # 设计 spec
│   ├── question-bank-ingestion-design.md  # Spec A（题库摄入）
│   ├── ai-engine-design.md                # Spec B（AI 引擎）
│   ├── backend-design.md                  # Spec C（后端）
│   ├── frontend-design.md                 # Spec D（前端功能）
│   ├── testing-design.md                  # Spec E（测试）
│   ├── frontend-visual-spec.md            # Spec F（视觉规范）
│   ├── admin-design.md                    # 管理后台
│   ├── agent-design.md                    # AI 学习助手
│   ├── vocabulary-design.md               # 背单词（间隔重复）
│   ├── writing-design.md                  # 英语作文批改
│   └── *-support-design.md                # 各题型（听力/长文/首字母填空）
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
├── tests/ tests_e2e/          # 子系统 6：单元 / 集成 / 跨系统 e2e（Spec E）
│
└── data/                      # 数据（题库与 chroma 已跟踪，其余 gitignored）
    ├── raw_md/                # EPUB 转出的 md
    ├── chapters/              # 章节树 JSON（含各题型）
    ├── kb/knowledge_tree.json # 审核后的知识点树
    ├── vocabulary/            # 背单词词表种子（moe core / shanghai basic）
    ├── questions.db           # SQLite 题库（只读、已跟踪）
    ├── app.db                 # 用户数据（gitignored，backend.cli init-db 创建）
    ├── agent_sessions.db      # 学习助手对话历史（gitignored）
    ├── chroma/                # Chroma 向量持久化（已跟踪）
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
| M8 | 题型扩展（听力/阅读/完形/首字母/作文）+ 前端重构（营销页、题型专项、整卷模拟、管理后台） | M6 |
| M9 | 背单词模块（SM-2 间隔重复）+ 用户库/题库分离（app.db / questions.db） | M8 |

## 核心原则

贯穿所有 spec 的几条硬约束：

1. **`shared/` 是唯一的跨子系统依赖交汇点**——`ingestion`/`ai_engine`/`backend` 之间不直接互相 import
2. **AI Engine 无状态**——一切持久化在后端层；`generate_paper` 是纯函数
3. **数据契约 pydantic 定义一次，全体复用**——契约变更 = 一次跨 spec 同步（有明确清单）
4. **知识点 id 一旦入库不变**——改 id 意味着级联重算所有引用，第一版不支持
5. **改题不改 `question_type` / `knowledge_point_ids`**——否则答题记录的 KP 归属会错乱（注：`difficulty` 字段已废弃，全系统不使用）
6. **判对错永远是纯字符串比较，不调 LLM**——答案唯一无歧义（用户已确认）
7. **测试专用端点只在 test env 挂载**——生产构建永不暴露 `/api/test/*`
