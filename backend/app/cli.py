"""CLI utilities for batch corpus import and retention cleanup."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.db import get_session_factory
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import ALLOWED_EXTENSIONS, validate_local_bytes
from app.main import run_migrations
from app.worker import purge_expired_submissions


def cmd_import_corpus(folder: str, source_type: str) -> int:
    settings = get_settings()
    run_migrations(settings.DATABASE_URL)
    target = Path(folder).resolve()
    if not target.exists() or not target.is_dir():
        print(f"Folder tidak ditemukan: {target}")
        return 1

    factory = get_session_factory()
    db = factory()
    imported = 0
    skipped = 0
    try:
        for file_path in sorted(target.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            try:
                raw = file_path.read_bytes()
                validated = validate_local_bytes(file_path.name, raw, settings.max_upload_bytes)
                ingest_validated_upload(
                    db,
                    validated,
                    role="CORPUS",
                    source_type=source_type,
                    access_status="INDEXED_LOCALLY",
                )
                imported += 1
                print(f"[OK] {file_path.name}")
            except Exception as exc:
                skipped += 1
                print(f"[LEWAT] {file_path.name}: {exc}")
    finally:
        db.close()

    print(f"Selesai. Diimpor: {imported}, dilewati: {skipped}.")
    return 0


def cmd_purge_retention() -> int:
    settings = get_settings()
    run_migrations(settings.DATABASE_URL)
    removed = purge_expired_submissions()
    print(f"Pembersihan retensi selesai. Dokumen dihapus: {removed}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="naskahguard-cli", description="CLI Manajemen NaskahGuard")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("import-corpus", help="Impor folder PDF/DOCX/TXT ke korpus lokal")
    p_imp.add_argument("folder", help="Path folder berisi dokumen korpus")
    p_imp.add_argument("--source-type", default="local_corpus", help="Label source_type")

    sub.add_parser("purge-retention", help="Jalankan pembersihan data submission berdasarkan RETENTION_DAYS")

    args = parser.parse_args()
    if args.command == "import-corpus":
        return cmd_import_corpus(args.folder, args.source_type)
    if args.command == "purge-retention":
        return cmd_purge_retention()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
