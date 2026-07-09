# English Test Paper AI Generator

面向**中考英语**的 AI 试卷生成系统：学生用自然语言描述需求（如"来 20 道现在完成时的选择题，中等难度"），系统从题库检索、由 LLM 加工，生成一份可在浏览器直接作答的完整试卷；支持基于错题的针对性巩固和基于历史答题的综合复习。

选择**中考英语**原因：纯文字题目，不涉及图片。

> **状态**：后端 M5 MVP 已完成（FastAPI 11 端点、鉴权、SQLite 持久化、判分、集成测试与 CLI smoke）；前端与跨系统 e2e 待后续里程碑。

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
| 基于错题/历史的针对性生成 | 多用户高并发 |
| 用户名+密码本地登录 | OAuth/SSO/邮箱验证 |
| 后端持久化试卷、答题、掌握度 | 分布式部署、多进程 session 共享 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              浏览器（React + Vite）                       │
│  登录页          主页                    掌握度页                         │
│  ─────         生成 + 做题 + 提交         知识点树 + 颜色标记              │
└─────────────────────────┬────────────────────────────────────────────────┘
                          │ HTTP + Cookie
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        FastAPI 后端（backend/）                           │
│  ─────────────────────────────────────────────────────────────────────   │
│  /api/auth/*     注册、登录、登出、当前用户                                │
│  /api/papers/*   生成、重出、读取、列表                                    │
│  /api/solutions  按需生成单题解析                                          │
│  /api/attempts   提交答题 + 判对错 + 落库                                  │
│  /api/users/me/mastery  掌握度画像                                         │
│                                                                          │
│  职责：鉴权、试卷持久化、答题记录、规范化字符串判对错、错误统一封装        │
└─────────────────┬──────────────────┬─────────────────────────────────────┘
                  │                  │
                  │ 函数调用          │ 读写
                  ▼                  ▼
┌──────────────────────────────┐   ┌──────────────────────────────────────┐
│    AI Engine（ai_engine/）    │   │       shared/（共享层）              │
│  ─────────────────────────── │   │  ─────────────────────────────────── │
│  Parser     自然语言 → Request│   │  schemas.py    全体 pydantic 契约    │
│  Retriever  属性过滤 + 向量检索│   │  storage.py    SQLite + Chroma 门面   │
│  Reviser    三档改题策略      │   │  embedding.py  Qwen 4B（本地）        │
│  Solutioner 按需生成解析      │   │  llm/deepseek.py  DeepSeek 客户端     │
│  Analyzer   Wilson 掌握度画像 │   │  config.py     AppConfig 单例         │
│                              │   │                                      │
│  纯函数、无状态、只调 LLM 与  │   │  唯一的跨子系统边界；防依赖倒置        │
│  shared/                     │   │                                      │
└──────────────────────────────┘   └──────────────────────────────────────┘
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

## 五个子系统

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
| **Solutioner** | 单题按需生成解析；原题解析写回题库缓存 |
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

组内联调与接口速查见 [`docs/backend-api.md`](./docs/backend-api.md)。

### 4. `frontend/` — React + Vite 前端

三页 MVP：

- **登录页** — 注册/登录 tab；Zod 表单校验
- **主页** — 生成表单 + 试卷视图 + 成绩视图（提交后展开）
- **掌握度页** — 知识点树 + Wilson 分数条形 + 颜色标记

技术栈：Vite + React + TypeScript + shadcn/ui + TanStack Query + React Router。所有 HTTP 走一个 `apiFetch` 薄封装；`ApiError` 按 `error_code` 分派处理（401 跳登录、429 toast、其它显 message）。

详见 [`docs/frontend-design.md`](./docs/frontend-design.md)（Spec D）。

### 5. `tests_e2e/` — 跨系统测试

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
├── docs/                      # 5 份设计 spec
│   ├── question-bank-ingestion-design.md  # Spec A
│   ├── ai-engine-design.md                # Spec B
│   ├── backend-design.md                  # Spec C
│   ├── frontend-design.md                 # Spec D
│   ├── testing-design.md                  # Spec E
│   └── backend-api.md                     # 后端协作接口手册
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
├── frontend/                  # 子系统 4：React 前端（Spec D）
├── tests_e2e/                 # 子系统 5：跨系统 e2e（Spec E）
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
