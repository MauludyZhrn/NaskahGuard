"""Unit tests for file validators, sanitization, and path traversal prevention."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.ingestion.validators import (
    resolve_safe_storage_path,
    sanitize_filename,
    validate_local_bytes,
    validate_magic_bytes,
)


def _make_minimal_docx(include_vba: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Halo dunia akademik.</w:t></w:r></w:p></w:body></w:document>',
        )
        if include_vba:
            zf.writestr("word/vbaProject.bin", b"FAKEVBA")
    return buf.getvalue()


def test_sanitize_filename_removes_traversal_and_special_chars():
    clean = sanitize_filename("../../etc/passwd;rm -rf *.pdf")
    assert ".." not in clean
    assert "/" not in clean
    assert "\\" not in clean
    assert clean.endswith(".pdf")


def test_resolve_safe_storage_path_blocks_traversal(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        resolve_safe_storage_path(tmp_path, "..", "secret.txt")
    assert exc.value.status_code == 400


def test_validate_magic_bytes_rejects_spoofed_pdf_and_binary_txt():
    with pytest.raises(HTTPException):
        validate_magic_bytes(".pdf", b"NOT A PDF FILE")
    with pytest.raises(HTTPException):
        validate_magic_bytes(".txt", b"hello\x00world")


def test_validate_docx_rejects_vba_macro():
    raw_bad = _make_minimal_docx(include_vba=True)
    with pytest.raises(HTTPException):
        validate_magic_bytes(".docx", raw_bad)
    raw_ok = _make_minimal_docx(include_vba=False)
    validate_magic_bytes(".docx", raw_ok)


def test_validate_local_bytes_size_limit():
    with pytest.raises(ValueError):
        validate_local_bytes("sample.txt", b"a" * 200, max_bytes=100)
