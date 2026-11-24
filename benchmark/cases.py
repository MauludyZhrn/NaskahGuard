"""Generator 12 kasus uji sintetis ber-ground-truth untuk evaluasi benchmark NaskahGuard."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchmarkCase:
    case_id: int
    name: str
    description: str
    corpus_docs: list[tuple[str, str]]  # (title, text)
    submission_text: str
    settings: dict = field(default_factory=dict)
    # Token-level ground truth sets per layer (indices in submission norm_tokens)
    gt_exact: set[int] = field(default_factory=set)
    gt_near_exact: set[int] = field(default_factory=set)
    gt_lexical: set[int] = field(default_factory=set)
    expected_zero_si: bool = False
    expect_excl_lower_than_raw: bool = False


def _token_range_for_substring(full_tokens: list[str], sub_tokens: list[str]) -> set[int]:
    n = len(sub_tokens)
    for i in range(len(full_tokens) - n + 1):
        if full_tokens[i : i + n] == sub_tokens:
            return set(range(i, i + n))
    return set()


def build_benchmark_cases() -> list[BenchmarkCase]:
    from app.ingestion.tokenize import tokenize_with_offsets

    def toks(s: str) -> list[str]:
        return [t.norm for t in tokenize_with_offsets(s)]

    base_a = (
        "Sistem temu kembali informasi akademik mengandalkan pengindeksan kata kunci dan sidik jari dokumen "
        "untuk menemukan kesamaan tekstual secara cepat pada koleksi skripsi dan tesis mahasiswa."
    )
    base_b = (
        "Evaluasi kualitas perangkat lunak pemeriksa naskah harus mengukur presisi dan perolehan kembali "
        "secara terbuka menggunakan dataset uji yang memiliki anotasi kebenaran dasar yang jelas."
    )
    filler_1 = (
        "Analisis metodologi eksperimen dilaksanakan di laboratorium komputasi dengan perangkat keras standar "
        "guna menjaga reproduktifitas pengukuran performa pada berbagai ukuran dokumen masukan."
    )
    filler_2 = (
        "Pengembangan arsitektur modular memudahkan tim pengembang menambahkan adaptor sumber ilmiah terbuka "
        "tanpa mengubah komponen inti pengolah teks maupun perhitungan indeks kemiripan."
    )

    cases: list[BenchmarkCase] = []

    # Case 1: Dua dokumen identik
    c1_text = f"{base_a}\n\n{base_b}"
    c1_toks = toks(c1_text)
    cases.append(
        BenchmarkCase(
            case_id=1,
            name="Dua dokumen identik",
            description="Submission identik penuh dengan dokumen korpus.",
            corpus_docs=[("Korpus 1", c1_text)],
            submission_text=c1_text,
            gt_exact=set(range(len(c1_toks))),
        )
    )

    # Case 2: Beberapa kalimat sama
    c2_sub = f"{filler_1}\n\n{base_a}\n\n{filler_2}"
    c2_toks = toks(c2_sub)
    cases.append(
        BenchmarkCase(
            case_id=2,
            name="Beberapa kalimat sama",
            description="Satu paragraf disalin persis, dua paragraf lainnya orisinal.",
            corpus_docs=[("Korpus 2", base_a)],
            submission_text=c2_sub,
            gt_exact=_token_range_for_substring(c2_toks, toks(base_a)),
        )
    )

    # Case 3: Susunan/kata sedikit berubah (Near-Exact)
    src_3 = (
        "Algoritma pemetaan sidik jari dokumen ilmiah mampu mendeteksi penyalinan kalimat panjang "
        "meskipun penulis mengganti beberapa kata penghubung di bagian tengah paragraf tersebut."
    )
    sub_3 = (
        "Algoritma pemetaan sidik jari naskah ilmiah mampu mendeteksi penyalinan kalimat panjang "
        "meskipun mahasiswa mengganti beberapa kata sambung di bagian tengah paragraf itu."
    )
    # Tokens identical between src_3 and sub_3 at matching positions
    s3_t = toks(src_3)
    b3_t = toks(sub_3)
    gt_near_3 = {i for i in range(min(len(s3_t), len(b3_t))) if s3_t[i] == b3_t[i]}
    cases.append(
        BenchmarkCase(
            case_id=3,
            name="Modifikasi kata ringan (Near-Exact)",
            description="Substitusi beberapa kata di dalam kalimat yang sama.",
            corpus_docs=[("Korpus 3", src_3)],
            submission_text=sub_3,
            gt_near_exact=gt_near_3,
        )
    )

    # Case 4: Paragraf dengan sinonim & permutasi frasa (Lexical char_wb, tanpa 3-gram identik)
    src_4 = "Pengembangan sistem deteksi kemiripan dokumen akademik memerlukan algoritma pencocokan leksikal yang akurat serta efisien."
    sub_4 = "Algoritma pencocokan leksikal yang tepat dan efisien dibutuhkan dalam pengembangan sistem deteksi kesamaan dokumen ilmiah."
    cases.append(
        BenchmarkCase(
            case_id=4,
            name="Paragraf dengan sinonim (Lexical)",
            description="Substitusi sinonim disertai penyusunan ulang frasa untuk menguji TF-IDF char_wb.",
            corpus_docs=[("Korpus 4", src_4)],
            submission_text=sub_4,
            gt_lexical=set(range(len(toks(sub_4)))),
        )
    )

    # Case 5: Paragraf dengan kesamaan makna (Semantic/Paraphrase)
    src_5 = "Keterbukaan akses jurnal ilmiah mempercepat penyebaran pengetahuan baru bagi masyarakat luas."
    sub_5 = "Publikasi penelitian tanpa biaya langganan membantu pembaca memperoleh temuan riset secara cepat."
    cases.append(
        BenchmarkCase(
            case_id=5,
            name="Kesamaan makna / parafrase berat",
            description="Parafrase total dengan pilihan kata berbeda (kandidat semantik bila aktif).",
            corpus_docs=[("Korpus 5", src_5)],
            submission_text=sub_5,
            expected_zero_si=True,
        )
    )

    # Case 6: Kutipan langsung dengan sitasi benar (Exclusion)
    sub_6 = f'Menurut peneliti sebelumnya, "{base_a}" (Santoso, 2024: 12).\n\n{filler_1}'
    cases.append(
        BenchmarkCase(
            case_id=6,
            name="Kutipan langsung dengan sitasi",
            description="Kalimat cocok berada dalam tanda kutip dan dikecualikan saat exclude_quotes=True.",
            corpus_docs=[("Korpus 6", base_a)],
            submission_text=sub_6,
            settings={"exclude_quotes": True, "exclude_citations": True},
            expected_zero_si=True,
            expect_excl_lower_than_raw=True,
        )
    )

    # Case 7: Daftar pustaka yang sama (Bibliography exclusion)
    bib_block = (
        "Schleimer, S., Wilkerson, D. S., & Aiken, A. (2003). Winnowing: Local Algorithms for Document Fingerprinting. "
        "Proceedings of ACM SIGMOD International Conference on Management of Data."
    )
    sub_7 = f"{filler_1}\n\nDaftar Pustaka\n\n{bib_block}"
    cases.append(
        BenchmarkCase(
            case_id=7,
            name="Daftar pustaka yang sama",
            description="Kecocokan hanya muncul di zona BIBLIOGRAPHY yang dikecualikan.",
            corpus_docs=[("Korpus 7", f"Daftar Pustaka\n\n{bib_block}")],
            submission_text=sub_7,
            settings={"exclude_bibliography": True},
            expected_zero_si=True,
            expect_excl_lower_than_raw=True,
        )
    )

    # Case 8: Frasa umum di banyak dokumen
    common_txt = (
        "Penelitian ini bertujuan untuk mengetahui pengaruh metode pembelajaran terhadap hasil belajar mahasiswa. "
        "Berdasarkan hasil penelitian tersebut dapat disimpulkan bahwa metode ini efektif."
    )
    cases.append(
        BenchmarkCase(
            case_id=8,
            name="Frasa umum akademik",
            description="Frasa akademik standar yang muncul di banyak dokumen korpus.",
            corpus_docs=[
                ("Korpus 8a", common_txt + " Tambahan konteks pertama yang berbeda."),
                ("Korpus 8b", common_txt + " Tambahan konteks kedua yang berlainan."),
                ("Korpus 8c", common_txt + " Tambahan konteks ketiga yang unik."),
                ("Korpus 8d", common_txt + " Tambahan konteks keempat yang lain."),
            ],
            submission_text=f"{filler_2}\n\nPenelitian ini bertujuan untuk mengetahui...",
            settings={"exclude_common_phrases": True},
            expected_zero_si=True,
        )
    )

    # Case 9: Dua sumber overlap
    sub_9 = f"{base_a}\n\n{filler_1}"
    c9_toks = toks(sub_9)
    cases.append(
        BenchmarkCase(
            case_id=9,
            name="Dua sumber overlap",
            description="Dua sumber mengandung kalimat identik yang sama; tidak boleh dihitung ganda.",
            corpus_docs=[
                ("Korpus 9A", f"{base_a}\n\nKalimat pembeda sumber A."),
                ("Korpus 9B", f"{base_a}\n\nKalimat pembeda sumber B."),
            ],
            submission_text=sub_9,
            gt_exact=_token_range_for_substring(c9_toks, toks(base_a)),
        )
    )

    # Case 10: Simulasi hasil OCR buruk (noise karakter pada sebagian kata)
    src_10 = (
        "Pengujian keandalan sistem deteksi kemiripan dokumen dilakukan dengan menyuntikkan gangguan karakter "
        "seperti hasil pemindaian optis beresolusi rendah pada berkas arsip lama."
    )
    sub_10 = (
        "Pengujian keandalan sistem deteksi kemiripan dokumen dilakukan dengan menyunt1kkan gangguan karakt3r "
        "seperti hasil pemindaian optis beresolusi rendah pada berkas arsip lama."
    )
    s10_t = toks(src_10)
    b10_t = toks(sub_10)
    # Tokens 0..7 (8 kata) dan 11..20 (10 kata) bersih (>= min_match_words=8 -> Exact),
    # sedangkan token 9 ("gangguan") di antara dua kata rusak merupakan token terverifikasi Near-Exact.
    gt_exact_10 = set(range(0, 8)) | set(range(11, 21))
    gt_near_10 = {i for i in range(min(len(s10_t), len(b10_t))) if s10_t[i] == b10_t[i]} - gt_exact_10
    cases.append(
        BenchmarkCase(
            case_id=10,
            name="Simulasi hasil OCR buruk",
            description="Noise karakter OCR ('1' dan '3') di tengah paragraf salinan.",
            corpus_docs=[("Korpus 10", src_10)],
            submission_text=sub_10,
            gt_exact=gt_exact_10,
            gt_near_exact=gt_near_10,
        )
    )

    # Case 11: Dokumen tanpa sumber pembanding
    cases.append(
        BenchmarkCase(
            case_id=11,
            name="Tanpa sumber pembanding",
            description="Korpus kosong; cakupan sangat terbatas dan SI 0%.",
            corpus_docs=[],
            submission_text=filler_1,
            expected_zero_si=True,
        )
    )

    # Case 12: Dokumen multibahasa ID + EN
    en_copy = (
        "Open source plagiarism detection requires transparent candidate retrieval and reproducible passage alignment "
        "across multilingual academic repositories."
    )
    sub_12 = f"{filler_1}\n\n{en_copy}"
    c12_toks = toks(sub_12)
    cases.append(
        BenchmarkCase(
            case_id=12,
            name="Dokumen multibahasa (ID + EN)",
            description="Naskah campuran Indonesia dan Inggris dengan bagian Inggris disalin.",
            corpus_docs=[("Korpus 12 EN", en_copy)],
            submission_text=sub_12,
            gt_exact=_token_range_for_substring(c12_toks, toks(en_copy)),
        )
    )

    return cases
