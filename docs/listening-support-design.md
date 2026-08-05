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
QuestionType = Literal["single_choice", "word_form", "sentence_rewriting", "listening_single_choice"]
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
])
```

**本地校验扩展**：

```python
# _local_validate 函数中，校验 type_distribution 的 key 是否为合法题型
VALID_QUESTION_TYPES = {"single_choice", "word_form", "sentence_rewriting", "listening_single_choice"}
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
    # 单选和听力选择：大小写无关比较
    if question_type in {"single_choice", "listening_single_choice"}:
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
export type QuestionType = "single_choice" | "word_form" | "sentence_rewriting" | "listening_single_choice";
```

### 4.2 新增题目组件

**新增文件**：`frontend/src/components/question-fields/ListeningSingleChoiceField.tsx`

组件结构：

```tsx
interface ListeningSingleChoiceFieldProps {
  question: RevisedQuestion;
  mode: "answering" | "review";
  value: string | undefined;
  onChange: (value: string) => void;
  correctLabel?: string;
  userAnswer?: string;
}

export function ListeningSingleChoiceField({ question, mode, value, onChange, correctLabel, userAnswer }: ListeningSingleChoiceFieldProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const options = question.options ?? [];
  
  const handlePlay = async () => {
    // TTS 播放逻辑
    setIsPlaying(true);
    try {
      await speakStem(question.stem ?? "");
    } finally {
      setIsPlaying(false);
    }
  };
  
  return (
    <div className="space-y-4">
      {/* 播放控件 */}
      <div className="flex items-center gap-3">
        <button
          onClick={handlePlay}
          disabled={isPlaying}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50"
        >
          {isPlaying ? (
            <Pause className="w-4 h-4" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          <span>{isPlaying ? "播放中..." : "播放听力"}</span>
        </button>
      </div>
      
      {/* 题干（听力原文） */}
      <div className="text-sm text-text-mid space-y-1">
        {(question.stem ?? "").split("\n").map((line, index) => {
          const speakerMatch = line.match(/^(M|W):\s*(.*)$/);
          if (speakerMatch) {
            const [, speaker, text] = speakerMatch;
            return (
              <p key={index}>
                <span className={speaker === "M" ? "text-blue-600 font-medium" : "text-pink-600 font-medium"}>
                  {speaker === "M" ? "男" : "女"}:
                </span>
                <span className="ml-2">{text}</span>
              </p>
            );
          }
          return <p key={index} className="font-medium">{line}</p>;
        })}
      </div>
      
      {/* 选项（参考单项选择题） */}
      <div className="grid grid-cols-2 gap-2 max-sm:grid-cols-1">
        {options.map((opt) => {
          const isUser = userAnswer === opt.label;
          const isCorrect = correctLabel === opt.label;
          
          if (mode === "answering") {
            return (
              <label key={opt.label} className="flex cursor-pointer items-center gap-2.5 p-3 rounded-lg border-2 border-line-light hover:border-primary/50">
                <RadioGroupItem value={opt.label} checked={value === opt.label} onCheckedChange={(checked) => checked && onChange(opt.label)} />
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-line-strong text-xs">
                  {opt.label}
                </span>
                <span className="font-question">{opt.text}</span>
              </label>
            );
          } else {
            // review mode
            return (
              <div key={opt.label} className={cn(
                "flex items-center gap-2.5 p-3 rounded-lg border-2",
                isCorrect ? "border-correct bg-correct/5" :
                isUser ? "border-wrong bg-wrong/5" :
                "border-line-light opacity-70"
              )}>
                <span className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full text-xs",
                  isCorrect ? "bg-correct text-white" :
                  isUser ? "bg-wrong text-white" :
                  "border border-line-strong"
                )}>
                  {opt.label}
                </span>
                <span className="font-question">{opt.text}</span>
                {isCorrect && <span className="ml-auto text-correct">✓</span>}
                {isUser && !isCorrect && <span className="ml-auto text-wrong">✗</span>}
              </div>
            );
          }
        })}
      </div>
    </div>
  );
}
```

### 4.3 TTS 工具函数

**新增文件**：`frontend/src/lib/tts.ts`

```typescript
/**
 * TTS 播放听力原文
 * @param stem 听力原文，格式：M: xxx\nW: xxx\nQuestion: xxx
 */
export async function speakStem(stem: string): Promise<void> {
  // 停止之前的播放
  window.speechSynthesis.cancel();
  
  const lines = stem.split("\n");
  const utterances: SpeechSynthesisUtterance[] = [];
  
  for (const line of lines) {
    const speakerMatch = line.match(/^(M|W):\s*(.*)$/);
    if (speakerMatch) {
      const [, speaker, text] = speakerMatch;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = 0.85; // 稍慢，便于听力理解
      // 根据说话者设置不同的 voice（尝试区分男女声）
      const voices = window.speechSynthesis.getVoices();
      if (speaker === "M") {
        // 优先选择男声
        const maleVoice = voices.find(v => v.name.includes("Male") || v.name.includes("male") || v.name.includes("Brian") || v.name.includes("Alex"));
        if (maleVoice) {
          utterance.voice = maleVoice;
        }
      } else {
        // 优先选择女声
        const femaleVoice = voices.find(v => v.name.includes("Female") || v.name.includes("female") || v.name.includes("Samantha") || v.name.includes("Google US English Female"));
        if (femaleVoice) {
          utterance.voice = femaleVoice;
        }
      }
      utterances.push(utterance);
    } else {
      // Question: 或其他内容，用默认 voice
      const utterance = new SpeechSynthesisUtterance(line);
      utterance.lang = "en-US";
      utterance.rate = 0.9;
      utterances.push(utterance);
    }
  }
  
  // 串行播放所有语句
  for (const utterance of utterances) {
    await new Promise<void>((resolve) => {
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve(); // 出错时继续下一句
      window.speechSynthesis.speak(utterance);
    });
  }
}

/**
 * 预加载 voices（解决某些浏览器首次调用时 voices 列表为空的问题）
 */
export function preloadVoices(): void {
  const loadVoices = () => {
    window.speechSynthesis.getVoices();
  };
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
