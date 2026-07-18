"""Qwen3-Embedding-4B wrapper for the ChromaDB loader.

Loads the model from a local path (assumed pre-downloaded — no network calls,
no HuggingFace hub lookups) using sentence-transformers.

Design notes
────────────
* Vector dim: **2560** (full Matryoshka output — Spec §1.3 default). Qwen
  supports smaller dims via truncation, but with 1066 questions the storage
  savings are not worth the retrieval-quality tradeoff.
* Distance: cosine, achieved by asking sentence-transformers to L2-normalise
  every output. ChromaDB's collection is created with `cosine` too; the two
  match end-to-end.
* Device: CUDA (Spec §1.3). Loading logs the actual GPU picked up.
* Batch size: 16 by default (per user, tunable at call site if OOM shows up).

The class deliberately holds a single model instance across its lifetime —
loading Qwen4B costs several seconds, and this loader may be reinvoked from
tests or notebooks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

# sentence-transformers is imported lazily inside methods so that this module
# can be safely `from ... import` even when the env doesn't yet have the
# heavy deps — matters for tests that only touch embedding_text.

log = logging.getLogger(__name__)


DEFAULT_MODEL_DIR = Path("models/Qwen3-Embedding-4B")
DEFAULT_DEVICE    = "cuda"
DEFAULT_BATCH     = 16
DEFAULT_DIM       = 2560


@dataclass
class EmbedderConfig:
    model_dir: Path = DEFAULT_MODEL_DIR
    device: str     = DEFAULT_DEVICE
    batch_size: int = DEFAULT_BATCH


class QwenEmbedder:
    """Thin wrapper around SentenceTransformer(Qwen3-Embedding-4B)."""

    def __init__(self, cfg: EmbedderConfig | None = None) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import

        self.cfg = cfg or EmbedderConfig()
        if not self.cfg.model_dir.is_dir():
            raise FileNotFoundError(
                f"Qwen model dir not found: {self.cfg.model_dir}. "
                "Expected the pre-downloaded Qwen3-Embedding-4B to live here."
            )

        log.info("loading Qwen3-Embedding-4B from %s on %s", self.cfg.model_dir, self.cfg.device)
        # `trust_remote_code=True` is not needed for this model — its custom
        # pooling is bundled as a proper sentence-transformers module.
        self._model = SentenceTransformer(str(self.cfg.model_dir), device=self.cfg.device)
        self._dim = self._model.get_sentence_embedding_dimension()
        log.info("model loaded; output dim = %d", self._dim)

    @property
    def dim(self) -> int:
        """Vector dimension — call sites need this to sanity-check ChromaDB collection state."""
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of strings to L2-normalised float vectors.

        Returns a plain `list[list[float]]` (not numpy) because ChromaDB's
        Python client wants that form and it survives JSON debugging traces.
        """
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=self.cfg.batch_size,
            normalize_embeddings=True,        # cosine ↔ inner product
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        # `.tolist()` yields nested Python lists — cheap on 1066×2560.
        return vectors.tolist()
