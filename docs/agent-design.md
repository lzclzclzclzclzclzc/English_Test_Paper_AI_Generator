# Agent 设计文档

**创建日期**：2026-07-20  
**范围**：`agent/` 子系统——学习教练 Agent 的架构设计、工具定义、Skill 封装、"一键实施学习计划"的完整链路设计，以及前后端对应变化。

---

## 1. 整体架构

```
用户输入（自然语言）
    ↓
Coach Agent（单一 Agent，加载所有 skill 指令）
    ├── Skill: generate_paper.md  → 调用 generate_paper 工具
    ├── Skill: study_plan.md      → 调用 get_user_history + get_example_questions
    └── 直接调用 get_example_questions（查例题）

工具层：
  generate_paper    → ai_engine.pipeline.generate_paper()
  get_user_history  → attempts + attempt_items 表（只读）
  get_example_questions → questions 表（只读）
```

**Phase 1**（对话内）：Agent 直接输出试卷内容 / 学习计划 + `<study_plan_ready />` 标记

**Phase 2**（用户点击"一键实施"后）：
```
前端 POST /api/agent/extract-plan
    ↓ plan_extractor.py：structured() 提取 StudyPlanData
    ↓ 逐天调用 retriever + reviser 生成试卷
    ↓ 存入 papers 表
返回 StudyPlanResponse → /study-plan 页面
```

---

## 2. 目录结构

```
agent/
├── __init__.py
├── coach.py            # 单一 Coach Agent，启动时加载 skills/*.md
├── run.py              # 多轮对话 CLI 入口
├── seed_demo.py        # 演示数据注入脚本
├── tools.py            # 工具：get_user_history / get_example_questions / generate_paper
├── plan_extractor.py   # Phase 2：自然语言计划 → StudyPlanData（instructor 校验）
└── skills/
    ├── __init__.py
    ├── study_plan.md       # Skill：制定学习计划
    └── generate_paper.md   # Skill：自然语言出题
```

---

## 3. Coach Agent（`coach.py`）

### 3.1 职责

单一 Agent，启动时从 `skills/*.md` 读取所有 skill 指令注入 system prompt。
根据用户意图按 skill 指令执行，直接调工具，没有 sub-agent。

### 3.2 Skill 加载机制

```python
def _load_skills() -> str:
    # 读取 agent/skills/*.md，按文件名排序，用 --- 分隔注入 system prompt
```

Skill 只在 Agent 启动时加载一次，长期运行时热更新需要重启。

### 3.3 工具列表

| 工具 | 触发场景 |
|------|---------|
| `generate_paper` | 用户要出题/练习/生成试卷 |
| `get_user_history` | 制定学习计划时分析薄弱点 |
| `get_example_questions` | 用户要看例题，或计划里展示第1天预习题 |

---

## 4. 工具定义（`tools.py`）

### 4.1 `get_user_history(user_id, window_days=30)`

查询用户最近 N 天做题记录，按 KP 汇总，按正确率升序返回。

### 4.2 `get_example_questions(knowledge_point_id, count=3)`

从题库随机抽取该 KP 的例题，返回题干、选项、答案。

### 4.3 `generate_paper(user_query, user_id, mode="fresh")`

包装 `ai_engine.pipeline.generate_paper()`，接收自然语言请求，返回试卷摘要（标题、题数、每题题干和答案）。

`mode` 取值：`fresh`（普通出题）/ `remediation`（错题巩固）/ `review`（复习薄弱点）

---

## 5. Skill 设计

### 5.1 `skills/generate_paper.md`——自然语言出题

**触发条件**：用户说"来X道题"、"出题"、"练习"等。

**步骤**：
1. 从用户请求提取 user_query、user_id、mode
2. 调用 `generate_paper` 工具
3. 按格式展示试卷（题干、选项、答案）

### 5.2 `skills/study_plan.md`——制定学习计划

**触发条件**：用户说"制定学习计划"、"帮我安排复习"等。

**步骤**：
1. 调 `get_user_history` 分析薄弱点
2. 按正确率安排 N 天计划
3. 对第 1 天知识点调 `get_example_questions` 展示例题
4. 输出自然语言计划，末尾追加 `<study_plan_ready user_id="..." total_days="..." />`

---

## 6. Phase 2：Plan Extractor（`plan_extractor.py`）

`extract_study_plan(plan_text, user_id, start_date)` 用 `instructor` + pydantic 从自然语言计划文本中提取结构化数据：

```python
class StudyPlanDay(BaseModel):
    index: int
    knowledge_point_id: str   # 必须是 kp_ 开头的真实 id
    kp_name: str
    question_type: QuestionType
    count: int = Field(ge=8, le=10)
    note: str = ""

class StudyPlanData(BaseModel):
    user_id: str
    total_days: int
    days: list[StudyPlanDay]
```

- `user_id` 由调用方（后端 session）覆盖，不信任 LLM 提取值
- `start_date` 由前端传入，计算每天具体日期注入 `note`
- `instructor` 负责格式校验，失败自动 retry（最多 3 次）

---

## 7. "一键实施"完整链路

### 7.1 Phase 1：前端检测标记 → 渲染按钮

```ts
function extractStudyPlanMeta(message: string) {
  const match = message.match(
    /<study_plan_ready\s+user_id="([^"]+)"\s+total_days="(\d+)"\s*\/>/
  );
  if (!match) return null;
  return { userId: match[1], totalDays: parseInt(match[2]) };
}
```

解析成功 → 在消息气泡下方渲染"一键实施"按钮，把完整消息文本存入 state 备用。

### 7.2 Phase 2：点击按钮 → 后端提取 JSON → 逐天出题

**新增后端接口**：

```
POST /api/agent/extract-plan
```

请求体：
```python
class ExtractPlanRequest(BaseModel):
    plan_text: str          # Agent 输出的完整计划文本
    start_date: str | None  # YYYY-MM-DD，默认今天；user_id 由 session 注入
```

后端内部：
```
1. plan_extractor.extract_study_plan(plan_text, user_id, start_date)
   ← instructor 校验，最多 3 次 retry
2. 逐天调用 retriever.retrieve + reviser.build_paper
3. 存入 papers 表
4. 返回 StudyPlanResponse
```

响应体：
```python
class StudyPlanResponse(BaseModel):
    user_id: str
    total_days: int
    papers: list[StudyPlanPaper]

class StudyPlanPaper(BaseModel):
    day_index: int
    date: str | None        # YYYY-MM-DD
    paper_id: str
    title: str
    knowledge_point_id: str
    kp_name: str
```

### 7.3 日期 + 覆盖逻辑

- `start_date` 由前端传入（默认今天），后端按 `start_date + (index-1) days` 算每天日期
- 新计划覆盖旧计划：按 `user_id` 找最新 `study_plan` 记录，标记为 `superseded`，写入新计划（需 `study_plans` 表，见 §9）

---

## 8. 前后端变化汇总

### 8.1 新增后端接口

| 接口 | 用途 |
|------|------|
| `POST /api/agent/chat` | Agent 对话入口（接收用户消息，返回 Agent 回复） |
| `POST /api/agent/extract-plan` | Phase 2：从计划文本提取 JSON + 逐天出题 |
| `GET /api/study-plans/latest` | 返回用户最新有效学习计划 |

**`POST /api/agent/chat` 设计**：

```python
class AgentChatRequest(BaseModel):
    message: str
    history: list[dict] = []    # 前端维护对话历史，格式与 SDK to_input_list() 一致
    # user_id 不在请求体里，由后端从 session 注入

class AgentChatResponse(BaseModel):
    reply: str                  # Agent 最终输出文本（例题、计划说明、问答等）
    history: list[dict]         # 更新后的对话历史，前端下次请求时带上
    action: dict | None         # 后端解析出的动作指令，前端按此跳转/渲染按钮（见下）
```

**`action` 字段设计**：后端解析 Agent 回复中的标记，转换成前端可直接执行的指令，
前端不需要自己 parse 文本：

```python
# action 示例
{"type": "open_paper",  "paper_id": "abc123"}          # 出题完成 → 前端跳转到 /papers/abc123
{"type": "study_plan_ready", "total_days": 7}           # 计划完成 → 前端渲染"一键实施"按钮
# 普通对话 / 例题展示 → action = null，结果直接在 reply 文本里
```

**user_id 注入方式**：后端从 session 拿到 `current_user.id`，在每次 `Runner.run()` 前
把它作为 system 消息注入到 history 最前面，Agent 直接从上下文读取，不依赖用户在对话里输入：

```python
# backend/api/agent.py
@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(body: AgentChatRequest, user: User = Depends(current_user)):
    system_ctx = {
        "role": "system",
        "content": f"当前用户ID：{user.id}",
    }
    full_input = [system_ctx] + body.history + [{"role": "user", "content": body.message}]
    result = await Runner.run(agent, input=full_input)
    reply = result.final_output
    action = _parse_action(reply)   # 解析 paper_ready / study_plan_ready 标记
    return AgentChatResponse(
        reply=reply,
        history=list(result.to_input_list()),
        action=action,
    )
```

这样所有工具调用（`generate_paper`、`get_user_history`）里的 `user_id` 参数，
模型从 system 消息里读取，安全可靠，前端无需传递也无需感知。

### 8.2 前端页面变化

**主界面（`/`）变为聊天界面**，`GenerateForm` 替换为聊天输入框 + 对话气泡，是所有功能的唯一入口：

| 用户意图 | Agent 行为 | 前端响应 |
|---------|-----------|---------|
| "来10道介词题" | 调 `generate_paper`，回复说"已生成试卷" | `action.type == "open_paper"` → 自动跳转 `/papers/{paper_id}` |
| "帮我制定7天学习计划" | 查历史+分析，输出文字计划+标记 | `action.type == "study_plan_ready"` → 气泡下方渲染"一键实施"按钮 → 点击跳转 `/study-plan` |
| "查一下介词的例题" | 调 `get_example_questions`，把例题写进 reply | `action == null` → 例题内容直接展示在气泡里 |
| "现在完成时怎么用" | 直接回答 | `action == null` → 回答展示在气泡里 |

**保留的页面**（不变）：
- `/papers/{paper_id}`：做题页面，复用现有实现
- `/study-plan`：学习计划页面，展示每天试卷
- `/mastery`：掌握度报告页

**移除**：原 `HomePage` 的 `GenerateForm`（出题表单），统一由聊天入口替代。

### 8.3 Agent 侧标记补充

`generate_paper.md` skill 在出题完成后，末尾追加：

```
<paper_ready paper_id="（实际 paper_id）" />
```

后端 `_parse_action()` 同时识别两种标记：

```python
def _parse_action(reply: str) -> dict | None:
    m = re.search(r'<paper_ready\s+paper_id="([^"]+)"\s*/>', reply)
    if m:
        return {"type": "open_paper", "paper_id": m.group(1)}
    m = re.search(r'<study_plan_ready\s+user_id="[^"]+"\s+total_days="(\d+)"\s*/>', reply)
    if m:
        return {"type": "study_plan_ready", "total_days": int(m.group(1))}
    return None
```

### 8.4 对话历史管理

前端维护 `history: list<dict>`，每次请求带上，后端传给 `Runner.run()`，响应里返回更新后的 history。后端无状态，对话上下文全在前端（刷新页面丢失，持久化见 §11 开放问题 #1）。

---

## 9. 数据库扩展（study_plans 表）

```sql
CREATE TABLE study_plans (
    id           TEXT PRIMARY KEY,       -- UUID hex
    user_id      TEXT NOT NULL REFERENCES users(id),
    created_at   TIMESTAMP NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active',  -- active / superseded
    total_days   INTEGER NOT NULL,
    plan_json    TEXT NOT NULL            -- 完整 StudyPlanData JSON
);
CREATE INDEX idx_study_plans_user ON study_plans(user_id, status);
```

新计划写入时，把该用户所有 `status='active'` 的旧计划更新为 `superseded`。

---

## 10. 数据流总览

```
聊天页面（/chat）
  ↓ POST /api/agent/chat
后端 Runner.run(coach_agent)
  ├── Skill: generate_paper → generate_paper tool → Paper 摘要 → 展示在聊天里
  └── Skill: study_plan → get_user_history + get_example_questions
        → 自然语言计划 + <study_plan_ready />
        → 前端渲染"一键实施"按钮
            ↓ POST /api/agent/extract-plan
            plan_extractor → StudyPlanData
            逐天 retriever + reviser → papers 表
            → /study-plan 页面（每天 → /papers/{id}）
```

---

## 11. 开放问题

1. **Agent 对话历史存储**：目前前端维护 history，刷新页面丢失。若需要持久化，后端加 `agent_sessions` 表存 history JSON。
2. **出题后的做题流程**：Agent 出的题目（`generate_paper` 工具返回的 `paper_id`）需要能跳转到做题页面。回复里可以附带 paper_id，前端识别后渲染"开始做题"按钮。
3. **逐天生成耗时**：7 天计划逐天调 `generate_paper()`，70 次 LLM 调用约 30-60s。可改为异步：先返回 `plan_id`，后台生成，前端轮询状态。
4. **`generate_paper` 工具的 user_id 来源**：已解决——后端在每次 `Runner.run()` 前将 `user_id` 作为 system 消息注入，Agent 从上下文读取，不依赖用户在对话里输入（见 §8.1）。
