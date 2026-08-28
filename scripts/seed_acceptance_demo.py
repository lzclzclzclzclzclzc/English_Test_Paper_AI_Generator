"""Deterministic fictional data for local acceptance demonstrations."""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.question_repo import QuestionRepo
from backend.auth.password import hash_password
from backend.services.credits.pricing import PRICES, price
from backend.services.payment.packs import PACKS
from shared import storage
from shared.schemas import GenerateRequest, Paper, PaperItem, RevisedQuestion

DEFAULT_DB = ROOT / "data" / "acceptance-demo.db"
DEFAULT_ACCOUNTS = ROOT / "data" / "acceptance-demo-accounts.csv"
WORDLIST = ROOT / "data" / "vocabulary" / "national-core-plus-shanghai-extension.json"
START, END = date(2026, 7, 15), date(2026, 8, 31)
PASSWORD, RNG_SEED = "Demo2026!", 20260831
QUESTION_TYPES = ("single_choice", "word_form", "sentence_rewriting")
EXPECTED_STUDENT_COUNT, EXPECTED_ADMIN_COUNT = 1091, 3
# 502 / 1091 = 46.01%; the dashboard rounds this to a 46% paid-user ratio.
EXPECTED_PAID_STUDENT_COUNT = 502
EXPECTED_AUDIT_LOG_COUNT = 42
SHOWCASE_USERNAME = "jingyi_29"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")
REGISTRATION_OVERRIDES = {date(2026, 8, 27): 3, date(2026, 8, 28): 5}
PAPER_ACTIONS = ("generate_original", "generate_light", "generate_fresh", "revise_paper")
PAPER_SOURCES = ("generate", "dashboard", "daily", "themes", "custom", "mock", "mastery_review", "errorbook", "agent", "study_plan", "drill:grammar")
INTENSITY = {"generate_original": "original", "generate_light": "light", "generate_fresh": "fresh", "revise_paper": "fresh"}
VOCAB_PER_DAY = {"high": 8, "steady": 5, "light": 3, "new": 2, "admin": 4}
FIRST_NAMES = ("Olivia", "Ethan", "Ava", "Liam", "Emma", "Noah", "Sophia", "Mason", "Isabella", "Lucas", "Mia", "Henry", "Amelia", "James", "Harper", "Benjamin", "Evelyn", "Alexander", "Ella", "Daniel", "Scarlett", "Michael", "Grace", "Sebastian", "Chloe", "Jack", "Victoria", "Owen", "Riley", "Wyatt", "Aria", "Leo", "Nora", "Julian", "Zoey", "Hudson", "Lily", "Ezra", "Hazel", "Mateo", "Layla", "Carter", "Ellie", "Isaac", "Violet", "Gabriel", "Aurora", "Anthony", "Lucy", "Dylan", "Claire", "Lincoln", "Stella", "Thomas", "Natalie", "Charles", "Alice", "Christopher", "Maya", "Josiah")
SURNAMES = ("Bennett", "Holloway", "Whitaker", "Marlowe", "Everett", "Langford", "Sullivan", "Hawthorne", "Kensington", "Calloway", "Waverly", "Ashford", "Briarwood", "Fairmont", "Northwood", "Westbrook", "Alderidge", "Rosemont", "Bellamy", "Kingsley")
PINYIN_SURNAMES = ("zhang", "wang", "li", "chen", "liu", "yang", "huang", "zhou", "wu", "xu", "sun", "zhao", "lin", "he", "gao", "luo", "tang", "feng", "peng", "cao", "guo", "ma", "han", "xie")
PINYIN_GIVEN_NAMES = ("xiaoyu", "zihao", "yiran", "wenxin", "haoran", "jingyi", "zihan", "yutong", "xinyue", "leilei", "tianyu", "ruoxi", "anran", "mingze", "yuxuan", "lingxi", "moyu", "jiaqi", "yichen", "xiaoran", "chenxi", "yining", "yuhang", "zixuan", "qianqian", "xinyi", "yuqing", "yifan", "kexin", "yutian")
NICK_ROOTS = ("bookworm", "studyfox", "paperplane", "grammarlab", "quietowl", "vocabtrail", "mangonotes", "bluepencil", "quizharbor", "readingstar", "wordcraft", "campuscat", "dailydose", "softcloud", "maplepage", "tinylamp", "notebooker", "sunnydesk", "cleverleaf", "mintstudy", "coffeepage")

@dataclass(frozen=True)
class Persona:
    username: str
    activity: str
    created_on: date
    accuracy: float
    role: str = "user"
    status: str = "active"

@dataclass(frozen=True)
class Spend:
    user_id: str
    action: str
    amount: int
    when: datetime
    ref_type: str
    ref_id: str

def ts(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)

def days_from(start: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((END - start).days + 1)]

def student_names() -> list[str]:
    rng = random.Random(RNG_SEED + 17)
    english_plain = [f"{first}{surname}" for first in FIRST_NAMES for surname in SURNAMES]
    pinyin_plain = [f"{surname}{given}" for surname in PINYIN_SURNAMES for given in PINYIN_GIVEN_NAMES]
    english_underscore = [f"{first.lower()}_{surname.lower()}" for first in FIRST_NAMES for surname in SURNAMES]
    pinyin_mixed = [
        f"{surname}_{given}{7 + (index * 13) % 83}" if index % 3 == 0 else f"{given}_{7 + (index * 13) % 83}"
        for index, (surname, given) in enumerate((surname, given) for surname in PINYIN_SURNAMES for given in PINYIN_GIVEN_NAMES)
    ]
    nickname_mixed = [
        root if index % 12 == 0 else f"{root}_{3 + (index * 11) % 87}" if index % 3 == 0 else f"{root}{3 + (index * 11) % 87}"
        for index, root in enumerate(root for root in NICK_ROOTS for _ in range(12))
    ]
    names = (
        rng.sample(english_plain, 380)
        + rng.sample(pinyin_plain, 270)
        + rng.sample(english_underscore, 120)
        + rng.sample(pinyin_mixed, 180)
        + rng.sample(nickname_mixed, 141)
    )
    rng.shuffle(names)
    if len(names) != len(set(names)) or any(not USERNAME_PATTERN.fullmatch(name) for name in names):
        raise RuntimeError("invalid fictional usernames")
    return names

def registration_days() -> list[date]:
    all_days = days_from(START)
    rng = random.Random(RNG_SEED + EXPECTED_STUDENT_COUNT)
    counts = {day: 0 for day in all_days}
    counts.update(REGISTRATION_OVERRIDES)
    active = rng.sample([day for day in all_days if day not in counts or day not in REGISTRATION_OVERRIDES], 40)
    for day in active:
        counts[day] = 12
    remaining = EXPECTED_STUDENT_COUNT - sum(counts.values())
    while remaining:
        choices = [day for day in active if counts[day] < 45]
        if not choices:
            raise RuntimeError("registration capacity exhausted")
        counts[rng.choice(choices)] += 1
        remaining -= 1
    result = [day for day in all_days for _ in range(counts[day])]
    if len(result) != EXPECTED_STUDENT_COUNT or sum(value == 0 for value in counts.values()) != 6:
        raise RuntimeError("invalid registration schedule")
    return result

def personas() -> list[Persona]:
    groups = (("high", 270, .80), ("steady", 410, .64), ("light", 270, .48), ("new", 141, .57))
    names, created = student_names(), registration_days()
    people: list[Persona] = []
    cursor = 0
    for activity, count, accuracy in groups:
        for offset in range(count):
            index = cursor + offset
            people.append(Persona(names[index], activity, created[index], accuracy, status="banned" if index and index % 173 == 0 else "active"))
        cursor += count
    people += [Persona("admin_zhou", "admin", START, .79, "admin"), Persona("admin_li", "admin", START + timedelta(days=3), .74, "admin"), Persona("admin_wang", "admin", START + timedelta(days=6), .76, "admin")]
    return people

def clear(path: Path, accounts: Path) -> None:
    if path.exists(): path.unlink()
    if accounts.exists(): accounts.unlink()

def catalog() -> dict[str, list[str]]:
    repo = QuestionRepo(ROOT / "data" / "questions.db")
    result = {kind: repo.filter_ids(question_types=[kind]) for kind in QUESTION_TYPES}
    if any(not ids for ids in result.values()): raise RuntimeError("question bank is incomplete")
    return result

def paper_days(person: Persona, user_index: int) -> list[date]:
    result, day, seq = [], person.created_on, 0
    while day <= END:
        result.append(day)
        day += timedelta(days=2 if (user_index + seq) % 2 == 0 else 3)
        seq += 1
    return result

def add_spend(events: list[Spend], user: str, action: str, when: datetime, ref_type: str, ref_id: str, units: int = 0) -> None:
    events.append(Spend(user, action, price(action, units), when, ref_type, ref_id))

def insert_learning(conn: sqlite3.Connection, rng: random.Random, people: list[Persona]) -> tuple[int, int, int, list[Spend], list[tuple[str, str, datetime]]]:
    repo, ids = QuestionRepo(ROOT / "data" / "questions.db"), catalog()
    papers = attempts = logs = 0
    events: list[Spend] = []
    submitted: list[tuple[str, str, datetime]] = []
    pattern = ("single_choice", "single_choice", "single_choice", "word_form", "word_form", "sentence_rewriting")
    for user_index, person in enumerate(people):
        for seq, day in enumerate(paper_days(person, user_index)):
            action, source = PAPER_ACTIONS[(user_index + seq) % 4], PAPER_SOURCES[(user_index * 3 + seq) % len(PAPER_SOURCES)]
            mode = ("fresh", "remediation", "review")[(user_index + seq) % 3]
            question_ids = [ids[kind][(seq * 11 + position * 7) % len(ids[kind])] for position, kind in enumerate(pattern)]
            records = repo.get_by_ids(question_ids)
            questions = [records[question_id] for question_id in question_ids]
            generated = ts(day, 9 + seq % 6, 10)
            request = GenerateRequest(mode=mode, total_questions=6, question_types=list(QUESTION_TYPES), type_distribution={kind: pattern.count(kind) for kind in QUESTION_TYPES}, revision_intensity=INTENSITY[action], user_id=person.username)
            paper_id = f"acceptance-paper-{person.username}-{seq:03d}"
            paper = Paper(paper_id=paper_id, title=f"暑期英语巩固练习 · 第 {seq + 1} 组", generated_at=generated, request=request, items=[PaperItem(index=i, source_question_id=q.id, revision_mode=INTENSITY[action], question=RevisedQuestion.model_validate(q.model_dump())) for i, q in enumerate(questions, 1)], metadata={"seed": "acceptance-demo", "activity": person.activity, "source": source, "generation_action": action})
            done = seq == 0 or rng.random() < .90
            answered = generated + timedelta(minutes=18 + seq % 20) if done else None
            conn.execute("INSERT INTO papers (paper_id,user_id,title,generated_at,payload_json,submitted,submitted_at) VALUES (?,?,?,?,?,?,?)", (paper_id, person.username, paper.title, generated.isoformat(), paper.model_dump_json(), int(done), answered.isoformat() if answered else None))
            add_spend(events, person.username, action, generated, "paper", paper_id, 6)
            papers += 1
            if done:
                attempt_id, wrong = f"acceptance-attempt-{person.username}-{seq:03d}", None
                conn.execute("INSERT INTO attempts (id,user_id,paper_id,answered_at) VALUES (?,?,?,?)", (attempt_id, person.username, paper_id, answered.isoformat()))
                for item, question in enumerate(questions, 1):
                    correct = int(rng.random() < max(.08, min(.94, person.accuracy + {"single_choice": .05, "word_form": -.06, "sentence_rewriting": -.12}[question.question_type])))
                    wrong = wrong or (None if correct else question.id)
                    conn.execute("INSERT INTO attempt_items (attempt_id,item_index,source_question_id,question_type,is_correct,kps_json,user_answer_json) VALUES (?,?,?,?,?,?,?)", (attempt_id, item, question.id, question.question_type, correct, json.dumps(question.knowledge_point_ids), json.dumps(question.answer if correct else "未掌握")))
                if wrong and (user_index + seq) % 3 == 0: add_spend(events, person.username, "solution", answered + timedelta(minutes=2), "solution", f"{attempt_id}:{wrong}")
                submitted.append((person.username, paper_id, answered)); attempts += 1
        conn.execute("INSERT INTO vocabulary_settings (user_id,daily_new_limit) VALUES (?,?)", (person.username, 30 if person.activity == "high" else 20))
        word_ids = [row[0] for row in conn.execute("SELECT id FROM vocabulary_words WHERE is_active=1 ORDER BY id")]
        for day_index, day in enumerate(days_from(person.created_on)):
            for slot in range(VOCAB_PER_DAY[person.activity]):
                word_id = word_ids[(user_index * 53 + day_index * VOCAB_PER_DAY[person.activity] + slot) % len(word_ids)]
                stage, completed = (5 if (day_index + slot) % 11 == 0 else 3), ts(day, 18, slot).isoformat()
                conn.execute("INSERT OR IGNORE INTO vocabulary_progress (user_id,word_id,stage,introduced_at,last_reviewed_at,due_at,review_count) VALUES (?,?,?,?,?,?,?)", (person.username, word_id, stage, ts(day, 8).isoformat(), ts(day, 20).isoformat(), ts(min(END, day + timedelta(days=stage)), 8).isoformat(), stage))
                conn.execute("INSERT INTO vocabulary_daily_cards (user_id,study_date,word_id,card_type,completed_at) VALUES (?,?,?,?,?)", (person.username, day.isoformat(), word_id, "new" if day_index < 2 or slot == 0 else "review", completed))
                conn.execute("INSERT INTO vocabulary_review_logs (id,user_id,word_id,reviewed_at,spelling_correct,requested_rating,applied_rating,stage_after,next_due_at) VALUES (?,?,?,?,1,'known','known',?,?)", (f"vlog-{person.username}-{day:%Y%m%d}-{slot}", person.username, word_id, completed, stage, ts(min(END, day + timedelta(days=1)), 8).isoformat()))
                logs += 1
            if day_index % 9 == 0: add_spend(events, person.username, "vocab_example", ts(day, 20), "vocab_word", f"{person.username}:{day}:example")
    return papers, attempts, logs, events, submitted

def insert_writing_and_agent(conn: sqlite3.Connection, rng: random.Random, people: list[Persona], submitted: list[tuple[str, str, datetime]]) -> list[Spend]:
    events: list[Spend] = []
    for index, (user, paper, when) in enumerate(submitted):
        if index % 11: continue
        score = round(60 + rng.random() * 32, 1); content = round(score * .36, 1); language = round(score * .34, 1)
        conn.execute("INSERT INTO writing_grade_results (id,user_id,paper_id,item_index,user_essay,total_score,content_score,language_score,organization_score,word_count,level,content_analysis,language_analysis,organization_analysis,overall_comment,revised_version,graded_at) VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"demo-writing-{index:05d}", user, paper, "Fictional acceptance writing sample.", score, content, language, round(score-content-language,1), 120 + index % 160, "A" if score >= 75 else "B", "内容完整。", "表达准确。", "结构清晰。", "验收用虚构批改。", "Fictional revision.", when.isoformat()))
        add_spend(events, user, "writing_grade", when, "writing", paper)
    for index, person in enumerate(people):
        for seq in range(3 if index < 10 else 1 + int(index % 5 == 0)):
            add_spend(events, person.username, "agent_message", ts(min(END, person.created_on + timedelta(days=seq * 9 + index % 4)), 21, seq), "agent", f"{person.username}:{seq}")
    return events

def insert_jingyi_showcase(conn: sqlite3.Connection) -> None:
    """Give one high-activity learner a coherent, inspectable acceptance story."""
    paper_specs = (
        (0, "暑期英语诊断卷：词汇与时态", "从基础时态和高频词汇开始复盘"),
        (5, "非谓语动词与句型转换专项卷", "集中巩固不定式、动名词和被动语态"),
        (8, "阶段复盘卷：阅读与书面表达", "阅读信息提取与书面表达同步训练"),
        (12, "定语从句与阅读理解巩固卷", "梳理关系词选择和长难句理解"),
        (14, "应用文写作表达训练", "练习邮件与活动通知中的衔接表达"),
        (17, "开学前英语综合自测", "根据错题回顾暑期薄弱知识点"),
    )
    paper_titles: dict[int, str] = {}
    for sequence, title, focus in paper_specs:
        paper_id = f"acceptance-paper-{SHOWCASE_USERNAME}-{sequence:03d}"
        row = conn.execute("SELECT payload_json FROM papers WHERE paper_id=? AND user_id=?", (paper_id, SHOWCASE_USERNAME)).fetchone()
        if row is None:
            raise RuntimeError("showcase paper is missing")
        payload = json.loads(row[0])
        payload["title"] = title
        payload.setdefault("metadata", {}).update({"showcase": True, "learning_focus": focus})
        conn.execute("UPDATE papers SET title=?, payload_json=? WHERE paper_id=?", (title, json.dumps(payload, ensure_ascii=False), paper_id))
        paper_titles[sequence] = title

    writing_rows = (
        (0, "Last Saturday, I joined a school reading activity in the library. I chose a book about space and shared three new words with my classmates. The activity made me more confident about reading English every day.", 82.5, 30.0, 28.5, 24.0, "A", "内容完整，活动经过交代清楚。", "时态使用基本准确，可增加连接词。", "段落层次清晰。", "继续积累活动类表达，如 take part in 和 share with。"),
        (5, "Dear Mike, I am writing to invite you to our English corner this Friday. We will discuss summer plans and play a word guessing game. It starts at 4 p.m. in Room 302. I hope you can join us.", 86.0, 31.5, 30.0, 24.5, "A", "邀请信息完整，目的明确。", "句式自然，个别表达可更丰富。", "格式规范，结尾得体。", "下次可尝试补充路线或联系方式。"),
        (8, "Our class will hold a green campus activity next week. Students can bring reusable bottles and collect waste paper after class. I believe small actions can make our school cleaner and help us build good habits.", 88.5, 32.5, 31.0, 25.0, "A", "观点清楚，细节贴近校园生活。", "词汇使用准确，建议尝试更复杂的从句。", "结构完整，结尾有号召力。", "这是一篇完成度很高的应用文，可继续强化句式多样性。"),
    )
    for sequence, essay, score, content, language, organization, level, content_note, language_note, organization_note, comment in writing_rows:
        paper_id = f"acceptance-paper-{SHOWCASE_USERNAME}-{sequence:03d}"
        paper_row = conn.execute("SELECT generated_at FROM papers WHERE paper_id=? AND user_id=?", (paper_id, SHOWCASE_USERNAME)).fetchone()
        if paper_row is None:
            raise RuntimeError("showcase writing paper is missing")
        graded_at = datetime.fromisoformat(paper_row[0]) + timedelta(minutes=35)
        conn.execute(
            "INSERT INTO writing_grade_results (id,user_id,paper_id,item_index,user_essay,total_score,content_score,language_score,organization_score,word_count,level,content_analysis,language_analysis,organization_analysis,overall_comment,revised_version,graded_at) VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id,paper_id,item_index) DO UPDATE SET user_essay=excluded.user_essay,total_score=excluded.total_score,content_score=excluded.content_score,language_score=excluded.language_score,organization_score=excluded.organization_score,word_count=excluded.word_count,level=excluded.level,content_analysis=excluded.content_analysis,language_analysis=excluded.language_analysis,organization_analysis=excluded.organization_analysis,overall_comment=excluded.overall_comment,revised_version=excluded.revised_version,graded_at=excluded.graded_at",
            (f"showcase-jingyi-writing-{sequence:03d}", SHOWCASE_USERNAME, paper_id, essay, score, content, language, organization, len(essay.split()), level, content_note, language_note, organization_note, comment, essay, graded_at.isoformat()),
        )

    plan_days = []
    for index, sequence in enumerate((12, 13, 14, 15, 16, 17, 18), 1):
        paper_id = f"acceptance-paper-{SHOWCASE_USERNAME}-{sequence:03d}"
        title = paper_titles.get(sequence, f"暑期巩固练习 · 第 {sequence + 1} 组")
        plan_days.append({"index": index, "date": (date(2026, 8, 19) + timedelta(days=index - 1)).isoformat(), "theme": "开学前综合复盘", "knowledge_points": ["grammar", "vocabulary"], "kp_names": ["语法基础", "核心词汇"], "question_types": list(QUESTION_TYPES), "total_questions": 6, "note": "已完成；根据错题调整下一日复习重点。", "paper_id": paper_id, "paper_title": title})
    plan = {"total_days": 7, "days": plan_days}
    conn.execute("INSERT INTO study_plans (id,user_id,created_at,status,total_days,plan_json) VALUES (?,?,?,'active',?,?)", ("showcase-jingyi-plan", SHOWCASE_USERNAME, ts(date(2026, 8, 18), 20).isoformat(), 7, json.dumps(plan, ensure_ascii=False)))

    mindmaps = (
        ("showcase-jingyi-grammar", "非谓语动词复习框架", "非谓语动词", "# 非谓语动词\n\n- 不定式：表目的、将来\n- 动名词：作主语或宾语\n- 分词：作定语、状语\n\n## 易错提醒\n\n- avoid 后接动名词\n- decide 后接不定式\n- 被动含义优先判断过去分词", date(2026, 8, 18)),
        ("showcase-jingyi-writing-map", "应用文写作检查清单", "应用文写作", "# 应用文写作\n\n- 开头：说明写信目的\n- 主体：时间、地点、活动安排\n- 结尾：表达期待或感谢\n\n## 自查\n\n- 时态是否统一\n- 是否使用连接词\n- 是否有明确称呼和落款", date(2026, 8, 27)),
    )
    for mindmap_id, title, knowledge_point, outline, day in mindmaps:
        when = ts(day, 20).isoformat()
        conn.execute("INSERT INTO mindmaps (id,user_id,created_at,updated_at,title,knowledge_point,outline_md) VALUES (?,?,?,?,?,?,?)", (mindmap_id, SHOWCASE_USERNAME, when, when, title, knowledge_point, outline))

    retry_specs = ((date(2026, 8, 24), 0, "forgot", "known", 2, ts(date(2026, 8, 24), 18, 35)), (date(2026, 8, 29), 1, "fuzzy", "fuzzy", 1, None))
    for day, slot, first_rating, last_rating, retry_count, passed_at in retry_specs:
        word = conn.execute("SELECT word_id FROM vocabulary_daily_cards WHERE user_id=? AND study_date=? ORDER BY word_id LIMIT 1 OFFSET ?", (SHOWCASE_USERNAME, day.isoformat(), slot)).fetchone()
        if word is None:
            raise RuntimeError("showcase vocabulary card is missing")
        word_id = word[0]
        log_id = f"vlog-{SHOWCASE_USERNAME}-{day:%Y%m%d}-{slot}"
        conn.execute("UPDATE vocabulary_review_logs SET spelling_correct=?, requested_rating=?, applied_rating=? WHERE id=?", (int(last_rating == "known"), first_rating, last_rating, log_id))
        conn.execute("INSERT INTO vocabulary_daily_retry_queue (user_id,study_date,word_id,first_rating,last_rating,retry_count,queue_order,passed_at) VALUES (?,?,?,?,?,?,?,?)", (SHOWCASE_USERNAME, day.isoformat(), word_id, first_rating, last_rating, retry_count, slot + 1, passed_at.isoformat() if passed_at else None))

def insert_admin_audit_logs(conn: sqlite3.Connection, people: list[Persona]) -> None:
    """Create realistic, read-only historical entries for the admin audit page."""
    admins = [person.username for person in people if person.role == "admin"]
    students = [person.username for person in people if person.role == "user" and person.status == "active"]
    actions = (
        ("adjust_credits", {"delta": 30, "reason": "活动奖励补发"}),
        ("reset_password", {"reason": "用户提交找回申请"}),
        ("grant_membership", {"days": 30, "reason": "暑期活动补偿"}),
        ("ban", {"reason": "异常请求待核验"}),
        ("unban", {"reason": "核验通过，恢复使用"}),
        ("set_role", {"role": "user", "reason": "权限核对后恢复普通账号"}),
        ("revoke_membership", {"reason": "重复权益已回收"}),
        ("adjust_credits", {"delta": -20, "reason": "重复发放积分回收"}),
    )
    for index in range(EXPECTED_AUDIT_LOG_COUNT):
        action, detail = actions[index % len(actions)]
        target = SHOWCASE_USERNAME if index in {6, 22, 38} else students[(index * 47 + 13) % len(students)]
        day = START + timedelta(days=index + (1 if index >= 24 else 0))
        conn.execute(
            "INSERT INTO admin_audit_logs (actor_user_id,action,target_user_id,detail_json,created_at) VALUES (?,?,?,?,?)",
            (admins[index % len(admins)], action, target, json.dumps(detail, ensure_ascii=False), ts(day, 9 + index % 9, (index * 7) % 60).isoformat()),
        )

def insert_credits_orders(conn: sqlite3.Connection, rng: random.Random, people: list[Persona], events: list[Spend]) -> tuple[int, int]:
    per_user: dict[str, list[Spend]] = defaultdict(list)
    for event in events: per_user[event.user_id].append(event)
    packs, purchases = {pack.id: pack for pack in PACKS}, defaultdict(list)
    paid_student_indexes = set(random.Random(RNG_SEED + 46).sample(range(EXPECTED_STUDENT_COUNT), EXPECTED_PAID_STUDENT_COUNT))
    orders = paid = 0
    for index, person in enumerate(people):
        if person.role == "user" and index in paid_student_indexes:
            pack = packs[("starter", "standard", "annual")[index % 3]]; day = min(END, person.created_on + timedelta(days=2 + index % 9)); order = f"DEMO{index:05d}PAID"
            conn.execute("INSERT INTO orders (out_trade_no,user_id,pack_id,amount_cents,credits,status,channel,qr_code,pay_url,alipay_trade_no,created_at,expires_at,paid_at) VALUES (?,?,?,?,?,'PAID','qr','demo://qr','demo://pay',?,?,?,?)", (order, person.username, pack.id, pack.amount_cents, pack.credits, f"TRADE{index:05d}", ts(day,10).isoformat(), ts(day,10,30).isoformat(), ts(day,10,5).isoformat()))
            purchases[person.username].append((ts(day,10,5), order, pack.credits, pack.id)); orders += 1; paid += 1
        elif person.role == "user" and index % 97 == 0:
            pack, day, status = packs["starter"], min(END, person.created_on + timedelta(days=1)), "EXPIRED" if index % 2 else "CREATED"
            conn.execute("INSERT INTO orders (out_trade_no,user_id,pack_id,amount_cents,credits,status,channel,qr_code,pay_url,created_at,expires_at) VALUES (?,?,?,?,?,?, 'qr','demo://qr','demo://pay',?,?)", (f"DEMO{index:05d}{status}", person.username, pack.id, pack.amount_cents, pack.credits, status, ts(day,11).isoformat(), ts(day,11,30).isoformat())); orders += 1
    for person in people:
        spent = sorted(per_user[person.username], key=lambda e:(e.when,e.ref_id)); current = rng.randrange(91) * 10 + sum(e.amount for e in spent); target = current - sum(e.amount for e in spent)
        conn.execute("INSERT INTO credit_accounts (user_id,balance,daily_balance,daily_date,updated_at) VALUES (?,?,0,?,?)", (person.username,target,END.isoformat(),ts(END,23,59).isoformat()))
        conn.execute("INSERT INTO credit_ledger (user_id,delta,bucket,balance_after,kind,ref_type,ref_id,note,created_at) VALUES (?,?,'balance',?,'admin_adjust','demo_seed',?,'验收初始积分',?)", (person.username,current,current,f"seed:{person.username}",ts(START,0).isoformat()))
        for when, order, credits, pack_id in purchases[person.username]:
            current += credits; conn.execute("INSERT INTO credit_ledger (user_id,delta,bucket,balance_after,kind,ref_type,ref_id,note,created_at) VALUES (?,?,'balance',?,'purchase','order',?,?,?)", (person.username,credits,current,order,f"购买积分包 {pack_id}",when.isoformat()))
        for event in spent:
            current -= event.amount; conn.execute("INSERT INTO credit_ledger (user_id,delta,bucket,balance_after,kind,action,ref_type,ref_id,note,created_at) VALUES (?,?,'balance',?,'spend',?,?,?,?,?)", (person.username,-event.amount,current,event.action,event.ref_type,event.ref_id,PRICES[event.action].label,event.when.isoformat()))
        purchase_total = sum(row[2] for row in purchases[person.username])
        if purchase_total:
            current -= purchase_total; conn.execute("INSERT INTO credit_ledger (user_id,delta,bucket,balance_after,kind,ref_type,ref_id,note,created_at) VALUES (?,?,'balance',?,'admin_adjust','demo_reconcile',?,'验收余额校准',?)", (person.username,-purchase_total,current,f"reconcile:{person.username}",ts(END,23,59).isoformat()))
        if current != target: raise RuntimeError("credit reconciliation failed")
    if paid != EXPECTED_PAID_STUDENT_COUNT:
        raise RuntimeError("invalid paid-user count")
    return orders, paid

def write_accounts(path: Path, people: list[Persona]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("username","password","role","activity","created_on","status")); writer.writeheader()
        for person in people: writer.writerow({"username":person.username,"password":PASSWORD,"role":person.role,"activity":person.activity,"created_on":person.created_on.isoformat(),"status":person.status})

def seed_database(db: Path, accounts: Path, *, reset: bool = False) -> dict[str,int]:
    if db.exists() and not reset: raise FileExistsError(f"{db} already exists; rerun with --reset")
    db.parent.mkdir(parents=True, exist_ok=True)
    if reset: clear(db, accounts)
    storage.set_db_path(db)
    try:
        storage.init_db(); storage.seed_vocabulary_from_json(WORDLIST)
        people, rng = personas(), random.Random(RNG_SEED); password = hash_password(PASSWORD)
        with storage.connect() as conn:
            for person in people: conn.execute("INSERT INTO users (id,username,password_hash,created_at,role,status) VALUES (?,?,?,?,?,?)", (person.username,person.username,password,ts(person.created_on,9).isoformat(),person.role,person.status))
            papers, attempts, logs, events, submitted = insert_learning(conn,rng,people)
            events += insert_writing_and_agent(conn,rng,people,submitted)
            insert_jingyi_showcase(conn)
            insert_admin_audit_logs(conn, people)
            orders, paid = insert_credits_orders(conn,rng,people,events)
        write_accounts(accounts,people)
        return {"users":len(people),"admins":EXPECTED_ADMIN_COUNT,"papers":papers,"attempts":attempts,"vocabulary_logs":logs,"orders":orders,"paid_orders":paid}
    finally: storage.set_db_path(None)

def verify_database(db: Path) -> dict[str,int]:
    conn = sqlite3.connect(db)
    try:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]; admins = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]; attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]; logs = conn.execute("SELECT COUNT(*) FROM vocabulary_review_logs").fetchone()[0]
        names = [r[0] for r in conn.execute("SELECT username FROM users")]
        counts = Counter({date.fromisoformat(day):count for day,count in conn.execute("SELECT substr(created_at,1,10),COUNT(*) FROM users WHERE role='user' GROUP BY substr(created_at,1,10)")})
        expected = Counter(registration_days()); actions = {r[0] for r in conn.execute("SELECT DISTINCT action FROM credit_ledger WHERE kind='spend'")}
        balances = [r[0] for r in conn.execute("SELECT balance FROM credit_accounts")]; top = conn.execute("SELECT user_id FROM credit_ledger WHERE kind='spend' GROUP BY user_id HAVING SUM(-delta)>0 ORDER BY SUM(-delta) DESC LIMIT 10").fetchall()
        packs = {r[0] for r in conn.execute("SELECT DISTINCT pack_id FROM orders WHERE status='PAID'")}; writing = conn.execute("SELECT COUNT(*) FROM writing_grade_results").fetchone()[0]
        paid_users = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders WHERE status='PAID'").fetchone()[0]
        showcase_writing = conn.execute("SELECT COUNT(*) FROM writing_grade_results WHERE user_id=?", (SHOWCASE_USERNAME,)).fetchone()[0]
        showcase_plan = conn.execute("SELECT COUNT(*) FROM study_plans WHERE user_id=? AND status='active'", (SHOWCASE_USERNAME,)).fetchone()[0]
        showcase_mindmaps = conn.execute("SELECT COUNT(*) FROM mindmaps WHERE user_id=?", (SHOWCASE_USERNAME,)).fetchone()[0]
        showcase_retries = conn.execute("SELECT COUNT(*) FROM vocabulary_daily_retry_queue WHERE user_id=?", (SHOWCASE_USERNAME,)).fetchone()[0]
        audit_count = conn.execute("SELECT COUNT(*) FROM admin_audit_logs").fetchone()[0]
        audit_actions = {row[0] for row in conn.execute("SELECT DISTINCT action FROM admin_audit_logs")}
        generation = conn.execute("SELECT COUNT(*) FROM credit_ledger WHERE kind='spend' AND action IN ('generate_original','generate_light','generate_fresh','revise_paper')").fetchone()[0]
        first,last = conn.execute("SELECT MIN(generated_at),MAX(generated_at) FROM papers").fetchone(); fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if (users,admins)!=(EXPECTED_STUDENT_COUNT+EXPECTED_ADMIN_COUNT,EXPECTED_ADMIN_COUNT) or len(names)!=len(set(names)) or any(not USERNAME_PATTERN.fullmatch(name) for name in names): raise RuntimeError("invalid accounts")
        if counts!=expected or counts[date(2026,8,27)]!=3 or counts[date(2026,8,28)]!=5: raise RuntimeError("invalid registrations")
        if len(balances)!=users or any(balance<0 or balance>900 or balance%10 for balance in balances): raise RuntimeError("invalid credits")
        if set(PRICES)-actions or generation!=papers or len(top)!=10 or not writing or packs!={p.id for p in PACKS} or paid_users != EXPECTED_PAID_STUDENT_COUNT: raise RuntimeError("incomplete monitoring data")
        if showcase_writing != 3 or showcase_plan != 1 or showcase_mindmaps != 2 or showcase_retries != 2: raise RuntimeError("incomplete showcase data")
        if audit_count != EXPECTED_AUDIT_LOG_COUNT or len(audit_actions) < 7: raise RuntimeError("incomplete audit data")
        if not attempts or not logs or first[:10]!=START.isoformat() or last[:10]!=END.isoformat() or fk: raise RuntimeError("incomplete learning data")
        return {"users":users,"admins":admins,"paid_users":paid_users,"papers":papers,"attempts":attempts,"vocabulary_logs":logs,"writing_results":writing,"showcase_writing":showcase_writing,"showcase_mindmaps":showcase_mindmaps,"audit_logs":audit_count,"top_spenders":len(top)}
    finally: conn.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fictional acceptance data for July 15 to August 31, 2026.")
    parser.add_argument("--db",type=Path,default=DEFAULT_DB); parser.add_argument("--accounts",type=Path,default=DEFAULT_ACCOUNTS); parser.add_argument("--reset",action="store_true"); parser.add_argument("--verify",action="store_true")
    args = parser.parse_args()
    result = verify_database(args.db) if args.verify else seed_database(args.db,args.accounts,reset=args.reset)
    print(json.dumps(result,ensure_ascii=False))
    if not args.verify: print(f"database: {args.db}\naccounts: {args.accounts}")

if __name__ == "__main__": main()
