import logging
import math
from typing import List, Optional
import numpy as np
from app.config import settings

logger = logging.getLogger("ai_file_search.embedding")


class EmbeddingManager:
    _instance: Optional["EmbeddingManager"] = None
    _model = None
    _dimension: int = 384
    _is_ready: bool = False
    _model_name: str = settings.EMBEDDING_MODEL

    def __init__(self):
        self._model_name = settings.EMBEDDING_MODEL
        self._device = settings.EMBEDDING_DEVICE
        self._load_model()

    @classmethod
    def get_instance(cls) -> "EmbeddingManager":
        if cls._instance is None:
            cls._instance = EmbeddingManager()
        return cls._instance

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading pretrained embedding model '{self._model_name}' on device '{self._device}'...")
            self._model = SentenceTransformer(self._model_name, device=self._device)
            # Detect dimension
            dummy = self._model.encode(["test"], normalize_embeddings=True)
            self._dimension = int(dummy.shape[1])
            self._is_ready = True
            logger.info(f"Embedding model '{self._model_name}' ready. Vector dimension: {self._dimension}")
        except Exception as e:
            logger.warning(
                f"SentenceTransformer load failed ({e}). "
                "Operating in fallback deterministic dense embedding mode for offline/resilient bootstrap."
            )
            self._model = None
            self._dimension = 384
            self._is_ready = True

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch encode texts into normalized float vectors."""
        if not texts:
            return []

        if self._model is not None:
            try:
                embeddings = self._model.encode(
                    texts,
                    batch_size=32,
                    show_progress_bar=False,
                    normalize_embeddings=True
                )
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                logger.error(f"Error during batch encoding: {e}. Falling back to resilient projection.")

        # Resilient offline fallback embedding (deterministic hashing vectorizer normalized)
        return [self._fallback_embed(t) for t in texts]

    def encode_query(self, query: str) -> List[float]:
        """Single query embedding for search."""
        batch = self.encode_batch([query])
        return batch[0] if batch else [0.0] * self._dimension

    def _fallback_embed(self, text: str) -> List[float]:
        """
        Cryptographically deterministic 384-dimensional dense semantic feature hashing
        using subword n-grams and L2-normalization (Weinberger et al. Feature Hashing).
        Guarantees 100% reproducible embeddings across processes and restarts.
        """
        import hashlib
        import re

        vec = np.zeros(self._dimension, dtype=np.float32)
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec.tolist()

        for word in words:
            # 1. Unigram feature
            h = int.from_bytes(hashlib.md5(f"w:{word}".encode("utf-8")).digest()[:8], "little")
            idx = h % self._dimension
            sign = 1.0 if (h & 1) else -1.0
            vec[idx] += sign * 1.5

            # 2. Subword character n-grams (3-grams and 4-grams) for Indonesian/English morphology
            if len(word) >= 4:
                for n in (3, 4):
                    for i in range(len(word) - n + 1):
                        ngram = word[i:i + n]
                        h_ng = int.from_bytes(hashlib.md5(f"ng:{ngram}".encode("utf-8")).digest()[:8], "little")
                        idx_ng = h_ng % self._dimension
                        sign_ng = 1.0 if (h_ng & 1) else -1.0
                        vec[idx_ng] += sign_ng * 0.5

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.tolist()



def get_embedding_manager() -> EmbeddingManager:
    return EmbeddingManager.get_instance()
