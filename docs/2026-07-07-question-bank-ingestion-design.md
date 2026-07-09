# Spec A：中考英语题库构建管线设计

**创建日期**：2026-07-07
**项目根目录**：`C:\Users\I779318\Desktop\CSS\English_Test_Paper_AI_Generator`
**范围**：从原始 EPUB 教辅书到"结构化、可检索、可生成"题库的完整入库管线
**状态**：设计中；配套的 AI Engine 设计（Spec B）尚未撰写，将在本 spec 获批后开始

---

## 0. 项目背景与整体愿景

本项目目标是构建一个**中考英语 AI 试卷生成系统**，让学生输入自然语言需求（如"来 10 道现在完成时的单选中等难度"），系统能从题库检索相关题目、按用户设定的改题尺度加工、生成一份完整试卷。系统还支持基于错题或历史答题记录生成针对性练习。

**整体架构**由若干子系统组成：

- **题库构建管线**（`ingestion/`）：本 spec 的主题
- **AI Engine**（`ai_engine/`）：消费题库产出试卷，见 Spec B
- **FastAPI 后端 + React 前端**：本轮不做，暂时搁置；未来另立 spec

**题库构建与 AI Engine 的边界**：两者通过共享数据契约（`shared/schemas.py`）和存储层（`shared/storage.py`）解耦。题库构建**只写**题库（除幂等去重需要查询外），AI Engine **只读**题库（Solutioner 一处例外，见 Spec B）。这份 spec 完整定义共享契约；Spec B 只引用不复制。

---

## 1. 覆盖范围与关键决策

### 1.1 学科与题型

- **学科**：中考英语
- **题型（三种一级类型）**：
  - `single_choice`：单项选择
  - `word_form`：词性转换（填空）
  - `sentence_rewriting`：改写句子（填空）
- **不覆盖**：阅读理解、作文
- **无图片**：所有题目为纯文本

### 1.2 数据源

- **原始形态**：EPUB 电子书
- **预处理**：脚本转 `.md`（`ebooklib` + `beautifulsoup4` + `html2text`）
- **原始文档不含解析**——解析文本由用户在做题后按需通过 AI Engine 生成（Solutioner 职责，见 Spec B）

### 1.3 存储

- **SQLite** 存题目主数据、知识点、答题记录
- **ChromaDB**（持久化模式）存题目向量
- **Embedding 模型**：本地 Qwen embedding 4B

### 1.4 知识点结构

- **两级层次**，用 `parent_id` 表达（扁平表）
- **一级 = 题型**：`single_choice` / `word_form` / `sentence_rewriting`，三个固定值
- **二级 = 具体考点**：如"时态/现在完成时"、"介词"、"定语从句"、"动词变名词"等；由 LLM 从章节标题归并得到，经**人工审核**后固化

### 1.5 无 LLM 生成解析

- 入库时 `Question.solution = None`
- 用户点"生成解析"时由 AI Engine 的 Solutioner 按需生成
- 只对题库原题（`revision_mode="original"`）缓存写回 `questions.solution` 字段
- 详见 Spec B

### 1.6 判对错不属于 AI Engine 职责

- 前端提交答案后，由未来的 FastAPI 后端做**规范化字符串比较**（小写、trim、多空白折叠、末尾标点忽略）
- 答案唯一，无歧义（用户已明确）
- 本 spec 只保证题库的 `answer` 字段被填好

---

## 2. 共享数据契约（`shared/schemas.py`）

**这一节是两份 spec 的锚点**。所有 pydantic 模型定义在此，AI Engine spec 引用不复制。

### 2.1 知识点

```python
class KnowledgePoint(BaseModel):
    id: str                    # "kp_single_choice_tense_present_perfect"，稳定 slug
    level1: str                # "single_choice" / "word_form" / "sentence_rewriting"
    level2: str                # "时态/现在完成时" 等
    aliases: list[str] = []    # 同义词（书上可能"动词时态"/"时态"混用）
    parent_id: str | None      # 一级 parent=None；二级 parent 指向所属一级
```

- 一级三条根记录永久固定
- 二级由 ingestion 阶段生成后经**人工审核**固化（见 §3.4）
- `id` 一旦入库不再更改

### 2.2 题目

```python
class Question(BaseModel):
    id: str                          # "q_00042"，稳定
    source: QuestionSource
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    stem: str                        # 题干；填空题用 "___" 表示空
    options: list[Option] | None     # 仅 single_choice；其他题型 None
    answer: str                      # 标准答案（唯一）
                                     #   single_choice: "B"
                                     #   word_form: "written"
                                     #   sentence_rewriting: 完整改写句
    solution: str | None = None      # 入库时为 None；按需生成后可写回
    knowledge_point_ids: list[str]   # 引用 KP.id，通常 1–2 个；至少含一个二级 KP
    difficulty: Literal["easy", "medium", "hard"]
    embedding_text: str              # 供 embedding 的规范化文本（见 §2.6）
    created_at: datetime
    version: int = 1                 # ingestion 层再入库时递增；AI Engine 不写

class Option(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str

class QuestionSource(BaseModel):
    book: str                        # 书名
    chapter: str | None              # EPUB 章节标题
    raw_ref: str | None              # data/raw_md/... 的引用（追溯用）
```

### 2.3 试卷（AI Engine 产出，本 spec 中不生成）

```python
class Paper(BaseModel):
    paper_id: str                    # AI Engine 生成的 UUID hex（Spec B § 5.4）
                                     # 由后端持久化到 papers 表（Spec C § 3.1）
    title: str
    generated_at: datetime
    request: GenerateRequest         # 回填生成时的请求
    items: list[PaperItem]
    total_score: int
    metadata: dict[str, Any] = {}    # 生成过程留痕

class PaperItem(BaseModel):
    index: int                       # 题号（1-based）
    question: RevisedQuestion
    score: int
    source_question_id: str          # 溯源到题库原题
    revision_mode: Literal["fresh", "light", "original"]
    revision_notes: str | None       # LLM 记录的改动摘要（fresh/light 时有）

class RevisedQuestion(BaseModel):
    """结构与 Question 一致，但字段可为改动版；不含 id/source/created_at 等元字段。"""
    stem: str
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    options: list[Option] | None
    answer: str
    solution: str | None = None      # 生成时不填；用户点"生成解析"时按需算
    knowledge_point_ids: list[str]
    difficulty: Literal["easy", "medium", "hard"]
```

### 2.4 生成请求（AI Engine 使用）

```python
class GenerateRequest(BaseModel):
    mode: Literal["fresh", "remediation", "review"]
    # fresh: 全新试卷
    # remediation: 能力 A，基于本次错题
    # review: 能力 B，基于历史掌握度

    # 通用字段
    knowledge_points: list[str] = []      # KP.id；空 = 不限
    knowledge_points_exclude: list[str] = []
    question_types: list[Literal["single_choice", "word_form",
                                 "sentence_rewriting"]] = []
    difficulty: list[Literal["easy", "medium", "hard"]] = []
    total_questions: int
    total_score: int | None = None        # 空 = 自动分配

    # 分布约束（可选）
    type_distribution: dict[str, int] = {}
    difficulty_distribution: dict[str, int] = {}
    per_kp_min: int = 0                   # 每个显式指定的 KP 至少 N 题

    # 改题尺度（由 Parser 内的 LLM 从用户 user_query 推断，见 Spec B § 3.5）
    revision_intensity: Literal["fresh", "light", "original"] = "light"
    # 默认值仅在测试代码或调试脚本直接构造 GenerateRequest 时生效；
    # 生产路径下 Parser 保证此字段被 LLM 输出填充（ParserLLMResponse 必填）。
    # fresh    : 参照原题风格，按 KP+难度重新出题
    # light    : 保留原题结构，改数值/词汇/情境；同步更新 answer 和 options
    # original : 直接用原题（Reviser 退化为 pass-through）

    # remediation / review 专用
    wrong_items: list[WrongItemRef] = []
    user_id: str | None = None
    review_window_days: int | None = None

    # 自由文本（保留用户原话，供 Reviser 参考语气/情境）
    free_text: str = ""

class WrongItemRef(BaseModel):
    """能力 A 使用：前端把刚做完的错题元数据发过来。"""
    knowledge_point_ids: list[str]
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    difficulty: Literal["easy", "medium", "hard"]
```

### 2.5 答题记录 & 掌握度画像

```python
class Attempt(BaseModel):
    """做完一份试卷后前端上报的最小信息。不存试卷、不存题面，只存元数据。"""
    user_id: str
    paper_id: str                    # AI Engine 生成、后端持久化的 paper_id
                                     # (Spec B § 5.4 / Spec C § 3.1 papers 表主键)
    answered_at: datetime
    items: list[AttemptItem]

class AttemptItem(BaseModel):
    source_question_id: str          # 溯源用；不用于 mastery 计算
    knowledge_point_ids: list[str]
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    difficulty: Literal["easy", "medium", "hard"]
    is_correct: bool

class MasteryProfile(BaseModel):
    """Analyzer 产出，Parser 消费（Spec B）。"""
    user_id: str
    window_days: int | None          # 时间窗
    weak_kps: list[KPMastery]        # 按 mastery 升序，前 N 个
    dominant_types: list[str]        # 出错最多的题型
    total_attempts_considered: int

class KPMastery(BaseModel):
    knowledge_point_id: str
    attempts: int
    correct_rate: float
    mastery: float                   # Wilson score lower bound（低样本降权）
```

### 2.6 Embedding 文本规范

`Question.embedding_text` 是**入库时预计算并持久化**的字符串，格式：

```
[题型] 单项选择
[考点] 时态/现在完成时
[难度] 中
[题干] I ___ my homework since 6 p.m.
[选项] A) do  B) am doing  C) have done  D) had done
```

- 加中文属性标签，让 Qwen embedding 同时捕获属性和内容
- 单选题把选项拼进去；填空题只有 `[题干]`
- Retriever 阶段用户描述按同模板拼后 embed

### 2.7 数据契约不变量

1. **`Question.id`、`KnowledgePoint.id` 永不变更**（改题产生的是 `RevisedQuestion`，无独立 id）
2. **`Attempt.source_question_id` 必须是入库题的 id**（不是改后题的临时 id）
3. **Reviser 不能修改 `knowledge_point_ids` / `question_type` / `difficulty`**——否则答题记录的知识点归属会和真实生成的题不符
4. **`revision_mode="original"` 时，`RevisedQuestion` 内容与 `Question` 对应字段完全一致**（不允许"顺手改一下"）
5. **答案唯一**：`answer` 是标准字符串；判等规则由后端实现，AI Engine 不做判等
6. **`solution` 写回题库的唯一条件**：`source_question_id` 存在、`revision_mode="original"`、题库中该题 `solution IS NULL`。任一不满足都不写回

---

## 3. 题库构建管线

### 3.1 管线总览

```
┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌ ─ ─ ─ ─ ─ ─ ┐   ┌──────────────┐   ┌──────────────┐
│  EPUB 文件  │→ │ epub_to_md   │→ │ chapter_     │→ │ knowledge_   │→ │ 人工审核 KB │→ │ question_    │→ │  loader      │
│  (若干本)   │   │ (脚本)       │   │ splitter     │   │ tree_builder │   │  (关键关卡) │   │ extractor    │   │ (双写)       │
└─────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └ ─ ─ ─ ─ ─ ─ ┘   └──────────────┘   └──────────────┘
                       ↓                    ↓                  ↓                    ↓                    ↓                  ↓
                  data/raw_md/       chapter 树 (JSON)  KnowledgeTree      knowledge_       Question 列表     SQLite + Chroma
                  *.md               带层级和路径       Draft (JSON)       tree.json         (含 KP 引用)      完成入库
```

六个自动化阶段 + 一个人工审核关卡。每一步产物都落盘（可断点续做、可肉眼审核）。人工审核关卡即§3.4 描述的 `knowledge_tree_draft.json → knowledge_tree.json` 手动重命名步骤。

### 3.2 阶段 1：EPUB → Markdown（`ingestion/epub_to_md.py`）

**纯脚本，无 LLM。**

- 用 `ebooklib` 读取 EPUB，提取每一份 HTML section
- 用 `beautifulsoup4` + `html2text` 转 Markdown，保留 `# / ## / ###` 层次
- 产出：`data/raw_md/<book_slug>/<section_index>.md`，一个 section 一个文件
- 附产：`data/raw_md/<book_slug>/manifest.json` 记录 section 顺序、原始 HTML 文件名，便于追溯

### 3.3 阶段 2：章节切分（`ingestion/chapter_splitter.py`）

**纯规则处理，无 LLM。**

把 md 切分为章节层次树：

```python
class ChapterNode(BaseModel):
    path: list[str]              # 从根到本节的标题链路，如
                                 # ["单项选择", "语法", "时态", "现在完成时"]
    depth: int                   # len(path)
    section_file: str            # 对应的 md 文件路径
    section_offset: tuple[int, int] | None  # md 文件内的字节范围
    body: str                    # 本节正文（不含子节）
    children: list["ChapterNode"] = []
```

- 遍历 md 文件的标题层级构建树
- 每个 `ChapterNode` 保留其在文件中的原始范围，便于后续引用回 md
- 输出：`data/chapters/<book_slug>.json`

**为什么单独一步**：知识点树的构建和题目抽取都要引用同一份章节树。集中一次结构化，下游各阶段直接吃 JSON。

### 3.4 阶段 3：知识点树构建（`ingestion/knowledge_tree_builder.py`）

**第一处需要 LLM 的地方。** 目标：把散落在多本书里、层次不一的章节标题，归并为统一的两级知识点体系。

**流程**：

1. **一级固定**：三个固定值 `single_choice / word_form / sentence_rewriting` 在代码中定义为常量
2. **分组归入一级**：对每本书的章节树，用启发式（章节顶层标题匹配"单项选择/词性转换/改写句子"等关键词）+ LLM 兜底歧义章节
3. **二级聚合**：把所有归入同一一级的叶子章节标题收集起来（跨书），一次性交给 LLM：
   > "这是若干章节标题，可能有同义、拼写差异、粗细粒度差异，请归并为一个规范的二级知识点列表，输出 JSON"
4. **产出**：

```python
class KnowledgeTreeDraft(BaseModel):
    knowledge_points: list[KnowledgePoint]
    chapter_to_kp: dict[str, list[str]]
    # 键：`"/".join(ChapterNode.path)`，例如 "单项选择/语法/时态/现在完成时"
    # 值：list[KP.id]，一个章节可能对应多个 KP
```

- LLM 走 DeepSeek + JSON Mode + pydantic 校验 + 重试（用 `instructor` 库，详见 §4）
- 输出保存到 `data/kb/knowledge_tree_draft.json`

**人工审核关（关键设计选择）**：

`knowledge_tree_draft.json` **不自动进库**。运行者过一眼，可以：
- 改 `id`（如统一命名风格）
- 合并近义 KP
- 拆分粒度过粗的 KP
- 补 `aliases`

确认后**手动重命名**为 `data/kb/knowledge_tree.json`。下游阶段读的是"审核过"的版本。

**为什么这么做**：知识点体系是全库骨架，一旦入库难改（改一个 `id` 要级联更新所有引用它的题目）。开销就 5–10 分钟人工，值得。

### 3.5 阶段 4：题目结构化（`ingestion/question_extractor.py`）

**第二处 LLM。** 目标：把每个 `ChapterNode.body` 里的题目原文抽成 `Question` 对象。

**分批策略**：一个章节可能含几十道题。逐节 → 分批（每批约 5–8 道题的字符量）传给 LLM，避免上下文过长导致遗漏。

**LLM 输入**：

```
[你所在章节路径] 单项选择 > 语法 > 时态 > 现在完成时
[候选知识点 id] kp_single_choice_tense_present_perfect,
                kp_single_choice_tense_past_simple, ...
              （从 knowledge_tree.chapter_to_kp 里预先解析出来的候选，帮 LLM 减少幻觉）
[章节正文片段]
...

请把其中所有独立题目抽取为 Question JSON 列表，Schema 见下方 ...
```

**LLM 产出（每道题）**：

- `stem`, `options`（若单选）, `answer`, `question_type`, `difficulty`
- `knowledge_point_ids`：LLM 从候选 id 里选（不允许发明新 id；后处理校验）
- **不填** `solution`（见 § 1.5 决策：入库不带解析，按需生成）
- **不填** `id`（由 loader 生成）

**难度打标**：`difficulty` 书上通常不标。策略：让 LLM 基于题面复杂度、词汇难度、语法结构给一个 `easy/medium/hard` 的启发式估计。**入库时保留**，允许未来通过后端接口人工修正。

**逐节产出**：`data/extracted/<book_slug>/<section_idx>.json`，一个 section 一份题目列表。

### 3.6 阶段 5：Loader（`ingestion/loader.py`）

**无 LLM，纯代码。** 把 `data/extracted/` 下所有题目 + `knowledge_tree.json` 一次性写入 SQLite + ChromaDB。

- 生成稳定 `Question.id`（如 `q_00001`，全库连号；跨批入库时读当前最大 id 递增）
- 计算 `embedding_text`（按 §2.6 模板）
- 用 `shared/embedding.py` 算 Qwen embedding 向量
- SQLite 写入 `knowledge_points`、`questions`、`question_knowledge_points` 表
- ChromaDB 写入向量集合，`metadata` 存 `question_type / difficulty / kp_ids`（供属性硬过滤）

**幂等性**：Loader 支持"重复运行不重复入库"——按 `(book, chapter, stem_hash)` 三元组做去重键。修改 extractor 后重跑不会污染库。

### 3.7 SQLite 表结构

```sql
CREATE TABLE knowledge_points (
    id           TEXT PRIMARY KEY,
    level1       TEXT NOT NULL,      -- single_choice / word_form / sentence_rewriting
    level2       TEXT NOT NULL,
    parent_id    TEXT REFERENCES knowledge_points(id),
    aliases_json TEXT NOT NULL        -- JSON list
);

CREATE TABLE questions (
    id                    TEXT PRIMARY KEY,
    book                  TEXT NOT NULL,
    chapter               TEXT,
    raw_ref               TEXT,       -- data/raw_md/... 的引用
    question_type         TEXT NOT NULL,
    stem                  TEXT NOT NULL,
    options_json          TEXT,       -- JSON list; single_choice 才有
    answer                TEXT NOT NULL,
    solution              TEXT,       -- 允许 NULL；按需生成后可写回
    difficulty            TEXT NOT NULL,
    embedding_text        TEXT NOT NULL,
    created_at            TIMESTAMP NOT NULL,
    version               INTEGER NOT NULL DEFAULT 1,
    stem_hash             TEXT NOT NULL,
    UNIQUE(book, chapter, stem_hash)  -- 幂等键
);

CREATE TABLE question_knowledge_points (
    question_id         TEXT NOT NULL REFERENCES questions(id),
    knowledge_point_id  TEXT NOT NULL REFERENCES knowledge_points(id),
    PRIMARY KEY (question_id, knowledge_point_id)
);

CREATE INDEX idx_q_type       ON questions(question_type);
CREATE INDEX idx_q_difficulty ON questions(difficulty);
CREATE INDEX idx_qkp_kp       ON question_knowledge_points(knowledge_point_id);
```

**答题记录相关表**（供未来 FastAPI 后端使用；本 spec 定义结构，AI Engine 的 Analyzer 只读它）：

```sql
CREATE TABLE attempts (
    id            TEXT PRIMARY KEY,  -- UUID
    user_id       TEXT NOT NULL,
    paper_id      TEXT NOT NULL,     -- AI Engine 生成、后端持久化的 paper_id
    answered_at   TIMESTAMP NOT NULL
);

CREATE TABLE attempt_items (
    attempt_id             TEXT NOT NULL REFERENCES attempts(id),
    source_question_id     TEXT NOT NULL,
    question_type          TEXT NOT NULL,
    difficulty             TEXT NOT NULL,
    is_correct             INTEGER NOT NULL,   -- 0/1
    kps_json               TEXT NOT NULL,       -- 冗余存储 KP id 列表
    PRIMARY KEY (attempt_id, source_question_id)  -- 同一 attempt 内一道题只记一次
);

CREATE INDEX idx_att_user      ON attempts(user_id);
CREATE INDEX idx_att_answered  ON attempts(answered_at);
CREATE INDEX idx_att_it_source ON attempt_items(source_question_id);  -- 便于按题回溯
```

**关于 `kps_json` 冗余**：本可从 `source_question_id` 关联出来，但 Analyzer 的聚合查询大量按 KP 分组——冗余可省一次 join，且答题当时的 KP 归属是历史事实，冗余存储比动态计算更稳。

**关于 `users` / `sessions` / `papers` 表**：这三张表由 [Spec C](./2026-07-07-backend-design.md) § 3.1 定义（对应用户体系与试卷持久化）。它们与本 spec 的表**同处一个 SQLite 文件**，通过 `shared/storage.py` 统一访问。本 spec 的 `attempts` / `attempt_items` 与 Spec C 的 `papers` 通过 `paper_id` 关联，与 `users` 通过 `user_id` 关联。

### 3.8 ChromaDB 集合结构

单一集合 `questions`：

- `ids`：`Question.id`
- `embeddings`：Qwen embedding 4B 输出向量
- `documents`：`Question.embedding_text`（便于调试观察）
- `metadatas`：
  ```python
  {
      "question_type": "single_choice",
      "difficulty": "medium",
      "kp_ids": "kp_a,kp_b",   # 逗号分隔字符串（Chroma metadata 不支持 list）
      "book": "..."
  }
  ```

Retriever 检索时用 `where` 过滤 `question_type`、`difficulty`；`kp_ids` 用 Python 端二次过滤或 `$contains`（视 Chroma 版本）。

### 3.9 CLI 使用

```bash
# 1. 转换 EPUB
python -m ingestion.cli epub-to-md ./raw_books/zhongkao_english_2024.epub

# 2. 切章节
python -m ingestion.cli split-chapters zhongkao_english_2024

# 3. 生成知识点树草稿（LLM）
python -m ingestion.cli build-kb-draft --books all

# 4. ★ 人工审核 data/kb/knowledge_tree_draft.json，改完保存为 knowledge_tree.json

# 5. 结构化抽题（LLM，按 book）
python -m ingestion.cli extract --book zhongkao_english_2024

# 6. 入库（双写 SQLite + Chroma）
python -m ingestion.cli load --book zhongkao_english_2024
```

- 每一步产物落盘、可断点重跑
- 步骤 5、6 支持增量（幂等去重）

### 3.10 与 AI Engine 的边界

- `ingestion/` **只写不读**（除幂等去重需要查 `stem_hash`）
- 入库完成后，`ai_engine/` 只通过 `shared/storage.py` 读；`shared/schemas.py` 是唯一契约
- ChromaDB 目录和 SQLite 文件路径由 `shared/config.py` 统一定义

---

## 4. LLM 稳定输出栈（与 ingestion 相关部分）

Ingestion 有两处调用 LLM（知识点归并、题目抽取）。稳定输出的完整设计放在 Spec B（因为 AI Engine 是主要消费方），此处只讲 ingestion 层需要的**最小子集**。

### 4.1 唯一的 LLM 出口

所有 LLM 调用（ingestion 与 AI Engine 两个子系统）统一走 `shared/llm/deepseek.py::DeepSeekClient`。把 LLM 客户端放在 `shared/` 而非某个子系统内，是为了避免子系统间依赖（`ingestion → ai_engine` 的反常方向）。

Ingestion 通过 `from shared.llm.deepseek import get_client` 拿单例实例。

### 4.2 结构化输出的三层防御

```
LLM 原始输出
   ↓
Layer 1: JSON Mode          ← DeepSeek response_format={"type":"json_object"}
   ↓
Layer 2: pydantic 校验       ← instructor 用 response_model 校验字段类型/枚举
   ↓
Layer 3: 语义校验（本地代码） ← 校验业务不变量（如 KP id 是否在候选中）
```

**Layer 3 在 ingestion 里的具体体现**：

- 知识点树构建后：所有 `KP.parent_id` 必须存在于同批产物内；`level1` 只能取三个固定值
- 题目抽取后：`knowledge_point_ids` 里的每个 id 都必须在 `knowledge_tree.json` 里存在（不允许 LLM 造 id）；`question_type` 与所在章节归属的一级 KP 必须一致

**违反 Layer 3 的处理**：不重试 LLM，而是**丢弃该条 + 记 warning**，让运行者在批处理结束后看 log 决定是否人工补救。

### 4.3 Prompt 组织

Ingestion 有两份 prompt：

```
ingestion/prompts/
├── build_kb.md              # 知识点树归并
└── extract_questions.md     # 题目结构化
```

- Markdown 文件 + Jinja2 变量渲染
- 每份模板顶部注释列出所有变量名
- 模板结构约定：`system` 部分和 `user` 部分用 `---` 分隔

### 4.4 观测

每次 LLM 调用写入 `data/llm_traces/index.jsonl`（每行一条 JSON 摘要，**不入 SQLite**）：

```python
class LLMTrace(BaseModel):
    call_id: str                     # UUID
    module: str                      # "ingestion.knowledge_tree_builder" / ...
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    retries: int
    ok: bool
    error: str | None
    prompt_preview: str              # 前 500 字符
    output_preview: str              # 前 500 字符
    prompt_full_ref: str | None      # 满 prompt 落 data/llm_traces/<call_id>.json（默认关闭）
    timestamp: datetime
```

- 摘要恒开
- 满 prompt/输出仅 `LLM_TRACE_FULL=1` 时开启（避免磁盘爆炸）

---

## 5. 目录结构（ingestion 部分及共享部分）

```
English_Test_Paper_AI_Generator/
├── README.md
├── pyproject.toml                    # 依赖列表
├── .env.example                      # DEEPSEEK_API_KEY=...
│
├── shared/                           # 两个子系统共享
│   ├── __init__.py
│   ├── schemas.py                    # 本 spec §2 所有 pydantic 模型
│   ├── storage.py                    # SQLite + Chroma 客户端封装
│   ├── embedding.py                  # Qwen embedding 4B 单例
│   ├── embedding_fake.py             # 测试用伪 embedding
│   ├── config.py                     # AppConfig 单例
│   └── llm/
│       ├── __init__.py
│       ├── deepseek.py               # DeepSeekClient（本 spec §4）
│       └── fake.py                   # FakeLLMClient（测试）
│
├── ingestion/                        # 子系统 1：题库构建（本 spec 的主体）
│   ├── __init__.py
│   ├── cli.py
│   ├── epub_to_md.py                 # 阶段 1
│   ├── chapter_splitter.py           # 阶段 2
│   ├── knowledge_tree_builder.py     # 阶段 3
│   ├── question_extractor.py         # 阶段 4
│   ├── loader.py                     # 阶段 5
│   └── prompts/
│       ├── build_kb.md
│       └── extract_questions.md
│
├── ai_engine/                        # 子系统 2：见 Spec B（本 spec 不定义内容）
│   └── ...
│
├── data/                             # 运行时产物；git 忽略
│   ├── raw_md/<book_slug>/*.md
│   ├── chapters/<book_slug>.json
│   ├── kb/
│   │   ├── knowledge_tree_draft.json # LLM 生成，待人工审核
│   │   └── knowledge_tree.json       # 人工审核后
│   ├── extracted/<book_slug>/*.json
│   ├── questions.db                  # SQLite 主库
│   ├── chroma/                       # Chroma 持久化目录
│   └── llm_traces/
│       ├── index.jsonl
│       └── <call_id>.json
│
├── tests/
│   ├── conftest.py                   # in-memory sqlite/chroma, fake llm
│   ├── unit/
│   │   ├── shared/
│   │   │   ├── test_schemas.py
│   │   │   ├── test_storage.py
│   │   │   └── test_llm_deepseek.py  # 用 fake response 测重试逻辑
│   │   └── ingestion/
│   │       ├── test_chapter_splitter.py
│   │       ├── test_knowledge_tree_builder.py
│   │       ├── test_question_extractor.py
│   │       └── test_loader.py
│   ├── contract/
│   │   ├── test_prompt_templates_load.py
│   │   └── test_schema_invariants.py
│   └── fixtures/
│       ├── raw_md_sample/            # 迷你 md 样例
│       └── knowledge_tree_sample.json
│
└── docs/superpowers/specs/
    ├── 2026-07-07-question-bank-ingestion-design.md   # 本文件
    └── 2026-07-07-ai-engine-design.md                 # Spec B，待撰写
```

---

## 6. 配置

```python
# shared/config.py

class LLMConfig(BaseModel):
    provider: Literal["deepseek"] = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str                      # 从 env DEEPSEEK_API_KEY
    default_model: str = "deepseek-chat"
    timeout_s: int = 60
    max_concurrency: int = 4

class StorageConfig(BaseModel):
    sqlite_path: Path = Path("data/questions.db")
    chroma_path: Path = Path("data/chroma")

class EmbeddingConfig(BaseModel):
    model_name: str = "Qwen/Qwen3-Embedding-4B"   # 具体名称按本地部署为准
    device: str = "cuda"                          # 或 "cpu" / "mps"
    max_batch_size: int = 32

class AppConfig(BaseModel):
    llm: LLMConfig
    storage: StorageConfig
    embedding: EmbeddingConfig
    llm_trace_full: bool = False
```

- 从 `.env` + 环境变量加载（`pydantic-settings`）
- 单例：`get_config()` 全模块可用
- 测试环境通过 fixture 覆盖

---

## 7. 测试策略

**三层测试网**（与 Spec B 共用同一套模式）：

### 7.1 Unit test

- Ingestion 每个阶段独立测试
- LLM 调用 mock 为 `FakeLLMClient`（`shared/llm/fake.py`），断言 prompt 里含预期变量、输出被正确回填
- SQLite 用 `:memory:` 数据库；Chroma 用 in-memory `EphemeralClient`
- Embedding 用 `embedding_fake.py`（确定性伪向量，避免 CI 加载真模型）

### 7.2 Contract test

- `shared/schemas.py` 的 pydantic 模型独立测试：序列化、必填、不变量
- Prompt 模板加载：所有 `.md` 能被 Jinja2 渲染，所需变量齐全

### 7.3 Live smoke（可选，非 CI 常规）

- 一份迷你 EPUB fixture（≤ 20 道题），跑完整 ingestion 六阶段
- 断言：`questions.db` 有 ≥ 15 道题、`knowledge_tree.json` 有 ≥ 3 个二级 KP
- 需真实 DeepSeek key，`pytest -m live` 触发

**Golden set 属于 AI Engine 层的回归**，在 Spec B 中详述。

---

## 8. 开发推进顺序（里程碑 M1）

Ingestion 层的开发顺序（对齐"确定契约 → 基础设施 → 无 LLM 部分 → LLM 部分 → 端到端"）：

1. `shared/schemas.py`（所有契约先写好——两份 spec 的锚点）
2. `shared/config.py` + `shared/storage.py` + 单元测试
3. `shared/embedding.py` + `embedding_fake.py`
4. `shared/llm/deepseek.py` + `shared/llm/fake.py`（骨架，ingestion 就要用）
5. `ingestion/epub_to_md.py`（无 LLM）+ 单元测试
6. `ingestion/chapter_splitter.py`（无 LLM）+ 单元测试
7. `ingestion/knowledge_tree_builder.py` + prompt + 单元测试（LLM mock）
8. **手工跑一次至少一本书 → 人工审核知识点树 → 固化 `knowledge_tree.json`**
9. `ingestion/question_extractor.py` + prompt + 单元测试
10. `ingestion/loader.py` + 单元测试
11. **端到端小规模验收**：一本书 → 全流程 → SQLite/Chroma 有数据 → 手工抽查 20 道

M1 交付后，AI Engine（M2/M3/M4）可以开始（见 Spec B）。

---

## 9. 明确的非目标（本 spec 范围外）

- ⚠️ FastAPI 后端由 [Spec C](./2026-07-07-backend-design.md) 定义（本 spec 只涵盖题库构建）
- ⚠️ React 前端由 Spec D 定义（待撰写）
- ⚠️ 用户注册/登录/鉴权由 Spec C 定义（用户名+密码+bcrypt+Cookie Session）；本 spec 只在数据契约中定义 `user_id` 字段
- ⚠️ 服务端"判对错"由 Spec C 后端做（规则见本文 § 1.6 判等约定：规范化字符串比较）
- ⚠️ 试卷持久化由 Spec C 后端做（新增 `papers` 表，见 Spec C § 3.1）；AI Engine 本身依然保持无状态
- ❌ 不实现题目图片处理（本轮题库无图片）
- ❌ 不实现阅读理解、作文两个题型
- ❌ 不实现 AI Engine 内部各模块（本 spec 只定义契约与共享设施；AI Engine 见 Spec B）

---

## 10. 已识别的开放问题（不阻塞设计，实现时确定）

1. **Qwen embedding 4B 具体加载路径**：本地模型文件位置、GPU/CPU 选择、显存需求——由实现阶段确定
2. **EPUB 结构差异**：不同出版方的 EPUB 章节层级不一致，`chapter_splitter` 可能需要 book-specific 适配器——第一本跑通后视情况抽象
3. **知识点树版本管理**：如果日后要改 `knowledge_point.id`（比如合并两个二级点），级联影响所有题目引用——本 spec 假设**知识点树入库后不改**；若真要改，需要专门的迁移脚本
4. **DeepSeek 具体模型选型**：`deepseek-chat` vs `deepseek-reasoner`——第一版用 `deepseek-chat`，reasoner 若解析质量提升明显可切换
5. **人工审核 UI**：目前假设运行者直接编辑 `knowledge_tree_draft.json`；若审核工作量大，未来可能需要一个最小编辑界面——留待实施时评估

---

## 11. 与 Spec B（AI Engine）的接口

Spec B 会引用本 spec 的以下内容，不再复制：

- §2 全部数据契约
- §4 LLM 稳定输出栈（Spec B 会扩展 §4 到完整的三层防御 + 观测细节 + Prompt 组织）
- §5 目录结构中 `shared/` 部分
- §6 配置
- §7 测试策略中的 unit + contract 部分

Spec B 会新增：

- AI Engine 五个模块（Parser、Retriever、Reviser、Solutioner、Analyzer）的详细设计
- Pipeline 编排（`generate_paper` / `revise_paper` / `generate_solution` / `build_profile`）
- `revise_paper` 的 review 迭代流程
- Golden set 回归测试
- AI Engine 的 CLI
- 未来 FastAPI 的接入契约
- 里程碑 M2/M3/M4

---

## 12. 附录：核心不变量速查

对实现和测试都反复引用的关键不变量集中在此，便于查阅：

1. `Question.id` 一旦入库不变
2. `KnowledgePoint.id` 一旦入库不变
3. `KnowledgePoint.level1` ∈ `{single_choice, word_form, sentence_rewriting}`
4. `Question.question_type` 等于对应一级 KP 的 `level1`
5. `Question.knowledge_point_ids` 至少含一个二级 KP 的 id（即该 `KnowledgePoint` 的 `parent_id != None`）
6. `Question.solution` 允许 `None`；写回条件由 Spec B 的 Solutioner 严格控制
7. Ingestion Loader 幂等键：`(book, chapter, stem_hash)`
8. LLM 抽题的 `knowledge_point_ids` 必须全部来自 `knowledge_tree.json`；否则丢弃该题并记 warning
