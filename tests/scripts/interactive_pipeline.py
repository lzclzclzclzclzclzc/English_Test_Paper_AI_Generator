"""Run the integrated Parser → Retriever → Reviser pipeline interactively.

Before running, copy .env.example to .env, set LLM_API_KEY, install project
dependencies, and run models/download_model.py when testing a semantic/vector request.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from ai_engine import generate_paper


def main() -> None:
    print("Interactive Parser → Retriever → Reviser. Type q to exit.")
    while True:
        query = input("prompt> ").strip()
        if query.lower() in {"q", "quit", "exit"}:
            return
        if not query:
            continue
        started = time.perf_counter()
        try:
            paper = generate_paper(query)
        except Exception as exc:
            print(f"Failed: {exc}")
            continue
        elapsed = time.perf_counter() - started
        print(f"{paper.title}: {len(paper.items)} questions in {elapsed:.2f}s")
        print(f"metadata={paper.metadata}")
        for item in paper.items:
            question = item.question
            print(f"\n[{item.index}] {question.question_type} ({item.revision_mode})")
            print(question.stem or question.original_sentence or "")
            if question.options:
                print(" ".join(f"{option.label}. {option.text}" for option in question.options))
            print(f"Answer: {question.answer}")


if __name__ == "__main__":
    main()
