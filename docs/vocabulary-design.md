# 背单词模块设计（Vocabulary / 间隔重复）

**创建日期**：2026-08-11（补写，追认已合入实现）
**范围**：中考词汇的间隔重复（spaced-repetition）背诵模块——离线词表构建、
用户库表结构、每日卡片调度、当日重试队列、批改反馈、进度画像、后端端点、前端页面。
**状态**：✅ 已实现并合入 `dev`（来自 `CJN/vocabulary-mvp`）。
**归属**：词汇数据与用户进度都属于**用户库** `data/app.db`，经 `storage.connect()` 访问；
与只读题库 `data/questions.db` 无关，两库不 JOIN。

---

## 0. 设计原则

- **词库是确定性数据，调度是确定性代码，LLM 不参与**——与全局理念一致：作文/解析用
  LLM，背单词的排期、判定、进度全是普通代码。
- **间隔重复采用 SM-2 变体**：正确则升级、间隔递增；模糊保持；遗忘归零。间隔固定为
  `1 / 3 / 7 / 14 / 30` 天（`VOCABULARY_INTERVALS`），最多 5 档（`stage 0..5`）。
- **当日重试队列**：当日答"模糊/遗忘"的词不等到明天，进入 same-day 重试队列，当日内
  再次出现直到答对，强化短期记忆。
- **时区固定 Asia/Shanghai（UTC+8）**：Windows 自带 Python 可能缺 IANA 时区库，上海无
  夏令时，用固定 `+08:00` 偏移（`VOCABULARY_TIMEZONE`）保证每日配额与"学习日"边界稳定。
- **每日新词上限**默认 20（`DEFAULT_DAILY_NEW_LIMIT`），用户可在 10–50 之间调整。

---

## 1. 离线词表构建（ingestion/）

两支脚本产出 JSON 种子文件，再由 `storage.seed_vocabulary_from_json()` 导入
`data/app.db` 的 `vocabulary_wordlists` / `vocabulary_words` 表。

| 脚本 | 职责 |
|------|------|
| `ingestion/build_vocabulary_wordlist.py` | 从公开索引构建可溯源的"上海基础词表"种子（保留来源 URL + 抓取页 SHA256；只取 word / 词性 / 中文释义，例句为占位模板） |
| `ingestion/build_merged_vocabulary.py` | 合并**国家核心词表**（教育部 2022 core 1600）与**上海扩展词表**（basic 1678），标注 `source_category`（`national_core` / `shanghai_extension`）；核心词表为权威成员来源，`dict.cn` 仅用于补全官方词的中文短义 |

- 词表来源数据放 `data/vocabulary/`（如 `moe-2022-core-1600.json`、`shanghai-basic-1678.json`）。
- 每个词条含：`term` / `normalized_term`（唯一）/ `part_of_speech` / `meanings`（JSON）/
  `example_en` / `example_zh` / `source_category`。例句在正式发布前为项目自有占位模板。

---

## 2. 数据表（`data/app.db`，8 张）

均由 `storage.init_db()` 经迁移创建（见 §5）。所有表通过 `user_id` 关联 `users(id)`。

| 表 | 用途 |
|----|------|
| `vocabulary_wordlists` | 词表元数据（label / source_url / source_accessed_at / source_sha256 / imported_at） |
| `vocabulary_words` | 词条主数据（term / normalized_term UNIQUE / part_of_speech / meanings_json / example_en / example_zh / source_category ∈ {national_core, shanghai_extension} / is_active） |
| `vocabulary_wordlist_sources` | 合并词表的分类来源溯源（wordlist_id × category → label / url / accessed_at / sha256） |
| `vocabulary_settings` | 每用户设置（`daily_new_limit`，CHECK 10–50，默认 20） |
| `vocabulary_progress` | 每用户每词进度：`stage`（0–5）/ `introduced_at` / `last_reviewed_at` / `due_at` / `review_count`，主键 (user_id, word_id)，索引 (user_id, due_at) |
| `vocabulary_daily_cards` | 当日卡片：(user_id, study_date, word_id) 主键，`card_type` ∈ {review, new}，`completed_at` |
| `vocabulary_review_logs` | 每次评分流水：requested_rating / applied_rating / spelling_correct / stage_after / next_due_at |
| `vocabulary_daily_retry_queue` | 当日重试队列：first_rating / last_rating / retry_count / queue_order / passed_at，主键 (user_id, study_date, word_id) |

---

## 3. 调度逻辑（`shared/storage.py`）

关键常量：`VOCABULARY_TIMEZONE`（Asia/Shanghai）、`VOCABULARY_INTERVALS = (1,3,7,14,30)`、
`DEFAULT_DAILY_NEW_LIMIT = 20`。

### 3.1 每日卡片组装（`_ensure_vocabulary_daily_cards`）

以"上海学习日"（`_vocabulary_date`）为界。进入某学习日时：
1. **复习卡**：取 `vocabulary_progress` 中 `due_at <= now` 的词，按 `due_at, word_id` 排序，
   建成 `card_type='review'` 卡片。
2. **新词卡**（`_append_vocabulary_daily_new_cards`）：在每日新词上限内补入尚未学过的词，
   建成 `card_type='new'` 卡片。

### 3.2 评分与进度更新（`_update_vocabulary_progress`）

评分 `rating ∈ {known, fuzzy, forgot}`：
- `known`：`stage = min(stage+1, 5)`，`delay = VOCABULARY_INTERVALS[stage-1]`，`due_at = now + delay 天`。
- `fuzzy`：`stage` 保持，按当前档重新排期。
- `forgot`：`stage = 0`（归零，很快重现）。

每次写 `vocabulary_review_logs` 一行流水（含 `stage_after` / `next_due_at`）。

### 3.3 当日重试队列（same-day retry）

`judge_vocabulary_card` 在主卡答完后：
- 若 `rating != known`，把该词加入 `vocabulary_daily_retry_queue`（当日内再考）。
- same-day 重试卡答 `known` → 标记 `passed_at`（当日过关）；仍非 known → `retry_count++`、
  重排 `queue_order` 到队尾。
- `_vocabulary_active_card` 决定"当前该考哪张卡"，`phase` 区分正常卡与 same_day_retry。

---

## 4. 后端端点（`backend/api/vocabulary.py`，prefix `/api/vocabulary`）

均需登录（`Depends(current_user)`）。`ValueError` → 422 `ValidationError`。

| 方法 | 路径 | 请求 → 响应 | 说明 |
|------|------|------------|------|
| GET | `/api/vocabulary/today` | — → `VocabularyTodayResponse` | 今日卡片：当前待考卡（题面隐藏例句中的目标词）+ 任务计数（新词/复习/重试） |
| POST | `/api/vocabulary/judgments` | `VocabularyJudgmentRequest`（word_id + rating）→ `VocabularyJudgmentResponse` | 提交对当前卡的评分，返回词条详情 + 新 stage + next_due_at + 是否入当日重试 + 最新计数 |
| GET | `/api/vocabulary/progress` | — → `VocabularyProgressResponse` | 学习进度画像（已学/到期/各 stage 分布等） |
| PATCH | `/api/vocabulary/settings` | `VocabularySettingsRequest`（daily_new_limit）→ `VocabularySettingsResponse` | 调整每日新词上限（10–50） |

对应 `storage` 函数：`get_vocabulary_today` / `judge_vocabulary_card` /
`get_vocabulary_progress` / `set_vocabulary_daily_new_limit`；
词表导入 `seed_vocabulary_from_json`。相关 pydantic 模型在 `backend/schemas.py`
（`VocabularyCardPrompt` / `VocabularyCardDetail` / `VocabularyTaskCounts` /
`VocabularyTodayResponse` / `VocabularyJudgmentRequest` / `VocabularyJudgmentResponse` /
`VocabularyProgressResponse` / `VocabularyWordlistSource` /
`VocabularySettingsRequest` / `VocabularySettingsResponse`）。

---

## 5. 迁移（`schema_migrations`，按 ID 字典序）

| 迁移 ID | 内容 |
|---------|------|
| `20260730_001_vocabulary_mvp` | 建 6 张核心表（wordlists / words / settings / progress / daily_cards / review_logs） |
| `20260804_001_vocabulary_retry_queue` | 建 `vocabulary_daily_retry_queue`（当日重试队列） |
| `20260805_001_vocabulary_word_sources` | `vocabulary_words` 增 `source_category` 列 + 建 `vocabulary_wordlist_sources` |

迁移函数 `_migrate_vocabulary_schema` / `_migrate_vocabulary_retry_queue` /
`_migrate_vocabulary_word_sources`，在 `_apply_migrations` 中注册。

---

## 6. 前端页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/vocabulary` | `VocabularyPage` | 今日背词：卡片正面（例句挖空 / 提示）→ 拼写作答 → 评分（认识 / 模糊 / 忘了）→ 反馈翻面，任务计数进度 |
| `/vocabulary/progress` | `VocabularyProgressPage` | 背词进度画像 |

- 侧边栏：`/vocabulary` 在「练习」组（"背单词"），`/vocabulary/progress` 在「复盘」组（"背词进度"）。
- 前端 API 封装：`frontend/src/api/vocabulary.ts`；展示辅助 `frontend/src/lib/vocabularyDisplay.ts`。

---

## 7. 与其他子系统的边界

- **不进题库/向量库**：词汇与 `questions.db`、ChromaDB 完全无关（题型 `QuestionType` 不含词汇）。
- **纯用户库**：所有词汇表在 `data/app.db`，`storage.connect()` 访问；`connect_bank()` 不涉及。
- **无 LLM**：调度、判定、进度全为确定性代码；例句/释义为离线词表内容。
