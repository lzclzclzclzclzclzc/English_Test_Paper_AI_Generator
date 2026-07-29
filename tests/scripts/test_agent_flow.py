"""Agent 全链路测试脚本（端到端，不依赖浏览器）。

测试覆盖：
  1. 注册 / 登录，获取 session cookie
  2. POST /api/agent/chat — 出题请求，验证 action=open_paper + paper_id
  3. POST /api/agent/chat — 制定学习计划，验证 action=study_plan_ready
  4. POST /api/agent/extract-plan — 一键实施，验证返回 StudyPlan
  5. GET  /api/agent/study-plans/latest — 验证计划已持久化
  6. GET  /api/papers/{paper_id} — 验证出题生成的试卷可读取

Usage:
    PYTHONIOENCODING=utf-8 python tests/scripts/test_agent_flow.py [--base http://localhost:8000]

后端需已启动，且 u_demo_review 的历史数据已注入（python agent/seed_demo.py）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))


def _req(
    method: str,
    url: str,
    body: dict | None = None,
    cookies: dict | None = None,
    timeout: int = 120,
) -> tuple[int, dict, dict]:
    """Simple HTTP helper. Returns (status, response_body, response_headers)."""
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = json.loads(resp.read().decode())
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp_body, resp_headers
    except urllib.error.HTTPError as e:
        resp_body = json.loads(e.read().decode())
        return e.code, resp_body, {}


def _extract_cookie(headers: dict) -> dict:
    """Extract session_id from Set-Cookie header."""
    raw = headers.get("set-cookie", "")
    cookies: dict = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            cookies[k.strip()] = v.strip()
    return cookies


def run(base: str) -> None:
    sep = "─" * 60
    print(sep)
    print("  Agent 全链路测试")
    print(f"  后端：{base}")
    print(sep)

    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  ✅ {label}")
        else:
            msg = f"  ❌ {label}" + (f"  ({detail})" if detail else "")
            print(msg)
            failures.append(label)

    # ── 1. 注册 / 登录 ───────────────────────────────────────────────
    print("\n[1] 认证")
    username = "demo"
    password = "demo123"

    status, body, headers = _req("POST", f"{base}/api/auth/login",
                                  {"username": username, "password": password})
    check("登录成功", status == 200, f"status={status}")
    cookies = _extract_cookie(headers)
    check("获取 session cookie", bool(cookies.get("session_id")),
          f"headers={dict(headers)}")

    # ── 2. Agent chat — 出题 ─────────────────────────────────────────
    print("\n[2] Agent chat — 出题（generate_paper skill）")
    t0 = time.time()
    status, body, _ = _req(
        "POST", f"{base}/api/agent/chat",
        {"message": "来3道介词单选题", "history": []},
        cookies,
    )
    elapsed = time.time() - t0
    check(f"chat 请求成功（{elapsed:.1f}s）", status == 200, f"status={status}, body={body}")

    if status == 200:
        reply = body.get("reply", "")
        action = body.get("action")
        history = body.get("history", [])
        check("reply 非空", bool(reply))
        check("history 有记录", len(history) > 0, f"len={len(history)}")
        check("action 为 open_paper", action is not None and action.get("type") == "open_paper",
              f"action={action}")
        paper_id_from_chat = action.get("paper_id") if action else None
    else:
        paper_id_from_chat = None

    # ── 3. Agent chat — 学习计划（study_plan skill）──────────────────
    print("\n[3] Agent chat — 制定学习计划（study_plan skill）")
    t0 = time.time()
    status, body, _ = _req(
        "POST", f"{base}/api/agent/chat",
        {
            "message": (
                "帮我制定3天学习计划，我的用户ID是 u_demo_review，"
                "请根据我的历史做题情况制定"
            ),
            "history": [],
        },
        cookies,
    )
    elapsed = time.time() - t0
    check(f"chat 请求成功（{elapsed:.1f}s）", status == 200, f"status={status}")

    plan_text = ""
    if status == 200:
        reply = body.get("reply", "")
        action = body.get("action")
        plan_text = reply
        check("reply 非空", bool(reply))
        check("action 为 study_plan_ready",
              action is not None and action.get("type") == "study_plan_ready",
              f"action={action}")
        if action and action.get("type") == "study_plan_ready":
            check("total_days > 0", action.get("total_days", 0) > 0,
                  f"total_days={action.get('total_days')}")

    # ── 4. Extract plan — 一键实施 ───────────────────────────────────
    print("\n[4] POST /api/agent/extract-plan — 一键实施")
    if not plan_text:
        print("  ⚠️  跳过（上一步未拿到 plan_text）")
    else:
        t0 = time.time()
        status, body, _ = _req(
            "POST", f"{base}/api/agent/extract-plan",
            {
                "plan_text": plan_text,
                "start_date": "2026-07-21",
            },
            cookies,
            timeout=300,
        )
        elapsed = time.time() - t0
        check(f"extract-plan 请求成功（{elapsed:.1f}s）", status == 200,
              f"status={status}, body={str(body)[:200]}")

        if status == 200:
            days = body.get("days", [])
            total = body.get("total_days", 0)
            check("total_days > 0", total > 0, f"total_days={total}")
            check("days 非空", len(days) > 0, f"len={len(days)}")
            if days:
                d0 = days[0]
                check("每天有 paper_id", bool(d0.get("paper_id")),
                      f"day[0]={d0}")
                check("每天有 knowledge_point_id",
                      bool(d0.get("knowledge_point_id")),
                      f"day[0]={d0}")
                print(f"\n  计划内容（前 3 天）：")
                for d in days[:3]:
                    print(f"    第{d['index']}天 | {d['kp_name']} | "
                          f"{d['question_type']} × {d['count']} 道 | "
                          f"paper_id={d['paper_id'][:8]}…")

    # ── 5. GET study-plans/latest ────────────────────────────────────
    print("\n[5] GET /api/agent/study-plans/latest — 验证持久化")
    if not plan_text:
        print("  ⚠️  跳过（extract-plan 未执行）")
    else:
        status, body, _ = _req("GET", f"{base}/api/agent/study-plans/latest",
                                cookies=cookies)
        check("读取最新计划成功", status == 200, f"status={status}")
        if status == 200 and body:
            check("latest plan 非空", body is not None and bool(body.get("days")))

    # ── 6. GET papers/{paper_id} — 验证出题的试卷可读取 ──────────────
    print("\n[6] GET /api/papers/{paper_id} — 验证试卷可读取")
    if not paper_id_from_chat:
        print("  ⚠️  跳过（步骤2未拿到 paper_id）")
    else:
        status, body, _ = _req("GET", f"{base}/api/papers/{paper_id_from_chat}",
                                cookies=cookies)
        check("试卷读取成功", status == 200, f"status={status}")
        if status == 200:
            items = body.get("items", [])
            check("试卷题目数量 > 0", len(items) > 0, f"items={len(items)}")
            print(f"  试卷：{body.get('title')}（{len(items)} 题）")

    # ── 汇总 ─────────────────────────────────────────────────────────
    print(f"\n{sep}")
    total_checks = 0
    # Count passes + failures
    pass_count = 0
    for line in failures:
        _ = line  # already collected
    # Re-scan: count by looking at what we printed isn't easy, use failures list
    print(f"  结果：{'通过' if not failures else '失败'}")
    if failures:
        print(f"  失败项（{len(failures)}）：")
        for f in failures:
            print(f"    - {f}")
    else:
        print("  所有检查项全部通过 🎉")
    print(sep)

    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000",
                        help="后端 base URL（默认 http://localhost:8000）")
    args = parser.parse_args()

    failures = run(args.base)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
