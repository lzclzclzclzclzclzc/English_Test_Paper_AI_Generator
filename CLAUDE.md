# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this project is

**中考英语 AI 试卷生成系统** (Chinese junior-high English test-paper generator).
A student types a natural-language request (e.g. "来 10 道现在完成时的单选"),
the system retrieves matching questions from a local bank, optionally revises
them with an LLM, and returns a complete paper to answer in the browser.

Core principle: **LLM only does intent-understanding, question-revision and
explanation-generation. The question bank and answer-grading are deterministic
code. Vector retrieval (RAG) bridges the two.**

## Subsystems (dependency order)

| Dir | Role | Status |
|-----|------|--------|
| `ingestion/` | Offline: EPUB → question bank (SQLite + ChromaDB) + vocabulary wordlist build | ✅ done |
| `shared/` | Cross-subsystem contracts (`schemas.py`), `storage.py`, `config.py` | ✅ done — schemas / storage / config / embedding / llm all extracted |
| `ai_engine/` | Parser / Retriever / Reviser / Solutioner / Analyzer / WritingGrader + `pipeline.py` | ✅ done — all modules integrated into `pipeline.py` |
| `backend/` | FastAPI (13 router groups, auth, persistence, grading, **credits ledger + Alipay-sandbox payment** — `services/credits/`, `services/payment/`) | ✅ done |
| `frontend/` | React + Vite (21 user pages + 7 admin pages) | ✅ done — full app: drill system, writing grading UI, vocabulary SRS UI, credits/top-up UI |

> 2026-08-23: the standalone `payment/` service (:8001) and the membership
> model were **removed**. Monetisation is a pure **credits** system (docs/
> `credits-design.md` = Spec P): every paper-generation / AI action charges
> credits server-side (`backend/services/credits`), orders + Alipay sandbox
> live inside the main backend (`/api/payment/*`), and the ledger is in
> `data/app.db`. `payment/data/payment.db` is kept locally only for the
> one-off `backend.cli migrate-payment-db`.

Specs live in `docs/` (`question-bank-ingestion-design.md` = Spec A,
`ai-engine-design.md` = Spec B, plus `backend-design.md`, `frontend-design.md`,
`testing-design.md`, `admin-design.md`, `agent-design.md`, per-question-type
specs (`writing-design.md`, `listening-support-design.md`,
`listening-fill-blank-design.md`, `longtext-support-design.md`,
`reading-first-blank-design.md`), `vocabulary-design.md`, and
`credits-design.md` (Spec P — credits ledger, pricing table, payment merge)). **Specs are kept
aligned with the actual implementation — when you change code that a spec
describes, update the spec too.**

## Data contracts — the most important thing

`shared/schemas.py` is the **single source of truth** for every pydantic model
that crosses a subsystem boundary. All subsystems `from shared import ...`.
Never redefine these types locally. Key reality-driven facts (differ from the
original spec):

- **No `difficulty` field anywhere** — dropped as unreliable/low-value.
- **No paper `score` / `total_score`** — papers vary in length so totals aren't
  comparable; use correctness rate instead.
- `KnowledgePoint` has **no `parent_id`** (flat tree; `level1` IS the parent).
- **`answer` is a union**: single-choice is a bare `str` (`"B"`); fill-in is a
  `list[dict[str, list[str]]]` — a list of candidate blank-groups, e.g.
  `[{"blank1": ["so"], "blank2": ["that"]}]`. Grading = "does user input match
  ANY candidate group" (normalised: lowercase + trim).
- `GenerateRequest.free_text` holds ONLY the leftover semantic topic the
  structured fields can't express ("关于环保"); a pure quota/KP request leaves it
  `""`. The Retriever switches on it: non-empty → vector path, empty → SQL random.
- `RetrievalResult.shortfall` reports per-bucket gaps; the Retriever never
  fabricates questions — the Reviser fills gaps (fresh), honouring
  `revision_intensity`.

## Environment & how to run

- Windows, `bash` shell, Python 3.11+ (dev machine currently 3.13, CPU-only on
  some boxes — code auto-falls-back CUDA→CPU).
- **Always prefix Python commands with `PYTHONIOENCODING=utf-8`** on Windows or
  Chinese output garbles.
- **Run tests with pytest, never `python <file>.py`** (the latter breaks
  `import ai_engine`):
  ```bash
  PYTHONIOENCODING=utf-8 python -m pytest tests/ -v
  ```
- The Qwen embedding model lives at `models/Qwen3-Embedding-4B/` (7.6 GB,
  gitignored). Retrieval's vector path loads it lazily — pure quota requests
  don't touch it.
- **Two SQLite files, split by ownership.** `data/questions.db` is the
  read-only, git-tracked question bank (`questions` / `knowledge_points` /
  `question_knowledge_points`). User data (`users` / `sessions` / `papers` /
  `attempts` / `attempt_items` / `study_plans` / `writing_grade_results` /
  `mindmaps` / the 7 `vocabulary_*` tables / `schema_migrations`) lives in `data/app.db`,
  which is **gitignored** — created fresh by `python -m backend.cli init-db`
  on first run. Bank reads go through `storage.connect_bank()` (env
  `SQLITE_PATH`, `config.db_path`); user reads go through `storage.connect()`
  (env `APP_DB_PATH`, `config.app_db_path`). No query JOINs across the two.
  A third file, `data/agent_sessions.db` (gitignored), holds agent
  conversation history and is separate from both.

### Ingestion CLI (offline bank building)

```bash
python -m ingestion.cli epub-to-md <epub> --slug <book_slug>   # stage 1
python -m ingestion.cli split <book_slug>                       # stage 2
python -m ingestion.cli apply-kp                                # stage 3b
python -m ingestion.cli assign-ids                              # stage 3c
python -m ingestion.cli build-sqlite                            # stage 4 → data/questions.db
python -m ingestion.cli build-vec                               # stage 5 → data/chroma/
python -m ingestion.cli search-vec "query" --qt single_choice   # sanity check
```

Vocabulary wordlist prep (offline, populates `vocabulary_wordlists` /
`vocabulary_words` in `data/app.db`): `ingestion/build_vocabulary_wordlist.py`
and `ingestion/build_merged_vocabulary.py` (national-core + Shanghai-extension
merge). See `docs/vocabulary-design.md`.

## Critical: the question bank is a hand-patched steady state

`data/chapters/*.json` is **NOT** purely regenerable from markdown. It's
"script output + ~100 manual patches" (answer fixes, `<u>` underline markers,
multi-candidate answer structuring, KP merging). **Never re-run `split` to
overwrite the JSON** — it would lose the patches. See Spec A §3.11.

The bank currently holds **1428 questions** across **10 question types**
(`single_choice` 606 / `word_form` 245 / `sentence_rewriting` 215 /
`cloze_single_choice` 126 / `reading_longtext_single_choice` 54 /
`listening_fill_blank` 42 / `listening_true_false` 41 /
`listening_single_choice` 37 / `reading_first_blank` 31 / `writing` 31),
mapped to **56 knowledge points**. Only the 3 free-form types
(`single_choice` / `word_form` / `sentence_rewriting`) get ChromaDB vectors
(`VECTOR_INDEXED_QUESTION_TYPES` in `shared/schemas.py`); everything else is
SQL-only.

## Retriever specifics (the RAG piece)

`ai_engine/retriever.py` does hybrid retrieval — **SQL hard-filter first, then
vector rank within that set** (`collection.get(ids=hard_ids)` + local cosine,
NOT `collection.query()` which under-covers the KP set). Vectors are
L2-normalised so cosine == dot product. See Spec B §4.4 for why.

## Conventions

- Match the surrounding code's comment density and idioms; comments are in
  English, user-facing strings often Chinese.
- Prefer editing specs alongside code (specs track reality here).
- Data/runtime artifacts (`data/`, `models/`, `*.egg-info/`) are gitignored
  except the built `data/questions.db` (question bank, read-only) and
  `data/chroma/` which are committed. `data/app.db` (user/session/paper data)
  is **gitignored** — never committed.
- Git remote is named `main` (not `origin`); branches: `master` / `dev` (integration)
  / per-feature (`retriever`, etc.). Team merges feature branches into `dev` via PR.
