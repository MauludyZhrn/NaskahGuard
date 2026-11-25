"""Live Playwright E2E verification for UNDIP in the Tambah Repositori Akademik modal (Phase 10.4.2)."""

from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5173"
SHOT_PATH = Path("docs/screenshots/phase10_after/25_undip_modal_wizard_pass.png")
ERR_SHOT_PATH = Path("docs/screenshots/phase10_after/26_oai_structured_error_alert.png")
OUT_JSON = Path("benchmark/results/phase10_4_2_undip_ui_e2e.json")


def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    SHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    network_events: list[dict[str, object]] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        def _on_response(resp) -> None:
            if "/api/oai/" in resp.url:
                network_events.append({"method": resp.request.method, "url": resp.url, "status": resp.status})

        page.on("response", _on_response)

        # Clean up UNDIP if already present in personal list from previous manual/live runs
        existing = page.request.get(f"{BASE_URL}/api/oai/repositories").json()
        for item in existing:
            if "eprints2.undip.ac.id" in item.get("base_url", ""):
                page.request.delete(f"{BASE_URL}/api/oai/repositories/{item['id']}")

        page.goto(f"{BASE_URL}/repositories", wait_until="networkidle")
        page.get_by_role("button", name="Tambah Repositori").first.click()
        page.wait_for_selector("#add-repo-url")

        # 1. Verify structured error UI (no bare generic "Not Found") on non-OAI 404 host
        page.fill("#add-repo-url", "https://example.org/cgi/oai2")
        page.get_by_role("button", name="Deteksi").click()
        page.wait_for_selector("text=Deteksi Otomatis Belum Menemukan Endpoint OAI-PMH", timeout=30000)
        page.screenshot(path=str(ERR_SHOT_PATH), full_page=False)
        err_dialog_text = page.locator("[role='dialog']").inner_text()
        assert "Endpoint OAI-PMH tidak ditemukan" in err_dialog_text
        assert "Tahap yang gagal" in err_dialog_text
        assert "URL yang sedang diuji" in err_dialog_text
        assert "Status HTTP" in err_dialog_text
        assert "Penyebab" in err_dialog_text
        assert "Saran perbaikan" in err_dialog_text
        assert "Gagal memproses — Not Found" not in err_dialog_text

        # 2. Test real UNDIP endpoint: Deteksi -> Uji Koneksi (8 Tahap) -> Simpan Repositori
        page.fill("#add-repo-url", "https://eprints2.undip.ac.id/cgi/oai2")
        page.get_by_role("button", name="Deteksi").click()
        page.wait_for_selector("text=Endpoint OAI-PMH Terdeteksi", timeout=30000)

        page.get_by_role("button", name="Uji Koneksi (8 Tahap)").click()
        page.wait_for_selector("text=Siap Dipanen", timeout=60000)
        page.screenshot(path=str(SHOT_PATH), full_page=False)

        pass_dialog_text = page.locator("[role='dialog']").inner_text()
        assert "Undip Repository" in pass_dialog_text
        assert "8 lulus" in pass_dialog_text
        assert "Mode Metadata Saja (Default)" in pass_dialog_text

        # Click Simpan Repositori
        page.get_by_role("button", name="Simpan Repositori").click()
        page.wait_for_selector("text=Repositori UNDIP berhasil ditambahkan dalam mode Metadata Saja", timeout=20000)

        # Verify persisted item enforces metadata-only policy in backend API & clean up test row
        saved = page.request.get(f"{BASE_URL}/api/oai/repositories").json()
        undip_saved = next((r for r in saved if "eprints2.undip.ac.id" in r.get("base_url", "")), None)
        assert undip_saved is not None
        assert undip_saved["fulltext_policy"] == "METADATA_ONLY_DEFAULT"
        assert undip_saved["harvesting_permission_status"] == "METADATA_ALLOWED_FULLTEXT_RESTRICTED"
        assert undip_saved["default_download_pdfs"] is False
        assert undip_saved["status"] == "VERIFIED"

        # Clean up test entry so personal workspace remains tidy
        page.request.delete(f"{BASE_URL}/api/oai/repositories/{undip_saved['id']}")
        browser.close()

    report = {
        "passed": True,
        "tested_url": "https://eprints2.undip.ac.id/cgi/oai2",
        "network_oai_calls": network_events,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "undip_saved_policy_verified": {
            "fulltext_policy": undip_saved["fulltext_policy"],
            "harvesting_permission_status": undip_saved["harvesting_permission_status"],
            "default_download_pdfs": undip_saved["default_download_pdfs"],
            "status": undip_saved["status"],
        },
        "screenshots": [str(SHOT_PATH), str(ERR_SHOT_PATH)],
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
