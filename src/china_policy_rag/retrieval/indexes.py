"""Safe JSON/NumPy persistent indexes; NumPy is always loaded with pickle disabled."""

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from china_policy_rag.models import PolicyDocument, SourceChunk

from .embeddings import EmbeddingProvider, _tokens

INDEX_VERSION = "phase2-index-v1"


def load_corpus(chunks_path: Path) -> tuple[list[SourceChunk], dict[str, PolicyDocument], str]:
    """Load trusted project JSONL and fingerprint its bytes with its sibling documents file."""
    documents_path = chunks_path.parent / "documents.jsonl"
    if not chunks_path.is_file() or not documents_path.is_file():
        raise FileNotFoundError("chunks.jsonl and sibling documents.jsonl are required")
    digest = sha256(chunks_path.read_bytes() + documents_path.read_bytes()).hexdigest()
    chunks = [
        SourceChunk.model_validate_json(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    documents = {
        str(item.document_id): item
        for item in (
            PolicyDocument.model_validate_json(line)
            for line in documents_path.read_text(encoding="utf-8").splitlines()
            if line
        )
    }
    if not chunks:
        raise ValueError("Cannot build an index from an empty corpus")
    return chunks, documents, digest


def build_indexes(
    chunks_path: Path, index_dir: Path, provider: EmbeddingProvider, overwrite: bool
) -> dict[str, object]:
    chunks, _, corpus_hash = load_corpus(chunks_path)
    index_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = index_dir / "index_manifest.json"
    if manifest_path.exists() and not overwrite:
        raise FileExistsError("Index already exists; use --overwrite to rebuild")
    token_lists = [_tokens(chunk.text) for chunk in chunks]
    document_frequency: Counter[str] = Counter(
        token for tokens in token_lists for token in set(tokens)
    )
    vectors = provider.embed_documents([chunk.text for chunk in chunks])
    if vectors.shape != (len(chunks), provider.dimension) or not np.isfinite(vectors).all():
        raise ValueError("Embedding provider returned invalid vectors")
    np.save(index_dir / "vectors.npy", vectors, allow_pickle=False)
    (index_dir / "lexical_index.json").write_text(
        json.dumps({"tokens": token_lists, "df": document_frequency, "version": INDEX_VERSION}),
        encoding="utf-8",
    )
    (index_dir / "chunk_ids.json").write_text(
        json.dumps([str(chunk.chunk_id) for chunk in chunks]), encoding="utf-8"
    )
    manifest = {
        "index_version": INDEX_VERSION,
        "chunks_path": str(chunks_path.resolve()),
        "corpus_hash": corpus_hash,
        "chunk_count": len(chunks),
        "embedding_model": provider.model_id,
        "dimension": provider.dimension,
        "normalized": True,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_indexes(
    index_dir: Path, provider: EmbeddingProvider
) -> tuple[
    list[SourceChunk],
    dict[str, PolicyDocument],
    dict[str, object],
    list[list[str]],
    NDArray[np.float64],
]:
    manifest = json.loads((index_dir / "index_manifest.json").read_text(encoding="utf-8"))
    if (
        manifest["embedding_model"] != provider.model_id
        or manifest["dimension"] != provider.dimension
    ):
        raise ValueError("Saved index does not match embedding provider configuration")
    chunks, documents, corpus_hash = load_corpus(Path(manifest["chunks_path"]))
    if corpus_hash != manifest["corpus_hash"]:
        raise ValueError("Index is stale because the processed corpus has changed; rebuild it")
    lexical = json.loads((index_dir / "lexical_index.json").read_text(encoding="utf-8"))
    vectors = np.load(index_dir / "vectors.npy", allow_pickle=False)
    if vectors.shape != (len(chunks), provider.dimension) or not np.isfinite(vectors).all():
        raise ValueError("Saved vector index is invalid")
    return chunks, documents, manifest, lexical["tokens"], vectors
