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
| `ingestion/` | Offline: EPUB → question bank (SQLite + ChromaDB) | ✅ done |
| `shared/` | Cross-subsystem contracts (`schemas.py`) | schemas done; storage/embedding/config/llm not yet extracted |
| `ai_engine/` | Parser / Retriever / Reviser / Solutioner / Analyzer + `pipeline.py` | Retriever + pipeline done; Parser/Reviser in progress; Analyzer/Solutioner not started |
| `backend/` | FastAPI (11 endpoints, auth, persistence, grading) | not started |
| `frontend/` | React + Vite (3 pages) | static demo only |

Specs live in `docs/` (`question-bank-ingestion-design.md` = Spec A,
`ai-engine-design.md` = Spec B, plus backend/frontend/testing). **Specs are kept
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

## Critical: the question bank is a hand-patched steady state

`data/chapters/*.json` is **NOT** purely regenerable from markdown. It's
"script output + ~100 manual patches" (answer fixes, `<u>` underline markers,
multi-candidate answer structuring, KP merging). **Never re-run `split` to
overwrite the JSON** — it would lose the patches. See Spec A §3.11.

The bank currently holds **1066 questions** (2 Shanghai 2021 mock books) across
`single_choice` / `word_form` / `sentence_rewriting`, mapped to **49 knowledge
points**.

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
  except the built `data/questions.db` and `data/chroma/` which are committed.
- Git remote is named `main` (not `origin`); branches: `master` / `dev` (integration)
  / per-feature (`retriever`, etc.). Team merges feature branches into `dev` via PR.
