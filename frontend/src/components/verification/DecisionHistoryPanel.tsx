"use client";

import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  Gavel,
  MessageSquare,
  RefreshCw,
  Scale,
  Send,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, Select } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  ApplicationAppeal,
  ApplicationDecision,
  ApplicationDecisionSummary,
  ApplicationDetail,
  RuleEvaluationItem,
  RuleExecution,
} from "@/lib/types";

const REASON_CODE_OPTIONS = [
  "REVIEWER_DISCRETION",
  "IMAGE_BLURRY",
  "IMAGE_GLARE",
  "IMAGE_CROPPED",
  "NAME_SPELLING_VARIANT",
  "NAME_MISMATCH",
  "DOB_MISMATCH",
  "BANK_NAME_MISMATCH",
  "FACE_MATCH_LOW",
  "UNDERAGE",
  "PAN_FORMAT_INVALID",
  "PAN_NOT_INDIVIDUAL",
  "EDU_NOT_ELIGIBLE",
  "ALREADY_REGISTERED",
];

function outcomeTone(outcome: string): "success" | "warning" | "danger" | "brand" | "neutral" {
  switch (outcome) {
    case "AUTO_PASS_ELIGIBLE":
      return "success";
    case "HUMAN_REVIEW":
      return "brand";
    case "NEEDS_MORE_INFO":
      return "warning";
    case "REJECT_RECOMMENDED":
      return "danger";
    default:
      return "neutral";
  }
}

function ruleStatusTone(status: RuleEvaluationItem["status"]): "success" | "warning" | "danger" | "brand" | "neutral" {
  switch (status) {
    case "PASS":
      return "success";
    case "FAIL":
      return "danger";
    case "HUMAN_REVIEW":
      return "brand";
    case "INFO":
      return "warning";
    default:
      return "neutral";
  }
}

export interface DecisionHistoryPanelProps {
  summary: ApplicationDecisionSummary | null;
  onRefresh: () => void | Promise<void>;
  onReapplied?: (child: ApplicationDetail) => void;
  canEvaluate?: boolean;
  canDecide?: boolean;
  canDecideEscalated?: boolean;
  isApplicantOwner?: boolean;
}

export function DecisionHistoryPanel({
  summary,
  onRefresh,
  onReapplied,
  canEvaluate = false,
  canDecide = false,
  canDecideEscalated = false,
  isApplicantOwner = false,
}: DecisionHistoryPanelProps) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Reviewer decision form state
  const [decision, setDecision] = useState<"APPROVE" | "NEEDS_MORE_INFO" | "REJECT" | "ESCALATE">("APPROVE");
  const [reasonCode, setReasonCode] = useState("REVIEWER_DISCRETION");
  const [reasonText, setReasonText] = useState("");

  // Applicant appeal & reapply state
  const [appealReason, setAppealReason] = useState("");
  const [appealNotes, setAppealNotes] = useState("");
  const [reapplyReason, setReapplyReason] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});

  // Notification sharing state
  const [copiedSms, setCopiedSms] = useState(false);
  const [notifNotice, setNotifNotice] = useState<string | null>(null);

  if (!summary) {
    return (
      <Card>
        <CardHeader
          title="Policy rules & decision engine"
          description="Deterministic eligibility, document completeness, consistency, and human-override history."
        />
        <div className="p-5 text-sm text-slate-600">Loading rule evaluation history…</div>
      </Card>
    );
  }

  const latest = summary.latest_execution;
  const openAppeal = summary.appeals.find((a) => a.status === "OPEN");
  const isDraftOrWithdrawn = summary.application_status === "DRAFT" || summary.application_status === "WITHDRAWN";
  const hasNameMismatch = latest?.reason_codes.includes("NAME_MISMATCH") ?? false;
  const isStatutoryReject = latest?.outcome === "REJECT_RECOMMENDED";

  async function runEvaluate() {
    if (!summary) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const res = await api<RuleExecution>(`/applications/${summary.application_id}/evaluate`, {
        method: "POST",
        body: { apply_transition: true, trigger_source: "MANUAL_EVALUATE" },
      });
      setNotice(`Evaluated against Ruleset v${res.ruleset_version}: ${res.outcome} → ${res.recommended_status}.`);
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to evaluate deterministic rules.");
    } finally {
      setBusy(false);
    }
  }

  async function submitDecision(e: React.FormEvent) {
    e.preventDefault();
    if (!summary) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const res = await api<ApplicationDecision>(`/applications/${summary.application_id}/decide`, {
        method: "POST",
        body: {
          decision,
          reason_codes: [reasonCode],
          reason_text: reasonText.trim(),
          rework_items: [],
        },
      });
      setReasonText("");
      setNotice(
        `Decision recorded: ${res.decision} (${res.previous_status} → ${res.new_status})${res.is_override ? " [Override]" : ""}.`,
      );
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to record decision.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitAppeal(e: React.FormEvent) {
    e.preventDefault();
    if (!summary) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      await api<ApplicationAppeal>(`/applications/${summary.application_id}/appeal`, {
        method: "POST",
        body: {
          appeal_reason: appealReason.trim(),
          supporting_notes: appealNotes.trim() || null,
        },
      });
      setAppealReason("");
      setAppealNotes("");
      setNotice("Formal appeal submitted for Senior Reviewer evaluation.");
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Unable to submit appeal.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReapply(e: React.FormEvent) {
    e.preventDefault();
    if (!summary) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const child = await api<ApplicationDetail>(`/applications/${summary.application_id}/reapply`, {
        method: "POST",
        body: { reason: reapplyReason.trim() },
      });
      setReapplyReason("");
      setNotice(`Started new linked reapplication ${child.reference_code}.`);
      if (onReapplied) {
        onReapplied(child);
      } else {
        await onRefresh();
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Unable to start reapplication.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResolveAppeal(appealId: string, resolution: "UPHOLD_REJECTION" | "REOPEN_FOR_REVIEW" | "APPROVE_KYC") {
    if (!summary) return;
    const notes = (resolutionNotes[appealId] ?? "").trim();
    if (notes.length < 10) {
      setErr("Enter at least 10 characters explaining the appeal resolution.");
      return;
    }
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      await api<ApplicationAppeal>(`/applications/${summary.application_id}/appeals/${appealId}/resolve`, {
        method: "POST",
        body: { resolution, resolution_notes: notes },
      });
      setNotice(`Appeal resolved (${resolution}).`);
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Unable to resolve appeal.");
    } finally {
      setBusy(false);
    }
  }

  function handleShareWhatsApp() {
    if (!summary || !latest || latest.rework_items.length === 0) return;
    const origin = typeof window !== "undefined" ? window.location.origin : "https://policynest-frontend-production.up.railway.app";
    const fixUrl = `${origin}/app/onboarding/${summary.application_id}?step=5`;
    const message = [
      `📋 *PolicyNest POSP Onboarding Correction Request*`,
      `Application Ref: *${summary.application_id.slice(0, 8).toUpperCase()}*`,
      ``,
      `Dear Candidate,`,
      `To complete your POSP appointment, please update the following document(s):`,
      ``,
      ...latest.rework_items.map(
        (it, idx) =>
          `${idx + 1}. *${it.title_en}* (${it.title_hi})\n   👉 Action: ${it.action_en}\n   👉 कार्य: ${it.action_hi}`
      ),
      ``,
      `🔗 *Upload replacement directly:*`,
      fixUrl,
      ``,
      `⏱️ _Please complete your upload within 24 hours._`,
    ].join("\n");

    const waUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(waUrl, "_blank", "noopener,noreferrer");
    setNotifNotice("Bilingual WhatsApp notification opened in WhatsApp.");
    setTimeout(() => setNotifNotice(null), 4000);
  }

  function handleCopySms() {
    if (!summary) return;
    const origin = typeof window !== "undefined" ? window.location.origin : "https://policynest-frontend-production.up.railway.app";
    const fixUrl = `${origin}/app/onboarding/${summary.application_id}?step=5`;
    const sms = `PolicyNest Alert: Action required for your POSP onboarding. Please update your document(s) at ${fixUrl} to proceed with verification.`;
    void navigator.clipboard.writeText(sms);
    setCopiedSms(true);
    setNotifNotice("Compact 160-char SMS text copied to clipboard.");
    setTimeout(() => {
      setCopiedSms(false);
      setNotifNotice(null);
    }, 3000);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Deterministic Rules & Decision Engine"
          description={`Active rulebook v${summary.active_ruleset_version} · Rework cycles: ${summary.rework_count}${summary.resolution_kind ? ` · Track: ${summary.resolution_kind}` : ""}`}
          action={
            canEvaluate && !isDraftOrWithdrawn ? (
              <Button type="button" size="sm" variant="secondary" loading={busy} onClick={runEvaluate}>
                <RefreshCw className="h-3.5 w-3.5" /> Re-evaluate rules
              </Button>
            ) : undefined
          }
        />

        <div className="space-y-5 p-5">
          {err && <Alert tone="error">{err}</Alert>}
          {notice && <Alert tone="success">{notice}</Alert>}

          {!latest ? (
            <Alert tone="info" title="Rules not evaluated yet">
              Deterministic rules run automatically on submission or when triggered by a reviewer.
            </Alert>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={outcomeTone(latest.outcome)}>{latest.outcome}</Badge>
                    <Badge tone="neutral">Recommended → {latest.recommended_status}</Badge>
                    <Badge tone="neutral">Ruleset v{latest.ruleset_version}</Badge>
                    {latest.auto_pass_eligible && <Badge tone="success">Auto-pass eligible</Badge>}
                    {latest.requires_human_review && <Badge tone="brand">Human review required</Badge>}
                  </div>
                  <p className="text-sm font-medium text-slate-900">{latest.summary}</p>
                  <p className="text-xs text-slate-500">
                    Executed {formatDateTime(latest.executed_at)} ({latest.trigger_source}) · Eligibility:{" "}
                    <strong>{latest.eligibility_status}</strong> · Completeness:{" "}
                    <strong>{latest.completeness_status}</strong> · Consistency:{" "}
                    <strong>{latest.consistency_status}</strong> · Risk: <strong>{latest.risk_level}</strong>
                  </p>
                </div>
              </div>

              {hasNameMismatch && (
                <Alert tone="warning" title="Non-auto-reject identity guardrail active">
                  Tier 7 name divergence (<code>NAME_MISMATCH</code>) is strictly routed to human confirmation by a
                  Senior Reviewer and can never trigger automatic rejection.
                </Alert>
              )}

              {latest.risk_indicators.some((rk) => rk.code.startsWith("ANOMALY_") || rk.code === "REPEATED_REWORK_ESCALATION") && (
                <div className="rounded-xl border border-red-300 bg-red-50 p-4">
                  <div className="flex items-start gap-3">
                    <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
                    <div className="space-y-1">
                      <h4 className="text-sm font-bold text-red-900">
                        Cross-Application Fraud Ring &amp; Identity Guardrail Triggered
                      </h4>
                      <p className="text-xs text-red-800">
                        Deterministic intelligence detected cross-application identity or document collisions
                        (reused document hashes, shared bank accounts, or repeated rework cycles).
                        Auto-approval is quarantined and this file is routed exclusively to Senior Compliance &amp; Fraud Desk review.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {notifNotice && <Alert tone="success">{notifNotice}</Alert>}

              {latest.rework_items.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-950">
                      <AlertTriangle className="h-4 w-4 text-amber-700" />
                      Consolidated Rework Checklist ({latest.rework_items.length})
                    </h3>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={handleShareWhatsApp}
                        className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-emerald-600 px-3 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
                        title="Share bilingual rework checklist directly via WhatsApp"
                      >
                        <MessageSquare className="h-3.5 w-3.5" /> 📱 WhatsApp Candidate
                      </button>
                      <button
                        type="button"
                        onClick={handleCopySms}
                        className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                        title="Copy compact 160-char SMS text to clipboard"
                      >
                        {copiedSms ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                        {copiedSms ? "Copied!" : "Copy SMS"}
                      </button>
                      {isApplicantOwner && summary.application_status === "NEEDS_MORE_INFO" && (
                        <Link
                          href={`/app/onboarding/${summary.application_id}?step=5`}
                          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-amber-700 px-3 text-xs font-semibold text-white hover:bg-amber-800"
                        >
                          Fix &amp; resubmit in-place (Correction) <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      )}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {latest.rework_items.map((item, idx) => (
                      <div key={`${item.reason_code}-${item.doc_type ?? idx}`} className="rounded-lg border border-amber-200 bg-white p-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <span className="font-semibold text-slate-900">{item.title_en}</span>
                          <Badge tone="warning">{item.doc_type || item.reason_code}</Badge>
                        </div>
                        <p className="mt-1 text-xs text-slate-700">{item.action_en}</p>
                        <div className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-600">
                          <p className="font-medium text-slate-800">{item.title_hi}</p>
                          <p>{item.action_hi}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {latest.risk_indicators.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Indicators</h3>
                  <div className="grid gap-2 md:grid-cols-2">
                    {latest.risk_indicators.map((rk, i) => (
                      <div
                        key={`${rk.code}-${i}`}
                        className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700"
                      >
                        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                        <div>
                          <span className="font-semibold text-slate-900">
                            {rk.code} ({rk.level})
                          </span>
                          <p>{rk.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Rule Breakdown ({latest.rule_results.length} rules evaluated)
                </h3>
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200">
                  {latest.rule_results.map((r) => (
                    <div key={r.rule_id} className="flex flex-wrap items-start justify-between gap-2 px-4 py-2.5 text-sm">
                      <div className="max-w-3xl">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-900">{r.name}</span>
                          <span className="text-xs text-slate-400">{r.rule_id}</span>
                          {r.reason_code && <Badge tone="neutral">{r.reason_code}</Badge>}
                        </div>
                        <p className="mt-0.5 text-xs text-slate-600">{r.explanation}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Badge tone="neutral">{r.category}</Badge>
                        <Badge tone={ruleStatusTone(r.status)}>{r.status}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {canDecide && !isDraftOrWithdrawn && (
            <form onSubmit={submitDecision} className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Gavel className="h-4 w-4 text-brand-700" />
                  Reviewer Decision &amp; Override Controls
                </h3>
                {!canDecideEscalated && (hasNameMismatch || isStatutoryReject || summary.application_status === "REJECTED") && (
                  <Badge tone="warning">Senior Reviewer required for override — use ESCALATE</Badge>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Decision action" htmlFor="dec-action">
                  <Select
                    id="dec-action"
                    value={decision}
                    onChange={(e) => setDecision(e.target.value as typeof decision)}
                  >
                    <option value="APPROVE">APPROVE (KYC_APPROVED)</option>
                    <option value="NEEDS_MORE_INFO">NEEDS_MORE_INFO (Correction Rework)</option>
                    <option value="ESCALATE">ESCALATE (Route to Senior / Fraud Desk)</option>
                    <option value="REJECT">REJECT (REJECTED)</option>
                  </Select>
                </Field>
                <Field label="Canonical reason code" htmlFor="dec-code">
                  <Select id="dec-code" value={reasonCode} onChange={(e) => setReasonCode(e.target.value)}>
                    {REASON_CODE_OPTIONS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>

              <Field
                label="Mandatory justification / audit reason"
                htmlFor="dec-reason"
                hint="Minimum 10 characters. Every approval, rejection, rework, or override is logged in audit_logs."
              >
                <Input
                  id="dec-reason"
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                  placeholder="State verification evidence or override justification…"
                  minLength={10}
                  required
                />
              </Field>

              <div className="flex justify-end">
                <Button type="submit" loading={busy} disabled={reasonText.trim().length < 10}>
                  Record reviewer decision
                </Button>
              </div>
            </form>
          )}

          {isApplicantOwner && summary.application_status === "REJECTED" && (
            <div className="grid gap-4 lg:grid-cols-2">
              <form onSubmit={handleSubmitAppeal} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Scale className="h-4 w-4 text-brand-700" />
                  Path A: File Formal Appeal
                </h3>
                <p className="text-xs text-slate-600">
                  Use this if you believe the rejection decision was made in error on existing records. A Senior
                  Reviewer will inspect your appeal.
                </p>
                {openAppeal ? (
                  <Alert tone="info">An appeal ({openAppeal.id.slice(0, 8)}) is currently OPEN and awaiting review.</Alert>
                ) : (
                  <>
                    <Field label="Appeal explanation" htmlFor="appeal-reason">
                      <Input
                        id="appeal-reason"
                        value={appealReason}
                        onChange={(e) => setAppealReason(e.target.value)}
                        placeholder="Explain why the rejection should be reconsidered…"
                        minLength={15}
                        required
                      />
                    </Field>
                    <Field label="Supporting context (optional)" htmlFor="appeal-notes">
                      <Input
                        id="appeal-notes"
                        value={appealNotes}
                        onChange={(e) => setAppealNotes(e.target.value)}
                        placeholder="Any reference ID or document clarification…"
                      />
                    </Field>
                    <Button type="submit" size="sm" loading={busy} disabled={appealReason.trim().length < 15}>
                      Submit formal appeal
                    </Button>
                  </>
                )}
              </form>

              <form onSubmit={handleReapply} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <CheckCircle2 className="h-4 w-4 text-emerald-700" />
                  Path B: Start New Linked Reapplication
                </h3>
                <p className="text-xs text-slate-600">
                  Creates a fresh application draft linked to this rejected record so you can supply updated eligibility
                  details and fresh documents.
                </p>
                {openAppeal ? (
                  <Alert tone="warning">Wait until your active appeal is resolved before starting a reapplication.</Alert>
                ) : (
                  <>
                    <Field label="Reason for reapplying" htmlFor="reapply-reason">
                      <Input
                        id="reapply-reason"
                        value={reapplyReason}
                        onChange={(e) => setReapplyReason(e.target.value)}
                        placeholder="Describe what changed (e.g., Individual PAN, completed Class 10)…"
                        minLength={10}
                        required
                      />
                    </Field>
                    <Button type="submit" variant="secondary" size="sm" loading={busy} disabled={reapplyReason.trim().length < 10}>
                      Create linked reapplication draft
                    </Button>
                  </>
                )}
              </form>
            </div>
          )}

          {summary.appeals.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Appeals ({summary.appeals.length})
              </h3>
              {summary.appeals.map((ap) => (
                <div key={ap.id} className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-slate-900">Appeal filed {formatDateTime(ap.created_at)}</span>
                    <Badge tone={ap.status === "APPROVED" ? "success" : ap.status === "OPEN" ? "brand" : "danger"}>
                      {ap.status}
                    </Badge>
                  </div>
                  <p className="text-slate-700">{ap.appeal_reason}</p>
                  {ap.supporting_notes && <p className="text-xs text-slate-500">Notes: {ap.supporting_notes}</p>}
                  {ap.resolution_notes && (
                    <div className="rounded-lg bg-slate-50 p-2.5 text-xs text-slate-700">
                      <strong>Resolution:</strong> {ap.resolution_notes}
                    </div>
                  )}
                  {ap.status === "OPEN" && canDecideEscalated && (
                    <div className="space-y-2 border-t border-slate-100 pt-3">
                      <Input
                        aria-label="Appeal resolution notes"
                        value={resolutionNotes[ap.id] ?? ""}
                        onChange={(e) => setResolutionNotes((prev) => ({ ...prev, [ap.id]: e.target.value }))}
                        placeholder="Senior Reviewer resolution explanation (min 10 chars)…"
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="primary" loading={busy} onClick={() => handleResolveAppeal(ap.id, "APPROVE_KYC")}>
                          Approve KYC
                        </Button>
                        <Button size="sm" variant="secondary" loading={busy} onClick={() => handleResolveAppeal(ap.id, "REOPEN_FOR_REVIEW")}>
                          Reopen for review
                        </Button>
                        <Button size="sm" variant="danger" loading={busy} onClick={() => handleResolveAppeal(ap.id, "UPHOLD_REJECTION")}>
                          Uphold rejection
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {summary.decisions.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Human Decision &amp; Override Audit ({summary.decisions.length})
              </h3>
              <div className="divide-y divide-slate-100 rounded-xl border border-slate-200">
                {summary.decisions.map((d) => (
                  <div key={d.id} className="space-y-1 px-4 py-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={d.decision === "APPROVE" ? "success" : d.decision === "REJECT" ? "danger" : "warning"}>
                          {d.decision}
                        </Badge>
                        <span className="font-medium text-slate-900">
                          {d.previous_status} → {d.new_status}
                        </span>
                        <Badge tone="neutral">{d.decided_by_role}</Badge>
                        {d.is_override && <Badge tone="brand">Override</Badge>}
                      </div>
                      <span className="text-xs text-slate-500">{formatDateTime(d.created_at)}</span>
                    </div>
                    <p className="text-xs text-slate-700">{d.reason_text}</p>
                    <p className="text-[11px] text-slate-400">Codes: {d.reason_codes.join(", ")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary.execution_history.length > 1 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Rule Execution History ({summary.execution_history.length} runs)
              </h3>
              <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 text-xs">
                {summary.execution_history.map((ex) => (
                  <div key={ex.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-3.5 w-3.5 text-slate-400" />
                      <span className="font-medium text-slate-800">v{ex.ruleset_version}</span>
                      <Badge tone={outcomeTone(ex.outcome)}>{ex.outcome}</Badge>
                      <span className="text-slate-500">{ex.trigger_source}</span>
                    </div>
                    <span className="text-slate-500">{formatDateTime(ex.executed_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
