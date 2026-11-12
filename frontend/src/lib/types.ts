export type RoleCode = "APPLICANT" | "REVIEWER" | "SENIOR_REVIEWER" | "ADMIN";

export interface Role {
  code: RoleCode;
  name: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  mobile: string | null;
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
  mode: "LIVE" | "LOCAL_DEVELOPMENT" | "NONE";
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

export interface DocumentRecord {
  id: string; document_type: string; version: number; filename: string; content_type: string;
  byte_size: number; status: string; quality_result: Record<string, unknown>; uploaded_at: string;
}

export interface ApplicationRecord {
  id: string; applicant_id: string; reference: string; status: string; current_step: number;
  region: string | null; sensitivity: number; date_of_birth: string | null; pan_number: string | null;
  aadhaar_last4: string | null; address: Record<string, string>; education: Record<string, string>;
  bank_details: Record<string, string>; declarations: Record<string, boolean>; rule_result: Record<string, unknown>;
  submitted_at: string | null; created_at: string; updated_at: string; documents: DocumentRecord[];
  applicant_name?: string; applicant_email?: string;
}

export interface TrainingModule {
  code: string; title: string; required_minutes: number; minutes_completed: number; completed: boolean;
}

export interface OperationsSummary {
  total_applications: number; by_status: Record<string, number>; submitted_last_30_days: number;
  average_review_hours: number | null; pending_review: number; corrections_open: number;
  certificates_issued: number; verification_statuses: Record<string, number>;
}
