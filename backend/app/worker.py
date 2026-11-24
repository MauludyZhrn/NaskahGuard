"""In-process background worker queue with startup recovery and data retention purge."""

from __future__ import annotations

import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db import get_session_factory
from app.engine.minhash_lsh import invalidate_lsh_cache
from app.engine.pipeline import run_check_pipeline
from app.ingestion.validators import resolve_safe_storage_path
from app.models import Check, Document

logger = logging.getLogger("naskahguard.worker")

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()
_stop_event = threading.Event()
_retention_thread: threading.Thread | None = None


def _run_job(check_id: str) -> None:
    factory = get_session_factory()
    db = factory()
    try:
        run_check_pipeline(db, check_id)
    except Exception as exc:
        logger.exception("Worker error on check %s: %s", check_id, exc)
    finally:
        db.close()


def enqueue_check(check_id: str) -> None:
    global _executor
    with _executor_lock:
        if _executor is None:
            settings = get_settings()
            _executor = ThreadPoolExecutor(max_workers=max(1, settings.WORKER_THREADS), thread_name_prefix="ng-worker")
        _executor.submit(_run_job, check_id)


def purge_expired_submissions() -> int:
    """Delete submission documents and associated data older than RETENTION_DAYS."""
    settings = get_settings()
    if settings.RETENTION_DAYS <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.RETENTION_DAYS)
    factory = get_session_factory()
    db = factory()
    removed = 0
    try:
        expired = (
            db.query(Document)
            .filter(Document.role == "SUBMISSION", Document.created_at < cutoff)
            .all()
        )
        for doc in expired:
            delete_document_artifacts(doc)
            db.delete(doc)
            removed += 1
        if removed:
            db.commit()
            invalidate_lsh_cache()
    finally:
        db.close()
    return removed


def delete_document_artifacts(doc: Document) -> None:
    """Remove physical uploaded file and extracted JSON safely."""
    settings = get_settings()
    try:
        upload_path = resolve_safe_storage_path(settings.storage_path, "uploads", doc.stored_name)
        if upload_path.exists():
            upload_path.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        ext_path = resolve_safe_storage_path(settings.storage_path, "extracted", f"{doc.id}.json")
        if ext_path.exists():
            ext_path.unlink(missing_ok=True)
    except Exception:
        pass


def _retention_loop() -> None:
    while not _stop_event.wait(86400):
        try:
            purge_expired_submissions()
        except Exception:
            logger.exception("Error during periodic retention purge")


def start_worker() -> None:
    global _executor, _retention_thread
    settings = get_settings()
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=max(1, settings.WORKER_THREADS), thread_name_prefix="ng-worker")

    # Purge expired data if configured
    purge_expired_submissions()

    # Recover QUEUED or interrupted PROCESSING checks on startup
    factory = get_session_factory()
    db = factory()
    try:
        pending = (
            db.query(Check)
            .filter(Check.status.in_(["QUEUED", "PROCESSING"]))
            .order_by(Check.created_at.asc())
            .all()
        )
        for chk in pending:
            chk.status = "QUEUED"
            chk.stage = "Antrean (Pemulihan)"
            db.commit()
            enqueue_check(chk.id)
    finally:
        db.close()

    if settings.RETENTION_DAYS > 0 and (_retention_thread is None or not _retention_thread.is_alive()):
        _stop_event.clear()
        _retention_thread = threading.Thread(target=_retention_loop, daemon=True, name="ng-retention")
        _retention_thread.start()


def stop_worker() -> None:
    global _executor
    _stop_event.set()
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=False)
            _executor = None
