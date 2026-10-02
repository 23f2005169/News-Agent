"""Embedding helpers for backend services."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer


DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def get_embedding_model(model_name: str = DEFAULT_MODEL_NAME) -> SentenceTransformer:
    """Load and cache the embedding model once per process."""
    return SentenceTransformer(model_name)


def embed_texts(texts: List[str], model_name: str = DEFAULT_MODEL_NAME) -> list[list[float]]:
    """Embed a batch of texts into dense vectors."""
    model = get_embedding_model(model_name)
    vectors = model.encode(texts, show_progress_bar=False)
    return [vector.tolist() for vector in vectors]


def embed_text(text: str, model_name: str = DEFAULT_MODEL_NAME) -> list[float]:
    """Embed a single text string into one vector."""
    return get_embedding_model(model_name).encode(text).tolist()