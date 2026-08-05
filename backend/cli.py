from __future__ import annotations

import os
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from backend.auth.password import hash_password
from shared import storage
from shared.config import reset_config_cache
from shared.schemas import GenerateRequest, Paper, PaperItem, RevisedQuestion


def _smoke_paper(*, user_id: str | None = None, **_: object) -> Paper:
    questions = [
        RevisedQuestion(question_type="single_choice", answer="B", knowledge_point_ids=["kp_sc"]),
        RevisedQuestion(question_type="word_form", answer="written", knowledge_point_ids=["kp_wf"]),
        RevisedQuestion(
            question_type="sentence_rewriting",
            answer=[{"blank1": ["so"], "blank2": ["that"]}],
            knowledge_point_ids=["kp_sr"],
        ),
    ]
    return Paper(
        paper_id=uuid4().hex,
        title="backend smoke",
        generated_at=datetime.now(timezone.utc),
        request=GenerateRequest(total_questions=3, user_id=user_id),
        items=[
            PaperItem(index=index, source_question_id=f"q_{index:05d}", revision_mode="original", question=question)
            for index, question in enumerate(questions, start=1)
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    sub.add_parser("init-db")

    create_user = sub.add_parser("create-user")
    create_user.add_argument("--username", required=True)
    create_user.add_argument("--password", required=True)

    promote = sub.add_parser("promote-admin")
    promote.add_argument("--username", required=True)

    sub.add_parser("cleanup-sessions")
    sub.add_parser("smoke")
    sub.add_parser("deploy-check")

    args = parser.parse_args(argv)
    if args.command == "serve":
        cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", args.host, "--port", str(args.port)]
        if args.reload:
            cmd.append("--reload")
        return subprocess.call(cmd)
    if args.command == "init-db":
        storage.init_db()
        print(f"initialized {storage.get_db_path()}")
        return 0
    if args.command == "create-user":
        storage.init_db()
        user = storage.create_user(args.username, hash_password(args.password))
        print(user.model_dump_json())
        return 0
    if args.command == "promote-admin":
        storage.init_db()
        record = storage.get_user_by_username(args.username)
        if record is None:
            print(json.dumps({"error": "user_not_found", "username": args.username}, ensure_ascii=False))
            return 2
        storage.set_user_role(record.id, "admin")
        print(json.dumps({"promoted": args.username}, ensure_ascii=False))
        return 0
    if args.command == "cleanup-sessions":
        print(json.dumps({"deleted": storage.cleanup_sessions()}))
        return 0
    if args.command == "smoke":
        return _smoke()
    if args.command == "deploy-check":
        return _deploy_check()
    return 1


def _smoke() -> int:
    from fastapi.testclient import TestClient

    with TemporaryDirectory() as tmp_dir:
        smoke_db = Path(tmp_dir) / "smoke.db"
        storage.set_db_path(smoke_db)
        previous_env = os.environ.get("BACKEND_ENV")
        os.environ["BACKEND_ENV"] = "test"
        reset_config_cache()
        try:
            from backend.main import create_app
            from backend.services import ai_gateway

            with patch.object(ai_gateway, "generate_paper", _smoke_paper), patch.object(
                ai_gateway, "generate_solution", lambda *_args, **_kwargs: "答案解析"
            ):
                app = create_app()
                with TestClient(app) as client:
                    username = "demo_smoke"
                    password = "demo123"
                    response = client.post("/api/auth/register", json={"username": username, "password": password})
                    response.raise_for_status()
                    paper = client.post("/api/papers/generate", json={"user_query": "来 3 道中等难度英语题", "mode": "fresh"}).json()
                    answers = [
                    {"index": 1, "user_answer": "B"},
                    {"index": 2, "user_answer": "written"},
                    {"index": 3, "user_answer": {"blank1": "so", "blank2": "that"}},
                    ]
                    grade = client.post("/api/attempts", json={"paper_id": paper["paper_id"], "items": answers}).json()
                    mastery = client.get("/api/users/me/mastery").json()
                    first_item = paper["items"][0]
                    solution = client.post(
                    "/api/solutions",
                    json={
                        "question": first_item["question"],
                        "source_question_id": first_item["source_question_id"],
                        "revision_mode": first_item["revision_mode"],
                    },
                    )
                    solution.raise_for_status()
                    print(
                    json.dumps(
                        {
                            "paper_id": paper["paper_id"],
                            "attempt_id": grade["attempt_id"],
                            "mastery": mastery,
                            "solution": solution.json()["solution"],
                        },
                        ensure_ascii=False,
                    )
                    )
        finally:
            storage.set_db_path(None)
            if previous_env is None:
                os.environ.pop("BACKEND_ENV", None)
            else:
                os.environ["BACKEND_ENV"] = previous_env
            reset_config_cache()
    return 0


def _deploy_check() -> int:
    """Validate the prerequisites for a same-origin remote demo deployment."""
    from backend.api.health import _readiness_checks
    from shared.config import get_config

    config = get_config()
    checks = {
        "production_mode": config.backend.env == "production",
        "llm_api_key": bool(config.llm_api_key.strip()),
        "static_index": (config.backend.static_dir / "index.html").is_file(),
        **_readiness_checks(),
    }
    ready = all(checks.values())
    print(
        json.dumps(
            {
                "status": "ready" if ready else "not_ready",
                "checks": checks,
                "static_dir": str(config.backend.static_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
