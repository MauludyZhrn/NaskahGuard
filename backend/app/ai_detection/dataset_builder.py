"""Multilingual Indonesian & English AI Writing Dataset Builder.

Builds strictly separated train / validation / test / false_positive_stress splits
across all 8 required writing categories with BOTH disjoint topic pools AND
disjoint rhetorical templates between (train, val) and unseen (test, fp_stress),
preventing n-gram/template memorization and producing honest generalization metrics.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

CATEGORIES = (
    "human_original_id",
    "human_original_en",
    "ai_pure_multi_style",
    "human_ai_assisted",
    "ai_human_edited",
    "ai_paraphrased",
    "academic_formal_human",
    "academic_nonformal_human",
)

TRAIN_TOPICS = [
    ("irigasi subak Bali", "ketimpangan distribusi air hulu dan hilir", "pengukuran debit 14 saluran tersier selama musim kemarau", "(Sutawan, 2021: 42)", "cooperative irrigation governance", "upstream-downstream allocation imbalance", "flow logs from fourteen tertiary canals during dry weeks"),
    ("retribusi sampah perkotaan", "rendahnya kepatuhan pembayaran warga rumah tangga", "audit 120 karcis pungutan manual di tiga kelurahan", "(Permendagri No. 7/2021)", "municipal waste fee collection", "irregular household payment compliance", "an audit of 120 paper receipts across three wards"),
    ("bakteri asam laktat tempe", "fluktuasi keasaman selama fermentasi hari kedua", "penurunan pH dari 6,1 menjadi 4,4 pada suhu ruang 29 derajat", "(Rahayu dkk., 2022)", "tempeh fermentation starter cultures", "rapid acidity shifts on day two", "pH dropping from 6.1 to 4.4 at twenty-nine degrees Celsius"),
    ("kredit mikro nelayan pesisir", "ketergantungan pada tengkulak saat musim angin barat", "catatan kas harian 28 perahu jukung selama delapan minggu", "(BPS Kelautan, 2023)", "small-scale fisheries microcredit", "debt tie-ins with middlemen during monsoon months", "eight weeks of boat cashbooks across twenty-eight crews"),
    ("literasi numerasi siswa SD", "kesalahan membaca soal cerita pecahan bertingkat", "lembar jawaban 64 siswa kelas lima di dua kecamatan", "(Kemendikbud, 2022)", "primary school numeracy diagnostic tasks", "misreading multi-step fraction word problems", "marked worksheets from sixty-four fifth graders"),
    ("arsitektur ventilasi silang tropis", "penumpukan panas sore hari di ruang tidur barat", "rekaman sensor suhu dinding tiap 15 menit selama sepekan", "(SNI 03-6572-2001)", "passive cross-ventilation housing", "late-afternoon heat retention along west walls", "fifteen-minute wall sensor logs across seven sunny days"),
    ("rantai dingin vaksin puskesmas", "jeda pencatatan suhu saat pemadaman listrik siang", "inspeksi empat kulkas vaksin dengan termologger USB", "(Kemenkes RI, 2021)", "rural clinic vaccine cold chains", "temperature logging gaps during midday blackouts", "USB logger traces inside four clinic refrigerators"),
    ("kearifan leuit masyarakat Baduy", "ketahanan stok gabah saat gagal panen kemarau panjang", "inventarisasi 19 lumbung keluarga dan jadwal buka pintu adat", "(Iskandar, 2020: 118)", "communal rice granary buffers", "grain reserve resilience after prolonged dry spells", "stock counts across nineteen family-owned granaries"),
    ("optimasi rute ambulans kota", "penyumbatan persimpangan sebidang kereta pada jam sibuk", "log GPS 47 perjalanan darurat di koridor selatan", "(Dishub Kota, 2023)", "urban ambulance dispatch routing", "grade-crossing delays during peak commute windows", "GPS traces from forty-seven emergency runs"),
    ("pengarsipan manuskrip lontar", "kerapuhan daun tal akibat kelembapan lemari kayu", "pemetaan 83 lempir berjamur menggunakan kamera makro", "(Perpusnas, 2021)", "palm-leaf manuscript preservation", "fungal embrittlement inside unsealed wooden cabinets", "macro imaging across eighty-three fragile folios"),
]

VAL_TOPICS = [
    ("rehabilitasi mangrove tambak terlantar", "tingkat kematian bibit tinggi akibat ombak pasang purnama", "pemantauan 300 ajir bambu dan tinggi salinitas tiap pagi", "(KKP, 2023)", "abandoned pond mangrove restoration", "seedling uprooting during spring high tides", "daily salinity checks along three hundred bamboo stakes"),
    ("penjualan langsung petani kopi arabika", "selisih mutu sangrai akibat pengeringan terpal terbuka", "pengukuran kadar air 22 karung ceri merah sebelum hulling", "(Puslitkoka, 2022)", "smallholder arabica direct trade", "uneven moisture loss on open-air patio tarps", "bean moisture tests across twenty-two parchment lots"),
    ("ergonomi meja kerja penjahit konveksi", "nyeri punggung bawah setelah enam jam menjahit obras", "penilaian sudut leher RULA pada 26 operator mesin", "(Permenaker No. 5/2018)", "garment workshop sewing ergonomics", "lower-back strain after six-hour overlock shifts", "RULA posture scoring across twenty-six machine operators"),
    ("aksesibilitas halte bus kota bagi lansia", "celah ketinggian trotoar yang menyulitkan kursi roda", "pengukuran kemiringan ramp di 15 titik transit utama", "(PUPR, 2021)", "bus stop ramp accessibility", "steep curb transitions blocking manual wheelchairs", "inclinometer measurements across fifteen transit shelters"),
]

TEST_TOPICS = [
    ("kepatuhan pelaporan pajak UMKM kuliner", "kebingungan membedakan omzet kotor dan modal belanja harian", "wawancara mendalam 18 pemilik warung tanpa pembukuan digital", "(PP No. 55/2022)", "small food stall tax compliance", "confusing gross daily turnover with ingredient restocking costs", "field notes from eighteen owners lacking digital ledgers"),
    ("stabilitas lereng terasering dataran tinggi", "rekahan tanah setelah hujan dua hari tanpa saluran pembuang", "uji geser langsung pada sembilan sampel tanah andosol", "(PVMBG, 2023)", "highland terrace slope stability", "tension cracks after two-day storms without stone drains", "direct shear tests on nine undisturbed volcanic soil cores"),
    ("penerimaan bahasa daerah di aplikasi layanan publik", "istilah birokrasi kaku yang asing bagi pengguna pedesaan", "uji pakai bersama 24 warga desa berusia di atas 55 tahun", "(UU No. 25/2009)", "regional language civic app adoption", "literal bureaucratic phrasing unfamiliar to rural elders", "usability walkthroughs with twenty-four residents over fifty-five"),
    ("manajemen stok reagen laboratorium RSUD", "kedaluwarsa kit imunologi akibat pembelian paket tahunan seragam", "kartu kendali gudang untuk 45 item pemeriksaan darah", "(Kemenkes PMK 43/2013)", "regional hospital reagent inventory", "expired immunoassay kits under rigid annual bulk orders", "stockroom bin cards covering forty-five blood test panels"),
    ("dampak kebisingan lalu lintas dekat ruang kelas", "suara klakson truk memutus penjelasan guru setiap lima menit", "pengukuran desibel puncak dBA di tiga ruang kelas menghadap jalan", "(KepmenLH No. 48/1996)", "roadside classroom acoustic distraction", "heavy truck horns interrupting instruction every few minutes", "peak decibel logs inside three street-facing classrooms"),
    ("efektivitas bank sampah tingkat RW", "penumpukan plastik multilapis yang ditolak pengepul keliling", "penimbangan mingguan 34 rumah tangga nasabah aktif", "(KLHK, 2022)", "neighborhood waste bank participation", "multi-layer snack wrappers rejected by scrap buyers", "weekly sorting weights from thirty-four member households"),
]


def _human_id_train(rng: random.Random, topic: tuple[str, ...], formal: bool, nonformal: bool) -> str:
    t_id, ph_id, det_id, cite, *_ = topic
    if formal:
        return (
            f"Penelitian tentang {t_id} mengacu pada ketentuan {cite} dengan rancangan deskriptif-analitis. "
            f"Fokus telaah diarahkan pada {ph_id} yang berulang dalam tiga triwulan pengamatan lapangan. "
            f"Variabel operasional dicatat berurutan tanpa mengubah alur kerja unit pelaksana.\n\n"
            f"Verifikasi data dilakukan melalui {det_id} serta pemeriksaan silang dokumen register asli. "
            f"Entri yang tidak bertanggal atau rusak fisiknya dikeluarkan dari tabulasi inti dan dicatat pada lampiran pengecualian."
        )
    if nonformal:
        return (
            f"Saat awal kami mengamati {t_id}, persoalan ternyata tidak sesederhana angka di laporan tahunan {cite}. "
            f"Di lokasi pengamatan, {ph_id} muncul hampir tiap minggu—dan petugas sering menambalnya pakai catatan kertas tempel.\n\n"
            f"Begitu tim merampungkan {det_id}, barulah terlihat akar masalahnya. Kebiasaan kerja lama berbenturan dengan formulir baru yang dianggap terlalu berbelit, sehingga mereka memilih cara cepat meski rawan selisih."
        )
    return (
        f"Pembahasan akademik mengenai {t_id} umumnya menyoroti aspek aturan tertulis {cite}, padahal kebiasaan harian di balik meja sering menentukan hasil akhir. "
        f"Persoalan {ph_id} tidak hadir mendadak. Ia menumpuk perlahan akibat keterbatasan tenaga pencatat.\n\n"
        f"Melalui {det_id}, tim menemukan perbedaan nyata antara rekap bulanan dan kondisi riil. Beberapa berkas tidak cocok. "
        f"Temuan ini menegaskan bahwa kendala koordinasi lapangan lebih menentukan daripada kekurangan perangkat lunak semata."
    )


def _human_en_train(rng: random.Random, topic: tuple[str, ...], formal: bool, nonformal: bool) -> str:
    *_, t_en, ph_en, det_en = topic
    if formal:
        return (
            f"This study examined {t_en} under institutional ethics approval, focusing specifically on {ph_en} across two consecutive quarters. "
            f"Administrative forms were audited against original site registers prior to statistical summary. "
            f"Incomplete sheets missing supervisor initials were excluded cleanly from primary tabulations.\n\n"
            f"Empirical verification relied on {det_en} gathered at predetermined weekly checkpoints. "
            f"Because site distributions skewed sharply, rank-order comparisons replaced pooled arithmetic means throughout the analytical chapter."
        )
    if nonformal:
        return (
            f"Before visiting the field sites for {t_en}, we assumed {ph_en} only happened during staff holidays. "
            f"We were wrong. Within three days, local clerks showed us the handwritten notebooks they trusted far more than the central portal.\n\n"
            f"Going through {det_en} confirmed how messy real workflows actually are. People rarely ignore policy out of laziness; usually the official form takes twice as long when customers are waiting in line."
        )
    return (
        f"Prior literature on {t_en} routinely treats {ph_en} as minor administrative noise rather than a structural signal. "
        f"During direct observation, frontline operators improvised workarounds whenever shift schedules tightened. Paper clips replaced digital flags.\n\n"
        f"Evidence compiled from {det_en} exposed sharp swings across shifts. Whenever senior supervisors rotated out, error counts doubled within forty-eight hours."
    )


def _ai_train(topic: tuple[str, ...], lang: str, edited: bool, paraphrased: bool) -> str:
    t_id, ph_id, det_id, _, t_en, ph_en, det_en = topic
    if lang == "id":
        if paraphrased:
            return (
                f"Kajian terkait {t_id} menggarisbawahi pentingnya keseimbangan antara tata laksana operasional dan kesiapan sumber daya manusia. "
                f"Berbagai persoalan seperti {ph_id} berdampak langsung terhadap stabilitas mutu layanan secara menyeluruh.\n\n"
                f"Dengan mengandalkan {det_id}, unit pelaksana mampu memetakan prioritas pembenahan yang terstruktur dan terukur bagi keberlanjutan organisasi."
            )
        if edited:
            return (
                f"Pengelolaan {t_id} masih berhadapan dengan kendala {ph_id} yang memengaruhi konsistensi capaian program. "
                f"Sinkronisasi standar prosedur serta pembaruan sistem pelaporan menjadi langkah penting untuk menekan kesenjangan operasional.\n\n"
                f"Berdasarkan {det_id}, optimalisasi koordinasi lintas unit dan evaluasi berkala berperan besar memperkuat akuntabilitas layanan publik."
            )
        return (
            f"Di era modern saat ini, pengelolaan {t_id} memainkan peran krusial dalam meningkatkan kualitas layanan berkelanjutan. "
            f"Penanganan {ph_id} menuntut pendekatan holistik dan sinergi antara berbagai pemangku kepentingan di seluruh tingkatan.\n\n"
            f"Selain itu, hasil dari {det_id} memberikan wawasan berharga bagi perumusan kebijakan adaptif. "
            f"Secara keseluruhan, strategi terpadu akan memperkuat daya saing institusi secara konsisten."
        )
    if paraphrased:
        return (
            f"Analyzing {t_en} demonstrates how operational alignment shapes organizational consistency across service contexts. "
            f"Recurring barriers related to {ph_en} weaken routine coordination and require calibrated administrative responses.\n\n"
            f"Insights drawn from {det_en} clarify practical interventions for enhancing resource distribution and sustainable accountability."
        )
    if edited:
        return (
            f"Managing {t_en} entails addressing persistent friction such as {ph_en} that undermines everyday reliability. "
            f"Standardized documentation paired with timely supervision strengthens operational clarity across participating branches.\n\n"
            f"Observations from {det_en} underscore how periodic review cycles support steady performance improvement."
        )
    return (
        f"In today's rapidly evolving landscape, {t_en} plays a pivotal role in fostering institutional resilience and service excellence. "
        f"Furthermore, resolving challenges such as {ph_en} requires a holistic approach grounded in cross-functional collaboration.\n\n"
        f"Moreover, data derived from {det_en} offers significant implications for evidence-based governance. "
        f"In conclusion, comprehensive evaluation unlocks lasting improvements across all organizational dimensions."
    )


def _unseen_test_sample(topic: tuple[str, ...], category: str, lang: str, variant: int) -> tuple[str, int, bool]:
    """Held-out TEST split using UNSEEN linguistic styles & structures (never seen during train/val)."""
    t_id, ph_id, det_id, cite, t_en, ph_en, det_en = topic

    if category == "human_original_id":
        txt = (
            f"Sejak bulan kedua pengamatan terhadap {t_id}, kami mulai meragukan angka rata-rata resmi yang beredar di rapat koordinasi {cite}. "
            f"Kenapa laporan pusat selalu rapi sedangkan antrean warga di luar ruangan mengular hingga sore? "
            f"Jawabannya baru terbuka setelah kami menyisir {det_id} satu per satu. Masalah pokoknya ternyata {ph_id}; berkas dicatat belakangan setelah petugas selesai melayani.\n\n"
            f"Kondisi semacam itu tidak bisa diselesaikan hanya lewat surat edaran baru. Beberapa pelaksana bahkan terang-terangan mengaku lebih nyaman memakai buku folio bergaris karena jaringan sering terputus ketika hujan deras. "
            f"Ketidakseragaman prosedur itulah yang menjelaskan lonjakan selisih pada akhir pekan."
        )
        return txt, 0, False

    if category == "academic_formal_human":
        if lang == "id":
            txt = (
                f"Merujuk ketentuan {cite}, evaluasi pelaksanaan {t_id} dilakukan melalui penelusuran dokumen primer dan verifikasi silang antarbagian selama enam bulan berjalan. "
                f"Indikator ketercapaian dibatasi pada kepatuhan alur pencatatan, ketepatan tanggal pengesahan, serta kesesuaian bukti transaksi terhadap {ph_id}.\n\n"
                f"Pengumpulan data empiris bertumpu pada {det_id} dengan kriteria inklusi ketat guna mencegah bias seleksi dari berkas susulan. "
                f"Seluruh penyimpangan yang ditemukan dihitung per unit pengamatan dan dilaporkan terpisah dari catatan administratif rutin sebelum uji kesesuaian dokumen ditutup."
            )
            return txt, 0, False
        txt = (
            f"Pursuant to statutory audit rules governing {t_en}, field records covering two reporting years were inspected chronologically without altering departmental classifications. "
            f"Analytical focus remained centered on {ph_en}, quantified against physical ledger stamps and time-logged supervisor countersignatures.\n\n"
            f"Primary data arose from {det_en} gathered using uniform calibration protocols across three decentralized posts. "
            f"Records lacking independent timestamp verification were quarantined rather than imputed so downstream sensitivity checks remained transparent and auditable."
        )
        return txt, 0, False

    if category == "academic_nonformal_human":
        if lang == "id":
            txt = (
                f"Jujur saja, rencana awal penelitian kami soal {t_id} sempat mentok gara-gara jadwal informan berubah terus menjelang tutup buku {cite}. "
                f"Hampir setengah responden segan membuka catatan asli karena takut dianggap menyalahi aturan pusat, padahal akar kesulitannya ya {ph_id} itu sendiri.\n\n"
                f"Baru setelah kami mengobrol santai sambil mengecek {det_id}, suasana mencair dan mereka mau menunjuk bagian mana yang paling menyita waktu. "
                f"Dari situ terlihat jelas betapa jauhnya jarak antara petunjuk teknis di kertas dan kenyataan di meja kerja harian."
            )
            return txt, 0, False
        txt = (
            f"Honestly, our early interviews on {t_en} nearly stalled because staff treated us like surprise inspectors until we put away the formal checklists. "
            f"Once conversations opened up, nearly everyone pointed straight at {ph_en} as the real daily headache nobody dared put in writing.\n\n"
            f"Checking {det_en} alongside the workers themselves cleared up two puzzling anomalies right away. Short staffing on Tuesdays forced crews to batch records at night, which explained why morning logs always looked suspiciously empty."
        )
        return txt, 0, False

    if category == "human_original_en":
        txt = (
            f"Studies of {t_en} seldom dwell on how quickly informal habits fill the gap when official templates lag behind reality. "
            f"On site, {ph_en} cropped up almost daily, forcing junior clerks to choose between following every signature box or clearing waiting lines before noon. "
            f"Not surprisingly, speed won most arguments.\n\n"
            f"Inspecting {det_en} revealed wide swings between morning and late-afternoon accuracy rather than steady failure across the board. "
            f"Once afternoon fatigue hit and phones kept ringing, handwritten tallies drifted apart from digital entries."
        )
        return txt, 0, False

    if category == "ai_pure_multi_style":
        if lang == "id":
            # Subtle, fluent LLM Indonesian WITHOUT cliché "Di era digital" opening on variant % 2 == 1
            if variant % 2 == 0:
                txt = (
                    f"Dinamika pengelolaan {t_id} mencerminkan keterhubungan yang erat antara kesiapan kelembagaan, ketepatan regulasi, dan mutu pelaksanaan program. "
                    f"Tantangan berupa {ph_id} berpotensi menghambat efektivitas layanan apabila tidak ditangani melalui langkah strategis yang terukur. "
                    f"Oleh karena itu, penyelarasan kebijakan serta peningkatan kapabilitas sumber daya manusia menjadi aspek penting yang perlu diperhatikan.\n\n"
                    f"Pemanfaatan temuan dari {det_id} dapat memperkuat pengambilan keputusan berbasis data serta mendorong perbaikan berkelanjutan. "
                    f"Dengan kolaborasi lintas sektor yang konsisten dan evaluasi berkala yang terstruktur, berbagai kendala operasional dapat diminimalkan demi tercapainya hasil yang optimal bagi seluruh pemangku kepentingan."
                )
            else:
                txt = (
                    f"Optimalisasi tata kelola {t_id} memerlukan pemahaman mendalam mengenai mekanisme internal serta faktor eksternal yang memengaruhi kinerja sistem. "
                    f"Dalam konteks tersebut, persoalan seperti {ph_id} menegaskan perlunya standardisasi alur kerja dan pengawasan yang berkelanjutan. "
                    f"Kejelasan pembagian tugas antarunit juga berperan menentukan keberhasilan implementasi di berbagai tingkatan organisasi.\n\n"
                    f"Melalui telaah sistematis terhadap {det_id}, pihak pengelola mampu menyusun indikator evaluasi yang relevan dan responsif. "
                    f"Pendekatan terstruktur tersebut berkontribusi positif dalam menciptakan tata laksana yang lebih transparan, adaptif, serta berorientasi pada peningkatan kualitas layanan publik."
                )
            return txt, 1, False
        txt = (
            f"Enhancing operational performance within {t_en} depends heavily on aligning institutional procedures with clear monitoring benchmarks. "
            f"Persistent challenges involving {ph_en} highlight the importance of structured workflows that balance flexibility with dependable oversight. "
            f"Addressing these gaps thoughtfully ensures that frontline teams maintain consistent execution across diverse settings.\n\n"
            f"Integrating insights obtained from {det_en} enables decision-makers to identify practical priorities and refine resource planning over time. "
            f"Ultimately, coherent coordination coupled with regular assessment strengthens organizational adaptability and supports sustained improvements in overall service delivery."
        )
        return txt, 1, False

    if category == "ai_human_edited":
        txt = (
            f"Evaluasi awal mengenai {t_id} menunjukkan adanya tantangan {ph_id} yang kerap mengganggu kelancaran pelaporan di lapangan {cite}. "
            f"Penyelarasan alur komunikasi antarunit kerja serta penyederhanaan pedoman teknis dinilai penting untuk menjaga keseragaman standar pelaksanaan. "
            f"Dalam situasi operasional yang dinamis, mekanisme kontrol kualitas yang konsisten membantu meminimalkan potensi penyimpangan administrasi.\n\n"
            f"Data yang diperoleh melalui {det_id} memberi gambaran jelas mengenai kebutuhan penguatan kapasitas pelaksana dan perbaikan tata kelola pencatatan secara berkelanjutan."
        )
        return txt, 1, False

    if category == "ai_paraphrased":
        if lang == "id":
            txt = (
                f"Pembahasan tentang {t_id} memperlihatkan hubungan timbal balik antara kesiapan perangkat kebijakan dan konsistensi praktik harian di berbagai wilayah layanan publik. "
                f"Hambatan semacam {ph_id} dapat melemahkan stabilitas proses kerja sehingga membutuhkan penataan ulang mekanisme pengawasan serta pembinaan SDM secara menyeluruh. "
                f"Keselarasan prosedur di tingkat operasional berfungsi sebagai pijakan utama guna menjaga keandalan capaian program dalam jangka panjang.\n\n"
                f"Informasi empiris yang terkumpul lewat {det_id} mendukung penyusunan strategi pembenahan yang lebih terarah, adaptif, dan berkelanjutan bagi seluruh pemangku kepentingan terkait."
            )
        else:
            txt = (
                f"Reviewing {t_en} reveals how institutional design interacts closely with routine execution challenges across local operational facilities. "
                f"Ongoing friction around {ph_en} diminishes administrative reliability and calls for calibrated adjustments in workflow supervision across every participating branch. "
                f"Establishing clearer operational guidelines helps staff sustain uniform quality benchmarks throughout fluctuating workloads.\n\n"
                f"Empirical evidence drawn from {det_en} informs targeted refinements that strengthen long-term program durability, organizational readiness, and stakeholder accountability over time."
            )
        return txt, 1, False

    # category == "human_ai_assisted" -> Genuine mixed paragraph (Paragraph 1 human field voice, Paragraph 2 LLM formal synthesis)
    if lang == "id":
        p1 = (
            f"Waktu kami menengok langsung pelaksanaan {t_id}, persoalan {ph_id} sebenarnya sudah dikeluhkan petugas sejak awal tahun {cite}. "
            f"Mereka tidak kurang aturan; yang kurang justru waktu senggang untuk mengisi tiga aplikasi berbeda sebelum loket tutup pukul tiga sore."
        )
        p2 = (
            f"Di sisi lain, hasil analisis terhadap {det_id} memberikan wawasan berharga guna memperkuat perencanaan strategis serta integrasi sistem secara holistik. "
            f"Secara keseluruhan, sinergi antara peningkatan kapasitas pelaksana dan evaluasi berkala akan mendorong keberhasilan implementasi program secara berkelanjutan."
        )
        return f"{p1}\n\n{p2}", 1, True
    p1 = (
        f"During our first week checking {t_en}, {ph_en} showed up in almost every handwritten logbook we pulled off the shelf. "
        f"Clerks complained loudly that updating duplicate tabs froze their old terminals right when lines grew longest."
    )
    p2 = (
        f"Furthermore, insights derived from {det_en} offer significant implications for designing adaptable and sustainable workflow strategies across institutions. "
        f"In conclusion, integrating evidence-based planning with structured governance unlocks lasting improvements in service reliability."
    )
    return f"{p1}\n\n{p2}", 1, True


def _build_train_or_val(topics: list[tuple[str, ...]], split_name: str, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    idx = 0
    for t_idx, topic in enumerate(topics):
        specs = [
            ("human_original_id", "id", 0, _human_id_train(rng, topic, formal=False, nonformal=False), False),
            ("academic_formal_human", "id", 0, _human_id_train(rng, topic, formal=True, nonformal=False), False),
            ("academic_nonformal_human", "id", 0, _human_id_train(rng, topic, formal=False, nonformal=True), False),
            ("human_original_en", "en", 0, _human_en_train(rng, topic, formal=False, nonformal=False), False),
            ("academic_formal_human", "en", 0, _human_en_train(rng, topic, formal=True, nonformal=False), False),
            ("academic_nonformal_human", "en", 0, _human_en_train(rng, topic, formal=False, nonformal=True), False),
            ("ai_pure_multi_style", "id", 1, _ai_train(topic, lang="id", edited=False, paraphrased=False), False),
            ("ai_pure_multi_style", "en", 1, _ai_train(topic, lang="en", edited=False, paraphrased=False), False),
            ("ai_human_edited", "id", 1, _ai_train(topic, lang="id", edited=True, paraphrased=False), False),
            ("ai_paraphrased", "id", 1, _ai_train(topic, lang="id", edited=False, paraphrased=True), False),
            ("ai_paraphrased", "en", 1, _ai_train(topic, lang="en", edited=False, paraphrased=True), False),
            (
                "human_ai_assisted",
                "id" if t_idx % 2 == 0 else "en",
                1,
                _human_id_train(rng, topic, formal=False, nonformal=False).split("\n\n")[0]
                + "\n\n"
                + _ai_train(topic, lang="id", edited=False, paraphrased=False).split("\n\n")[1]
                if t_idx % 2 == 0
                else _human_en_train(rng, topic, formal=False, nonformal=False).split("\n\n")[0]
                + "\n\n"
                + _ai_train(topic, lang="en", edited=False, paraphrased=False).split("\n\n")[1],
                True,
            ),
        ]
        for category, lang, label, text, is_mixed in specs:
            rows.append({
                "id": f"{split_name}_{idx:04d}",
                "split": split_name,
                "category": category,
                "lang": lang,
                "label": label,
                "is_mixed": is_mixed,
                "text": text,
            })
            idx += 1
    return rows


def _build_test(topics: list[tuple[str, ...]], seed: int = 303) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    idx = 0
    for t_idx, topic in enumerate(topics):
        test_specs = [
            ("human_original_id", "id"),
            ("academic_formal_human", "id"),
            ("academic_nonformal_human", "id"),
            ("human_original_en", "en"),
            ("academic_formal_human", "en"),
            ("academic_nonformal_human", "en"),
            ("ai_pure_multi_style", "id"),
            ("ai_pure_multi_style", "en"),
            ("ai_human_edited", "id"),
            ("ai_paraphrased", "id"),
            ("ai_paraphrased", "en"),
            ("human_ai_assisted", "id" if t_idx % 2 == 0 else "en"),
        ]
        for category, lang in test_specs:
            txt, label, is_mixed = _unseen_test_sample(topic, category, lang, variant=t_idx)
            rows.append({
                "id": f"test_{idx:04d}",
                "split": "test",
                "category": category,
                "lang": lang,
                "label": label,
                "is_mixed": is_mixed,
                "text": txt,
            })
            idx += 1
    return rows


def build_false_positive_stress_samples() -> list[dict[str, object]]:
    """Human texts that notoriously trigger false positives in naive AI detectors."""
    return [
        {
            "id": "fp_01_id_formal_law",
            "category": "academic_formal_human",
            "lang": "id",
            "label": 0,
            "risk_profile": "Penulisan hukum & regulasi formal dengan konjungsi baku",
            "text": (
                "Berdasarkan ketentuan Pasal 27 ayat (2) Peraturan Pemerintah tentang Tata Kelola Arsip Daerah, setiap satuan kerja diwajibkan menyimpan berita acara serah terima berkas paling singkat lima tahun terhitung sejak penandatanganan dokumen. "
                "Apabila terjadi alih media dari warkat kertas ke salinan elektronik, keabsahan dokumen tetap melekat sepanjang dilakukan verifikasi tanda tangan pejabat berwenang dan pencatatan nomor registrasi tahunan.\n\n"
                "Dalam praktik pemeriksaan administratif pada sebelas dinas teknis tahun anggaran 2023, keterlambatan penomoran kerap disebabkan oleh pergantian bendahara barang di pertengahan triwulan tanpa pelimpahan daftar inventaris tertulis. "
                "Akibatnya, bagian pengawasan internal harus mencocokkan kuitansi asli satu per satu sebelum menyusun laporan pertanggungjawaban akhir tahun."
            ),
        },
        {
            "id": "fp_02_id_dense_abstract",
            "category": "academic_formal_human",
            "lang": "id",
            "label": 0,
            "risk_profile": "Abstrak IMRAD padat Bahasa Indonesia dengan istilah metodologi standar",
            "text": (
                "Latar Belakang: Resistensi antimikroba pada isolat urin pasien rawat jalan terus meningkat dan menyulitkan pemilihan terapi empiris awal di fasilitas tingkat pertama. "
                "Metode: Penelitian potong lintang dilakukan terhadap 142 sampel kultur positif selama periode Januari hingga Agustus 2023 di dua rumah sakit rujukan tipe C. Uji kepekaan cakram mengacu pada standar CLSI edisi ke-32.\n\n"
                "Hasil: Escherichia coli mendominasi sebesar 61,3 persen isolat dengan tingkat kepekaan terhadap ampisilin di bawah 24 persen, sedangkan fosfomisin tetap sensitif pada 91,5 persen spesimen. "
                "Simpulan: Pedoman resep empiris lokal perlu disesuaikan dengan peta kuman enam bulanan guna menekan kegagalan terapi lini pertama."
            ),
        },
        {
            "id": "fp_03_en_formal_methods",
            "category": "academic_formal_human",
            "lang": "en",
            "label": 0,
            "risk_profile": "Formal English methodology section with clean copy-editing",
            "text": (
                "Semi-structured interviews were conducted with thirty-four municipal water engineers between March and October 2022 after obtaining written institutional ethics clearance (Ref. 2022/ENG-14). "
                "Interviews averaged forty-six minutes and followed an explicit topic guide covering valve maintenance logs, seasonal turbidity spikes, and emergency chlorine dosing records.\n\n"
                "All audio files were transcribed verbatim, checked against handwritten field sketches, and coded independently by two analysts before resolving disagreements through line-by-line review. "
                "Inter-coder agreement reached Cohen's kappa of 0.84 across primary operational themes, while three outlier repair cases were retained as negative-case examples."
            ),
        },
        {
            "id": "fp_04_id_grammar_polished",
            "category": "human_original_id",
            "lang": "id",
            "label": 0,
            "risk_profile": "Tulisan asli manusia berbahasa Indonesia rapi hasil suntingan ejaan",
            "text": (
                "Kenaikan harga pakan pabrikan sepanjang musim kemarau memaksa peternak itik di Kecamatan Candi mencari alternatif bahan lokal tanpa menurunkan bobot telur harian. "
                "Melalui uji coba kandang selama enam minggu bersama tiga kelompok tani, pencampuran bungkil kelapa dan keong sawah rebus sebanyak 18 persen terbukti menahan biaya ransum agar tidak melonjak.\n\n"
                "Kendala yang justru paling banyak dikeluhkan warga bukanlah komposisi gizi pakan, melainkan bau menyengat saat proses pengeringan di pekarangan sempit. "
                "Oleh sebab itu, dua kelompok mulai mengalihkan perebusan ke tepi saluran irigasi desa setiap Selasa dan Jumat pagi sebelum matahari terlalu terik."
            ),
        },
        {
            "id": "fp_05_short_text_guard",
            "category": "short_insufficient",
            "lang": "id",
            "label": 0,
            "expect_insufficient": True,
            "risk_profile": "Teks terlalu pendek (< 80 kata) wajib mendapat status TIDAK CUKUP BUKTI",
            "text": (
                "Penelitian ini membahas efektivitas pembelajaran daring pada mahasiswa semester awal dengan membandingkan hasil kuis mingguan sebelum dan sesudah pendampingan mentor."
            ),
        },
    ]


def build_all_splits() -> dict[str, list[dict[str, object]]]:
    """Generate deterministic, leakage-free train/val/test/fp datasets."""
    return {
        "train": _build_train_or_val(TRAIN_TOPICS, "train", seed=101),
        "validation": _build_train_or_val(VAL_TOPICS, "validation", seed=202),
        "test": _build_test(TEST_TOPICS, seed=303),
        "false_positive_stress": build_false_positive_stress_samples(),
    }


def save_dataset_splits(output_dir: Path) -> dict[str, object]:
    """Persist splits as JSONL files plus a summary manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    splits = build_all_splits()
    manifest: dict[str, object] = {"splits": {}, "categories": list(CATEGORIES)}
    for name, rows in splits.items():
        path = output_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        manifest["splits"][name] = {
            "count": len(rows),
            "path": str(path),
            "languages": sorted({str(r.get("lang", "")) for r in rows}),
            "categories": sorted({str(r.get("category", "")) for r in rows}),
        }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
