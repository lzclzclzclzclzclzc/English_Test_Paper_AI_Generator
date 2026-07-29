# Agent 设计文档

**创建日期**：2026-07-20
**范围**：`agent/` 子系统——学习教练 Agent 的架构设计、工具定义、Skill 封装、"帮我实施学习计划"的完整链路，以及前后端对应关系。
**说明**：本文档描述当前实现的现状（present tense）。

---

## 1. 整体架构

```
用户输入（自然语言）
    ↓
Coach Agent（单一 Agent）
  system prompt = 基础人设 + 题库知识点清单（真实 49 个 KP，按题型分组）+ skills/*.md
    ├── Skill: generate_paper.md  → 调用 generate_paper 工具
    ├── Skill: study_plan.md      → get_user_history + get_example_questions
    │                                （用户要求实施时）→ implement_study_plan
    └── 直接调用 get_example_questions（查例题）

工具层（4 个，均从 ContextVar 读取当前用户，不接受 user_id 参数）：
  generate_paper        → ai_engine.pipeline.generate_paper()
  implement_study_plan  → plan_extractor + retriever + reviser + storage（并行逐天出题）
  get_user_history      → attempts + attempt_items 表（只读）
  get_example_questions → questions 表（只读）
```

**单阶段设计**：Coach 在一次对话中直接完成所有工作。出题、查例题、制定计划、实施计划
都是在对话内由 Coach 直接调用相应工具完成，没有 sub-agent，也没有独立的"提取计划"接口。

- 出题完成后，Coach 在回复末尾输出 `<paper_ready paper_id=.../>` 标记，后端解析成
  `open_paper` 动作，前端据此跳转做题页。
- 制定学习计划只是普通的对话文本输出；用户之后说"帮我实施"时，Coach 直接调用
  `implement_study_plan` 工具当场生成每日试卷并落库。**不再有 `<study_plan_ready>` 标记，
  也不再有 `/extract-plan` 接口。**

---

## 2. 目录结构

```
agent/
├── __init__.py
├── coach.py            # 单一 Coach Agent，启动时装配 system prompt（KP 清单 + skills）
├── run.py              # 多轮对话 CLI 入口
├── seed_demo.py        # 演示数据注入脚本
├── tools.py            # 工具：get_user_history / get_example_questions / generate_paper / implement_study_plan
├── plan_extractor.py   # 自然语言计划 → StudyPlanData（instructor 校验）
└── skills/
    ├── __init__.py
    ├── study_plan.md       # Skill：制定 + 实施学习计划
    └── generate_paper.md   # Skill：自然语言出题
```

---

## 3. Coach Agent（`coach.py`）

### 3.1 职责

单一 Agent，启动时装配 system prompt，根据用户意图按 skill 指令执行，直接调工具，没有 sub-agent。

### 3.2 system prompt 组成

`create_coach_agent()` 用三段拼出 system prompt：

1. **基础人设 `_COACH_BASE_PROMPT`**：中考英语学习助手的角色、能力清单、"严禁编造题目"
   与"只能使用真实知识点"等硬规则。
2. **题库知识点清单 `_load_kp_catalog()`**：从 `data/questions.db` 的 `knowledge_points`
   表读出全部真实 KP（当前 49 个），按 `level1`（题型：单项选择 / 词形转换 / 改写句子）
   分组，每条列出 `level2` 中文名与 `kp_ id`。这样 Agent 出题 / 排计划时**只会挑选真实存在
   的知识点**，且题型与知识点所属分组一致，避免实施时出卷失败。读取失败或空库时回退为占位文本。
3. **Skill 指令 `_load_skills()`**：把 `skills/*.md` 按文件名排序、用 `---` 拼接注入。

### 3.3 Skill 加载机制

```python
def _load_skills() -> str:
    # 读取 agent/skills/*.md，按文件名排序，用 --- 分隔拼入 system prompt
```

Skill 与 KP 清单都只在 `create_coach_agent()` 装配时读取一次；热更新需要重新创建 Agent。

### 3.4 工具列表

| 工具 | 触发场景 |
|------|---------|
| `generate_paper` | 用户要出题 / 练习 / 生成试卷 |
| `get_user_history` | 制定学习计划时分析薄弱点 |
| `get_example_questions` | 用户要看例题，或计划里展示第 1 天预习例题 |
| `implement_study_plan` | 用户说"帮我实施这个计划"时，把计划文本落实为每日试卷 |

---

## 4. 工具定义（`tools.py`）

### 4.0 用户身份绑定（安全）

**所有工具都不接受 `user_id` 参数。** 当前操作用户由后端在每次 `Runner.run()` 前通过
`set_current_user_id(user.id)` 写入一个 `ContextVar`，工具内部用 `_require_user_id()` 读取。

原因是安全：LLM 与客户端传来的对话内容都**不能**决定工具操作谁的数据。若把 `user_id`
暴露为工具参数（或从 prompt / history 里取），用户可通过提示注入操作他人数据。绑定在
服务端上下文杜绝了这一点。

### 4.1 `get_user_history(window_days=30)`

查询**当前用户**最近 N 天做题记录，按 KP 汇总，按正确率升序返回（最薄弱在前）。
每条含 `knowledge_point_id / level2 / question_type / attempts / correct / accuracy`。

### 4.2 `get_example_questions(knowledge_point_id, count=3)`

从题库随机抽取该 KP 的例题，返回题干、选项、提示词、改写原句 / 要求、答案等。

### 4.3 `generate_paper(user_query, mode="fresh")`

包装 `ai_engine.pipeline.generate_paper()`，接收自然语言请求，出题后**立即落库**
（`storage.save_paper`，保存失败会明确报错，避免返回一个前端打不开的 paper_id），
返回试卷摘要（paper_id、标题、题数、改题档位、每题题干和答案）。

`mode` 取值：`fresh`（普通出题）/ `remediation`（错题巩固）/ `review`（复习薄弱点）。

### 4.4 `implement_study_plan(plan_text, start_date="")`

把 Coach 输出的自然语言学习计划落实为每日试卷并持久化，是"帮我实施"的核心。流程：

```
1. 校验 start_date（YYYY-MM-DD，空则取今天），格式非法直接返回 error
2. plan_extractor.extract_study_plan(plan_text, user_id, start_date)
   → StudyPlanData（instructor 校验 + 本地 KP 合法性校验）
3. 每一天 = 一个 GenerateRequest（可含多个 KP / 多种题型）：
   ThreadPoolExecutor 并行（max_workers ≤ 5）逐天 retrieve + build_paper + save_paper
4. 只把真正成功保存的天计入 total_days；全失败则返回 error
5. storage.save_study_plan(user_id, total_days, ...) 落库
6. 返回 { plan_id, total_days, days[] }
```

要点：**各天相互独立，并行生成**；结果按 `index` 排序保证顺序；`total_days` 反映
实际成功保存的天数而非原始意图；单天失败会在该天 `days[]` 条目里带 `error` 字段。

---

## 5. Skill 设计

### 5.1 `skills/generate_paper.md`——自然语言出题

**触发**：用户说"来 X 道题"、"出题"、"练习"、"来一套试卷"等。

**步骤**：
1. 从用户请求提取 `user_query` 和 `mode`（错题→remediation，薄弱点→review，其他→fresh）；
   工具自动使用当前登录用户，skill 明确告知模型"你不需要也无法指定用户 ID"。
2. 调 `generate_paper` 工具。
3. 按格式展示试卷标题与题量，并在末尾追加 `<paper_ready paper_id="..." />` 标记（不加任何解释）。

### 5.2 `skills/study_plan.md`——制定与实施学习计划

**Phase 1（制定，输出自然语言计划）**：
1. 调 `get_user_history` 获取做题记录。
2. 按正确率分析薄弱点，把相关知识点组织成每天的"专题"（<0.4 优先多练、0.4~0.7 巩固、
   >0.7 不纳入、样本 <5 仅参考）。**一天可安排多个相关知识点（一个专题），也可单点一天**；
   所有知识点必须来自 system prompt 中的真实 KP 清单，题型一致。
3. 对第 1 天的知识点调 `get_example_questions` 展示 3 道例题。
4. 输出完整计划文本，并提示用户"如需生成每日试卷，请说'帮我实施这个计划'"。

**Phase 2（实施，用户主动要求时）**：
当用户说"帮我实施 / 实施计划 / 按计划来"等：
1. 找到上文最近一次输出的完整计划文本。
2. 调 `implement_study_plan(plan_text, start_date=今天)`。
3. 成功则告知用户可去"学习计划"页面查看每日试卷；返回 `error` 则告知失败原因。

---

## 6. 结构化提取（`plan_extractor.py`）

`extract_study_plan(plan_text, user_id, start_date)` 用 `shared/llm/deepseek.py::structured()`
+ `instructor` + pydantic，从自然语言计划文本中提取结构化数据（schema 失败自动 retry，最多 3 次）：

```python
class StudyPlanDay(BaseModel):
    """一天的练习安排 = 一个出题需求（可含多个知识点/题型，对应 GenerateRequest）。"""
    index: int                       # 第几天，从 1 开始
    theme: str = ""                  # 当天主题，如"名词专题"
    knowledge_points: list[str]      # 当天要练的 KP id 列表，必须全部来自合法清单，至少一个
    question_types: list[QuestionType]  # 当天涉及题型（与所选 KP 对应）
    total_questions: int             # 当天总题量（1~20）
    note: str = ""                   # 备注

class StudyPlanData(BaseModel):
    user_id: str
    total_days: int
    days: list[StudyPlanDay]
```

关键点（与旧"一天一个知识点"设计不同）：

- **一天携带多个知识点**：`knowledge_points` 是列表，一个专题的多个考点都要放进来；
  提取 prompt 明确要求不能只保留一个。一天对应一张多考点试卷（一个 `GenerateRequest`）。
- `user_id` 由调用方（`implement_study_plan` 从 ContextVar 取的会话用户）覆盖，不信任 LLM 提取值。
- 提取后做**本地 KP 合法性校验**：任何不在 `knowledge_points` 表里的 id 直接 `raise ValueError`。
- 若传入 `start_date`，按 `start_date + (index-1) days` 计算每天日期并写入 `note`。

---

## 7. "帮我实施"完整链路

```
对话内：用户"帮我制定学习计划"
    ↓ Coach: get_user_history → 分析 → 输出自然语言计划文本（含第1天例题）
用户"帮我实施这个计划"
    ↓ Coach: implement_study_plan(plan_text, start_date=今天)
        ├── plan_extractor.extract_study_plan → StudyPlanData（多考点/天）
        ├── ThreadPoolExecutor 并行逐天：retrieve + build_paper + save_paper
        ├── storage.save_study_plan（旧计划被覆盖为非最新）
        └── 返回 { plan_id, total_days, days[] }
    ↓ Coach 告知"已生成，去'学习计划'页面查看"
前端：GET /api/agent/study-plans/latest → /study-plan 页面（每天 → /papers/{id}）
```

整个过程都在**一次对话内**完成——没有前端点击"一键实施"再打独立接口的两阶段流程，
实施动作就是 Coach 调 `implement_study_plan` 工具。

---

## 8. 前后端接口

### 8.1 后端接口

| 接口 | 用途 |
|------|------|
| `POST /api/agent/chat` | Agent 对话入口（接收新消息，返回回复 + 可选动作） |
| `POST /api/agent/chat/clear` | "新对话"：清空该用户的服务端会话历史（204） |
| `GET /api/agent/study-plans/latest` | 返回用户最新学习计划（无则 null） |

> 旧的 `POST /api/agent/extract-plan` 已移除——实施改由 `implement_study_plan` 工具在对话内完成。

**`POST /api/agent/chat` 设计**：

```python
class AgentChatRequest(BaseModel):
    message: str            # 只有新消息，没有 history 字段
    # user_id 不在请求体里，由后端从 session 注入

class AgentChatResponse(BaseModel):
    reply: str              # Agent 最终输出文本
    action: dict | None     # 后端解析出的动作指令（见下），没有 history 字段
```

**服务端会话记忆（`SQLiteSession`）**：对话历史存在服务端，按用户键
（`session_id = f"user_{user_id}"`，DB 在 `data/agent_sessions.db`）。客户端**只发新消息**，
不回传历史；SDK 从会话库加载 / 保存历史，客户端无法伪造 system / assistant 轮（防提示注入）。
`/chat/clear` 调 `clear_session()` 实现"新对话"。

**用户身份绑定**：后端在 `Runner.run()` 前调 `set_current_user_id(user.id)`，工具从
ContextVar 读取；不作为 system 消息注入，也不依赖用户在对话里输入。

```python
# backend/api/agent.py（要点）
@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(body: AgentChatRequest, user: User = Depends(current_user)):
    set_current_user_id(user.id)              # 服务端绑定当前用户
    agent = create_coach_agent()
    session = _user_session(user.id)          # SQLiteSession，服务端记忆
    result = await Runner.run(agent, input=body.message, session=session)
    reply = result.final_output or ""
    action = _parse_action(reply)             # 只解析 <paper_ready />
    return AgentChatResponse(reply=reply, action=action)
```

**`action` 字段**：后端解析回复里的标记，转成前端可直接执行的指令。当前只有一种：

```python
{"type": "open_paper", "paper_id": "abc123"}   # 出题完成 → 前端跳转 /papers/abc123
# 普通对话 / 例题 / 计划文本 → action = null，内容直接在 reply 里
```

`_parse_action()` 仅匹配 `<paper_ready paper_id="..." />`。学习计划不再有标记，实施由用户
下一句话触发工具，因此对话回复不需要 `study_plan_ready` 动作。

### 8.2 前端页面

**主界面变为聊天界面**，聊天输入框 + 对话气泡是所有功能的唯一入口：

| 用户意图 | Agent 行为 | 前端响应 |
|---------|-----------|---------|
| "来 10 道介词题" | 调 `generate_paper` + 输出 `<paper_ready/>` | `action.type == "open_paper"` → 跳转 `/papers/{paper_id}` |
| "帮我制定 7 天学习计划" | 查历史 + 分析，输出文字计划 | `action == null` → 计划文本展示在气泡里 |
| "帮我实施这个计划" | 调 `implement_study_plan` 落库 | `action == null` → 告知去 `/study-plan` 查看 |
| "查一下介词的例题" | 调 `get_example_questions` | `action == null` → 例题直接在气泡里 |
| "现在完成时怎么用" | 直接回答 | `action == null` → 回答在气泡里 |

**保留页面**：`/papers/{paper_id}`（做题）、`/study-plan`（学习计划，读 `study-plans/latest`）、
`/mastery`（掌握度报告）。

**会话历史管理**：历史全部在服务端（`SQLiteSession`），前端不维护、不回传，只发新消息；
"新对话"按钮打 `/chat/clear`。刷新页面不会丢历史（服务端持久化）。

---

## 9. 数据库

- **`agent_sessions.db`**：`SQLiteSession` 的会话库，按 `user_{id}` 存对话历史（SDK 管理）。
- **学习计划持久化**：`implement_study_plan` 调 `storage.save_study_plan(user_id, total_days, data)`
  落库，`storage.get_latest_study_plan(user_id)` 取最新计划供 `/study-plans/latest`。计划中每天的
  多考点试卷通过 `storage.save_paper` 写入 papers 表，`/papers/{id}` 即可做题。

---

## 10. 数据流总览

```
聊天界面
  ↓ POST /api/agent/chat（只发新消息）
后端 set_current_user_id(user.id) → Runner.run(coach, input=message, session=SQLiteSession)
  ├── Skill generate_paper → generate_paper 工具 → 落库 → <paper_ready/> → action=open_paper
  ├── Skill study_plan(制定) → get_user_history + get_example_questions → 计划文本（action=null）
  └── Skill study_plan(实施) → implement_study_plan 工具
        → plan_extractor → StudyPlanData（多考点/天）
        → ThreadPoolExecutor 并行逐天 retriever + reviser → save_paper + save_study_plan
        → /study-plan 页面（GET /study-plans/latest；每天 → /papers/{id}）
```

---

## 11. 开放问题

1. **逐天生成耗时**：实施计划时已用 `ThreadPoolExecutor` 并行逐天生成（每天内部
   `build_paper` 也并发改题），显著缩短总耗时。若计划很长仍可能偏慢，可进一步改为
   异步任务 + 轮询状态。
2. **Skill / KP 清单热更新**：system prompt 在 `create_coach_agent()` 装配时读取一次；
   题库或 skill 变更后需重新创建 Agent 才生效。当前每次 `/chat` 都重新创建 Agent，
   因此天然拿到最新内容，但也带来每请求的装配开销，可视需要缓存。
