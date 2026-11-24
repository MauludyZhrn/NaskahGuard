"""Base interfaces, dataclasses, and compatibility helpers for Source Discovery."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class SourceRecord:
    provider: str
    external_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    canonical_url: str | None = None
    source_type: str = "external_paper"
    access_status: str = "METADATA_ONLY"  # FULL_TEXT_AVAILABLE | METADATA_ONLY | ACCESS_DENIED | FETCH_FAILED | INDEXED_LOCALLY
    oa_pdf_url: str | None = None
    candidate_urls: list[str] = field(default_factory=list)
    license: str | None = None
    abstract: str | None = None
    retrieved_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchedContent:
    filename: str
    raw_bytes: bytes
    content_type: str = "application/pdf"
    file_type: str = "pdf"


@dataclass
class ProviderSearchOutcome:
    records: list[SourceRecord]
    http_status: int | None = None
    error: str | None = None
    duration_ms: int = 0


class SourceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str) -> list[SourceRecord]:
        """Search provider using a short query (title/keywords, never full document text)."""

    @abstractmethod
    def fetch_content(self, source_id: str) -> FetchedContent | None:
        """Fetch full text content if openly licensed and permitted."""

    @abstractmethod
    def get_metadata(self, source_id: str) -> SourceRecord | None:
        """Retrieve metadata for a specific source identifier."""


def extract_query_keywords(title: str | None, segments_text: list[str], max_keywords: int = 10) -> list[str]:
    """Compatibility helper building safe short search queries from title + top TF-IDF phrases."""
    queries: list[str] = []
    clean_title = (title or "").strip()
    if clean_title and not clean_title.lower().endswith((".pdf", ".docx", ".txt")):
        queries.append(clean_title[:200])

    body = [t for t in segments_text if len(t.split()) >= 5][:120]
    if body:
        try:
            vec = TfidfVectorizer(ngram_range=(1, 2), max_features=30, stop_words=None)
            mat = vec.fit_transform(body)
            scores = mat.sum(axis=0).A1
            terms = vec.get_feature_names_out()
            ranked = sorted(zip(terms, scores), key=lambda x: -x[1])
            top_terms = [term for term, _ in ranked[:max_keywords] if len(term) >= 4]
            if top_terms:
                queries.append(" ".join(top_terms[:6]))
                if len(top_terms) > 6:
                    queries.append(" ".join(top_terms[4:10]))
        except ValueError:
            pass

    if not queries and body:
        first_words = " ".join(body[0].split()[:8])
        if first_words:
            queries.append(first_words)
    return queries[:3]
