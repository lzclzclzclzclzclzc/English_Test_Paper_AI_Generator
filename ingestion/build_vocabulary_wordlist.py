"""Build the attributable Shanghai vocabulary seed file from its public index.

The source is a third-party transcription, not an official machine-readable
publication.  We retain its URL and a hash of fetched pages in the generated
file.  Only word, part of speech and Chinese meaning are imported; examples are
project-owned templates and must be editorially improved before a public launch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

INDEX_URL = "https://www.koolearn.com/dict/tag_1606_{page}.html"
SOURCE_URL = "https://www.koolearn.com/dict/tag_1606_1.html"
EXPECTED_COUNT = 1678
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EnglishTestPaperVocabulary/1.0)"}


def _get(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return urlopen(Request(url, headers=HEADERS), timeout=12).read().decode("utf-8")
        except Exception as exc:  # The public source occasionally throttles detail pages.
            last_error = exc
            sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}") from last_error


def _index_entries() -> tuple[list[tuple[str, str]], str]:
    entries: list[tuple[str, str]] = []
    source_pages: list[str] = []
    for page in range(1, 10):
        html = _get(INDEX_URL.format(page=page))
        source_pages.append(html)
        soup = BeautifulSoup(html, "html.parser")
        box = soup.select_one(".word-wrap .word-box")
        if box is None:
            raise RuntimeError(f"source page {page} has no vocabulary box")
        for link in box.select("a.word[href]"):
            term = link.get_text(" ", strip=True)
            # The declared 1,678-item Word List excludes multi-word phrases.
            if term and not re.search(r"\s", term):
                entries.append((term, link["href"]))
    return entries, hashlib.sha256("\n".join(source_pages).encode("utf-8")).hexdigest()


def _entry(term: str, href: str) -> dict | None:
    soup = BeautifulSoup(_get(f"https://www.koolearn.com{href}"), "html.parser")
    senses = soup.select("li.clearfix")
    meanings: list[str] = []
    parts: list[str] = []
    for sense in senses:
        prop = sense.select_one("span.prop")
        description = sense.select_one("p")
        if prop is None or description is None:
            continue
        text = description.get_text("", strip=True)
        if not text:
            continue
        parts.append(prop.get_text("", strip=True))
        meanings.append(text)
    if not meanings:
        return None
    # These examples are intentionally project-authored templates, not scraped.
    return {
        "term": term,
        "part_of_speech": " / ".join(dict.fromkeys(parts)),
        "meanings": meanings[:4],
        "example_en": f"Remember how to use {term} in a sentence.",
        "example_zh": f"请结合释义记忆 {term} 的用法。",
    }


def build(output: Path, expected_count: int = EXPECTED_COUNT) -> int:
    candidates, source_sha256 = _index_entries()
    results: list[dict] = []
    # The source rate-limits aggressively. Keep requests bounded and stop once
    # the declared word-list size has been collected.
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_entry, term, href): term for term, href in candidates[: expected_count + 80]}
        extracted: dict[str, dict] = {}
        for future in as_completed(futures):
            try:
                value = future.result()
            except RuntimeError:
                continue
            if value is not None:
                extracted[value["term"].casefold()] = value
    for term, _ in candidates:
        value = extracted.get(term.casefold())
        if value is not None:
            value["id"] = f"shanghai_basic_{len(results) + 1:04d}"
            results.append(value)
        if len(results) == expected_count:
            break
    if len(results) != expected_count:
        raise RuntimeError(f"expected {expected_count} usable single-word entries, got {len(results)}")
    payload = {
        "metadata": {
            "id": "shanghai-basic-1678-third-party-v1",
            "label": "上海课程标准依据词表（第三方整理）",
            "source_url": SOURCE_URL,
            "source_accessed_at": date.today().isoformat(),
            "source_sha256": source_sha256,
        },
        "words": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/vocabulary/shanghai-basic-1678.json"))
    parser.add_argument("--expected-count", type=int, default=EXPECTED_COUNT)
    args = parser.parse_args()
    print(json.dumps({"written": build(args.output, args.expected_count), "output": str(args.output)}, ensure_ascii=False))
