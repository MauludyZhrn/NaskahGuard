"""Local-first AI Writing Detection package for NaskahGuard."""

from __future__ import annotations

from app.ai_detection.detector import (
    DEFAULT_DISCLAIMER_ID,
    analyze_document_ai,
    classify_paragraph,
)
from app.ai_detection.features import detect_text_language
from app.ai_detection.model_registry import (
    activate_model,
    get_active_model_id,
    list_models,
    verify_model,
)

__all__ = [
    "DEFAULT_DISCLAIMER_ID",
    "activate_model",
    "analyze_document_ai",
    "classify_paragraph",
    "detect_text_language",
    "get_active_model_id",
    "list_models",
    "verify_model",
]
