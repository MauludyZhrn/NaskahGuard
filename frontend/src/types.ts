export type CheckMode = "PLAGIARISM_ONLY" | "AI_ONLY" | "COMBINED";

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
  check_mode?: CheckMode;
  ai_model_id?: string | null;
  exclude_bibliography: boolean;
  exclude_quotes: boolean;
  exclude_citations: boolean;
  exclude_cover: boolean;
  exclude_toc: boolean;
  exclude_common_phrases: boolean;
  min_match_words: number;
  include_lexical_in_index: boolean;
  include_local_corpus?: boolean;
  use_external_sources: boolean;
  enable_academic_search: boolean;
  enable_web_search: boolean;
  enable_oai_sources?: boolean;
  enable_fulltext_download: boolean;
  enable_browser_crawler: boolean;
  search_intensity?: "QUICK" | "BALANCED" | "DEEP";
  max_search_queries: number;
  max_crawled_urls: number;
  max_download_mb: number;
  search_language: "all" | "id" | "en";
  external_providers: string[];
  compare_with_previous_submissions: boolean;
  add_to_corpus_after_check: boolean;
  use_noplag_engine: boolean;
}

export interface ProviderHealthItem {
  id: string;
  name: string;
  type: string;
  default_enabled: boolean;
  full_text_capable: boolean;
  indexed_documents?: number;
  rate_limit?: string;
  status: string;
  configured: boolean;
  enabled: boolean;
  reachable?: boolean | null;
  last_checked?: string | null;
  health: "healthy" | "ready" | "degraded" | "unconfigured";
  request_count: number;
  result_count: number;
  timeout_count: number;
  last_successful_request: string | null;
  last_error: string | null;
}

export interface OAIWizardStage {
  step: number;
  key: string;
  title: string;
  status: "PASS" | "WARN" | "FAIL" | "SKIP";
  http_status: number | null;
  error_code: string | null;
  message: string;
  suggestion: string | null;
  duration_ms: number;
  data?: Record<string, unknown>;
}

export interface OAISampleRecord {
  identifier: string;
  datestamp: string | null;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  doc_type?: string | null;
  subjects?: string[];
  rights: string | null;
  urls: string[];
  pdf_urls: string[];
  set_specs?: string[];
}

export interface OAIConnectionWizardReport {
  ok: boolean;
  overall_status: "READY" | "PARTIAL" | "FAILED";
  summary_counts: { pass: number; warn: number; fail: number };
  input_url: string;
  effective_url: string;
  platform_detected: string;
  platform_label: string;
  identified_name: string | null;
  identify?: Record<string, string>;
  recommended_prefix: string;
  supported_formats: string[];
  available_sets: Array<{ setSpec: string; setName: string }>;
  sample_records: OAISampleRecord[];
  stages: OAIWizardStage[];
  tested_at: string;
  auto_detect_suggestion?: OAIAutoDetectResult | null;
}

export interface OAIAutoDetectResult {
  found: boolean;
  input_url: string;
  detected_url: string | null;
  identified_base_url?: string | null;
  platform_detected: string;
  platform_label?: string;
  identified_name: string | null;
  attempts: Array<{
    url: string;
    status: string;
    http_status?: number | null;
    error_code?: string | null;
    message: string;
  }>;
  message: string;
}

export interface OAIRepositoryFunnel {
  metadata_found: number;
  metadata_saved: number;
  pdf_urls_found: number;
  pdf_accessible: number;
  fulltext_extracted: number;
  document_indexed: number;
  document_compared: number;
  failed_records: number;
}

export interface OAIRepositoryItem {
  id: string;
  name: string;
  base_url: string;
  repo_type: string;
  platform_detected?: string | null;
  platform_label?: string;
  enabled: boolean;
  identified_name: string | null;
  metadata_prefix: string;
  selected_set?: string | null;
  supported_formats?: string[];
  available_sets?: Array<{ setSpec: string; setName: string }>;
  has_resumption_token?: boolean;
  harvest_state?: string;
  last_test_report?: OAIConnectionWizardReport | null;
  last_harvested_at: string | null;
  last_datestamp: string | null;
  records_harvested: number;
  metadata_saved_count?: number;
  pdf_urls_found_count?: number;
  pdf_accessible_count?: number;
  fulltext_extracted_count?: number;
  fulltext_indexed: number;
  failed_records_count?: number;
  rate_limit_delay_sec?: number;
  request_timeout_sec?: number;
  year_from?: number | null;
  year_to?: number | null;
  keyword_filter?: string | null;
  doc_type_filter?: string | null;
  max_downloads?: number;
  schedule_enabled?: boolean;
  schedule_interval_hours?: number;
  next_scheduled_at?: string | null;
  funnel?: OAIRepositoryFunnel;
  status: string;
  last_error: string | null;
  created_at: string | null;
  updated_at?: string | null;
}

export interface RepositoryCatalogItem {
  id: string;
  university: string;
  name: string;
  base_url: string;
  platform: string;
  platform_label: string;
  description: string | null;
  oai_status: "UNVERIFIED" | "VERIFIED" | "PARTIAL" | "ERROR" | string;
  identified_name: string | null;
  collections_count: number;
  supported_formats: string[];
  available_sets: Array<{ setSpec: string; setName: string }>;
  last_error: string | null;
  last_tested_at: string | null;
  is_custom: boolean;
  already_in_personal: boolean;
  created_at: string | null;
}

export interface OAIHarvestRunItem {
  id: string;
  repository_id: string;
  trigger_mode: string;
  status: string;
  set_spec: string | null;
  metadata_prefix: string | null;
  filters_snapshot: Record<string, unknown>;
  records_scanned: number;
  records_matched_filter: number;
  records_harvested: number;
  fulltext_indexed: number;
  metadata_only: number;
  failed_records: number;
  duplicates_skipped: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface OAIIndexedDocumentItem {
  document_id: string;
  oai_identifier: string;
  university: string;
  repository_name: string;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  doc_type: string | null;
  url: string | null;
  license: string | null;
  retrieved_at: string | null;
  word_count: number;
  page_count: number;
  indexing_status: string;
  compared_checks_count: number;
}

export interface OAIHarvestRecordItem {
  id: number;
  repository_id: string;
  oai_identifier: string;
  datestamp: string | null;
  set_spec: string | null;
  metadata_prefix: string | null;
  deleted: boolean;
  title: string | null;
  authors: string[];
  year: number | null;
  doi: string | null;
  doc_type?: string | null;
  subjects?: string[];
  rights: string | null;
  landing_urls: string[];
  pdf_urls: string[];
  status: string;
  document_id: string | null;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface OAIHarvestLogItem {
  id: number;
  repository_id: string;
  level: string;
  stage: string;
  http_status: number | null;
  error_code: string | null;
  message: string;
  details: Record<string, unknown>;
  created_at: string | null;
}

export interface OAIReferenceEndpoint {
  name: string;
  base_url: string;
  platform: string;
  metadata_prefix: string;
  default_set: string;
  note: string;
}

export interface AiSignalItem {
  key: string;
  title: string;
  direction: "ai" | "human" | "neutral";
  detail: string;
}

export interface AiParagraphItem {
  paragraph_index: number;
  char_start: number;
  char_end: number;
  word_count: number;
  text: string;
  classification: "HUMAN_LIKELY" | "MIXED_UNCERTAIN" | "AI_LIKELY" | "INSUFFICIENT_DATA";
  classification_label: string;
  ai_likelihood_pct: number | null;
  uncertainty_pct: number | null;
  highlighted: boolean;
  reasons: string[];
}

export interface AiHighlightItem {
  paragraph_index: number;
  char_start: number;
  char_end: number;
  classification: string;
  classification_label: string;
  ai_likelihood_pct: number | null;
  reasons: string[];
  excerpt: string;
}

export interface AiReportPayload {
  score_available: boolean;
  ai_likelihood_pct: number | null;
  classification: "HUMAN_LIKELY" | "MIXED_UNCERTAIN" | "AI_LIKELY" | "INSUFFICIENT_DATA";
  classification_label: string;
  classification_description: string;
  confidence_label: string;
  uncertainty_pct: number | null;
  word_count: number;
  min_words_required: number;
  language: {
    code: string;
    label: string;
    supported: boolean;
  };
  model_used: string;
  requested_model?: string;
  calibration?: {
    calibrated: boolean;
    method: string;
    temperature: number;
    ai_threshold: number;
    human_threshold: number;
    validation_metrics?: Record<string, unknown>;
  };
  paragraph_summary?: {
    total_paragraphs: number;
    ai_likely_count: number;
    human_likely_count: number;
    uncertain_count: number;
    insufficient_count: number;
  };
  summary_id: string;
  signals: AiSignalItem[];
  paragraphs: AiParagraphItem[];
  highlights: AiHighlightItem[];
  feature_snapshot?: Record<string, number>;
  limitations: string[];
  disclaimer: string;
}

export interface CheckSummary {
  id: string;
  report_number: string;
  document_id: string;
  document_filename: string | null;
  document_title: string | null;
  status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
  mode?: CheckMode;
  stage: string;
  progress: number;
  settings: CheckSettings;
  stage_counts: Record<string, Record<string, unknown>>;
  metrics: Record<string, unknown>;
  coverage: Record<string, unknown>;
  ai_report?: AiReportPayload | null;
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
  canonical_url?: string | null;
  alternate_urls?: string[];
  license?: string | null;
  indexing_status?: string;
  source_type: string;
  category_key?: "internet" | "publication" | "local" | string;
  category_label?: string;
  color_hex?: string;
  highlight_hex?: string;
  chip_bg_hex?: string;
  chip_text_hex?: string;
  access_status: string;
  provider: string;
  matched_words_exclusive: number;
  matched_words_total: number;
  contribution_pct: number;
  layers: Record<string, number>;
  can_download_file: boolean;
}

export interface IntegrityFlagItem {
  code: string;
  title: string;
  severity: "warning" | "info" | string;
  count: number;
  pages_count: number;
  summary: string;
  detail: string;
}

export interface SourceCategorySummary {
  internet_pct: number;
  publication_pct: number;
  local_pct: number;
  counts: {
    internet: number;
    publication: number;
    local: number;
  };
}

export interface SourceAcquisitionItem {
  id: number;
  check_id?: string;
  provider: string;
  query: string;
  title: string;
  authors?: string[];
  year?: number | null;
  doi?: string | null;
  source_url?: string | null;
  canonical_url?: string | null;
  source_type?: string;
  file_type?: string | null;
  license?: string | null;
  status: string;
  used_playwright: boolean;
  document_id?: string | null;
  error?: string | null;
  duration_ms: number;
  created_at?: string | null;
}

export interface SearchCoverageAnalytics {
  total_search_queries: number;
  total_provider_responses: number;
  total_unique_urls_found: number;
  total_pages_crawled: number;
  total_fulltext_fetched: number;
  total_fulltext_indexed: number;
  total_metadata_only: number;
  total_inaccessible_sources: number;
  total_verified_matching_sources: number;
  providers_failed: string[];
  generated_queries?: Array<{ query: string; kind: string; chapter: string; score: number }>;
  indicators?: {
    local_corpus_coverage: string;
    academic_database_coverage: string;
    public_web_coverage: string;
    fulltext_availability: string;
    external_search_coverage: string;
  };
  coverage_disclaimer?: string;
}

export interface ReportMatch {
  id: number;
  source_document_id: string;
  source_rank?: number | null;
  source_color?: string | null;
  source_highlight?: string | null;
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
  mode?: CheckMode;
  stage: string;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  document: {
    id: string;
    filename: string;
    stored_name?: string;
    title: string;
    authors?: string[];
    file_type: string;
    size_bytes?: number;
    language: string;
    page_count: number;
    word_count: number;
    character_count?: number;
    extraction_method: string;
    extraction_confidence: number;
    ocr_pages: number[];
    extra: Record<string, unknown>;
  };
  settings: CheckSettings;
  active_filters?: string[];
  source_categories?: SourceCategorySummary;
  integrity_flags?: IntegrityFlagItem[];
  ai_report?: AiReportPayload | null;
  plain_summary?: {
    similarity_answer: string;
    sources_answer: string;
    ai_answer: string;
    review_answer: string;
    coverage_answer: string;
  };
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
    operational_category?: {
      level: string;
      threshold_low: number;
      threshold_high: number;
      disclaimer: string;
    };
    score_explanation?: {
      formula: string;
      adjusted_formula?: string;
      raw_formula: string;
      raw_similarity?: number;
      adjusted_similarity?: number;
      unrounded_raw_similarity?: number;
      unrounded_adjusted_similarity?: number;
      unrounded_exact_pct?: number;
      unrounded_near_exact_pct?: number;
      rounding_note?: string;
      matched_eligible_words?: number;
      unique_matched_words?: number;
      raw_matched_words?: number;
      eligible_words: number;
      total_words: number;
      excluded_words: number;
      exclusion_breakdown?: Record<string, number>;
      exact_words?: number;
      exact_match_words?: number;
      exact_match_pct?: number;
      near_exact_words?: number;
      near_exact_match_words?: number;
      near_exact_match_pct?: number;
      lexical_words?: number;
      overlap_tokens_removed?: number;
      raw_vs_adjusted_reason?: string;
      raw_vs_adjusted_diff_reason?: string;
    };
    stage_timings_ms?: Record<string, number>;
  };
  coverage: {
    level?: string;
    full_text_sources_compared?: number;
    metadata_only_sources?: number;
    access_denied_sources?: number;
    fetch_failed_sources?: number;
    external_sources_enabled?: boolean;
    notes?: string[];
    statement?: string;
    source_metrics?: {
      search_results_count?: number;
      total_sources_discovered: number;
      total_urls_found: number;
      fulltext_downloaded: number;
      fulltext_indexed: number;
      fulltext_compared: number;
      metadata_only_sources: number;
      inaccessible_sources: number;
      failed_acquisitions?: number;
      matching_sources: number;
      verified_contributing_sources: number;
    };
    search_coverage?: SearchCoverageAnalytics;
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
  acquisitions?: SourceAcquisitionItem[];
}

export interface ViewerSegment {
  char_start: number;
  char_end: number;
  text: string;
  category: "PLAIN" | "EXACT" | "NEAR_EXACT" | "LEXICAL" | "SEMANTIC" | "EXCLUDED";
  match_ids: number[];
  excluded_reason: string | null;
  source_rank?: number | null;
  source_color?: string | null;
  source_highlight?: string | null;
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

export interface ModelCatalogItem {
  id: string;
  name: string;
  family: string;
  source_reference: string;
  license: string;
  tier: "BUILTIN_CPU" | "OPTIONAL_HF";
  languages: string[];
  indonesian_support: string;
  requirements: {
    runtime: string;
    min_ram_mb: number;
    disk_mb: number;
    offline_capable: boolean;
    dependencies_installed: boolean;
    missing_packages?: string[];
  };
  installed: boolean;
  active?: boolean;
  status: string;
  artifact_path: string;
  limitations: string[];
}

export interface DashboardData {
  total_documents_checked: number;
  total_submissions: number;
  average_similarity: number | null;
  average_ai_likelihood: number | null;
  ai_stats?: {
    total_ai_analyzed: number;
    total_ai_only: number;
    total_combined: number;
    total_plagiarism_only: number;
    classification_counts: Record<string, number>;
  };
  recent_reports: Array<{
    check_id: string;
    report_number: string;
    document_id: string;
    filename: string;
    title: string;
    mode?: CheckMode;
    similarity_index: number;
    matched_words: number;
    eligible_words: number;
    ai_likelihood_pct?: number | null;
    ai_classification?: string | null;
    ai_classification_label?: string | null;
    finished_at: string | null;
  }>;
  recent_activity: Array<{
    id: number;
    ts: string | null;
    actor: string;
    action: string;
    target_type: string;
    target_id: string | null;
    details: Record<string, unknown>;
  }>;
  trend: Array<{
    report_number: string;
    mode?: CheckMode;
    similarity_index: number;
    ai_likelihood_pct?: number | null;
    date: string;
  }>;
  corpus_stats: {
    total_documents: number;
    fulltext_sources_available: number;
    total_words: number;
    total_fingerprints: number;
  };
  provider_stats: {
    total_queries: number;
    total_acquisitions: number;
  };
}
