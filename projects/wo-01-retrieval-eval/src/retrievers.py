"""Chunked BM25, dense cosine, document-level RRF, and cross-encoder reranking."""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def lexical_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def make_chunks(corpus: dict, tokenizer, size: int, overlap: int = 24):
    if size > 256 or size <= overlap:
        raise ValueError("MiniLM supports at most 256 wordpieces; size must exceed overlap")
    chunks, parents = [], []
    for docid, row in corpus.items():
        text = f"{row.get('title', '')}. {row.get('text', '')}".strip()
        tokens = tokenizer.encode(text, add_special_tokens=False)
        step = size - overlap
        for start in range(0, len(tokens), step):
            part = tokenizer.decode(tokens[start:start + size], skip_special_tokens=True)
            if part.strip():
                chunks.append(part)
                parents.append(docid)
            if start + size >= len(tokens):
                break
    return chunks, parents


def _rank_parent_docs(scores, parents, limit: int = 50) -> list[str]:
    order = np.argsort(-scores, kind="stable")
    ranked, seen = [], set()
    for index in order:
        docid = parents[index]
        if docid not in seen:
            ranked.append(docid)
            seen.add(docid)
            if len(ranked) == limit:
                break
    return ranked


def bm25_runs(chunks, parents, queries, limit=50):
    index = BM25Okapi([lexical_tokens(chunk) for chunk in chunks])
    return {qid: _rank_parent_docs(index.get_scores(lexical_tokens(query)), parents, limit)
            for qid, query in queries.items()}


def dense_runs(model, chunks, parents, queries, cache_dir: Path, size: int, limit=50):
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps([EMBED_MODEL, size, parents, chunks], ensure_ascii=False).encode()).hexdigest()[:16]
    cache = cache_dir / f"embeddings-{size}-{fingerprint}.npy"
    if cache.exists():
        embeddings = np.load(cache)
    else:
        embeddings = model.encode(chunks, batch_size=64, show_progress_bar=True,
                                  normalize_embeddings=True, convert_to_numpy=True)
        np.save(cache, embeddings)
    qids = list(queries)
    query_vectors = model.encode([queries[qid] for qid in qids], batch_size=64,
                                 show_progress_bar=True, normalize_embeddings=True,
                                 convert_to_numpy=True)
    runs = {}
    for qid, vector in zip(qids, query_vectors):
        scores = embeddings @ vector
        runs[qid] = _rank_parent_docs(scores, parents, limit)
    return runs


def rrf_runs(first, second, limit=50, k=60):
    result = {}
    for qid in first:
        scores = {}
        for ranking in (first[qid], second[qid]):
            for position, docid in enumerate(ranking, 1):
                scores[docid] = scores.get(docid, 0.0) + 1.0 / (k + position)
        result[qid] = sorted(scores, key=lambda doc: (-scores[doc], doc))[:limit]
    return result


def rerank_runs(runs, corpus, queries, top_n=20):
    cross_encoder = CrossEncoder(RERANK_MODEL, max_length=512)
    output = {}
    for count, (qid, ranking) in enumerate(runs.items(), 1):
        candidates = ranking[:top_n]
        pairs = [(queries[qid], f"{corpus[doc]['title']}. {corpus[doc]['text']}") for doc in candidates]
        scores = cross_encoder.predict(pairs, batch_size=32, show_progress_bar=False)
        reordered = sorted(zip(candidates, scores), key=lambda pair: -float(pair[1]))
        output[qid] = [doc for doc, _ in reordered] + ranking[top_n:]
        if count % 50 == 0:
            print(f"Reranked {count}/{len(runs)} queries", flush=True)
    return output
