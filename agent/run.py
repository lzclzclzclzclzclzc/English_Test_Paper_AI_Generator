"""Interactive CLI for the study-coach agent.

Usage:
    PYTHONIOENCODING=utf-8 python agent/run.py

The agent will ask for user_id and plan requirements through conversation.
Or pass them directly:
    PYTHONIOENCODING=utf-8 python agent/run.py --user u_demo_review --days 7
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.coach import ask_coach


async def main() -> None:
    parser = argparse.ArgumentParser(description="中考英语学习助手")
    parser.add_argument("--user", default=None, help="用户ID（不传则通过对话获取）")
    parser.add_argument("--days", type=int, default=7, help="学习计划天数")
    args = parser.parse_args()

    if args.user:
        message = (
            f"请帮用户 {args.user} 制定未来 {args.days} 天的学习计划，"
            f"并展示第一天的例题。"
        )
    else:
        print("中考英语学习助手")
        print("─" * 60)
        message = input("你好！请告诉我你的用户ID和需求：").strip()
        if not message:
            print("输入不能为空")
            return

    print("\n思考中...\n")
    print("─" * 60)

    response = await ask_coach(message)
    print(response)
    print("─" * 60)


if __name__ == "__main__":
    asyncio.run(main())
