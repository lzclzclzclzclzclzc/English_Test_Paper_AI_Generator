"""Interactive multi-turn CLI for the study-coach agent.

Usage:
    PYTHONIOENCODING=utf-8 python agent/run.py [--user USER_ID] [--days N]

Type 'exit' / 'q' or press Ctrl+C to quit.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Runner
from agent.coach import create_coach_agent


async def main() -> None:
    parser = argparse.ArgumentParser(description="中考英语学习助手")
    parser.add_argument("--user", default=None, help="用户ID（也可以在对话中告知）")
    parser.add_argument("--days", type=int, default=7, help="学习计划天数")
    args = parser.parse_args()

    agent = create_coach_agent()

    print("=" * 60)
    print("  中考英语学习助手（多轮对话）")
    print("  输入 'exit' / 'q' 或按 Ctrl+C 退出")
    print("=" * 60)

    history = []

    if args.user:
        first_msg = (
            f"请帮用户 {args.user} 制定未来 {args.days} 天的学习计划，并展示第一天的例题。"
        )
        print(f"\n你: {first_msg}")
        print("\n助手: ", end="", flush=True)
        try:
            result = await Runner.run(agent, input=first_msg)
            print(result.final_output)
            history = list(result.to_input_list())
        except Exception as e:
            print(f"\n出错了: {e}")
            return
    else:
        print("\n你可以告诉我你的用户ID和需求，例如：")
        print("  「帮 u_demo_review 制定7天学习计划」")

    while True:
        print()
        try:
            user_input = input("你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("再见！")
            break

        print("\n助手: ", end="", flush=True)
        try:
            result = await Runner.run(
                agent,
                input=history + [{"role": "user", "content": user_input}],
            )
            print(result.final_output)
            history = list(result.to_input_list())
        except Exception as e:
            print(f"\n出错了: {e}")


if __name__ == "__main__":
    asyncio.run(main())
