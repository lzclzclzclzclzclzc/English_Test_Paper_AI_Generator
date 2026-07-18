#!/usr/bin/env python3
"""Interactive Parser module tester.

Run to enter a REPL loop for testing the Parser module.
Input natural language queries and see the structured GenerateRequest output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_engine.parser import parse


def main() -> None:
    print("=" * 60)
    print("  Interactive Parser Tester")
    print("=" * 60)
    print("输入自然语言指令，按 Ctrl+C 或输入 'exit' 退出")
    print("示例:")
    print("  生成5道动词时态的单选题")
    print("  帮我出10道中考英语练习题")
    print("=" * 60)

    while True:
        try:
            print()
            user_query = input("输入指令: ").strip()

            if user_query.lower() in ("exit", "quit", "q"):
                print("退出...")
                break

            if not user_query:
                continue

            print("\n正在处理...")

            result = parse(user_query)

            print("\n" + "=" * 60)
            print("结果 (GenerateRequest):")
            print("=" * 60)
            output = json.dumps(
                result.model_dump(),
                ensure_ascii=False,
                indent=2,
                default=str
            )
            print(output)

        except KeyboardInterrupt:
            print("\n\n退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")


if __name__ == "__main__":
    main()
