"""Build the learnable vocabulary list from the official core and Shanghai extension.

The Ministry document is the authority for membership in the national core list.
``dict.cn`` is used only for the short Chinese glosses of official terms that do
not already have an audited project gloss; it is never presented as the word-list
authority.  Example sentences are deliberately left as the hidden placeholder
until the separate example-content review is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORE = ROOT / "data/vocabulary/moe-2022-core-1600.json"
DEFAULT_SHANGHAI = ROOT / "data/vocabulary/shanghai-basic-1678.json"
DEFAULT_OUTPUT = ROOT / "data/vocabulary/national-core-plus-shanghai-extension.json"
DEFAULT_CACHE = ROOT / "data/vocabulary/dictcn-short-glosses.json"
PLACEHOLDER_EN = "Remember how to use {term} in a sentence."
PLACEHOLDER_ZH = "请结合释义记忆 {term} 的用法。"


def normalize(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower().replace("’", "'"))


def fetch_gloss(term: str) -> tuple[str, str]:
    """Fetch only the first short POS/Chinese gloss from a public dictionary page."""
    result = subprocess.run(
        ["curl.exe", "--http1.1", "--ssl-no-revoke", "--max-time", "12", "-sS", f"https://dict.cn/{quote(term)}"],
        check=True,
        capture_output=True,
    )
    page = result.stdout.decode("utf-8", errors="ignore")
    match = re.search(
        r'<li[^>]*>\s*<span[^>]*>(?P<pos>[^<]+)</span>\s*<strong>(?P<meaning>.*?)</strong>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("no basic gloss found")
    pos = html.unescape(re.sub(r"<[^>]+>", "", match.group("pos"))).strip()
    meaning = html.unescape(re.sub(r"<[^>]+>", "", match.group("meaning"))).strip()
    meaning = re.sub(r"\s+", " ", meaning).rstrip("；;，,")
    if not pos or not meaning:
        raise ValueError("empty basic gloss")
    return pos, meaning


def load_cache(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("glosses", {})


def enrich_missing(terms: list[str], cache: dict[str, dict[str, str]]) -> None:
    missing = [term for term in terms if term not in cache]
    if not missing:
        return
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        future_map = {pool.submit(fetch_gloss, term): term for term in missing}
        for future in as_completed(future_map):
            term = future_map[future]
            try:
                pos, meaning = future.result()
                cache[term] = {"part_of_speech": pos, "meaning": meaning}
            except Exception as exc:  # pragma: no cover - depends on remote HTML
                failures[term] = str(exc)
    if failures:
        failed = ", ".join(sorted(failures))
        raise RuntimeError(f"could not fetch short glosses for: {failed}")


def build(core_path: Path, shanghai_path: Path, output_path: Path, cache_path: Path, fetch_missing: bool) -> int:
    core = json.loads(core_path.read_text(encoding="utf-8"))
    shanghai = json.loads(shanghai_path.read_text(encoding="utf-8"))
    core_terms = core["terms"]
    if len(core_terms) != core["metadata"].get("expected_count") or len(set(core_terms)) != len(core_terms):
        raise ValueError("core list must contain its declared number of unique source terms")
    core_normalized = {normalize(term) for term in core_terms}
    existing_by_term = {normalize(word["term"]): word for word in shanghai["words"]}
    cache = load_cache(cache_path)
    missing_core = sorted(core_normalized - set(existing_by_term))
    if fetch_missing:
        enrich_missing(missing_core, cache)
        cache_path.write_text(
            json.dumps({"source": "https://dict.cn/", "glosses": cache}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    unresolved = [term for term in missing_core if term not in cache]
    if unresolved:
        raise RuntimeError("missing short-gloss cache; rerun with --fetch-missing-definitions")

    words: list[dict] = []
    for word in shanghai["words"]:
        copied = dict(word)
        copied["source_category"] = "national_core" if normalize(copied["term"]) in core_normalized else "shanghai_extension"
        words.append(copied)
    for index, term in enumerate(missing_core, start=1):
        gloss = cache[term]
        words.append(
            {
                "id": f"moe_core_{index:04d}",
                "term": term,
                "part_of_speech": gloss["part_of_speech"],
                "meanings": [gloss["meaning"]],
                "example_en": PLACEHOLDER_EN.format(term=term),
                "example_zh": PLACEHOLDER_ZH.format(term=term),
                "source_category": "national_core",
            }
        )
    normalized = [normalize(word["term"]) for word in words]
    if len(normalized) != len(set(normalized)):
        raise ValueError("merged word list contains duplicate normalized terms")

    core_meta = core["metadata"]
    shanghai_meta = shanghai["metadata"]
    output = {
        "metadata": {
            "id": "national-core-plus-shanghai-extension-v1",
            "label": "国家核心词 + 上海扩展词",
            "source_url": core_meta["source_url"],
            "source_accessed_at": core_meta["source_accessed_at"],
            "source_sha256": hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest(),
            "expected_count": len(words),
            "sources": [
                {
                    "category": "national_core",
                    "label": core_meta["label"],
                    "source_url": core_meta["source_url"],
                    "source_accessed_at": core_meta["source_accessed_at"],
                    "source_sha256": core_meta["source_sha256"],
                },
                {
                    "category": "shanghai_extension",
                    "label": shanghai_meta["label"],
                    "source_url": shanghai_meta["source_url"],
                    "source_accessed_at": shanghai_meta["source_accessed_at"],
                    "source_sha256": shanghai_meta["source_sha256"],
                },
            ],
        },
        "words": words,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(words)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, default=DEFAULT_CORE)
    parser.add_argument("--shanghai", type=Path, default=DEFAULT_SHANGHAI)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--fetch-missing-definitions", action="store_true")
    args = parser.parse_args()
    print(build(args.core, args.shanghai, args.output, args.cache, args.fetch_missing_definitions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
