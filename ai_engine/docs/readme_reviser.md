# Reviser Module

将候选题目集按照 `revision_intensity` 三档策略加工为最终试卷。

## Overview

Reviser 是 AI Engine 的核心模块，负责将 Retriever 返回的候选题集合转换为最终试卷。支持三档改题策略：
- **original**：直接拷贝原题，不调用 LLM
- **light**：保留题型/KP/难度不变，改写词汇、数值和情境
- **fresh**：参考原题风格，全新出题

核心特点是三层防御机制 + 失败 fallback，确保输出质量和系统稳定性。

## Data Flow

```
RetrievalResult（候选题集合）
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Reviser 模块                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1. 根据 revision_intensity 选择策略                        │ │
│  └─────────────────────────┬──────────────────────────────────┘ │
│                            │                                     │
│     ┌──────────────────────┼──────────────────────┐             │
│     ▼                      ▼                      ▼             │
│  original               light                 fresh             │
│  (0次LLM)           (1次LLM/题)           (1次LLM/题)           │
│     │                      │                      │             │
│     ▼                      ▼                      ▼             │
│  _copy_question    _revise_one + LLM    _revise_one + LLM       │
│     │                      │                      │             │
│     └──────────────────────┼──────────────────────┘             │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2. 三层防御校验                                             │ │
│  │    Layer 1: pydantic Schema 校验                           │ │
│  │    Layer 2: 不变量校验（题型/KP/难度必须匹配）               │ │
│  │    Layer 3: 答案格式校验（单选答案 ∈ A/B/C/D）              │ │
│  └─────────────────────────┬──────────────────────────────────┘ │
│                            │                                     │
│              ┌─────────────┴─────────────┐                      │
│              ▼                           ▼                      │
│           通过                      不通过                        │
│              │                           │                      │
│              ▼                           ▼                      │
│        使用改写结果               fallback 到原题                 │
│              │                           │                      │
│              └─────────────┬─────────────┘                      │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3. 并发处理 + 批装配 build_paper()                          │ │
│  │    ThreadPoolExecutor(max_workers=4)                        │ │
│  └─────────────────────────┬──────────────────────────────────┘ │
│                            │                                     │
│                            ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 4. 输出 Paper（最终试卷）                                   │ │
│  │    包含标题、题目列表、总分、元数据                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
传给前端展示或保存到数据库
```

## Usage

### Basic Usage

```python
from ai_engine.reviser import build_paper
from shared.schemas import (
    GenerateRequest,
    Question,
    RetrievedItem,
    RetrievalResult,
)

# 创建请求（包含 revision_intensity）
req = GenerateRequest(
    mode="fresh",
    question_types=["single_choice"],
    total_questions=5,
    revision_intensity="light",  # 保留结构改词汇
    free_text="来几道动词时态的单选题",
)

# 创建候选题目
questions = [Question(id="q_0", ...), Question(id="q_1", ...)]
retrieval = RetrievalResult(
    items=[RetrievedItem(question=q, score=0.9) for q in questions]
)

# 构建试卷
paper = build_paper(req, retrieval)

# 输出示例
print(paper.title)           # "单选5道练习"
print(paper.total_score)     # 10
print(len(paper.items))      # 5
print(paper.metadata["llm_calls"])  # 5
```

### Three Revision Strategies

#### 1. Original Mode（直接拷贝）

```python
req = GenerateRequest(
    ...,
    revision_intensity="original"  # 不调用 LLM
)
paper = build_paper(req, retrieval)
# LLM Calls: 0
```

**适用场景**：用户明确要求"原题"、"真题"、"别改"

#### 2. Light Mode（保留结构改词汇）

```python
req = GenerateRequest(
    ...,
    revision_intensity="light"  # 每道题调用 1 次 LLM
)
paper = build_paper(req, retrieval)
# LLM Calls: N（题目数）
```

**适用场景**：用户说"练习"、"巩固"、"多做几道"，默认档位

**改题效果**：
```
原题：Tom ______ to school every day.
改后：My mother ______ breakfast for us every morning.
```

#### 3. Fresh Mode（全新出题）

```python
req = GenerateRequest(
    ...,
    revision_intensity="fresh"  # 每道题调用 1 次 LLM
)
paper = build_paper(req, retrieval)
# LLM Calls: N（题目数）
```

**适用场景**：用户说"重新出"、"全新的"、描述了具体情境需求

**改题效果**：
```
原题参考：Tom ______ to school every day.
新题：She often ______ books in the library.
```

## Test Results

### 测试数据

| 模式 | 题目数 | LLM 调用 | 失败数 | 结果 |
|------|--------|----------|--------|------|
| **ORIGINAL** | 3 | 0 | 0 | ✅ 通过 |
| **LIGHT** | 2 | 2 | 0 | ✅ 通过 |
| **FRESH** | 2 | 2 | 0 | ✅ 通过 |

### 详细对比

#### ORIGINAL 模式

```
原题：Tom ______ to school every day.
     A. go / B. goes / C. going / D. went

结果：完全相同（0 次 LLM 调用）
```

#### LIGHT 模式

```
原题：Tom ______ to school every day.

改后：My mother ______ breakfast for us every morning.
     A. cook / B. cooks / C. cooking / D. cooked
```

**特点**：保留主谓结构和时态考点，替换主语、动词和宾语

#### FRESH 模式

```
原题参考：Tom ______ to school every day.

新题：She often ______ books in the library.
     A. read / B. reads / C. reading / D. readed
```

**特点**：题干、选项全部全新生成，围绕相同知识点

## 运行测试 (Run Test)

### 前置条件

1. 已配置 `.env` 文件（含 `LLM_API_KEY`）
2. 已加载数据库 `data/questions.db`（执行过 `ingestion build-sqlite`）
3. 已有题目数据 `data/chapters/shanghai_2021_yimo.json`
4. 在项目根目录运行

### 测试命令（一次跑三档对比）

以下命令会从真实题库加载 3 道单选题，分别用 `original` / `light` / `fresh` 三档策略生成试卷，并打印对比结果：

```bash
python -c "
import json
from ai_engine.reviser import build_paper
from shared.schemas import GenerateRequest, Question, RetrievedItem, RetrievalResult

# 从真实题库加载 3 道单选题
with open('data/chapters/shanghai_2021_yimo.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)
questions = [Question(**q) for q in raw[:3]]
retrieval = RetrievalResult(items=[RetrievedItem(question=q, score=0.9) for q in questions])

# 三档策略对比
for intensity in ['original', 'light', 'fresh']:
    req = GenerateRequest(
        mode='fresh',
        question_types=['single_choice'],
        total_questions=3,
        revision_intensity=intensity,
        free_text=f'测试 {intensity} 模式',
    )
    paper = build_paper(req, retrieval)
    print(f'=== {intensity.upper()} 模式 ===')
    print(f'标题:           {paper.title}')
    print(f'总分:           {paper.total_score}')
    print(f'LLM 调用次数:   {paper.metadata[\"llm_calls\"]}')
    print(f'失败数:         {len(paper.metadata[\"revision_failures\"])}')
    for it in paper.items:
        print(f'  [{it.index}] 题型={it.question.question_type} 分值={it.score} 溯源={it.source_question_id} 模式={it.revision_mode}')
        print(f'      题干: {it.question.stem[:60] if it.question.stem else \"(无)\"}')
        print(f'      答案: {it.question.answer}')
        if it.revision_notes:
            print(f'      备注: {it.revision_notes}')
    print()
"
```

### 预期输出

```
=== ORIGINAL 模式 ===
标题:           单选原题3道练习
总分:           6
LLM 调用次数:   0
失败数:         0
  [1] 题型=single_choice 分值=2 溯源=q_00001 模式=original
      题干: John is good at English，so he rarely makes mistakes in Eng...
      答案: B
  [2] 题型=single_choice 分值=2 溯源=q_00002 模式=original
      题干: Which of the following words is pronounced as/heɪt/?
      答案: B
  [3] 题型=single_choice 分值=2 溯源=q_00003 模式=original
      题干: Which of the following underlined parts is different in pr...
      答案: B

=== LIGHT 模式 ===
标题:           单选3道练习
总分:           6
LLM 调用次数:   3
失败数:         0
  [1] 题型=single_choice 分值=2 溯源=q_00001 模式=light
      题干: <LLM 改写后的题干，保留结构替换词汇>
      答案: B
  [2] 题型=single_choice 分值=2 溯源=q_00002 模式=light
      题干: <LLM 改写后的题干>
      答案: B
  [3] 题型=single_choice 分值=2 溯源=q_00003 模式=light
      题干: <LLM 改写后的题干>
      答案: B

=== FRESH 模式 ===
标题:           单选新题3道练习
总分:           6
LLM 调用次数:   3
失败数:         0
  [1] 题型=single_choice 分值=2 溯源=q_00001 模式=fresh
      题干: <LLM 全新生成的题干>
      答案: A
  [2] 题型=single_choice 分值=2 溯源=q_00002 模式=fresh
      题干: <LLM 全新生成的题干>
      答案: C
  [3] 题型=single_choice 分值=2 溯源=q_00003 模式=fresh
      题干: <LLM 全新生成的题干>
      答案: B
```

> 注：LIGHT/FRESH 档的题干和答案由 LLM 实时生成，每次运行结果不同。重点观察：
> - **题型、知识点、难度保持不变**（不变量校验）
> - **答案格式合法**（A/B/C/D）
> - **LLM 调用次数**：original=0，light/fresh=题目数
> - **失败数**：正常情况下为 0，若网络异常会自动 fallback 到原题

### 单档快速测试

如只想快速验证某一档，可使用以下简化命令：

```bash
# ORIGINAL 档（无 LLM 调用，最快验证）
python -c "
import json
from ai_engine.reviser import build_paper
from shared.schemas import GenerateRequest, Question, RetrievedItem, RetrievalResult
with open('data/chapters/shanghai_2021_yimo.json', 'r', encoding='utf-8') as f:
    questions = [Question(**q) for q in json.load(f)[:2]]
paper = build_paper(
    GenerateRequest(mode='fresh', question_types=['single_choice'], total_questions=2, revision_intensity='original', free_text='原题'),
    RetrievalResult(items=[RetrievedItem(question=q, score=0.9) for q in questions])
)
print(f'标题: {paper.title}, 总分: {paper.total_score}, LLM调用: {paper.metadata[\"llm_calls\"]}')
"

# LIGHT 档（每题 1 次 LLM 调用）
python -c "
import json
from ai_engine.reviser import build_paper
from shared.schemas import GenerateRequest, Question, RetrievedItem, RetrievalResult
with open('data/chapters/shanghai_2021_yimo.json', 'r', encoding='utf-8') as f:
    questions = [Question(**q) for q in json.load(f)[:2]]
paper = build_paper(
    GenerateRequest(mode='fresh', question_types=['single_choice'], total_questions=2, revision_intensity='light', free_text='练习'),
    RetrievalResult(items=[RetrievedItem(question=q, score=0.9) for q in questions])
)
print(f'标题: {paper.title}, 总分: {paper.total_score}, LLM调用: {paper.metadata[\"llm_calls\"]}')
for it in paper.items:
    print(f'  [{it.index}] {it.question.stem[:50]}... 答案={it.question.answer}')
"
```

### 三档对比速查

| 模式 | LLM 调用 | 失败 fallback | 关键看点 |
|------|----------|---------------|---------|
| **ORIGINAL** | 0 次 | 不需要 | 原题直接拷贝，最快 |
| **LIGHT** | N 次 | 回退原题 | 题型/KP/难度不变，词汇情境替换 |
| **FRESH** | N 次 | 回退原题 | 全新题干和选项，围绕相同 KP |

## Three-Layer Defense

### Layer 1: Schema Validation（pydantic）

由 `instructor` 自动处理，确保返回的 JSON 符合 `RevisedQuestion` 结构。如果 LLM 返回格式错误，会自动重试（最多 2 次）。

### Layer 2: Invariant Validation（不变量校验）

确保改写后的题目与原题在核心属性上保持一致：

```python
# 必须保持不变的字段
revised.question_type == original.question_type
set(revised.knowledge_point_ids) == set(original.knowledge_point_ids)
```

如果校验失败，**fallback 到原题**。

### Layer 3: Answer Format Validation（答案格式校验）

根据题型检查答案格式：

| 题型 | 校验规则 |
|------|----------|
| `single_choice` | 答案 ∈ {"A", "B", "C", "D"}，选项数 = 4，标签完整 |
| `word_form` | 答案非空 |
| `sentence_rewriting` | 答案非空 |

如果校验失败，**fallback 到原题**。

## Failure Fallback

当 LLM 改题失败时（任何原因），系统会自动 fallback 到原题：

```python
# LLM 调用失败
try:
    revised = llm_client.structured(...)
except Exception as e:
    return _copy_question(question), f"revision failed: {str(e)}"

# 不变量校验失败
if not _validate_revision(question, revised):
    return _copy_question(question), "revision failed: invariant violation"
```

**关键点**：
- 内容等价于 `original` 档
- `revision_mode` 仍为原档位（`light`/`fresh`）
- `revision_notes` 记录失败原因
- 失败题目索引记录在 `Paper.metadata["revision_failures"]`

## Concurrent Processing

使用 `ThreadPoolExecutor` 并发处理多道题：

```python
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = []
    for question in questions:
        futures.append(executor.submit(_revise_one, question, ...))
    
    for future in as_completed(futures):
        rq, notes = future.result()
```

**并发数**：默认 4，可以通过配置调整。

## Default Scores

根据题型自动分配分值：

| 题型 | 分值 |
|------|------|
| `single_choice` | 2 分 |
| `word_form` | 1 分 |
| `sentence_rewriting` | 3 分 |

## Auto-Generated Title

根据请求参数自动生成试卷标题：

```python
# 示例
"单选原题3道练习"   # question_types + revision_intensity + total_questions
"单选新题5道练习"   # question_types + "新题" + total_questions
"单选5道练习"       # question_types + total_questions
```

## Output Structure

```python
Paper(
    paper_id: str,                        # UUID hex
    title: str,                           # 自动生成标题
    generated_at: datetime,               # 生成时间
    request: GenerateRequest,             # 原始请求
    items: list[PaperItem],               # 题目列表
    total_score: int,                     # 总分
    metadata: dict = {
        "retrieval_warnings": [],         # Retriever 警告
        "revision_failures": [],          # 失败题目索引
        "llm_calls": 0,                   # LLM 调用次数
    },
)

PaperItem(
    index: int,                           # 题目序号
    question: RevisedQuestion,            # 改写后的题目
    score: int,                           # 分值
    source_question_id: str,              # 溯源原题 ID
    revision_mode: str,                   # 改题模式
    revision_notes: str | None,           # 改题笔记（失败原因）
)
```

## Design Decisions

### Invariant Fields Protection

题型、知识点、难度在任何档位下都不被修改，确保答题记录的 KP 归属正确。这是一个**核心不变量**。

### revision_intensity Drives Everything

改题尺度是决定 LLM 调用次数和改题策略的唯一因素：

| revision_intensity | LLM 调用 | 改题策略 |
|--------------------|----------|----------|
| `"original"` | 0 次/题 | 直接拷贝 |
| `"light"` | 1 次/题 | 保留结构改内容 |
| `"fresh"` | 1 次/题 | 全新出题 |

### Failure is Not Fatal

任何 LLM 调用失败或校验失败都不会导致整个试卷生成失败，而是 fallback 到原题。这保证了系统的**可用性**。

## Files

```
ai_engine/
├── reviser.py              # 核心改写逻辑
├── prompts/
│   ├── reviser_light.md    # light 档 Prompt 模板
│   ├── reviser_fresh.md    # fresh 档 Prompt 模板
│   └── __init__.py         # Prompt 加载器（含 to_json 过滤器）
├── errors.py               # 错误定义
└── __init__.py             # 模块入口
```

## Related Modules

- [shared/schemas.py](../shared/schemas.py) — 数据契约定义（Paper、PaperItem、RevisedQuestion）
- [shared/llm/deepseek.py](../shared/llm/deepseek.py) — LLM 客户端
- [ai_engine/parser.py](parser.py) — 上游模块，提供 `GenerateRequest`
- [ai_engine/retriever.py](retriever.py) — 上游模块，提供 `RetrievalResult`