"""SQLAlchemy ORM models for NaskahGuard."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("file_hash", "role", name="uq_documents_hash_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # SUBMISSION | CORPUS | EXTERNAL
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    normalized_title: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    indexing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="FULLTEXT_INDEXED")
    alternate_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="local_document")
    access_status: Mapped[str] = mapped_column(String(32), nullable=False, default="INDEXED_LOCALLY")
    extraction_method: Mapped[str] = mapped_column(String(24), nullable=False, default="TEXT")
    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    ocr_pages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    minhash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    segments: Mapped[list["Segment"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    fingerprints: Mapped[list["Fingerprint"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    checks: Mapped[list["Check"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="Check.document_id",
    )


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        Index("ix_segments_doc_seq", "document_id", "sentence_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sentence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_start: Mapped[int] = mapped_column(Integer, nullable=False)
    token_end: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    zone: Mapped[str] = mapped_column(String(24), nullable=False, default="BODY")

    document: Mapped[Document] = relationship(back_populates="segments")


class Fingerprint(Base):
    __tablename__ = "fingerprints"
    __table_args__ = (
        Index("ix_fingerprints_hash_doc", "hash", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    hash: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    token_pos: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped[Document] = relationship(back_populates="fingerprints")


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    report_number: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED", index=True)
    mode: Mapped[str] = mapped_column(String(24), nullable=False, default="PLAGIARISM_ONLY", index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="Antrean")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stage_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    coverage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship(back_populates="checks", foreign_keys=[document_id])
    matches: Mapped[list["Match"]] = relationship(back_populates="check", cascade="all, delete-orphan")
    check_sources: Mapped[list["CheckSource"]] = relationship(back_populates="check", cascade="all, delete-orphan")
    provider_queries: Mapped[list["ProviderQuery"]] = relationship(back_populates="check", cascade="all, delete-orphan")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(String(36), ForeignKey("checks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(24), nullable=False)  # EXACT | NEAR_EXACT | LEXICAL | SEMANTIC
    sub_token_start: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_token_end: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    src_token_start: Mapped[int] = mapped_column(Integer, nullable=False)
    src_token_end: Mapped[int] = mapped_column(Integer, nullable=False)
    src_char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    src_char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    src_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_words: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    sub_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    src_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    excluded_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    counted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    check: Mapped[Check] = relationship(back_populates="matches")
    source_document: Mapped[Document] = relationship(foreign_keys=[source_document_id])


class CheckSource(Base):
    __tablename__ = "check_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(String(36), ForeignKey("checks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_words_exclusive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_words_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contribution_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    layers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    check: Mapped[Check] = relationship(back_populates="check_sources")
    source_document: Mapped[Document] = relationship(foreign_keys=[source_document_id])


class ProviderQuery(Base):
    __tablename__ = "provider_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(String(36), ForeignKey("checks.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    check: Mapped[Check] = relationship(back_populates="provider_queries")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SourceAcquisition(Base):
    __tablename__ = "source_acquisitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(String(36), ForeignKey("checks.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="external_paper")
    file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SEARCH_RESULT_ONLY", index=True)
    used_playwright: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class OAIRepository(Base):
    __tablename__ = "oai_repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    repo_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ojs")
    platform_detected: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    identified_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_prefix: Mapped[str] = mapped_column(String(64), nullable=False, default="oai_dc")
    selected_set: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supported_formats: Mapped[list | None] = mapped_column(JSON, nullable=True)
    available_sets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    resumption_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    harvest_state: Mapped[str] = mapped_column(String(24), nullable=False, default="IDLE")
    last_test_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_harvested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_datestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    records_harvested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_saved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pdf_urls_found_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pdf_accessible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulltext_extracted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulltext_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_limit_delay_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    request_timeout_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNVERIFIED")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=utcnow)

    harvest_records: Mapped[list[OAIHarvestRecord]] = relationship(
        "OAIHarvestRecord", back_populates="repository", cascade="all, delete-orphan"
    )
    harvest_logs: Mapped[list[OAIHarvestLog]] = relationship(
        "OAIHarvestLog", back_populates="repository", cascade="all, delete-orphan"
    )


class OAIHarvestRecord(Base):
    __tablename__ = "oai_harvest_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oai_repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    oai_identifier: Mapped[str] = mapped_column(String(512), nullable=False)
    datestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    set_spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    rights: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landing_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pdf_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="METADATA_SAVED", index=True)
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    repository: Mapped[OAIRepository] = relationship("OAIRepository", back_populates="harvest_records")

    __table_args__ = (
        UniqueConstraint("repository_id", "oai_identifier", name="uq_oai_repo_identifier"),
    )


class OAIHarvestLog(Base):
    __tablename__ = "oai_harvest_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oai_repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    stage: Mapped[str] = mapped_column(String(48), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    repository: Mapped[OAIRepository] = relationship("OAIRepository", back_populates="harvest_logs")
