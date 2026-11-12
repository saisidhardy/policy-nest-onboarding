export type RoleCode = "APPLICANT" | "REVIEWER" | "SENIOR_REVIEWER" | "ADMIN";
export type LanguageCode = "EN" | "HI";

export interface Role {
  code: RoleCode;
  name: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  mobile: string | null;
  preferred_language: LanguageCode;
  role: Role;
  is_active: boolean;
  email_verified: boolean;
  region: string | null;
  clearance_level: number;
  last_login_at: string | null;
  created_at: string;
}

export interface AdminUser extends User {
  locked_until: string | null;
  failed_login_count: number;
  invitation_pending: boolean;
}

export interface Me {
  user: User;
  permissions: string[];
  session_expires_at: string;
  email_delivery_configured: boolean;
}

export interface AuthConfig {
  email_delivery_configured: boolean;
  require_email_verification: boolean;
  password_min_length: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  ip_address: string | null;
  user_agent: string | null;
  current: boolean;
}

export interface AuditLog {
  id: number;
  occurred_at: string;
  actor_user_id: string | null;
  actor_email: string | null;
  actor_role: string | null;
  action: string;
  outcome: "SUCCESS" | "FAILURE" | "DENIED";
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  request_id: string | null;
  details: Record<string, unknown>;
}

export interface Permission {
  code: string;
  category: string;
  description: string;
}

export interface RoleDetail {
  code: RoleCode;
  name: string;
  description: string;
  is_staff: boolean;
  user_count: number;
  permissions: string[];
}

export interface RolesMatrix {
  roles: RoleDetail[];
  permissions: Permission[];
  regions: string[];
}

export interface IntegrationStatus {
  key: string;
  name: string;
  status: "CONFIGURED" | "NOT_CONFIGURED" | "DEGRADED";
  mode: "LIVE" | "LOCAL_DEVELOPMENT" | "SANDBOX" | "NONE";
  detail: string;
}

export interface SystemHealth {
  status: string;
  app_env: string;
  version: string;
  database: Record<string, unknown>;
  integrations: IntegrationStatus[];
  email_deliveries_last_24h: Record<string, number>;
}

export interface AdminStats {
  users_by_role: Record<string, number>;
  active_users: number;
  inactive_users: number;
  unverified_users: number;
  pending_invitations: number;
  active_sessions: number;
  registrations_last_7_days: number;
  failed_logins_last_24h: number;
  recent_audit: AuditLog[];
}

export interface Message {
  message: string;
}

export interface EmailDispatchResult {
  message: string;
  email_delivery: string;
}

export type DocumentType =
  | "PAN_CARD"
  | "AADHAAR_FRONT"
  | "AADHAAR_BACK"
  | "CLASS_10_MARKSHEET"
  | "BANK_DOCUMENT"
  | "APPLICANT_SELFIE";

export type GenderType = "MALE" | "FEMALE" | "OTHER" | "PREFER_NOT_TO_SAY";
export type EducationLevelType = "CLASS_10" | "CLASS_12" | "GRADUATE" | "POST_GRADUATE";
export type ResultStatusType = "PASS" | "FAIL" | "AWAITING";
export type AccountType = "SAVINGS" | "CURRENT";

export interface ApplicationDocument {
  id: string;
  application_id: string;
  doc_type: DocumentType;
  version: number;
  is_current: boolean;
  status: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  storage_provider: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationEvent {
  id: number;
  application_id: string;
  actor_user_id: string | null;
  actor_role: string | null;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  summary: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface SectionCompleteness {
  personal: boolean;
  address: boolean;
  education: boolean;
  bank: boolean;
  documents: boolean;
  declarations: boolean;
}

export interface CompletenessReport {
  sections: SectionCompleteness;
  missing_fields: string[];
  missing_documents: DocumentType[];
  uploaded_document_count: number;
  required_document_count: number;
  completed_sections: number;
  total_sections: number;
  ready_to_submit: boolean;
}

export interface ApplicationSummary {
  id: string;
  reference_code: string;
  status: string;
  current_step: number;
  region: string | null;
  preferred_language: LanguageCode;
  full_name: string | null;
  submitted_at: string | null;
  last_saved_at: string;
  resolution_kind?: string | null;
  rework_count?: number;
  created_at: string;
  updated_at: string;
  completeness: CompletenessReport;
}

export interface ApplicationDetail {
  id: string;
  reference_code: string;
  user_id: string;
  status: string;
  current_step: number;
  region: string | null;
  sensitivity: number;
  preferred_language: LanguageCode;
  channel: string;

  full_name: string | null;
  date_of_birth: string | null;
  gender: GenderType | null;
  father_or_spouse_name: string | null;
  mobile: string | null;
  email: string | null;
  pan_number: string | null;
  aadhaar_last4: string | null;

  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  pincode: string | null;
  same_as_permanent: boolean;
  permanent_address_line1: string | null;
  permanent_address_line2: string | null;
  permanent_city: string | null;
  permanent_state: string | null;
  permanent_pincode: string | null;

  education_level: EducationLevelType | null;
  board_name: string | null;
  school_or_university: string | null;
  passing_year: number | null;
  roll_number: string | null;
  result_status: ResultStatusType | null;
  percentage_or_cgpa: string | null;

  account_holder_name: string | null;
  bank_name: string | null;
  branch_name: string | null;
  ifsc_code: string | null;
  account_number_last4: string | null;
  account_number_masked: string | null;
  has_account_number: boolean;
  account_type: AccountType | null;
  is_joint_account: boolean;
  is_primary_holder: boolean;

  consent_terms: boolean;
  consent_kyc_processing: boolean;
  declaration_no_other_posp: boolean;
  declared_at: string | null;
  submitted_at: string | null;
  last_saved_at: string;
  parent_application_id?: string | null;
  resolution_kind?: string | null;
  reapplication_reason?: string | null;
  rework_count?: number;
  created_at: string;
  updated_at: string;

  documents: ApplicationDocument[];
  document_history: ApplicationDocument[];
  events: ApplicationEvent[];
  completeness: CompletenessReport;
}

export interface NotificationItem {
  id: string;
  application_id: string | null;
  category: string;
  title: string;
  body: string;
  action_url: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationsPage {
  items: NotificationItem[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export interface DocumentExtraction {
  id: string;
  document_id: string;
  doc_type: DocumentType;
  application_id: string;
  ocr_engine: string;
  ai_assistant_provider: string;
  predicted_doc_type: string | null;
  classification_confidence: number | null;
  classification_match: boolean | null;
  quality_status: string;
  blur_score: number | null;
  glare_ratio: number | null;
  edge_clip_ratio: number | null;
  face_detected: boolean | null;
  ocr_confidence: number | null;
  raw_ocr_text_masked: string | null;
  extracted_fields: Record<string, string>;
  missing_fields: string[];
  ai_explanation: string | null;
  aadhaar_masked_applied: boolean;
  has_redacted_image: boolean;
  reviewer_corrected_fields: Record<string, string> | null;
  effective_fields: Record<string, string>;
  corrected_by_user_id: string | null;
  corrected_at: string | null;
  processed_at: string;
}

export interface VerificationCheck {
  id: string;
  application_id: string;
  check_type: string;
  target_doc_type: string | null;
  status: string;
  origin: string;
  provider_name: string | null;
  provider_reference: string | null;
  is_simulated: boolean;
  confidence: number | null;
  details: Record<string, unknown>;
  explanation: string | null;
  checked_at: string;
}

export interface FieldCorrection {
  id: string;
  extraction_id: string;
  application_id: string;
  document_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  corrected_by_user_id: string | null;
  created_at: string;
}

export interface VerificationSummary {
  documents_processed: number;
  quality_passed: number;
  quality_warn: number;
  quality_failed: number;
  checks_passed: number;
  checks_warn: number;
  checks_needs_info: number;
  checks_failed: number;
  checks_not_configured: number;
  advisory_note: string;
}

export interface ApplicationVerificationReport {
  application_id: string;
  reference_code: string;
  status: string;
  extractions: DocumentExtraction[];
  checks: VerificationCheck[];
  corrections: FieldCorrection[];
  summary: VerificationSummary;
}

export interface RuleSetConfig {
  min_age_years: number;
  min_ocr_confidence: number;
  face_match_auto_pass_threshold: number;
  face_match_rework_threshold: number;
  max_rework_cycles_before_human: number;
  auto_approve_enabled: boolean;
  auto_reject_statutory: boolean;
  never_auto_reject_name_mismatch: true;
  recognized_education_boards: string[];
  require_all_six_documents: boolean;
  allow_bank_truncation_match: boolean;
}

export interface RuleSet {
  id: string;
  version: string;
  name: string;
  description: string | null;
  status: string;
  is_active: boolean;
  rules_config: RuleSetConfig;
  created_by_user_id: string | null;
  activated_by_user_id: string | null;
  activated_at: string | null;
  created_at: string;
}

export interface RuleEvaluationItem {
  rule_id: string;
  category: string;
  name: string;
  status: "PASS" | "FAIL" | "HUMAN_REVIEW" | "INFO" | "NOT_EVALUATED";
  severity: "HARD_REJECT" | "REWORK" | "HUMAN_ONLY" | "INFO" | "NONE";
  reason_code: string | null;
  explanation: string;
  evidence: Record<string, unknown>;
}

export interface ReworkItem {
  doc_type: string | null;
  reason_code: string;
  title_en: string;
  title_hi: string;
  action_en: string;
  action_hi: string;
}

export interface RiskIndicator {
  code: string;
  level: string;
  message: string;
}

export interface RuleExecution {
  id: string;
  application_id: string;
  ruleset_id: string;
  ruleset_version: string;
  trigger_source: string;
  triggered_by_user_id: string | null;
  outcome: string;
  recommended_status: string;
  eligibility_status: string;
  completeness_status: string;
  consistency_status: string;
  risk_level: string;
  auto_pass_eligible: boolean;
  requires_human_review: boolean;
  reason_codes: string[];
  rule_results: RuleEvaluationItem[];
  rework_items: ReworkItem[];
  risk_indicators: RiskIndicator[];
  summary: string;
  executed_at: string;
}

export interface ApplicationDecision {
  id: string;
  application_id: string;
  rule_execution_id: string | null;
  decided_by_user_id: string;
  decided_by_role: string;
  decision: string;
  previous_status: string;
  new_status: string;
  is_override: boolean;
  override_of_outcome: string | null;
  reason_codes: string[];
  reason_text: string;
  rework_items: ReworkItem[];
  created_at: string;
}

export interface ApplicationAppeal {
  id: string;
  application_id: string;
  submitted_by_user_id: string;
  status: string;
  appeal_reason: string;
  supporting_notes: string | null;
  resolution_notes: string | null;
  resolved_by_user_id: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ApplicationDecisionSummary {
  application_id: string;
  application_status: string;
  resolution_kind: string | null;
  parent_application_id: string | null;
  rework_count: number;
  active_ruleset_version: string;
  latest_execution: RuleExecution | null;
  execution_history: RuleExecution[];
  decisions: ApplicationDecision[];
  appeals: ApplicationAppeal[];
}
