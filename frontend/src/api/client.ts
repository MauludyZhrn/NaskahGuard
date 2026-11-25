const API_BASE = "/api";

export type UiErrorKind =
  | "API_ROUTE_NOT_FOUND"
  | "OAI_ENDPOINT_NOT_FOUND"
  | "EMPTY_RECORDS"
  | "UNAVAILABLE_METADATA_FORMAT"
  | "FULLTEXT_POLICY_RESTRICTED"
  | "RESOURCE_NOT_FOUND"
  | "NETWORK_ERROR"
  | "HTTP_ERROR";

export interface StructuredUiError {
  errorKind: UiErrorKind;
  errorKindLabel: string;
  stage: string;
  testedUrl: string;
  httpStatus: number | null;
  cause: string;
  suggestion: string;
}

export class ApiRequestError extends Error {
  status: number | null;
  path: string;
  detail: string;
  errorKind: UiErrorKind;
  errorKindLabel: string;
  cause: string;
  suggestion: string;

  constructor(opts: {
    message: string;
    status: number | null;
    path: string;
    detail: string;
    errorKind: UiErrorKind;
    errorKindLabel: string;
    cause: string;
    suggestion: string;
  }) {
    super(opts.message);
    this.name = "ApiRequestError";
    this.status = opts.status;
    this.path = opts.path;
    this.detail = opts.detail;
    this.errorKind = opts.errorKind;
    this.errorKindLabel = opts.errorKindLabel;
    this.cause = opts.cause;
    this.suggestion = opts.suggestion;
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("ng_api_token") || "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function classifyHttpFailure(
  status: number,
  path: string,
  rawDetail: string
): {
  errorKind: UiErrorKind;
  errorKindLabel: string;
  cause: string;
  suggestion: string;
} {
  const detail = rawDetail.trim();
  const low = detail.toLowerCase();

  // Distinguish FastAPI built-in 404 ({"detail": "Not Found"}) from domain 404 / external OAI 404
  if (status === 404 && (!detail || low === "not found" || low === "http 404")) {
    return {
      errorKind: "API_ROUTE_NOT_FOUND",
      errorKindLabel: "API route tidak ditemukan",
      cause: `Route backend internal '${API_BASE}${path}' mengembalikan HTTP 404 (API route tidak ditemukan pada server backend yang aktif, kemungkinan masih menjalankan proses server versi lama).`,
      suggestion:
        "Mulai ulang server backend menggunakan scripts/dev.ps1 atau 'uvicorn app.main:app --reload', lalu muat ulang halaman ini.",
    };
  }

  if (status === 404) {
    return {
      errorKind: "RESOURCE_NOT_FOUND",
      errorKindLabel: "Data repositori tidak ditemukan",
      cause: detail,
      suggestion: "Muat ulang daftar repositori atau periksa apakah entri masih tersedia.",
    };
  }

  if (low.includes("policy_restricted") || low.includes("dibatasi kebijakan") || low.includes("panen robot")) {
    return {
      errorKind: "FULLTEXT_POLICY_RESTRICTED",
      errorKindLabel: "Full-text dibatasi kebijakan",
      cause: detail,
      suggestion:
        "Gunakan mode Metadata Saja (default) agar tetap mematuhi kebijakan repositori sumber.",
    };
  }

  if (low.includes("cannotdisseminateformat") || low.includes("nometadataformats") || low.includes("format metadata")) {
    return {
      errorKind: "UNAVAILABLE_METADATA_FORMAT",
      errorKindLabel: "Metadata format tidak tersedia",
      cause: detail,
      suggestion: "Jalankan Uji Koneksi untuk melihat daftar format metadata yang didukung lalu pilih format yang tersedia (mis. oai_dc).",
    };
  }

  if (low.includes("norecordsmatch") || low.includes("tidak ada rekaman")) {
    return {
      errorKind: "EMPTY_RECORDS",
      errorKindLabel: "Repository tidak memiliki record",
      cause: detail,
      suggestion: "Kosongkan filter koleksi (setSpec) atau perluas rentang tanggal/tahun publikasi.",
    };
  }

  if (low.includes("http_404") || low.includes("html_response") || low.includes("endpoint oai-pmh tidak ditemukan")) {
    return {
      errorKind: "OAI_ENDPOINT_NOT_FOUND",
      errorKindLabel: "Endpoint OAI-PMH tidak ditemukan",
      cause: detail,
      suggestion:
        "Periksa URL endpoint OAI-PMH (/cgi/oai2 untuk EPrints, /server/oai/request untuk DSpace 7, /index.php/{jurnal}/oai untuk OJS).",
    };
  }

  return {
    errorKind: "HTTP_ERROR",
    errorKindLabel: `Kesalahan HTTP ${status}`,
    cause: detail || `Server mengembalikan status HTTP ${status}.`,
    suggestion:
      status >= 500
        ? "Periksa log backend atau coba ulang beberapa saat lagi jika server repositori eksternal sedang sibuk."
        : "Periksa kembali data masukan pada formulir lalu coba lagi.",
  };
}

export function toStructuredUiError(
  err: unknown,
  context: { stage: string; testedUrl?: string; endpointPath?: string }
): StructuredUiError {
  const urlDisplay = context.testedUrl || (context.endpointPath ? `${API_BASE}${context.endpointPath}` : "-");

  if (err instanceof ApiRequestError) {
    return {
      errorKind: err.errorKind,
      errorKindLabel: err.errorKindLabel,
      stage: context.stage,
      testedUrl:
        err.errorKind === "API_ROUTE_NOT_FOUND"
          ? `${API_BASE}${err.path}${context.testedUrl ? ` (target: ${context.testedUrl})` : ""}`
          : urlDisplay,
      httpStatus: err.status,
      cause: err.cause,
      suggestion: err.suggestion,
    };
  }

  const rawMsg = err instanceof Error ? err.message : String(err || "Kesalahan tidak diketahui");
  const isNetwork =
    err instanceof TypeError ||
    rawMsg.toLowerCase().includes("failed to fetch") ||
    rawMsg.toLowerCase().includes("networkerror");

  return {
    errorKind: isNetwork ? "NETWORK_ERROR" : "HTTP_ERROR",
    errorKindLabel: isNetwork ? "Koneksi ke server backend gagal" : "Kendala Pemrosesan",
    stage: context.stage,
    testedUrl: urlDisplay,
    httpStatus: null,
    cause: isNetwork
      ? "Tidak dapat menjangkau server API NaskahGuard (/api) melalui proxy Vite."
      : rawMsg === "Not Found"
        ? `Route backend ${context.endpointPath || "/api/oai"} tidak ditemukan (HTTP 404).`
        : rawMsg,
    suggestion: isNetwork
      ? "Pastikan backend FastAPI (port 8000) dan frontend Vite (port 5173) sedang berjalan via scripts/dev.ps1."
      : "Periksa URL endpoint atau mulai ulang server backend bila route baru belum aktif.",
  };
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...getAuthHeaders(),
    ...(init?.headers as Record<string, string> | undefined),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      if (data?.detail) detail = String(data.detail);
    } catch {
      // ignore non-JSON body
    }
    const info = classifyHttpFailure(res.status, path, detail);
    throw new ApiRequestError({
      message: info.cause,
      status: res.status,
      path,
      detail: detail || `HTTP ${res.status}`,
      errorKind: info.errorKind,
      errorKindLabel: info.errorKindLabel,
      cause: info.cause,
      suggestion: info.suggestion,
    });
  }
  return (await res.json()) as T;
}

export async function downloadProtectedFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Gagal mengunduh berkas (HTTP ${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
