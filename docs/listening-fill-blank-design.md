# Spec H：听力填词支持设计

**创建日期**：2026-08-04
**项目根目录**：`d:\Code\English_Test_Paper_AI_Generator`
**范围**：新增听力填词（`listening_fill_blank`）题型支持，覆盖数据契约、AI Engine、后端、前端全链路
**依赖**：
- [Spec A（题库摄入）](./2026-07-07-question-bank-ingestion-design.md)
- [Spec B（AI Engine）](./2026-07-07-ai-engine-design.md)
- [Spec C（后端）](./2026-07-07-backend-design.md)
- [Spec D（前端）](./2026-07-07-frontend-design.md)
- [Spec G（听力选择）](./listening-support-design.md)

---

## 0. 范围与产出

### 0.1 本 spec 定义

- 新增题型 `listening_fill_blank`（听力填词）的数据契约扩展
- AI Engine 各模块对听力填词的支持（Parser / Retriever / Reviser / Solutioner）
- 后端判对错逻辑复用（无需改）
- 前端听力填词组件实现（**播放形式模仿听力 TF / 听力选择**，**题目显示形式模仿改写句子**）

### 0.2 本 spec 不定义

- 其他听力题型（如听力听写、听力填空长句）——留待未来
- 真实音频文件支持——当前使用浏览器 TTS 合成（复用 Spec G 的 `tts.ts`）

### 0.3 核心需求

1. **播放形式**：沿用听力 TF 题型的 `PassageBlock`（一段 `passage` 渲染一次，播放按钮 + TTS 分段朗读，做题态隐藏原文、复盘态展示原文）。
2. **题目显示形式**：沿用改写句子（`sentence_rewriting`）的 `BlankedText` 填空线输入框，按 `answer` 的空键数渲染输入框。
3. 一篇听力文章共 **10 个空**（通常 5 小题 × 每空 2 词，或按空数自由组合），每空格限填一词。
4. 支持改题（light / fresh / original）与解析功能。

---

## 1. 数据契约扩展（Spec A §2 扩展）

### 1.1 新增题型枚举

在 `shared/schemas.py` 的 `QuestionType` 中新增：

```python
QuestionType = Literal[
    "single_choice", "word_form", "sentence_rewriting", "listening_single_choice",
    "listening_true_false",
    "listening_fill_blank",          # 新增
    "reading_longtext_single_choice",
    "cloze_single_choice",
]
```

### 1.2 听力填词数据结构

听力填词采用**共享材料（passage）+ 组内多小题**的结构，与 `listening_true_false` 一致：

- `passage_id` / `passage_json`：共享的听力篇章（`kind="listening"`），供 `PassageBlock` 播放与复盘展示
- `stem`：带空位的句子（`________` 下划线占位，可含中文注释），与改写句子的 `template` 同构，供 `BlankedText` 原位渲染
- `answer`：`list[BlankGroup]`，每个空为 `blankN → [可接受词]`，直接复用改写句子的判空逻辑

```json
{
  "id": "q_13001",
  "book": "shanghai_2026_yimo",
  "question_type": "listening_fill_blank",
  "chapter_l1": "1 听力填词",
  "chapter_l2": null,
  "number": "16",
  "passage_id": "psg_2026_d_001",
  "passage_json": {
    "kind": "listening",
    "title": "Passage - Audiobooks",
    "content": "Audio books were first developed in the 18 seventies...",
    "audio_url": null
  },
  "stem": "People called Audiobooks（有声读物）, developed in the 1870s. ________ ________ at first.",
  "hint": null,
  "original_sentence": null,
  "instruction": null,
  "template": null,
  "answer": [
    {
      "blank1": ["talking"],
      "blank2": ["stories"]
    }
  ],
  "source_md": null,
  "source_line": 0,
  "knowledge_point_ids": [
    "kp_listening_fill_blank"
  ]
}
```

**字段约定**：
- `stem` 用连续下划线 `________` 表示空位，`BlankedText` 按 `answer` 的空键数切分；空位标记与空数不一致时回退为"原文 + 下方标签输入框"（与改写句子一致，见 `lib/answers.ts::splitTemplateByBlanks`）。
- `answer` 的 `blankN` 数量即该题空数；整篇 passage 的组内所有题空数之和通常为 10。
- 每空可提供多个候选词（如语气拼写差异），`list[BlankGroup]` 天然支持。

### 1.3 知识点扩展

在 `data/kb/knowledge_tree.json` 中新增听力填词知识点：

```json
{
  "id": "kp_listening_fill_blank",
  "level1": "listening_fill_blank",
  "level2": "听力填词",
  "aliases": ["听力填词", "听力填空", "听写填空", "听短文填词"]
}
```

并在 `knowledge_tree.json` 的 chapter → KP 映射部分新增：

```json
"listening_fill_blank / 1 听力填词 / None": [
  "kp_listening_fill_blank"
]
```

### 1.4 RevisedQuestion 支持

`RevisedQuestion` 模型已含 `passage_id` / `passage_json` / `stem` / `answer` 等字段，无需额外字段变更。

---

## 2. AI Engine 支持（Spec B 扩展）

### 2.1 Parser 扩展

**修改文件**：`ai_engine/parser.py`

**新增题型枚举**：

```python
question_types = "\n".join([
    "- single_choice: 单项选择",
    "- word_form: 词性转换",
    "- sentence_rewriting: 改写句子",
    "- listening_single_choice: 听力选择",
    "- listening_true_false: 听力判断",
    "- listening_fill_blank: 听力填词",
])
```

**本地校验扩展**（`VALID_QUESTION_TYPES` 加入 `"listening_fill_blank"`）：

```python
VALID_QUESTION_TYPES = {
    "single_choice", "word_form", "sentence_rewriting",
    "listening_single_choice", "listening_true_false", "listening_fill_blank",
}
```

**Prompt 修改**：`ai_engine/prompts/parser.md`

- 题型枚举部分添加 `- listening_fill_blank: 听力填词`
- light 档位触发词中添加"听力填词""听力填空""听短文填词"等
- 添加 few-shot 示例：
  ```json
  输入："来 5 道听力填词（一篇短文 10 个空）"
  输出：{"question_types": ["listening_fill_blank"], ...}
  ```

### 2.2 Retriever 扩展

**修改文件**：`ai_engine/retriever.py`

Retriever 的混合检索策略对 `listening_fill_blank` 完全兼容，无需修改核心逻辑。注意：

- 听力填词以 `passage` 为共享材料，检索时按 `question_type` + `knowledge_point_ids` 过滤，命中组内任一小题即带回整组（`passage_id` 相同）。
- 向量检索基于 `stem` / `passage_json.content` 语义匹配。

### 2.3 Reviser 扩展

**修改文件**：`ai_engine/reviser.py`

Reviser 三档策略（original / light / fresh）对 `listening_fill_blank` 兼容。

**答案格式校验扩展**：

```python
def _validate_revision(question, revised):
    # 听力填词与改写句子共享空位校验：answer 为非空 list[BlankGroup]
    if question.question_type in {"sentence_rewriting", "listening_fill_blank"}:
        if not isinstance(revised.answer, list) or not revised.answer:
            return False, "answer must be a non-empty list[BlankGroup]"
        # 每个 BlankGroup 至少含一个非空键
        if any(not grp or not all(v for v in grp.values()) for grp in revised.answer):
            return False, "each blank must have non-empty candidates"
    return True, None
```

**Prompt 修改**：`ai_engine/prompts/reviser_light.md` 和 `ai_engine/prompts/reviser_fresh.md`

在不变约束中补充听力填词的 `stem` 格式要求：

```
- 听力填词（listening_fill_blank）的 stem 必须保留原空位标记（用连续下划线 ________ 表示空位），
  空数必须与 answer 的 blankN 键数一致；每空格限填一词。
- 示例：stem = "People called Audiobooks（___） ________ ________ at first."
        answer = [{"blank1": ["talking"], "blank2": ["stories"]}]
```

### 2.4 Solutioner 扩展

**修改文件**：`ai_engine/solutioner.py`

Solutioner 对 `listening_fill_blank` 的支持与 `sentence_rewriting` 类似——`user_answer` 为 `list[str]` 或 `{blankN: str}`，`_format_user_answer` 已支持。

**Prompt 修改**：`ai_engine/prompts/solutioner.md`

在特别要求中添加：

```
- 听力填词（listening_fill_blank）：必须指出该词在原文听力中的读音/语境线索，并解释为何是这个词形；
  若因拼写或听取错误，指出正确词与其在文中的位置。
```

---

## 3. 后端支持（Spec C 扩展）

### 3.1 判对错逻辑复用

**修改文件**：`backend/services/grading.py`

`compare()` 已兼容：`listening_fill_blank` 的 `answer` 是 `list[BlankGroup]`，会命中 `isinstance(correct_answer, list)` 分支走 `_compare_blank_answers`（按空逐一比对、候选组任一命中即对）。**无需改动**，仅需在本文件注释中补充该题型说明。

### 3.2 知识点目录

后端无需修改——`GET /api/knowledge-points` 会自动返回新添加的听力填词知识点。

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
  | "listening_fill_blank";
```

### 4.2 新增题目组件

**新增文件**：`frontend/src/components/question-fields/ListeningFillBlankField.tsx`

组件结构（复用 `BlankedText`，与 `SentenceRewritingField` 同构）：

```tsx
import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import type { BlankMap } from '@/lib/answers'
import { getBlankKeys, toBlankMap } from '@/lib/answers'
import { BlankedText } from '@/components/question-fields/BlankedText'

interface ListeningFillBlankFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: BlankMap
  onChange?: (v: BlankMap) => void
  result?: GradeResultItem
}

/** 听力填词：带空句子（stem）+ 填空线输入框。passage 由外层 PassageBlock 渲染一次。 */
export function ListeningFillBlankField({
  question,
  mode,
  value,
  onChange,
  result,
}: ListeningFillBlankFieldProps) {
  const blankKeys = getBlankKeys(question.answer)
  const displayValue =
    mode === 'review' ? toBlankMap(blankKeys, result?.user_answer) : (value ?? {})

  return (
    <div className="flex flex-col gap-2">
      {question.stem && (
        <BlankedText
          text={question.stem}
          blankKeys={blankKeys}
          mode={mode}
          value={displayValue}
          onChange={onChange}
        />
      )}
    </div>
  )
}
```

> 说明：`passage` 不在此组件渲染——由 `PaperPage` 的 `groupByPassage` 统一分组渲染一次 `PassageBlock`（与听力 TF 一致）。

### 4.3 QuestionCard 分派扩展

**修改文件**：`frontend/src/components/QuestionCard.tsx`

- 引入 `ListeningFillBlankField`
- 新增分派分支（填空类，传 `BlankMap`）：

```tsx
) : question.question_type === 'listening_fill_blank' ? (
  <ListeningFillBlankField
    question={question}
    mode={mode}
    value={typeof value === 'object' ? (value as BlankMap) : undefined}
    onChange={onChange}
    result={result}
  />
) : (
```

- 复盘态"你的答案 / 正确答案"比对区：`listening_fill_blank` 与 `word_form` / `sentence_rewriting` 相同，走 `formatUserAnswer` / `formatCorrectAnswer`（该分支无需增减，因为 `listening_fill_blank` 不在已排除的选项类题型列表里）。

### 4.4 答案构建扩展

**修改文件**：`frontend/src/lib/answers.ts`

`getBlankKeys` / `buildSubmission` / `toBlankMap` / `formatUserAnswer` / `formatCorrectAnswer` 均按 `answer` 是否为 `list[BlankGroup]` 判断填空类，`listening_fill_blank` 天然命中，**无需改动**。

### 4.5 PaperPage 分组（复用）

**修改文件**：`frontend/src/pages/PaperPage.tsx`

`groupByPassage` 已按 `passage_id` 分组，听力填词题带 `passage_id`，**自动复用**，无需改动。听力材料（`kind="listening"`）在做题态由 `PassageBlock` 只显示播放按钮、复盘态显示原文。

### 4.6 题型标签

**修改文件**：`frontend/src/lib/kp.ts`（`TYPE_LABELS`）

为 `listening_fill_blank` 补充中文标签：

```typescript
listening_fill_blank: '听力填词',
```

---

## 5. 题库摄入支持

### 5.1 数据文件

数据模板文件：`data/chapters/shanghai_2026_yimo_listening_fill_blank.json`

### 5.2 知识点树

在 `data/kb/knowledge_tree.json` 中新增听力填词知识点 + chapter 映射（见 § 1.3）。

### 5.3 构建命令

```bash
# 重新构建 SQLite
python -m ingestion.cli build-sqlite

# 重新构建向量索引
python -m ingestion.cli build-vec --model models/qwen3-embedding-4b
```

---

## 6. 测试

### 6.1 后端集成测试

在 `tests/integration/backend/test_papers.py` 中添加听力填词测试用例：

- 生成听力填词试卷（含 passage 分组）
- 提交听力填词答题并判分（填空空位比对、候选词命中）
- 生成听力填词解析

### 6.2 前端组件测试

在 `frontend/src/components/question-fields/ListeningFillBlankField.test.tsx` 添加测试：

- 组件渲染（填空线输入框数量 = answer 空键数）
- 答题态可输入、复盘态展示用户答案与对错
- 空位标记与空数不一致时回退为"原文 + 标签输入框"

---

## 7. 里程碑

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 数据契约扩展（QuestionType、知识点） | 待实现 |
| 2 | AI Engine Parser 扩展 | 待实现 |
| 3 | AI Engine Reviser 扩展 | 待实现 |
| 4 | AI Engine Solutioner 扩展 | 待实现 |
| 5 | 后端判对错（复用 `_compare_blank_answers`） | 待实现 |
| 6 | 前端 ListeningFillBlankField 组件 | 待实现 |
| 7 | 前端 QuestionCard 分派扩展 | 待实现 |
| 8 | 前端 TYPE_LABELS 扩展 | 待实现 |
| 9 | 题库数据加载 | 待实现 |
| 10 | 测试 | 待实现 |

---

## 8. 开放问题

1. **TTS 语音质量**：与听力选择一致，浏览器原生 TTS 的男女声区分能力因浏览器而异；未来可接入第三方 TTS API。
2. **空位与空数一致性**：真题库中偶尔出现空位标记数与空数不符，前端已用 `splitTemplateByBlanks` 回退策略兜底；出题时 Prompt 应尽量保证 `stem` 空位数 = `answer` 空键数。
3. **整篇空数约束**：当前契约不强制"整篇恰好 10 空"，由组卷/出题时人工或 Prompt 约束。若需硬约束，可在 Reviser 或 Parser 层加校验。
4. **听取词的拼写容错**：听力填词对拼写敏感。当前判空按候选词集合匹配，可考虑为常见同音/拼写变体增加候选词。

---

## 9. 不变量

1. **听力填词的答案格式与改写句子一致**：`answer` 为 `list[BlankGroup]`，判对错复用 `_compare_blank_answers`。
2. **Reviser 不变字段**：`question_type` / `knowledge_point_ids` / `passage_id` 在任何档位下都不被修改。
3. **每篇 passage 只渲染一次**：听力材料由 `PassageBlock` 按 `passage_id` 分组渲染，做题态隐藏原文、复盘态展示原文。
4. **前端 TTS 不依赖后端**：播放逻辑完全在浏览器端实现，不产生额外 API 调用。
5. **Solutioner 无缓存**：每次调用都直接问 LLM，不读/写 `questions.solution`。