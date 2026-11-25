"""Linguistic, stylometric, burstiness, and language-model predictability features.

Designed for zero-leakage generalization across unseen academic & general prose
in both Bahasa Indonesia and English on Windows CPU.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9\"(])")
PARA_SPLIT_RE = re.compile(r"\n\s*\n+")
SPECIFIC_NUMBER_OR_CITE_RE = re.compile(
    r"(\(\s*[A-Z][A-Za-z\s.&-]+,\s*(?:19|20)\d{2}[a-z]?(?::\s*\d+(?:-\d+)?)?\s*\)"
    r"|\b(?:Pasal|Ayat|UU|PP|Permen|Permendagri|Permenaker|KepmenLH|PMK|SNI|Ref\.|Table|Fig\.|Tabel|Gambar|Bab|BAB)\s+[A-Z0-9.-]+"
    r"|\bn\s*=\s*\d+"
    r"|\b\d+(?:[.,]\d+)?\s*(?:%|persen|percent)\b"
    r"|\b(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|June|July|August|September|October|November|December)\b"
    r"|\b\d{2,4}\b)"
)

ID_FUNCTION_WORDS = frozenset({
    "yang", "dan", "di", "ke", "dari", "pada", "untuk", "dengan", "dalam", "sebagai",
    "oleh", "bahwa", "dapat", "atau", "juga", "tersebut", "karena", "tidak", "ini",
    "itu", "adalah", "akan", "telah", "serta", "namun", "secara", "bagi", "hingga",
    "antara", "melalui", "lebih", "saat", "ketika", "apabila", "jika", "kami", "peneliti",
})

EN_FUNCTION_WORDS = frozenset({
    "the", "and", "of", "to", "in", "for", "with", "that", "on", "as", "by", "this",
    "from", "are", "is", "was", "were", "be", "been", "which", "or", "however",
    "therefore", "between", "through", "such", "their", "these", "those", "we", "our",
})

# Rhetorical & synthetic filler markers observed across multi-family LLMs (ID + EN).
ID_AI_MARKERS = (
    "di era digital",
    "dalam era modern",
    "di era modern",
    "secara keseluruhan",
    "penting untuk dicatat",
    "perlu digarisbawahi",
    "tidak dapat dipungkiri",
    "di sisi lain",
    "lebih jauh lagi",
    "dengan demikian dapat disimpulkan",
    "memainkan peran krusial",
    "memainkan peran penting",
    "berkelanjutan dan inklusif",
    "pendekatan yang holistik",
    "pendekatan holistik",
    "pendekatan komprehensif",
    "pendekatan terstruktur",
    "sinergi antara berbagai",
    "berbagai pemangku kepentingan",
    "seluruh pemangku kepentingan",
    "memberikan wawasan berharga",
    "tantangan sekaligus peluang",
    "secara berkelanjutan",
    "perbaikan berkelanjutan",
    "langkah strategis yang terukur",
    "optimalisasi tata kelola",
    "mencerminkan keterhubungan",
    "menuntut penyelarasan",
    "penguatan kapasitas",
    "tata laksana yang lebih transparan",
    "kualitas layanan publik",
    "jangka menengah maupun panjang",
)

EN_AI_MARKERS = (
    "in today's rapidly evolving",
    "in conclusion",
    "furthermore",
    "moreover",
    "it is worth noting",
    "it is important to note",
    "plays a crucial role",
    "plays a pivotal role",
    "comprehensive overview",
    "multifaceted challenge",
    "holistic approach",
    "significant implications",
    "delve into",
    "underscores the importance",
    "underscores how",
    "on the other hand",
    "taken together",
    "foster innovation",
    "streamline processes",
    "unlock the potential",
    "unlocks lasting",
    "ultimately",
    "long-term program durability",
    "stakeholder accountability",
    "evidence-based governance",
    "structured framework",
    "sustained improvements in overall",
    "adaptable and sustainable",
    "calibrated administrative responses",
)

# Balanced doublet regex ("X and/dan Y" adjective/abstract noun symmetry common in LLM synthesis).
SYMMETRIC_DOUBLET_RE = re.compile(
    r"\b(?:terarah|terukur|adaptif|berkelanjutan|transparan|akuntabel|komprehensif|holistik|konsisten|responsif|inovatif|relevan|optimal|strategis|merata|inklusif"
    r"|adaptable|sustainable|transparent|accountable|coherent|durable|reliable|structured|consistent|equitable|measurable|practical|targeted|thoughtful)"
    r"\s+(?:dan|serta|maupun|and)\s+"
    r"(?:terarah|terukur|adaptif|berkelanjutan|transparan|akuntabel|komprehensif|holistik|konsisten|responsif|inovatif|relevan|optimal|strategis|merata|inklusif"
    r"|adaptable|sustainable|transparent|accountable|coherent|durable|reliable|structured|consistent|equitable|measurable|practical|targeted|thoughtful)\b",
    re.IGNORECASE,
)

HUMAN_ANCHOR_PHRASES = (
    "pengamatan kami",
    "di lapangan",
    "wawancara dengan",
    "responden",
    "catatan kami",
    "kami menemukan",
    "tim peneliti",
    "jujur saja",
    "ternyata",
    "anehnya",
    "ironisnya",
    "gara-gara",
    "padahal",
    "justru",
    "meskipun begitu",
    "sebaliknya di lokasi",
    "kuitansi",
    "buku folio",
    "ketika hujan",
    "selasa dan jumat",
    "in our fieldwork",
    "our interviews",
    "we were wrong",
    "honestly",
    "oddly enough",
    "to our surprise",
    "on closer inspection",
    "when we checked",
    "checked by hand",
    "wrote those fixes",
    "nobody dared",
    "handwritten",
    "micro-level",
    "coding",
    "cohen's kappa",
    "inter-coder",
    "ethics clearance",
)


@dataclass(slots=True)
class ParagraphSpan:
    index: int
    char_start: int
    char_end: int
    text: str
    word_count: int


def tokenize_words(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    parts = [p.strip() for p in SENTENCE_SPLIT_RE.split(cleaned) if p.strip()]
    if len(parts) <= 1:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            return lines
    return parts


def split_paragraphs(text: str) -> list[ParagraphSpan]:
    spans: list[ParagraphSpan] = []
    pos = 0
    raw_chunks = list(PARA_SPLIT_RE.finditer(text))
    boundaries: list[tuple[int, int]] = []
    for match in raw_chunks:
        boundaries.append((pos, match.start()))
        pos = match.end()
    boundaries.append((pos, len(text)))

    idx = 0
    for start, end in boundaries:
        segment = text[start:end]
        stripped = segment.strip()
        if not stripped:
            continue
        lead_ws = len(segment) - len(segment.lstrip())
        trail_ws = len(segment) - len(segment.rstrip())
        c_start = start + lead_ws
        c_end = end - trail_ws
        words = tokenize_words(stripped)
        spans.append(
            ParagraphSpan(
                index=idx,
                char_start=c_start,
                char_end=c_end,
                text=stripped,
                word_count=len(words),
            )
        )
        idx += 1

    if len(spans) == 1 and spans[0].word_count > 240:
        sole = spans[0]
        sentence_matches = list(SENTENCE_SPLIT_RE.finditer(sole.text))
        if len(sentence_matches) >= 5:
            grouped: list[ParagraphSpan] = []
            group_start = 0
            for i in range(2, len(sentence_matches), 3):
                cut = sentence_matches[i].start()
                sub = sole.text[group_start:cut].strip()
                if sub:
                    grouped.append(
                        ParagraphSpan(
                            index=len(grouped),
                            char_start=sole.char_start + group_start,
                            char_end=sole.char_start + group_start + len(sub),
                            text=sub,
                            word_count=len(tokenize_words(sub)),
                        )
                    )
                group_start = sentence_matches[i].end()
            tail = sole.text[group_start:].strip()
            if tail:
                grouped.append(
                    ParagraphSpan(
                        index=len(grouped),
                        char_start=sole.char_start + group_start,
                        char_end=sole.char_end,
                        text=tail,
                        word_count=len(tokenize_words(tail)),
                    )
                )
            if len(grouped) >= 2:
                return grouped
    return spans


def detect_text_language(text: str) -> dict[str, object]:
    """Identify whether prose is Indonesian, English, Mixed, or Unknown."""
    words = tokenize_words(text)
    if len(words) < 12:
        return {
            "code": "unknown",
            "label": "Tidak Diketahui (Teks Terlalu Pendek)",
            "id_ratio": 0.0,
            "en_ratio": 0.0,
            "supported": False,
        }
    total = len(words)
    id_hits = sum(1 for w in words if w in ID_FUNCTION_WORDS)
    en_hits = sum(1 for w in words if w in EN_FUNCTION_WORDS)
    id_ratio = id_hits / max(1, total)
    en_ratio = en_hits / max(1, total)

    if id_ratio >= 0.06 and en_ratio >= 0.06 and abs(id_ratio - en_ratio) < 0.05:
        return {
            "code": "mixed",
            "label": "Campuran Indonesia & Inggris",
            "id_ratio": round(id_ratio, 4),
            "en_ratio": round(en_ratio, 4),
            "supported": True,
        }
    if id_ratio >= en_ratio * 1.25 and id_hits >= 2:
        return {
            "code": "id",
            "label": "Bahasa Indonesia",
            "id_ratio": round(id_ratio, 4),
            "en_ratio": round(en_ratio, 4),
            "supported": True,
        }
    if en_ratio >= id_ratio * 1.25 and en_hits >= 2:
        return {
            "code": "en",
            "label": "Bahasa Inggris",
            "id_ratio": round(id_ratio, 4),
            "en_ratio": round(en_ratio, 4),
            "supported": True,
        }
    return {
        "code": "other",
        "label": "Bahasa Lain / Campuran Tidak Dominan",
        "id_ratio": round(id_ratio, 4),
        "en_ratio": round(en_ratio, 4),
        "supported": False,
    }


def _mattr(words: list[str], window: int = 35) -> float:
    if not words:
        return 0.0
    if len(words) <= window:
        return len(set(words)) / len(words)
    scores = []
    for i in range(0, len(words) - window + 1):
        scores.append(len(set(words[i : i + window])) / window)
    return sum(scores) / len(scores)


class NgramEntropyModel:
    """Character-level entropy & smoothness estimator fit only on human baseline prose."""

    def __init__(
        self,
        char_log_probs: dict[str, float] | None = None,
        default_log_prob: float = -10.0,
    ) -> None:
        self.char_log_probs = char_log_probs or {}
        self.default_log_prob = default_log_prob

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    @classmethod
    def fit(cls, train_samples: list[dict[str, object]], max_vocab: int = 3000) -> "NgramEntropyModel":
        counts: Counter[str] = Counter()
        for row in train_samples:
            cleaned = cls._clean(str(row["text"]))
            counts.update(cleaned[i : i + 4] for i in range(max(0, len(cleaned) - 3)))
        top = {k for k, _ in counts.most_common(max_vocab)}
        alpha = 0.5
        total = sum(counts.values()) + alpha * (len(top) + 1)
        probs = {k: round(math.log((counts[k] + alpha) / total), 5) for k in top}
        default_lp = round(math.log(alpha / max(1.0, total)), 5)
        return cls(char_log_probs=probs, default_log_prob=default_lp)

    def to_dict(self) -> dict[str, object]:
        return {"char_log_probs": self.char_log_probs, "default_log_prob": self.default_log_prob}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "NgramEntropyModel":
        return cls(
            char_log_probs=dict(data.get("char_log_probs", {})),
            default_log_prob=float(data.get("default_log_prob", -10.0)),
        )

    def cross_entropy(self, text: str) -> float:
        cleaned = self._clean(text)
        grams = [cleaned[i : i + 4] for i in range(max(0, len(cleaned) - 3))]
        if not grams:
            return 0.0
        lp = sum(self.char_log_probs.get(g, self.default_log_prob) for g in grams) / len(grams)
        return round(float(-lp), 5)


FEATURE_ORDER = [
    "sentence_len_cv",
    "sentence_len_min_max_ratio",
    "short_sentence_ratio",
    "opener_diversity",
    "mattr_35",
    "avg_word_len",
    "ai_marker_rate",
    "symmetric_doublet_rate",
    "human_anchor_rate",
    "cite_number_rate",
    "expressive_punct_rate",
    "char_cross_entropy",
]


def extract_feature_dict(text: str, lm: NgramEntropyModel | None = None) -> dict[str, float]:
    """Extract generalizable stylometry, burstiness, specificity, and LM entropy features."""
    words = tokenize_words(text)
    sentences = split_sentences(text)
    word_count = max(1, len(words))

    sent_lengths = [len(tokenize_words(s)) for s in sentences]
    sent_lengths = [n for n in sent_lengths if n > 0] or [word_count]
    mean_s = sum(sent_lengths) / len(sent_lengths)
    if len(sent_lengths) > 1:
        var_s = sum((n - mean_s) ** 2 for n in sent_lengths) / len(sent_lengths)
        sent_cv = math.sqrt(var_s) / max(1.0, mean_s)
        min_max_ratio = min(sent_lengths) / max(1, max(sent_lengths))
    else:
        sent_cv = 0.30
        min_max_ratio = 0.65

    short_sentence_ratio = sum(1 for n in sent_lengths if n <= 12) / max(1, len(sent_lengths))

    openers = []
    for s in sentences:
        sw = tokenize_words(s)
        if sw:
            openers.append(sw[0])
    opener_diversity = len(set(openers)) / max(1, len(openers))

    mattr_35 = _mattr(words, window=35)
    avg_word_len = sum(len(w) for w in words) / word_count

    lowered = text.lower()
    ai_hits = sum(lowered.count(m) for m in ID_AI_MARKERS) + sum(lowered.count(m) for m in EN_AI_MARKERS)
    ai_marker_rate = (ai_hits / word_count) * 100.0

    doublet_hits = len(SYMMETRIC_DOUBLET_RE.findall(text))
    symmetric_doublet_rate = (doublet_hits / word_count) * 100.0

    human_hits = sum(lowered.count(m) for m in HUMAN_ANCHOR_PHRASES)
    human_anchor_rate = (human_hits / word_count) * 100.0

    cite_hits = len(SPECIFIC_NUMBER_OR_CITE_RE.findall(text))
    cite_number_rate = (cite_hits / word_count) * 100.0

    expressive = sum(text.count(ch) for ch in ("?", "!", "—", "-", "(", ":", ";"))
    expressive_punct_rate = (expressive / word_count) * 100.0

    entropy = lm.cross_entropy(text) if lm is not None else 7.5

    return {
        "sentence_len_cv": round(sent_cv, 5),
        "sentence_len_min_max_ratio": round(min_max_ratio, 5),
        "short_sentence_ratio": round(short_sentence_ratio, 5),
        "opener_diversity": round(opener_diversity, 5),
        "mattr_35": round(mattr_35, 5),
        "avg_word_len": round(avg_word_len, 5),
        "ai_marker_rate": round(ai_marker_rate, 5),
        "symmetric_doublet_rate": round(symmetric_doublet_rate, 5),
        "human_anchor_rate": round(human_anchor_rate, 5),
        "cite_number_rate": round(cite_number_rate, 5),
        "expressive_punct_rate": round(expressive_punct_rate, 5),
        "char_cross_entropy": round(entropy, 5),
    }


def vectorize_features(feat_dict: dict[str, float]) -> list[float]:
    return [float(feat_dict.get(name, 0.0)) for name in FEATURE_ORDER]
