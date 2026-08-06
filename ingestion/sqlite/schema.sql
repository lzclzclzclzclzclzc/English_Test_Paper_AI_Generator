-- SQLite schema for the question bank (Spec §3.7, adjusted for the fields we
-- actually ended up with after ingestion).
--
-- Deviations from Spec §3.7:
--   * `difficulty` column dropped (we decided not to grade difficulty)
--   * `embedding_text` column dropped (belongs to ChromaDB.documents per §3.8)
--   * `knowledge_points.parent_id` dropped (KP tree is flat: level1 is a
--     fixed 3-value enum, no need for a self-referential parent link)
--   * `questions.chapter` split into `chapter_l1` + `chapter_l2` (chapter
--     numbering differs across books; two-segment key matches our JSON)
--   * `questions` gains `hint / original_sentence / instruction / template`
--     for word_form and sentence_rewriting layouts
--   * `attempt_items.difficulty` dropped (mastery is per-KP, not per-difficulty)
--
-- Everything writable by ingestion; ai_engine will only SELECT (except
-- Solutioner filling `questions.solution` — Spec §1.5).

PRAGMA foreign_keys = ON;

-- ─── knowledge_points ────────────────────────────────────────────
-- Flat table: level1 is `question_type` verbatim, level2 is 中文.
CREATE TABLE IF NOT EXISTS knowledge_points (
    id            TEXT PRIMARY KEY,
    level1        TEXT NOT NULL
                    CHECK (level1 IN ('single_choice', 'word_form', 'sentence_rewriting', 'listening_single_choice', 'listening_true_false', 'listening_fill_blank', 'reading_longtext_single_choice', 'cloze_single_choice', 'reading_first_blank', 'writing')),
    level2        TEXT NOT NULL,
    aliases_json  TEXT NOT NULL DEFAULT '[]'
);

-- ─── questions ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS questions (
    id                  TEXT PRIMARY KEY,       -- q_00001
    book                TEXT NOT NULL,
    question_type       TEXT NOT NULL
                          CHECK (question_type IN ('single_choice', 'word_form', 'sentence_rewriting', 'listening_single_choice', 'listening_true_false', 'listening_fill_blank', 'reading_longtext_single_choice', 'cloze_single_choice', 'reading_first_blank', 'writing')),
    chapter_l1          TEXT NOT NULL,          -- "1 单项选择"
    chapter_l2          TEXT NOT NULL,          -- "1.4 不定代词"
    number              TEXT NOT NULL,          -- "1" or "1-3"

    -- Content — populated conditionally per question_type.
    stem                TEXT,                   -- single_choice / word_form
    options_json        TEXT,                   -- single_choice / listening_true_false; JSON list
    hint                TEXT,                   -- word_form only
    original_sentence   TEXT,                   -- sentence_rewriting; may embed <u>...</u>
    instruction         TEXT,                   -- sentence_rewriting
    template            TEXT,                   -- sentence_rewriting; null for 连词成句

    -- Shared material for listening_true_false (null for non-passage types)
    passage_id          TEXT,                   -- passage group id (e.g. psg_2026_c_001)
    passage_json        TEXT,                   -- JSON Passage object {kind,title,content,audio_url}

    -- Writing-specific fields (null for non-writing types)
    reference_expressions  TEXT,                 -- 参考表达，如 "have difficulty in..."
    min_words             INTEGER,               -- 最低词数要求，如 60

    answer_json         TEXT,                   -- writing: null; single_choice: JSON string "\"B\""; fill-in: JSON list-of-dict
    solution            TEXT,                   -- nullable; filled on demand by Solutioner

    source_md           TEXT NOT NULL,          -- provenance
    source_line         INTEGER NOT NULL,       -- provenance

    stem_hash           TEXT NOT NULL,          -- sha256(stem or original_sentence + options + answer)
    created_at          TIMESTAMP NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_q_type       ON questions(question_type);
CREATE INDEX IF NOT EXISTS idx_q_book       ON questions(book);
CREATE INDEX IF NOT EXISTS idx_q_chapter_l2 ON questions(chapter_l2);
CREATE INDEX IF NOT EXISTS idx_q_stem_hash  ON questions(stem_hash);
CREATE INDEX IF NOT EXISTS idx_q_passage    ON questions(passage_id);

-- ─── question ↔ knowledge_point (many-to-many) ───────────────────
CREATE TABLE IF NOT EXISTS question_knowledge_points (
    question_id         TEXT NOT NULL REFERENCES questions(id),
    knowledge_point_id  TEXT NOT NULL REFERENCES knowledge_points(id),
    PRIMARY KEY (question_id, knowledge_point_id)
);

CREATE INDEX IF NOT EXISTS idx_qkp_kp ON question_knowledge_points(knowledge_point_id);

-- ─── attempts (future FastAPI backend will populate; empty for now) ───
CREATE TABLE IF NOT EXISTS attempts (
    id            TEXT PRIMARY KEY,             -- UUID
    user_id       TEXT NOT NULL,
    paper_id      TEXT NOT NULL,
    answered_at   TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_att_user     ON attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_att_answered ON attempts(answered_at);

CREATE TABLE IF NOT EXISTS attempt_items (
    attempt_id             TEXT NOT NULL REFERENCES attempts(id),
    source_question_id     TEXT NOT NULL,
    question_type          TEXT NOT NULL,
    is_correct             INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    kps_json               TEXT NOT NULL,       -- redundant: KP id list at answer time
    PRIMARY KEY (attempt_id, source_question_id)
);

CREATE INDEX IF NOT EXISTS idx_att_it_source ON attempt_items(source_question_id);
