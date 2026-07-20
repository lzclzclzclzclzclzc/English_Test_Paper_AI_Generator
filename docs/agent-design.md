# Agent 设计文档

**创建日期**：2026-07-20  
**范围**：`agent/` 子系统——学习教练 Agent 的架构设计、工具定义、Skill 封装、以及"一键实施学习计划"的完整链路设计。

---

## 1. 整体架构

```
用户输入（自然语言）
    ↓
Coach Agent（角色定义 + 意图路由）
    ↓ 调用 skill
Study Plan Skill（sub-agent，制定学习计划）
    ├── 工具：get_user_history（查历史做题记录）
    └── 工具：get_example_questions（查题库例题）
    ↓ 返回含结构化 JSON 的计划文本
Coach Agent 输出最终回复
    ↓
前端解析 JSON → 渲染"一键实施"按钮
    ↓ 用户点击
POST /api/study-plans（后端）
    ↓ 逐天调用 generate_paper()
返回 StudyPlan（含每天的 Paper）→ /study-plan 页面
```

---

## 2. 目录结构

```
agent/
├── __init__.py
├── coach.py           # Coach Agent：角色定义 + 挂载 skill
├── run.py             # 多轮对话 CLI 入口
├── seed_demo.py       # 演示数据注入脚本
├── tools.py           # 工具函数：get_user_history / get_example_questions
└── skills/
    ├── __init__.py
    └── study_plan.py  # Study Plan Skill（sub-agent）
```

---

## 3. Coach Agent（`coach.py`）

### 3.1 职责

**只做角色定义和意图路由**，不含业务逻辑：

- 接收用户自然语言输入
- 判断意图（制定计划 → 调用 `create_study_plan` skill；其他问题 → 直接回答）
- 把 skill 返回的计划文本输出给用户

### 3.2 System Prompt 要点

```
你是一位中考英语学习助手。
当学生请求制定学习计划时，调用 create_study_plan 工具。
对其他英语学习问题直接回答。
```

### 3.3 多轮对话

`run.py` 维护 `history = result.to_input_list()`，每轮把历史追加传入 `Runner.run()`，实现上下文连续的多轮对话。

---

## 4. 工具定义（`tools.py`）

### 4.1 `get_user_history(user_id, window_days=30)`

查询用户最近 N 天的做题记录，按知识点汇总：

```json
{
  "user_id": "u_demo",
  "window_days": 30,
  "total_items": 153,
  "kp_summary": [
    {
      "knowledge_point_id": "kp_sc_prepositions",
      "level2": "介词",
      "question_type": "single_choice",
      "attempts": 16,
      "correct": 3,
      "accuracy": 0.188
    },
    ...
  ]
}
```

`kp_summary` 按 `accuracy` 升序排列（最薄弱在前），供 skill 直接使用。

### 4.2 `get_example_questions(knowledge_point_id, count=3)`

从题库随机抽取该知识点的例题，帮助学生预览难度：

```json
{
  "knowledge_point_id": "kp_sc_prepositions",
  "count": 3,
  "questions": [
    {
      "id": "q_00623",
      "question_type": "single_choice",
      "stem": "Many students go to school ______ public bus.",
      "options": [{"label": "A", "text": "for"}, ...],
      "answer": "C"
    }
  ]
}
```

---

## 5. Study Plan Skill（`skills/study_plan.py`）

### 5.1 职责

接收用户ID + 计划天数 → 调工具 → 输出自然语言学习计划 + 末尾嵌入触发标记。

**只负责生成人类可读的计划，不输出 JSON。** JSON 提取是 Phase 2 的事（由后端在用户点击"一键实施"后触发）。

### 5.2 执行步骤

1. 调 `get_user_history` 获取做题记录
2. 分析薄弱知识点：
   - `accuracy < 0.4`：严重薄弱，每个 KP 占 2 天（第1天练习，第2天巩固）
   - `0.4 ~ 0.7`：需要巩固，每个 KP 占 1 天
   - `accuracy > 0.7`：已掌握，不纳入计划
   - 做题数 < 5：样本不足，仅参考
3. 对第 1 天的知识点调 `get_example_questions` 获取 3 道例题展示
4. 输出完整自然语言计划（见 §5.3）
5. **在计划末尾追加触发标记**（见 §5.4）

### 5.3 自然语言计划格式

```
📊 当前状况分析
- 已练习 X 道题，覆盖 Y 个知识点
- 严重薄弱（<40%）：知识点名 正确率%
- 需要巩固（40-70%）：知识点名 正确率%

📆 N 天学习安排
第1天 | 知识点：XXX（正确率 XX%）| 建议练习 10 道单选题
第2天 | 知识点：XXX 巩固 | 建议练习 8 道题
...
最后1天 | 综合复习

📝 第1天预习例题
[3 道从题库获取的例题]
```

### 5.4 触发标记（Phase 1 信号）

计划末尾追加一个 XML 标记，前端检测到它就渲染"一键实施"按钮：

```
<study_plan_ready user_id="u_demo" total_days="7" />
```

**为什么用 XML 标记而不是直接嵌 JSON**：
- Phase 1 只需要告诉前端"计划已就绪，可以实施"，不需要暴露结构化数据
- 标记简单、不会污染自然语言内容、前端正则一行就能提取
- 真正的 JSON 在用户点击后才生成，避免每次对话都浪费一次 `structured()` 调用

---

## 6. "一键实施"完整链路

### 6.1 Phase 1：前端检测标记 → 渲染按钮

前端渲染 skill 输出时，检测消息末尾是否有 `<study_plan_ready .../>` 标记：

```ts
function extractStudyPlanMeta(message: string) {
  const match = message.match(
    /<study_plan_ready\s+user_id="([^"]+)"\s+total_days="(\d+)"\s*\/>/
  );
  if (!match) return null;
  return { userId: match[1], totalDays: parseInt(match[2]) };
}
```

解析成功 → 在消息气泡下方渲染"一键实施"按钮，同时把 `userId` 和完整计划文本（`message`）存入 React state 备用。

### 6.2 Phase 2：点击按钮 → 后端提取 JSON → 逐天出题

用户点击"一键实施"→ 前端 POST 到 `POST /api/study-plans/extract`，把计划文本发给后端：

```python
class ExtractStudyPlanRequest(BaseModel):
    plan_text: str          # skill 输出的完整自然语言计划
    start_date: str | None  # 可选，格式 YYYY-MM-DD，默认今天
```

**后端 Phase 2 内部流程**：

```
1. 调 client.structured(response_model=StudyPlanData, prompt=plan_text)
   ← instructor 负责 JSON 格式校验，失败自动 retry（最多3次）
   ← pydantic 验证 knowledge_point_id / question_type 枚举 / count 范围
2. 按 start_date 给每天分配具体日期
3. 逐天调 retriever.retrieve + reviser.build_paper 生成试卷
4. 存入 papers 表，返回 StudyPlanResponse
```

**`StudyPlanData` pydantic 模型**（instructor 校验目标）：

```python
class StudyPlanDayData(BaseModel):
    index: int
    knowledge_point_id: str         # 必须是合法 KP id
    kp_name: str
    question_type: QuestionType     # Literal 枚举，非法值自动触发 retry
    count: int = Field(ge=8, le=10) # 8~10，范围约束
    note: str = ""

class StudyPlanData(BaseModel):
    user_id: str
    total_days: int
    days: list[StudyPlanDayData]
```

**请求/响应体**：

```python
class CreateStudyPlanRequest(BaseModel):
    plan_text: str
    start_date: str | None = None   # user_id 由 session 注入

class StudyPlanResponse(BaseModel):
    user_id: str
    total_days: int
    papers: list[StudyPlanPaper]

class StudyPlanPaper(BaseModel):
    day_index: int
    date: str | None                # YYYY-MM-DD，若无 start_date 则 null
    paper_id: str
    title: str
    knowledge_point_id: str
    kp_name: str
```

### 6.3 日期 + 覆盖逻辑

- `start_date` 由前端传入（默认今天），后端按 `start_date + (index-1) days` 计算每天日期
- **新计划覆盖旧计划**：后端按 `user_id` 查最新的 `study_plan` 记录，标记为 `superseded`，再写入新计划（需要 `study_plans` 表，见 §8 开放问题 3）

### 6.4 前端学习计划页面（`/study-plan`）

路由：`GET /study-plan`（新增，需要登录）。

数据来源：`GET /api/study-plans/latest` 返回最新有效计划。

页面结构：

```
📅 我的 7 天学习计划（2026-07-20 起）

2026-07-20（第1天）| 介词 | 10 道单选      [开始练习 →]
2026-07-21（第2天）| 介词 巩固 | 8 道单选   [开始练习 →]
2026-07-22（第3天）| 动词时态 | 10 道单选   [开始练习 →]
...
```

每个"开始练习"跳转到 `/papers/{paper_id}`，复用现有做题页面。

---

## 7. 数据流总览

```
Coach Agent
  └── Study Plan Skill（Phase 1）
        ├── get_user_history  ──► attempts + attempt_items 表（只读）
        └── get_example_questions ──► questions 表（只读）
        └── 输出自然语言计划 + <study_plan_ready user_id="..." total_days="..." />

前端检测标记 → 渲染"一键实施"按钮

用户点击"一键实施"（Phase 2）
  └── POST /api/study-plans/extract  { plan_text, start_date }
        └── client.structured() 提取 StudyPlanData（instructor 校验）
        └── 按日期逐天调 retriever + reviser 生成试卷
        └── 存入 papers 表 + study_plans 表
        └── 返回 StudyPlanResponse

前端 /study-plan 页面
  └── 每天 → /papers/{paper_id}（复用现有做题页面）
```
```

---

## 8. 开放问题

1. **JSON 输出稳定性**：LLM 不一定每次都输出合法 JSON。前端解析时应宽松处理（try/catch），解析失败就不渲染按钮，不报错。后续可给 skill 加 few-shot 示例加强格式稳定性。

2. **逐天生成耗时**：7 天计划逐天调 `generate_paper()`，如果每天 10 道 light 改写，共 70 次 LLM 调用，耗时可能较长（30-60s）。可以改为异步生成（后端先返回 `plan_id`，前端轮询状态）。

3. **学习计划持久化**：目前 `StudyPlan` 没有独立的数据库表，只靠 papers 表的 `paper_id` 列表关联。未来如果需要查历史计划，需要新增 `study_plans` 表。

4. **Parser 绕过**：直接用 JSON 数据组装 `GenerateRequest`，不经过 Parser 的 LLM 推断，`revision_intensity` 硬编码为 `"light"`。如果用户在制定计划时说了"要原题"，这个信息目前会丢失。可以在 JSON 里加一个 `revision_intensity` 字段让 skill 填写。
