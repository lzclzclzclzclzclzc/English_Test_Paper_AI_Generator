"""Build deterministic, fictional acceptance data for the local application.

The generated database is deliberately separate from ``data/app.db``.  It is
safe to regenerate with ``--reset`` and contains no real-person information.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.auth.password import hash_password
from shared import storage
from shared.schemas import GenerateRequest, Paper, PaperItem, RevisedQuestion
from ai_engine.question_repo import QuestionRepo


DEFAULT_DB = ROOT / "data" / "acceptance-demo.db"
DEFAULT_ACCOUNTS = ROOT / "data" / "acceptance-demo-accounts.csv"
WORDLIST = ROOT / "data" / "vocabulary" / "national-core-plus-shanghai-extension.json"
START = date(2026, 7, 15)
END = date(2026, 9, 5)
PASSWORD = "Demo2026!"
RNG_SEED = 20260905
QUESTION_TYPES = ("single_choice", "word_form", "sentence_rewriting")
EXPECTED_STUDENT_COUNT = 151
EXPECTED_ADMIN_COUNT = 3
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")
MAX_STUDENT_REGISTRATIONS_PER_DAY = 6
ACTIVE_REGISTRATION_DAYS = 44
REGISTRATION_OVERRIDES = {
    date(2026, 8, 27): 3,
    date(2026, 8, 28): 5,
}


@dataclass(frozen=True)
class Persona:
    username: str
    activity: str
    created_on: date
    accuracy: float
    papers: int
    vocabulary_words: int
    role: str = "user"


STUDENT_NAMES = (
    "OliviaStudy", "EthanReads", "AvaLearns", "LiamWrites", "EmmaQuizzes",
    "NoahGrammar", "SophiaBooks", "MasonNotes", "IsabellaWords", "LucasPaper",
    "MiaReader", "HenryEssay", "AmeliaVocab", "JamesPractice", "HarperLesson",
    "BenjaminReview", "EvelynEnglish", "AlexanderStudy", "EllaReads", "DanielWrites",
    "ScarlettQuiz", "MichaelGrammar", "GraceBooks", "SebastianNotes", "ChloeWords",
    "JackPaper", "VictoriaReader", "OwenEssay", "RileyVocab", "WyattPractice",
    "AriaLesson", "LeoReview", "NoraEnglish", "JulianStudy", "ZoeyReads",
    "HudsonWrites", "LilyQuiz", "EzraGrammar", "HazelBooks", "MateoNotes",
    "LaylaWords", "CarterPaper", "EllieReader", "IsaacEssay", "VioletVocab",
    "GabrielPractice", "AuroraLesson", "AnthonyReview", "LucyEnglish", "DylanStudy",
    "ClaireReads", "LincolnWrites", "StellaQuiz", "ThomasGrammar", "NatalieBooks",
    "CharlesNotes", "AliceWords", "ChristopherPaper", "MayaReader", "JosiahEssay",
    "PenelopeVocab", "AndrewPractice", "RubyLesson", "JoshuaReview", "IslaEnglish",
    "NathanStudy", "IvyReads", "CalebWrites", "SadieQuiz", "RyanGrammar",
    "ElenaBooks", "AdrianNotes", "LillianWords", "ConnorPaper", "BellaReader",
    "AaronEssay", "SkylarVocab", "ChristianPractice", "PaisleyLesson", "JonathanReview",
    "TaylorStudy", "MorganReads", "JordanLearns", "CaseyWrites", "CameronQuiz",
    "RowanGrammar", "PeytonBooks", "AveryNotes", "DakotaWords", "QuinnPaper",
    "BlakeReader", "ReeseEssay", "KendallVocab", "ParkerPractice", "BaileyLesson",
    "FinleyReview", "SloaneEnglish", "EmersonStudy", "LoganReads", "HaydenWrites",
    "SydneyQuiz", "MarleyGrammar", "ReaganBooks", "BrookeNotes", "CallieWords",
    "SummerPaper", "TessaReader", "PaigeEssay", "WillaVocab", "FionaPractice",
    "GeorgiaLesson", "VioletReview", "MadelineEnglish", "DaphneStudy", "CoraReads",
    "GemmaWrites", "FreyaQuiz", "SelenaGrammar", "NaomiBooks", "PhoebeNotes",
    "mila_notes", "oliver_reads", "emma_studies", "noah_writes", "sophia_quiz",
    "lucas_grammar", "ava_books", "ethan_paper", "mia_reader", "james_essay",
    "harper_vocab", "ben_practice", "lily_lessons", "leo_review", "nora_english",
    "aria_study", "owen_reads", "chloe_writes", "jack_quiz", "grace_grammar",
    "Oliver23", "Emma48", "StudyMia7", "NoahReads9", "Ava2026", "LiamStudy12",
    "Sophia8", "MasonNotes5", "EllaReader27", "HenryQuiz3", "Chloe2026",
)


def _registration_days() -> list[date]:
    """Return a fixed, non-uniform student registration schedule."""
    days = [START + timedelta(days=offset) for offset in range((END - START).days + 1)]
    if not set(REGISTRATION_OVERRIDES).issubset(days):
        raise RuntimeError("registration overrides must be inside the acceptance range")
    if ACTIVE_REGISTRATION_DAYS > len(days) or ACTIVE_REGISTRATION_DAYS < len(REGISTRATION_OVERRIDES):
        raise RuntimeError("invalid active registration day count")

    rng = random.Random(RNG_SEED + EXPECTED_STUDENT_COUNT)
    counts = {day: 0 for day in days}
    counts.update(REGISTRATION_OVERRIDES)
    candidates = [day for day in days if day not in REGISTRATION_OVERRIDES]
    active_days = rng.sample(candidates, ACTIVE_REGISTRATION_DAYS - len(REGISTRATION_OVERRIDES))
    for day in active_days:
        counts[day] = 1

    remaining = EXPECTED_STUDENT_COUNT - sum(counts.values())
    while remaining:
        available = [day for day in active_days if counts[day] < MAX_STUDENT_REGISTRATIONS_PER_DAY]
        if not available:
            raise RuntimeError("registration schedule cannot satisfy the student count")
        counts[rng.choice(available)] += 1
        remaining -= 1

    scheduled = [day for day in days for _ in range(counts[day])]
    if len(scheduled) != EXPECTED_STUDENT_COUNT or not any(count == 0 for count in counts.values()):
        raise RuntimeError("registration schedule is incomplete")
    if max(counts.values()) > MAX_STUDENT_REGISTRATIONS_PER_DAY:
        raise RuntimeError("registration schedule exceeds the daily limit")
    return scheduled


def _personas() -> list[Persona]:
    people: list[Persona] = []
    groups = (
        ("high", 40, 0.80, 9, 100),
        ("steady", 56, 0.62, 6, 55),
        ("light", 35, 0.45, 3, 22),
        ("new", 20, 0.56, 1, 8),
    )
    expected_students = sum(count for _, count, *_ in groups)
    if len(STUDENT_NAMES) != expected_students or expected_students != EXPECTED_STUDENT_COUNT:
        raise RuntimeError("student username list does not match the configured activity groups")
    if len(set(STUDENT_NAMES)) != len(STUDENT_NAMES):
        raise RuntimeError("student usernames must be unique")
    invalid_names = [username for username in STUDENT_NAMES if not USERNAME_PATTERN.fullmatch(username)]
    if invalid_names:
        raise RuntimeError(f"student usernames do not meet account validation: {invalid_names}")
    registration_days = _registration_days()
    cursor = 0
    for activity, count, accuracy, papers, words in groups:
        for offset in range(count):
            index = cursor + offset
            created = registration_days[index]
            people.append(Persona(STUDENT_NAMES[index], activity, created, accuracy, papers, words))
        cursor += count
    people.extend((
        Persona("admin_zhou", "admin", START, 0.78, 4, 35, "admin"),
        Persona("admin_li", "admin", START + timedelta(days=3), 0.72, 3, 28, "admin"),
        Persona("admin_wang", "admin", START + timedelta(days=6), 0.75, 3, 30, "admin"),
    ))
    if sum(person.role == "admin" for person in people) != EXPECTED_ADMIN_COUNT:
        raise RuntimeError("admin account list does not match the expected count")
    return people


def _timestamp(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def _day_for(index: int, total: int) -> date:
    span = (END - START).days
    return START + timedelta(days=(index * span) // max(total - 1, 1))


def _clear_existing(path: Path, accounts_path: Path) -> None:
    if path.exists():
        path.unlink()
    if accounts_path.exists():
        accounts_path.unlink()


def _question_catalog() -> dict[str, list[str]]:
    repo = QuestionRepo(ROOT / "data" / "questions.db")
    catalog = {kind: repo.filter_ids(question_types=[kind]) for kind in QUESTION_TYPES}
    missing = [kind for kind, ids in catalog.items() if not ids]
    if missing:
        raise RuntimeError(f"question bank has no usable questions for: {', '.join(missing)}")
    return catalog


def _build_paper(repo: QuestionRepo, catalog: dict[str, list[str]], persona: Persona, seq: int, generated_at: datetime) -> tuple[Paper, list]:
    pattern = ("single_choice", "single_choice", "single_choice", "word_form", "word_form", "sentence_rewriting")
    ids = [catalog[kind][(seq * 11 + pos * 7) % len(catalog[kind])] for pos, kind in enumerate(pattern)]
    source = repo.get_by_ids(ids)
    questions = [source[item_id] for item_id in ids]
    distribution = {kind: pattern.count(kind) for kind in QUESTION_TYPES}
    request = GenerateRequest(
        mode="fresh", total_questions=len(questions), question_types=list(QUESTION_TYPES),
        type_distribution=distribution, revision_intensity="original", user_id=persona.username,
    )
    items = [
        PaperItem(index=index, source_question_id=question.id, revision_mode="original",
                  question=RevisedQuestion.model_validate(question.model_dump()))
        for index, question in enumerate(questions, start=1)
    ]
    paper = Paper(
        paper_id=f"acceptance-paper-{persona.username}-{seq:03d}",
        title=f"暑期英语巩固练习 · 第 {seq + 1} 组",
        generated_at=generated_at,
        request=request,
        items=items,
        metadata={"seed": "acceptance-demo", "activity": persona.activity},
    )
    return paper, questions


def _insert_papers_and_attempts(conn: sqlite3.Connection, rng: random.Random, personas: list[Persona]) -> tuple[int, int]:
    repo = QuestionRepo(ROOT / "data" / "questions.db")
    catalog = _question_catalog()
    paper_total = attempt_total = 0
    for user_index, persona in enumerate(personas):
        for seq in range(persona.papers):
            day = _day_for(user_index * 9 + seq, len(personas) * 9)
            if user_index == len(personas) - 1 and seq == persona.papers - 1:
                day = END
            generated_at = _timestamp(day, 9 + (seq % 6), 10)
            paper, questions = _build_paper(repo, catalog, persona, seq, generated_at)
            submitted = seq < max(1, round(persona.papers * (0.89 if persona.activity in {"high", "steady", "admin"} else 0.65)))
            submitted_at = generated_at + timedelta(minutes=18 + seq * 2) if submitted else None
            conn.execute(
                "INSERT INTO papers (paper_id, user_id, title, generated_at, payload_json, submitted, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (paper.paper_id, persona.username, paper.title, generated_at.isoformat(), paper.model_dump_json(), int(submitted), submitted_at.isoformat() if submitted_at else None),
            )
            paper_total += 1
            if not submitted:
                continue
            attempt_id = f"acceptance-attempt-{persona.username}-{seq:03d}"
            conn.execute("INSERT INTO attempts (id, user_id, paper_id, answered_at) VALUES (?, ?, ?, ?)",
                         (attempt_id, persona.username, paper.paper_id, submitted_at.isoformat()))
            for item_index, question in enumerate(questions, start=1):
                # Make the displayed mastery profile differ across personas and question types.
                adjustment = {"single_choice": 0.05, "word_form": -0.06, "sentence_rewriting": -0.12}[question.question_type]
                correct = int(rng.random() < max(0.08, min(0.94, persona.accuracy + adjustment)))
                user_answer = json.dumps(question.answer if correct else "未掌握", ensure_ascii=False)
                conn.execute(
                    "INSERT INTO attempt_items (attempt_id, item_index, source_question_id, question_type, is_correct, kps_json, user_answer_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (attempt_id, item_index, question.id, question.question_type, correct,
                     json.dumps(question.knowledge_point_ids, ensure_ascii=False), user_answer),
                )
            attempt_total += 1
    return paper_total, attempt_total


def _insert_vocabulary(conn: sqlite3.Connection, rng: random.Random, personas: list[Persona]) -> int:
    word_ids = [row[0] for row in conn.execute("SELECT id FROM vocabulary_words WHERE is_active = 1 ORDER BY id")]
    if not word_ids:
        raise RuntimeError("vocabulary wordlist was not seeded")
    logs = 0
    for user_index, persona in enumerate(personas):
        conn.execute("INSERT INTO vocabulary_settings (user_id, daily_new_limit) VALUES (?, ?)",
                     (persona.username, 20 if persona.activity != "high" else 30))
        count = persona.vocabulary_words
        for position, word_id in enumerate(word_ids[(user_index * 37) % len(word_ids):] + word_ids[:(user_index * 37) % len(word_ids)]):
            if position >= count:
                break
            introduced = START + timedelta(days=(position * 3 + user_index) % ((END - START).days + 1))
            stage = 5 if position % 9 == 0 else 3 if position % 3 == 0 else 1 + position % 3
            review_count = stage + 1 + position % 3
            last_reviewed = min(END, introduced + timedelta(days=max(0, review_count - 1)))
            due = last_reviewed + timedelta(days=storage.VOCABULARY_INTERVALS[stage - 1])
            conn.execute(
                "INSERT INTO vocabulary_progress (user_id, word_id, stage, introduced_at, last_reviewed_at, due_at, review_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (persona.username, word_id, stage, _timestamp(introduced, 8).isoformat(), _timestamp(last_reviewed, 20).isoformat(), _timestamp(due, 8).isoformat(), review_count),
            )
            for review in range(min(review_count, 4)):
                reviewed = min(END, introduced + timedelta(days=review))
                rating = "known" if review or position % 5 else "fuzzy"
                conn.execute(
                    "INSERT INTO vocabulary_review_logs (id, user_id, word_id, reviewed_at, spelling_correct, requested_rating, applied_rating, stage_after, next_due_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"vlog-{persona.username}-{position:03d}-{review}", persona.username, word_id,
                     _timestamp(reviewed, 19, review).isoformat(), int(rating == "known"), rating, rating,
                     min(stage, review + 1), _timestamp(reviewed + timedelta(days=1), 8).isoformat()),
                )
                logs += 1
        # Current-day cards make the vocabulary screens useful immediately; some retain an open retry.
        study_day = date(2026, 8, 14)
        start_index = (user_index * 37) % len(word_ids)
        for offset in range(6):
            word_id = word_ids[(start_index + offset) % len(word_ids)]
            completed = None if offset == 5 else _timestamp(study_day, 18, offset).isoformat()
            conn.execute("INSERT OR IGNORE INTO vocabulary_daily_cards (user_id, study_date, word_id, card_type, completed_at) VALUES (?, ?, ?, ?, ?)",
                         (persona.username, study_day.isoformat(), word_id, "review" if offset < 2 else "new", completed))
        if user_index % 4 == 0:
            word_id = word_ids[(start_index + 5) % len(word_ids)]
            conn.execute("INSERT OR IGNORE INTO vocabulary_daily_retry_queue (user_id, study_date, word_id, first_rating, last_rating, retry_count, queue_order, passed_at) VALUES (?, ?, ?, 'fuzzy', 'fuzzy', 1, 1, NULL)",
                         (persona.username, study_day.isoformat(), word_id))
    return logs


def _write_accounts(path: Path, personas: list[Persona]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["username", "password", "role", "activity", "created_on"])
        writer.writeheader()
        for person in personas:
            writer.writerow({"username": person.username, "password": PASSWORD, "role": person.role,
                             "activity": person.activity, "created_on": person.created_on.isoformat()})


def seed_database(db_path: Path, accounts_path: Path, *, reset: bool = False) -> dict[str, int]:
    if db_path.exists() and not reset:
        raise FileExistsError(f"{db_path} already exists; rerun with --reset to replace it")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if reset:
        _clear_existing(db_path, accounts_path)
    storage.set_db_path(db_path)
    try:
        storage.init_db()
        storage.seed_vocabulary_from_json(WORDLIST)
        personas = _personas()
        password_hash = hash_password(PASSWORD)
        rng = random.Random(RNG_SEED)
        with storage.connect() as conn:
            for person in personas:
                conn.execute("INSERT INTO users (id, username, password_hash, created_at, role, status) VALUES (?, ?, ?, ?, ?, 'active')",
                             (person.username, person.username, password_hash, _timestamp(person.created_on, 9).isoformat(), person.role))
            papers, attempts = _insert_papers_and_attempts(conn, rng, personas)
            logs = _insert_vocabulary(conn, rng, personas)
        _write_accounts(accounts_path, personas)
        return {"users": len(personas), "admins": sum(person.role == "admin" for person in personas), "papers": papers, "attempts": attempts, "vocabulary_logs": logs}
    finally:
        storage.set_db_path(None)


def verify_database(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        logs = conn.execute("SELECT COUNT(*) FROM vocabulary_review_logs").fetchone()[0]
        unique_usernames = conn.execute("SELECT COUNT(DISTINCT username) FROM users").fetchone()[0]
        usernames = [row[0] for row in conn.execute("SELECT username FROM users")]
        start, end = conn.execute("SELECT MIN(generated_at), MAX(generated_at) FROM papers").fetchone()
        attempt_start, attempt_end = conn.execute("SELECT MIN(answered_at), MAX(answered_at) FROM attempts").fetchone()
        review_start, review_end = conn.execute("SELECT MIN(reviewed_at), MAX(reviewed_at) FROM vocabulary_review_logs").fetchone()
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        invalid_usernames = [username for username in usernames if not USERNAME_PATTERN.fullmatch(username)]
        registration_counts = Counter({date.fromisoformat(day): count for day, count in conn.execute(
            "SELECT substr(created_at, 1, 10), COUNT(*) FROM users WHERE role = 'user' GROUP BY substr(created_at, 1, 10)"
        )})
        expected_registration_counts = Counter(_registration_days())
        if (users, admins) != (EXPECTED_STUDENT_COUNT + EXPECTED_ADMIN_COUNT, EXPECTED_ADMIN_COUNT) or users != unique_usernames or invalid_usernames or not papers or not attempts or not logs:
            raise RuntimeError("acceptance database is incomplete")
        if registration_counts != expected_registration_counts:
            raise RuntimeError("student registration distribution is incomplete")
        if any(count > MAX_STUDENT_REGISTRATIONS_PER_DAY for count in registration_counts.values()):
            raise RuntimeError("student registration distribution exceeds the daily limit")
        if registration_counts[date(2026, 8, 27)] != 3 or registration_counts[date(2026, 8, 28)] != 5:
            raise RuntimeError("student registration distribution is missing the required daily variation")
        if start[:10] != START.isoformat() or end[:10] != END.isoformat():
            raise RuntimeError("paper timestamps are outside the acceptance range")
        if attempt_start[:10] != START.isoformat() or attempt_end[:10] != END.isoformat():
            raise RuntimeError("attempt timestamps are outside the acceptance range")
        if review_start[:10] != START.isoformat() or review_end[:10] != END.isoformat():
            raise RuntimeError("vocabulary timestamps are outside the acceptance range")
        if fk_errors:
            raise RuntimeError(f"foreign-key validation failed: {fk_errors[:3]}")
        return {"users": users, "admins": admins, "papers": papers, "attempts": attempts, "vocabulary_logs": logs}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fictional acceptance data for July 15 to September 5, 2026.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="target app database (default: data/acceptance-demo.db)")
    parser.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS, help="generated credentials CSV")
    parser.add_argument("--reset", action="store_true", help="replace an existing target database")
    parser.add_argument("--verify", action="store_true", help="verify an existing database without writing data")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_database(args.db), ensure_ascii=False))
        return
    result = seed_database(args.db, args.accounts, reset=args.reset)
    print(json.dumps(result, ensure_ascii=False))
    print(f"database: {args.db}")
    print(f"accounts: {args.accounts}")


if __name__ == "__main__":
    main()
