"""Ingestion CLI. See Spec A § 3.9 for the full six-command surface.

For M1 stage 1 only `epub-to-md` is implemented; later stages will add
`split-chapters`, `build-kb-draft`, `extract`, `load`.
"""
from __future__ import annotations

from pathlib import Path

import typer

from ingestion.apply_knowledge_tree import apply_all as apply_kp_all
from ingestion.assign_ids import assign_ids
from ingestion.chapter_splitter import split_book, write_split_result
from ingestion.chromadb.loader import load as chroma_load, search as chroma_search
from ingestion.epub_to_md import convert_epub_to_md
from ingestion.sqlite.loader import load as sqlite_load

app = typer.Typer(add_completion=False, help="EPUB → Markdown → 题库 pipeline (Spec A).")


@app.callback()
def _root() -> None:
    """Multi-command entry (Spec A § 3.9). Later stages add split-chapters,
    build-kb-draft, extract, load. The empty callback forces Typer into
    multi-command mode even when only one subcommand exists.
    """


@app.command("epub-to-md")
def epub_to_md_cmd(
    epub_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True,
                                     help="Path to input .epub file."),
    book_slug: str = typer.Option(None, "--slug",
                                  help="Directory name under data/raw_md/. "
                                       "Defaults to the epub filename stem."),
    out_root: Path = typer.Option(Path("data/raw_md"), "--out",
                                  help="Root output directory."),
) -> None:
    """Stage 1: convert an EPUB into per-section Markdown + manifest.json."""
    slug = book_slug or epub_path.stem
    result = convert_epub_to_md(epub_path, out_root=out_root, book_slug=slug)
    typer.echo(f"✓ wrote {len(result.sections)} section(s) to {result.book_dir}")


@app.command("split")
def split_cmd(
    book_slug: str = typer.Argument(..., help="Book slug (subdir under raw_md)."),
    raw_md_root: Path = typer.Option(Path("data/raw_md"), "--raw",
                                     help="Root of per-book markdown dirs."),
    out_root: Path = typer.Option(Path("data/chapters"), "--out",
                                  help="Output root for parsed JSON."),
) -> None:
    """Stage 2: parse a book's four markdown files → RawQuestion JSON list."""
    book_dir = raw_md_root / book_slug
    if not book_dir.is_dir():
        raise typer.BadParameter(f"missing book dir: {book_dir}")
    result = split_book(book_dir, book_slug=book_slug)

    out_path = out_root / f"{book_slug}.json"
    write_split_result(result, out_path)

    typer.echo(f"✓ wrote {len(result.questions)} question(s) to {out_path}")
    typer.echo("  per-type:")
    for qtype, n in result.stats.per_type_ok.items():
        typer.echo(f"    {qtype:22s} {n}")
    if result.stats.discarded:
        typer.echo("  discarded:")
        for reason, n in sorted(result.stats.discarded.items()):
            typer.echo(f"    {reason:30s} {n}")


@app.command("apply-kp")
def apply_kp_cmd(
    tree_path: Path = typer.Option(Path("data/kb/knowledge_tree.json"), "--tree",
                                   help="Reviewed knowledge tree JSON."),
    chapters_dir: Path = typer.Option(Path("data/chapters"), "--chapters",
                                      help="Directory with per-book chapters JSON."),
) -> None:
    """Stage 3b: fill knowledge_point_ids in each question by looking up the
    (question_type, chapter_l1, chapter_l2) three-segment key."""
    stats = apply_kp_all(tree_path=tree_path, chapters_dir=chapters_dir)
    typer.echo("✓ applied knowledge tree")
    typer.echo(stats.format())
    typer.echo("  top KP by题量 (前 15):")
    for kp_id, n in stats.per_kp_count.most_common(15):
        typer.echo(f"    {kp_id:32s} {n:4d}")


@app.command("assign-ids")
def assign_ids_cmd(
    chapters_dir: Path = typer.Option(Path("data/chapters"), "--chapters",
                                      help="Directory with per-book chapters JSON."),
) -> None:
    """Stage 3c: assign globally-monotonic `id` (q_NNNNN) to every question.
    Idempotent — existing ids are preserved; only questions missing an `id`
    get a fresh one from the next unused number."""
    stats = assign_ids(chapters_dir)
    typer.echo(f"✓ processed {stats.total} question(s)")
    typer.echo(f"    preserved existing ids : {stats.preserved}")
    typer.echo(f"    newly assigned         : {stats.assigned}")
    for slug, (min_id, max_id) in stats.per_book.items():
        typer.echo(f"    {slug:24s} {min_id} .. {max_id}")


@app.command("build-sqlite")
def build_sqlite_cmd(
    tree_path: Path = typer.Option(Path("data/kb/knowledge_tree.json"), "--tree",
                                   help="Reviewed knowledge tree JSON."),
    chapters_dir: Path = typer.Option(Path("data/chapters"), "--chapters",
                                      help="Directory with per-book chapters JSON."),
    db_path: Path = typer.Option(Path("data/questions.db"), "--db",
                                 help="Target SQLite database file."),
) -> None:
    """Stage 4: create/populate the SQLite question bank (Spec §3.7).
    Idempotent — rerunning skips rows that already exist by primary key."""
    stats = sqlite_load(tree_path=tree_path, chapters_dir=chapters_dir, db_path=db_path)
    typer.echo(f"✓ wrote SQLite DB: {db_path}")
    typer.echo(stats.summary())


@app.command("build-vec")
def build_vec_cmd(
    sqlite_path: Path = typer.Option(Path("data/questions.db"), "--db",
                                     help="SQLite question bank to read from."),
    chroma_dir: Path = typer.Option(Path("data/chroma"), "--chroma",
                                    help="Destination Chroma persistent directory."),
    model_dir: Path = typer.Option(Path("models/qwen3-embedding-4b"), "--model",
                                   help="Pre-downloaded Qwen3-Embedding-4B directory."),
) -> None:
    """Stage 5: build the ChromaDB `questions` collection (Spec §3.8).
    Reads SQLite → generates embedding_text → encodes with Qwen3-Embedding-4B
    → writes vectors + metadata. Idempotent — skips ids already in the collection."""
    from ingestion.chromadb.embedder import EmbedderConfig

    cfg = EmbedderConfig(model_dir=model_dir)
    stats = chroma_load(sqlite_path=sqlite_path, chroma_dir=chroma_dir, embedder_cfg=cfg)
    typer.echo(f"✓ wrote ChromaDB: {chroma_dir}")
    typer.echo(stats.summary())


@app.command("search-vec")
def search_vec_cmd(
    query: str = typer.Argument(..., help="Natural-language query to search for."),
    n: int = typer.Option(5, "-n", help="Number of results."),
    question_type: str = typer.Option(None, "--qt",
                                      help="Optional filter: single_choice / word_form / sentence_rewriting."),
    book: str = typer.Option(None, "--book", help="Optional filter: book slug."),
    chroma_dir: Path = typer.Option(Path("data/chroma"), "--chroma",
                                    help="Chroma persistent directory."),
    model_dir: Path = typer.Option(Path("models/qwen3-embedding-4b"), "--model",
                                   help="Qwen3-Embedding-4B directory."),
) -> None:
    """Quick similarity search against the ChromaDB collection — sanity check
    the vector store after building it. Not the AI Engine's real Retriever."""
    from ingestion.chromadb.embedder import EmbedderConfig

    cfg = EmbedderConfig(model_dir=model_dir)
    hits = chroma_search(
        query, n_results=n,
        question_type=question_type, book=book,
        chroma_dir=chroma_dir, embedder_cfg=cfg,
    )
    typer.echo(f"query: {query!r}")
    typer.echo(f"top-{n} hits:")
    for i, h in enumerate(hits, 1):
        typer.echo(f"\n─── #{i}  {h['id']}  (distance={h['distance']:.4f}) ───")
        typer.echo(f"  {h['metadata']['question_type']}  {h['metadata']['chapter_l1']} / {h['metadata']['chapter_l2']}")
        typer.echo(f"  kp: {h['metadata']['kp_ids']}")
        # Indent multi-line document for readability.
        for line in h["document"].splitlines():
            typer.echo(f"    {line}")


if __name__ == "__main__":
    app()
