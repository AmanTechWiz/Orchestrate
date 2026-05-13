from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

from ingest import build_chunks, cache_dir, chunks_to_dicts, data_hash, data_root, read_json, write_json
from utils.text import build_idf, tfidf_vector


INDEX_VERSION = 1


def build_index(force: bool = False) -> Path:
    cache = cache_dir()
    index_path = cache / "index.json"
    current_hash = data_hash(data_root())
    if index_path.exists() and not force:
        existing = read_json(index_path)
        if existing.get("data_hash") == current_hash and existing.get("version") == INDEX_VERSION:
            print(f"Index cache reused: {index_path}")
            return index_path

    chunks = build_chunks()
    tokenized_docs = [chunk.tokens for chunk in chunks]
    idf = build_idf(tokenized_docs)
    doc_vectors: List[Dict[str, float]] = [tfidf_vector(tokens, idf) for tokens in tokenized_docs]
    doc_freqs = [dict(Counter(tokens)) for tokens in tokenized_docs]
    doc_lengths = [len(tokens) for tokens in tokenized_docs]
    avg_doc_length = sum(doc_lengths) / max(len(doc_lengths), 1)

    payload = {
        "version": INDEX_VERSION,
        "data_hash": current_hash,
        "chunk_count": len(chunks),
        "chunks": chunks_to_dicts(chunks),
        "idf": idf,
        "doc_vectors": doc_vectors,
        "doc_freqs": doc_freqs,
        "doc_lengths": doc_lengths,
        "avg_doc_length": avg_doc_length,
    }
    write_json(index_path, payload)
    print(f"Index built: {index_path} ({len(chunks)} chunks)")
    return index_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local support-corpus retrieval index.")
    parser.add_argument("--force", action="store_true", help="Rebuild even if the data hash matches.")
    args = parser.parse_args()
    build_index(force=args.force)


if __name__ == "__main__":
    main()
