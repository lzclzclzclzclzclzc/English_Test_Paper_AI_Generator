"""Stage 1 of the ingestion pipeline: EPUB → Markdown.

Spec A § 3.2:
  - Read EPUB with `ebooklib`
  - Extract HTML sections, convert to Markdown via html2text (h1–h3 preserved)
  - Emit `data/raw_md/<book_slug>/<section_index>.md` (one per section)
  - Emit `manifest.json` recording section order + original HTML file names

Pure script — no LLM, no network. Idempotent: rerunning overwrites deterministically.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import ebooklib
import html2text
from bs4 import BeautifulSoup
from ebooklib import epub


# Some 教辅 EPUB (e.g. 林烜《上海中考试题分类汇编》系列) don't use real
# <h1>/<h2>/<h3> tags. Instead they mark headings via CSS class on <p>.
# We normalize these to real heading tags before handing HTML to html2text,
# so the produced Markdown carries the # / ## / ### hierarchy Spec A § 3.2
# requires.
#
# Additions here should be safe (matching only a specific class on <p>) —
# books that already use real headings are unaffected.
CLASS_TO_HEADING: dict[str, str] = {
    "chapterTitle": "h1",
    "sectionTitle": "h2",
    "listTitle1":   "h3",
    "listTitle2":   "h4",
}

# `toc_*` variants only appear inside the EPUB's own table-of-contents page;
# promoting them to real headings would duplicate the outline. Skip explicitly.
SKIP_HEADING_CLASSES: frozenset[str] = frozenset({
    "toc_chapterTitle",
    "toc_sectionTitle",
    "toc_listTitle1",
    "toc_listTitle2",
})


@dataclass(frozen=True)
class SectionEntry:
    """One entry in manifest.sections."""
    index: int
    md_file: str        # relative filename inside book_dir
    source_href: str    # original EPUB item file_name (for traceability)
    title: str | None   # from EPUB item, if any


@dataclass(frozen=True)
class ConvertResult:
    book_dir: Path
    sections: list[SectionEntry]


def _make_html2text() -> html2text.HTML2Text:
    """Configured converter: keep headings, plain output, no wrapping."""
    h = html2text.HTML2Text()
    h.body_width = 0          # no line wrapping — preserves paragraphs verbatim
    h.ignore_links = False
    h.ignore_images = True     # Spec A § 1.1: no images
    h.ignore_emphasis = False
    h.unicode_snob = True      # keep unicode instead of transliterating
    h.single_line_break = False
    return h


def _normalize_class_headings(soup: BeautifulSoup) -> None:
    """Rewrite class-based pseudo-headings to real <h1>/<h2>/<h3>.

    Many 教辅 EPUB (this project's Shanghai 中考 sources included) skip real
    heading tags and instead mark titles via CSS class on <p>. html2text has
    no way to see that intent, so unless we rewrite the tags the output is
    a flat wall of paragraphs and Spec A § 3.2 ("h1–h3 preserved") fails.

    Books that already use real <h1>..<h6> are unaffected: we only touch
    <p class="..."> elements whose class appears in CLASS_TO_HEADING.
    """
    for p in soup.find_all("p"):
        classes = p.get("class") or []
        # `class` may be a str depending on parser; normalize to list.
        if isinstance(classes, str):
            classes = classes.split()

        # Skip the TOC copies of these titles first — otherwise the outer
        # loop would still match a real heading class if a book combined them.
        if any(c in SKIP_HEADING_CLASSES for c in classes):
            continue

        for c in classes:
            heading_tag = CLASS_TO_HEADING.get(c)
            if heading_tag is None:
                continue
            p.name = heading_tag
            # Drop the class list so html2text doesn't emit any residue.
            del p["class"]
            break


def _html_to_markdown(raw_html: bytes | str, converter: html2text.HTML2Text) -> str:
    """Convert one HTML doc to markdown; strip empty leading/trailing whitespace."""
    # EPUB payloads are XHTML — using an HTML parser triggers
    # XMLParsedAsHTMLWarning and, more importantly, can mishandle
    # self-closing tags and namespaces. Prefer BeautifulSoup's XML mode when
    # the doc declares itself XML, and fall back to lxml (HTML) otherwise.
    html_str = raw_html.decode("utf-8", errors="replace") if isinstance(raw_html, bytes) else raw_html
    parser = "lxml-xml" if html_str.lstrip().startswith("<?xml") else "lxml"
    soup = BeautifulSoup(html_str, parser)
    _normalize_class_headings(soup)
    cleaned = str(soup)
    md = converter.handle(cleaned)
    return md.strip() + "\n"


def convert_epub_to_md(
    epub_path: Path,
    *,
    out_root: Path,
    book_slug: str,
) -> ConvertResult:
    """Convert an EPUB into per-section Markdown files under `out_root/<book_slug>/`.

    Parameters
    ----------
    epub_path : Path
        Path to a `.epub` file.
    out_root : Path
        Root directory under which `<book_slug>/` will be created.
    book_slug : str
        Deterministic short name for this book (used as dir name). Caller is
        responsible for choosing a slug; we do not derive it from metadata to
        avoid surprises when book titles contain punctuation or spaces.

    Returns
    -------
    ConvertResult
        - book_dir: `out_root / book_slug`
        - sections: list of SectionEntry, one per written .md file, in order.

    Raises
    ------
    FileNotFoundError
        If `epub_path` doesn't exist.
    """
    if not epub_path.is_file():
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    book = epub.read_epub(str(epub_path))
    book_dir = out_root / book_slug
    book_dir.mkdir(parents=True, exist_ok=True)

    converter = _make_html2text()

    # Iterate content documents in spine order. `get_items_of_type(ITEM_DOCUMENT)`
    # returns them in manifest order; ebooklib doesn't expose spine order directly
    # in a stable way across versions, but manifest order matches for typical books.
    # If a book's spine differs, extractor stages downstream can still find content
    # by chapter path, so absolute reading order is not critical here.
    documents = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

    sections: list[SectionEntry] = []
    for idx, item in enumerate(documents):
        # Skip the nav document — it's a table of contents, not chapter content.
        # ebooklib marks it via `is_chapter()` being False for EpubNav items.
        if item.get_name().lower() in {"nav.xhtml", "nav.html"}:
            continue
        md_text = _html_to_markdown(item.get_content(), converter)
        # Skip completely empty sections (e.g. cover pages with only images).
        if not md_text.strip():
            continue

        section_index = len(sections)
        md_filename = f"{section_index:03d}.md"
        (book_dir / md_filename).write_text(md_text, encoding="utf-8")

        sections.append(
            SectionEntry(
                index=section_index,
                md_file=md_filename,
                source_href=item.get_name(),
                title=_extract_item_title(item),
            )
        )

    manifest = {
        "book_slug": book_slug,
        "title": _extract_book_title(book),
        "source_epub": epub_path.name,
        "sections": [
            {
                "index": s.index,
                "md_file": s.md_file,
                "source_href": s.source_href,
                "title": s.title,
            }
            for s in sections
        ],
    }
    (book_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ConvertResult(book_dir=book_dir, sections=sections)


def _extract_book_title(book: epub.EpubBook) -> str | None:
    md = book.get_metadata("DC", "title")
    if md and md[0] and md[0][0]:
        return md[0][0]
    return None


def _extract_item_title(item: epub.EpubItem) -> str | None:
    """Prefer the `title` attribute set on EpubHtml; fall back to <title>/<h1>."""
    title = getattr(item, "title", None)
    if title:
        return title
    try:
        raw = item.get_content()
        html_str = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        parser = "lxml-xml" if html_str.lstrip().startswith("<?xml") else "lxml"
        soup = BeautifulSoup(html_str, parser)
    except Exception:
        return None
    for sel in ("title", "h1", "h2"):
        tag = soup.find(sel)
        if tag and tag.get_text(strip=True):
            return tag.get_text(strip=True)
    return None
