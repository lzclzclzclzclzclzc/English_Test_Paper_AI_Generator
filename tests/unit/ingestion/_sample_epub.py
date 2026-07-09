"""Build a minimal EPUB in-memory for tests. Avoids checking a binary into the repo."""
from __future__ import annotations

from pathlib import Path

from ebooklib import epub


def build_sample_epub(path: Path, *, title: str = "Sample Book") -> Path:
    """Create a small EPUB at `path` with 3 chapters, return the path.

    Chapter shape (mirrors typical 中考英语 教辅 layout):
      Chapter 1: 单项选择 → h1 + h2 (语法) + h3 (时态)
      Chapter 2: 词性转换 → h1 + h2 (动词变名词)
      Chapter 3: 改写句子 → h1 + one paragraph
    """
    book = epub.EpubBook()
    book.set_identifier("id-sample-001")
    book.set_title(title)
    book.set_language("zh")
    book.add_author("Fixture Author")

    ch1 = epub.EpubHtml(title="Chapter 1", file_name="chap_01.xhtml", lang="zh")
    ch1.content = (
        "<html><body>"
        "<h1>单项选择</h1>"
        "<h2>语法</h2>"
        "<h3>时态</h3>"
        "<p>I <b>have done</b> my homework.</p>"
        "<p>A) do  B) am doing  C) have done  D) had done</p>"
        "</body></html>"
    )
    ch2 = epub.EpubHtml(title="Chapter 2", file_name="chap_02.xhtml", lang="zh")
    ch2.content = (
        "<html><body>"
        "<h1>词性转换</h1>"
        "<h2>动词变名词</h2>"
        "<p>decide → <em>decision</em></p>"
        "</body></html>"
    )
    ch3 = epub.EpubHtml(title="Chapter 3", file_name="chap_03.xhtml", lang="zh")
    ch3.content = (
        "<html><body>"
        "<h1>改写句子</h1>"
        "<p>Rewrite: <i>She can sing.</i> → She is able to sing.</p>"
        "</body></html>"
    )

    for ch in (ch1, ch2, ch3):
        book.add_item(ch)

    book.toc = (ch1, ch2, ch3)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch1, ch2, ch3]

    path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(path), book)
    return path
