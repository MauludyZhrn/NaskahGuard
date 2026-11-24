"""Shared pytest fixtures for isolated DB and local storage per test session/module."""

from __future__ import annotations

from pathlib import Path
import pytest

from app import config, db as db_mod
from app.main import run_migrations


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    storage = tmp_path / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    monkeypatch.setenv("NG_DATABASE_URL", db_url)
    monkeypatch.setenv("NG_STORAGE_DIR", str(storage))
    monkeypatch.setenv("NG_API_TOKEN", "")
    monkeypatch.setenv("NG_HOST", "127.0.0.1")
    monkeypatch.setenv("NG_RATE_LIMIT_PER_MIN", "0")
    config.get_settings.cache_clear()

    run_migrations(db_url)
    yield tmp_path
    engine = db_mod.get_engine()
    db_mod.Base.metadata.drop_all(bind=engine)
    config.get_settings.cache_clear()
