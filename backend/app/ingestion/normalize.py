"""Unicode text normalization utilities (never mutates original text)."""

from __future__ import annotations

import unicodedata

_LIGATURES = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
    }
)


def normalize_token(token: str) -> str:
    """Normalize a single token using NFKC, ligature folding, casefold, and diacritic removal."""
    text = unicodedata.normalize("NFKC", token).translate(_LIGATURES)
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFKC", stripped).casefold()


def normalize_text_tokens(tokens: list[str]) -> str:
    """Join normalized tokens with a single space."""
    return " ".join(normalize_token(t) for t in tokens if t)
