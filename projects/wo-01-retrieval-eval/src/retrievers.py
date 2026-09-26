"""Chunked BM25, dense cosine, document-level RRF, and cross-encoder reranking."""

import hashlib
import json
import re
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
from numpy.typing import NDArray
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from .evaluate import Run
from .load import Corpus, Queries

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
CHUNK_OVERLAP = 24
MAX_EMBEDDING_TOKENS = 256
RETRIEVAL_LIMIT = 50
RRF_RANK_CONSTANT = 60
EMBED_BATCH_SIZE = 64
RERANK_BATCH_SIZE = 32
RERANK_LIMIT = 20
RERANK_MAX_LENGTH = 512
PROGRESS_INTERVAL = 50


class Tokenizer(Protocol):
    """Minimal tokenizer surface required by the chunker."""

    def encode(self, text: str, **kwargs: object) -> list[int]:
        """Encode text as integer token identifiers."""
        ...

    def decode(self, token_ids: Sequence[int], **kwargs: object) -> str:
        """Decode integer token identifiers back to text."""
        ...


def lexical_tokens(text: str) -> list[str]:
    """Normalize English alphanumeric terms for BM25."""
    return TOKEN_RE.findall(text.lower())


def make_chunks(
    corpus: Corpus,
    tokenizer: Tokenizer,
    size: int,
    overlap: int = CHUNK_OVERLAP,
) -> tuple[list[str], list[str]]:
    """Split documents into overlapping model-token chunks and retain parent IDs."""
    if size > MAX_EMBEDDING_TOKENS or size <= overlap:
        raise ValueError("MiniLM supports at most 256 wordpieces; size must exceed overlap")
    chunks: list[str] = []
    parents: list[str] = []
    for docid, row in corpus.items():
        text = f"{row.get('title', '')}. {row.get('text', '')}".strip()
        tokens = tokenizer.encode(text, add_special_tokens=False, verbose=False)
        step = size - overlap
        for start in range(0, len(tokens), step):
            part = tokenizer.decode(tokens[start : start + size], skip_special_tokens=True)
            if part.strip():
                chunks.append(part)
                parents.append(docid)
            if start + size >= len(tokens):
                break
    return chunks, parents


def _rank_parent_docs(
    scores: NDArray[np.floating],
    parents: Sequence[str],
    limit: int = RETRIEVAL_LIMIT,
) -> list[str]:
    """Collapse chunk scores to the best occurrence of each parent document."""
    order = np.argsort(-scores, kind="stable")
    ranked: list[str] = []
    seen: set[str] = set()
    for index in order:
        docid = parents[index]
        if docid not in seen:
            ranked.append(docid)
            seen.add(docid)
            if len(ranked) == limit:
                break
    return ranked


def bm25_runs(
    chunks: list[str],
    parents: list[str],
    queries: Queries,
    limit: int = RETRIEVAL_LIMIT,
) -> Run:
    """Retrieve parent documents with chunk-level BM25 scores."""
    index = BM25Okapi([lexical_tokens(chunk) for chunk in chunks])
    return {
        qid: _rank_parent_docs(index.get_scores(lexical_tokens(query)), parents, limit)
        for qid, query in queries.items()
    }


def dense_runs(
    model: SentenceTransformer,
    chunks: list[str],
    parents: list[str],
    queries: Queries,
    cache_dir: Path,
    size: int,
    limit: int = RETRIEVAL_LIMIT,
) -> Run:
    """Retrieve parent documents by maximum chunk cosine similarity."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        [EMBED_MODEL, size, parents, chunks], ensure_ascii=False
    ).encode()
    fingerprint = hashlib.sha256(serialized).hexdigest()[:16]
    cache = cache_dir / f"embeddings-{size}-{fingerprint}.npy"
    if cache.exists():
        embeddings = np.load(cache)
    else:
        embeddings = model.encode(
            chunks,
            batch_size=EMBED_BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        np.save(cache, embeddings)
    qids = list(queries)
    query_vectors = model.encode(
        [queries[qid] for qid in qids],
        batch_size=EMBED_BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    runs: Run = {}
    for qid, vector in zip(qids, query_vectors):
        scores = embeddings @ vector
        runs[qid] = _rank_parent_docs(scores, parents, limit)
    return runs


def rrf_runs(
    first: Run,
    second: Run,
    limit: int = RETRIEVAL_LIMIT,
    k: int = RRF_RANK_CONSTANT,
) -> Run:
    """Fuse two document rankings with Reciprocal Rank Fusion."""
    result: Run = {}
    for qid in first:
        scores: dict[str, float] = {}
        for ranking in (first[qid], second[qid]):
            for position, docid in enumerate(ranking, 1):
                scores[docid] = scores.get(docid, 0.0) + 1.0 / (k + position)
        result[qid] = sorted(scores, key=lambda doc: (-scores[doc], doc))[:limit]
    return result


def rerank_runs(
    runs: Run,
    corpus: Corpus,
    queries: Queries,
    top_n: int = RERANK_LIMIT,
) -> Run:
    """Cross-encode the leading candidates while preserving the remaining tail."""
    cross_encoder = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LENGTH)
    output: Run = {}
    for count, (qid, ranking) in enumerate(runs.items(), 1):
        candidates = ranking[:top_n]
        pairs = [
            (
                queries[qid],
                f"{corpus[doc].get('title', '')}. {corpus[doc].get('text', '')}",
            )
            for doc in candidates
        ]
        scores = cross_encoder.predict(
            pairs, batch_size=RERANK_BATCH_SIZE, show_progress_bar=False
        )
        reordered = sorted(zip(candidates, scores), key=lambda pair: -float(pair[1]))
        output[qid] = [doc for doc, _ in reordered] + ranking[top_n:]
        if count % PROGRESS_INTERVAL == 0:
            print(f"Reranked {count}/{len(runs)} queries", flush=True)
    return output
