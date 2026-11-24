"""File upload validation, filename sanitization, and path traversal protection."""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ACQUIRED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".xml"}
_SAFE_FILENAME_RE = re.compile(r"[^\w\-. ]", re.UNICODE)

MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".html": "text/html",
    ".xml": "application/xml",
}


@dataclass(frozen=True)
class ValidatedUpload:
    clean_filename: str
    file_type: str
    mime: str
    size_bytes: int
    file_hash: str
    raw_bytes: bytes


def sanitize_filename(filename: str | None) -> str:
    base = os.path.basename((filename or "dokumen").strip())
    base = _SAFE_FILENAME_RE.sub("_", base).strip(" .")
    if not base:
        base = "dokumen"
    if len(base) > 150:
        stem, ext = os.path.splitext(base)
        base = stem[: 150 - len(ext)] + ext
    return base


def resolve_safe_storage_path(storage_dir: Path, *parts: str) -> Path:
    root = storage_dir.resolve()
    target = (root / Path(*parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path berkas tidak valid (terdeteksi path traversal).",
        ) from exc
    return target


def validate_magic_bytes(ext: str, raw: bytes) -> None:
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Berkas kosong tidak dapat diproses.")

    if ext == ".pdf":
        if not raw.lstrip()[:5].startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="Berkas PDF tidak valid (signature %PDF- tidak ditemukan).",
            )
    elif ext == ".docx":
        if not raw.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=400,
                detail="Berkas DOCX tidak valid (bukan arsip ZIP OOXML).",
            )
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = set(zf.namelist())
                if "word/document.xml" not in names:
                    raise HTTPException(
                        status_code=400,
                        detail="Berkas DOCX tidak valid (word/document.xml tidak ditemukan).",
                    )
                if any(name.lower().endswith("vbaproject.bin") for name in names):
                    raise HTTPException(
                        status_code=400,
                        detail="Berkas DOCX yang mengandung makro VBA ditolak demi keamanan.",
                    )
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Berkas DOCX rusak atau tidak dapat dibuka.") from exc
    elif ext == ".txt":
        if b"\x00" in raw:
            raise HTTPException(
                status_code=400,
                detail="Berkas TXT mengandung byte biner (NUL) dan ditolak.",
            )
        try:
            raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                raw.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Berkas TXT tidak dapat didekode sebagai UTF-8 maupun CP1252.",
                ) from exc


async def read_and_validate_upload(file: UploadFile, max_bytes: int) -> ValidatedUpload:
    clean_name = sanitize_filename(file.filename)
    ext = os.path.splitext(clean_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipe berkas '{ext or 'tanpa ekstensi'}' tidak didukung. Gunakan PDF, DOCX, atau TXT.",
        )

    chunks: list[bytes] = []
    total = 0
    chunk_size = 256 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Ukuran berkas melebihi batas maksimum ({max_bytes // (1024 * 1024)} MB).",
            )
        chunks.append(chunk)

    raw = b"".join(chunks)
    validate_magic_bytes(ext, raw)
    file_hash = hashlib.sha256(raw).hexdigest()
    return ValidatedUpload(
        clean_filename=clean_name,
        file_type=ext.lstrip("."),
        mime=MIME_BY_EXT[ext],
        size_bytes=total,
        file_hash=file_hash,
        raw_bytes=raw,
    )


def validate_local_bytes(
    filename: str,
    raw: bytes,
    max_bytes: int,
    *,
    allow_web_formats: bool = False,
) -> ValidatedUpload:
    clean_name = sanitize_filename(filename)
    ext = os.path.splitext(clean_name)[1].lower()
    allowed = ACQUIRED_EXTENSIONS if allow_web_formats else ALLOWED_EXTENSIONS
    if ext not in allowed:
        raise ValueError(f"Ekstensi tidak didukung: {ext}")
    if len(raw) > max_bytes:
        raise ValueError("Ukuran berkas melebihi batas maksimum.")
    if ext in ALLOWED_EXTENSIONS:
        validate_magic_bytes(ext, raw)
    elif len(raw) == 0:
        raise ValueError("Konten kosong.")
    file_hash = hashlib.sha256(raw).hexdigest()
    return ValidatedUpload(
        clean_filename=clean_name,
        file_type=ext.lstrip("."),
        mime=MIME_BY_EXT[ext],
        size_bytes=len(raw),
        file_hash=file_hash,
        raw_bytes=raw,
    )
