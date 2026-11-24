export interface AppConfig {
  app_name: string;
  version: string;
  max_upload_mb: number;
  pdf_backend: string;
  ocr_available: boolean;
  ocr_message: string;
  semantic_enabled: boolean;
  semantic_available: boolean;
  semantic_message: string;
  retention_days: number;
  threshold_low: number;
  threshold_high: number;
}

export interface DocumentItem {
  id: string;
  role: string;
  filename: string;
  file_hash: string;
  file_type: string;
  mime: string;
  size_bytes: number;
  language: string;
  page_count: number;
  word_count: number;
  title: string | null;
  authors: string[] | null;
  year: number | null;
  doi: string | null;
  url: string | null;
  source_type: string;
  access_status: string;
  extraction_method: string;
  extraction_confidence: number;
  ocr_pages: number[] | null;
  provider: string | null;
  external_id: string | null;
  created_at: string;
}

export interface CheckSettings {
  exclude_bibliography: boolean;
  exclude_quotes: boolean;
  exclude_citations: boolean;
  exclude_cover: boolean;
  exclude_toc: boolean;
  exclude_common_phrases: boolean;
  min_match_words: number;
  include_lexical_in_index: boolean;
  use_external_sources: boolean;
  external_providers: string[];
  compare_with_previous_submissions: boolean;
  add_to_corpus_after_check: boolean;
  use_noplag_engine: boolean;
}

export interface CheckSummary {
  id: string;
  report_number: string;
  document_id: string;
  document_filename: string | null;
  document_title: string | null;
  status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
  stage: string;
  progress: number;
  settings: CheckSettings;
  stage_counts: Record<string, Record<string, unknown>>;
  metrics: Record<string, unknown>;
  coverage: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ReportSource {
  rank: number;
  source_document_id: string;
  title: string;
  filename: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  url: string | null;
  source_type: string;
  access_status: string;
  provider: string;
  matched_words_exclusive: number;
  matched_words_total: number;
  contribution_pct: number;
  layers: Record<string, number>;
  can_download_file: boolean;
}

export interface ReportMatch {
  id: number;
  source_document_id: string;
  source_title: string;
  layer: "EXACT" | "NEAR_EXACT" | "LEXICAL" | "SEMANTIC";
  sub_token_start: number;
  sub_token_end: number;
  sub_char_start: number;
  sub_char_end: number;
  src_token_start: number;
  src_token_end: number;
  src_char_start: number;
  src_char_end: number;
  src_page: number | null;
  matched_words: number;
  score: number;
  sub_excerpt: string;
  src_excerpt: string;
  excluded_reason: string | null;
  counted: boolean;
}

export interface FullReport {
  app_name: string;
  check_id: string;
  report_number: string;
  status: string;
  stage: string;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  document: {
    id: string;
    filename: string;
    title: string;
    file_type: string;
    language: string;
    page_count: number;
    word_count: number;
    extraction_method: string;
    extraction_confidence: number;
    ocr_pages: number[];
    extra: Record<string, unknown>;
  };
  settings: CheckSettings;
  metrics: {
    similarity_index: number;
    raw_similarity: number;
    adjusted_similarity: number;
    exact_match_pct: number;
    near_exact_match_pct: number;
    lexical_match_pct: number;
    include_lexical_in_index: boolean;
    total_words: number;
    eligible_words: number;
    excluded_words: number;
    exclusion_breakdown: Record<string, number>;
    matched_words: number;
    raw_matched_words: number;
    unmatched_eligible_words: number;
    sources_found: number;
    lexical_candidates_count: number;
    semantic_candidates_count: number;
    semantic_candidate_words: number;
    semantic_status: string;
    operational_category: {
      level: string;
      threshold_low: number;
      threshold_high: number;
      disclaimer: string;
    };
  };
  coverage: {
    level: string;
    full_text_sources_compared: number;
    metadata_only_sources: number;
    access_denied_sources: number;
    fetch_failed_sources: number;
    external_sources_enabled: boolean;
    notes: string[];
    statement: string;
    metadata_only_items?: Array<{
      provider: string;
      external_id: string;
      title: string;
      authors: string[];
      year: number | null;
      doi: string | null;
      url: string | null;
      access_status: string;
    }>;
  };
  stage_counts: Record<string, Record<string, unknown>>;
  sources: ReportSource[];
  matches: ReportMatch[];
  analytics: {
    by_chapter: Array<{ chapter: string; total_words: number; matched_words: number; similarity_pct: number }>;
    by_page: Array<{ page: number; total_words: number; matched_words: number; similarity_pct: number }>;
  };
  provider_queries: Array<{
    provider: string;
    query: string;
    status: string;
    result_count: number;
    http_status: number | null;
    error: string | null;
    duration_ms: number;
  }>;
}

export interface ViewerSegment {
  char_start: number;
  char_end: number;
  text: string;
  category: "PLAIN" | "EXACT" | "NEAR_EXACT" | "LEXICAL" | "SEMANTIC" | "EXCLUDED";
  match_ids: number[];
  excluded_reason: string | null;
}

export interface ViewerPayload {
  document_id: string;
  text: string;
  pages: Array<{ number: number; char_start: number; char_end: number }>;
  segments: ViewerSegment[];
}

export interface SourceViewerPayload {
  source_document_id: string;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  url: string | null;
  text: string;
  pages: Array<{ number: number; char_start: number; char_end: number }>;
  highlights: Array<{
    match_id: number;
    layer: string;
    src_char_start: number;
    src_char_end: number;
    sub_char_start: number;
    sub_char_end: number;
    src_page: number | null;
    counted: boolean;
  }>;
}
