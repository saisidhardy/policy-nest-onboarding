"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  FileUp,
  History,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader } from "@/components/ui";
import { api, apiForm, ApiError } from "@/lib/api";
import { extractAutofillFromReport } from "@/lib/autofill";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { normalizeAndOptimizeImage } from "@/lib/imagePrep";
import type {
  ApplicationDetail,
  ApplicationDocument,
  ApplicationVerificationReport,
  DocumentExtraction,
  DocumentType,
} from "@/lib/types";
import { DocumentPreviewModal } from "./DocumentPreviewModal";
import { GuidedDocumentCapture } from "./GuidedDocumentCapture";
import { SelfieCameraCapture } from "./SelfieCameraCapture";

const QUALITY_META: Record<string, { label: string; tone: "success" | "warning" | "danger" }> = {
  OK: { label: "Quality OK", tone: "success" },
  IMAGE_BLURRY: { label: "Blurry image", tone: "danger" },
  IMAGE_GLARE: { label: "Glare detected", tone: "warning" },
  IMAGE_CROPPED: { label: "Edges cropped", tone: "warning" },
  LOW_RESOLUTION: { label: "Low resolution", tone: "danger" },
  FACE_NOT_DETECTED: { label: "No face detected", tone: "danger" },
  UNREADABLE: { label: "Unreadable / blank", tone: "danger" },
};

export function DocumentsStep({
  application,
  onReload,
  onApplyAutofill,
  onBack,
  onContinue,
}: {
  application: ApplicationDetail;
  onReload: () => Promise<void>;
  onApplyAutofill?: (patch: Record<string, unknown>, targetStep?: number) => Promise<void>;
  onBack: () => void;
  onContinue: () => void;
}) {
  const { t } = useI18n();
  const [busyType, setBusyType] = useState<DocumentType | null>(null);
  const [uploadStage, setUploadStage] = useState<string | null>(null);
  const [uploadPercent, setUploadPercent] = useState<number>(0);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [autofillLoading, setAutofillLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slotError, setSlotError] = useState<{ docType: DocumentType; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<ApplicationDocument | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [precheckLoading, setPrecheckLoading] = useState(false);
  const [precheck, setPrecheck] = useState<ApplicationVerificationReport | null>(null);

  const byType = new Map<DocumentType, ApplicationDocument>();
  for (const doc of application.documents) {
    if (doc.is_current) byType.set(doc.doc_type, doc);
  }
  const previousVersions = application.document_history.filter((d) => !d.is_current);

  const loadVerification = useCallback(async () => {
    try {
      const report = await api<ApplicationVerificationReport>(`/applications/${application.id}/verification`);
      setPrecheck(report);
    } catch {
      // Verification report may not exist yet for a brand-new empty draft
    }
  }, [application.id]);

  useEffect(() => {
    if (application.documents.length > 0) {
      void loadVerification();
    }
  }, [application.documents.length, loadVerification]);

  const extractionByType = new Map<string, DocumentExtraction>();
  for (const ext of precheck?.extractions ?? []) {
    extractionByType.set(ext.doc_type, ext);
  }

  async function runPrecheck() {
    setPrecheckLoading(true);
    setError(null);
    setNotice(null);
    try {
      const report = await api<ApplicationVerificationReport>(`/applications/${application.id}/process`, {
        method: "POST",
      });
      setPrecheck(report);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to run document pre-check.");
    } finally {
      setPrecheckLoading(false);
    }
  }

  async function uploadFile(docType: DocumentType, rawFile: File) {
    setBusyType(docType);
    setError(null);
    setSlotError(null);
    setNotice(null);
    setUploadPercent(15);
    setUploadStage(t.docs.uploadStage1);
    const timers = [
      setTimeout(() => {
        setUploadPercent(45);
        setUploadStage(t.docs.uploadStage2);
      }, 400),
      setTimeout(() => {
        setUploadPercent(75);
        setUploadStage(t.docs.uploadStage3);
      }, 1200),
      setTimeout(() => {
        setUploadPercent(90);
        setUploadStage(t.docs.uploadStage4);
      }, 2300),
    ];
    try {
      const prepared = await normalizeAndOptimizeImage(rawFile);
      const fd = new FormData();
      fd.append("file", prepared.file);
      const uploaded = await apiForm<ApplicationDocument>(`/applications/${application.id}/documents/${docType}`, fd);
      setUploadPercent(100);
      await onReload();
      await loadVerification();

      const ext = uploaded.extraction;
      if (prepared.qualityWarning && (!ext || ext.quality_status === "OK")) {
        setNotice(`⚡ Camera Quality Advisory: ${prepared.qualityWarning}`);
      }
      if (ext && ext.quality_status !== "OK") {
        const msg = `${uploaded.original_filename}: Quality check flagged "${QUALITY_META[ext.quality_status]?.label ?? ext.quality_status}". ${prepared.qualityWarning ?? "Upload a clearer copy."}`;
        setError(msg);
        setSlotError({ docType, message: msg });
      } else if (
        ext &&
        ext.classification_match === false &&
        ext.predicted_doc_type &&
        ext.predicted_doc_type !== "UNKNOWN"
      ) {
        const msg = `Uploaded ${uploaded.original_filename} (v${uploaded.version}), but it appears to be ${ext.predicted_doc_type} instead of ${docType}. Verify you uploaded to the right slot.`;
        setError(msg);
        setSlotError({ docType, message: msg });
      } else if (ext && ext.ocr_engine === "OCR_UNAVAILABLE") {
        setNotice(
          `Uploaded ${uploaded.original_filename} (v${uploaded.version}) — Quality OK. Automated text OCR requires GEMINI_API_KEY or HTTP OCR configured on the server.`,
        );
      } else {
        const extractedCount = ext ? Object.keys(ext.effective_fields || {}).length : 0;
        setNotice(
          `Uploaded ${uploaded.original_filename} (v${uploaded.version}) — Quality OK${extractedCount > 0 ? `, extracted ${extractedCount} field(s)` : ""}.`,
        );
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Document upload failed.";
      setError(msg);
      setSlotError({ docType, message: msg });
    } finally {
      timers.forEach(clearTimeout);
      setBusyType(null);
      setUploadStage(null);
      setUploadPercent(0);
    }
  }

  async function removeDoc(doc: ApplicationDocument) {
    setRemovingId(doc.id);
    setError(null);
    setNotice(null);
    try {
      await api(`/applications/${application.id}/documents/${doc.id}`, { method: "DELETE" });
      await onReload();
      await loadVerification();
      setNotice(`Removed ${doc.original_filename} from draft.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove document.");
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Step 5: Document upload centre"
          description={`Upload all 6 required documents (${application.completeness.uploaded_document_count}/6 uploaded). Files are stored privately and validated server-side.`}
          action={
            previousVersions.length > 0 && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowHistory((v) => !v)}>
                <History className="h-4 w-4" />
                {showHistory ? "Hide history" : `Version history (${previousVersions.length})`}
              </Button>
            )
          }
        />
        <div className="space-y-4 px-5 py-5">
          {error && <Alert tone="error">{error}</Alert>}
          {notice && <Alert tone="success">{notice}</Alert>}

          {(() => {
            const autofill = extractAutofillFromReport(application, precheck);
            if (!onApplyAutofill || autofill.appliedFields.length === 0) return null;
            return (
              <div className="rounded-xl border border-brand-200 bg-brand-50/70 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-brand-900">
                      <Wand2 className="h-4 w-4 text-brand-700" />
                      Document-first auto-fill ready ({autofill.appliedFields.length} empty fields detected)
                    </p>
                    <p className="mt-1 text-xs text-brand-800">
                      We extracted verified details from your uploaded documents. Apply them to your form in one click—nothing existing is overwritten.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      loading={autofillLoading}
                      onClick={async () => {
                        setAutofillLoading(true);
                        setError(null);
                        try {
                          await onApplyAutofill(autofill.patch);
                          setNotice(`Auto-filled ${autofill.appliedFields.length} fields from your uploaded documents.`);
                        } finally {
                          setAutofillLoading(false);
                        }
                      }}
                    >
                      <Wand2 className="h-3.5 w-3.5" /> Auto-fill empty fields
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      loading={autofillLoading}
                      onClick={async () => {
                        setAutofillLoading(true);
                        setError(null);
                        try {
                          await onApplyAutofill(autofill.patch, 1);
                        } finally {
                          setAutofillLoading(false);
                        }
                      }}
                    >
                      Auto-fill &amp; review Step 1
                    </Button>
                  </div>
                </div>
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {autofill.appliedFields.map((item) => (
                    <span
                      key={item.key}
                      className="rounded border border-brand-200 bg-white px-2 py-0.5 text-[11px] text-slate-700"
                    >
                      <strong className="text-slate-900">{item.label}:</strong> {String(item.value)}{" "}
                      <span className="text-slate-400">({item.source})</span>
                    </span>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* DPDP Act 2023 Explicit Consent and Data Protection Disclosure Card */}
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 shadow-xs">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
              <div>
                <p className="text-xs font-semibold text-emerald-950">{t.docs.dpdpNotice}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-emerald-900">{t.docs.dpdpClause}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {REQUIRED_DOCUMENTS.map((spec) => {
              const doc = byType.get(spec.type);
              const ext = extractionByType.get(spec.type);
              const isBusy = busyType === spec.type;
              const qMeta = ext
                ? (QUALITY_META[ext.quality_status] ?? { label: ext.quality_status, tone: "warning" as const })
                : null;
              const fieldPairs = Object.entries(ext?.effective_fields ?? {});

              const localizedLabels: Record<string, { label: string; desc: string }> = {
                PAN_CARD: { label: t.docs.pan, desc: t.docs.panDesc },
                AADHAAR_FRONT: { label: t.docs.aadhaarFront, desc: t.docs.aadhaarFrontDesc },
                AADHAAR_BACK: { label: t.docs.aadhaarBack, desc: t.docs.aadhaarBackDesc },
                CLASS_10_MARKSHEET: { label: t.docs.marksheet, desc: t.docs.marksheetDesc },
                BANK_DOCUMENT: { label: t.docs.cheque, desc: t.docs.chequeDesc },
                APPLICANT_SELFIE: { label: t.docs.selfie, desc: t.docs.selfieDesc },
              };
              const meta = localizedLabels[spec.type] ?? { label: spec.label, desc: spec.description };

              return (
                <div key={spec.type} className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4">
                  <div>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <h3 className="text-sm font-semibold text-slate-900">{meta.label}</h3>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {doc ? <Badge tone="success">Uploaded v{doc.version}</Badge> : <Badge tone="warning">Required</Badge>}
                        {qMeta && <Badge tone={qMeta.tone}>{qMeta.label}</Badge>}
                      </div>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-600">{meta.desc}</p>

                    {doc && (
                      <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-700">
                        <p className="truncate font-medium text-slate-900">{doc.original_filename}</p>
                        <p className="mt-0.5 text-slate-500">
                          {formatBytes(doc.file_size_bytes)} · SHA-256 <span className="font-mono">{doc.sha256_hash.slice(0, 12)}</span>
                        </p>
                        <p className="mt-0.5 text-slate-500">Uploaded {formatDateTime(doc.created_at)}</p>
                      </div>
                    )}

                    {ext && (
                      <div className="mt-2 space-y-1.5 rounded-lg border border-slate-200 bg-slate-50/70 p-2.5 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {ext.classification_match === true && (
                            <span className="inline-flex items-center gap-1 font-medium text-emerald-700">
                              <CheckCircle2 className="h-3.5 w-3.5" /> Type verified ({ext.predicted_doc_type})
                            </span>
                          )}
                          {ext.classification_match === false &&
                            ext.predicted_doc_type &&
                            ext.predicted_doc_type !== "UNKNOWN" && (
                              <span className="inline-flex items-center gap-1 font-medium text-amber-700">
                                <AlertTriangle className="h-3.5 w-3.5" /> Looks like {ext.predicted_doc_type}
                              </span>
                            )}
                          {ext.aadhaar_masked_applied && <Badge tone="brand">Aadhaar masked</Badge>}
                        </div>
                        {fieldPairs.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {fieldPairs.map(([k, v]) => (
                              <span
                                key={k}
                                className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-800"
                              >
                                {k}: {String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                        {ext.missing_fields.length > 0 && ext.ocr_engine !== "OCR_UNAVAILABLE" && (
                          <p className="text-[11px] text-amber-700">
                            Missing/unreadable fields: {ext.missing_fields.join(", ")}
                          </p>
                        )}
                        {ext.ocr_engine === "OCR_UNAVAILABLE" && (
                          <p className="text-[11px] text-slate-500">
                            Image quality checked ({ext.quality_status}). Text OCR requires GEMINI_API_KEY or external OCR configured.
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="mt-4 space-y-2">
                    {slotError?.docType === spec.type && (
                      <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                        {slotError.message}
                      </div>
                    )}

                    {isBusy && (
                      <div className="rounded-lg border border-blue-200 bg-blue-50/90 p-3 text-xs shadow-xs">
                        <div className="flex items-center justify-between font-medium text-blue-900">
                          <span className="flex items-center gap-1.5">
                            <Sparkles className="h-3.5 w-3.5 animate-spin text-blue-600" />
                            {uploadStage || t.docs.uploadStage1}
                          </span>
                          <span className="font-mono font-semibold text-blue-700">{uploadPercent}%</span>
                        </div>
                        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
                          <div
                            className="h-full bg-blue-600 transition-all duration-300 ease-out"
                            style={{ width: `${uploadPercent}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-2">
                      <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800 hover:bg-slate-50">
                        {doc ? <FileUp className="h-3.5 w-3.5" /> : <UploadCloud className="h-3.5 w-3.5" />}
                        {isBusy ? "Processing..." : doc ? t.docs.reuploadButton : t.docs.uploadButton}
                        <input
                          type="file"
                          accept={spec.accept}
                          disabled={isBusy}
                          className="sr-only"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            e.target.value = "";
                            if (file) void uploadFile(spec.type, file);
                          }}
                        />
                      </label>
                      {doc && (
                        <Button type="button" variant="secondary" size="sm" onClick={() => setPreviewDoc(doc)}>
                          <Eye className="h-3.5 w-3.5" /> {t.docs.previewButton}
                        </Button>
                      )}
                      {doc && application.status === "DRAFT" && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          loading={removingId === doc.id}
                          onClick={() => void removeDoc(doc)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-red-600" /> {t.docs.removeButton}
                        </Button>
                      )}
                    </div>
                    {spec.captureCamera ? (
                      <SelfieCameraCapture uploading={isBusy} onCapture={(file) => uploadFile(spec.type, file)} />
                    ) : (
                      <GuidedDocumentCapture
                        docLabel={spec.label}
                        uploading={isBusy}
                        onCapture={(file) => uploadFile(spec.type, file)}
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {showHistory && previousVersions.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Replaced document versions</p>
              <ul className="mt-2 divide-y divide-slate-200 text-xs">
                {previousVersions.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span>
                      <strong>{d.doc_type}</strong> v{d.version} · {d.original_filename} ({formatBytes(d.file_size_bytes)})
                    </span>
                    <div className="flex items-center gap-3 text-slate-500">
                      <span>{formatDateTime(d.created_at)}</span>
                      <button type="button" className="font-medium text-brand-700 hover:underline" onClick={() => setPreviewDoc(d)}>
                        View
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {precheck && (
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-slate-800">
                  Live verification &amp; cross-check summary: {precheck.summary.quality_passed}/{precheck.summary.documents_processed} documents passed quality inspection
                </p>
                <span className="text-slate-500">
                  {precheck.summary.checks_passed} passed · {precheck.summary.checks_warn + precheck.summary.checks_needs_info} warnings · {precheck.summary.checks_not_configured} govt/vendor APIs pending setup
                </span>
              </div>
              {precheck.checks.length > 0 && (
                <div className="grid gap-2 sm:grid-cols-2">
                  {precheck.checks.map((chk) => (
                    <div key={chk.id} className="rounded border border-slate-200 bg-white px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-slate-800">{chk.check_type}</span>
                        <Badge
                          tone={
                            chk.status === "PASSED"
                              ? "success"
                              : chk.status === "FAILED"
                                ? "danger"
                                : chk.status === "NOT_CONFIGURED"
                                  ? "neutral"
                                  : "warning"
                          }
                        >
                          {chk.status}
                        </Badge>
                      </div>
                      {chk.explanation && <p className="mt-1 text-[11px] text-slate-600">{chk.explanation}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
            <Button type="button" variant="secondary" onClick={onBack}>
              Back
            </Button>
            <div className="flex flex-wrap gap-2">
              {byType.size > 0 && (
                <Button type="button" variant="secondary" loading={precheckLoading} onClick={() => void runPrecheck()}>
                  <Sparkles className="h-4 w-4" /> Pre-check quality &amp; OCR
                </Button>
              )}
              <Button type="button" onClick={onContinue}>
                Continue to review
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <DocumentPreviewModal applicationId={application.id} document={previewDoc} onClose={() => setPreviewDoc(null)} />
    </>
  );
}
