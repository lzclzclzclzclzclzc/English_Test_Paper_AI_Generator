# Spec I：阅读首字母填空支持设计

**创建日期**：2026-08-04
**项目根目录**：`d:\Code\English_Test_Paper_AI_Generator`
**范围**：新增阅读首字母填空（`reading_first_blank`）题型支持，覆盖数据契约、AI Engine、后端、前端全链路
**依赖**：
- [Spec A（题库摄入）](./2026-07-07-question-bank-ingestion-design.md)
- [Spec B（AI Engine）](./2026-07-07-ai-engine-design.md)
- [Spec C（后端）](./2026-07-07-backend-design.md)
- [Spec D（前端）](./2026-07-07-frontend-design.md)
- [Spec H（听力填词）](./listening-fill-blank-design.md)（填空线渲染与判空逻辑复用）

---

## 0. 范围与产出

### 0.1 本 spec 定义

- 新增题型 `reading_first_blank`（阅读首字母填空）的数据契约扩展
- AI Engine 各模块对阅读首字母填空的支持（Parser / Retriever / Reviser / Solutioner）
- 后端判对错逻辑复用（无需改）
- 前端阅读首字母填空组件实现（**填空形式模仿听力填词，题目显示只显示单栏文章**）

### 0.2 本 spec 不定义

- 其他阅读题型（如任务型阅读、选词填空、主旨大意填空）——留待未来
- 音频播放——阅读题型无听力，`PassageBlock` 不显示播放控件（复用既有逻辑）

### 0.3 核心需求

1. **填空形式**：模仿听力填词（`listening_fill_blank`）的 `BlankedText` 填空线输入框，但空位带有**首字母提示**（首字母已给出，剩余部分填空）。
2. **题目显示**：只显示单栏（文章）——整篇阅读短文作为一道题，7 个空位内联在文章中，不拆分小题。
3. 一篇首字母填空文章共 **7 个空**（题号 `(1)`–`(7)`），每空限填一词。
4. 支持改题（light / fresh / original）与解析功能。

---

## 1. 数据契约扩展（Spec A §2 扩展）

### 1.1 新增题型枚举

在 `shared/schemas.py` 的 `QuestionType` 中新增：

```python
QuestionType = Literal[
    "single_choice", "word_form", "sentence_rewriting", "listening_single_choice",
    "listening_true_false",
    "listening_fill_blank",
    "reading_longtext_single_choice",
    "cloze_single_choice",
    "reading_first_blank",          # 新增
]
```

### 1.2 阅读首字母填空数据结构

阅读首字母填空采用**一道题 = 一篇短文**的结构：

- `passage_id` / `passage_json`：共享的阅读短文（`kind="reading"`），**空位内联在 `passage_json.content` 中**，不拆分为单独 stem
- `stem`：恒为 `null`（文章即题目，无独立题干）
- `answer`：`list[BlankGroup]`，顺序对应文章的 7 个空位，值为**完整单词**，直接复用判空逻辑

```json
{
  "id": "q_30001",
  "book": "shanghai_2020_yimo",
  "question_type": "reading_first_blank",
  "chapter_l1": "3 阅读理解",
  "chapter_l2": null,
  "number": "1",
  "passage_id": "psg_2020_r_001",
  "passage_json": {
    "kind": "reading",
    "title": "Reading - 宝山 2020",
    "content": "Should we use tablet computers in the classroom?\nThe use of tablet computers ... a______(1)____ of the problems.\n...",
    "audio_url": null
  },
  "stem": null,
  "hint": null,
  "original_sentence": null,
  "instruction": null,
  "template": null,
  "answer": [
    { "blank1": ["aware"] },
    { "blank2": ["advantages"] },
    { "blank3": ["Therefore"] },
    { "blank4": ["activities"] },
    { "blank5": ["focusing"] },
    { "blank6": ["repair"] },
    { "blank7": ["certainly"] }
  ],
  "source_md": null,
  "source_line": 0,
  "knowledge_point_ids": ["kp_reading_first_blank"]
}
```

#### 1.2.1 空位标记格式（`content` 内）

`passage_json.content` 中每个空位使用如下标记：

```
{首字母}{下划线}({题号}){下划线}
```

- **首字母**：已给出，作为填空提示（如 `a`、`T`、`f`）
- **下划线**：空位占位（前后两段下划线，中间夹题号）
- **题号**：`(1)`–`(7)`，标识该空位对应的 `blankN`

示例：

```
we must also be a______(1)____of the problems.
T______(3)____，using tablets in the classroom could reduce the time...
```

**前端解析正则**：`/([A-Za-z])_{2,}\((\d+)\)_{2,}/g`，捕获首字母与题号。

#### 1.2.2 首字母与答案的关系

- `answer` 存**完整单词**（如 `"aware"`、`"Therefore"`）
- 首字母由标记给出（如 `aware` 的首字母 `a`）
- 前端提交时自动将「首字母 + 用户输入」拼成完整单词再提交，**后端判空按完整单词比对**，无需感知首字母

---

### 1.3 知识点扩展

在 `data/kb/knowledge_tree.json` 的 `knowledge_points` 数组中新增：

```json
{
  "id": "kp_reading_first_blank",
  "level1": "reading_first_blank",
  "level2": "阅读首字母填空",
  "aliases": ["首字母填空", "阅读首字母", "短文首字母"]
}
```

并在 `chapter_to_kp` 中添加映射：

```json
"reading_first_blank / 3 阅读理解 / None": ["kp_reading_first_blank"]
```

### 1.4 RevisedQuestion 支持

`RevisedQuestion` 模型已含 `passage_id` / `passage_json` / `answer` 等字段，无需额外字段变更。

---

## 2. AI Engine 支持（Spec B 扩展）

### 2.1 Parser 扩展

**修改文件**：`ai_engine/parser.py`

**新增题型枚举**：

```python
question_types = "\n".join([
    # ... 现有 ...
    "- reading_first_blank: 阅读首字母填空（一篇短文，内嵌 7 个首字母填空）",
])
```

**本地校验扩展**（`VALID_QUESTION_TYPES` 加入 `"reading_first_blank"`）：

```python
VALID_QUESTION_TYPES = {
    # ... 现有 ...
    "reading_first_blank",
}
```

**Prompt 修改**：`ai_engine/prompts/parser.md`

- 题型枚举部分添加 `- reading_first_blank: 阅读首字母填空`
- light 档位触发词中添加"首字母填空""阅读首字母"等
- 添加 few-shot 示例：
  ```
  输入："来 1 篇阅读首字母填空（7 个空）"
  输出：{"question_types": ["reading_first_blank"], "total_questions": 1, ...}
  ```

### 2.2 Retriever 扩展（SQL only，不做向量库）

**修改文件**：`ai_engine/retriever.py`

阅读首字母填空与阅读长文单选同属**长文本 passage 题型**：

- **不进向量库**：`reading_first_blank` 加入 `NON_VECTOR_TYPES`（与 `reading_longtext_single_choice` 一致），走 SQL 路径
- **按 passage 整组检索**：`reading_first_blank` 一道题即一篇 passage，SQL 按 `question_type` 过滤 + 按 `passage_id` 随机取篇即可

```python
NON_VECTOR_TYPES = {
    "listening_true_false",
    "listening_fill_blank",
    "reading_longtext_single_choice",
    "reading_first_blank",   # 新增
}
```

### 2.3 Reviser 扩展

**修改文件**：`ai_engine/reviser.py`

**核心行为：阅读首字母填空一律跳过 LLM 改写。**

`reading_first_blank` 题型复杂，light/fresh 改写极易导致答案与原题 7 空错位、
拼写错误等问题。因此 `_revise_one` 在函数开头做硬性拦截：无论 `revision_intensity`
是 light / fresh / original，一律调用 `_copy_question(question)` 原样返回（`is_fallback=False`），
**从不调用 LLM**。作文题（`writing`）同样在此处被拦截——作文无标准答案（`answer=None`），
也按原题拷贝返回、不调用 LLM。

```python
def _revise_one(question, intensity, free_text):
    if question.question_type == "reading_first_blank":
        # 一律按原题出，不做任何改写（避免答案与 7 空错位、拼写错误）
        return _copy_question(question), False
    if question.question_type == "writing":
        # 作文题没有标准答案（answer=None），直接使用原题
        return _copy_question(question), False
    if intensity == "original":
        return _copy_question(question), False
    # ... light / fresh 才走 LLM ...
```

因为始终走原题路径，`reading_first_blank` 和 `writing` 都不计入 `metadata.llm_calls`。

**答案格式校验（防御性）**：即便阅读首字母填空不走 LLM，`_validate_revision`
仍对填空类题型（`word_form` / `sentence_rewriting` / `listening_fill_blank` /
`reading_first_blank`）复用 `_is_valid_blank_answer`（要求 answer 为非空
`list[BlankGroup]`、每空至少一个非空候选词）。针对 `reading_first_blank`，额外校验
**修订后答案的空位数必须与原题一致**（`len(revised.answer) == len(original.answer)`），
否则会出现"文章有 7 空、答案只有 1 空"的错位，导致文章下方额外渲染填空框——此时
拒绝修订并回退到原题拷贝：

```python
elif qt in ("word_form", "sentence_rewriting", "listening_fill_blank", "reading_first_blank"):
    if not _is_valid_blank_answer(revised.answer):
        return False
    if qt == "reading_first_blank" and len(revised.answer) != len(original.answer):
        return False
```

**Prompt 修改**：由于阅读首字母填空不走 LLM 改写，`reviser_light.md` /
`reviser_fresh.md` 的 prompt 对该题型不生效；无需为其新增 prompt 约束。

### 2.4 Solutioner 扩展

**修改文件**：`ai_engine/solutioner.py`

**实际行为：阅读首字母填空走通用解析路径，没有该题型专属的 prompt 分支。**

`generate_solution` 对所有题型统一加载同一个 `solutioner` prompt（`ai_engine/prompts/solutioner.md`），
不按 `question_type` 分派、不为 `reading_first_blank` 注入专门的解析要求。唯一与该题型
相关的特殊处理在 `_format_answer`：它按 **answer 的结构形状**（而非题型名）识别"多个单空
dict"（`[{blank1},{blank2},…]`，每个 dict 只有一个键），将其**逐空分行展示**
（`blank1: aware` 换行 `blank2: advantages` …），避免 LLM 把这些当作"或"关系的候选组合而
只解析其中一个空。

```python
def _format_answer(answer):
    if isinstance(answer, str):
        return answer
    # 逐空分行（阅读首字母填空的 [{blank1},{blank2},…] 命中此分支）
    if answer and all(isinstance(g, dict) and len(g) == 1 for g in answer):
        lines = []
        for g in answer:
            blank, cands = next(iter(g.items()))
            lines.append(f"{blank}: {' / '.join(cands)}")
        return "\n".join(lines)
    # 其它填空类：候选组以"或"连接
    ...
```

> 注：此分支基于答案形状触发，对任何"每空一个单键 dict"的答案生效，并非专为
> `reading_first_blank` 硬编码。解析文本本身由通用 prompt 生成，无题型专属提示。

---

## 3. 后端支持（Spec C 扩展）

### 3.1 判对错逻辑复用

**修改文件**：`backend/services/grading.py`

`compare()` 已兼容：`reading_first_blank` 的 `answer` 是 `list[BlankGroup]`，会命中
`isinstance(correct_answer, list)` 分支走 `_compare_blank_answers`（按空逐一比对、候选组任一
命中即对）。**无需改动**，仅需在本文件注释中补充该题型说明。

**特殊处理：`_normalize_candidates` 合并单空 dict。** 阅读首字母填空的 answer 形如
`[{blank1},{blank2},…]`——每个空一个 dict、各只含一个键，语义是"所有空必须**一起**正确"，
而非"多个可替换的候选组合"。`_compare_blank_answers` 在比对前先调用 `_normalize_candidates`：
当 `correct_answers` 全部是单键 dict 时，把它们 `merge` 成**单个整体候选**
`[{blank1, blank2, …, blank7}]`。否则（如 `word_form` / `sentence_rewriting` /
`listening_fill_blank` 的候选元素含多个键，或本身即单元素）保持原样。

合并的必要性：若不合并，逐候选比对时用户填满 7 空的键集合（`{blank1..blank7}`）永远不等于
任一单键候选，整道题会**恒判错**。合并后，比对要求用户键集合与合并候选完全一致，且每个空
都命中该空的候选词集合——因此**所有空必须同时正确，任一空错误即整题判错，无按空部分给分**。

```python
def _normalize_candidates(correct_answers):
    if correct_answers and all(isinstance(c, dict) and len(c) == 1 for c in correct_answers):
        merged = {}
        for c in correct_answers:
            merged.update(c)
        return [merged]           # 7 个单空 dict → 1 个整体候选
    return correct_answers
```

### 3.2 知识点目录

后端无需修改——`GET /api/knowledge-points` 会自动返回新添加的阅读首字母填空知识点。

---

## 4. 前端支持（Spec D 扩展）

### 4.1 类型定义扩展

**修改文件**：`frontend/src/types/api.ts`

```typescript
export type QuestionType =
  | "single_choice"
  | "word_form"
  | "sentence_rewriting"
  | "listening_single_choice"
  | "listening_true_false"
  | "listening_fill_blank"
  | "reading_first_blank";
```

### 4.2 新增题目组件

**新增文件**：`frontend/src/components/question-fields/ReadingFirstBlankField.tsx`

组件自包含渲染整篇文章（单栏），空位内联：
- 解析 `passage_json.content` 中的空位标记（见 §1.2.1）
- 每个空位渲染为：**首字母 + 填空线输入框**（输入剩余部分）+ 题号小标签
- 提交时把「首字母 + 用户输入」拼成完整单词构建 `BlankMap`
- 答题态可输入，复盘态展示用户答案与对错

```tsx
import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import type { BlankMap } from '@/lib/answers'
import { getBlankKeys, toBlankMap } from '@/lib/answers'

interface ReadingFirstBlankFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: BlankMap
  onChange?: (v: BlankMap) => void
  result?: GradeResultItem
}

/** 阅读首字母填空：整篇文章单栏渲染，空位内联（首字母 + 输入框）。 */
export function ReadingFirstBlankField({ question, mode, value, onChange, result }: ReadingFirstBlankFieldProps) {
  const blankKeys = getBlankKeys(question.answer)
  // 1) 解析 content 中的空位标记，得到 [{letter, number, blankKey}]
  const blanks = parseFirstBlankMarkers(question.passage_json?.content ?? '', blankKeys)
  const displayValue = mode === 'review' ? toBlankMap(blankKeys, result?.user_answer) : (value ?? {})

  return (
    <div className="w-full whitespace-pre-wrap text-[15px] leading-[1.8] text-ink">
      {renderContentWithBlanks(question.passage_json?.content ?? '', blanks, displayValue, mode, onChange)}
    </div>
  )
}
```

> 说明：`passage` 不另外用 `PassageBlock` 渲染——该组件本身就是"单栏文章"视图，空位需内联可填，无法复用纯文本 `PassageBlock`。

**首字母与提交逻辑**：
- 标记 `a______(1)____` → 首字母 `a`，题号 `1`，对应 `blank1`
- 用户输入 `ware` → 提交值 `a` + `ware` = `aware`（完整单词）
- 复盘态比对的是完整单词

### 4.3 QuestionCard 分派扩展

**修改文件**：`frontend/src/components/QuestionCard.tsx`

- 引入 `ReadingFirstBlankField`
- 新增分派分支（填空类，传 `BlankMap`）：

```tsx
) : question.question_type === 'reading_first_blank' ? (
  <ReadingFirstBlankField
    question={question}
    mode={mode}
    value={typeof value === 'object' ? (value as BlankMap) : undefined}
    onChange={onChange}
    result={result}
  />
) : (
```

- 复盘态"你的答案 / 正确答案"比对区：`reading_first_blank` 与 `word_form` / `sentence_rewriting` / `listening_fill_blank` 相同，走 `formatUserAnswer` / `formatCorrectAnswer`（不需额外分支）。

### 4.4 答案构建扩展

**修改文件**：`frontend/src/lib/answers.ts`

`getBlankKeys` / `buildSubmission` / `toBlankMap` / `formatUserAnswer` / `formatCorrectAnswer` 均按 `answer` 是否为 `list[BlankGroup]` 判断填空类，`reading_first_blank` 天然命中，**无需改动**。

### 4.5 PaperPage 分组（复用）

**修改文件**：`frontend/src/pages/PaperPage.tsx`

`groupByPassage` 已按 `passage_id` 分组，阅读首字母填空题带 `passage_id`，**自动复用**。阅读材料（`kind="reading"`）不显示播放控件，直接由 `ReadingFirstBlankField` 渲染单栏文章。

### 4.6 题型标签

**修改文件**：`frontend/src/lib/kp.ts`（`TYPE_LABELS`）

为 `reading_first_blank` 补充中文标签：

```typescript
reading_first_blank: '阅读首字母填空',
```

---

## 5. 题库摄入支持

### 5.1 数据文件

数据模板文件：`data/chapters/shanghai_2020_yimo_reading_first_blank.json`

### 5.2 SQLite schema 扩展

**修改文件**：`ingestion/sqlite/schema.sql`

- `knowledge_points` 表的 `CHECK (level1 IN (...))` 加入 `'reading_first_blank'`
- `questions` 表的 `CHECK (question_type IN (...))` 加入 `'reading_first_blank'`

### 5.3 loader 扩展

**修改文件**：`ingestion/sqlite/loader.py`

**`_stem_hash` 加分支**：

```python
elif qt == "reading_first_blank":
    # 阅读首字母填空：passage_id + 空位答案（无 stem）
    payload["passage_id"] = q.get("passage_id")
    payload["answer"]     = q.get("answer")
```

**INSERT 逻辑**：`stem` 传 `None`，`passage_id` / `passage_json` 照常写入（与阅读长文一致），无需额外改动。

### 5.4 不做向量库（明确）

**修改文件**：`ingestion/chromadb/loader.py`

在遍历 SQLite 入向量库时，跳过 `reading_first_blank`（加入 `NON_VECTOR_TYPES` 集合），与阅读长文单选一致。

### 5.5 构建命令

```bash
# 重新构建 SQLite
python -m ingestion.cli build-sqlite
```

---

## 6. 测试

### 6.1 后端集成测试

在 `tests/integration/backend/test_papers.py` 中添加阅读首字母填空测试用例：

- 生成阅读首字母填空试卷（按 passage 整组出题）
- 提交答题并判分（空位比对、完整单词命中、首字母+输入拼接）
- 生成解析

### 6.2 前端组件测试

在 `frontend/src/components/question-fields/ReadingFirstBlankField.test.tsx` 添加测试：

- 组件渲染（解析出 7 个空位标记，渲染 7 个输入框）
- 答题态可输入、提交拼出完整单词
- 复盘态展示用户答案与对错
- 空位标记解析：首字母 + 题号 → blankKey 映射正确

---

## 7. 里程碑

> 本 spec 现记录**已完成**的工作：`reading_first_blank` 全链路已实现，题库中含 31 道阅读首字母填空题。

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 数据契约扩展（QuestionType、知识点） | 完成 |
| 2 | AI Engine Parser 扩展 | 完成 |
| 3 | AI Engine Retriever 扩展（SQL only + passage 整组） | 完成 |
| 4 | AI Engine Reviser 扩展 | 完成 |
| 5 | AI Engine Solutioner 扩展 | 完成 |
| 6 | 后端判对错（复用 `_compare_blank_answers`） | 完成 |
| 7 | 前端 ReadingFirstBlankField 组件 | 完成 |
| 8 | 前端 QuestionCard 分派扩展 | 完成 |
| 9 | 前端 TYPE_LABELS 扩展 | 完成 |
| 10 | 题库数据加载（schema / loader / 跳过向量库） | 完成 |
| 11 | 测试 | 完成 |

---

## 8. 开放问题

1. **空位标记解析的鲁棒性**：`([A-Za-z])_{2,}\((\d+)\)_{2,}` 要求首字母后紧跟下划线、题号在括号内。若真题出现大小写混排或下划线数量不一致，需调整正则。当前要求出题时严格遵循该格式。
2. **首字母大小写**：答案存完整单词（含首字母正确大小写），前端拼接时首字母取自标记，需保证标记首字母与答案单词首字母一致（Reviser 校验已覆盖）。
3. **整篇 7 空约束**：当前契约不强制恰好 7 空，由出题/Prompt 约束。若需硬约束，可在 Reviser 或 Parser 层加校验。
4. **单词拼写容错**：对拼写敏感，当前判空按候选词集合匹配，可考虑为常见同音/拼写变体增加候选词。

---

## 9. 不变量

1. **阅读首字母填空的答案格式**：`answer` 为 `list[BlankGroup]`，值是完整单词，判对错复用 `_compare_blank_answers`。
2. **一道题 = 一篇短文**：`stem` 恒为 `null`，空位内联在 `passage_json.content` 中，整篇作为一道题渲染（单栏）。
3. **Reviser 不变字段**：`question_type` / `knowledge_point_ids` / `passage_id` 在任何档位下都不被修改。
4. **不进向量库**：`reading_first_blank` 永远不写入 ChromaDB 集合，Retriever 只走 SQL 路径。
5. **空位标记与答案一致**：content 中 `(N)` 题号与 `blankN` 一一对应，标记首字母与答案单词首字母一致。
6. **前端提交拼完整单词**：提交值为「首字母 + 用户输入」，后端不感知首字母。
7. **Solutioner 无缓存**：每次调用都直接问 LLM，不读/写 `questions.solution`。