"""Layer 4: Optional multilingual sentence embeddings for semantic candidate review."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import numpy as np

from app.config import get_settings
from app.engine.exact import RawMatch
from app.models import Segment

SEMANTIC_THRESHOLD = 0.80

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError:
    SentenceTransformer = None  # type: ignore

_model_lock = Lock()
_loaded_model = None
_loaded_model_name: str | None = None


@dataclass(frozen=True)
class SemanticStatus:
    enabled: bool
    available: bool
    model_name: str
    message: str


def get_semantic_status() -> SemanticStatus:
    settings = get_settings()
    if not settings.SEMANTIC_ENABLED:
        return SemanticStatus(
            enabled=False,
            available=SentenceTransformer is not None,
            model_name=settings.SEMANTIC_MODEL,
            message="Modul semantik tidak aktif (dinonaktifkan secara default).",
        )
    if SentenceTransformer is None:
        return SemanticStatus(
            enabled=True,
            available=False,
            model_name=settings.SEMANTIC_MODEL,
            message="Modul semantik diaktifkan, namun paket sentence-transformers belum terpasang.",
        )
    return SemanticStatus(
        enabled=True,
        available=True,
        model_name=settings.SEMANTIC_MODEL,
        message=f"Modul semantik aktif ({settings.SEMANTIC_MODEL}).",
    )


def _get_model():
    global _loaded_model, _loaded_model_name
    settings = get_settings()
    with _model_lock:
        if _loaded_model is None or _loaded_model_name != settings.SEMANTIC_MODEL:
            _loaded_model = SentenceTransformer(settings.SEMANTIC_MODEL)
            _loaded_model_name = settings.SEMANTIC_MODEL
        return _loaded_model


def find_semantic_candidates(
    sub_segments: list[Segment],
    cand_segments: list[Segment],
    covered_tokens: set[int],
    *,
    threshold: float = SEMANTIC_THRESHOLD,
) -> tuple[list[RawMatch], SemanticStatus]:
    """Identify semantically similar sentences as review candidates (never counted in textual SI)."""
    status = get_semantic_status()
    if not status.enabled or not status.available:
        return [], status

    eligible_sub = [
        s for s in sub_segments
        if (s.token_end - s.token_start) >= 6
        and len(set(range(s.token_start, s.token_end)) & covered_tokens) / max(1, s.token_end - s.token_start) < 0.5
        and s.original_text.strip()
    ]
    eligible_cand = [
        c for c in cand_segments
        if (c.token_end - c.token_start) >= 6 and c.original_text.strip()
    ]
    if not eligible_sub or not eligible_cand:
        return [], status

    model = _get_model()
    sub_emb = model.encode([s.original_text for s in eligible_sub], normalize_embeddings=True)
    cand_emb = model.encode([c.original_text for c in eligible_cand], normalize_embeddings=True)
    sims = np.matmul(sub_emb, cand_emb.T)

    candidates: list[RawMatch] = []
    for i, s_seg in enumerate(eligible_sub):
        best_j = int(np.argmax(sims[i]))
        best_score = float(sims[i, best_j])
        if best_score >= threshold:
            c_seg = eligible_cand[best_j]
            candidates.append(
                RawMatch(
                    source_document_id=c_seg.document_id,
                    layer="SEMANTIC",
                    sub_token_start=s_seg.token_start,
                    sub_token_end=s_seg.token_end,
                    src_token_start=c_seg.token_start,
                    src_token_end=c_seg.token_end,
                    matched_words=s_seg.token_end - s_seg.token_start,
                    score=round(best_score, 4),
                    counted_token_indices=set(),  # Never counted in textual SI
                )
            )
    return candidates, status
