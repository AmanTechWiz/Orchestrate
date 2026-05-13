from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from build_index import build_index
from ingest import cache_dir, read_json
from schemas import RetrievedChunk
from utils.lang import translate_for_retrieval
from utils.text import cosine_sparse, normalize_scores, tfidf_vector, tokenize


class Retriever:
    def __init__(self, index_path: Optional[Path] = None) -> None:
        self.index_path = index_path or cache_dir() / "index.json"
        if not self.index_path.exists():
            build_index()
        self.index = read_json(self.index_path)
        self.chunks: List[Dict[str, object]] = list(self.index["chunks"])  # type: ignore[index]
        self.idf: Dict[str, float] = dict(self.index["idf"])  # type: ignore[index]
        self.doc_vectors: List[Dict[str, float]] = list(self.index["doc_vectors"])  # type: ignore[index]
        self.doc_freqs: List[Dict[str, int]] = list(self.index["doc_freqs"])  # type: ignore[index]
        self.doc_lengths: List[int] = list(self.index["doc_lengths"])  # type: ignore[index]
        self.avg_doc_length = float(self.index["avg_doc_length"])

    def bm25(self, query_tokens: Iterable[str], doc_idx: int, k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        freqs = self.doc_freqs[doc_idx]
        doc_len = self.doc_lengths[doc_idx] or 1
        for token in query_tokens:
            tf = freqs.get(token, 0)
            if tf <= 0:
                continue
            idf = self.idf.get(token, 0.0)
            denom = tf + k1 * (1.0 - b + b * doc_len / max(self.avg_doc_length, 1.0))
            score += idf * ((tf * (k1 + 1.0)) / denom)
        return score

    def search(
        self,
        query: str,
        company: str = "",
        top_k: int = 5,
        candidate_k: int = 20,
        bm25_weight: float = 0.55,
    ) -> List[RetrievedChunk]:
        query_text = translate_for_retrieval(query)
        query_tokens = tokenize(query_text)
        query_vector = tfidf_vector(query_tokens, self.idf)
        candidates: List[tuple[int, float, float]] = []
        for idx, chunk in enumerate(self.chunks):
            if company and chunk.get("company") != company:
                continue
            bm25_score = self.bm25(query_tokens, idx)
            vector_score = cosine_sparse(query_vector, self.doc_vectors[idx])
            if bm25_score > 0 or vector_score > 0:
                candidates.append((idx, bm25_score, vector_score))

        if not candidates:
            return []

        bm25_norm = normalize_scores(item[1] for item in candidates)
        vector_norm = normalize_scores(item[2] for item in candidates)
        ranked: List[tuple[int, float, float, float]] = []
        for pos, (idx, bm25_score, vector_score) in enumerate(candidates):
            hybrid = bm25_weight * bm25_norm[pos] + (1.0 - bm25_weight) * vector_norm[pos]
            ranked.append((idx, hybrid, bm25_score, vector_score))
        ranked.sort(key=lambda item: item[1], reverse=True)

        results: List[RetrievedChunk] = []
        for idx, score, bm25_score, vector_score in ranked[: max(candidate_k, top_k)][:top_k]:
            chunk = self.chunks[idx]
            results.append(
                RetrievedChunk(
                    text=str(chunk["text"]),
                    source_path=str(chunk["source_path"]),
                    company=str(chunk["company"]),
                    product_area=str(chunk["product_area"]),
                    heading_path=str(chunk.get("heading_path", "")),
                    score=round(float(score), 4),
                    bm25_score=round(float(bm25_score), 4),
                    vector_score=round(float(vector_score), 4),
                )
            )
        return results

    def infer_company(self, query: str) -> tuple[str, float]:
        scores: Dict[str, float] = {}
        for company in ("hackerrank", "claude", "visa"):
            results = self.search(query, company=company, top_k=1)
            scores[company] = results[0].score if results else 0.0
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if not ordered or ordered[0][1] <= 0:
            return "", 0.0
        gap = ordered[0][1] - (ordered[1][1] if len(ordered) > 1 else 0.0)
        return ordered[0][0], gap


def max_score(chunks: List[RetrievedChunk]) -> float:
    return max((chunk.score for chunk in chunks), default=0.0)
