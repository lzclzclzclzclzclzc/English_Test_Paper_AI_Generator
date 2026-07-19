from __future__ import annotations

import os
import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.auth.password import hash_password
from shared import storage
from shared.config import reset_config_cache


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

    sub.add_parser("cleanup-sessions")
    sub.add_parser("smoke")

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
    if args.command == "cleanup-sessions":
        print(json.dumps({"deleted": storage.cleanup_sessions()}))
        return 0
    if args.command == "smoke":
        return _smoke()
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


if __name__ == "__main__":
    raise SystemExit(main())
