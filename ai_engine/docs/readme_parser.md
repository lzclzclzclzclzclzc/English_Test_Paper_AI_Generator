# Parser Module

将用户的自然语言请求解析为结构化的 `GenerateRequest`。

## Overview

Parser 是 AI Engine 的入口模块，负责将用户的自然语言输入（如"来十道单选原题"）转换为系统可理解的结构化请求。核心特点是 `revision_intensity`（改题尺度）由 LLM 自动推断，而非用户显式选择。

## Data Flow

```
用户自然语言输入
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Parser 模块                                │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐           │
│  │ 1.加载KP   │ →  │ 2.构建Prompt│ →  │ 3.LLM调用   │           │
│  │  目录      │    │ (Jinja2)   │    │ (JSON Mode) │           │
│  └────────────┘    └────────────┘    └──────┬─────┘           │
│                                              │                 │
│                                              ▼                 │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐           │
│  │ 5.输出      │ ←  │ 4.本地校验  │ ←  │ ParserLLM  │           │
│  │ Generate   │    │ (过滤非法)  │    │ Response   │           │
│  │ Request    │    └────────────┘    └────────────┘           │
│  └────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
传给 Retriever 模块
```

## Usage

### Basic Usage

```python
from ai_engine.parser import parse

# 解析用户请求
req = parse("来十道单选原题")

# 输出示例
print(req.mode)                # "fresh"
print(req.question_types)      # ["single_choice"]
print(req.total_questions)     # 10
print(req.revision_intensity)  # "original" ⭐ LLM推断
```

### Different Modes

```python
# fresh 模式（默认）- 全新生成
parse("来 10 道现在完成时的单项选择")

# remediation 模式 - 基于错题练习
from shared.schemas import WrongItemRef

parse(
    "针对这些错题多练几道",
    mode="remediation",
    wrong_items=[
        WrongItemRef(
            source_question_id="q_00123",
            question_type="single_choice",
            knowledge_point_ids=["kp_sc_verbs"]
        )
    ]
)

# review 模式 - 基于历史复习
from shared.schemas import MasteryProfile

parse(
    "帮我复习最近一个月的薄弱点",
    mode="review",
    mastery=MasteryProfile(
        weak_kps=["kp_sc_verbs", "kp_sc_prepositions"],
        dominant_types=["single_choice"],
        total_attempts_considered=50
    ),
    user_id="u_001",
    review_window_days=30
)
```

### Test Result

输入 `"来十道单选原题"` 的解析结果：

| 字段 | 值 |
|------|------|
| `mode` | `"fresh"` |
| `question_types` | `["single_choice"]` |
| `total_questions` | `10` |
| `revision_intensity` | `"original"` |
| `type_distribution` | `{"single_choice": 10}` |

## 运行测试 (Run Test)

### 前置条件

1. 已配置 `.env` 文件（含 `LLM_API_KEY`）
2. 已加载数据库 `data/questions.db`（执行过 `ingestion build-sqlite`）
3. 在项目根目录运行

### 测试命令

在项目根目录执行以下命令，可快速验证 Parser 模块：

```bash
python -c "
from ai_engine.parser import parse
import json

req = parse('来十道单选原题')
print('=== Parser 测试结果 ===')
print(f'mode:                {req.mode}')
print(f'question_types:      {req.question_types}')
print(f'total_questions:     {req.total_questions}')
print(f'revision_intensity:  {req.revision_intensity}')
print(f'type_distribution:   {req.type_distribution}')
print(f'knowledge_points:    {req.knowledge_points}')
print()
print('完整 JSON 输出：')
print(json.dumps(req.dict(exclude_none=True), ensure_ascii=False, indent=2))
"
```

### 预期输出

```
=== Parser 测试结果 ===
mode:                fresh
question_types:      ['single_choice']
total_questions:     10
revision_intensity:  original
type_distribution:   {'single_choice': 10}
knowledge_points:    []

完整 JSON 输出：
{
  "mode": "fresh",
  "knowledge_points": [],
  "knowledge_points_exclude": [],
  "question_types": ["single_choice"],
  "total_questions": 10,
  "type_distribution": {"single_choice": 10},
  "per_kp_min": 0,
  "revision_intensity": "original",
  "free_text": "来十道单选原题"
}
```

### 不同输入测试

可替换输入字符串以测试不同推断结果：

```bash
# 测试 fresh 档（用户提到"重新出"）
python -c "from ai_engine.parser import parse; r = parse('重新出五道现在完成时的单选题'); print(f'intensity={r.revision_intensity}, types={r.question_types}, n={r.total_questions}')"

# 测试 light 档（用户只说"练习"）
python -c "from ai_engine.parser import parse; r = parse('来几道介词练习巩固一下'); print(f'intensity={r.revision_intensity}, kps={r.knowledge_points}')"

# 测试 review 模式
python -c "from ai_engine.parser import parse; r = parse('帮我复习最近一个月的错题', mode='review', user_id='u_001', review_window_days=30); print(f'mode={r.mode}, intensity={r.revision_intensity}')"
```

### 推断规则对照表

| 输入示例 | 预期 `revision_intensity` |
|---------|--------------------------|
| "来十道单选原题" | `original` |
| "重新出五道题" | `fresh` |
| "来几道练习巩固一下" | `light` |

## Configuration

### `.env` File

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.scnet.cn/api/llm/v1
LLM_MODEL=DeepSeek-V4-Flash
LLM_MAX_CONCURRENCY=4
LLM_MAX_RETRIES=3
```

### Config Chain

```
.env → shared/config.py → shared/llm/deepseek.py → OpenAI Client
```

## Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_query` | `str` | Yes | 用户自然语言请求 |
| `mode` | `Literal["fresh", "remediation", "review"]` | No | 默认 `"fresh"` |
| `wrong_items` | `list[WrongItemRef] \| None` | No | 错题列表（remediation模式） |
| `mastery` | `MasteryProfile \| None` | No | 掌握度画像（review模式） |
| `user_id` | `str \| None` | No | 用户ID |
| `review_window_days` | `int \| None` | No | 复习时间窗口 |

## Output Structure

```python
GenerateRequest(
    mode: str,                              # 生成模式
    knowledge_points: list[str],            # 目标知识点
    knowledge_points_exclude: list[str],    # 排除知识点
    question_types: list[str],              # 题型列表
    total_questions: int,                   # 题目总数（≤ 30）
    type_distribution: dict[str, int],      # 题型分布
    per_kp_min: int,                        # 每个知识点最少题目数
    revision_intensity: str,                # ⭐ 改题尺度（LLM推断）
    free_text: str,                         # 用户原始请求
    wrong_items: list[WrongItemRef] | None,
    user_id: str | None,
    review_window_days: int | None,
)
```

## Design Decisions

### revision_intensity 由 LLM 推断

改题尺度不是用户输入，而是 LLM 根据用户自然语言自动识别：

| 档位 | 触发条件 |
|------|----------|
| `"original"` | 用户提到"原题"、"真题"、"别改" |
| `"fresh"` | 用户提到"重新出"、"全新的"、描述具体情境 |
| `"light"` | 默认：用户只说"练习"、"巩固" |

### Three-Layer Defense

1. **Layer 1**: JSON Mode — DeepSeek API 强制返回 JSON
2. **Layer 2**: pydantic Validation — `instructor` 自动校验和重试
3. **Layer 3**: Local Validation — 过滤非法 KP id、截断题目数、调整分布

### Stateless Design

Parser 不写任何持久化存储，纯函数式设计，便于测试和复用。

## Files

```
ai_engine/
├── parser.py           # 核心解析逻辑
├── prompts/
│   ├── parser.md       # Prompt 模板（含 few-shot）
│   └── __init__.py     # Prompt 加载器
├── errors.py           # 错误定义
└── __init__.py         # 模块入口
```

## Related Modules

- [shared/schemas.py](../shared/schemas.py) — 数据契约定义
- [shared/config.py](../shared/config.py) — 配置管理
- [shared/llm/deepseek.py](../shared/llm/deepseek.py) — LLM 客户端
