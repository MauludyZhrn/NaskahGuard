"""Phase 10 tests: AI writing detection, conservative guardrails, model registry, and E2E modes."""

from __future__ import annotations

import time
from fastapi.testclient import TestClient

from app.ai_detection.dataset_builder import build_all_splits
from app.ai_detection.detector import analyze_document_ai
from app.ai_detection.features import detect_text_language
from app.main import create_app


def _poll_check(client: TestClient, check_id: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/checks/{check_id}")
        assert res.status_code == 200
        data = res.json()
        if data["status"] in {"COMPLETED", "FAILED"}:
            return data
        time.sleep(0.12)
    raise AssertionError(f"Check {check_id} did not finish within {timeout}s")


def test_dataset_splits_are_disjoint_and_cover_all_categories():
    splits = build_all_splits()
    assert set(splits.keys()) == {"train", "validation", "test", "false_positive_stress"}
    train_texts = {r["text"] for r in splits["train"]}
    val_texts = {r["text"] for r in splits["validation"]}
    test_texts = {r["text"] for r in splits["test"]}
    assert train_texts.isdisjoint(val_texts)
    assert train_texts.isdisjoint(test_texts)
    assert val_texts.isdisjoint(test_texts)

    expected_cats = {
        "human_original_id",
        "human_original_en",
        "ai_pure_multi_style",
        "human_ai_assisted",
        "ai_human_edited",
        "ai_paraphrased",
        "academic_formal_human",
        "academic_nonformal_human",
    }
    assert expected_cats.issubset({r["category"] for r in splits["test"]})


def test_short_text_returns_insufficient_data():
    short_txt = "Penelitian ini hanya berisi ringkasan singkat tentang observasi awal di ruang kelas."
    res = analyze_document_ai(short_txt)
    assert res["score_available"] is False
    assert res["ai_likelihood_pct"] is None
    assert res["classification"] == "INSUFFICIENT_DATA"
    assert res["classification_label"] == "Tidak Cukup Bukti"


def test_false_positive_guardrails_on_formal_human_prose():
    splits = build_all_splits()
    for case in splits["false_positive_stress"]:
        res = analyze_document_ai(str(case["text"]))
        if case.get("expect_insufficient"):
            assert res["classification"] == "INSUFFICIENT_DATA", case["id"]
        else:
            assert res["classification"] != "AI_LIKELY", f"False positive on {case['id']}: {res['classification']} ({res['ai_likelihood_pct']}%)"


def test_language_detection_id_and_en():
    id_res = detect_text_language(
        "Penelitian ini menelaah hubungan antara tata kelola air dan ketahanan panen di tiga desa selama musim kemarau."
    )
    en_res = detect_text_language(
        "This paper investigates operational bottlenecks between frontline clerks and regional municipal supervisors over two quarters."
    )
    assert id_res["code"] == "id"
    assert en_res["code"] == "en"


def test_e2e_ai_only_and_combined_modes_and_model_registry(isolated_env):
    app = create_app()
    with TestClient(app) as client:
        # 1. Model management API
        m_list = client.get("/api/models")
        assert m_list.status_code == 200
        m_data = m_list.json()
        assert m_data["active_model_id"] == "ng-id-stylo-lm-v1"
        assert any(m["id"] == "ng-id-stylo-lm-v1" and m["installed"] for m in m_data["models"])

        v_res = client.post("/api/models/ng-id-stylo-lm-v1/verify")
        assert v_res.status_code == 200
        assert v_res.json()["verified"] is True

        # Optional HF model must refuse activation cleanly when optional deps/weights absent
        opt_act = client.post("/api/models/ng-fast-detect-curv-en/activate")
        assert opt_act.status_code == 400

        # 2. Prepare shared local corpus doc
        shared_passage = (
            "Sistem pengendalian persediaan reagen laboratorium di rumah sakit daerah menuntut "
            "pencatatan kedaluwarsa per kelompok uji agar tidak terjadi pemborosan anggaran tahunan."
        )
        r_corp = client.post(
            "/api/corpus",
            files={"file": ("ref_reagen.txt", (shared_passage + " " * 3).encode("utf-8"), "text/plain")},
            data={"title": "Manajemen Reagen RSUD", "authors": "R. Pratama", "year": "2023"},
        )
        assert r_corp.status_code == 201

        # Submission with both a copied sentence AND clear AI-style synthesis (~145 words)
        sub_text = (
            f"{shared_passage} Pada pengamatan kami di tiga gudang instalasi farmasi sepanjang Juli 2023, "
            "kartu stok manual kerap terlewat ketika petugas mengejar laporan akhir bulan.\n\n"
            "Di era modern saat ini, optimalisasi tata kelola layanan memainkan peran krusial dalam meningkatkan "
            "kualitas pelayanan publik secara berkelanjutan. Selain itu, pendekatan komprehensif dan sinergi antara "
            "berbagai pemangku kepentingan memberikan wawasan berharga guna merumuskan langkah strategis yang terukur. "
            "Secara keseluruhan, evaluasi berkala yang terstruktur, adaptif, dan transparan dapat mendorong perbaikan berkelanjutan."
        )
        r_sub = client.post(
            "/api/documents",
            files={"file": ("naskah_uji.txt", sub_text.encode("utf-8"), "text/plain")},
            data={"title": "Uji Gabungan"},
        )
        assert r_sub.status_code == 201
        doc_id = r_sub.json()["id"]

        # 3. Run AI_ONLY check
        c_ai = client.post(
            "/api/checks",
            json={"document_id": doc_id, "settings": {"check_mode": "AI_ONLY", "use_external_sources": False}},
        )
        assert c_ai.status_code == 202
        ai_chk_id = c_ai.json()["check_id"]
        ai_done = _poll_check(client, ai_chk_id)
        assert ai_done["status"] == "COMPLETED"
        assert ai_done["mode"] == "AI_ONLY"
        assert ai_done["metrics"]["similarity_index"] == 0.0
        assert ai_done["ai_report"] is not None
        assert ai_done["ai_report"]["score_available"] is True
        assert len(ai_done["ai_report"]["paragraphs"]) == 2

        # 4. Run COMBINED check & confirm plagiarism similarity_index is computed independently of AI score
        c_comb = client.post(
            "/api/checks",
            json={
                "document_id": doc_id,
                "settings": {"check_mode": "COMBINED", "use_external_sources": False},
            },
        )
        assert c_comb.status_code == 202
        comb_id = c_comb.json()["check_id"]
        comb_done = _poll_check(client, comb_id)
        assert comb_done["status"] == "COMPLETED"
        assert comb_done["mode"] == "COMBINED"
        assert comb_done["metrics"]["similarity_index"] > 0.0
        assert comb_done["ai_report"] is not None
        assert comb_done["metrics"]["similarity_index"] != comb_done["ai_report"]["ai_likelihood_pct"]

        # Mode filter on GET /checks
        only_ai = client.get("/api/checks?mode=AI_ONLY").json()
        assert any(x["id"] == ai_chk_id for x in only_ai)
        assert all(x["mode"] == "AI_ONLY" for x in only_ai)

        # Full report, plain_summary, HTML & PDF export
        rep = client.get(f"/api/checks/{comb_id}/report").json()
        assert rep["mode"] == "COMBINED"
        assert rep["ai_report"] is not None
        assert "plain_summary" in rep and "ai_answer" in rep["plain_summary"]

        html_res = client.get(f"/api/checks/{comb_id}/export.html")
        assert html_res.status_code == 200
        assert "Deteksi Pola Tulisan AI" in html_res.text

        pdf_res = client.get(f"/api/checks/{comb_id}/export.pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF")

        # Dashboard stats verify ai_stats without distorting plagiarism avg
        dash = client.get("/api/dashboard").json()
        assert dash["ai_stats"]["total_ai_analyzed"] >= 2
        assert dash["ai_stats"]["total_ai_only"] >= 1
        assert dash["ai_stats"]["total_combined"] >= 1
