"use client";

import { Eye, FileUp, History, Sparkles, Trash2, UploadCloud } from "lucide-react";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader } from "@/components/ui";
import { api, apiForm, ApiError } from "@/lib/api";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type {
  ApplicationDetail,
  ApplicationDocument,
  ApplicationVerificationReport,
  DocumentType,
} from "@/lib/types";
import { DocumentPreviewModal } from "./DocumentPreviewModal";
import { SelfieCameraCapture } from "./SelfieCameraCapture";

export function DocumentsStep({
  application,
  onReload,
  onBack,
  onContinue,
}: {
  application: ApplicationDetail;
  onReload: () => Promise<void>;
  onBack: () => void;
  onContinue: () => void;
}) {
  const [busyType, setBusyType] = useState<DocumentType | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  async function uploadFile(docType: DocumentType, file: File) {
    setBusyType(docType);
    setError(null);
    setNotice(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const uploaded = await apiForm<ApplicationDocument>(`/applications/${application.id}/documents/${docType}`, fd);
      await onReload();
      setNotice(`Uploaded ${uploaded.original_filename} (v${uploaded.version}).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Document upload failed.");
    } finally {
      setBusyType(null);
    }
  }

  async function removeDoc(doc: ApplicationDocument) {
    setRemovingId(doc.id);
    setError(null);
    setNotice(null);
    try {
      await api(`/applications/${application.id}/documents/${doc.id}`, { method: "DELETE" });
      await onReload();
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

          <div className="grid gap-4 md:grid-cols-2">
            {REQUIRED_DOCUMENTS.map((spec) => {
              const doc = byType.get(spec.type);
              const isBusy = busyType === spec.type;
              return (
                <div key={spec.type} className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4">
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-semibold text-slate-900">{spec.label}</h3>
                      {doc ? <Badge tone="success">Uploaded v{doc.version}</Badge> : <Badge tone="warning">Required</Badge>}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-600">{spec.description}</p>

                    {doc && (
                      <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-700">
                        <p className="truncate font-medium text-slate-900">{doc.original_filename}</p>
                        <p className="mt-0.5 text-slate-500">
                          {formatBytes(doc.file_size_bytes)} · SHA-256 <span className="font-mono">{doc.sha256_hash.slice(0, 12)}</span>
                        </p>
                        <p className="mt-0.5 text-slate-500">Uploaded {formatDateTime(doc.created_at)}</p>
                      </div>
                    )}
                  </div>

                  <div className="mt-4 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-800 hover:bg-slate-50">
                        {doc ? <FileUp className="h-3.5 w-3.5" /> : <UploadCloud className="h-3.5 w-3.5" />}
                        {isBusy ? "Uploading..." : doc ? "Replace file" : "Upload file"}
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
                          <Eye className="h-3.5 w-3.5" /> Preview
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
                          <Trash2 className="h-3.5 w-3.5 text-red-600" /> Remove
                        </Button>
                      )}
                    </div>
                    {spec.captureCamera && (
                      <SelfieCameraCapture uploading={isBusy} onCapture={(file) => uploadFile(spec.type, file)} />
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
            <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-slate-800">
                  Pre-check summary: {precheck.summary.quality_passed}/{precheck.summary.documents_processed} documents passed quality inspection
                </p>
                <span className="text-slate-500">Advisory check only</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {precheck.extractions.map((ext) => (
                  <div key={ext.id} className="flex items-center justify-between rounded border border-slate-200 bg-white px-3 py-2">
                    <span className="font-medium text-slate-800">{ext.doc_type}</span>
                    <Badge tone={ext.quality_status === "OK" ? "success" : "warning"}>{ext.quality_status}</Badge>
                  </div>
                ))}
              </div>
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
