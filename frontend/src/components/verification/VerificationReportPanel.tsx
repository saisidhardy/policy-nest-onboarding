"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Edit3,
  Eye,
  FileSearch,
  History,
  Info,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Dialog, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { REQUIRED_DOCUMENTS } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type {
  ApplicationVerificationReport,
  DocumentExtraction,
  VerificationCheck,
} from "@/lib/types";

const QUALITY_BADGE: Record<string, { label: string; tone: "success" | "warning" | "danger" }> = {
  OK: { label: "Quality OK", tone: "success" },
  IMAGE_GLARE: { label: "Glare detected", tone: "warning" },
  IMAGE_CROPPED: { label: "Edges clipped", tone: "warning" },
  IMAGE_BLURRY: { label: "Too blurry", tone: "danger" },
  LOW_RESOLUTION: { label: "Low resolution", tone: "danger" },
  FACE_NOT_DETECTED: { label: "No face detected", tone: "danger" },
  UNREADABLE: { label: "Unreadable file", tone: "danger" },
};

const CHECK_BADGE: Record<string, { label: string; tone: "success" | "warning" | "danger" | "neutral" | "brand" }> = {
  PASSED: { label: "Passed", tone: "success" },
  WARN: { label: "Needs review", tone: "warning" },
  NEEDS_INFO: { label: "Needs confirmation", tone: "warning" },
  FAILED: { label: "Failed", tone: "danger" },
  NOT_CONFIGURED: { label: "Not configured", tone: "neutral" },
  UNAVAILABLE: { label: "Unavailable", tone: "neutral" },
};

const ORIGIN_LABEL: Record<string, string> = {
  DETERMINISTIC_RULE: "Deterministic rule",
  PUBLIC_DIRECTORY: "Live public directory",
  SANDBOX: "Sandbox fixture (simulated)",
  REAL_PROVIDER: "Authorized provider",
  UNCONFIGURED: "Adapter not configured",
};

const EDITABLE_FIELD_OPTIONS: { key: string; label: string }[] = [
  { key: "full_name", label: "Full name" },
  { key: "dob", label: "Date of birth (YYYY-MM-DD or YYYY)" },
  { key: "pan_number", label: "PAN number" },
  { key: "aadhaar_last4", label: "Aadhaar last 4 digits" },
  { key: "pincode", label: "PIN code" },
  { key: "address_or_pincode", label: "Address / PIN indicator" },
  { key: "board_name", label: "Education board" },
  { key: "result_status", label: "Result status" },
  { key: "roll_number", label: "Roll number" },
  { key: "passing_year", label: "Passing year" },
  { key: "ifsc_code", label: "IFSC code" },
  { key: "account_last4", label: "Account last 4 digits" },
  { key: "bank_name", label: "Bank name" },
];

function docLabel(docType: string): string {
  return REQUIRED_DOCUMENTS.find((d) => d.type === docType)?.label ?? docType;
}

export function RedactedImageDialog({
  applicationId,
  documentId,
  docType,
  onClose,
}: {
  applicationId: string;
  documentId: string | null;
  docType: string | null;
  onClose: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) {
      setUrl(null);
      setError(null);
      return;
    }
    let active = true;
    let objectUrl: string | null = null;
    setLoading(true);
    setError(null);
    fetch(`/api/v1/applications/${applicationId}/documents/${documentId}/redacted`, {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Unable to load redacted image (HTTP ${res.status}).`);
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (active) setUrl(objectUrl);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load redacted Aadhaar image.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [applicationId, documentId]);

  return (
    <Dialog
      open={!!documentId}
      onClose={onClose}
      title={docType ? `Redacted ${docLabel(docType)}` : "Redacted Aadhaar image"}
      description="12-digit Aadhaar numbers and QR codes are masked with solid OpenCV redaction boxes before preview."
    >
      <div className="space-y-3">
        {loading && <p className="text-sm text-slate-600">Loading masked image...</p>}
        {error && <Alert tone="error">{error}</Alert>}
        {url && (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="Redacted Aadhaar copy" className="mx-auto max-h-[60vh] w-auto object-contain" />
          </div>
        )}
      </div>
    </Dialog>
  );
}

export function FieldCorrectionDialog({
  applicationId,
  extraction,
  onClose,
  onUpdated,
}: {
  applicationId: string;
  extraction: DocumentExtraction | null;
  onClose: () => void;
  onUpdated: (report: ApplicationVerificationReport) => void;
}) {
  const [fieldName, setFieldName] = useState("full_name");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!extraction) return;
    const keys = Object.keys(extraction.effective_fields);
    const initialKey = keys[0] ?? (extraction.missing_fields[0] || "full_name");
    setFieldName(initialKey);
    setValue(extraction.effective_fields[initialKey] ?? "");
    setReason("");
    setError(null);
  }, [extraction]);

  useEffect(() => {
    if (!extraction) return;
    setValue(extraction.effective_fields[fieldName] ?? "");
  }, [extraction, fieldName]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!extraction) return;
    const cleanVal = value.trim();
    const cleanReason = reason.trim();
    if (!cleanVal) {
      setError("Enter a non-empty corrected value.");
      return;
    }
    if (/\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/.test(cleanVal) || /\d{12,}/.test(cleanVal)) {
      setError("Never enter a 12-digit Aadhaar number; store only the last 4 digits.");
      return;
    }
    if (cleanReason.length < 5) {
      setError("Enter a correction audit reason of at least 5 characters.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const updated = await api<ApplicationVerificationReport>(
        `/applications/${applicationId}/documents/${extraction.document_id}/fields`,
        {
          method: "PATCH",
          body: { fields: { [fieldName]: cleanVal }, reason: cleanReason },
        },
      );
      onUpdated(updated);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save field correction.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={!!extraction}
      onClose={onClose}
      title={extraction ? `Correct extracted field · ${docLabel(extraction.doc_type)}` : "Correct extracted field"}
      description="Corrections create an immutable reviewer audit entry and immediately re-run deterministic cross-document checks."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="Field to correct" htmlFor="correction-field-name">
          <select
            id="correction-field-name"
            value={fieldName}
            onChange={(e) => setFieldName(e.target.value)}
            className="block h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900"
          >
            {EDITABLE_FIELD_OPTIONS.map((opt) => (
              <option key={opt.key} value={opt.key}>
                {opt.label} ({opt.key})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Corrected value" htmlFor="correction-field-value">
          <Input
            id="correction-field-value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Enter verified value from document"
            required
          />
        </Field>
        <Field label="Audit reason" htmlFor="correction-reason">
          <Input
            id="correction-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Confirmed blurry digit directly from source PAN scan"
            required
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Save correction &amp; re-verify
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function VerificationReportPanel({
  report,
  onReportChange,
  canRunProcessing = false,
  canCorrectFields = false,
}: {
  report: ApplicationVerificationReport | null;
  onReportChange?: (next: ApplicationVerificationReport) => void;
  canRunProcessing?: boolean;
  canCorrectFields?: boolean;
}) {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [expandedOcrId, setExpandedOcrId] = useState<string | null>(null);
  const [redactedTarget, setRedactedTarget] = useState<{ documentId: string; docType: string } | null>(null);
  const [editingExt, setEditingExt] = useState<DocumentExtraction | null>(null);

  async function triggerProcessing(applicationId: string) {
    setRunning(true);
    setRunError(null);
    try {
      const next = await api<ApplicationVerificationReport>(`/applications/${applicationId}/process`, {
        method: "POST",
      });
      onReportChange?.(next);
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Document processing failed.");
    } finally {
      setRunning(false);
    }
  }

  if (!report || report.extractions.length === 0) {
    return (
      <Card>
        <CardHeader
          title="Document intelligence & verification"
          description="OCR extraction, image quality inspection, Aadhaar redaction, and cross-document checks."
        />
        <div className="space-y-4 px-5 py-5 text-sm text-slate-600">
          {runError && <Alert tone="error">{runError}</Alert>}
          <p>Document intelligence has not run for the current uploaded files yet.</p>
          {canRunProcessing && report && (
            <Button onClick={() => triggerProcessing(report.application_id)} loading={running} variant="secondary">
              <Sparkles className="h-4 w-4" /> Run document intelligence now
            </Button>
          )}
        </div>
      </Card>
    );
  }

  const { summary, extractions, checks, corrections } = report;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Document intelligence & consistency summary"
          description={summary.advisory_note}
          action={
            canRunProcessing ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => triggerProcessing(report.application_id)}
                loading={running}
              >
                <RefreshCw className="h-4 w-4" /> Re-run OCR &amp; checks
              </Button>
            ) : undefined
          }
        />
        <div className="space-y-4 p-5">
          {runError && <Alert tone="error">{runError}</Alert>}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryTile
              label="Documents processed"
              value={summary.documents_processed}
              hint={`${summary.quality_passed} quality OK · ${summary.quality_failed + summary.quality_warn} flagged`}
            />
            <SummaryTile
              label="Checks passed"
              value={summary.checks_passed}
              tone="success"
              hint="Deterministic rule & directory checks"
            />
            <SummaryTile
              label="Needs confirmation / warn"
              value={summary.checks_warn + summary.checks_needs_info}
              tone="warning"
              hint={`${summary.checks_failed} hard failure(s)`}
            />
            <SummaryTile
              label="Unconfigured providers"
              value={summary.checks_not_configured}
              tone="neutral"
              hint="Authorized external APIs pending credentials"
            />
          </div>
          <Alert tone="info" title="AI & OCR Governance">
            AI explanations and OCR scores assist triage only and never auto-approve or reject an onboarding application.
            Name mismatches always route to human confirmation.
          </Alert>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Per-document OCR, quality & Aadhaar redaction"
          description="Measured OpenCV image quality, document classification, extracted fields, and Aadhaar masking."
        />
        <div className="divide-y divide-slate-200">
          {extractions.map((ext) => {
            const qBadge = QUALITY_BADGE[ext.quality_status] ?? { label: ext.quality_status, tone: "warning" as const };
            const fieldEntries = Object.entries(ext.effective_fields ?? {});
            const showOcr = expandedOcrId === ext.id;
            return (
              <div key={ext.id} className="space-y-3 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-slate-900">{docLabel(ext.doc_type)}</h3>
                      <Badge tone={qBadge.tone}>{qBadge.label}</Badge>
                      {ext.classification_match === true && <Badge tone="success">Type verified ({ext.predicted_doc_type})</Badge>}
                      {ext.classification_match === false && (
                        <Badge tone="warning">Predicted: {ext.predicted_doc_type ?? "UNKNOWN"}</Badge>
                      )}
                      {ext.aadhaar_masked_applied && (
                        <Badge tone="brand">Aadhaar masked</Badge>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      Engine: {ext.ocr_engine} · Assistant: {ext.ai_assistant_provider}
                      {ext.ocr_confidence != null && ` · OCR confidence ${Math.round(ext.ocr_confidence * 100)}%`}
                      {ext.blur_score != null && ` · Sharpness var ${ext.blur_score}`}
                      {ext.face_detected !== null && ` · Face detected: ${ext.face_detected ? "Yes" : "No"}`}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {ext.has_redacted_image && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setRedactedTarget({ documentId: ext.document_id, docType: ext.doc_type })}
                      >
                        <Eye className="h-4 w-4" /> View redacted Aadhaar
                      </Button>
                    )}
                    {ext.raw_ocr_text_masked && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setExpandedOcrId(showOcr ? null : ext.id)}
                      >
                        <FileSearch className="h-4 w-4" /> {showOcr ? "Hide OCR text" : "Masked OCR text"}
                      </Button>
                    )}
                    {canCorrectFields && (
                      <Button size="sm" variant="secondary" onClick={() => setEditingExt(ext)}>
                        <Edit3 className="h-4 w-4" /> Correct fields
                      </Button>
                    )}
                  </div>
                </div>

                {fieldEntries.length > 0 ? (
                  <dl className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:grid-cols-2 lg:grid-cols-3">
                    {fieldEntries.map(([k, v]) => {
                      const corrected = ext.reviewer_corrected_fields && k in ext.reviewer_corrected_fields;
                      return (
                        <div key={k} className="text-xs">
                          <dt className="flex items-center gap-1.5 font-medium text-slate-500">
                            <span>{k}</span>
                            {corrected && <Badge tone="brand">Corrected</Badge>}
                          </dt>
                          <dd className="mt-0.5 font-mono text-sm text-slate-900">{String(v)}</dd>
                        </div>
                      );
                    })}
                  </dl>
                ) : (
                  <p className="text-xs text-slate-500">No structured fields extracted yet.</p>
                )}

                {ext.missing_fields.length > 0 && (
                  <p className="text-xs text-amber-700">
                    Missing expected fields: <span className="font-mono">{ext.missing_fields.join(", ")}</span>
                  </p>
                )}
                {ext.ai_explanation && (
                  <p className="text-xs text-slate-600">
                    <Cpu className="mr-1 inline h-3.5 w-3.5 text-slate-400" aria-hidden />
                    {ext.ai_explanation}
                  </p>
                )}
                {showOcr && ext.raw_ocr_text_masked && (
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-900 p-3 text-xs text-slate-100">
                    {ext.raw_ocr_text_masked}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Cross-document consistency & verification checks"
          description="Origin tags distinguish deterministic rules, live public directories, sandbox fixtures, and unconfigured integrations."
        />
        <div className="divide-y divide-slate-200">
          {checks.map((chk: VerificationCheck) => {
            const cb = CHECK_BADGE[chk.status] ?? { label: chk.status, tone: "neutral" as const };
            return (
              <div key={chk.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <CheckIcon status={chk.status} />
                    <span className="text-sm font-medium text-slate-900">{chk.check_type}</span>
                    {chk.target_doc_type && <Badge tone="neutral">{chk.target_doc_type}</Badge>}
                    <Badge tone={cb.tone}>{cb.label}</Badge>
                    {chk.is_simulated && <Badge tone="warning">SIMULATED SANDBOX</Badge>}
                  </div>
                  {chk.explanation && <p className="text-sm text-slate-600">{chk.explanation}</p>}
                  <p className="text-xs text-slate-500">
                    Origin: {ORIGIN_LABEL[chk.origin] ?? chk.origin}
                    {chk.provider_name && ` · Provider: ${chk.provider_name}`}
                    {chk.confidence != null && ` · Confidence: ${Math.round(chk.confidence * 100)}%`}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {corrections.length > 0 && (
        <Card>
          <CardHeader
            title="Reviewer field correction history"
            description="Immutable audit log of every reviewer correction made to extracted document fields."
          />
          <ul className="divide-y divide-slate-200 text-sm">
            {corrections.map((c) => (
              <li key={c.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <span className="inline-flex items-center gap-1.5 font-medium text-slate-900">
                    <History className="h-3.5 w-3.5 text-slate-400" />
                    <span className="font-mono">{c.field_name}</span>: {c.old_value ?? "(empty)"} →{" "}
                    <span className="text-brand-800">{c.new_value ?? "(cleared)"}</span>
                  </span>
                  <p className="text-xs text-slate-600">Reason: {c.reason}</p>
                </div>
                <span className="text-xs text-slate-500">{formatDateTime(c.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <RedactedImageDialog
        applicationId={report.application_id}
        documentId={redactedTarget?.documentId ?? null}
        docType={redactedTarget?.docType ?? null}
        onClose={() => setRedactedTarget(null)}
      />

      {canCorrectFields && (
        <FieldCorrectionDialog
          applicationId={report.application_id}
          extraction={editingExt}
          onClose={() => setEditingExt(null)}
          onUpdated={(next) => onReportChange?.(next)}
        />
      )}
    </div>
  );
}

function SummaryTile({
  label,
  value,
  hint,
  tone = "info",
}: {
  label: string;
  value: number;
  hint: string;
  tone?: "success" | "warning" | "neutral" | "info";
}) {
  const accent =
    tone === "success"
      ? "text-emerald-700"
      : tone === "warning"
        ? "text-amber-700"
        : tone === "neutral"
          ? "text-slate-600"
          : "text-brand-700";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${accent}`}>{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

function CheckIcon({ status }: { status: string }) {
  if (status === "PASSED") return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (status === "FAILED") return <ShieldAlert className="h-4 w-4 text-red-600" />;
  if (status === "WARN" || status === "NEEDS_INFO") return <AlertTriangle className="h-4 w-4 text-amber-600" />;
  if (status === "NOT_CONFIGURED") return <Info className="h-4 w-4 text-slate-400" />;
  return <ShieldCheck className="h-4 w-4 text-brand-600" />;
}
