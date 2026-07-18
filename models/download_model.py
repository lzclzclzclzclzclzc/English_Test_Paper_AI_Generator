"""Download the local embedding model required by vector retrieval.

Run: python models/download_model.py
The model is stored in models/Qwen3-Embedding-4B and intentionally ignored by Git.
"""
from pathlib import Path


TARGET_DIR = Path(__file__).parent / "Qwen3-Embedding-4B"


def main() -> None:
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise SystemExit("Install project dependencies first: pip install -r requirements.txt") from exc
    path = snapshot_download(model_id="Qwen/Qwen3-Embedding-4B", local_dir=str(TARGET_DIR))
    size = sum(item.stat().st_size for item in TARGET_DIR.rglob("*") if item.is_file()) / 1024 ** 3
    print(f"Model saved to: {path}\nSize: {size:.2f} GB")


if __name__ == "__main__":
    main()
