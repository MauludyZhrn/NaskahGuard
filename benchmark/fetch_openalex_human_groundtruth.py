"""Fetch real pre-2022 open-access Indonesian, Legal/Islamic, and English academic abstracts from DOAJ & Europe PMC
for the Phase 10.2 independent AI detection validation dataset (pre-ChatGPT ground truth, explicit DOI/URL & CC license).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(r"d:\Projects\NaskahGuard")
OUT = ROOT / "benchmark" / "data" / "ai_detection_v2" / "real_human_open_access.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def _clean_text(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


DOAJ_QUERIES = [
    ("human_written_id", "id", "penelitian pendidikan masyarakat ekonomi"),
    ("formal_academic_id", "id", "metode penelitian analisis regresi sampel"),
    ("legal_islamic_id", "id", "hukum islam fiqh syariah perundang undangan"),
    ("legal_islamic_id", "id", "ilmu falak hisab rukyat mazhab syafii"),
    ("english_academic_en", "en", "empirical study survey methodology findings"),
    ("formal_academic_en", "en", "statutory governance audit framework policy"),
]


def _looks_indonesian(txt: str) -> bool:
    low = txt.lower().split()
    id_sw = {"yang", "dan", "dari", "pada", "dalam", "untuk", "dengan", "penelitian", "ini", "adalah", "hukum", "tidak"}
    en_sw = {"the", "and", "of", "in", "to", "that", "with", "this", "study", "results", "were"}
    id_c = sum(1 for w in low if w in id_sw)
    en_c = sum(1 for w in low if w in en_sw)
    return id_c >= 6 and id_c > en_c * 1.5


def _looks_english(txt: str) -> bool:
    low = txt.lower().split()
    id_sw = {"yang", "dan", "dari", "pada", "dalam", "untuk", "dengan", "penelitian", "ini", "adalah"}
    en_sw = {"the", "and", "of", "in", "to", "that", "with", "this", "study", "results", "were", "for"}
    id_c = sum(1 for w in low if w in id_sw)
    en_c = sum(1 for w in low if w in en_sw)
    return en_c >= 8 and en_c > id_c * 2.0


def main() -> int:
    collected: list[dict] = []
    seen_ids: set[str] = set()
    headers = {"User-Agent": "NaskahGuard-Phase10.2-Eval/1.0 (mailto:naskahguard@localhost.localdomain)"}

    with httpx.Client(timeout=40.0, headers=headers) as client:
        for category, lang, q in DOAJ_QUERIES:
            try:
                q_enc = quote(q)
                url = f"https://doaj.org/api/search/articles/{q_enc}?page=1&pageSize=40"
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as exc:
                print(f"WARN DOAJ {q}: {exc}")
                continue
            for item in resp.json().get("results", []):
                aid = str(item.get("id") or "")
                if not aid or aid in seen_ids:
                    continue
                bib = item.get("bibjson") or {}
                year_raw = str(bib.get("year") or "").strip()
                if not year_raw.isdigit():
                    continue
                year = int(year_raw)
                # Strictly pre-2022 to guarantee human authorship before modern LLMs (ChatGPT Nov 2022)
                if year < 2015 or year > 2021:
                    continue
                abst = _clean_text(str(bib.get("abstract") or ""))
                words = abst.split()
                if len(words) < 95 or len(words) > 420:
                    continue
                if "http://" in abst or "https://" in abst:
                    continue
                if lang == "id" and not _looks_indonesian(abst):
                    continue
                if lang == "en" and not _looks_english(abst):
                    continue

                journal = (bib.get("journal") or {}) if isinstance(bib.get("journal"), dict) else {}
                venue = str(journal.get("title") or "DOAJ Open Access Journal")
                issns = journal.get("issns") or []
                source_id = f"doaj:{issns[0]}" if issns else f"doaj:{venue.lower()[:60]}"
                doi = None
                for ident in bib.get("identifier") or []:
                    if isinstance(ident, dict) and str(ident.get("type", "")).lower() == "doi":
                        doi = str(ident.get("id") or "")
                        break
                lic_list = journal.get("license") or bib.get("license") or []
                lic = str(lic_list[0].get("type", "CC-BY")) if (lic_list and isinstance(lic_list[0], dict)) else "DOAJ-Open-Access"
                seen_ids.add(aid)
                collected.append(
                    {
                        "document_id": f"doaj_{aid[:16]}",
                        "source_id": source_id,
                        "venue": venue,
                        "doi": doi,
                        "year": year,
                        "title": str(bib.get("title") or "")[:240],
                        "license": lic,
                        "provenance": f"DOAJ Pre-2022 Open-Access Human Academic Article ({venue}, {year})",
                        "category": category,
                        "lang": lang,
                        "label": 0,
                        "is_mixed": False,
                        "word_count": len(words),
                        "text": abst,
                    }
                )
            time.sleep(0.35)

        # Supplement English pre-2022 OA abstracts via Europe PMC if needed
        en_count = sum(1 for r in collected if r["lang"] == "en")
        if en_count < 24:
            for category, q in [
                ("english_academic_en", "empirical survey methodology AND PUB_YEAR:2020 AND OPEN_ACCESS:Y"),
                ("formal_academic_en", "policy institutional governance AND PUB_YEAR:2020 AND OPEN_ACCESS:Y"),
            ]:
                try:
                    resp = client.get(
                        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                        params={"query": q, "format": "json", "resultType": "core", "pageSize": 18},
                    )
                    resp.raise_for_status()
                except Exception as exc:
                    print(f"WARN EuropePMC {category}: {exc}")
                    continue
                for art in (resp.json().get("resultList") or {}).get("result", []):
                    pmid = str(art.get("id") or "")
                    if not pmid or pmid in seen_ids:
                        continue
                    abst = _clean_text(str(art.get("abstractText") or ""))
                    words = abst.split()
                    if len(words) < 100 or len(words) > 400 or not _looks_english(abst):
                        continue
                    venue = str(art.get("journalTitle") or "Europe PMC OA")
                    seen_ids.add(pmid)
                    collected.append(
                        {
                            "document_id": f"epmc_{pmid}",
                            "source_id": f"epmc:{venue.lower()[:60]}",
                            "venue": venue,
                            "doi": art.get("doi"),
                            "year": int(art.get("pubYear") or 2020),
                            "title": str(art.get("title") or "")[:240],
                            "license": "Europe-PMC-Open-Access",
                            "provenance": f"Europe PMC Pre-2022 Open-Access Human Academic Article ({venue}, {art.get('pubYear')})",
                            "category": category,
                            "lang": "en",
                            "label": 0,
                            "is_mixed": False,
                            "word_count": len(words),
                            "text": abst,
                        }
                    )

    OUT.write_text(json.dumps(collected, indent=2, ensure_ascii=False), encoding="utf-8")
    by_cat: dict[str, int] = {}
    for row in collected:
        by_cat[row["category"]] = by_cat.get(row["category"], 0) + 1
    print(f"Collected {len(collected)} real pre-2022 DOAJ/EuropePMC human abstracts -> {OUT}")
    print("Counts by category:", json.dumps(by_cat, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
