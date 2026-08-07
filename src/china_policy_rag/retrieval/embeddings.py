"""Replaceable local embedding providers with an offline deterministic test provider."""

import re
from hashlib import sha256
from importlib import import_module
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from .query import normalize_query


class EmbeddingProvider(Protocol):
    model_id: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> NDArray[np.float64]: ...

    def embed_query(self, text: str) -> NDArray[np.float64]: ...


class DeterministicHashEmbeddingProvider:
    """Stable hash vectors for tests only; these vectors are not semantic embeddings."""

    model_id = "deterministic-hash-v1"

    def __init__(self, dimension: int = 64) -> None:
        if dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        self.dimension = dimension

    def _embed(self, text: str) -> NDArray[np.float64]:
        vector = np.zeros(self.dimension, dtype=np.float64)
        for token in _tokens(normalize_query(text)):
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1.0 if digest[8] % 2 else -1.0
            vector[index] += sign
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def embed_documents(self, texts: list[str]) -> NDArray[np.float64]:
        return (
            np.vstack([self._embed(text) for text in texts])
            if texts
            else np.empty((0, self.dimension))
        )

    def embed_query(self, text: str) -> NDArray[np.float64]:
        return self._embed(text)


class SentenceTransformerEmbeddingProvider:
    """Lazy optional local provider; it never downloads models at import time."""

    def __init__(
        self,
        model_id: str,
        normalize: bool = True,
        batch_size: int = 32,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
    ) -> None:
        self.model_id = model_id
        self.normalize = normalize
        self.batch_size = batch_size
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self._model: Any | None = None
        self.dimension = 0

    def _load(self) -> Any:
        if self._model is None:
            try:
                sentence_transformers = import_module("sentence_transformers")
            except ImportError as error:
                raise RuntimeError(
                    "sentence-transformers is optional; install with `.[semantic]` to use it"
                ) from error
            self._model = sentence_transformers.SentenceTransformer(self.model_id, device="cpu")
            self.dimension = int(self._model.get_embedding_dimension())
        return self._model

    def embed_documents(self, texts: list[str]) -> NDArray[np.float64]:
        model = self._load()
        return np.asarray(
            model.encode(
                [f"{self.passage_prefix}{text}" for text in texts],
                batch_size=self.batch_size,
                normalize_embeddings=self.normalize,
            ),
            dtype=np.float64,
        )

    def embed_query(self, text: str) -> NDArray[np.float64]:
        model = self._load()
        return cast(
            NDArray[np.float64],
            np.asarray(
                model.encode(
                    [f"{self.query_prefix}{text}"],
                    batch_size=self.batch_size,
                    normalize_embeddings=self.normalize,
                ),
                dtype=np.float64,
            )[0],
        )


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]+|[\u3400-\u9fff]", text)
    return words or [text]


def provider_for(name: str, model: str | None = None) -> EmbeddingProvider:
    """Create a configured provider without loading optional models eagerly."""
    if name == "deterministic":
        return DeterministicHashEmbeddingProvider()
    if name == "sentence-transformers":
        if not model:
            raise ValueError("--embedding-model is required for sentence-transformers")
        return SentenceTransformerEmbeddingProvider(model)
    raise ValueError("Unsupported embedding provider; use deterministic or sentence-transformers")
