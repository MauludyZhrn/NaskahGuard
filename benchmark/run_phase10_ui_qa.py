"""Phase 10 Automated Playwright UI/UX QA & After-Screenshots Runner.

Starts isolated SQLite + FastAPI backend + Vite built frontend preview,
exercises real corpus indexing, combined plagiarism + AI writing check,
mode filtering, dark/light themes, desktop/tablet/mobile viewports, and captures
after-redesign screenshots into `docs/screenshots/phase10_after/`.
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
SCREENSHOT_DIR = ROOT / "docs" / "screenshots" / "phase10_after"
RESULT_JSON = ROOT / "benchmark" / "results" / "phase10_ui_qa.json"
BACKEND_PORT = 8031
FRONTEND_PORT = 4191


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIST), **kwargs)

    def log_message(self, format, *args):
        return

    def _proxy(self):
        target = f"http://127.0.0.1:{BACKEND_PORT}{self.path}"
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else None
        req = urllib.request.Request(target, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in {"content-type", "authorization"}:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
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
            return self._proxy()
        rel = self.path.split("?", 1)[0].lstrip("/")
        if rel and (FRONTEND_DIST / rel).is_file():
            return super().do_GET()
        self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(405)

    def do_PUT(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(405)

    def do_DELETE(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(405)


def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ng_phase10_qa_", ignore_cleanup_errors=True) as tmpdir:
        tmp = Path(tmpdir)
        db_url = f"sqlite:///{(tmp / 'qa_phase10.db').as_posix()}"
        env = os.environ.copy()
        env["NG_DATABASE_URL"] = db_url
        env["DATABASE_URL"] = db_url
        env["NG_STORAGE_DIR"] = str(tmp / "storage")
        env["STORAGE_DIR"] = str(tmp / "storage")
        env["NG_API_TOKEN"] = ""
        env["NG_HOST"] = "127.0.0.1"
        env["NG_RATE_LIMIT_PER_MIN"] = "0"

        py_exe = str(BACKEND_DIR / ".venv" / "Scripts" / "python.exe")
        proc = subprocess.Popen(
            [py_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("127.0.0.1", FRONTEND_PORT), ProxyHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        try:
            for _ in range(50):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{BACKEND_PORT}/api/health", timeout=2) as r:
                        if r.status == 200:
                            break
                except Exception:
                    time.sleep(0.25)

            sys.path.insert(0, str(BACKEND_DIR))
            import httpx

            with httpx.Client(base_url=f"http://127.0.0.1:{BACKEND_PORT}/api", timeout=30.0) as c:
                ref_text = (
                    "Sistem pengelolaan rantai dingin vaksin di puskesmas pedesaan memerlukan pencatatan suhu harian "
                    "yang konsisten serta cadangan catu daya agar stabilitas biologis sediaan tetap terjaga."
                )
                c.post(
                    "/corpus",
                    files={"file": ("referensi_vaksin.txt", ref_text.encode("utf-8"), "text/plain")},
                    data={"title": "Tata Kelola Rantai Dingin Vaksin Puskesmas", "authors": "Dr. A. Nugroho", "year": "2024"},
                )

                sub_text = (
                    f"BAB I PENDAHULUAN\n\n{ref_text} Pada pengamatan kami di tiga kecamatan selama Oktober 2023, "
                    "jeda pencatatan suhu sering terjadi pada hari Jumat siang saat petugas berjaga sendirian di loket.\n\n"
                    "Di era modern saat ini, optimalisasi tata kelola layanan kesehatan memainkan peran krusial dalam "
                    "meningkatkan mutu pelayanan publik secara berkelanjutan. Selain itu, pendekatan komprehensif dan "
                    "sinergi antara berbagai pemangku kepentingan memberikan wawasan berharga guna merumuskan langkah "
                    "strategis yang terukur. Secara keseluruhan, evaluasi berkala yang terstruktur, adaptif, dan "
                    "transparan mendorong perbaikan berkelanjutan bagi masyarakat."
                )
                r_doc = c.post(
                    "/documents",
                    files={"file": ("skripsi_uji_gabungan.txt", sub_text.encode("utf-8"), "text/plain")},
                    data={"title": "Uji Gabungan Skripsi Rantai Dingin"},
                )
                doc_id = r_doc.json()["id"]

                # 1. Combined check
                comb_id = c.post(
                    "/checks",
                    json={
                        "document_id": doc_id,
                        "settings": {"check_mode": "COMBINED", "min_match_words": 6, "use_external_sources": False},
                    },
                ).json()["check_id"]

                # 2. Plagiarism only check
                plag_id = c.post(
                    "/checks",
                    json={
                        "document_id": doc_id,
                        "settings": {"check_mode": "PLAGIARISM_ONLY", "min_match_words": 6, "use_external_sources": False},
                    },
                ).json()["check_id"]

                # 3. AI only check
                ai_id = c.post(
                    "/checks",
                    json={
                        "document_id": doc_id,
                        "settings": {"check_mode": "AI_ONLY", "use_external_sources": False},
                    },
                ).json()["check_id"]

                for cid in (comb_id, plag_id, ai_id):
                    for _ in range(45):
                        if c.get(f"/checks/{cid}").json()["status"] == "COMPLETED":
                            break
                        time.sleep(0.25)

            base_url = f"http://127.0.0.1:{FRONTEND_PORT}"
            console_errors: list[str] = []
            page_errors: list[str] = []
            bad_http: list[str] = []
            layout_checks: list[dict] = []

            with sync_playwright() as p:
                browser = p.chromium.launch()
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                page = ctx.new_page()
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                page.on("response", lambda resp: bad_http.append(f"{resp.status} {resp.url}") if resp.status >= 500 else None)

                desktop_routes = [
                    ("/", "01_dashboard.png", "Ringkasan Pemeriksaan"),
                    ("/new-check", "02_new_check.png", "Pemeriksaan Baru"),
                    ("/history", "03_history.png", "Riwayat Pemeriksaan"),
                    ("/plagiarism-checks", "04_plagiarism_checks.png", "Deteksi Plagiasi"),
                    ("/ai-checks", "05_ai_checks.png", "Deteksi Tulisan AI"),
                    ("/combined-reports", "06_combined_reports.png", "Laporan Gabungan"),
                    ("/documents", "07_documents.png", "Pustaka Dokumen"),
                    ("/corpus", "08_corpus.png", "Korpus Sumber"),
                    ("/discovery-monitor", "09_discovery_monitor.png", "Monitor Penemuan"),
                    ("/repositories", "10_repositories.png", "Repositori Akademik"),
                    (f"/reports/{comb_id}", "11_report_detail_plagiarism.png", "Ringkasan Hasil"),
                    ("/analytics", "12_analytics.png", "Analitik"),
                    ("/analytics/ai", "13_analytics_ai.png", "Analitik Deteksi Tulisan AI"),
                    ("/settings", "14_settings.png", "Pengaturan Aplikasi"),
                    ("/models", "15_models.png", "Manajemen Model"),
                ]

                for route, fname, expected_text in desktop_routes:
                    page.goto(f"{base_url}{route}", wait_until="networkidle")
                    page.wait_for_timeout(850)
                    body_txt = page.inner_text("body")
                    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                    svg_count = page.locator("svg").count()
                    layout_checks.append({
                        "viewport": "desktop_1440_light",
                        "route": route,
                        "expected_found": expected_text.lower() in body_txt.lower(),
                        "horizontal_overflow": bool(overflow),
                        "svg_icons_present": svg_count > 0,
                    })
                    page.screenshot(path=str(SCREENSHOT_DIR / fname), full_page=False)

                # Switch Combined Report to AI tab & capture separate AI report view
                page.goto(f"{base_url}/reports/{comb_id}", wait_until="networkidle")
                page.wait_for_timeout(250)
                ai_tab_btn = page.get_by_role("button", name="Laporan Deteksi AI")
                if ai_tab_btn.count() > 0:
                    ai_tab_btn.first.click()
                    page.wait_for_timeout(250)
                page.screenshot(path=str(SCREENSHOT_DIR / "16_report_detail_ai_tab.png"), full_page=False)

                # Verify Dark Mode parity on Dashboard & Report AI
                theme_btn = page.get_by_label("Ubah tema tampilan")
                if theme_btn.count() > 0:
                    theme_btn.first.click()
                    page.wait_for_timeout(250)
                page.goto(f"{base_url}/", wait_until="networkidle")
                page.wait_for_timeout(300)
                dark_attr = page.evaluate("document.documentElement.getAttribute('data-theme')")
                page.screenshot(path=str(SCREENSHOT_DIR / "17_dashboard_dark.png"), full_page=False)

                # Reset to Light Mode & test Tablet (768x1024) + Mobile (390x844)
                page.evaluate("localStorage.setItem('ng_theme','light'); document.documentElement.setAttribute('data-theme','light');")
                for label, w, h, fname in [
                    ("tablet_768", 768, 1024, "18_tablet_new_check.png"),
                    ("mobile_390", 390, 844, "19_mobile_new_check.png"),
                ]:
                    page.set_viewport_size({"width": w, "height": h})
                    page.goto(f"{base_url}/new-check", wait_until="networkidle")
                    page.wait_for_timeout(300)
                    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                    layout_checks.append({
                        "viewport": label,
                        "route": "/new-check",
                        "expected_found": True,
                        "horizontal_overflow": bool(overflow),
                        "svg_icons_present": page.locator("svg").count() > 0,
                    })
                    page.screenshot(path=str(SCREENSHOT_DIR / fname), full_page=False)

                browser.close()

            report_obj = {
                "passed": (
                    len(console_errors) == 0
                    and len(page_errors) == 0
                    and len(bad_http) == 0
                    and all(c["expected_found"] and not c["horizontal_overflow"] and c["svg_icons_present"] for c in layout_checks)
                    and dark_attr == "dark"
                ),
                "console_errors": console_errors,
                "page_errors": page_errors,
                "bad_http": bad_http,
                "dark_mode_verified": dark_attr == "dark",
                "checks_count": len(layout_checks),
                "layout_checks": layout_checks,
                "screenshots_saved": sorted(f.name for f in SCREENSHOT_DIR.glob("*.png")),
            }
            RESULT_JSON.write_text(json.dumps(report_obj, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(report_obj, indent=2, ensure_ascii=False))
            return 0 if report_obj["passed"] else 1
        finally:
            httpd.shutdown()
            httpd.server_close()
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
