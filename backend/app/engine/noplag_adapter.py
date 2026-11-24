"""Optional loopback-only adapter for an external local Noplag Engine instance."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.security import validate_loopback_url


class NoplagAdapter:
    """HTTP adapter restricted strictly to loopback addresses."""

    def __init__(self, base_url: str | None = None) -> None:
        raw_url = (base_url if base_url is not None else get_settings().NOPLAG_ENGINE_URL).strip()
        self.base_url = validate_loopback_url(raw_url) if raw_url else ""

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def health(self) -> dict[str, Any]:
        if not self.base_url:
            return {"configured": False, "reachable": False, "detail": "NOPLAG_ENGINE_URL belum dikonfigurasi."}
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/health")
                return {
                    "configured": True,
                    "reachable": resp.status_code < 400,
                    "status_code": resp.status_code,
                    "url": self.base_url,
                }
        except Exception as exc:
            return {"configured": True, "reachable": False, "detail": str(exc), "url": self.base_url}

    def check_text(self, query_text: str) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("Noplag Engine tidak dikonfigurasi.")
        with httpx.Client(timeout=30.0) as client:
            submit = client.post(f"{self.base_url}/v1/checks", json={"query_text": query_text})
            submit.raise_for_status()
            check_id = submit.json()["check_id"]
            report = client.get(f"{self.base_url}/v1/checks/{check_id}/report")
            report.raise_for_status()
            return report.json()
