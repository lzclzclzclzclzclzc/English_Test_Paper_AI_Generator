# Spec H：长文本题型（听力长文判断 + 阅读理解选择）支持设计

**创建日期**：2026-08-01
**项目根目录**：`d:\Code\English_Test_Paper_AI_Generator`
**范围**：新增两类"一段长文本 + 多小题"题型支持，覆盖数据契约、AI Engine、后端、前端全链路
**依赖**：
- [Spec A（题库摄入）](./question-bank-ingestion-design.md)
- [Spec B（AI Engine）](./ai-engine-design.md)
- [Spec C（后端）](./backend-design.md)
- [Spec D（前端）](./frontend-design.md)
- [Spec G（听力选择题支持）](./listening-support-design.md)（TTS 工具函数复用）

---

## 0. 范围与产出

### 0.1 本 spec 定义
- 新增题型 `listening_true_false`（听力长文·判断 T/F）的数据契约与全链路支持
- 新增题型 `reading_longtext_single_choice`（阅读理解·4 选项单选）的数据契约与全链路支持
- 共享材料（passage）的字段设计与前端分组渲染
- 听力长文复用浏览器 TTS（男女声区分，与 Spec G 一致）
- 题库摄入对两类题型的 SQLite 入库支持

### 0.2 本 spec 不定义
- **两类题型均不进向量库（ChromaDB）**——见 §0.4 与 §5.5
- 其他阅读题型（如任务型阅读、选词填空、主旨大意填空）——留待未来
- 真实音频文件支持——听力长文当前使用浏览器 TTS 合成（与 Spec G 一致）
- 作文题——留待未来

### 0.3 核心需求
1. 一段长文本（passage）后跟随多道小题，passage 在前端只渲染一次
2. 听力长文小题为**判断题**（True/False），非 4 选项单选
3. 阅读理解小题为**4 选项单选**（A/B/C/D），选项呈现参考单项选择题
4. 听力长文复用 Spec G 的 TTS 男女声区分与全局播放锁
5. 两类题型都支持改题（light/fresh/original）和解析生成
6. 听力播放控件位于 passage 区域（一段材料一个播放控件，而非每小题一个）

### 0.4 关键决策：不做向量库
两类长文本题型**不写入 ChromaDB 向量集合**，原因：

1. **passage 长文本不适合语义检索**：一段材料含多小题，embedding 单题会丢失材料上下文；embedding 整段材料又与"按小题检索"的粒度不匹配
2. **组卷按 passage 整组出**：长文本题组卷时按 passage_id 整组检索（见 §2.2），SQL 按 `question_type` + `passage_id` 分组随机即可，无需向量语义匹配
3. **降低入库成本**：避免对长文本做 Qwen 4B 编码（耗时长、显存占用大）
4. **检索路径明确**：Retriever 对这两类题型直接走 SQL 路径（按 question_type 过滤 + passage_id 分组），不触发向量检索

**实现影响**：
- `ingestion/chromadb/loader.py` 跳过这两类 question_type，不写入向量
- `ingestion/chromadb/embedding_text.py` 的 `build_embedding_text()` 不需要为这两类添加模板
- `ai_engine/retriever.py` 对这两类题型跳过向量路径，仅用 SQL

---

## 1. 数据契约扩展（Spec A §2 扩展）

### 1.1 新增题型枚举

在 `shared/schemas.py` 的 `QuestionType` 中新增两个值：

```python
QuestionType = Literal[
    "single_choice",
    "word_form",
    "sentence_rewriting",
    "listening_single_choice",
    "listening_true_false",      # 新增：听力长文·判断 T/F
    "reading_longtext_single_choice",   # 新增：阅读理解·4 选项单选
]
```

### 1.2 passage 共享材料字段

每道小题仍是独立的 `Question`，新增两个可选字段实现"一段材料 + 多小题"的共享：

| 字段 | 类型 | 说明 |
|---|---|---|
| `passage_id` | `str \| None` | 共享材料组 ID（如 `psg_2026_l_001`）。同组小题必须相同；无材料的题留空 |
| `passage_json` | `Passage \| None` | 材料对象，同组小题冗余存储相同内容（见 §1.2.1 取舍） |

#### 1.2.1 `Passage` 结构

```python
class Passage(BaseModel):
    kind: Literal["listening", "reading"]
    title: str | None = None        # 材料标题（如 "Passage One"）
    content: str                     # 长文本正文
    audio_url: str | None = None     # 预留：未来真实音频文件路径；当前 null 走浏览器 TTS
```

**`content` 格式约定**：
- `kind="listening"`：每行以 `M:`（男声）或 `W:`（女声）开头，与 Spec G 的 stem 格式一致，便于复用 TTS
- `kind="reading"`：纯文本段落，换行符 `\n` 分隔段落

#### 1.2.2 存储取舍：每题冗余 vs 顶层抽离

**采用「每题自包含冗余存储」**，理由：
- 符合现有"一行一题"loader 架构（`loader.py` 逐题 INSERT），无需改两段加载逻辑
- retrieval 取出单题自带材料，无需二次查表关联 passages
- grading/错题本按单题判分，单题带材料可独立复盘展示
- INSERT OR IGNORE 幂等性不受影响（`Question.id` 去重，passage_json 重复无碍）
- 代价：JSON 体积略增（同组 N 题 × 材料重复 N 次），但材料通常几百字可接受

### 1.3 听力长文判断题数据结构（TF）

```json
{
  "id": "q_11001",
  "book": "shanghai_2026_yimo",
  "question_type": "listening_true_false",
  "chapter_l1": "2 听力长文",
  "chapter_l2": null,
  "number": "11",
  "passage_id": "psg_2026_l_001",
  "passage_json": {
    "kind": "listening",
    "title": "Long Conversation One",
    "content": "M: Good morning. Welcome to the City Library. How can I help you?\nW: Hi, I'd like to apply for a library card. I just moved to this city last week.\nM: No problem. All we need is a photo ID and a proof of your address.\nW: Yes, I have my passport and a recent electricity bill.\nM: With a standard card, you can borrow up to five books for three weeks.\nW: That sounds great. Let me fill out the form now.",
    "audio_url": null
  },
  "stem": "Question 11: The woman has just moved to the city.",
  "options": null,
  "hint": null,
  "original_sentence": null,
  "instruction": null,
  "template": null,
  "answer": "T",
  "source_md": null,
  "source_line": 0,
  "knowledge_point_ids": ["kp_listening_passage"]
}
```

**TF 题字段约定**：
- `options` 恒为 `null`（TF 题无选项）
- `answer` 为 `"T"` 或 `"F"`（大写），复用 `Answer = str | list[BlankGroup]` 的 str 分支，**无需扩展 Answer 联合类型**
- `stem` 为小题题干（如 "Question 11: The woman has just moved to the city."），不含对话原文
- 听力原文存在 `passage_json.content` 中

### 1.4 阅读理解单选题数据结构（4 选项）

```json
{
  "id": "q_20001",
  "book": "shanghai_2026_yimo",
  "question_type": "reading_longtext_single_choice",
  "chapter_l1": "3 阅读理解",
  "chapter_l2": null,
  "number": "21",
  "passage_id": "psg_2026_r_001",
  "passage_json": {
    "kind": "reading",
    "title": "The Discovery of Coffee",
    "content": "Coffee was first discovered in the highlands of Ethiopia, in East Africa. The most popular story tells of a goat herder named Kaldi. One day, Kaldi noticed that his goats became unusually active after eating some red berries from a certain plant.\nWord of these special berries soon reached the monks at a nearby monastery. From Ethiopia, coffee traveled across the Red Sea to the Arabian Peninsula. By the 15th century, coffee was being grown in Yemen.\nIn the 17th century, coffee reached Europe. Today, coffee is one of the most popular drinks in the world.",
    "audio_url": null
  },
  "stem": "Question 21: Where was coffee first discovered?",
  "options": [
    {"label": "A", "text": "In Yemen."},
    {"label": "B", "text": "In Europe."},
    {"label": "C", "text": "In Ethiopia."},
    {"label": "D", "text": "In Mecca."}
  ],
  "hint": null,
  "original_sentence": null,
  "instruction": null,
  "template": null,
  "answer": "C",
  "source_md": null,
  "source_line": 0,
  "knowledge_point_ids": ["kp_reading_passage"]
}
```

**阅读理解字段约定**：
- `options` 为 4 个 `Option`（A/B/C/D），与 `single_choice` 完全一致
- `answer` 为 `"A"`/`"B"`/`"C"`/`"D"`
- 文本材料存在 `passage_json.content` 中

### 1.5 知识点扩展

在 `data/kb/knowledge_tree.json` 的 `knowledge_points` 数组中新增两条 KP：

```json
{
  "id": "kp_listening_passage",
  "level1": "listening_true_false",
  "level2": "听力长文理解",
  "aliases": ["听力长对话", "听力短文", "听力篇章"]
},
{
  "id": "kp_reading_passage",
  "level1": "reading_longtext_single_choice",
  "level2": "阅读理解",
  "aliases": ["阅读", "阅读篇章", "阅读短文"]
}
```

并在 `chapter_to_kp` 中添加映射（`chapter_l2` 为 null 时 key 末段用字符串 "null" 或保持与现有听力一致的写法）：

```json
"listening_true_false / 2 听力长文 / None": ["kp_listening_passage"],
"reading_longtext_single_choice / 3 阅读理解 / None": ["kp_reading_passage"]
```

### 1.6 `Question` / `RevisedQuestion` 模型扩展

在 `shared/schemas.py` 的 `Question` 模型中新增两个可选字段：

```python
class Question(BaseModel):
    # ... 现有字段 ...
    passage_id: str | None = None
    passage_json: Passage | None = None
```

`RevisedQuestion` 同样新增这两个字段（改卷时 passage 内容可被 fresh 档重写）：

```python
class RevisedQuestion(BaseModel):
    # ... 现有字段 ...
    passage_id: str | None = None
    passage_json: Passage | None = None
```

**`Passage` 模型**新增（见 §1.2.1），定义在 `shared/schemas.py` 中。

### 1.7 number 字段约定

每道小题的 `number` 字段**各自独立存**（与现有单题一致），不存为区间：
- 听力长文：`"11"`、`"12"`、`"13"`（同组 3 题）
- 阅读理解：`"21"`、`"22"`、`"23"`（同组 3 题）

前端按 `passage_id` 分组后，题号显示由前端控制（可显示为 "11-13" 区间或逐题显示）。

### 1.8 ID 编号约定

- 听力长文：从 `q_11001` 开始
- 阅读理解：从 `q_20001` 开始
- 两种题型分两个 JSON 文件存储（见 §5.1）

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
    "- listening_true_false: 听力长文判断题",
    "- reading_longtext_single_choice: 阅读理解",
])
```

**本地校验扩展**：

```python
VALID_QUESTION_TYPES = {
    "single_choice", "word_form", "sentence_rewriting",
    "listening_single_choice",
    "listening_true_false", "reading_longtext_single_choice",
}
```

**revision_intensity 触发词**（遵循 Spec B 优先级）：
- `listening_true_false` 和 `reading_longtext_single_choice` 触发词遵循通用规则：
  - 原题档（original）：含"原题"、"真题"、"一模"、"二模"
  - 重新出（fresh）：含"重新出"、"场景"、"主题"、"情境"、"关于"、"结合"
  - 默认 light 档：含"练习"、"巩固"、"复习"、知识点名称

**Prompt 修改**：`ai_engine/prompts/parser.md`

在题型枚举与 few-shot 示例中添加：
```
- listening_true_false: 听力长文判断题（一段长对话/短文 + 多道 True/False 判断题）
- reading_longtext_single_choice: 阅读理解（一段短文 + 多道 4 选项单选题）

示例：
输入："来 1 篇听力长文，3 道判断题"
输出：{"question_types": ["listening_true_false"], "total_questions": 3, ...}

输入："出 2 篇阅读理解，每篇 4 题"
输出：{"question_types": ["reading_longtext_single_choice"], "total_questions": 8, ...}
```

### 2.2 Retriever 扩展（SQL only，不做向量库）

**修改文件**：`ai_engine/retriever.py`

**核心策略**：对 `listening_true_false` 和 `reading_longtext_single_choice` **跳过向量检索路径**，仅走 SQL：

```python
PASSAGE_TYPES = {
    "listening_true_false",
    "reading_longtext_single_choice",
}

def retrieve(req: GenerateRequest) -> RetrievalResult:
    # 向量路径只处理 PASSAGE_TYPES 之外的题型
    vector_types = [qt for qt in req.question_types if qt not in PASSAGE_TYPES]
    non_vector_types = [qt for qt in req.question_types if qt in PASSAGE_TYPES]

    items = []
    # 向量检索（仅对 vector_types）
    if vector_types:
        items.extend(_vector_retrieve(req, vector_types))
    # SQL 检索（对所有题型，但 PASSAGE_TYPES 只走这里）
    items.extend(_sql_retrieve(req, non_vector_types))
    return RetrievalResult(items=items, ...)
```

**passage 整组检索约束**：长文本题组卷时必须**按 passage_id 整组出**，不能只取某 passage 的一道小题：

```python
def _sql_retrieve(req, question_types):
    # 对长文本题型：先选 passage_id，再取该 passage 下全部小题
    if set(question_types) & PASSAGE_TYPES:
        # 随机选 N 个 passage_id
        passage_ids = _random_passage_ids(question_types, req.total_questions)
        # 取这些 passage 下的全部小题
        items = _fetch_by_passage_ids(passage_ids)
        return items
    # 其他题型走原 SQL 逻辑
    ...
```

**注意**：`total_questions` 对长文本题型应理解为"小题总数"，Retriever 按小题数估算所需 passage 数（如 3 小题/篇 → 1 篇）。

### 2.3 Reviser 扩展

**修改文件**：`ai_engine/reviser.py`

**答案格式校验扩展**：

```python
def _validate_revision(question, revised):
    qt = question.question_type
    # 阅读理解：与 single_choice 共享校验
    if qt in {"single_choice", "listening_single_choice", "reading_longtext_single_choice"}:
        if revised.answer not in {"A", "B", "C", "D"}:
            return False, "answer must be A/B/C/D"
        if len(revised.options) != 4:
            return False, "options must have exactly 4 items"
        labels = {opt.label for opt in revised.options}
        if labels != {"A", "B", "C", "D"}:
            return False, "options labels must be A/B/C/D without duplicates"
    # 听力长文判断题：answer 为 T/F，options 必须为 None
    elif qt == "listening_true_false":
        if revised.answer not in {"T", "F"}:
            return False, "answer must be T/F"
        if revised.options is not None:
            return False, "truefalse question must have no options"
    return True, None
```

**passage 不变约束**：
- `original` 档：`passage_id` / `passage_json` 内容与原题**完全一致**（与 stem/options/answer 同等不可变）
- `light` 档：`passage_json.content` **可微调**（如替换少量词汇），`passage_id` 保持不变
- `fresh` 档：`passage_json` 可整体重写，`passage_id` 生成新值（如 `psg_fresh_001`）

**Prompt 修改**：`ai_engine/prompts/reviser_light.md` 和 `ai_engine/prompts/reviser_fresh.md`

在不变约束中添加：
```
- 听力长文判断题（listening_true_false）：
  - answer 必须是 "T" 或 "F"
  - options 必须为 null
  - passage_json.content 的每行必须以 M: 或 W: 开头（与听力原文格式一致）
  - stem 为小题题干（如 "Question 11: ..."），不含对话原文

- 阅读理解（reading_longtext_single_choice）：
  - answer 必须是 A/B/C/D
  - options 必须为 4 个，label 分别为 A/B/C/D
  - passage_json.content 为阅读短文纯文本
  - stem 为小题题干，不含短文原文
```

### 2.4 Solutioner 扩展

**修改文件**：`ai_engine/solutioner.py`

**Prompt 修改**：`ai_engine/prompts/solutioner.md`

在特别要求中添加：
```
- 听力长文判断题（listening_true_false）：
  - 必须引用 passage 中的关键语句说明判断依据
  - 指出干扰点（如时间、地点、人物关系的反转）
  - 说明 T/F 判断的关键信息在 passage 哪一段

- 阅读理解（reading_longtext_single_choice）：
  - 必须引用 passage 中的原文片段说明答案依据
  - 指出其他选项为何不符合 passage 内容
  - 说明考点（细节理解 / 主旨大意 / 推理判断 / 词义猜测）
```

---

## 3. 后端支持（Spec C 扩展）

### 3.1 判对错逻辑扩展

**修改文件**：`backend/services/grading.py`

```python
def compare(user_answer, correct_answer, question_type):
    # 阅读理解：与 single_choice 共享（A/B/C/D 大小写无关）
    if question_type in {"single_choice", "listening_single_choice", "reading_longtext_single_choice"}:
        return isinstance(user_answer, str) and user_answer.strip().upper() == correct_answer.strip().upper()
    # 听力长文判断题：T/F 大小写无关
    if question_type == "listening_true_false":
        if not isinstance(user_answer, str):
            return False
        u = user_answer.strip().upper()
        # 兼容用户输入 "True"/"False" 全称
        u = {"TRUE": "T", "FALSE": "F"}.get(u, u)
        return u in {"T", "F"} and u == correct_answer.strip().upper()
    # ... 其他题型逻辑不变 ...
```

### 3.2 知识点目录

后端无需修改——`GET /api/knowledge-points` 会自动返回新添加的两条 KP（与 Spec G 一致）。

### 3.3 试卷持久化

`passage_id` / `passage_json` 随 `PaperItem.question` 一起序列化到 `papers` 表的 `items_json`，无需额外表结构。

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
  | "reading_longtext_single_choice";

export interface Passage {
  kind: "listening" | "reading";
  title: string | null;
  content: string;
  audio_url: string | null;
}

// RevisedQuestion / Question 新增 passage_id / passage_json
```

### 4.2 passage 分组渲染逻辑

**修改文件**：`frontend/src/pages/PaperPage.tsx`（与 `WrongBookList.tsx` 同样适用）

在渲染 `paper.items` 前，按 `passage_id` 分组：

```typescript
interface PassageGroup {
  passageId: string | null;
  passage: Passage | null;
  items: PaperItem[];
}

function groupByPassage(items: PaperItem[]): PassageGroup[] {
  const groups = new Map<string, PassageGroup>();
  for (const item of items) {
    const pid = item.question.passage_id ?? null;
    const key = pid ?? `solo-${item.index}`;
    if (!groups.has(key)) {
      groups.set(key, {
        passageId: pid,
        passage: item.question.passage_json ?? null,
        items: [],
      });
    }
    groups.get(key)!.items.push(item);
  }
  return Array.from(groups.values());
}
```

**渲染结构**：
```tsx
{groupByPassage(paper.items).map((group) => (
  <div key={group.passageId ?? `solo-${group.items[0].index}`}>
    {group.passage && (
      <PassageBlock passage={group.passage} />
    )}
    {group.items.map((item) => (
      <QuestionCard key={item.index} item={item} mode={mode} ... />
    ))}
  </div>
))}
```

### 4.3 PassageBlock 组件（共享材料展示 + 听力播放）

**新增文件**：`frontend/src/components/PassageBlock.tsx`

```tsx
import { useState } from "react";
import { Play, Pause } from "lucide-react";
import { speakStem, stopAll, useGloballyPlaying } from "@/lib/tts";
import type { Passage } from "@/types/api";

interface PassageBlockProps {
  passage: Passage;
}

export function PassageBlock({ passage }: PassageBlockProps) {
  const isGloballyPlaying = useGloballyPlaying();
  const [isPlaying, setIsPlaying] = useState(false);

  // 仅听力材料显示播放控件
  const showPlayer = passage.kind === "listening";

  const handlePlay = async () => {
    if (isPlaying) {
      stopAll();
      setIsPlaying(false);
      return;
    }
    setIsPlaying(true);
    try {
      await speakStem(passage.content);
    } finally {
      setIsPlaying(false);
    }
  };

  return (
    <div className="kk-rise mb-6 rounded-md border border-hairline p-5">
      {passage.title && (
        <p className="text-[12px] tracking-[0.1em] text-quiet">{passage.title}</p>
      )}
      {showPlayer && (
        <button
          onClick={handlePlay}
          disabled={isGloballyPlaying && !isPlaying}
          className="mt-2 flex items-center gap-2 rounded-sm border border-accent bg-wash px-4 py-2 text-[14px] text-ink transition-colors hover:text-accent disabled:opacity-50"
        >
          {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
          {isPlaying ? "停止" : "播放听力"}
        </button>
      )}
      <div className="mt-3 whitespace-pre-wrap text-[15px] leading-[1.8] text-ink">
        {passage.content.split("\n").map((line, i) => {
          // 听力材料：标注 M/W 说话者
          if (passage.kind === "listening") {
            const m = line.match(/^(M|W):\s*(.*)$/);
            if (m) {
              const [, speaker, text] = m;
              return (
                <p key={i}>
                  <span className={speaker === "M" ? "text-blue-600 font-medium" : "text-pink-600 font-medium"}>
                    {speaker === "M" ? "M" : "W"}:
                  </span>
                  <span className="ml-2">{text}</span>
                </p>
              );
            }
          }
          return <p key={i}>{line}</p>;
        })}
      </div>
    </div>
  );
}
```

**关键点**：
- 听力材料（`kind="listening"`）显示播放控件，复用 Spec G 的 `speakStem`（M/W 男女声区分）和全局播放锁
- 阅读材料（`kind="reading"`）不显示播放控件，仅展示文本
- 一段 passage 只有一个播放控件（而非每小题一个），避免多按钮播放冲突

### 4.4 听力长文判断题组件（TF）

**新增文件**：`frontend/src/components/question-fields/ListeningTrueFalseField.tsx`

```tsx
import { cn } from "@/lib/utils";

interface ListeningLongtextFieldProps {
  question: RevisedQuestion;
  mode: "answering" | "review";
  value: "T" | "F" | undefined;
  onChange: (value: "T" | "F") => void;
  correctAnswer?: "T" | "F";
  userAnswer?: "T" | "F";
}

export function ListeningLongtextField({
  question, mode, value, onChange, correctAnswer, userAnswer,
}: ListeningLongtextFieldProps) {
  // 注意：passage 不在此组件渲染，由 PassageBlock 在外层渲染一次
  const choices: Array<"T" | "F"> = ["T", "F"];

  return (
    <div className="space-y-3">
      <p className="text-[15px] leading-[1.8] text-ink">{question.stem}</p>
      <div className="flex gap-3">
        {choices.map((choice) => {
          const isUser = (mode === "review" ? userAnswer : value) === choice;
          const isCorrect = correctAnswer === choice;
          return (
            <button
              key={choice}
              type="button"
              disabled={mode === "review"}
              onClick={() => onChange(choice)}
              className={cn(
                "flex-1 rounded-sm border-2 px-4 py-2.5 text-[15px] transition-colors",
                mode === "answering" && "hover:border-accent/50",
                mode === "review" && isCorrect && "border-correct bg-correct/5",
                mode === "review" && isUser && !isCorrect && "border-wrong bg-wrong/5",
                mode === "review" && !isCorrect && !isUser && "border-line-light opacity-70",
                mode === "answering" && isUser && "border-accent bg-wash",
                mode === "answering" && !isUser && "border-line-strong",
              )}
            >
              {choice === "T" ? "True (√)" : "False (×)"}
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

### 4.5 阅读理解组件

**新增文件**：`frontend/src/components/question-fields/ReadingLongtextField.tsx`

复用 `SingleChoiceField` 的选项渲染逻辑（4 选项 A/B/C/D），仅 stem 展示略调整：

```tsx
// 直接复用 SingleChoiceField，因为：
// - options 结构相同（4 个 Option）
// - answer 格式相同（A/B/C/D）
// - 判对错逻辑相同
// 唯一差异：passage 由外层 PassageBlock 渲染
// 因此 ReadingLongtextField 可以直接 = SingleChoiceField 的别名导出
export { SingleChoiceField as ReadingLongtextField } from "./SingleChoiceField";
```

### 4.6 QuestionCard 分派扩展

**修改文件**：`frontend/src/components/QuestionCard.tsx`

```tsx
{question.question_type === "single_choice" ? (
  <SingleChoiceField ... />
) : question.question_type === "listening_single_choice" ? (
  <ListeningSingleChoiceField ... />
) : question.question_type === "listening_true_false" ? (
  <ListeningLongtextField ... />
) : question.question_type === "reading_longtext_single_choice" ? (
  <ReadingLongtextField ... />
) : question.question_type === "word_form" ? (
  <WordFormField ... />
) : (
  <SentenceRewritingField ... />
)}
```

**注意**：TF 题的 `value`/`onChange` 类型为 `"T" | "F"`，与单选的 `string` 不同，`QuestionCard` 的 props 类型需相应扩展。

### 4.7 答案构建扩展

**修改文件**：`frontend/src/lib/answers.ts`

TF 题答案为裸字符串 `"T"`/`"F"`，与单选的裸字符串 `"A"`-`"D"` 同属 `AnswerDraft` 的 string 分支，**无需修改 buildSubmission/listUnanswered 逻辑**。

### 4.8 TTS 工具函数复用

复用 Spec G 的 `frontend/src/lib/tts.ts`：
- `speakStem(passage.content)` —— 听力长文的 content 格式与 Spec G 的 stem 一致（M/W 标注），可直接复用
- 全局播放锁 `useGloballyPlaying` / `subscribePlayingState` —— 确保同一时间只播放一段听力（包括听力单选和听力长文之间互斥）
- `stopAll` —— 离开页面/提交试卷时停止（PaperPage / ReviewPage 已集成，无需重复添加）

---

## 5. 题库摄入支持

### 5.1 数据文件

两类题型分两个 JSON 文件存储：

| 文件 | 题型 | ID 范围 | 起始 passage_id |
|---|---|---|---|
| `data/chapters/shanghai_2026_yimo_listening_c.json` | `listening_true_false` | `q_12001` 起 | `psg_2026_c_001` |
| `data/chapters/shanghai_2026_yimo_reading.json` | `reading_longtext_single_choice` | `q_20001` 起 | `psg_2026_r_001` |

> 📌 实际听力题库按 B/C/D 三部分分文件存储：`shanghai_2026_yimo_listening_b.json`（`listening_single_choice`）、`shanghai_2026_yimo_listening_c.json`（`listening_true_false`）、`shanghai_2026_yimo_listening_d.json`（`listening_fill_blank`）。本 spec 关注的 `listening_true_false` 位于 `_listening_c.json`。

> ⚠️ 已创建的 `shanghai_2026_yimo_listening_c.json` 模板当前为 4 选项单选结构，**需按本 spec §1.3 调整为 TF 结构**（`options: null`，`answer: "T"/"F"`）。

### 5.2 知识点树

在 `data/kb/knowledge_tree.json` 中添加 §1.5 的两条 KP 与映射。

### 5.3 SQLite schema 扩展

**修改文件**：`ingestion/sqlite/schema.sql`

```sql
-- knowledge_points 表：CHECK 约束加新题型
CREATE TABLE IF NOT EXISTS knowledge_points (
    id            TEXT PRIMARY KEY,
    level1        TEXT NOT NULL
                    CHECK (level1 IN (
                        'single_choice', 'word_form', 'sentence_rewriting',
                        'listening_single_choice',
                        'listening_true_false',
                        'reading_longtext_single_choice'
                    )),
    level2        TEXT NOT NULL,
    aliases_json  TEXT NOT NULL DEFAULT '[]'
);

-- questions 表：新增 passage_id / passage_json 列，CHECK 约束加新题型
CREATE TABLE IF NOT EXISTS questions (
    id                  TEXT PRIMARY KEY,
    book                TEXT NOT NULL,
    question_type       TEXT NOT NULL
                          CHECK (question_type IN (
                              'single_choice', 'word_form', 'sentence_rewriting',
                              'listening_single_choice',
                              'listening_true_false',
                              'reading_longtext_single_choice'
                          )),
    chapter_l1          TEXT NOT NULL,
    chapter_l2          TEXT NOT NULL,
    number              TEXT NOT NULL,

    -- 内容字段
    stem                TEXT,
    options_json        TEXT,
    hint                TEXT,
    original_sentence   TEXT,
    instruction         TEXT,
    template            TEXT,

    -- 新增：长文本共享材料
    passage_id          TEXT,
    passage_json        TEXT,           -- JSON 序列化的 Passage 对象

    answer_json         TEXT NOT NULL,
    solution            TEXT,

    source_md           TEXT NOT NULL,
    source_line         INTEGER NOT NULL,
    stem_hash           TEXT NOT NULL,
    created_at          TIMESTAMP NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_q_passage ON questions(passage_id);
```

**迁移注意**：`questions` 表已有数据，新增 `passage_id`/`passage_json` 列需用 `ALTER TABLE ADD COLUMN`（SQLite 允许加列，默认 NULL）。由于 schema.sql 用 `CREATE TABLE IF NOT EXISTS`，对已存在的表不会自动加列——**需要手动执行 ALTER 或重建表**。

### 5.4 loader 扩展

**修改文件**：`ingestion/sqlite/loader.py`

#### 5.4.1 `_stem_hash` 加分支

```python
def _stem_hash(q: dict) -> str:
    payload: dict[str, Any] = {"qt": q["question_type"], "answer": q["answer"]}
    qt = q["question_type"]
    if qt in {"single_choice", "listening_single_choice"}:
        payload["stem"]    = q.get("stem")
        payload["options"] = q.get("options")
    elif qt == "word_form":
        payload["stem"] = q.get("stem")
        payload["hint"] = q.get("hint")
    elif qt == "sentence_rewriting":
        payload["orig"]     = q.get("original_sentence")
        payload["instr"]     = q.get("instruction")
        payload["template"]  = q.get("template")
    elif qt == "reading_longtext_single_choice":
        # 阅读理解：stem + passage_id + options + answer
        payload["stem"]       = q.get("stem")
        payload["passage_id"] = q.get("passage_id")
        payload["options"]    = q.get("options")
    elif qt == "listening_true_false":
        # 听力长文 TF：stem + passage_id + answer（无 options）
        payload["stem"]       = q.get("stem")
        payload["passage_id"] = q.get("passage_id")
    else:
        raise ValueError(f"unknown question_type: {qt!r}")
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
```

**`passage_id` 纳入 hash 的理由**：区分不同材料组的小题，避免同 stem 不同 passage 被误判为重复。

#### 5.4.2 INSERT 语句加两列

```python
cur = conn.execute(
    """
    INSERT OR IGNORE INTO questions (
        id, book, question_type, chapter_l1, chapter_l2, number,
        stem, options_json,
        hint,
        original_sentence, instruction, template,
        passage_id, passage_json,
        answer_json, solution,
        source_md, source_line, stem_hash,
        created_at, version
    ) VALUES (?, ?, ?, ?, ?, ?,
              ?, ?,
              ?,
              ?, ?, ?,
              ?, ?,
              ?, ?,
              ?, ?, ?,
              ?, ?)
    """,
    (
        q["id"], q["book"], q["question_type"],
        q["chapter_l1"], q["chapter_l2"] or "", q["number"],
        q.get("stem"), options_json,
        q.get("hint"),
        q.get("original_sentence"), q.get("instruction"), q.get("template"),
        q.get("passage_id"),
        json.dumps(q["passage_json"], ensure_ascii=False) if q.get("passage_json") else None,
        answer_json, None,
        q["source_md"] or "", q["source_line"], _stem_hash(q),
        now, 1,
    ),
)
```

### 5.5 不做向量库（明确）

**修改文件**：`ingestion/chromadb/loader.py`

在遍历 SQLite 入向量库时，跳过这两类 question_type：

```python
NON_VECTOR_TYPES = {
    "listening_true_false",
    "reading_longtext_single_choice",
}

def _build_embeddings(rows):
    for row in rows:
        if row["question_type"] in NON_VECTOR_TYPES:
            continue  # 长文本题型不进向量库
        text = build_embedding_text(row)
        if text is None:
            continue
        vec = embedder.encode([text])[0]
        collection.add(...)
```

**`embedding_text.py` 不需要为这两类添加模板**——因为根本不会调用到。`build_embedding_text()` 遇到这两类可以返回 None 或直接不处理（loader 已在调用前跳过）。

**CLI `build-vec` 命令**：重跑时这两类题不会被写入 ChromaDB 集合；若历史上有误写入，需手动从集合删除（按 id）。

---

## 6. 测试

### 6.1 后端集成测试

在 `tests/integration/backend/` 中添加：

- `test_papers.py`：生成听力长文/阅读理解试卷（验证 passage 整组出卷）
- `test_grading.py`：
  - TF 题判分（"T"/"F"/"True"/"False"/"t"/"f" 均能正确判对错）
  - 阅读理解判分（A/B/C/D 大小写无关）
- `test_solutions.py`：两类题型解析生成

### 6.2 前端组件测试

- `PassageBlock.test.tsx`：听力播放控件显示、阅读材料无播放按钮、TTS 调用
- `ListeningLongtextField.test.tsx`：TF 按钮渲染、answering/review 模式样式
- `groupByPassage` 单元测试：单 passage 多题分组、无 passage 题独立成组

### 6.3 AI Engine 测试

- Parser few-shot：听力长文/阅读理解的 user_query → question_types 映射
- Retriever：两类题型走 SQL 路径、passage 整组检索
- Reviser：TF 题 answer 校验（拒绝非 T/F）、passage 不变约束

---

## 7. 里程碑

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 数据契约扩展（QuestionType、Passage、Question/RevisedQuestion 加字段） | 待实现 |
| 2 | knowledge_tree.json 加两条 KP | 待实现 |
| 3 | SQLite schema.sql 加 passage 列 + CHECK 约束 | 待实现 |
| 4 | loader.py 扩展（_stem_hash + INSERT） | 待实现 |
| 5 | chromadb/loader.py 跳过两类题型 | 待实现 |
| 6 | 修正 listening_c JSON 模板为 TF 结构 | 待实现 |
| 7 | AI Engine Parser 扩展 | 待实现 |
| 8 | AI Engine Retriever 扩展（SQL only + passage 整组） | 待实现 |
| 9 | AI Engine Reviser 扩展 | 待实现 |
| 10 | AI Engine Solutioner 扩展 | 待实现 |
| 11 | 后端 grading.py TF 判分 | 待实现 |
| 12 | 前端 types/api.ts + PassageBlock 组件 | 待实现 |
| 13 | 前端 ListeningLongtextField + ReadingLongtextField 组件 | 待实现 |
| 14 | 前端 QuestionCard 分派 + PaperPage passage 分组 | 待实现 |
| 15 | 题库数据加载 + 测试 | 待实现 |

---

## 8. 开放问题

1. **passage 整组出卷的 total_questions 语义**：用户说"来 3 道听力长文"是指 3 篇还是 3 道小题？当前设计按小题数估算（3 小题 = 1 篇）。Prompt 需明确 few-shot 引导用户表达（"1 篇听力长文，3 道判断题"）。

2. **passage 跨卷复用**：同一 passage 是否可在不同试卷中重复出现？当前无去重机制，Retriever 随机选 passage 可能跨卷重复。未来可考虑按用户近期答题记录排除已做 passage。

3. **听力长文语速**：复用 Spec G 的 TTS 语速（0.85）。长对话可能更长，未来可考虑分段播放控件（当前整段串行播放）。

4. **passage_json 冗余存储的更新成本**：若材料内容有误需修正，同组 N 题都要改。可写脚本按 passage_id 批量更新。

5. **TF 题答案输入兼容**：用户可能输入 "True"/"False" 全称。后端 grading 已做兼容（见 §3.1），前端 TF 按钮固定为 "T"/"F" 无此问题。

6. **SQLite 表迁移**：现有 `questions` 表已有数据，新增 `passage_id`/`passage_json` 列需 ALTER TABLE。schema.sql 用 `CREATE TABLE IF NOT EXISTS` 不会自动加列，需写迁移脚本或在加载前手动 ALTER。

---

## 9. 不变量

1. **TF 题答案格式**：`answer` 为 `"T"` 或 `"F"`（大写），`options` 恒为 `null`。

2. **阅读理解答案格式**：`answer` 为 `"A"`/`"B"`/`"C"`/`"D"`，`options` 为 4 个 Option，与 `single_choice` 一致。

3. **passage 同组一致性**：同 `passage_id` 的所有小题，其 `passage_json` 内容必须完全一致（冗余存储的一致性约束，loader 不强制校验，由数据生产端保证）。

4. **两类题型不进向量库**：`listening_true_false` 和 `reading_longtext_single_choice` 永远不写入 ChromaDB 集合，Retriever 对它们只走 SQL 路径。

5. **passage 整组出卷**：Retriever 检索长文本题时必须按 `passage_id` 整组返回，不允许只取某 passage 的部分小题。

6. **passage 不变约束**（Reviser）：
   - `original` 档：`passage_id` / `passage_json` 与原题完全一致
   - `light` 档：`passage_json.content` 可微调，`passage_id` 不变
   - `fresh` 档：`passage_json` 可重写，`passage_id` 生成新值

7. **TTS 复用**：听力长文播放复用 Spec G 的 `speakStem` / `stopAll` / 全局播放锁，不引入新的 TTS 实现。

8. **`question_type` / `knowledge_point_ids` 不可变**：与 Spec A §2.6 一致，Reviser 任何档位都不修改这两个字段。

---

## 10. 与现有 spec 的接口

- **Spec A**：扩展 `Question` / `RevisedQuestion` 数据契约（加 passage 字段）；扩展 SQLite schema（加列 + CHECK）
- **Spec B**：Parser 加题型枚举；Retriever 加 SQL-only 路径与 passage 整组逻辑；Reviser 加 TF 校验；Solutioner 加解析要求
- **Spec C**：grading 加 TF 判分兼容
- **Spec D**：前端加 PassageBlock / ListeningLongtextField / ReadingLongtextField 组件与 passage 分组渲染
- **Spec G**：复用 TTS 工具函数（`tts.ts`），全局播放锁覆盖听力单选与听力长文
