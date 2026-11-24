"""JSON report exporter."""

from __future__ import annotations

import json
from typing import Any


def render_json_bytes(report: dict[str, Any]) -> bytes:
    return json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
