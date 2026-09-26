"""Chunked BM25, FAISS HNSW dense retrieval, RRF, and cross-encoder reranking."""

import hashlib
import json
import re
from pathlib import Path
from typing import Protocol, Sequence

import faiss
import numpy as np
from numpy.typing import NDArray
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from .models import Chunk, Corpus, Queries, Run, SearchHit

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CHUNK_TOKENS = 128
CHUNK_OVERLAP = 24
MAX_MODEL_TOKENS = 256
RETRIEVAL_LIMIT = 50
DENSE_CHUNK_CANDIDATES = 1_000
HNSW_CONNECTIONS = 32
HNSW_CONSTRUCTION_DEPTH = 40
HNSW_SEARCH_DEPTH = 64
RRF_CONSTANT = 60
RERANK_CANDIDATES = 20
EMBED_BATCH_SIZE = 64
RERANK_BATCH_SIZE = 64
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


class Tokenizer(Protocol):
    """Minimal tokenizer operations needed for deterministic chunking."""

    def encode(self, text: str, **kwargs: object) -> list[int]:
        """Encode text into token identifiers."""
        ...

    def decode(self, token_ids: Sequence[int], **kwargs: object) -> str:
        """Decode token identifiers into text."""
        ...


def lexical_tokens(text: str) -> list[str]:
    """Return lower-cased alphanumeric tokens for BM25."""
    return TOKEN_PATTERN.findall(text.lower())


def chunk_corpus(
    corpus: Corpus,
    tokenizer: Tokenizer,
    size: int = CHUNK_TOKENS,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Split each document into overlapping model-token chunks."""
    if size > MAX_MODEL_TOKENS or size <= overlap:
        raise ValueError("Chunk size must exceed overlap and fit the embedding model")
    chunks: list[Chunk] = []
    for doc_id, document in corpus.items():
        text = f"{document.get('title', '')}. {document.get('text', '')}".strip()
        token_ids = tokenizer.encode(text, add_special_tokens=False, verbose=False)
        step = size - overlap
        chunk_number = 0
        for start in range(0, len(token_ids), step):
            part = tokenizer.decode(
                token_ids[start : start + size], skip_special_tokens=True
            ).strip()
            if part:
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc_id}#c{chunk_number}",
                        doc_id=doc_id,
                        text=part,
                    )
                )
                chunk_number += 1
            if start + size >= len(token_ids):
                break
    return chunks


class HybridIndex:
    """In-memory BM25 and FAISS HNSW indexes over the same chunks."""

    def __init__(
        self,
        chunks: list[Chunk],
        embedding_model: SentenceTransformer,
        cache_directory: Path,
    ) -> None:
        """Build lexical and vector indexes, reusing cached corpus embeddings."""
        if not chunks:
            raise ValueError("At least one chunk is required")
        self.chunks = chunks
        self.embedding_model = embedding_model
        self.bm25 = BM25Okapi([lexical_tokens(chunk.text) for chunk in chunks])
        embeddings = self._load_or_encode(cache_directory)
        faiss.omp_set_num_threads(1)
        dimension = int(embeddings.shape[1])
        self.vector_index = faiss.IndexHNSWFlat(
            dimension, HNSW_CONNECTIONS, faiss.METRIC_INNER_PRODUCT
        )
        self.vector_index.hnsw.efConstruction = HNSW_CONSTRUCTION_DEPTH
        self.vector_index.hnsw.efSearch = HNSW_SEARCH_DEPTH
        self.vector_index.add(embeddings)

    def _load_or_encode(self, cache_directory: Path) -> NDArray[np.float32]:
        """Load a matching embedding matrix or compute and cache it."""
        cache_directory.mkdir(parents=True, exist_ok=True)
        signature = hashlib.sha256(
            json.dumps(
                [EMBEDDING_MODEL, [(chunk.chunk_id, chunk.text) for chunk in self.chunks]],
                ensure_ascii=False,
            ).encode()
        ).hexdigest()[:16]
        cache_path = cache_directory / f"chunk-embeddings-{signature}.npy"
        if cache_path.exists():
            return np.asarray(np.load(cache_path), dtype=np.float32)
        embeddings = self.embedding_model.encode(
            [chunk.text for chunk in self.chunks],
            batch_size=EMBED_BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        ).astype(np.float32)
        np.save(cache_path, embeddings)
        return embeddings

    def bm25_search(self, query: str, limit: int = RETRIEVAL_LIMIT) -> list[SearchHit]:
        """Rank parent documents by their highest-scoring BM25 chunk."""
        scores = np.asarray(self.bm25.get_scores(lexical_tokens(query)))
        indices = np.argsort(-scores, kind="stable")
        return self._collapse(indices, scores, limit)

    def dense_search(self, query: str, limit: int = RETRIEVAL_LIMIT) -> list[SearchHit]:
        """Search normalized embeddings with a FAISS HNSW inner-product index."""
        vector = self.embedding_model.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True
        ).astype(np.float32)
        candidate_count = min(DENSE_CHUNK_CANDIDATES, len(self.chunks))
        scores, indices = self.vector_index.search(vector, candidate_count)
        return self._collapse(indices[0], scores[0], limit)

    def _collapse(
        self,
        indices: NDArray[np.integer],
        scores: NDArray[np.floating],
        limit: int,
    ) -> list[SearchHit]:
        """Keep the strongest retrieved chunk for each parent document."""
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for index, score in zip(indices, scores):
            position = int(index)
            if position < 0:
                continue
            chunk = self.chunks[position]
            if chunk.doc_id in seen:
                continue
            hits.append(
                SearchHit(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    score=float(score),
                )
            )
            seen.add(chunk.doc_id)
            if len(hits) == limit:
                break
        return hits


def rrf_fuse(
    first: list[SearchHit],
    second: list[SearchHit],
    limit: int = RETRIEVAL_LIMIT,
    rank_constant: int = RRF_CONSTANT,
) -> list[SearchHit]:
    """Fuse two rankings without normalizing their incompatible score scales."""
    scores: dict[str, float] = {}
    representatives: dict[str, SearchHit] = {}
    for ranking in (first, second):
        for rank, hit in enumerate(ranking, 1):
            scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + 1.0 / (
                rank_constant + rank
            )
            representatives.setdefault(hit.doc_id, hit)
    ranked_ids = sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))[:limit]
    return [
        SearchHit(
            chunk_id=representatives[doc_id].chunk_id,
            doc_id=doc_id,
            text=representatives[doc_id].text,
            score=scores[doc_id],
        )
        for doc_id in ranked_ids
    ]


def _rerank_all(
    queries: Queries,
    hybrid_hits: dict[str, list[SearchHit]],
    reranker: CrossEncoder,
) -> dict[str, list[SearchHit]]:
    """Cross-encode every query's leading hybrid candidates in one batch."""
    pairs: list[tuple[str, str]] = []
    spans: dict[str, tuple[int, int]] = {}
    for query_id, query in queries.items():
        candidates = hybrid_hits[query_id][:RERANK_CANDIDATES]
        start = len(pairs)
        pairs.extend((query, hit.text) for hit in candidates)
        spans[query_id] = (start, len(pairs))
    predictions = np.asarray(
        reranker.predict(pairs, batch_size=RERANK_BATCH_SIZE, show_progress_bar=True)
    )
    output: dict[str, list[SearchHit]] = {}
    for query_id, ranking in hybrid_hits.items():
        start, end = spans[query_id]
        candidates = ranking[:RERANK_CANDIDATES]
        rescored = [
            SearchHit(hit.chunk_id, hit.doc_id, hit.text, float(score))
            for hit, score in zip(candidates, predictions[start:end])
        ]
        rescored.sort(key=lambda hit: (-hit.score, hit.doc_id))
        output[query_id] = rescored + ranking[RERANK_CANDIDATES:]
    return output


def retrieve_all_stages(
    index: HybridIndex,
    queries: Queries,
    reranker: CrossEncoder,
) -> tuple[dict[str, Run], dict[str, list[SearchHit]]]:
    """Run BM25, dense, RRF hybrid, and reranked hybrid for every query."""
    bm25_hits: dict[str, list[SearchHit]] = {}
    dense_hits: dict[str, list[SearchHit]] = {}
    hybrid_hits: dict[str, list[SearchHit]] = {}
    for count, (query_id, query) in enumerate(queries.items(), 1):
        sparse = index.bm25_search(query)
        dense = index.dense_search(query)
        bm25_hits[query_id] = sparse
        dense_hits[query_id] = dense
        hybrid_hits[query_id] = rrf_fuse(sparse, dense)
        if count % 50 == 0:
            print(f"Retrieved {count}/{len(queries)} queries", flush=True)
    reranked_hits = _rerank_all(queries, hybrid_hits, reranker)
    hit_groups = {
        "bm25": bm25_hits,
        "dense_hnsw": dense_hits,
        "hybrid_rrf": hybrid_hits,
        "hybrid_rerank": reranked_hits,
    }
    runs = {
        stage: {
            query_id: [hit.doc_id for hit in hits]
            for query_id, hits in stage_hits.items()
        }
        for stage, stage_hits in hit_groups.items()
    }
    return runs, reranked_hits
