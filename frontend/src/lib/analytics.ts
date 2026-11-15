"use client";

/**
 * PolicyNest Product Journey & Telemetry Client SDK
 * Handles non-blocking lifecycle tracking, active vs inactive time instrumentation,
 * session management, and DPDP-compliant event payloads.
 */

const ANON_STORAGE_KEY = "policynest_anon_id";
const SESS_STORAGE_KEY = "policynest_session_id";
const SESS_LAST_ACTIVE_KEY = "policynest_last_active_ts";
const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

function getOrCreateId(storage: Storage, key: string): string {
  if (typeof window === "undefined") return "server_ssr";
  let id = storage.getItem(key);
  if (!id) {
    id = "pn_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now().toString(36);
    storage.setItem(key, id);
  }
  return id;
}

export function getAnonymousId(): string {
  if (typeof window === "undefined") return "ssr_anon";
  return getOrCreateId(localStorage, ANON_STORAGE_KEY);
}

export function getSessionId(): string {
  if (typeof window === "undefined") return "ssr_sess";
  const now = Date.now();
  const lastActive = parseInt(sessionStorage.getItem(SESS_LAST_ACTIVE_KEY) || "0", 10);

  if (now - lastActive > SESSION_TIMEOUT_MS) {
    // Session expired, start fresh session
    const newSess = "sess_" + Math.random().toString(36).substring(2, 11) + "_" + now.toString(36);
    sessionStorage.setItem(SESS_STORAGE_KEY, newSess);
    sessionStorage.setItem(SESS_LAST_ACTIVE_KEY, now.toString());
    return newSess;
  }

  sessionStorage.setItem(SESS_LAST_ACTIVE_KEY, now.toString());
  return getOrCreateId(sessionStorage, SESS_STORAGE_KEY);
}

export interface TrackOptions {
  applicationId?: string;
  stage?: string;
  stageDurationMs?: number;
  activeTimeMs?: number;
  inactiveTimeMs?: number;
  waitingTimeMs?: number;
  backendTimeMs?: number;
  isAbandonment?: boolean;
  validationErrorsCount?: number;
  attemptNumber?: number;
}

export async function trackEvent(
  eventName: string,
  properties: Record<string, unknown> = {},
  options: TrackOptions = {}
): Promise<void> {
  if (typeof window === "undefined") return;

  const payload = {
    event_name: eventName,
    anonymous_id: getAnonymousId(),
    session_id: getSessionId(),
    application_id: options.applicationId || undefined,
    stage: options.stage || undefined,
    stage_duration_ms: options.stageDurationMs || undefined,
    active_time_ms: options.activeTimeMs || undefined,
    inactive_time_ms: options.inactiveTimeMs || undefined,
    waiting_time_ms: options.waitingTimeMs || undefined,
    backend_time_ms: options.backendTimeMs || undefined,
    is_abandonment: options.isAbandonment ?? false,
    validation_errors_count: options.validationErrorsCount ?? 0,
    attempt_number: options.attemptNumber ?? 1,
    source: "web",
    environment: process.env.NEXT_PUBLIC_APP_ENV || "production",
    properties: {
      ...properties,
      url: window.location.pathname,
      referrer: document.referrer || "direct",
      screen_width: window.innerWidth,
    },
  };

  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://policynest-backend-production-49f797fc.up.railway.app";
    void fetch(`${apiBase}/api/v1/analytics/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {
      // Non-blocking telemetry failure
    });
  } catch {
    // Fail safe
  }
}

// 16 Lifecycle Step Tracking Helpers
export const analytics = {
  // Step 1: Website Visit
  visit: (pageName: string) => trackEvent("visitor.viewed", { page_name: pageName }, { stage: "LANDING" }),

  // Steps 2 & 3: Registration
  registrationStarted: (method = "email") =>
    trackEvent("registration.started", { method }, { stage: "REGISTRATION" }),
  registrationCompleted: (method = "email") =>
    trackEvent("registration.completed", { method }, { stage: "REGISTRATION" }),

  // Step 4: Login
  login: (persona?: string) => trackEvent("auth.login", { persona }, { stage: "AUTH" }),

  // Step 5: Application Created
  applicationCreated: (appId: string) =>
    trackEvent("application.created", {}, { applicationId: appId, stage: "APPLICATION" }),

  // Step 6: Section opened / completed
  sectionOpened: (appId: string, section: string) =>
    trackEvent("application.section_opened", { section }, { applicationId: appId, stage: section }),
  sectionCompleted: (appId: string, section: string, durationMs?: number) =>
    trackEvent("application.section_completed", { section }, { applicationId: appId, stage: section, stageDurationMs: durationMs }),

  // Step 7: Document Upload
  docUploadStarted: (appId: string, docType: string) =>
    trackEvent("document.upload_started", { doc_type: docType }, { applicationId: appId, stage: "DOCUMENT_UPLOAD" }),
  docUploadCompleted: (appId: string, docType: string, qualityStatus = "OK", attemptNumber = 1) =>
    trackEvent(
      "document.upload_completed",
      { doc_type: docType, quality_status: qualityStatus },
      { applicationId: appId, stage: "DOCUMENT_UPLOAD", attemptNumber }
    ),

  // Step 8: Application Submitted
  submitted: (appId: string, docsCount = 6) =>
    trackEvent("application.submitted", { docs_count: docsCount }, { applicationId: appId, stage: "SUBMISSION" }),

  // Step 9: Document Processing
  docProcessed: (appId: string, docType: string, latencyMs: number) =>
    trackEvent("document.processed", { doc_type: docType, latency_ms: latencyMs }, { applicationId: appId, stage: "OCR" }),

  // Step 10: Verification & Instant Decision
  verificationEvaluated: (appId: string, outcome: string, isStp = false) =>
    trackEvent("verification.evaluated", { outcome, is_stp: isStp }, { applicationId: appId, stage: "VERIFICATION" }),

  // Step 11 & 12: Reviewer assignment & decision
  reviewerAssigned: (appId: string, reviewerId: string) =>
    trackEvent("reviewer.assigned", { reviewer_id: reviewerId }, { applicationId: appId, stage: "REVIEW" }),
  reviewerDecided: (appId: string, decision: string, reviewerId?: string) =>
    trackEvent("reviewer.decided", { decision, reviewer_id: reviewerId }, { applicationId: appId, stage: "REVIEW" }),

  // Step 13 & 14: Correction requested & submitted
  correctionRequested: (appId: string, reasons: string[]) =>
    trackEvent("correction.requested", { reasons }, { applicationId: appId, stage: "REWORK" }),
  correctionSubmitted: (appId: string, attempt = 1) =>
    trackEvent("correction.submitted", {}, { applicationId: appId, stage: "REWORK", attemptNumber: attempt }),

  // Step 15: Training
  trainingStarted: (appId: string) =>
    trackEvent("training.started", {}, { applicationId: appId, stage: "TRAINING" }),
  trainingCompleted: (appId: string, score: number) =>
    trackEvent("training.completed", { score }, { applicationId: appId, stage: "TRAINING" }),

  // Step 16: Certification Issued
  certificationIssued: (appId: string, certNumber: string) =>
    trackEvent("certification.issued", { cert_number: certNumber }, { applicationId: appId, stage: "CERTIFIED" }),
};
