from __future__ import annotations

import re
import unicodedata
from collections import Counter
from math import log, sqrt
from typing import Dict, Iterable, List, Sequence, Tuple


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+-]*", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return text.replace("\u2019", "'").replace("\u2018", "'").strip()


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(normalize_text(text).lower())


def slugify(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def cosine_sparse(left: Dict[str, float], right: Dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = set(left).intersection(right)
    dot = sum(left[token] * right[token] for token in common)
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def build_idf(tokenized_docs: Sequence[Sequence[str]]) -> Dict[str, float]:
    doc_count = max(len(tokenized_docs), 1)
    dfs: Counter[str] = Counter()
    for tokens in tokenized_docs:
        dfs.update(set(tokens))
    return {token: log((doc_count + 1) / (df + 1)) + 1.0 for token, df in dfs.items()}


def tfidf_vector(tokens: Sequence[str], idf: Dict[str, float]) -> Dict[str, float]:
    counts = Counter(tokens)
    length = max(sum(counts.values()), 1)
    return {token: (count / length) * idf.get(token, 1.0) for token, count in counts.items()}


def normalize_scores(scores: Iterable[float]) -> List[float]:
    values = list(scores)
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high <= low:
        return [1.0 if high > 0 else 0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def rouge_l(reference: str, candidate: str) -> float:
    ref_tokens = tokenize(reference)
    cand_tokens = tokenize(candidate)
    if not ref_tokens or not cand_tokens:
        return 0.0
    previous = [0] * (len(cand_tokens) + 1)
    for ref_token in ref_tokens:
        current = [0]
        for idx, cand_token in enumerate(cand_tokens, start=1):
            if ref_token == cand_token:
                current.append(previous[idx - 1] + 1)
            else:
                current.append(max(previous[idx], current[-1]))
        previous = current
    lcs = previous[-1]
    return (2 * lcs) / (len(ref_tokens) + len(cand_tokens))


def strip_csv_hostile(text: str) -> str:
    return re.sub(r"[\r\t]+", " ", normalize_text(text)).strip()


def first_sentence(text: str, max_chars: int = 240) -> str:
    text = re.sub(r"\s+", " ", normalize_text(text))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
