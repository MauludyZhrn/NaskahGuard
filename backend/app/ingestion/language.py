"""Stopword-ratio language detection for Indonesian and English."""

from __future__ import annotations

_ID_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "adalah",
    "ini", "itu", "dalam", "tidak", "atau", "sebagai", "oleh", "tersebut",
    "dapat", "akan", "telah", "bahwa", "penelitian", "hasil", "metode",
    "merupakan", "karena", "juga", "sehingga", "antara", "lebih", "sangat",
}

_EN_STOPWORDS = {
    "the", "and", "of", "to", "in", "is", "for", "that", "with", "as",
    "are", "this", "on", "by", "from", "an", "be", "or", "which", "was",
    "have", "has", "not", "can", "research", "results", "method", "study",
    "between", "also", "these", "using", "based", "data",
}


def detect_language(norm_tokens: list[str]) -> str:
    if not norm_tokens:
        return "unknown"
    id_hits = sum(1 for t in norm_tokens if t in _ID_STOPWORDS)
    en_hits = sum(1 for t in norm_tokens if t in _EN_STOPWORDS)
    total_hits = id_hits + en_hits
    if total_hits < 3:
        return "unknown"
    id_ratio = id_hits / total_hits
    en_ratio = en_hits / total_hits
    if id_ratio >= 0.7:
        return "id"
    if en_ratio >= 0.7:
        return "en"
    return "mixed"
