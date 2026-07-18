"""
Download Qwen3-Embedding-4B from ModelScope (fastest in mainland China).

Usage:
    pip install modelscope
    python download_model.py

Saves to ./Qwen3-Embedding-4B (same path used by build_index.py / servicenow_mcp.py).
"""

from pathlib import Path
from modelscope import snapshot_download

TARGET_DIR = Path(__file__).parent / "Qwen3-Embedding-4B"

def main():
    print(f"Downloading Qwen3-Embedding-4B from ModelScope ...")
    print(f"Target: {TARGET_DIR.resolve()}")

    local_dir = snapshot_download(
        model_id="Qwen/Qwen3-Embedding-4B",
        local_dir=str(TARGET_DIR),
        # ModelScope mirrors HF but uses CDN nodes inside China — much faster.
    )

    print(f"\nDone. Model saved to: {local_dir}")

    # Sanity check: expected files
    expected = ["config.json", "tokenizer.json"]
    missing = [f for f in expected if not (TARGET_DIR / f).exists()]
    if missing:
        print(f"WARNING: missing files: {missing}")
    else:
        print("All key files present.")

    total_size = sum(f.stat().st_size for f in TARGET_DIR.rglob("*") if f.is_file())
    print(f"Total size: {total_size / 1024**3:.2f} GB")


if __name__ == "__main__":
    main()
