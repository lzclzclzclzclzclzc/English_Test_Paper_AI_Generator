# Spec G：听力选择题支持设计

**创建日期**：2026-07-24
**项目根目录**：`d:\Code\English_Test_Paper_AI_Generator`
**范围**：新增听力选择题（`listening_single_choice`）题型支持，覆盖数据契约、AI Engine、后端、前端全链路
**依赖**：
- [Spec A（题库摄入）](./2026-07-07-question-bank-ingestion-design.md)
- [Spec B（AI Engine）](./2026-07-07-ai-engine-design.md)
- [Spec C（后端）](./2026-07-07-backend-design.md)
- [Spec D（前端）](./2026-07-07-frontend-design.md)

---

## 0. 范围与产出

### 0.1 本 spec 定义
- 新增题型 `listening_single_choice`（听力选择）的数据契约扩展
- AI Engine 各模块对听力选择题的支持（Parser/Retriever/Reviser/Solutioner）
- 后端判对错逻辑扩展
- 前端听力题组件实现（选项呈现 + TTS 播放）

### 0.2 本 spec 不定义
- 其他听力题型（如听力填空、听力听写等）——留待未来
- 真实音频文件支持——当前使用浏览器 TTS 合成

### 0.3 核心需求
1. 选项呈现方式参考单项选择题（`single_choice`）
2. 支持改题（light/fresh/original）和解析功能
3. 题号前显示播放控件，点击播放 `stem` 字段内容
4. 使用浏览器 TTS，区分 M（男声）和 W（女声）

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
    "writing",
]
```

### 1.2 听力选择题数据结构

听力选择题的数据结构与单项选择题类似，但 `stem` 字段格式特殊：

```json
{
  "id": "q_10001",
  "book": "shanghai_2026_yimo",
  "question_type": "listening_single_choice",
  "chapter_l1": "1 听力选择",
  "chapter_l2": null,
  "number": "7",
  "stem": "M: Good afternoon. What can I do for you?\nW: I'd like to report a theft, please. Someone has stolen my mobile phone.\nM: All right, let's start with what happened.\nQuestion: Where does the dialogue take place?",
  "options": [
    {"label": "A", "text": "At a store."},
    {"label": "B", "text": "At a cinema."},
    {"label": "C", "text": "At a hotel."},
    {"label": "D", "text": "At a police office."}
  ],
  "answer": "D",
  "knowledge_point_ids": ["kp_listening_dialogue"]
}
```

**`stem` 格式约定**：
- 每行以 `M:`（男声）或 `W:`（女声）开头，表示说话者性别
- 最后一行以 `Question:` 开头，表示听力问题
- 换行符 `\n` 分隔不同说话者的台词

### 1.3 知识点扩展

在 `data/kb/knowledge_tree.json` 中新增听力相关知识点：

```json
{
  "id": "kp_listening_dialogue",
  "level1": "listening_single_choice",
  "level2": "听力对话理解",
  "aliases": ["听力", "听力理解", "对话"]
}
```

### 1.4 RevisedQuestion 支持

`RevisedQuestion` 模型已支持 `listening_single_choice`，无需额外字段变更。

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
    "- listening_true_false: 听力判断题（一段长文本/对话后跟多道 True/False 判断题）",
    "- listening_fill_blank: 听力填词（一段听力材料后跟多道小题，每空限填一词，题号连续）",
    "- reading_longtext_single_choice: 阅读理解（一段短文后跟多道 4 选项单选题）",
    "- cloze_single_choice: 完形填空（一段短文含多处空格，每空 4 选项单选）",
    "- reading_first_blank: 阅读首字母填空（一篇短文，内嵌 7 个首字母填空，每空限填一词）",
    "- writing: 英语作文（给出作文题目，由用户写作并由 AI 批改评分）",
])
```

**本地校验扩展**：

```python
# _local_validate 函数中，校验 type_distribution 的 key 是否为合法题型
VALID_QUESTION_TYPES = {"single_choice", "word_form", "sentence_rewriting", "listening_single_choice", "listening_true_false", "listening_fill_blank", "reading_longtext_single_choice", "cloze_single_choice", "reading_first_blank", "writing"}
```

**Prompt 修改**：`ai_engine/prompts/parser.md`

在题型枚举部分添加：
```
- listening_single_choice: 听力选择
```

在 light 档位触发词中添加：
```
- 题型类：任何题型名称（如"单选题"、"单项选择"、"词性转换"、"改写句子"、"听力"、"听力选择"等）
```

添加 few-shot 示例：
```json
输入："来 10 道听力选择题"
输出：{"question_types": ["listening_single_choice"], ...}
```

### 2.2 Retriever 扩展

**修改文件**：`ai_engine/retriever.py`

Retriever 的混合检索策略对 `listening_single_choice` 完全兼容，无需修改核心逻辑。

**注意**：听力选择题的向量检索基于 `stem` 字段内容进行语义匹配，与 `single_choice` 一致。

### 2.3 Reviser 扩展

**修改文件**：`ai_engine/reviser.py`

Reviser 的三档策略（original/light/fresh）对 `listening_single_choice` 完全兼容。

**答案格式校验扩展**：

```python
def _validate_revision(question, revised):
    # 听力选择题与单项选择题共享答案格式校验
    if question.question_type in {"single_choice", "listening_single_choice"}:
        if revised.answer not in {"A", "B", "C", "D"}:
            return False, "answer must be A/B/C/D"
        if len(revised.options) != 4:
            return False, "options must have exactly 4 items"
        labels = {opt.label for opt in revised.options}
        if labels != {"A", "B", "C", "D"}:
            return False, "options labels must be A/B/C/D without duplicates"
    return True, None
```

**Prompt 修改**：`ai_engine/prompts/reviser_light.md` 和 `ai_engine/prompts/reviser_fresh.md`

在不变约束中添加听力选择题的 `stem` 格式要求：
```
- 听力选择题（listening_single_choice）的 stem 必须包含说话者标识（M: 男声 / W: 女声）和问题（Question:）
- 示例格式：
  M: Good morning.\nW: Hello.\nQuestion: What time is it?
```

### 2.4 Solutioner 扩展

**修改文件**：`ai_engine/solutioner.py`

Solutioner 对 `listening_single_choice` 的支持与 `single_choice` 类似，但解析内容需要针对听力特点进行调整。

**Prompt 修改**：`ai_engine/prompts/solutioner.md`

在特别要求中添加：
```
- 听力选择题（listening_single_choice）：必须解释对话中的关键信息、语气或语境如何帮助确定答案，并指出干扰项为何不符合对话内容
```

---

## 3. 后端支持（Spec C 扩展）

### 3.1 判对错逻辑扩展

**修改文件**：`backend/services/grading.py`

听力选择题的判对错逻辑与单项选择题完全一致（大小写无关比较）：

```python
def compare(user_answer, correct_answer, question_type):
    # 单选类题型：大小写无关比较
    if question_type in {"single_choice", "listening_single_choice", "listening_true_false", "reading_longtext_single_choice", "cloze_single_choice"}:
        return isinstance(user_answer, str) and user_answer.strip().upper() == correct_answer.strip().upper()
    # ... 其他逻辑不变
```

### 3.2 知识点目录

后端无需修改——`GET /api/knowledge-points` 会自动返回新添加的听力知识点。

---

## 4. 前端支持（Spec D 扩展）

### 4.1 类型定义扩展

**修改文件**：`frontend/src/types/api.ts`

```typescript
export type QuestionType = "single_choice" | "word_form" | "sentence_rewriting" | "listening_single_choice" | "listening_true_false" | "listening_fill_blank" | "reading_longtext_single_choice" | "cloze_single_choice" | "reading_first_blank" | "writing";
```

### 4.2 新增题目组件

**新增文件**：`frontend/src/components/question-fields/ListeningSingleChoiceField.tsx`

**听力原文的呈现分模式**（贴近真实听力考试）：
- **答题模式（`mode === "answering"`）**：只显示播放控件（播放/播放中按钮），不显示听力原文——用户只能靠听。
- **复盘模式（`mode === "review"`）**：显示播放控件 + 完整听力原文，每行以 M/W 说话者标签区分（`♂ M` / `♀ W`），非台词行（如 `Question:`）加粗呈现。

组件结构：

```tsx
interface ListeningSingleChoiceFieldProps {
  question: RevisedQuestion;
  mode: "answering" | "review";
  value?: string;
  onChange?: (v: string) => void;
  result?: GradeResultItem;
}

export function ListeningSingleChoiceField({ question, mode, value, onChange, result }: ListeningSingleChoiceFieldProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  // 订阅全局播放锁：同一时间只允许一段听力播放
  const globallyPlaying = useSyncExternalStore(subscribePlayingState, isGloballyPlaying);
  const options = question.options ?? [];

  const handlePlay = async () => {
    if (!question.stem) return;
    setIsPlaying(true);
    try {
      await speakStem(question.stem);
    } finally {
      setIsPlaying(false);
    }
  };

  return (
    <div className="flex flex-col gap-3.5">
      {/* 播放控件（全局播放中时禁用） */}
      <button onClick={handlePlay} disabled={isPlaying || globallyPlaying}>
        {/* play / pause 图标 */}
        <span>{isPlaying ? "播放中..." : "播放听力"}</span>
      </button>

      {/* 听力原文：做题态隐藏（仅靠听），交卷后 review 态才呈现 */}
      {mode === "review" && question.stem && (
        <div>
          {question.stem.split("\n").map((line, index) => {
            const speakerMatch = line.match(/^(M|W):\s*(.*)$/);
            if (speakerMatch) {
              const [, speaker, text] = speakerMatch;
              return (
                <p key={index}>
                  <span>{speaker === "M" ? "♂ M" : "♀ W"}</span>
                  <span>{text}</span>
                </p>
              );
            }
            return <p key={index} className="font-bold">{line}</p>;
          })}
        </div>
      )}

      {/* 选项（与 SingleChoiceField 一致的纵向布局），answering 用 RadioGroup，review 用只读态高亮对错 */}
      {/* ... */}
    </div>
  );
}
```

**注意**：M/W 仅用文字标签（`♂ M` / `♀ W`）区分，遵循 Kissaten 设计系统的 one-chroma rule，不使用 blue/pink 双色。

### 4.3 TTS 工具函数

**新增文件**：`frontend/src/lib/tts.ts`

**设计要点**：
- **全局播放锁**：模块级变量 `_playing` 保证同一时间只有一段听力在播放。`isGloballyPlaying()` / `subscribePlayingState()` 供组件通过 `useSyncExternalStore` 订阅播放状态（其它听力题的播放按钮据此禁用）。
- **token 取消机制**：每次 `speakStem` 递增 `_cancelToken` 并记住自己的 `myToken`；`stopAll()` 通过再次递增 `_cancelToken` 使正在串行播放的循环在下一句前中断。
- `speakStem` 返回 `Promise<boolean>`：`true` = 已开始播放，`false` = 被阻止（已有播放进行中）。
- `preloadVoices()` 注册 `onvoiceschanged` 监听器并立即调用一次 `getVoices()`，解决某些浏览器首次调用时 voices 列表为空的问题。
- 男/女声匹配抽为 `getMaleVoice()` / `getFemaleVoice()`，优先系统语音（`localService`），按常见英文名称清单匹配，回退到第一个英语语音。

```typescript
// 全局播放锁 + 取消 token（模块级单例）
let _playing = false;
let _cancelToken = 0;
const _listeners = new Set<() => void>();

export function isGloballyPlaying(): boolean {
  return _playing;
}

export function subscribePlayingState(callback: () => void): () => void {
  _listeners.add(callback);
  return () => { _listeners.delete(callback); };
}

/**
 * TTS 播放听力原文。
 * 如果已有播放进行中，直接返回不播放。
 * @returns true=已开始播放，false=被阻止（已有播放中）
 */
export async function speakStem(stem: string): Promise<boolean> {
  if (_playing) return false;
  _setPlaying(true);
  const myToken = ++_cancelToken;

  try {
    window.speechSynthesis.cancel();
    const lines = stem.split("\n");
    const maleVoice = getMaleVoice();
    const femaleVoice = getFemaleVoice();
    const utterances = lines.map((line) => {
      const m = line.match(/^(M|W):\s*(.*)$/);
      const u = new SpeechSynthesisUtterance(m ? m[2] : line);
      u.lang = "en-US";
      u.rate = m ? 0.85 : 0.9; // 台词稍慢，便于听力理解
      if (m) u.voice = (m[1] === "M" ? maleVoice : femaleVoice) ?? u.voice;
      return u;
    });

    for (const utterance of utterances) {
      if (myToken !== _cancelToken) break; // 被 stopAll 取消，立即退出
      await new Promise<void>((resolve) => {
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
      });
    }
  } finally {
    if (myToken === _cancelToken) _setPlaying(false); // 未被外部取消才复位
  }
  return true;
}

/** 停止所有播放并重置全局锁（递增 token 使运行中的循环中断） */
export function stopAll(): void {
  _cancelToken++;
  window.speechSynthesis.cancel();
  _setPlaying(false);
}

/** 预加载 voices（解决某些浏览器首次调用时 voices 列表为空的问题） */
export function preloadVoices(): void {
  const loadVoices = () => { window.speechSynthesis.getVoices(); };
  window.speechSynthesis.onvoiceschanged = loadVoices;
  loadVoices();
}
```

### 4.4 QuestionCard 分派扩展

**修改文件**：`frontend/src/components/QuestionCard.tsx`

```tsx
{question.question_type === 'single_choice' ? (
  <SingleChoiceField question={question} mode={mode} ... />
) : question.question_type === 'listening_single_choice' ? (
  <ListeningSingleChoiceField question={question} mode={mode} ... />
) : question.question_type === 'word_form' ? (
  <WordFormField question={question} mode={mode} ... />
) : (
  <SentenceRewritingField question={question} mode={mode} ... />
)}
```

### 4.5 答案构建扩展

**修改文件**：`frontend/src/lib/answers.ts`

听力选择题的答案格式与单项选择题相同（裸标签 `str`），无需修改。

---

## 5. 题库摄入支持

### 5.1 数据文件

已存在的听力题目数据文件：`data/chapters/shanghai_2026_yimo_listening_b.json`

### 5.2 知识点树

需要在 `data/kb/knowledge_tree.json` 中添加听力相关知识点。

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

在 `tests/integration/backend/test_papers.py` 中添加听力选择题的测试用例：

- 生成听力选择题试卷
- 提交听力选择题答题并判分
- 生成听力选择题解析

### 6.2 前端组件测试

在 `frontend/src/components/question-fields/ListeningSingleChoiceField.test.tsx` 中添加测试：

- 组件渲染（播放按钮、题干、选项）
- TTS 播放功能（mock window.speechSynthesis）
- 答题模式和复盘模式的选项样式

---

## 7. 里程碑

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 数据契约扩展（QuestionType、知识点） | 待实现 |
| 2 | AI Engine Parser 扩展 | 待实现 |
| 3 | AI Engine Reviser 扩展 | 待实现 |
| 4 | AI Engine Solutioner 扩展 | 待实现 |
| 5 | 后端判对错逻辑扩展 | 待实现 |
| 6 | 前端 ListeningSingleChoiceField 组件 | 待实现 |
| 7 | 前端 TTS 工具函数 | 待实现 |
| 8 | 前端 QuestionCard 分派扩展 | 待实现 |
| 9 | 题库数据加载 | 待实现 |
| 10 | 测试 | 待实现 |

---

## 8. 开放问题

1. **TTS 语音质量**：浏览器原生 TTS 的语音质量和男女声区分能力因浏览器而异，可能在某些浏览器上效果不佳。未来可考虑接入第三方 TTS API（如百度、讯飞）。

2. **播放进度控制**：当前只支持播放/停止，不支持暂停和进度条。未来可考虑添加更精细的播放控制。

3. **听力原文显示**：当前在播放控件下方显示完整的听力原文，这与真实听力考试有所不同。未来可考虑添加"隐藏原文"模式，更接近真实考试场景。

4. **语速调节**：当前语速固定为 0.85，未来可考虑添加语速调节控件。

---

## 9. 不变量

1. **听力选择题的答案格式与单项选择题一致**：`answer` 为裸标签 `str`（"A"/"B"/"C"/"D"），判对错逻辑复用。

2. **Reviser 不变字段**：`question_type` / `knowledge_point_ids` 在任何档位下都不被修改（与 `single_choice` 一致）。

3. **Solutioner 无缓存**：每次调用都直接问 LLM，不读/写 `questions.solution`。

4. **前端 TTS 不依赖后端**：播放逻辑完全在浏览器端实现，不产生额外的 API 调用。
