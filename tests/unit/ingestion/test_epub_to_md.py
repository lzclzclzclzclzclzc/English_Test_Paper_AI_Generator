"""Unit tests for ingestion.epub_to_md.

Contract (Spec A § 3.2):
- Read EPUB, produce one .md per HTML section
- Preserve h1 / h2 / h3 heading levels
- Emit manifest.json mapping section_index → source info
- Slug books by their `book_slug` parameter (deterministic dir name)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.epub_to_md import convert_epub_to_md
from tests.unit.ingestion._sample_epub import build_sample_epub


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    return build_sample_epub(tmp_path / "sample.epub", title="Sample Book")


def test_convert_creates_output_dir(sample_epub: Path, tmp_path: Path) -> None:
    out_root = tmp_path / "raw_md"
    result = convert_epub_to_md(sample_epub, out_root=out_root, book_slug="sample")
    assert result.book_dir == out_root / "sample"
    assert result.book_dir.is_dir()


def test_convert_writes_one_md_per_section(sample_epub: Path, tmp_path: Path) -> None:
    out_root = tmp_path / "raw_md"
    result = convert_epub_to_md(sample_epub, out_root=out_root, book_slug="sample")

    # 3 chapters in the sample; ebooklib may also expose a nav doc — we filter to
    # content documents only (see impl). Contract: at least the 3 chapters land.
    md_files = sorted(result.book_dir.glob("*.md"))
    assert len(md_files) >= 3

    # Names follow zero-padded section_index scheme.
    assert all(f.stem.isdigit() for f in md_files)
    assert md_files[0].stem == "000"


def test_convert_preserves_heading_levels(sample_epub: Path, tmp_path: Path) -> None:
    out_root = tmp_path / "raw_md"
    result = convert_epub_to_md(sample_epub, out_root=out_root, book_slug="sample")

    # Concatenate all md; chapter 1 has h1/h2/h3, chapter 2 has h1/h2, chapter 3 h1.
    all_md = "\n".join(p.read_text(encoding="utf-8") for p in result.book_dir.glob("*.md"))
    assert "# 单项选择" in all_md
    assert "## 语法" in all_md
    assert "### 时态" in all_md
    assert "# 词性转换" in all_md
    assert "## 动词变名词" in all_md
    assert "# 改写句子" in all_md


def test_convert_writes_manifest(sample_epub: Path, tmp_path: Path) -> None:
    out_root = tmp_path / "raw_md"
    result = convert_epub_to_md(sample_epub, out_root=out_root, book_slug="sample")

    manifest_path = result.book_dir / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Spec A § 3.2: manifest records section order + original HTML file names.
    assert manifest["book_slug"] == "sample"
    assert manifest["title"] == "Sample Book"
    assert isinstance(manifest["sections"], list)
    # Every section entry has the fields we need for later traceability.
    for entry in manifest["sections"]:
        assert set(entry.keys()) >= {"index", "md_file", "source_href"}
        assert entry["md_file"].endswith(".md")


def test_convert_is_idempotent(sample_epub: Path, tmp_path: Path) -> None:
    """Running twice on the same input produces identical output."""
    out_root = tmp_path / "raw_md"
    r1 = convert_epub_to_md(sample_epub, out_root=out_root, book_slug="sample")
    files1 = {p.name: p.read_bytes() for p in r1.book_dir.iterdir()}

    r2 = convert_epub_to_md(sample_epub, out_root=out_root, book_slug="sample")
    files2 = {p.name: p.read_bytes() for p in r2.book_dir.iterdir()}

    assert files1 == files2


def test_convert_rejects_missing_epub(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        convert_epub_to_md(
            tmp_path / "does_not_exist.epub",
            out_root=tmp_path / "raw_md",
            book_slug="sample",
        )
