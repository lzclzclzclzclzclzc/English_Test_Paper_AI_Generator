# Spec J：英语作文（Writing）支持设计

**创建日期**：2026-08-06
**项目根目录**：`d:\Code\English_Test_Paper_AI_Generator`
**范围**：新增英语作文（`writing`）题型支持，覆盖数据契约、AI Engine、后端、前端全链路，以及基于 LLM 的作文批改功能
**依赖**：
- [Spec A（题库摄入）](question-bank-ingestion-design.md)
- [Spec B（AI Engine）](ai-engine-design.md)
- [Spec C（后端）](backend-design.md)
- [Spec D（前端）](frontend-design.md)

---

## 0. 范围与产出

### 0.1 本 spec 定义

- 新增题型 `writing`（英语作文）的数据契约与全链路支持
- 基于 LLM 的作文批改系统：三维度评分（内容/语言/组织结构）+ 总分
- 独立的批改端点 `POST /api/writing/grade`，与客观题判分分离
- 前端作文答题组件（题目 + 文本框 + 词数统计 + 提交按钮）
- 提交后仅直接显示总分与各维度得分；详细评析、修改范文作为会员功能

### 0.2 本 spec 不定义

- 真实音频/口语评分——当前仅支持书面作文
- 多人协作批改——当前为单 LLM 批改
- 作文自动生成/润色——当前仅支持批改评分，不提供 AI 写作辅助
- 作文题材分类（记叙文/议论文/应用文等）——统一按三维度评分

### 0.3 核心需求

1. **题型特征**：作文题无标准答案（`answer: null`），由 LLM 按需批改
2. **答题界面**：题目 → 文本框（实时显示 word count）→ 提交按钮
3. **批改流程**：提交后调用 LLM，等待返回结果
4. **显示策略**：非会员仅显示总分与各维度得分表；会员可查看详细评析、错误分析、修改范文
5. **不进向量库**：作文题不走向量检索路径，仅走 SQL 随机抽取
6. **不支持改题**：作文题不经过 Reviser 的 light/fresh/original 流程，题目原样使用

### 0.4 关键决策：独立批改端点

作文判分完全不同于客观题的字符串比对，采用**独立端点** `POST /api/writing/grade`：

- **不 fork 现有 `POST /api/attempts`**：客观题判分是同步快速返回（字符串比对），作文判分需要 LLM 调用（可能 5-15 秒），混在一起会阻塞整体交卷体验
- **独立的返回类型**：客观题返回 `GradeSubmissionResponse`（逐题对错），作文返回 `WritingGradeResponse`（总分+分项+详细评析）
- **解耦演进**：未来若需支持口语评分、听力听写批改等，可按相同模式扩展独立端点

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
    "reading_first_blank",
    "writing",                      # 新增：英语作文
]
```

### 1.2 作文题数据结构

作文题采用**单题即一份作文**的结构，`answer` 为 `null`（无标准答案）：

```json
{
  "id": "q_30001",
  "book": "shanghai_2026_yimo",
  "question_type": "writing",
  "chapter_l1": "5 书面表达",
  "chapter_l2": null,
  "number": "1",
  "stem": "A thank-you letter to ________",
  "options": null,
  "hint": "在日常的生活与学习中有许多人曾经帮助或鼓励过我们，令我们时常心存感激。请选择一个对象写一封感谢信，并结合你们之间的真实经历谈一谈你为何要感谢他/她，说一说你当时的感受以及此时此刻想对他/她说的话。",
  "original_sentence": null,
  "instruction": "Write at least 60 words about the topic \"A thank-you letter to ________\". (信件格式已给，标点符号不占格)",
  "template": null,
  "passage_id": null,
  "passage_json": null,
  "answer": null,
  "source_md": null,
  "source_line": 0,
  "knowledge_point_ids": ["kp_writing"]
}
```

#### 1.2.1 作文题字段约定

| 字段 | 约定 | 说明 |
|------|------|------|
| `stem` | 作文标题 | 如 "A thank-you letter to ________" |
| `hint` | 写作提示/要点 | 中文提示，说明作文要求和要点 |
| `instruction` | 英文指令 | 如 "Write at least 60 words..." |
| `answer` | `null` | 无标准答案，由 LLM 批改 |
| `options` | `null` | 作文题无选项 |
| `template` | `null` | 无需模板 |
| `passage_id` | `null` | 作文题无共享材料 |

#### 1.2.2 新增可选字段

为作文题新增两个可选字段，用于存储作文参考表达和最低词数要求：

在 `shared/schemas.py` 的 `Question` 模型中：

```python
class Question(BaseModel):
    # ... 现有字段 ...
    reference_expressions: str | None = None  # 参考表达，如 "have difficulty in...; encourage me to..."
    min_words: int | None = None               # 最低词数要求，如 60
```

`RevisedQuestion` 同样新增这两个字段：

```python
class RevisedQuestion(BaseModel):
    # ... 现有字段 ...
    reference_expressions: str | None = None
    min_words: int | None = None
```

### 1.3 作文批改结果模型

在 `shared/schemas.py` 中新增作文批改结果模型：

```python
class WritingGradeResult(BaseModel):
    """单篇作文的批改结果"""
    total_score: float              # 总分（0-20）
    content_score: float            # 内容得分（0-8）
    language_score: float           # 语言得分（0-8）
    organization_score: float       # 组织结构得分（0-4）
    word_count: int                 # 词数统计
    level: str                      # 档次描述，如 "优秀"/"良好"/"合格"/"待提升"
    # 以下字段为会员专属，非会员为 null
    content_analysis: str | None = None      # 内容评析
    language_analysis: str | None = None     # 语言评析（含语法/拼写错误）
    organization_analysis: str | None = None # 组织结构评析
    overall_comment: str | None = None       # 总体评价
    revised_version: str | None = None       # 修改范文
```

### 1.4 知识点扩展

在 `data/kb/knowledge_tree.json` 的 `knowledge_points` 数组中新增：

```json
{
  "id": "kp_writing",
  "level1": "writing",
  "level2": "书面表达",
  "aliases": ["作文", "英语写作", "书面表达", "作文批改"]
}
```

并在 `chapter_to_kp` 中添加映射：

```json
"writing / 5 书面表达 / None": ["kp_writing"]
```

### 1.5 ID 编号约定

作文题 ID 从 `q_30001` 开始编号：

| 编号范围 | 题型 | 说明 |
|---------|------|------|
| `q_00001`–`q_09999` | single_choice | 单项选择 |
| `q_10001`–`q_19999` | listening / reading | 听力/阅读 |
| `q_20001`–`q_29999` | reading_longtext | 阅读理解 |
| `q_30001`–`q_39999` | **writing** | **作文（新增）** |

---

## 2. AI Engine 支持（Spec B 扩展）

### 2.1 Parser 扩展

**修改文件**：`ai_engine/parser.py`

**题型枚举**：

```python
question_types = "\n".join([
    "- single_choice: 单项选择",
    "- word_form: 词性转换",
    "- sentence_rewriting: 改写句子",
    "- listening_single_choice: 听力选择",
    "- listening_longtext_truefalse: 听力长文判断题",
    "- reading_longtext_single_choice: 阅读理解",
    "- reading_first_blank: 阅读首字母填空",
    "- writing: 英语作文",
])
```

**本地校验扩展**：

```python
VALID_QUESTION_TYPES = {
    "single_choice", "word_form", "sentence_rewriting",
    "listening_single_choice",
    "listening_longtext_truefalse", "reading_longtext_single_choice",
    "reading_first_blank",
    "writing",   # 新增
}
```

**Prompt 修改**：`ai_engine/prompts/parser.md`

在题型枚举与 few-shot 示例中添加：

```
- writing: 英语作文（给出作文题目，由用户写作并由 AI 批改评分）

示例：
输入："来 1 篇英语作文，感谢信主题"
输出：{"question_types": ["writing"], "total_questions": 1, ...}
```

### 2.2 Retriever 扩展（SQL only，不做向量库）

**修改文件**：`ai_engine/retriever.py`

作文题与阅读长文、听力长文同属**不进向量库**的题型：

```python
NON_VECTOR_TYPES = {
    "listening_longtext_truefalse",
    "reading_longtext_single_choice",
    "reading_first_blank",
    "writing",   # 新增：作文题不进向量库
}
```

作文题检索走 SQL 路径：按 `question_type='writing'` 过滤，随机抽取指定数量的作文题。

### 2.3 Reviser 扩展

**修改文件**：`ai_engine/reviser.py`

作文题**不经过 Reviser 的改题流程**——作文题目原文使用，不做 light/fresh/original 改写：

```python
def build_paper(req, retrieval):
    # ... 现有逻辑 ...
    for item in retrieval.items:
        if item.question.question_type == "writing":
            # 作文题直接使用原题，不做改写
            revised = RevisedQuestion(
                question_type="writing",
                stem=item.question.stem,
                hint=item.question.hint,
                instruction=item.question.instruction,
                answer=None,
                knowledge_point_ids=item.question.knowledge_point_ids,
                reference_expressions=item.question.reference_expressions,
                min_words=item.question.min_words,
            )
        else:
            # 其他题型走正常 Reviser 流程
            revised = _revise_question(item, req.revision_intensity)
    # ...
```

**Prompt 修改**：`ai_engine/prompts/reviser_light.md` 和 `ai_engine/prompts/reviser_fresh.md`

在不变约束中补充：

```
- 英语作文（writing）：
  - 作文题目（stem/hint/instruction）不做任何改写
  - answer 必须为 null
  - 作文题的作用是让用户写作并提交批改，题目本身保持原样
```

### 2.4 Writing Grader（作文批改器）

**新增文件**：`ai_engine/writing_grader.py`

这是作文批改的核心模块，独立于现有 Solutioner：

```python
def grade_writing(
    question: RevisedQuestion,
    user_essay: str,
) -> WritingGradeResult:
    """批改一篇学生作文。
    
    调用 LLM 按三维度评分，返回结构化结果。
    详细评析（content_analysis/language_analysis 等）
    仅在用户是会员时由前端请求显示。
    """
```

**Prompt 文件**：`ai_engine/prompts/writing_grade.md`（基于现有 `writing.md` 改写）

见 §2.5。

### 2.5 Writing Grade Prompt

**修改文件**：`ai_engine/prompts/writing.md` → 重命名为 `writing_grade.md` 并修改为结构化输出

Prompt 需输出结构化 JSON（供 `instructor` + `pydantic` 解析）：

```jinja2
# Role
你是一位具有多年上海中考英语阅卷经验的资深教师。

# Scoring Framework（总分20分）
请严格按以下三个维度评分...

# Output Format
请以 JSON 格式输出批改结果，结构如下：
{
  "total_score": X.X,
  "content_score": X.X,
  "language_score": X.X,
  "organization_score": X.X,
  "word_count": XX,
  "level": "档次",
  "content_analysis": "...",
  "language_analysis": "...",
  "organization_analysis": "...",
  "overall_comment": "...",
  "revised_version": "..."
}

# Input
作文题目：{{ stem }}
写作提示：{{ hint }}
写作要求：{{ instruction }}
参考表达：{{ reference_expressions }}
最低词数：{{ min_words }}
学生作文：{{ user_essay }}
```

### 2.6 Solutioner 扩展

作文题不调用 Solutioner——作文的"解析"就是批改结果本身，由 `writing_grader.py` 产生。

---

## 3. 后端支持（Spec C 扩展）

### 3.1 新增批改端点

**新增文件**：`backend/api/writing.py`

```python
router = APIRouter(prefix="/writing", tags=["writing"])

@router.post("/grade", response_model=WritingGradeResponse)
async def grade_writing(
    body: WritingGradeRequest,
    user: User = Depends(current_user),
) -> WritingGradeResponse:
    """批改一篇英语作文。
    
    与客观题判分分离的独立端点。
    调用 LLM 进行三维度评分，返回结构化批改结果。
    """
```

**请求/响应模型**（`backend/schemas.py`）：

```python
class WritingGradeItem(BaseModel):
    index: int                          # 试卷中的题号
    user_essay: str                     # 用户作文内容

class WritingGradeRequest(BaseModel):
    paper_id: str
    items: list[WritingGradeItem]       # 通常只有 1 篇作文

class WritingGradeResponse(BaseModel):
    paper_id: str
    results: list[WritingGradeResult]  # 与 items 一一对应
    # 会员信息由前端另接口查询判断

class WritingGradeResult(BaseModel):
    index: int
    total_score: float                  # 0-20
    content_score: float                # 0-8
    language_score: float               # 0-8
    organization_score: float           # 0-4
    word_count: int
    level: str
    # 详细评析（会员专属，非会员为 null）
    content_analysis: str | None = None
    language_analysis: str | None = None
    organization_analysis: str | None = None
    overall_comment: str | None = None
    revised_version: str | None = None
```

### 3.2 批改流程

```
前端提交作文 → POST /api/writing/grade
  ↓
后端路由 → ai_gateway.grade_writing(paper_id, items)
  ↓
获取试卷 → 找到对应作文题
  ↓
调用 writing_grader.grade_writing(question, user_essay)
  ↓
LLM 三维度评分 → 返回 WritingGradeResult
  ↓
后端判断会员身份 → 非会员清空详细评析字段
  ↓
保存批改记录（可选，供"我的作文"回看）
  ↓
返回 WritingGradeResponse
```

### 3.3 会员判定逻辑

在 `backend/deps.py` 中新增会员依赖：

```python
async def require_member(user: User = Depends(current_user)) -> User:
    """要求用户为会员，否则返回 403。"""
    # 查询 membership 状态
    is_member = storage.check_membership(user.id)
    if not is_member:
        raise AuthorizationError("membership required")
    return user
```

作文批改端点对所有登录用户开放（可看分数），但**详细评析的获取**需要会员：

```python
@router.post("/grade", response_model=WritingGradeResponse)
async def grade_writing(body: WritingGradeRequest, user: User = Depends(current_user)):
    # 1. 批改对所有用户开放
    results = ai_gateway.grade_writing(...)
    
    # 2. 仅会员保留详细评析
    is_member = storage.check_membership(user.id)
    if not is_member:
        for r in results:
            r.content_analysis = None
            r.language_analysis = None
            r.organization_analysis = None
            r.overall_comment = None
            r.revised_version = None
    
    return WritingGradeResponse(paper_id=..., results=results)
```

### 3.4 路由注册

**修改文件**：`backend/main.py`

```python
from backend.api import writing as writing_api
app.include_router(writing_api.router, prefix="/api")
```

### 3.5 存储扩展

在 `shared/storage.py` 中新增作文批改记录方法：

```python
def save_writing_grade(
    user_id: str,
    paper_id: str,
    index: int,
    result: WritingGradeResult,
) -> None:
    """保存作文批改记录，供'我的作文'回看。"""

def get_writing_grades(
    user_id: str,
    paper_id: str,
) -> list[WritingGradeResult]:
    """获取某份试卷的所有作文批改结果。"""
```

---

## 4. 前端支持（Spec D 扩展）

### 4.1 类型定义扩展

**修改文件**：`frontend/src/types/api.ts`

```typescript
export type QuestionType =
  // ... 现有类型 ...
  | "writing";                          // 新增

export interface WritingGradeResult {
  index: number
  total_score: number
  content_score: number
  language_score: number
  organization_score: number
  word_count: number
  level: string
  content_analysis: string | null
  language_analysis: string | null
  organization_analysis: string | null
  overall_comment: string | null
  revised_version: string | null
}

export interface WritingGradeResponse {
  paper_id: string
  results: WritingGradeResult[]
}

export interface WritingGradeItem {
  index: number
  user_essay: string
}

export interface WritingGradeRequest {
  paper_id: string
  items: WritingGradeItem[]
}
```

### 4.2 作文答题组件

**新增文件**：`frontend/src/components/question-fields/WritingField.tsx`

```tsx
import { useState, useMemo } from 'react'
import type { RevisedQuestion } from '@/types/api'

interface WritingFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: string
  onChange?: (v: string) => void
}

/** 英语作文答题组件：题目 + 文本框 + 词数统计。 */
export function WritingField({ question, mode, value, onChange }: WritingFieldProps) {
  const [text, setText] = useState(value ?? '')
  
  const wordCount = useMemo(() => {
    if (!text.trim()) return 0
    return text.trim().split(/\s+/).length
  }, [text])
  
  const minWords = question.min_words ?? 60
  const isBelowMin = wordCount > 0 && wordCount < minWords
  
  if (mode === 'review') {
    return (
      <div className="space-y-3">
        <div className="rounded-md border border-hairline bg-wash p-4">
          <pre className="whitespace-pre-wrap text-[15px] leading-[1.8] text-ink">
            {text}
          </pre>
        </div>
        <p className="text-[12px] text-quiet">
          词数：{wordCount}
        </p>
      </div>
    )
  }
  
  return (
    <div className="space-y-3">
      {question.stem && (
        <h3 className="text-[17px] font-medium text-ink">{question.stem}</h3>
      )}
      {question.instruction && (
        <p className="text-[14px] text-quiet">{question.instruction}</p>
      )}
      {question.hint && (
        <div className="rounded-sm border border-hairline bg-wash px-3 py-2">
          <p className="text-[13px] leading-[1.8] text-ink">{question.hint}</p>
        </div>
      )}
      {question.reference_expressions && (
        <p className="text-[12.5px] text-quiet">
          参考表达：{question.reference_expressions}
        </p>
      )}
      <textarea
        rows={10}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          onChange?.(e.target.value)
        }}
        placeholder="在此输入你的作文..."
        className="w-full resize-y rounded-md border border-ink-20 bg-transparent px-4 py-3 text-[15px] leading-[1.8] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
      />
      <div className="flex items-center justify-between">
        <span className={`text-[13px] ${isBelowMin ? 'text-accent' : 'text-quiet'}`}>
          词数：{wordCount} / {minWords}
        </span>
        {isBelowMin && (
          <span className="text-[12px] text-accent">词数不足 {minWords} 词</span>
        )}
      </div>
    </div>
  )
}
```

### 4.3 QuestionCard 分派扩展

**修改文件**：`frontend/src/components/QuestionCard.tsx`

```tsx
) : question.question_type === 'writing' ? (
  <WritingField
    question={question}
    mode={mode}
    value={typeof value === 'string' ? value : undefined}
    onChange={onChange}
  />
) : (
```

### 4.4 批改结果展示组件

**新增文件**：`frontend/src/components/WritingGradeResult.tsx`

```tsx
import type { WritingGradeResult } from '@/types/api'
import { useMembership } from '@/hooks/useMembership'

interface WritingGradeResultProps {
  result: WritingGradeResult
  question: RevisedQuestion
}

/** 作文批改结果展示：总分表 + 会员专属详细评析。 */
export function WritingGradeResult({ result, question }: WritingGradeResultProps) {
  const { locked } = useMembership()
  
  return (
    <div className="space-y-6">
      {/* 1. 总分表（所有用户可见） */}
      <div className="rounded-md border border-accent/30 bg-wash p-5">
        <h3 className="text-center text-[24px] font-medium text-ink">
          {result.total_score} / 20 <span className="text-[16px] text-quiet">分</span>
        </h3>
        <p className="mt-1 text-center text-[13px] text-quiet">
          {result.level} · 词数 {result.word_count}
        </p>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <ScoreCard label="内容" score={result.content_score} max={8} />
          <ScoreCard label="语言" score={result.language_score} max={8} />
          <ScoreCard label="组织结构" score={result.organization_score} max={4} />
        </div>
      </div>
      
      {/* 2. 详细评析（会员专属） */}
      {!locked && (
        <div className="space-y-4">
          {result.content_analysis && (
            <Section title="📝 内容评析" content={result.content_analysis} />
          )}
          {result.language_analysis && (
            <Section title="✍️ 语言评析" content={result.language_analysis} />
          )}
          {result.organization_analysis && (
            <Section title="🏗️ 组织结构评析" content={result.organization_analysis} />
          )}
          {result.overall_comment && (
            <Section title="🌟 总体评价" content={result.overall_comment} />
          )}
          {result.revised_version && (
            <Section title="🔧 修改范文" content={result.revised_version} />
          )}
        </div>
      )}
      {locked && (
        <div className="rounded-md border border-hairline bg-wash p-4 text-center">
          <p className="text-[13px] text-quiet">
            详细评析、错误分析与修改范文为会员功能
          </p>
          <UpgradeButton reason="解锁作文详细评析、错误定位、修改范文" />
        </div>
      )}
    </div>
  )
}

function ScoreCard({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = (score / max) * 100
  return (
    <div className="rounded-sm border border-hairline p-3 text-center">
      <p className="text-[12px] text-quiet">{label}</p>
      <p className="mt-1 text-[20px] font-medium text-ink">
        {score} <span className="text-[13px] text-quiet">/ {max}</span>
      </p>
      <div className="mt-2 h-1 rounded-full bg-hairline">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-md border border-hairline p-4">
      <h4 className="mb-2 text-[14px] font-medium text-ink">{title}</h4>
      <div className="whitespace-pre-wrap text-[13.5px] leading-[1.8] text-ink">
        {content}
      </div>
    </div>
  )
}
```

### 4.5 PaperPage 适配

**修改文件**：`frontend/src/pages/PaperPage.tsx`

作文题有特殊的提交流程——不参与客观题判分，走独立的 `POST /api/writing/grade`：

```typescript
// 识别作文题
const writingItems = paper.items.filter(
  (item) => item.question.question_type === 'writing'
)
const objectiveItems = paper.items.filter(
  (item) => item.question.question_type !== 'writing'
)

// 客观题走原有提交流程
// 作文题走独立批改流程
async function handleSubmit() {
  // 1. 先提交客观题（如果有）
  if (objectiveItems.length > 0) {
    await submitAttempt({ paper_id, items: objectiveItemsSubmission })
  }
  
  // 2. 批改作文题
  if (writingItems.length > 0) {
    const writingResponse = await gradeWriting({
      paper_id,
      items: writingItems.map((item) => ({
        index: item.index,
        user_essay: answers[item.index] as string,
      })),
    })
    // 展示批改结果
  }
}
```

### 4.6 答案构建扩展

**修改文件**：`frontend/src/lib/answers.ts`

作文题答案为纯字符串（用户输入的作文全文），`AnswerDraft` 已是 `string | BlankMap` 联合，天然支持：

```typescript
// WritingField 的 value/onChange 使用 string 类型
// buildSubmission 对 writing 题型提交完整作文文本
```

### 4.7 题型标签

**修改文件**：`frontend/src/lib/kp.ts`（`TYPE_LABELS`）

```typescript
writing: '英语作文',
```

---

## 5. 题库摄入支持

### 5.1 数据文件

作文题数据模板文件：`data/chapters/shanghai_writing.json`

ID 从 `q_30001` 开始，格式遵循 §1.2 定义。

### 5.2 SQLite schema 扩展

**修改文件**：`ingestion/sqlite/schema.sql`

```sql
-- knowledge_points 表：CHECK 约束加 writing
CREATE TABLE IF NOT EXISTS knowledge_points (
    id            TEXT PRIMARY KEY,
    level1        TEXT NOT NULL
                    CHECK (level1 IN (
                        'single_choice', 'word_form', 'sentence_rewriting',
                        'listening_single_choice', 'listening_true_false',
                        'listening_fill_blank',
                        'reading_longtext_single_choice',
                        'cloze_single_choice',
                        'reading_first_blank',
                        'writing'    -- 新增
                    )),
    level2        TEXT NOT NULL,
    aliases_json  TEXT NOT NULL DEFAULT '[]'
);

-- questions 表：CHECK 约束加 writing
CREATE TABLE IF NOT EXISTS questions (
    -- ... 现有列 ...
    question_type  TEXT NOT NULL
                      CHECK (question_type IN (
                          'single_choice', 'word_form', 'sentence_rewriting',
                          'listening_single_choice', 'listening_true_false',
                          'listening_fill_blank',
                          'reading_longtext_single_choice',
                          'cloze_single_choice',
                          'reading_first_blank',
                          'writing'    -- 新增
                      )),
    -- 新增字段
    reference_expressions  TEXT,   -- 参考表达
    min_words              INTEGER -- 最低词数要求
    -- ... 其他列 ...
);
```

### 5.3 loader 扩展

**修改文件**：`ingestion/sqlite/loader.py`

#### 5.3.1 `_stem_hash` 加分支

```python
elif qt == "writing":
    # 作文题：stem + hint + instruction（无 answer）
    payload["stem"] = q.get("stem")
    payload["hint"] = q.get("hint")
    payload["instruction"] = q.get("instruction")
```

#### 5.3.2 INSERT 语句加字段

```python
cur = conn.execute(
    """
    INSERT OR IGNORE INTO questions (
        id, book, question_type, chapter_l1, chapter_l2, number,
        stem, options_json, hint,
        original_sentence, instruction, template,
        passage_id, passage_json,
        reference_expressions, min_words,
        answer_json, solution,
        source_md, source_line, stem_hash,
        created_at, version
    ) VALUES (?, ?, ?, ?, ?, ?,
              ?, ?,
              ?,
              ?, ?, ?,
              ?, ?,
              ?, ?,
              ?, ?,
              ?, ?, ?,
              ?, ?)
    """,
    (
        q["id"], q["book"], q["question_type"],
        q["chapter_l1"], q["chapter_l2"] or "", q["number"],
        q.get("stem"), options_json, q.get("hint"),
        q.get("original_sentence"), q.get("instruction"), q.get("template"),
        q.get("passage_id"),
        json.dumps(q["passage_json"], ensure_ascii=False) if q.get("passage_json") else None,
        q.get("reference_expressions"),
        q.get("min_words"),
        answer_json, None,
        q["source_md"] or "", q["source_line"], _stem_hash(q),
        now, 1,
    ),
)
```

### 5.4 不做向量库（明确）

**修改文件**：`ingestion/chromadb/loader.py`

作文题加入 `NON_VECTOR_TYPES`，不写入 ChromaDB 集合。

### 5.5 构建命令

```bash
# 重新构建 SQLite（新增作文题）
python -m ingestion.cli build-sqlite

# 作文题不会写入向量库（已自动跳过）
```

---

## 6. 测试

### 6.1 后端集成测试

在 `tests/integration/backend/` 中添加：

- `test_writing_grade.py`：
  - 提交作文批改，验证返回三维度得分
  - 验证非会员返回时详细评析字段为 null
  - 验证会员返回时详细评析字段完整
  - 验证词数统计正确

### 6.2 前端组件测试

- `WritingField.test.tsx`：
  - 文本框渲染与输入
  - 词数统计实时更新
  - 词数不足时的警告显示
  - review 态只读展示

- `WritingGradeResult.test.tsx`：
  - 总分表渲染
  - 非会员时详细评析隐藏
  - 会员时详细评析显示

### 6.3 AI Engine 测试

- Parser：`writing` 题型的 user_query → question_types 映射
- Reviser：作文题不被改写，直接使用原题
- Writing Grader：LLM 返回结构化结果解析

---

## 7. 里程碑

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 数据契约扩展（QuestionType、WritingGradeResult、新增字段） | 待实现 |
| 2 | knowledge_tree.json 加 kp_writing | 待实现 |
| 3 | SQLite schema.sql 加 writing + 新增字段 | 待实现 |
| 4 | loader.py 扩展（_stem_hash + INSERT） | 待实现 |
| 5 | chromadb/loader.py 跳过 writing | 待实现 |
| 6 | 创建作文题库 JSON 模板 | 待实现 |
| 7 | AI Engine Parser 扩展 | 待实现 |
| 8 | AI Engine Retriever 扩展（SQL only） | 待实现 |
| 9 | AI Engine Reviser 扩展（不做改写） | 待实现 |
| 10 | AI Engine Writing Grader 实现 | 待实现 |
| 11 | Writing Grade Prompt 修改 | 待实现 |
| 12 | 后端 writing.py 路由 + 会员判定 | 待实现 |
| 13 | 前端 WritingField 组件 | 待实现 |
| 14 | 前端 WritingGradeResult 组件 | 待实现 |
| 15 | 前端 QuestionCard + PaperPage 适配 | 待实现 |
| 16 | 前端 TYPE_LABELS 扩展 | 待实现 |
| 17 | 测试 | 待实现 |

---

## 8. 开放问题

1. **作文与客观题混合试卷**：若一份试卷既有作文又有客观题，需要先提交客观题（同步），再批改作文（异步）。当前设计分两步提交，可能导致 UX 复杂。可考虑在"生成试卷"时就区分开：作文卷和客观题卷分别处理。

2. **多篇作文批改**：当前设计支持一份试卷多篇作文（罕见但可能），`WritingGradeRequest.items` 为数组。LLM 调用串行还是并行待定。

3. **批改超时处理**：LLM 批改可能耗时较长（5-15秒）。前端需有 loading 状态和超时重试机制。超时后可降级：仅显示"批改中，请稍后查看"。

4. **词数统计方式**：当前按空格分词（英文标准）。若用户输入中文标点连写，词数可能偏低。可考虑更精确的分词方案（如 spaCy），但增加依赖。当前方案够用。

5. **批改结果持久化**：批改结果当前存于 `paper.items[].question.solution` 字段复用，或新增 `writing_grades` 表。新增表更清晰但需改 schema，复用字段简单但语义不准确。**建议新增 `writing_grades` 表**。

6. **会员门槛的合理性**：非会员只能看分数表，看不到具体哪里错。这是否足以吸引用户付费？可能需要调整：非会员可看 1-2 条评析摘要（如"语法错误较多"），会员看完整详情。

---

## 9. 不变量

1. **作文题 answer 恒为 null**：作文题无标准答案，不由 Reviser 生成 answer。

2. **作文题不进向量库**：`writing` 永远不写入 ChromaDB 集合，Retriever 只走 SQL 路径。

3. **作文题不被 Reviser 改写**：`original`/`light`/`fresh` 三档均不修改作文题目内容，原样使用。

4. **批改独立端点**：作文判分始终走 `POST /api/writing/grade`，不混在 `POST /api/attempts` 中。

5. **非会员仅可见分数表**：提交批改后，非会员只能看到总分和三维度得分表，详细评析、修改范文等字段为 null。

6. **词数统计基于空格分词**：`word_count = text.trim().split(/\s+/).length`。

7. **QuestionType / knowledge_point_ids 不可变**：与其他题型一致。

---

## 10. 与现有 spec 的接口

- **Spec A**：扩展 `Question` / `RevisedQuestion` 数据契约（加 `reference_expressions` / `min_words` 字段）；扩展 SQLite schema（加列 + CHECK）
- **Spec B**：Parser 加题型枚举；Retriever 加 SQL-only 路径；Reviser 加不做改写逻辑；新增 `writing_grader.py`
- **Spec C**：新增 `POST /api/writing/grade` 端点；扩展存储层
- **Spec D**：前端加 `WritingField` / `WritingGradeResult` 组件；PaperPage 适配作文题提交流程
- **会员系统**：复用 `useMembership` / `require_member` 模式控制详细评析的可见性
