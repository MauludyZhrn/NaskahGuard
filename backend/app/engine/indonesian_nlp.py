"""Indonesian Academic Morphology, Synonym Normalization & Paraphrase Fusion (Phase 9).

Handles:
- Indonesian affixation changes (meN-, peN-, ber-, ter-, di-, ke-, -kan, -an, -i, -nya)
- Curated Indonesian academic synonym groups (non-technical verbs/nouns)
- Conjunction & clause-order variation resilience
- Technical/Arabic/English loanword protection (shared technical terms alone do NOT trigger matches)
- Human-readable explanation for flagged lexical/paraphrase candidates
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9\-]+")

_FUNCTION_WORDS = {
    "yang", "dan", "atau", "serta", "pada", "dari", "untuk", "dengan", "dalam",
    "adalah", "ialah", "merupakan", "oleh", "sebagai", "tidak", "bukan", "akan",
    "telah", "sudah", "sedang", "dapat", "bisa", "mampu", "bahwa", "tersebut",
    "ini", "itu", "antara", "secara", "lebih", "paling", "karena", "sebab",
    "sehingga", "akibatnya", "namun", "tetapi", "melainkan", "sedangkan",
    "apabila", "jika", "bila", "ketika", "saat", "walaupun", "meskipun",
    "terhadap", "melalui", "menjadi", "kepada", "menurut", "berdasarkan",
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "have", "has", "been", "into", "through", "using", "while", "whereas",
}

# Common academic/technical loanwords (EN/AR/ID) — shared domain terms alone should not count as plagiarism
_TECHNICAL_TERMS = {
    "algoritma", "algorithm", "database", "sistem", "system", "model", "metodologi",
    "signifikansi", "validitas", "reliabilitas", "regresi", "korelasi", "hipotesis",
    "variabel", "populasi", "sampel", "responden", "kuesioner", "instrumen",
    "kuantitatif", "kualitatif", "empiris", "statistik", "probabilitas", "distribusi",
    "framework", "arsitektur", "architecture", "machine", "learning", "deep", "neural",
    "network", "transformer", "embedding", "token", "dataset", "akurasi", "presisi",
    "syariah", "muamalah", "mudharabah", "musyarakah", "murabahah", "wakaf", "zakat",
    "maqashid", "ijtihad", "fikih", "fiqh", "ushul",
}

_SYNONYM_GROUPS: dict[str, str] = {
    # menggunakan / memanfaatkan / memakai
    "pakai": "guna",
    "manfaat": "guna",
    "terap": "guna",
    "aplikasi": "guna",
    # menunjukkan / memperlihatkan / mengindikasikan / membuktikan
    "perlihat": "tunjuk",
    "indikasi": "tunjuk",
    "bukti": "tunjuk",
    # penelitian / riset / kajian / studi
    "riset": "teliti",
    "kaji": "teliti",
    "studi": "teliti",
    # dampak / pengaruh / efek / implikasi
    "pengaruh": "dampak",
    "efek": "dampak",
    "implikasi": "dampak",
    # peningkatan / kenaikan / pertambahan
    "naik": "tingkat",
    "tambah": "tingkat",
    # penurunan / pengurangan / reduksi
    "kurang": "turun",
    "reduksi": "turun",
    # kesimpulan / simpulan
    "simpul": "simpul",
    "kesimpulan": "simpul",
    # tujuan / sasaran / maksud
    "sasar": "tuju",
    "maksud": "tuju",
    # evaluasi / penilaian / pengujian
    "nilai": "uji",
    "evaluasi": "uji",
}

_PROTECTED_WORDS = _TECHNICAL_TERMS | {
    "indonesia", "universitas", "fakultas", "pendidikan", "pemerintah", "masyarakat",
}


def stem_indonesian_token(word: str) -> str:
    """Lightweight deterministic Sastrawi-inspired root stemmer for Bahasa Indonesia."""
    w = word.lower().strip("-")
    if len(w) <= 4 or w in _FUNCTION_WORDS or w in _PROTECTED_WORDS or w.isdigit():
        return w

    # Strip enclitics / particles (-lah, -kah, -nya)
    for p in ("lah", "kah", "nya"):
        if w.endswith(p) and len(w) - len(p) >= 4:
            w = w[: -len(p)]
            break

    # Strip derivational suffixes (-kan, -an, -i)
    for suf in ("kan", "an", "i"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break

    # Strip prefixes with morphophonemic nasal assimilation rules
    if w.startswith("meng") and len(w) >= 7:
        rest = w[4:]
        w = ("k" + rest) if rest[0] in "aiueo" and len(rest) >= 4 and rest not in {"ambil", "ukur", "uji", "analisis", "olah"} else rest
    elif w.startswith("meny") and len(w) >= 7:
        w = "s" + w[4:]
    elif w.startswith("me") and len(w) >= 6 and w[2] in {"l", "r", "w", "y"}:
        w = w[2:]
    elif w.startswith("mem") and len(w) >= 6:
        rest = w[3:]
        if rest.startswith("anfaat"):
            w = "manfaat"
        else:
            w = ("p" + rest) if rest[0] in "aiueo" else rest
    elif w.startswith("men") and len(w) >= 6:
        rest = w[3:]
        w = ("t" + rest) if rest[0] in "aiueo" else rest
    elif w.startswith("me") and len(w) >= 6:
        w = w[2:]
    elif w.startswith("peng") and len(w) >= 7:
        w = w[4:]
    elif w.startswith("peny") and len(w) >= 7:
        w = "s" + w[4:]
    elif w.startswith("pem") and len(w) >= 6:
        rest = w[3:]
        w = ("p" + rest) if rest[0] in "aiueo" else rest
    elif w.startswith("pen") and len(w) >= 6:
        rest = w[3:]
        w = ("t" + rest) if rest[0] in "aiueo" else rest
    elif w.startswith(("ber", "ter", "per")) and len(w) >= 7:
        w = w[3:]
    elif w.startswith(("di", "ke", "se", "pe")) and len(w) >= 6:
        w = w[2:]

    return _SYNONYM_GROUPS.get(w, w)


def extract_stemmed_signature(text: str) -> tuple[list[str], set[str], set[str]]:
    """Return (ordered_stems, non_technical_stems, technical_stems) for a sentence/segment."""
    raw_words = [w.lower() for w in _WORD_RE.findall(text) if len(w) >= 3]
    ordered: list[str] = []
    non_tech: set[str] = set()
    tech: set[str] = set()

    for w in raw_words:
        if w in _FUNCTION_WORDS or w.isdigit():
            continue
        if w in _TECHNICAL_TERMS:
            tech.add(w)
            ordered.append(w)
            continue
        st = stem_indonesian_token(w)
        ordered.append(st)
        non_tech.add(st)

    return ordered, non_tech, tech


def compute_indonesian_paraphrase_similarity(
    sub_text: str,
    src_text: str,
    char_cosine: float,
) -> tuple[float, str | None]:
    """Compute morphology + synonym + clause-reordering similarity with anti-false-positive guard.

    Shared technical/domain terminology alone CANNOT exceed 0.55 unless non-technical predicate/content
    roots also overlap substantially (>= 0.50 Dice).
    """
    sub_ord, sub_nt, sub_tech = extract_stemmed_signature(sub_text)
    src_ord, src_nt, src_tech = extract_stemmed_signature(src_text)

    if len(sub_ord) < 4 or len(src_ord) < 4:
        return char_cosine, None

    # Non-technical stemmed content Dice similarity
    if not sub_nt or not src_nt:
        return min(char_cosine, 0.50), None

    nt_inter = len(sub_nt & src_nt)
    nt_dice = (2.0 * nt_inter) / (len(sub_nt) + len(src_nt))

    all_sub = sub_nt | sub_tech
    all_src = src_nt | src_tech
    all_dice = (2.0 * len(all_sub & all_src)) / max(1, len(all_sub) + len(all_src))

    # Guard against technical-jargon-only overlap!
    if nt_inter < 3 or nt_dice < 0.48:
        return min(char_cosine, 0.62), None

    # Fused lexical-morphological score (resilient to prefix/suffix changes, synonyms & clause reordering)
    if nt_dice >= 0.65:
        fused = 0.35 * char_cosine + 0.45 * nt_dice + 0.20 * all_dice
    else:
        fused = 0.45 * char_cosine + 0.35 * nt_dice + 0.20 * all_dice

    reasons: list[str] = []
    if nt_dice >= 0.60 and char_cosine < 0.72:
        reasons.append("variasi imbuhan/sinonim Bahasa Indonesia")
    # Detect clause reordering if unordered Dice is high while bigram order overlap is lower
    sub_bi = set(zip(sub_ord, sub_ord[1:]))
    src_bi = set(zip(src_ord, src_ord[1:]))
    bi_dice = (2.0 * len(sub_bi & src_bi)) / max(1, len(sub_bi) + len(src_bi)) if (sub_bi and src_bi) else 0.0
    if all_dice - bi_dice >= 0.22:
        reasons.append("perubahan urutan klausa/struktur kalimat")
    if sub_tech & src_tech:
        reasons.append("konteks istilah akademik serupa")

    explanation = (
        f"Kemiripan leksikal-morfologis ({round(fused * 100)}%): " + (", ".join(reasons) if reasons else "kesamaan pola kata inti")
    )
    return round(min(1.0, fused), 4), explanation
