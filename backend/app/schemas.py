"""Pydantic schemas for request validation and response serialization."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CheckSettingsSchema(BaseModel):
    exclude_bibliography: bool = True
    exclude_quotes: bool = False
    exclude_citations: bool = True
    exclude_cover: bool = False
    exclude_toc: bool = True
    exclude_common_phrases: bool = True
    min_match_words: int = Field(default=8, ge=3, le=50)
    include_lexical_in_index: bool = False
    use_external_sources: bool = False
    external_providers: list[str] = Field(default_factory=lambda: ["openalex", "crossref", "arxiv"])
    compare_with_previous_submissions: bool = False
    add_to_corpus_after_check: bool = False
    use_noplag_engine: bool = False


class AppSettingsPayload(BaseModel):
    default_exclusions: CheckSettingsSchema = Field(default_factory=CheckSettingsSchema)
    threshold_low: float = Field(default=15.0, ge=1.0, le=90.0)
    threshold_high: float = Field(default=30.0, ge=2.0, le=99.0)

    @field_validator("threshold_high")
    @classmethod
    def _validate_thresholds(cls, v: float, info) -> float:
        low = info.data.get("threshold_low", 15.0)
        if v <= low:
            raise ValueError("threshold_high harus lebih besar dari threshold_low")
        return v


class CheckCreateRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=64)
    settings: CheckSettingsSchema | None = None


class DocumentOut(BaseModel):
    id: str
    role: str
    filename: str
    file_hash: str
    file_type: str
    mime: str
    size_bytes: int
    language: str
    page_count: int
    word_count: int
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    source_type: str
    access_status: str
    extraction_method: str
    extraction_confidence: float
    ocr_pages: list[int] | None = None
    provider: str | None = None
    external_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckSummaryOut(BaseModel):
    id: str
    report_number: str
    document_id: str
    document_filename: str | None = None
    document_title: str | None = None
    status: str
    stage: str
    progress: int
    settings: dict[str, Any]
    stage_counts: dict[str, Any]
    metrics: dict[str, Any]
    coverage: dict[str, Any]
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
