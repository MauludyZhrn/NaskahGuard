"""Automated Phase 9 Playwright UI/UX, Responsive & Screenshot QA Suite.

Tests all 5 required viewports:
- Desktop 1600x900
- Desktop 1440x900
- Desktop 1280x800
- Tablet 768x1024
- Mobile 390x844

Verifies:
- ZERO duplicate navigation (desktop tabs and mobile select are NEVER both visible!)
- ZERO horizontal overflow across all viewports and key routes
- Sidebar collapse, expand, and localStorage persistence
- Report "Penjelasan Perhitungan Similarity" accordion + Expand All / Collapse All
- Light mode & Dark mode consistency
- Document viewer sticky toolbar + Source matching table & detail modal
- Saves PNG screenshots of key pages into `docs/screenshots/phase9/`
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
SCREENSHOT_DIR = ROOT / "docs" / "screenshots" / "phase9"
BACKEND_PORT = 8019
FRONTEND_PORT = 4179


class SPAProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIST), **kwargs)

    def log_message(self, format, *args):
        return

    def _proxy_api(self):
        target = f"http://127.0.0.1:{BACKEND_PORT}{self.path}"
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else None
        req = urllib.request.Request(target, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in {"content-type", "authorization"}:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() in {"content-type", "content-disposition"}:
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as err:
            data = err.read()
            self.send_response(err.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy_api()
        rel = self.path.split("?", 1)[0].lstrip("/")
        if rel and (FRONTEND_DIST / rel).is_file():
            return super().do_GET()
        self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy_api()
        self.send_error(405)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            return self._proxy_api()
        self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            return self._proxy_api()
        self.send_error(405)


def wait_for_health(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"Backend did not become ready at {url}")


def seed_sample_check() -> str:
    import httpx

    base = f"http://127.0.0.1:{BACKEND_PORT}/api"
    with httpx.Client(base_url=base, timeout=30.0) as client:
        corpus_text = (
            "Sistem deteksi kemiripan dokumen akademik NaskahGuard menggunakan algoritma sidik jari Winnowing "
            "dan penyelarasan token untuk menemukan kecocokan teks identik serta hampir identik secara transparan."
        ).encode("utf-8")
        r1 = client.post(
            "/corpus",
            files={"file": ("sumber_qa_phase9.txt", corpus_text, "text/plain")},
            data={"title": "Dokumen Referensi QA Phase 9", "authors": "Tim Riset NaskahGuard", "year": "2025"},
        )
        r1.raise_for_status()

        sub_text = (
            "BAB I PENDAHULUAN\n\n"
            "Sistem deteksi kemiripan dokumen akademik NaskahGuard menggunakan algoritma sidik jari Winnowing "
            "dan penyelarasan token untuk menemukan kecocokan teks identik serta hampir identik secara transparan.\n\n"
            "BAB II PEMBAHASAN\n\n"
            "Pengujian antarmuka Phase 9 memverifikasi tata letak proporsional, penghapusan navigasi ganda, "
            "dan transparansi penuh perhitungan skor pada semua ukuran layar.\n"
        ).encode("utf-8")
        r2 = client.post("/documents", files={"file": ("naskah_qa_phase9.txt", sub_text, "text/plain")})
        r2.raise_for_status()
        doc_id = r2.json()["id"]

        r3 = client.post("/checks", json={"document_id": doc_id, "settings": {"min_match_words": 5}})
        r3.raise_for_status()
        check_id = r3.json()["check_id"]

        for _ in range(40):
            st = client.get(f"/checks/{check_id}").json()
            if st["status"] == "COMPLETED":
                return check_id
            if st["status"] == "FAILED":
                raise RuntimeError(f"QA check failed: {st.get('error')}")
            time.sleep(0.25)
    raise RuntimeError("QA check timed out")


def main() -> None:
    if not FRONTEND_DIST.exists():
        raise RuntimeError(f"frontend/dist not found at {FRONTEND_DIST}. Run npm run build first.")

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ng_qa9_") as tmpdir:
        tmp = Path(tmpdir)
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{(tmp / 'qa9.db').as_posix()}"
        env["STORAGE_DIR"] = str(tmp / "storage")
        env["APP_HOST"] = "127.0.0.1"
        env["APP_PORT"] = str(BACKEND_PORT)

        py_exe = str(BACKEND_DIR / ".venv" / "Scripts" / "python.exe")
        backend_proc = subprocess.Popen(
            [py_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        httpd = socketserver.TCPServer(("127.0.0.1", FRONTEND_PORT), SPAProxyHandler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        results: dict = {
            "viewports_tested": ["1600x900", "1440x900", "1280x800", "768x1024", "390x844"],
            "checks": [],
            "duplicate_nav_violations": [],
            "screenshots": [],
            "console_errors": [],
            "page_errors": [],
        }
        try:
            wait_for_health(f"http://127.0.0.1:{BACKEND_PORT}/api/health")
            check_id = seed_sample_check()
            base_url = f"http://127.0.0.1:{FRONTEND_PORT}"

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()
                page.on("console", lambda msg: results["console_errors"].append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda err: results["page_errors"].append(str(err)))

                # 1. Test all 5 required viewports on Report page + Dashboard + New Check + Discovery Monitor
                viewports = [
                    (1600, 900),
                    (1440, 900),
                    (1280, 800),
                    (768, 1024),
                    (390, 844),
                ]
                routes = [
                    "/",
                    "/new-check",
                    "/discovery-monitor",
                    "/repositories",
                    "/analytics",
                    f"/reports/{check_id}",
                ]

                for vw, vh in viewports:
                    page.set_viewport_size({"width": vw, "height": vh})
                    target_routes = routes if vw in (1440, 390) else ["/", "/new-check", f"/reports/{check_id}"]
                    for route in target_routes:
                        page.goto(f"{base_url}{route}", wait_until="networkidle")
                        page.wait_for_timeout(300)
                        overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                        results["checks"].append(
                            {"viewport": f"{vw}x{vh}", "route": route, "horizontal_overflow": overflow}
                        )

                        # Strictly check Report navigation mutual exclusivity!
                        if route.startswith("/reports/"):
                            tabs_vis = page.locator(".tabs-bar").is_visible()
                            mob_vis = page.locator(".mobile-tab-select").is_visible()
                            if (tabs_vis and mob_vis) or (not tabs_vis and not mob_vis):
                                results["duplicate_nav_violations"].append(
                                    {"viewport": f"{vw}x{vh}", "tabs_visible": tabs_vis, "mobile_select_visible": mob_vis}
                                )

                # 2. Capture Desktop (1440x900) Light & Dark screenshots + interactive checks
                page.set_viewport_size({"width": 1440, "height": 900})

                for slug, route in [
                    ("01_dashboard_light", "/"),
                    ("02_new_check_light", "/new-check"),
                    ("03_discovery_monitor_light", "/discovery-monitor"),
                    ("04_report_overview_light", f"/reports/{check_id}"),
                ]:
                    page.goto(f"{base_url}{route}", wait_until="networkidle")
                    page.wait_for_timeout(350)
                    shot_path = SCREENSHOT_DIR / f"{slug}.png"
                    page.screenshot(path=str(shot_path), full_page=False)
                    results["screenshots"].append(str(shot_path.relative_to(ROOT)))

                # Verify Report Accordions (Expand All / Collapse All + Penjelasan Perhitungan Similarity)
                page.goto(f"{base_url}/reports/{check_id}", wait_until="networkidle")
                page.wait_for_timeout(250)
                formula_visible = page.get_by_text("Rumus Similarity Index (Adjusted):").is_visible()
                if not formula_visible:
                    page.get_by_text("Penjelasan Perhitungan Similarity").click()
                    page.wait_for_timeout(200)
                    formula_visible = page.get_by_text("Rumus Similarity Index (Adjusted):").is_visible()
                results["formula_accordion_visible"] = formula_visible

                # Collapse All then Expand All
                if page.get_by_text("Perluas Semua Bagian").is_visible():
                    page.get_by_text("Perluas Semua Bagian").click()
                    page.wait_for_timeout(200)
                results["expand_all_works"] = page.get_by_text("Ciutkan Semua Bagian").is_visible()
                page.get_by_text("Ciutkan Semua Bagian").click()
                page.wait_for_timeout(200)
                results["collapse_all_works"] = page.get_by_text("Perluas Semua Bagian").is_visible()

                # Check Compare Viewer Sticky Toolbar & Source Matching Table + Detail Dialog
                page.get_by_role("tab", name="Perbandingan Dokumen").click()
                page.wait_for_timeout(250)
                results["viewer_sticky_toolbar_visible"] = page.locator(".viewer-toolbar-sticky").is_visible()
                shot_cmp = SCREENSHOT_DIR / "05_report_compare_viewer.png"
                page.screenshot(path=str(shot_cmp), full_page=False)
                results["screenshots"].append(str(shot_cmp.relative_to(ROOT)))

                page.get_by_role("tab", name="Sumber Cocok", exact=False).click()
                page.wait_for_timeout(250)
                page.get_by_role("button", name="Detail").first.click()
                page.wait_for_timeout(200)
                results["source_detail_dialog_visible"] = page.get_by_text("Kontribusi Eksklusif:").is_visible()
                page.keyboard.press("Escape")
                page.wait_for_timeout(150)

                # Sidebar Collapse, Expand & Persistence
                page.goto(f"{base_url}/", wait_until="networkidle")
                w_expanded = page.locator("aside.sidebar").evaluate("el => el.getBoundingClientRect().width")
                page.get_by_label("Ciutkan sidebar").click()
                page.wait_for_timeout(250)
                w_collapsed = page.locator("aside.sidebar").evaluate("el => el.getBoundingClientRect().width")
                page.reload(wait_until="networkidle")
                persisted = page.locator("aside.sidebar").get_attribute("data-collapsed") == "true"
                page.get_by_label("Perluas sidebar").click()
                page.wait_for_timeout(250)
                w_reexpanded = page.locator("aside.sidebar").evaluate("el => el.getBoundingClientRect().width")
                results["sidebar"] = {
                    "expanded_width": round(w_expanded),
                    "collapsed_width": round(w_collapsed),
                    "reexpanded_width": round(w_reexpanded),
                    "persisted_after_reload": persisted,
                }

                # Dark Mode Verification & Screenshot
                page.goto(f"{base_url}/reports/{check_id}", wait_until="networkidle")
                page.get_by_label("Aktifkan mode gelap").click()
                page.wait_for_timeout(250)
                results["dark_mode_applied"] = page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
                shot_dark = SCREENSHOT_DIR / "06_report_overview_dark.png"
                page.screenshot(path=str(shot_dark), full_page=False)
                results["screenshots"].append(str(shot_dark.relative_to(ROOT)))

                # Mobile 390x844 Screenshot (showing clean mobile selector with zero duplicate tabs!)
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(250)
                shot_mob = SCREENSHOT_DIR / "07_report_mobile_390.png"
                page.screenshot(path=str(shot_mob), full_page=False)
                results["screenshots"].append(str(shot_mob.relative_to(ROOT)))

                browser.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_proc.kill()

    out_json = ROOT / "benchmark" / "results" / "phase9_ui_qa.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    assert not any(c["horizontal_overflow"] for c in results["checks"]), f"Overflow detected: {results['checks']}"
    assert not results["duplicate_nav_violations"], f"Duplicate nav violation: {results['duplicate_nav_violations']}"
    assert not results["console_errors"], f"Console errors: {results['console_errors']}"
    assert not results["page_errors"], f"Page errors: {results['page_errors']}"
    assert results["formula_accordion_visible"], "Formula accordion failed!"
    assert results["expand_all_works"] and results["collapse_all_works"], "Expand/Collapse all failed!"
    assert results["viewer_sticky_toolbar_visible"], "Viewer sticky toolbar not visible!"
    assert results["source_detail_dialog_visible"], "Source detail dialog failed!"
    assert results["sidebar"]["collapsed_width"] <= 76 and results["sidebar"]["persisted_after_reload"]
    assert results["dark_mode_applied"], "Dark mode failed!"


if __name__ == "__main__":
    main()
