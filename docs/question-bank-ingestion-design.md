# Spec A：中考英语题库构建管线设计

**创建日期**：2026-07-07
**最后更新**：2026-07-09（对齐实际实现）
**项目根目录**：`C:\Users\I779318\Desktop\CSS\English_Test_Paper_AI_Generator`
**范围**：从原始 EPUB 教辅书到"结构化、可检索、可生成"题库的完整入库管线
**状态**：SQLite 入库已完成；ChromaDB 向量化尚待 Qwen 4B 环境到位

**与最初设计的偏差**：本次文档整体反映了**开发过程中的关键调整**——最主要的一条是"LLM 抽题被脚本+人工完全取代"，其结果是 ingestion 阶段**没有实际调用 LLM**。原 spec 的 §4 "LLM 稳定输出栈"整节已删除；那部分设计将挪到 Spec B（AI Engine）。

---

## 0. 项目背景与整体愿景

本项目目标是构建一个**中考英语 AI 试卷生成系统**，让学生输入自然语言需求（如"来 10 道现在完成时的单选中等难度"），系统能从题库检索相关题目、按用户设定的改题尺度加工、生成一份完整试卷。系统还支持基于错题或历史答题记录生成针对性练习。

**整体架构**由若干子系统组成：

- **题库构建管线**（`ingestion/`）：本 spec 的主题
- **AI Engine**（`ai_engine/`）：消费题库产出试卷，见 Spec B（待撰写）
- **FastAPI 后端 + React 前端**：暂时搁置；未来另立 spec

**题库构建与 AI Engine 的边界**：两者通过共享数据契约（`shared/schemas.py`，未来抽出）和存储层（`shared/storage.py`，未来抽出）解耦。当前 ingestion 阶段所有 pydantic 模型都定义在 `ingestion/chapter_splitter.py` 内，未来 AI Engine 启动前会重构到 `shared/`。题库构建**只写**题库（除幂等去重需要查询外），AI Engine **只读**题库（Solutioner 一处例外，见 Spec B）。

---

## 1. 覆盖范围与关键决策

### 1.1 学科与题型

- **学科**：中考英语
- **题型（三种一级类型）**：
  - `single_choice`：单项选择
  - `word_form`：词性转换（填空）
  - `sentence_rewriting`：改写句子（填空）
- **不覆盖**：阅读理解、作文、选词填空、任务型阅读
- **无图片**：所有题目为纯文本；原书带图题目在入库时被丢弃

### 1.2 数据源

- **原始形态**：EPUB 电子书
- **当前入库**：《2021 上海中考试题分类汇编·英语（一模/二模）》两本，共 1066 道题（一模 507 + 二模 559）
- **预处理**：脚本转 `.md`（`ebooklib` + `beautifulsoup4` + `html2text`）
- **原始文档不含解析**——解析文本由用户在做题后按需通过 AI Engine 生成（Solutioner 职责，见 Spec B）

### 1.3 存储

- **SQLite** 存题目主数据、知识点、答题记录（`data/questions.db`）
- **ChromaDB**（持久化模式）存题目向量（`data/chroma/`，**尚未创建**）
- **Embedding 模型**：本地 Qwen embedding 4B（**尚未部署**，当前环境不支持）

### 1.4 知识点结构

- **两级层次**，扁平表（**无 `parent_id`**：level1 是 3 值枚举，父子关系已由 level1 值直接表达）
- **一级 = 题型**：`single_choice` / `word_form` / `sentence_rewriting`，三个固定值
- **二级 = 具体考点**：如"语音"、"介词"、"动词时态与语态"、"改为被动语态"等，共 49 个
- **归并方式**：**由开发者手工归并**（原设计的 LLM 归并被评估后放弃：60 个 `chapter_l2` 规模小、语义清晰、人工做映射的性价比高于 LLM 归并 + 审核）

### 1.5 无 LLM 生成解析

- 入库时 `Question.solution = None`
- 用户点"生成解析"时由 AI Engine 的 Solutioner 按需生成
- 只对题库原题（`revision_mode="original"`）缓存写回 `questions.solution` 字段
- 详见 Spec B

### 1.6 判对错不属于 AI Engine 职责

- 前端提交答案后，由未来的 FastAPI 后端做**规范化字符串比较**（小写、trim、多空白折叠、末尾标点忽略）
- 单选：答案是单字母字符串（`"B"`），直接字符串比对
- 填空：答案是"候选组合列表" `list[dict[blank_i, list[候选]]]`，判等规则详见 §2.2
- 本 spec 只保证题库的 `answer` 字段被填好

### 1.7 没有 `difficulty` 字段

- 原 spec 计划让 LLM 打标 `easy` / `medium` / `hard`，评估后**决定不做**：主观标准不稳定、AI 打标不可靠、业务收益不明确
- 数据契约、SQLite 表结构均**已删除** difficulty 相关字段

---

## 2. 数据契约

### 2.1 知识点

```python
class KnowledgePoint(BaseModel):
    id: str                    # "kp_sc_verbs"，稳定 slug
    level1: Literal["single_choice", "word_form", "sentence_rewriting"]
    level2: str                # "动词时态与语态"、"介词" 等
    aliases: list[str] = []    # 同义词（不同书章节标题差异）
```

- 一级 3 值固定；二级由 ingestion 阶段人工归并后固化
- `id` 一旦入库不再更改（Spec §2.7 不变量 2）
- 无 `parent_id`：level1 是枚举值本身，父子关系隐式表达

### 2.2 题目

```python
class Option(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str


class RawQuestion(BaseModel):
    """入库前的中间态。Loader 会补上 id/created_at/version 后写入 questions 表。"""

    id: str | None                       # 由 assign_ids 阶段填充，例如 "q_00042"
    book: str                            # "shanghai_2021_yimo"
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    chapter_l1: str                      # "1 单项选择"
    chapter_l2: str                      # "1.4 不定代词"
    number: str                          # "1" 或 "1-3"（变体）；半角减号

    # 内容字段（按题型条件填充）
    stem: str | None = None              # single_choice / word_form
    options: list[Option] | None = None  # 仅 single_choice
    hint: str | None = None              # 仅 word_form；提示词
    original_sentence: str | None = None # 仅 sentence_rewriting；可能含 <u>...</u>
    instruction: str | None = None       # 仅 sentence_rewriting；"改为否定句" 等
    template: str | None = None          # sentence_rewriting；连词成句为 None

    answer: str | list[dict]             # 见下方
    knowledge_point_ids: list[str] = []  # 引用 KnowledgePoint.id
    source_md: str                       # 溯源
    source_line: int                     # 溯源
```

**`answer` 字段的两种形式**：

- **单选题**：单字母字符串 `"B"`
- **填空题**：`list[dict]`，每 dict 是一种候选组合：

```json
[
  {"blank1": ["so"], "blank2": ["that"]}
]

[
  {"blank1": ["It's"], "blank2": ["impossible", "hard", "difficult"]}
]

[
  {"blank1": ["in"], "blank2": ["order"]},
  {"blank1": ["so"], "blank2": ["as"]}
]
```

- 外层 list：多种候选组合（`in order` 或 `so as`）
- 每个 dict：一种填法（blank1/blank2/...）
- 每空的 value 是候选列表（`if`/`whether` 都对）
- 连词成句：`[{"blank1": ["完整正确排序"]}]`

**判等规则**（后端实现）：用户按顺序填 N 空 → 检查是否**存在任一 dict 满足**"每空的用户输入 ∈ 该 blank 的候选列表"（都做规范化：lowercase + trim）。

### 2.3 试卷（AI Engine 产出，本 spec 中不生成）

见 Spec B。本 spec 只保证入库题的 `id`、`question_type`、`knowledge_point_ids` 稳定。

### 2.4 生成请求 & 掌握度画像

见 Spec B。本 spec 只提供 `Question` 和 `KnowledgePoint` 数据契约。

### 2.5 Embedding 文本规范

`embedding_text` 是**入库时不落主库**的派生字符串，只在向量化阶段临时生成并写入 ChromaDB 的 `documents` 字段。

**模板**（**无 `[难度]` 行**）：

**单选**：
```
[题型] 单项选择
[考点] 时态与语态
[题干] I ___ my homework since 6 p.m.
[选项] A) do  B) am doing  C) have done  D) had done
```

**词性转换**：
```
[题型] 词性转换
[考点] 动词转换为名词
[提示] memory
[题干] He can correctly ___ a pack of cards in just 31.16 seconds.
```

**改写句子**（普通）：
```
[题型] 改写句子
[考点] 保持句意基本不变
[原句] I'm not able to finish the task successfully within half an hour.
[要求] 保持句意基本不变
[模板] ___ ___ for me to finish the task successfully within half an hour.
```

**改写句子·连词成句**（无模板）：
```
[题型] 改写句子
[考点] 连词成句
[要求] 连词成句
[词组] Tom，to make，tells，every night，stories，his baby sister，go to sleep，her
```

**规则**：
- 多 KP 用**多个 `[考点]` 行**
- 空占位符（`___`、下划线段）**保持原样**，不做压缩
- `<u>...</u>` 划线标签在 embedding 阶段**剥除**（模型不理解 HTML）

### 2.6 数据契约不变量

1. **`Question.id`、`KnowledgePoint.id` 永不变更**（改题产生的是 `RevisedQuestion`，无独立 id）
2. **`Attempt.source_question_id` 必须是入库题的 id**
3. **Reviser 不能修改 `knowledge_point_ids` / `question_type`**——答题记录归属会失准
4. **`revision_mode="original"` 时，`RevisedQuestion` 内容与 `Question` 对应字段完全一致**
5. **答案唯一**（`answer` 字段结构规定见 §2.2）；判等规则由后端实现
6. **`solution` 写回题库的唯一条件**：`source_question_id` 存在、`revision_mode="original"`、题库中该题 `solution IS NULL`

---

## 3. 题库构建管线

### 3.1 管线总览

```
EPUB → md → RawQuestion JSON → 人工归并 KP 树 → apply_kp → assign_ids → SQLite
                                        ↑                                     ↓
                              (审核 knowledge_tree_draft                 ChromaDB
                              → knowledge_tree.json)                     (待做)
```

**六个阶段**（按 CLI 子命令映射）：

| # | 阶段 | 命令 | 类型 | 输入 → 输出 |
|---|------|-----|------|------------|
| 1 | EPUB → Markdown | `epub-to-md` | 无 LLM | `.epub` → `data/raw_md/<book>/*.md` |
| 2 | md → RawQuestion JSON | `split` | 无 LLM | md → `data/chapters/<book>.json` |
| 3a | 人工归并 KP 树 | — | 人工 | 60 个 `chapter_l2` → `data/kb/knowledge_tree.json` |
| 3b | 回填 KP id | `apply-kp` | 无 LLM | tree + chapters JSON → chapters JSON（新增 `knowledge_point_ids`） |
| 3c | 分配全库 id | `assign-ids` | 无 LLM | chapters JSON → chapters JSON（新增 `id`） |
| 4 | 入库 SQLite | `build-sqlite` | 无 LLM | tree + chapters JSON → `data/questions.db` |
| 5 | 入库 ChromaDB | *（未实现）* | 需 Qwen 4B | tree + chapters JSON → `data/chroma/` |

每一步产物落盘、可断点重跑、幂等。

### 3.2 阶段 1：EPUB → Markdown（`ingestion/epub_to_md.py`）

**纯脚本，无 LLM。**

- `ebooklib` 读取 EPUB，提取每一份 HTML section
- `beautifulsoup4` + `html2text` 转 Markdown
- **关键处理**：许多教辅 EPUB 用 `<p class="chapterTitle">` 等 CSS class 表达标题层级而非真正的 `<h1>/<h2>/<h3>`——脚本内置了 `CLASS_TO_HEADING` 映射把它们规范化成真标题
- **XHTML 感知**：自动切换 `lxml-xml` 解析器（消除 `XMLParsedAsHTMLWarning`）
- 产出：`data/raw_md/<book_slug>/000.md, 001.md, ...` + `manifest.json`

### 3.3 阶段 2：md → RawQuestion JSON（`ingestion/chapter_splitter.py`）

**纯脚本，无 LLM。** 直接把 md 切成扁平的 `RawQuestion` 列表——**跳过了原 spec 里的"ChapterNode 树"中间态**。

**输入约定**：每本书目录下有 4 个 md 文件（用户手工整理章节归属后重命名）：
```
data/raw_md/<book>/单项选择.md
                   词性转换.md
                   改写句子.md
                   参考答案.md
```
文件名直接对应 `question_type`。

**切分规则**（按题型分立）：

- **单选题**：opener 是 `( )N.` / `（ ）N.`（半/全角括号 + 编号 + 半/全角句号）；stem 是 opener 后到下一段落之前的文本；options 从下一段解析 `A.foo B.bar C.baz D.qux`（单行）或每选项各占一段
- **词性转换**：opener 是 `N.`（无前括号）；行末括号里 `(word)` 是 hint
- **改写句子**：opener 是 `N.`；括号里 `(改为...)` / `(保持...)` 是 instruction；下一段是含 `________` 的 template
- **连词成句**（4.11）：单段结构，无 template；`instruction` 恒为"连词成句"

**变体处理**：`【同考点汇总】` 后的编号形如 `N-K.`（全角减号 `－` 归一化为半角 `-`）。变体和主题目**平等入库**、独立占用 id，不做额外标记。

**答案配对**：解析 `参考答案.md` 得到 `(question_type, chapter_l2, number) → answer` 索引；每题按此 key 查表填 `answer`。

**图片题丢弃**：原书中带图的题目在 EPUB→md 阶段图片被丢弃（`ignore_images=True`）；chapter_splitter 检测到选项数不足/无 hint/无模板时**丢弃该题并计入 stats**，不会入库不完整数据。当前两本书共丢弃 8 道图片题。

**产出**：`data/chapters/<book>.json`，list of `RawQuestion`。

### 3.4 阶段 3a：知识点树人工归并

**关键设计选择**：原 spec 用 LLM 归并被评估后**改为人工**。理由：

- 60 个 `chapter_l2` 规模小
- 语义清晰（教材编纂本身已归类，只需处理同义/粒度差异）
- LLM 归并 + 人工审核的性价比不如直接人工

**归并原则**：

- **同义合并**（`名词改复数` ≡ `名词变复数`）→ 保留一个 id，另一个进 `aliases`
- **粒度不同 → 一章节映射到多个 KP**（一模`1.4 不定代词` 映射 1 个 KP；二模 `1.4 不定代词与限定词` 映射 2 个 KP）
- **章节号错位不影响**（一模 `1.17` 和二模 `1.18` 都指"反意疑问句"）

**产出**：`data/kb/knowledge_tree.json`（**手工写、手工审、直接固化**，无 `_draft` 中间态）。

**格式**（简化示例）：
```json
{
  "knowledge_points": [
    { "id": "kp_sc_indef_pronoun", "level1": "single_choice",
      "level2": "不定代词", "aliases": [] },
    { "id": "kp_sc_determiner",    "level1": "single_choice",
      "level2": "限定词",   "aliases": [] }
  ],
  "chapter_to_kp": {
    "single_choice / 1 单项选择 / 1.4 不定代词":         ["kp_sc_indef_pronoun"],
    "single_choice / 1 单项选择 / 1.4 不定代词与限定词": ["kp_sc_indef_pronoun", "kp_sc_determiner"]
  }
}
```

- **`chapter_to_kp` 的 key 是三段** `"{question_type} / {chapter_l1} / {chapter_l2}"`——防止未来加书时不同题型下的 `chapter_l2` 撞车
- **value 是 list**，支持一对多

**可视化审核工具**：`ingestion/viz_knowledge_tree.py` 产出一份自包含 HTML（`data/kb/knowledge_tree_draft.html`），双击浏览器打开审核。

**当前规模**：49 个 KP（单选 25 + 词性转换 13 + 改写句子 11），60 个 `chapter_to_kp` 映射。

### 3.5 阶段 3b：apply-kp（`ingestion/apply_knowledge_tree.py`）

**纯脚本，无 LLM。** 读 `knowledge_tree.json` + `chapters/*.json`，用三段 key 查表，把 `knowledge_point_ids` 字段回填到每道题。

- 幂等（重跑不改动已正确的行）
- 完整性校验：每题至少 1 个 KP；引用的 kp_id 必须存在；KP 的 level1 必须等于题的 question_type
- 未映射时打 warning 但不失败（写回空列表）

### 3.6 阶段 3c：assign-ids（`ingestion/assign_ids.py`）

**纯脚本，无 LLM。** 给每题分配全库连号 `q_NNNNN`。

**排序键**：`(BOOK_ORDER, QTYPE_ORDER, chapter_l2 数字部分, number 数字部分)`
- `BOOK_ORDER`：`yimo=0, ermo=1`（未来加书时在此表追加）
- `QTYPE_ORDER`：`single_choice=0, word_form=1, sentence_rewriting=2`

**幂等原则**：`Question.id` 是永久不变的（§2.6 不变量 1）。已有 id 的题**绝不覆盖**；缺 id 的题从"未使用的最小编号"分配。

**当前分配**：`q_00001` ~ `q_01066`，一模占 `q_00001~q_00507`、二模占 `q_00508~q_01066`。

### 3.7 阶段 4：build-sqlite（`ingestion/sqlite/loader.py`）

**纯脚本，无 LLM。** 读 KP 树 + chapters JSON，写入 SQLite（`data/questions.db`）。

- DDL 定义在 `ingestion/sqlite/schema.sql`
- 通过 `INSERT OR IGNORE` 保证幂等
- 事务包裹：任何一行失败整体回滚
- `attempts` / `attempt_items` 建表但暂时空表（未来 FastAPI 后端使用）

**stem_hash**：每题存 `sha256(题型专属字段 + answer)`——支持未来查重和内容校验（虽然当前 1066 题无重复）。

### 3.8 SQLite 表结构

```sql
CREATE TABLE knowledge_points (
    id            TEXT PRIMARY KEY,
    level1        TEXT NOT NULL
                    CHECK (level1 IN ('single_choice', 'word_form', 'sentence_rewriting')),
    level2        TEXT NOT NULL,
    aliases_json  TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE questions (
    id                  TEXT PRIMARY KEY,       -- q_00001
    book                TEXT NOT NULL,
    question_type       TEXT NOT NULL,
    chapter_l1          TEXT NOT NULL,          -- "1 单项选择"
    chapter_l2          TEXT NOT NULL,          -- "1.4 不定代词"
    number              TEXT NOT NULL,          -- "1" 或 "1-3"

    -- 内容字段（按题型条件填充）
    stem                TEXT,
    options_json        TEXT,                   -- single_choice; JSON list
    hint                TEXT,                   -- word_form only
    original_sentence   TEXT,                   -- sentence_rewriting; 可含 <u>...</u>
    instruction         TEXT,
    template            TEXT,

    answer_json         TEXT NOT NULL,          -- 单选是 "\"B\""；填空是复杂结构
    solution            TEXT,                   -- nullable; 按需生成

    source_md           TEXT NOT NULL,
    source_line         INTEGER NOT NULL,
    stem_hash           TEXT NOT NULL,
    created_at          TIMESTAMP NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_q_type       ON questions(question_type);
CREATE INDEX idx_q_book       ON questions(book);
CREATE INDEX idx_q_chapter_l2 ON questions(chapter_l2);
CREATE INDEX idx_q_stem_hash  ON questions(stem_hash);

CREATE TABLE question_knowledge_points (
    question_id         TEXT NOT NULL REFERENCES questions(id),
    knowledge_point_id  TEXT NOT NULL REFERENCES knowledge_points(id),
    PRIMARY KEY (question_id, knowledge_point_id)
);
CREATE INDEX idx_qkp_kp ON question_knowledge_points(knowledge_point_id);

-- 答题记录相关表（供未来 FastAPI 后端使用；本 Loader 只建表不写数据）
CREATE TABLE attempts (
    id            TEXT PRIMARY KEY,             -- UUID
    user_id       TEXT NOT NULL,
    paper_id      TEXT NOT NULL,
    answered_at   TIMESTAMP NOT NULL
);
CREATE INDEX idx_att_user     ON attempts(user_id);
CREATE INDEX idx_att_answered ON attempts(answered_at);

CREATE TABLE attempt_items (
    attempt_id             TEXT NOT NULL REFERENCES attempts(id),
    item_index             INTEGER NOT NULL,
    source_question_id     TEXT NOT NULL,
    question_type          TEXT NOT NULL,
    is_correct             INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    kps_json               TEXT NOT NULL,
    PRIMARY KEY (attempt_id, item_index)
);
CREATE INDEX idx_att_it_source ON attempt_items(source_question_id);
```

**关键调整**（相对原 §3.7）：
- `knowledge_points` 删掉 `parent_id`（KP 树扁平，无父子关系）
- `questions` 删掉 `difficulty` 和 `embedding_text`（§1.7 / §2.5）
- `questions` 把 `chapter` 拆成 `chapter_l1` + `chapter_l2` + `number`
- `questions` 新增 6 个题型专属列：`hint / original_sentence / instruction / template`（原 spec 假设都塞 `stem`，实际发现分开更好查询）
- `attempt_items` 删掉 `difficulty` 列

### 3.9 ChromaDB 集合结构（未实现）

沿用原设计——单一集合 `questions`：

- `ids`：`Question.id`
- `embeddings`：Qwen embedding 4B 输出向量
- `documents`：**embedding_text（按 §2.5 模板临时生成，不落主库）**
- `metadatas`：
  ```python
  {
      "question_type": "single_choice",
      "kp_ids": "kp_a,kp_b",   # 逗号分隔字符串
      "book": "..."
  }
  ```

Retriever 检索时用 `where` 过滤 `question_type`；`kp_ids` 用 Python 端二次过滤。

**注意**：Retriever 不再按 `difficulty` 过滤（该字段已删）。

### 3.10 CLI 使用

```bash
# 1. 转换 EPUB
python -m ingestion.cli epub-to-md ./data/books/1.epub --slug shanghai_2021_yimo

# ★ 手动整理：把 EPUB 输出的 section 按题型合并/重命名为
#   单项选择.md / 词性转换.md / 改写句子.md / 参考答案.md

# 2. 切分成 RawQuestion JSON
python -m ingestion.cli split shanghai_2021_yimo
python -m ingestion.cli split shanghai_2021_ermo

# ★ 手工归并 KP 树 → data/kb/knowledge_tree.json
#   可选辅助工具:
#     python -m ingestion.viz_knowledge_tree
#     → 生成可视化 HTML 便于审核

# 3. 回填 knowledge_point_ids
python -m ingestion.cli apply-kp

# 4. 分配全库 id q_NNNNN
python -m ingestion.cli assign-ids

# 5. 入库 SQLite
python -m ingestion.cli build-sqlite

# 6. 入库 ChromaDB —— 待 Qwen 4B 环境到位后实现
```

- 每一步产物落盘、可断点重跑
- 步骤 3/4/5 幂等
- 步骤 5 之前允许手工编辑 JSON（用于修补 EPUB 转换损失、划线标注等——见 §3.11）

### 3.11 允许手工介入的地方

题库最终态是**"脚本产出 + 少量手工补丁"**的组合，不是纯脚本可重放。以下场景在开发过程中做过手工介入：

- **图片题**：脚本已丢弃，无需手工
- **答案页跨节污染**：原书答案页某些 section 之间会把"任务型阅读答案"格式串到相邻单选 section 下——**已手工修补 18 处 answer**（一模 2 处 + 二模 16 处）
- **选项行未切干净**：EPUB 转换后音标类题目 `A./B./C./D.` 中间的分隔符是全角 `／` 而非空格——**脚本用扩展正则修补 62 处**
- **划线部分提问**（`4.3`）：md 转换丢失了原书的 `<u>` 标签——**已手工反推划线位置并嵌入 `<u>...</u>` 标签**（34 道题）
- **填空题答案结构化**：从原始字符串（含 `／` 分隔候选、空格分隔多空）**手工拆分为** `list[dict[blank_i, list[候选]]]` 结构；纯脚本按空格切能处理约 440 处，剩余 20 处含斜线的**手工 patch**
- **KP 归并**：60 个 chapter_l2 → 49 个 KP 的映射**全手工**

**维护策略**：这些手工补丁**已内嵌在 `data/chapters/*.json`**，通过 SQLite 加载后成为主库事实。**未来切勿从 md 端重跑 `split` 覆盖 JSON**——否则手工补丁会丢失。真正需要修 splitter 逻辑时，须**同时更新补丁或把补丁逻辑纳入 splitter**。

### 3.12 与 AI Engine 的边界

- `ingestion/` **只写不读**（除幂等去重需要查 id / stem_hash 外）
- 入库完成后，`ai_engine/`（Spec B）只通过 SQLite/ChromaDB 读；`Question` / `KnowledgePoint` 契约是唯一交互协议
- ChromaDB 目录和 SQLite 文件路径**目前硬编码**（`data/questions.db`、`data/chroma/`）；未来抽出 `shared/config.py` 统一管理

---

## 4. LLM 稳定输出栈

**（已删除，整节挪至 Spec B）**

题库入库阶段**没有实际调用 LLM**：知识点归并改为人工，题目抽取由脚本完成，`difficulty` 字段被评估后放弃。因此原 §4 关于 JSON Mode / instructor / 三层防御的设计不再属于本 spec 范围，将在 Spec B（AI Engine）中重新定义。

---

## 5. 目录结构

```
English_Test_Paper_AI_Generator/
├── README.md
├── pyproject.toml                    # 依赖列表
│
├── ingestion/                        # 题库构建
│   ├── __init__.py
│   ├── cli.py                        # 5 个子命令
│   ├── epub_to_md.py                 # 阶段 1
│   ├── chapter_splitter.py           # 阶段 2（含 RawQuestion 模型）
│   ├── apply_knowledge_tree.py       # 阶段 3b
│   ├── assign_ids.py                 # 阶段 3c
│   ├── viz_knowledge_tree.py         # KP 审核 HTML 生成器
│   └── sqlite/
│       ├── __init__.py
│       ├── schema.sql                # 阶段 4 建表 DDL
│       └── loader.py                 # 阶段 4 双写
│
├── ai_engine/                        # 见 Spec B（未实现）
│
├── shared/                           # 未来抽出（当前空目录）
│   └── __init__.py
│
├── data/                             # 运行时产物；git 忽略
│   ├── books/*.epub                  # 原始 EPUB
│   ├── raw_md/<book_slug>/*.md       # 阶段 1 产出
│   ├── chapters/<book_slug>.json     # 阶段 2/3b/3c 产出
│   ├── kb/
│   │   ├── knowledge_tree.json       # 阶段 3a 手工产出
│   │   └── knowledge_tree_draft.html # 可视化审核工具产出
│   ├── questions.db                  # 阶段 4 SQLite 主库
│   └── chroma/                       # 阶段 5 ChromaDB（未实现）
│
├── tests/
│   ├── unit/ingestion/
│   │   ├── test_epub_to_md.py
│   │   ├── test_chapter_splitter.py
│   │   └── _sample_epub.py
│   └── ...
│
└── docs/
    ├── question-bank-ingestion-design.md   # 本文件
    ├── ai-engine-design.md                 # Spec B（待撰写）
    ├── backend-design.md                   # Spec C（待撰写）
    ├── frontend-design.md                  # Spec D（待撰写）
    └── testing-design.md
```

**与原 spec §5 的偏差**：
- `ingestion/` 下无 `prompts/` 目录（无 LLM 调用）
- `ingestion/sqlite/` 是新增子目录
- `shared/llm/` **未创建**（未来 Spec B 添加）
- `shared/schemas.py` **未创建**（当前 pydantic 模型在 `ingestion/chapter_splitter.py`）
- `shared/embedding.py` **未创建**（等 Qwen 4B）

---

## 6. 配置

**当前状态**：路径硬编码（`data/questions.db` / `data/chroma/` / `data/kb/knowledge_tree.json` 等）在各脚本的 `DEFAULT_*_PATH` 常量里。

**未来目标**（Spec B 启动时抽出）：

```python
class StorageConfig(BaseModel):
    sqlite_path: Path = Path("data/questions.db")
    chroma_path: Path = Path("data/chroma")

class EmbeddingConfig(BaseModel):
    model_name: str = "Qwen/Qwen3-Embedding-4B"
    device: str = "cuda"
    max_batch_size: int = 32

class AppConfig(BaseModel):
    storage: StorageConfig
    embedding: EmbeddingConfig
```

---

## 7. 测试策略

### 7.1 Unit test（已实现）

- `tests/unit/ingestion/test_epub_to_md.py`（6 个测试）：EPUB → md 转换的核心契约
- `tests/unit/ingestion/test_chapter_splitter.py`（12 个测试）：三种题型 parser + 半/全角字符 + 变体 + 图片题丢弃 + 答案页两种格式 + JSON round-trip

全部通过：**18/18**。

### 7.2 Contract test（未实现）

预留：pydantic 模型序列化、prompt 模板加载（当前无 prompt）、schema 不变量。

### 7.3 Live smoke（未实现，无 CI 常规）

预留：迷你 EPUB fixture 跑完整六阶段管线。

### 7.4 数据抽查（已完成的一次性人工验证）

在开发过程中做了**多轮 30+ 道题的人工抽查**，验证：
- stem/options/hint/original_sentence/template 字段解析正确
- answer 按英语知识判断正确（含单选 A/B/C/D 分布 23-28%、词性转换答案长度 2-14 字母、改写句子答案格式合理）
- 手工补丁生效（划线、答案修正、选项切分）

Golden set 属于 AI Engine 层的回归，见 Spec B。

---

## 8. 开发推进顺序（M1 里程碑）

**已完成**：

1. ✅ 阶段 1：EPUB → Markdown（`epub_to_md.py`）
2. ✅ 阶段 2：md → RawQuestion JSON（`chapter_splitter.py`）
3. ✅ 阶段 3a：人工归并 KP 树 → `knowledge_tree.json`（49 KP）
4. ✅ 阶段 3b：回填 knowledge_point_ids（`apply_knowledge_tree.py`）
5. ✅ 阶段 3c：分配全库 id q_NNNNN（`assign_ids.py`）
6. ✅ 阶段 4：入库 SQLite（`sqlite/loader.py` + `sqlite/schema.sql`）
7. ✅ 手工补丁（划线、答案修正、选项切分、多候选答案结构化）

**未完成**：

8. ⬜ 阶段 5：入库 ChromaDB（需要 Qwen 4B 部署环境；embedding_text 生成函数纯代码，可先写）
9. ⬜ `shared/` 抽出（数据契约、配置、存储客户端）——等 AI Engine 启动时做
10. ⬜ 端到端 live-smoke 测试

M1 交付：题库 SQLite 稳态；AI Engine（M2/M3/M4）可以开始（见 Spec B，待撰写）。

---

## 9. 明确的非目标（本 spec 范围外）

- ⚠️ FastAPI 后端由 Spec C 定义（本 spec 只涵盖题库构建）
- ⚠️ React 前端由 Spec D 定义（待撰写）
- ⚠️ 用户注册/登录/鉴权由 Spec C 定义
- ⚠️ 服务端"判对错"由 Spec C 后端做（判等规则见 §1.6 / §2.2）
- ⚠️ 试卷持久化由 Spec C 后端做（AI Engine 本身依然保持无状态）
- ❌ 不实现题目图片处理（本轮题库无图片）
- ❌ 不实现阅读理解、作文两个题型
- ❌ 不实现 AI Engine 内部各模块（本 spec 只定义契约与共享设施；AI Engine 见 Spec B）
- ❌ 不实现 `difficulty` 难度打标（见 §1.7）

---

## 10. 已识别的开放问题

1. **Qwen embedding 4B 环境**：当前开发机不支持——**阶段 5 阻塞在此**。可选后备方案：调云端 embedding API（收费）、换更轻量本地模型（BGE-small 之类）
2. **EPUB 结构差异**：`epub_to_md.py` 里的 `CLASS_TO_HEADING` 目前只覆盖两本上海教辅系列——加新书前需要检查
3. **知识点树版本管理**：当前假设 KP 树入库后不改；若真要改（合并、拆分、改 id），需要专门迁移脚本 + 级联更新 `question_knowledge_points` 表
4. **手工补丁的可重放性**：题库最终态包含 100+ 处手工补丁，不能靠"从 md 重跑"完全重生（见 §3.11）——**目前把 chapters/*.json 视为"手工审核后的稳定态"**，任何改动必须同步维护
5. **变体去重**：352 道变体（`number` 含 `-`）当前作为独立题目入库；未来若发现"变体和主题目重复率过高"可能需要人工去重

---

## 11. 与 Spec B（AI Engine）的接口

Spec B 会引用本 spec 的：

- §2 全部数据契约（Question、KnowledgePoint、embedding_text 模板）
- §3.8 SQLite 表结构（只读，除 Solutioner 写 `solution`）
- §3.9 ChromaDB 集合结构

Spec B 会新增：

- AI Engine 五个模块（Parser、Retriever、Reviser、Solutioner、Analyzer）的详细设计
- LLM 稳定输出栈（原 spec §4 挪到 Spec B）
- Pipeline 编排（`generate_paper` / `revise_paper` / `generate_solution` / `build_profile`）
- `revise_paper` 的 review 迭代流程
- Golden set 回归测试
- AI Engine 的 CLI
- 未来 FastAPI 的接入契约
- 里程碑 M2/M3/M4

---

## 12. 附录：核心不变量速查

对实现和测试都反复引用的关键不变量集中在此：

1. `Question.id` 一旦入库不变
2. `KnowledgePoint.id` 一旦入库不变
3. `KnowledgePoint.level1` ∈ `{single_choice, word_form, sentence_rewriting}`
4. `Question.question_type` 等于对应 KP 的 `level1`
5. `Question.knowledge_point_ids` 至少含一个 KP（apply-kp 阶段保证）
6. `Question.solution` 允许 `None`；写回条件由 Spec B 的 Solutioner 严格控制
7. **`Question.answer` 结构**：
   - `single_choice`：字符串（`"B"`）
   - 填空题：`list[dict[blank_i, list[候选]]]`，判等规则见 §2.2
8. Ingestion 幂等键：`Question.id`（不再依赖 `(book, chapter, stem_hash)` 三元组；stem_hash 作为辅助索引存在但不用于去重）
9. `chapter_to_kp` 的 key 是三段 `"{question_type} / {chapter_l1} / {chapter_l2}"`

---

## 13. 附录：与最初设计的差异汇总

供审阅者快速对比：

| 项 | 原 Spec | 现实 | 原因 |
|----|--------|-----|-----|
| `difficulty` 字段 | 由 LLM 打标 | **删除** | 主观标准不稳定 |
| `embedding_text` 存主库 | `questions.embedding_text` 列 | **不存主库**，只写 ChromaDB `documents` | 主库保持业务干净 |
| KP `parent_id` | 有 | **删除** | level1 是 3 值枚举，父子隐式 |
| `chapter` 一列 | 单列 | **拆成 chapter_l1 + chapter_l2 + number** | 便于按章节查询 |
| ChapterNode 中间态 | 有 | **跳过**，直接产 RawQuestion | md 结构规整，一步到位 |
| `question_extractor`（LLM 抽题） | 阶段 4 | **删除** | 脚本能完成，避免幻觉 |
| KP 归并 | LLM + 人工审 | **纯人工** | 规模小，人工性价比高 |
| `answer` 字段 | 字符串 | **单选是 str，填空是 list[dict]** | 支持多候选组合、多空 |
| `is_variant` 字段 | 有 | **删除** | 冗余（`"-" in number` 可推） |
| Loader 位置 | `ingestion/loader.py` | **`ingestion/sqlite/loader.py`** | 隔离 SQLite 特定代码 |
| LLM 稳定输出栈 (§4) | 详细规范 | **整节挪至 Spec B** | ingestion 不用 LLM |
| Prompt 目录 | `ingestion/prompts/` | **不存在** | 无 LLM 调用 |
| `shared/llm/` 目录 | 存在 | **未创建** | 等 Spec B |
| `shared/schemas.py` | 存在 | **未创建**，模型嵌在 chapter_splitter.py | 等 Spec B 抽出 |
| assign-ids 阶段 | 无 | **新增** | 需要稳定全库 id |
| viz_knowledge_tree | 无 | **新增** | 辅助人工审核 KP 树 |
