# Spec B：AI Engine 详细设计

**创建日期**：2026-07-07
**范围**：AI Engine 子系统（`ai_engine/`）的模块设计、Pipeline 编排、LLM 稳定输出栈、Prompt 组织、观测、测试与未来 FastAPI 接入契约
**依赖**：本 spec 引用 [`./2026-07-07-question-bank-ingestion-design.md`](./2026-07-07-question-bank-ingestion-design.md)（下称 Spec A），共享数据契约、目录结构、存储、LLM 客户端、配置、测试基础设施均在 Spec A 中定义，本 spec 不复制

---

## 0. 范围与产出

**本 spec 定义 AI Engine 子系统**，包括：

- 五个业务模块：Parser / Retriever / Reviser / Solutioner / Analyzer
- 顶层编排：`generate_paper` / `revise_paper` / `generate_solution` / `build_profile`
- LLM 稳定输出栈的完整设计（三层防御 + 观测 + Prompt 组织）
- Golden set 回归测试
- 未来 FastAPI 接入契约
- 里程碑 M2 / M3 / M4

**本 spec 不重复定义**：数据契约、SQLite/Chroma 表结构、`shared/` 目录内容、`ingestion/` 相关内容——全部见 Spec A。

**引用约定**：本文中所有形如 "见 Spec A §X" 的引用指向 [`./2026-07-07-question-bank-ingestion-design.md`](./2026-07-07-question-bank-ingestion-design.md) 的对应章节。

---

## 1. 整体架构

### 1.1 Pipeline

AI Engine 采用**纯 pipeline 架构**（无反馈回路，无 agent 编排）：

```
用户请求（自然语言）
    ↓
┌───────────┐        ┌───────────┐        ┌───────────┐
│  Parser   │ ────→  │ Retriever │ ────→  │  Reviser  │ ────→ Paper
└───────────┘        └───────────┘        └───────────┘
   ↑ (可选)                                     
   │
   ├── mode="review":     Analyzer → MasteryProfile
   └── mode="remediation": 前端提供的 wrong_items
```

**独立入口**（不在主 pipeline 内）：

- **Solutioner**：按需生成单题解析（用户点"查看解析"按钮时调用）
- **Analyzer**：查用户答题历史 → 掌握度画像；供 `review` 模式的 Parser 使用，也可独立被前端调用展示"薄弱点面板"

**取消 Verifier 的依据**：答案唯一无歧义（Spec A § 1.6），改题后 LLM 直接产出新答案，无需二次验证。判对错由未来 FastAPI 后端做规范化字符串比较。

### 1.2 无状态原则

- **AI Engine 完全无状态、只读**：`generate_paper` / `revise_paper` / `generate_solution` / `build_profile` 每次都返回全新对象；AI Engine **不写任何 SQL 表**——五个模块全部只读题库/答题记录或只产返回值
- `revise_paper` 接受**完整 `Paper`** 和用户指令 → 返回**完整新 `Paper`**（`paper_id` 换新）
- **持久化职责在后端层**：由 [Spec C](./2026-07-07-backend-design.md) 定义。FastAPI 拿到 `Paper` 后写入 `papers` 表；`revise_paper` 时后端从表里读出完整 `Paper` 喂给 AI Engine——**边界依然清晰：AI Engine 是纯函数，后端负责持久化**
- **Solutioner 无写回缓存**：`generate_solution` 每次调用都直接问 LLM，不读也不写 `questions.solution`（历史上曾设计"命中缓存则跳过 LLM + 原题解析写回"，现已移除，理由见 § 6）

### 1.3 模块依赖图

```
                       pipeline.py
                            │
        ┌──────────┬────────┼────────┬──────────┐
        │          │        │        │          │
     parser    retriever  reviser  solutioner  analyzer
        │          │        │        │          │
        └───┬──────┴────┬───┴────────┴─────┬────┘
            │           │                  │
            ▼           ▼                  ▼
      shared/llm/  shared/embedding.py  shared/storage.py
      deepseek.py                       (SQLite+Chroma)
                                              │
                                              ▼
                                        shared/schemas.py
```

- 所有 LLM 调用统一走 `shared/llm/deepseek.py`（Spec A § 4.1）
- 所有存储访问统一走 `shared/storage.py`（Spec A § 3.7 / § 3.8 定义的结构）
- 所有 embedding 统一走 `shared/embedding.py`
- Prompt 模板全部在 `ai_engine/prompts/`（见 § 6）

> **实现现状注记**（2026-07-16）：上图是**目标态**（`shared/` 完全抽出）。当前 Retriever 已实现，但存储/embedding 尚未抽到 `shared/`：
> - SQLite 读取在 `ai_engine/question_repo.py`（`QuestionRepo`，只读）
> - embedding 复用 `ingestion/chromadb/embedder.py::QwenEmbedder`
> - ChromaDB 访问直接在 `ai_engine/retriever.py` 内
>
> 待 Parser / Reviser / Solutioner / Analyzer 都落地、需要共享这些设施时，再统一抽到 `shared/storage.py` + `shared/embedding.py`。届时 Retriever 改为依赖 `shared/`，接口不变。

---

## 2. 顶层入口（`ai_engine/pipeline.py`）

### 2.1 公开函数签名

```python
def generate_paper(
    user_query: str,
    mode: Literal["fresh", "remediation", "review"] = "fresh",
    *,
    wrong_items: list[WrongItemRef] | None = None,
    user_id: str | None = None,
    review_window_days: int | None = None,
) -> Paper: ...


def revise_paper(current_paper: Paper, user_instruction: str) -> Paper: ...


def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: Literal["fresh", "light", "original"] | None = None,
    user_answer: str | list[str] | dict[str, str] | None = None,
) -> str: ...


def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile: ...
```

数据类型引用 Spec A § 2。

**`revision_intensity` 不在签名里**：改题尺度由 Parser 内的 LLM 从用户自然语言推断（见 § 3），不作为顶层入参。前端无需在 UI 上暴露"改题尺度"选项。

### 2.2 `generate_paper` 内部编排

```python
def generate_paper(user_query, mode="fresh", *, wrong_items=None,
                   user_id=None, review_window_days=None):
    # 1. review 模式：先跑 Analyzer 得到掌握度画像
    profile = None
    if mode == "review":
        if not user_id:
            raise ParserError("mode=review requires user_id")
        profile = analyzer.build_profile(user_id, review_window_days)

    # 2. Parser：user_query + 上下文 → GenerateRequest
    #    revision_intensity 由 Parser 内的 LLM 从自然语言推断，无需外部传入
    req = parser.parse(
        user_query,
        mode=mode,
        wrong_items=wrong_items,
        mastery=profile,
    )
    # Parser 只填题目相关字段；调用上下文由 pipeline 补
    req.user_id = user_id
    req.review_window_days = review_window_days

    # 3. Retriever：GenerateRequest → 候选题
    retrieval = retriever.retrieve(req)

    # 4. Reviser：候选题 + req → Paper
    paper = reviser.build_paper(req, retrieval)

    return paper
```

无反馈回路；每步单一职责；任何一步抛异常都由未来 FastAPI 层捕获转 HTTP 错误。

---

## 3. Parser（`ai_engine/parser.py`）

**目标**：自然语言（含可选的错题上下文、掌握度上下文）→ `GenerateRequest` JSON。

### 3.1 接口

```python
def parse(
    user_query: str,
    *,
    mode: Literal["fresh", "remediation", "review"],
    wrong_items: list[WrongItemRef] | None = None,
    mastery: MasteryProfile | None = None,
) -> GenerateRequest: ...
```

**`revision_intensity` 不作参数传入**——它是 LLM 从 `user_query` 推断的输出字段之一，Parser 内部处理。见 § 3.2 步骤 3 与 § 3.4 的 prompt 规则。

### 3.2 内部流程

1. **加载 KP 目录**：从 SQLite 读所有 `KnowledgePoint`，构造紧凑清单（id + level1 + level2 + aliases）塞进 prompt。中考英语规模有限（预计几百条），完全可接受
2. **按 mode 装配 prompt 头部**：
   - `fresh`：只解析 `user_query`
   - `remediation`：`user_query` + "用户刚做完试卷的错题分布：单选/时态 × 3, 词性转换/动词变名词 × 2, ..."
   - `review`：`user_query` + `mastery.weak_kps` 前 N 条（默认 8 条）作为薄弱知识点提示
3. **LLM 调用**：走 `shared/llm/deepseek.py::DeepSeekClient.structured()`，**`response_model=GenerateRequest`（直接以对外契约作为响应模型）**，`max_retries=3`，`temperature=0.2`
4. **本地二次校验**（在 pydantic 之外）：
   - `knowledge_points` 里的每个 id 必须存在于 SQLite；不存在则丢弃并记入 `warnings`
   - `total_questions` ≤ 上限（默认 30）；超限截断
   - `type_distribution` 的 key 必须是合法 `question_type`（非法丢弃）；累加 ≤ `total_questions`，超出按比例缩放
   - **`revision_intensity` 不做二次校验**：`Literal["fresh","light","original"]` 由 pydantic 约束值域（`GenerateRequest` 里默认 `"light"`）；LLM 省略即落默认，输出非法值则由 `instructor` 反馈回 LLM 重试
5. **补全上下文字段**：LLM 已直接产出 `GenerateRequest` 的核心字段（含 `revision_intensity`）；本地代码补 `mode`、`wrong_items`（`user_id`、`review_window_days` 由 pipeline 在 `parse()` 返回后补——见 § 2.2）。**`free_text` 只填"结构化字段无法表达的情境/主题诉求"**（如"关于环保"、"结合校园场景"），由 LLM 在 `GenerateRequest.free_text` 中输出；纯配额/纯 KP 请求（如"5 道单选 5 道改写"）此字段为空串。**不要把整句 user_query 塞进 free_text**——否则每个请求都会触发 Retriever 的向量检索（见 § 3.4 规则 + Spec A `GenerateRequest.free_text` 契约）
6. **兜底**：若 LLM 3 次仍无法产出合法 JSON → 抛 `ParserError`

### 3.3 关键决策

- **LLM 只负责意图理解和结构映射**，一致性检查由本地代码做（规则确定的事情不劳烦模型）
- **不允许 LLM 造 KP id**：清单在 prompt 里显式给出，本地代码丢弃非法 id。若用户提到清单外的**情境/主题**（如"环保""校园生活"），写入 `free_text` 供 Retriever 做语义检索；若是清单外的生僻语法点且无对应 KP，则只能丢弃
- **`total_questions` 上限**：常量，第一版 30；后续可放到 `AppConfig`
- **`revision_intensity` 由 LLM 决定**：用户通常不会显式说"要原题/轻改/新出"，LLM 根据 prompt 语义推断（详细规则见 § 3.4）；兜底逻辑写在 prompt 里（默认选 `"light"`），不写在 Python 代码里

### 3.4 Prompt 关键要点

放在 `ai_engine/prompts/parser.md`。要点：

- 头部列出**所有合法 KP id + 三种 `question_type` 枚举**
- Few-shot 覆盖：单一 KP 请求、多 KP 请求、`type_distribution` 显式指定、模糊请求（"随便出 10 道"）、`remediation` 附加错题、`review` 附加掌握度
- **`free_text` 填写规则**（关键，影响 Retriever 走向量还是 SQL）：

  ```
  free_text 只填"结构化字段（knowledge_points / question_types /
  type_distribution）无法表达的情境或主题诉求"，用于语义向量检索。

  - 填入：用户描述的题目情境/主题，如"关于环保""结合校园生活场景"
    "多用旅游购物的例子"——这些是题库没有显式标注、只能靠语义匹配的内容。
  - 留空（""）：纯配额/纯知识点/纯题型请求，如"5 道单选 5 道改写"
    "来 10 道时态题""随便出 10 道"——这些诉求已被结构化字段完整表达，
    没有额外主题。
  - 绝不把整句 user_query 原样塞进 free_text。
  ```

  配 few-shot：
  - `"来 10 道关于环保的时态单选"` → `free_text="关于环保"`（时态/单选/数量进结构化字段）
  - `"5 道单选 5 道改写"` → `free_text=""`
  - `"结合校园生活多出几道介词题"` → `free_text="结合校园生活"`
  - `"随便来 10 道"` → `free_text=""`

- **`revision_intensity` 推断规则**（关键规则）：prompt 用严格的**判定流程**，按优先级顺序逐条匹配，命中即定：

  ```
  1. 有 "original" 触发词 → original（最高优先级）
  2. 有 "light" 触发词   → light（第二优先级）
  3. 有 "fresh" 触发词或明确情境描述 → fresh
  4. 其他所有情况 → light（默认档位）

  注意：light 优先级高于 fresh——若同时命中 light 与 fresh 触发词，选 light。

  - "original"（直接用原题）：
    · 触发词："原题"、"真题"、"一模"、"二模"、"考试原题"、"中考真题"、
      "别改"、"照原题出"、"保持原样"……
    · 有 original 触发词时忽略情境描述（如"来十道单选原题，关于校园生活" → original）

  - "light"（保留原题结构，改数值/词汇/情境）—— 默认档位：
    · 触发词："练习"、"巩固"、"复习"、"来几道"、"出几道"，以及任何
      知识点名称（"动词时态""不定代词""介词"……）或题型名称
    · 知识点名称不算情境描述——纯 KP/题型请求一律 light

  - "fresh"（完全按知识点新出题）：
    · 没有 original 触发词，且有 "重新出"、"全新的"、"别用现成的"、"原创" 等词
    · 或有明确的生活情境/主题描述（"场景""主题""情境""关于""结合""围绕"）
  ```

  配 few-shot（各 1-2 条）：
  - `"来 10 道现在完成时的中考真题"` → `"original"`
  - `"帮我重新出十道单选题"` / `"帮我按被动语态出一份练习，多用校园场景"` → `"fresh"`
  - `"多练几道时态"` / `"复习一下我上周的错题"` → `"light"`（无特殊指示，走默认）

### 3.5 响应模型：直接用 `GenerateRequest`

Parser **不用单独的内部响应模型**——`structured()` 的 `response_model` 就是对外契约 `GenerateRequest`（`shared/schemas.py`）本身。LLM 直接产出 `GenerateRequest` 的字段，Parser 随后做本地二次校验（丢非法 KP id、截断题数、清洗 `type_distribution`、缩放分布）并补 `mode` / `wrong_items`。

> **契约对齐**（2026-07-14/15）：`GenerateRequest` 已删除 `knowledge_points_exclude`、`difficulty`、`difficulty_distribution`、`per_kp_min`（均已从契约移除），新增 `free_text`（语义主题，供 Retriever 判断走向量还是 SQL）。

**关于 `revision_intensity`**：

- 契约里 `revision_intensity` 有默认值 `"light"`（`shared/schemas.py`）——LLM 省略时不会触发 pydantic 报错，而是落到默认 `"light"`。这与 prompt 里的兜底规则（无明确改题信号一律选 `light`，见 § 3.4）一致，两处默认互为保险
- 本地代码**不对 `revision_intensity` 做二次校验**：`Literal["fresh","light","original"]` 由 pydantic 约束值域，非法值会被 instructor 反馈回 LLM 重试

**为什么本地仍要二次校验**（而不是完全信任 LLM 产出的 `GenerateRequest`）：

- `knowledge_points` 里可能含清单外的非法 id，需在 Parser 层丢弃并记 `warnings`
- `type_distribution` 的 key 是 `dict[str,int]`，pydantic 不校验 key 值，需本地检查是否合法题型
- `total_questions` 需按上限截断；`type_distribution` 之和超 `total_questions` 需按比例缩放

---

## 4. Retriever（`ai_engine/retriever.py`）

**目标**：`GenerateRequest` → 覆盖需求的候选题集合，供 Reviser 挑选/改造。

采用 **"属性硬过滤（SQL）+ 语义向量检索（Chroma）"** 的混合检索。**已实现**（`ai_engine/retriever.py`，见 § 4.4 实现说明）。

### 4.1 接口

```python
def retrieve(req: GenerateRequest) -> RetrievalResult: ...

class RetrievedItem(BaseModel):
    question: Question               # 完整题库题（Spec A § 2.2）
    score: float                     # 语义相似度（cosine，越大越近；SQL 随机路径为 0）

class RetrievalResult(BaseModel):
    items: list[RetrievedItem]
    warnings: list[str] = []
    shortfall: dict[str, int] = {}   # 每个桶还缺几道，供 Reviser 决定是否 fresh 补
```

`RetrievalResult` 与 `RetrievedItem` 定义在 `shared/schemas.py`（Spec A 未涵盖，属 AI Engine 扩展契约）。`shortfall` 是关键——Retriever **只取不造**，取不够就在此结构化上报缺口，由 Reviser 决定补不补（且受 `revision_intensity` 约束：`original` 档不补）。

### 4.2 两条路径（混合检索）

Retriever 按 `req.free_text` 是否有内容，走两条路径之一：

- **`free_text` 为空** → **SQL 随机路径**：纯配额/纯 KP 请求（如"5 道单选 5 道改写"）。属性硬过滤后随机取（带种子，测试可复现）。**不加载模型。**
- **`free_text` 非空** → **向量语义路径**：有情境/主题诉求（如"关于环保的单选"）。属性硬过滤后，在硬过滤集内按语义相似度排序取前 N。

Parser 保证 `free_text` 只装"结构化字段无法表达的主题词"（见 § 3.4），所以这个开关简单可靠：`bool(free_text.strip())`。

### 4.3 内部流程

1. **分桶（`_plan_buckets`）**：
   - `req.type_distribution` 非空 → 每个题型一个桶，各取指定数
   - 否则 → 单桶，按 `req.question_types` 过滤后取 `total_questions`

2. **每个桶填充（`_fill_bucket`）**：
   - **属性硬过滤（SQL）**：`question_repo.filter_ids()` 按 `question_type` + `knowledge_points`（join `question_knowledge_points`）过滤，得该桶候选 id 集 `hard_ids`
   - **排序**：
     - SQL 路径 → `hard_ids` 随机打乱（种子）
     - 向量路径 → 见 § 4.4，在 `hard_ids` 内按相似度排序
   - 取前 `target` 个 id → `question_repo.get_by_ids()` 取完整 Question
   - 若不足 `target` → 记 `shortfall[桶] += 缺口` + `warnings`

3. **产出 `RetrievalResult`**；`items` 全空则抛 `RetrieverError`

### 4.4 向量路径实现（先 SQL 后向量）

**关键设计：SQL 在前，向量在后**——在**已经 KP 过滤好的 `hard_ids` 集合内**做相似度排序，而不是"先全库向量取 Top-M 再和硬过滤集求交"。

```python
# hard_ids 已是 SQL 过滤好的候选（如 52 道介词题）
query_vec = embedder.embed([req.free_text])[0]
stored = collection.get(ids=hard_ids, include=["embeddings"])   # 按 id 取这些题的向量
scores = {qid: dot(query_vec, vec) for qid, vec in zip(...)}     # 本地 cosine（向量已归一化）
ordered = sorted(hard_ids, key=lambda i: scores[i], reverse=True)
```

**为什么不用 `collection.query()`**：
- Chroma 的 `query()` 只能按 metadata 过滤（`where`），**不能限定 id 集合**；且 `kp_ids` 在 metadata 里是逗号分隔字符串，KP 过滤不可靠（Spec A § 3.8）
- 若用 `query()` 先取全库 Top-M 再和 `hard_ids` 求交，交集可能远小于 target（例："既是介词题、又语义接近旅游"的题很少）——曾导致"要 5 道介词题只匹配到 2 道，再拿无关介词题凑数"的 bug
- 改用 `collection.get(ids=hard_ids)` 把该桶**全部**候选的向量取出、本地算 cosine 排序——保证排序范围就是目标 KP 集，取前 N 名副其实

**向量归一化**：`build_vec` 阶段 `normalize_embeddings=True`（Spec A § 3.9），故点积即 cosine。

### 4.5 关键决策

- **只取不造**：Retriever 绝不生成新题；缺口通过 `shortfall` 上报，Reviser 负责（fresh 档）补齐
- **不做语义去重**：同 KP 的题语义天然接近，去重伤覆盖度；去重只按 `question.id`（跨桶用 `exclude` 集）
- **不感知 mode**：`remediation` / `review` 模式下，Parser 已把错题 KP / 薄弱 KP 塞进 `req.knowledge_points`，Retriever 无需感知 mode
- **device 自适应**：`_auto_device()` 检测 CUDA，不可用则降级 CPU——同一代码在 GPU 建库机和 CPU 开发机都能跑
- **懒加载模型**：仅向量路径加载 Qwen；纯配额请求不碰模型

---

## 5. Reviser（`ai_engine/reviser.py`）

**目标**：候选题 → 最终 `Paper`，按 `revision_intensity` 三档处理。

### 5.1 三档策略

| 档位 | Reviser 做什么 |
|---|---|
| `original` | **不调 LLM**。字段拷贝 |
| `light` | LLM 逐题改写：保留题型/KP；改数值/词汇/句式；同步更新 `answer` 和 `options`；不填 `solution` |
| `fresh` | LLM 参考原题风格 + KP 出**新题**：题干、选项、答案全新生成；不改 KP/题型；不填 `solution` |


### 5.2 逐题 LLM 调用（`light` / `fresh`）

- **单题一次调用**（不 batch）——一题失败不拖全部
- **Prompt 输入**：
  - 原题（`stem` + `options` + `answer`）
  - 目标 `knowledge_point_ids` 对应的 `level2` 中文名
  - `question_type`（不变约束）
  - `req.free_text`（用户情境主题诉求，控制情境倾向）
  - 档位标识（`light` / `fresh`）
- **输出**：`instructor` + `RevisedQuestion` pydantic 校验；`max_retries=2`
- **兜底**：仍失败 → **fallback 到原题**（按 `original` 档拷贝），并把该题号记入 `Paper.metadata["revision_failures"]`

### 5.3 硬约束层（Reviser 自防御）

因取消 Verifier，Reviser 必须自己保证输出正确性。三层防御：

1. **Schema 层**：pydantic 校验 `question_type` / `knowledge_point_ids` 字段类型和枚举
2. **不变量层**（本地 Python 二次校验）：
   - `question_type` / `knowledge_point_ids` 必须与原题**完全一致**——检测到 LLM 修改这两个字段中的任一 → 视为 revision 失败，走 § 5.2 的 fallback 路径（不走 pydantic 层重试，因为这不是 Schema 违规而是业务不变量违规）
3. **答案格式层**：
   - `single_choice`：`answer ∈ {"A","B","C","D"}`；`options` 长度为 4；`options[i].label` 为 `A/B/C/D` 无遗漏
   - `word_form` / `sentence_rewriting`：`answer.strip() != ""`
   - 违反任一条 → 视为 revision 失败，走 fallback

### 5.4 批装配（`build_paper`）

```python
def build_paper(req: GenerateRequest, retrieval: RetrievalResult) -> Paper:
    items: list[PaperItem] = []
    for idx, retrieved in enumerate(retrieval.items[: req.total_questions], start=1):
        rq = _revise_one(retrieved.question, req.revision_intensity, req.free_text)
        items.append(PaperItem(
            index=idx,
            question=rq,
            source_question_id=retrieved.question.id,
            revision_mode=req.revision_intensity,
        ))
    return Paper(
        paper_id=uuid4().hex,
        title=_infer_title(req),
        generated_at=datetime.now(UTC),
        request=req,
        items=items,
        metadata={
            "retrieval_warnings": retrieval.warnings,
            "shortfall": retrieval.shortfall,
            "revision_failures": [it.index for it in items
                                  if _is_fallback(it)],
            "llm_calls": _stats(),
        },
    )
```

**契约同步说明**（2026-07-14）：`PaperItem` 已删除 `score` 与 `revision_notes` 字段，`Paper` 已删除 `total_score` 字段（见 `shared/schemas.py`）：

- **分值删除**：不同请求题数不同 → 总分不可横向比较，分值无意义。衡量表现改用**正确率**（`Attempt.items` 里每题的 `is_correct`）。
- **revision_notes 删除**：改题摘要属于调试信息，前端不展示；若需排查失败，`Paper.metadata["revision_failures"]` 已记录 fallback 的题号。

### 5.5 并发

Reviser 批量改题时并发调用 LLM，通过 `shared/llm/deepseek.py` 的内部信号量限流（默认 `max_concurrency=4`，见 Spec A § 6 `LLMConfig`）。

---

## 6. Solutioner（`ai_engine/solutioner.py`）

**目标**：单题按需生成解析。用户在做题后点"查看解析"按钮时通过未来 FastAPI 调用。

**无缓存、纯只读**：Solutioner **每次调用都直接问 LLM**——不读 `questions.solution`，也不写回。历史版本曾设计"原题命中缓存则跳过 LLM，并把生成的解析写回 `questions.solution`"，现已整体移除。这样 AI Engine 保持完全无状态/只读；且每次都实时生成，才能针对学生这一次的具体作答给出个性化解析（见 § 6.2 `user_answer`）。

### 6.1 接口

```python
def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: RevisionMode | None = None,   # RevisionMode = Literal["fresh","light","original"]
    user_answer: str | list[str] | dict[str, str] | None = None,
) -> str: ...
```

- **`user_answer`**（学生的作答，通常是**错误答案**）：三种题型全支持——单选是裸标签 `str`（`"B"`）；填空是按空顺序的 `list[str]` 或 `{blankN: text}` 的 `dict`。传入后由 `_format_user_answer()` 渲染成可读文本（如 `"blank1: went  blank2: to"`）再进 prompt。**非空时**解析的第三段变为【错误原因】，针对该错误作答说明"错在哪、为什么错"；**为空时**是通用的【易错点】（见 § 6.3）。
- **`source_question_id` / `revision_mode`**：现为**残留参数**——签名保留（向后兼容与未来可能的溯源用途），但缓存移除后**代码内不再使用**。

### 6.2 内部流程

1. **组装 prompt 输入**：`q.stem` + `q.options`（若有，渲染为 `A. ... / B. ...` 文本）+ `_format_answer(q.answer)`（正确答案，单选裸标签、填空渲染为 `blank1: a / b` 形式）+ `q.question_type` + `q.knowledge_point_ids` 对应的 `level2` 中文名 + `_format_user_answer(user_answer)`（学生作答，可为空）
2. **LLM 调用**：走 `shared/llm/deepseek.py::DeepSeekClient.text()`（唯一使用 `text()` 而非 `structured()` 的模块），`temperature=0.4`
   - 输出**纯文本**（不走 pydantic 校验；解析文本更自然）
   - LLM 抛异常 → 包装为 `SolutionerError`
3. **返回 solution 文本**：`strip()` 后为空则抛 `SolutionerError`

### 6.3 Prompt 结构约定

`ai_engine/prompts/solutioner.md` 要求 LLM 三段式输出。前两段固定，第三段随 `user_answer` 切换：

```
【关键考点】...
【解题思路】...
【易错点】...          ← user_answer 为空时
```

或

```
【关键考点】...
【解题思路】...
【错误原因】...        ← user_answer 非空时：针对该错误作答指出错在哪、为什么错；
                        填空/改写题若有多空，指出具体哪个空错了、正确应是什么
```

- 无 markdown 代码块包裹
- 词性转换/改写句子必须解释"为什么是这个词形/句式"的语法根据

---

## 7. Analyzer（`ai_engine/analyzer.py`）

**目标**：`user_id` + 时间窗 → 按 KP 掌握度排序的画像，供 Parser 在 `review` 模式下使用。

### 7.1 接口

```python
def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile: ...
```

### 7.2 内部流程

1. **查询答题记录**（`attempts` + `attempt_items` 表，由后端写入）：
   ```sql
   SELECT ai.kps_json, ai.question_type, ai.is_correct
   FROM attempts a
   JOIN attempt_items ai ON a.id = ai.attempt_id
   WHERE a.user_id = ?
     AND (? IS NULL OR a.answered_at >= datetime('now', '-' || ? || ' days'))
   ```
   注：`attempt_items.kps_json` 列存的是对应 `AttemptItem.knowledge_point_ids` 的 JSON 数组，
   实现时通过 `json.loads(row["kps_json"])` 还原为 `list[str]`。
   `window_days` 传 `None` 则不过滤时间范围，查全部历史。

2. **展开 KP 列表**：一道题命中多个 KP → 每个 KP 都记一次（该题对错平摊到每个 KP，不按 KP 数量分比例——用户已确认）
   ```python
   for row in rows:
       for kp_id in json.loads(row["kps_json"]):
           kp_stats[kp_id]["attempts"] += 1
           kp_stats[kp_id]["correct"] += int(row["is_correct"])
   ```

3. **按 `kp_id` 分组**统计 `attempts` 和 `correct`

4. **计算 Wilson score lower bound（95%）** 作为 `mastery`：
   ```python
   def wilson_lower(correct: int, total: int, z: float = 1.96) -> float:
       if total == 0:
           return 0.0
       p = correct / total
       denom = 1 + z*z/total
       centre = p + z*z/(2*total)
       margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total))
       return (centre - margin) / denom
   ```
   低样本降权，避免"只做过 1 道且错了"排在"做过 20 道正确率 60%"之前

5. **产出 `MasteryProfile`**（对应 `shared/schemas.py::MasteryProfile`）：
   - `weak_kps: list[KPMastery]`：按 `mastery` 升序取前 N（默认 8）
   - `dominant_types: list[str]`：从 `attempt_items.question_type` 中按**错题数**降序取前 3，值为 `QuestionType` 字符串
   - `total_attempts_considered: int`：查询到的 `attempt_items` 总行数

### 7.3 边界处理

- **无答题记录** → 返回 `MasteryProfile(weak_kps=[], dominant_types=[], total_attempts_considered=0)`；Parser 在 `review` 模式下应回退到"按 `user_query` 出题"，并在返回的 `Paper.metadata` 里注记 "无历史数据"
- **全对** → `weak_kps` 用 `mastery` 最低的那几个（即使都很高），供"查漏补缺"

### 7.4 只读

Analyzer 只查表不写；不修改任何持久化状态。

---

## 8. `revise_paper`（review 迭代）

**目标**：用户对已生成的试卷提修改意见 → 新版试卷。**在 `pipeline.py` 内编排**，复用主 pipeline 的模块（Parser → Retriever → Reviser），没有独立的 `reviser.revise_paper` 函数。

### 8.1 内部流程（`pipeline.revise_paper`）

修改本质上就是"在原试卷已有的样子上再发一次请求"，所以直接复用 `generate_paper` 的三段式：

1. **拼接上下文查询**：从 `current_paper.request` 提取原试卷的形状（题数、题型中文名、考点、`free_text` 主题），拼成一段中文说明 + `user_instruction`，作为新的 `user_query`：

   ```
   这是在一份已有试卷基础上的修改请求。
   原试卷：共 N 题；题型：单项选择、词性转换；考点：...；主题：...。
   用户的修改要求：{user_instruction}
   请在原试卷基础上应用修改要求，输出修改后完整的出题需求。
   ```

2. **Parser**：`parser.parse(query, mode="fresh")` → 新的 `GenerateRequest`；从原 `request` 继承 `user_id` / `review_window_days`。改题尺度仍由 Parser 内的 LLM 从指令语义推断，不显式传入
3. **Retriever → Reviser**：`retriever.retrieve(req)` → `reviser.build_paper(req, retrieval)`，与 `generate_paper` 完全一致
4. **溯源**：新 `Paper` 的 `metadata["revised_from"]` 记录 `current_paper.paper_id`，供前端链接回原卷

### 8.2 无状态、`paper_id` 换新

- 所有输入来自参数（`current_paper` 由后端从 `papers` 表读出），返回全新 `Paper`；**`paper_id` 换新**（便于前端做版本管理）
- **相对指令靠上下文解析**：把原试卷形状塞进查询头部，让"把选择题换成词形转换""多加 5 道时态题"这类相对指令能相对真实原卷解析，而不是凭空理解
- 前端的"删除第 3 题"这类纯前端动作可**本地做**（直接从数组去掉），无需服务端参与——统一走 `revise_paper` 只用于需要重新出题/换题/调分布的语义修改

---

## 9. LLM 稳定输出栈（完整版）

Spec A § 4 给了 ingestion 用的最小子集。这里给完整设计。

### 9.1 `shared/llm/deepseek.py`

```python
class DeepSeekClient:
    def __init__(self, cfg: LLMConfig):
        self._raw = openai.OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        self._instructor = instructor.from_openai(
            self._raw, mode=instructor.Mode.JSON,
        )
        self._cfg = cfg
        self._sem = threading.Semaphore(cfg.max_concurrency)

    def structured(
        self,
        *,
        response_model: type[BaseModel],
        prompt: str,
        system: str | None = None,
        max_retries: int = 3,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> BaseModel:
        """结构化调用：JSON Mode + pydantic 校验 + 校验失败自动重试。"""
        ...

    def text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.4,
        model: str | None = None,
    ) -> str:
        """纯文本调用（Solutioner 唯一用户）。"""
        ...
```

**关键设计**：

- **两个 API 面**：`structured()` 走 instructor + JSON Mode + pydantic；`text()` 直接返字符串
- **temperature 默认分层**：结构化 0.2、文本 0.4——单点可覆盖
- **`max_retries` 由调用方指定**：Parser=3，Reviser=2；Solutioner 用 `text()` 无 pydantic 校验层，无对应重试参数（外层 tenacity 处理网络/5xx 仍存在）
- **单例注入**：`shared/config.get_llm_client()` 全局单例；测试时 `shared/llm/fake.py::FakeLLMClient` 替换

### 9.2 三层防御（完整版）

```
LLM 原始输出
   ↓
Layer 1: JSON Mode          ← DeepSeek response_format={"type":"json_object"}
   ↓
Layer 2: pydantic 校验       ← instructor 用 response_model；校验失败把错误消息追加回上下文再重试
   ↓
Layer 3: 语义校验（本地代码） ← 校验业务不变量
   ↓
成功
```

**失败处理**：

| Layer | 失败场景 | 处理 |
|---|---|---|
| 1 | 罕见（JSON Mode 已强制） | `instructor` 感知，重发 |
| 2 | pydantic 校验失败 | `instructor` 把错误消息作为 assistant 附加消息再让模型输出 |
| 3 | 业务不变量违反 | **AI Engine 自己处理**——Parser 丢字段+warning；Reviser fallback 原题；Ingestion 丢该条+warning |

**为什么用 `instructor`**：对 DeepSeek 这种 OpenAI 兼容后端支持成熟，省 200 行自研代码。DeepSeek 是它 supported providers 之一。

### 9.3 并发与限流

- **内部信号量**：`DeepSeekClient` 内 `threading.Semaphore(max_concurrency)`，默认 4
- **外层重试**：`tenacity` 装饰器处理 429/5xx，最多 3 次指数退避——独立于 `instructor` 的 pydantic 重试
- **成本兜底**（可选，`LLM_MAX_TOKENS_PER_REQUEST` env）：单次调用估算超阈值提前拒绝——只作防呆

### 9.4 观测（`LLMTrace`）

Spec A § 4.4 定义了 `LLMTrace` 结构和落地方式（JSONL 摘要 + 可选全文）。AI Engine 与 ingestion 共用同一份观测机制。补充：

- `LLMTrace.module` 命名规约：`"ai_engine.parser"` / `"ai_engine.reviser.light"` / `"ai_engine.solutioner"` / ...
- **retries** 字段区分 instructor 内部重试（Layer 2）和 tenacity 外层重试——两者相加

---

## 10. Prompt 组织

### 10.1 目录

```
ai_engine/prompts/
├── __init__.py                          # load() 加载器（见 § 10.3）
├── parser.md
├── reviser_light.md
├── reviser_fresh.md
└── solutioner.md
```

`revise_paper` **没有独立 prompt**——它复用 `parser.md`（§ 8 把原试卷上下文拼进 `user_query` 后走 Parser）。

### 10.2 模板约定

每份 prompt 是一个 markdown 文件，用 `---` 分隔 system 部分和 user 部分：

```markdown
<!-- vars: user_query, mode, kp_catalog, wrong_items?, mastery? -->

# 系统角色
你是一个中考英语试卷生成助手 ...

---

# 任务
根据用户请求生成 GenerateRequest JSON。

# 输入
用户请求：{{ user_query }}
模式：{{ mode }}
可选知识点：
{{ kp_catalog }}

# 输出格式
（instructor 会自动附加 JSON Schema）

# Few-shot
...
```

**Jinja2 变量**：模板顶部注释显式列出，便于 IDE 检查和 contract test 验证（见 § 11.2）。

### 10.3 加载器

```python
# ai_engine/prompts/__init__.py
def load(name: str, **vars) -> tuple[str, str]:
    """
    加载 prompts/<name>.md，用 Jinja2 渲染，返回 (system, user)。
    以 --- 分隔。
    """
```

### 10.4 各 prompt 关键要点

**Parser** (`parser.md`)：
- 头部列出**所有合法 KP id + `question_type` 枚举**
- Few-shot 覆盖：单一 KP / 多 KP / 显式分布 / 模糊请求 / remediation / review
- 显式规则："不要造 KP id；清单外概念写进 `free_text`"
- `revision_intensity` 判定流程（`original` > `light` > `fresh` > 默认 `light`，见 § 3.4）
- vars：`user_query, mode, kp_catalog, kp_count, wrong_items?, mastery?, question_types`
- 响应模型直接是 `GenerateRequest`（无 `reasoning` 等附加字段，见 § 3.5）

**Reviser light** (`reviser_light.md`)：
- 显式列出**不变字段**：`question_type / knowledge_point_ids` 由系统透传，不需要 LLM 输出
- 显式约束："若为单选题，选项数量必须为 4，标签为 A/B/C/D"
- 显式约束："`answer` 必须是 `options[i].label` 之一"
- Few-shot 含反例：错的写法 `answer: "B) written"`（应为 `answer: "B"`）

**Reviser fresh** (`reviser_fresh.md`)：
- 明确"参考原题只用于把握**难易感和风格**，不必与原题内容相关"
- 提供 2-3 道同 KP 的示例作为风格锚点（从候选池随机抽的其他题）

**Solutioner** (`solutioner.md`)：
- 输出**纯文本**，禁止 markdown 代码块包裹
- 三段式：`【关键考点】/【解题思路】/`——第三段随 `wrong_answer` 变量切换：为空 → `【易错点】`，非空 → `【错误原因】`（针对该错误作答）
- 词性转换/改写句子必须解释语法根据
- vars：`question, kp_names, options_text, answer, wrong_answer`

**Revise paper**：无独立 prompt，复用 `parser.md`（见 § 8）。

---

## 11. 测试

### 11.1 Unit test

对应 Spec A § 7.1 的模式，AI Engine 每个模块独立测试：

```
tests/unit/ai_engine/
├── test_parser.py
├── test_retriever.py
├── test_reviser.py
├── test_solutioner.py
├── test_analyzer.py
└── test_pipeline.py
```

**共同 fixture**（`tests/conftest.py`）：

- 内存 SQLite（`shared/storage.py` 支持 `sqlite_path=":memory:"`）
- 内存 Chroma（`chromadb.EphemeralClient`）
- `FakeLLMClient`（`shared/llm/fake.py`）：接受"prompt 关键词 → 预设响应"的映射；断言支持"某次调用的 prompt 中含预期片段"
- `FakeEmbedding`（`shared/embedding_fake.py`）：确定性伪向量

**关键断言维度**：

- **Parser**：不同 mode 下 prompt 是否含预期上下文；LLM 假响应的 KP id 越界时是否被丢弃并记 warning
- **Retriever**：属性硬过滤逻辑正确（空过滤 = 全库；多 KP OR/AND 语义）；`$in` 回退分支的正确性
- **Reviser**：三档策略下 LLM 调用次数正确（original=0；light/fresh=题数）；答案格式违规时 fallback；不变字段被改时拒绝
- **Solutioner**：每次调用都调一次 LLM（无缓存）；`user_answer` 为空 → 解析含【易错点】、非空 → 含【错误原因】；三种题型的 `user_answer` 都能被 `_format_user_answer` 渲染成可读文本；LLM 返回空串时抛 `SolutionerError`
- **Analyzer**：Wilson 公式在若干经典输入的正确值；空历史返回空 profile；多 KP 展开正确
- **Pipeline**：三种 mode 端到端调用（全 mock LLM）

### 11.2 Contract test

```
tests/contract/
├── test_prompt_templates_load.py       # 所有 .md 能被 Jinja2 渲染
├── test_prompt_vars_declared.py        # 顶部 <!-- vars: --> 声明与模板实际用到的变量一致
└── test_schema_invariants.py           # pydantic 模型的关键不变量
```

### 11.3 Golden set 回归

```
tests/golden/
├── requests.jsonl          # 典型请求样例（自然语言 + 期望 GenerateRequest 关键字段）
├── questions.jsonl         # 30 道人工验收题目 + 期望 KP 归属
└── test_live_pipeline.py   # pytest -m live
```

**Golden set 组成**：

- **Parser 断言**：30 条典型自然语言请求 → 期望的 KP 命中率 ≥ 95%、`question_types` 命中率 ≥ 90%
- **Reviser 断言**：Light 档改题后 `answer` 字段类型未变（单选仍是 `A-D`，填空仍非空）；`question_type` / `KP` 严格未变
- **Solutioner 断言**：解析文本非空、包含"关键考点"或类似标记

**触发**：`pytest -m live` 显式触发，需真实 DeepSeek API key。默认 skip。CI 不跑；release 前或 prompt 大改后手动跑。

**评分策略**：Golden set 目的是**抵御回归**，阈值宽松。不追求 100%——LLM 天生不确定。

---

## 12. FastAPI 接入契约

**本 spec 不实现 FastAPI**。HTTP 端点、鉴权、持久化由 [Spec C](./2026-07-07-backend-design.md) 定义并实现。本节固定 AI Engine 对外的**函数级契约**，Spec C 直接消费。

### 12.1 端点映射（在 Spec C 中定义）

Spec C § 5.1 定义完整端点表，本节仅回顾"5 个 AI Engine 函数 ↔ HTTP 端点"的对应关系：

| AI Engine 函数 | HTTP 端点（Spec C） | 说明 |
|---|---|---|
| `generate_paper(user_query, mode, ...)` | `POST /api/papers/generate` | 生成试卷（三 mode） |
| `revise_paper(current_paper, user_instruction)` | `POST /api/papers/revise` | Review 迭代（后端先按 paper_id 从库读出 current_paper） |
| `generate_solution(q, user_answer, ...)` | `POST /api/solutions` | 单题按需解析（传入学生作答则解释错因） |
| `build_profile(user_id, window_days)` | `GET /api/users/me/mastery` | 掌握度画像（user_id 由后端从 session 注入） |

### 12.2 请求/响应体

**直接用 `shared/schemas.py` 的 pydantic 模型序列化**——FastAPI 天然支持，零适配层。Spec C 会额外定义几个**后端专用请求/响应体**（如 `GeneratePaperRequest`、`ErrorResponse`），追加到 `shared/schemas.py` 中，但**不改动 AI Engine 消费的类型**。

### 12.3 AI Engine 不涉及的端点

以下端点由 Spec C 定义与实现，AI Engine 不参与：

| 端点 | 语义 |
|---|---|
| `POST /api/auth/*` | 用户注册/登录/登出/查询 |
| `POST /api/attempts` | 前端提交答题；后端判对错 + 写 `attempts` / `attempt_items` 表 |
| `GET /api/papers` / `GET /api/papers/{id}` | 历史试卷列表 / 单份读取 |

**判对错**：Spec C § 5.2 定义规范化字符串比较（小写、trim、空白折叠、末尾标点忽略）；AI Engine 不参与判等。

**`shared/storage.py` 提供 `write_attempt()`** 等方法，给 Spec C 后端直接调用；两个子系统对表结构定义在同一处（Spec A § 3.7）。

### 12.4 公开导出

```python
# ai_engine/__init__.py
from .pipeline import generate_paper, revise_paper, generate_solution
from .analyzer import build_profile
from shared.schemas import (
    GenerateRequest, Paper, MasteryProfile,
    RevisedQuestion, WrongItemRef,
)
# Attempt 不在此 re-export：AI Engine 不消费 Attempt 对象；
# 未来 FastAPI 从 shared.schemas 直接导入。
```

FastAPI 未来只做：请求验证 → 调这 5 个函数 → 序列化响应。**AI Engine 不知道 HTTP 的存在。**

---

## 13. AI Engine CLI

`ai_engine/cli.py` 提供开发调试命令：

```bash
# 生成一份试卷（fresh）
python -m ai_engine.cli generate \
    --query "来 10 道现在完成时的单项选择"
# revision_intensity 由 LLM 从 --query 内容推断（见 § 3.4）；不暴露 CLI 参数

# 基于错题练习（remediation）
python -m ai_engine.cli generate \
    --query "针对这些错题多练几道" \
    --mode remediation \
    --wrong-items ./tmp/wrong.json

# 基于历史复习（review）
python -m ai_engine.cli generate \
    --query "帮我复习最近一个月的薄弱点" \
    --mode review \
    --user-id u_demo \
    --window-days 30

# 单题生成解析
python -m ai_engine.cli solution \
    --question-json ./tmp/q.json
# 可选：传入学生作答 --user-answer B，解析改为解释该错误答案为何错

# 快速看掌握度画像
python -m ai_engine.cli profile --user-id u_demo --window-days 30

# Review 迭代
python -m ai_engine.cli revise \
    --paper ./tmp/paper.json \
    --instruction "把前三道改成计算类"
```

CLI 是**开发者友好接口**，未来前端不通过 CLI。

---

## 14. 里程碑（M2 / M3 / M4）

### M2：AI Engine 核心模块

前置：Spec A 的 M1 完成（题库已入库，`shared/` 基础设施可用）。

1. ✅ `ai_engine/errors.py`（统一异常层次）
2. `ai_engine/parser.py` + prompt + 单元测试（进行中）
3. ✅ `ai_engine/retriever.py` + `question_repo.py` + 单元测试（混合检索：SQL 硬过滤 + 桶配额 + 先SQL后向量的本地相似度排序 + shortfall 兜底；15 个测试 + 10 样例 demo 报告）
4. `ai_engine/reviser.py` + `reviser_light.md` / `reviser_fresh.md` + 单元测试（三档策略、失败 fallback、答案格式硬约束）（进行中）
5. ✅ `ai_engine/pipeline.py` 顶层编排（懒 import；待 Parser/Reviser 落地后端到端集成测试）
6. `ai_engine/solutioner.py` + prompt + 单元测试（每次调 LLM，无缓存；支持 `user_answer` 解释错因）
7. `ai_engine/analyzer.py` + 单元测试（Wilson 公式验证、边界处理）
8. `revise_paper` 分支 + prompt + 单元测试
9. Golden set 骨架（10 条 request、10 道题）

### M3：Ops 层

1. `LLMTrace` 落盘（`data/llm_traces/`）
2. `AppConfig` 完整化（`.env` 加载、单例）
3. `ai_engine/cli.py` 六个命令
4. Golden set 扩至 30 条，跑首次 live 回归
5. 观测面板：一个简单脚本 `scripts/summarize_traces.py` 从 `index.jsonl` 输出"每模块调用数 / 平均延迟 / 失败率"

### M4：交付验收（本 spec 范围结束点）

端到端 CLI 演示：

- `fresh` 生成一份试卷
- `remediation` 基于错题生成
- `review` 基于历史生成
- `revise` 修改试卷
- `solution` 单题解析（可选传入学生作答演示错因解析）

**验收标准**：
- 一本书完整入库（M1 里程碑）+ AI Engine 五路径全跑通
- 单测覆盖 ≥ 80%
- Golden set 通过阈值（Parser KP 命中率 ≥ 95%、Reviser 不变字段 100%、Solutioner 非空 100%）

---

## 15. 明确的非目标（本 spec 范围外）

- ⚠️ FastAPI 后端由 [Spec C](./2026-07-07-backend-design.md) 定义（本 spec 只涵盖 AI Engine）
- ⚠️ React 前端由 Spec D 定义（待撰写）
- ⚠️ 用户注册/登录/鉴权由 Spec C 定义
- ⚠️ 服务端"判对错"由 Spec C 定义（规则简单：规范化字符串等）
- ⚠️ 试卷持久化由 Spec C 定义（后端 `papers` 表）；**AI Engine 本身依然保持无状态**——持久化在 Spec C 后端层完成
- ❌ 不实现题目图片处理（题库无图片）
- ❌ 不实现阅读理解、作文两个题型
- ❌ 不实现 Verifier 环节（答案唯一 + LLM 直接产出新答案，Verifier 收益不足）
- ❌ 不实现 agent 编排 / LangGraph 类框架（Pipeline 已足够）

---

## 16. 已识别的开放问题（不阻塞设计，实现时确定）

1. **DeepSeek 具体模型选型**：`deepseek-chat` vs `deepseek-reasoner`——第一版用 `deepseek-chat`；Reviser fresh 档若质量不足可局部切 `deepseek-reasoner`
2. **答题记录清理策略**：`attempts` 表长期增长；Analyzer 用 `review_window_days` 已限查询范围，但历史数据永不删——第一版不做清理，留给未来后端 spec
3. **向量路径低分阈值**：当前向量路径在 KP 集内按相似度取前 N，即使排名靠后的题相似度不高也照取（例："介词题里最像旅游的第 5 名"分数可能只有 0.42）。未来可加一个相似度阈值——低于阈值宁可报 `shortfall` 让 Reviser fresh 出更贴题的新题。阈值需实测分布后定，第一版不做
4. **Golden set 阈值**：初始 95% / 100% / 100% 是猜测值；跑一次真实回归后按实际调整
5. **Chroma metadata 过滤语法**：`$in` / `$and` 语法因 Chroma 版本而异，写代码时需验证；若某语法不支持则退化为"取 Top-M 再 Python 端过滤"
6. **Wilson lower bound 的 z 值**：默认 95% (z=1.96)；若薄弱点选择太保守（低样本 KP 被压得太低），可降为 90% (z=1.645)——观测 `weak_kps` 稳定性后决定

> **已移除的开放问题**：原"单题分值可配置化"（2026-07-14 删除）——分值字段整体废弃（题数不同总分不可比），改用正确率衡量表现，见 §5.4 契约同步说明。

---

## 17. 附录：核心不变量速查（AI Engine 相关）

Spec A § 12 定义了全局不变量。AI Engine 侧的补充：

1. **Pipeline 无反馈回路**：Parser → Retriever → Reviser 严格单向
2. **`revise_paper` 无状态、`paper_id` 换新**
3. **Solutioner 无副作用、无缓存**：`generate_solution` 每次都调 LLM，既不读 `questions.solution` 也不写回（旧的"原题解析写回"机制已移除）。`source_question_id` / `revision_mode` 为残留参数，不再被使用
4. **Reviser 不变字段**：`question_type` / `knowledge_point_ids` 在任何档位下都不被修改（`difficulty` 字段已废弃，不在契约中）
5. **Reviser 失败 fallback**：`revision_mode` 仍为原档位，但内容等同 `original`，题号记入 `Paper.metadata["revision_failures"]`
6. **AI Engine 全模块只读无副作用**：Parser / Retriever / Reviser / Solutioner / Analyzer 全部只读题库或答题记录、只产返回值，**不写任何持久化状态**（Solutioner 曾是唯一的写入侧信道，写回缓存移除后不再成立）
7. **Analyzer 只读**：不修改任何持久化状态
8. **`revision_intensity` 的填写者是 LLM，不是调用方**：`generate_paper` / `parse` 接口都不接受此参数；LLM 直接在 `GenerateRequest.revision_intensity` 输出（省略则落契约默认 `"light"`）；一旦离开 Parser 就是完整的三值枚举之一
