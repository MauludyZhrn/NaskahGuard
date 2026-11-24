"""Local document corpus provider."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Document
from app.sources.base import FetchedContent, SourceProvider, SourceRecord


class LocalCorpusProvider(SourceProvider):
    name = "local_corpus"

    def __init__(self, db: Session, include_submissions: bool = False, exclude_doc_id: str | None = None) -> None:
        self.db = db
        self.include_submissions = include_submissions
        self.exclude_doc_id = exclude_doc_id

    def list_eligible_doc_ids(self) -> set[str]:
        roles = ["CORPUS", "EXTERNAL"]
        if self.include_submissions:
            roles.append("SUBMISSION")
        q = self.db.query(Document.id).filter(Document.role.in_(roles))
        if self.exclude_doc_id:
            q = q.filter(Document.id != self.exclude_doc_id)
        return {row[0] for row in q.all()}

    def search(self, query: str) -> list[SourceRecord]:
        q = self.db.query(Document).filter(Document.role.in_(["CORPUS", "EXTERNAL"]))
        if query.strip():
            like = f"%{query.strip()}%"
            q = q.filter(Document.title.ilike(like) | Document.filename.ilike(like))
        docs = q.limit(50).all()
        return [
            SourceRecord(
                provider=self.name,
                external_id=d.id,
                title=d.title or d.filename,
                authors=d.authors or [],
                year=d.year,
                doi=d.doi,
                url=d.url,
                source_type=d.source_type,
                access_status=d.access_status,
            )
            for d in docs
        ]

    def fetch_content(self, source_id: str) -> FetchedContent | None:
        return None

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        d = self.db.query(Document).filter(Document.id == source_id).first()
        if not d:
            return None
        return SourceRecord(
            provider=self.name,
            external_id=d.id,
            title=d.title or d.filename,
            authors=d.authors or [],
            year=d.year,
            doi=d.doi,
            url=d.url,
            source_type=d.source_type,
            access_status=d.access_status,
        )
