"use client";

import { Download, ExternalLink } from "lucide-react";
import { Alert, Button, Dialog, Spinner } from "@/components/ui";
import type { ApplicationDocument } from "@/lib/types";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { useEffect, useState } from "react";

export function DocumentPreviewModal({
  applicationId,
  document: doc,
  onClose,
}: {
  applicationId: string;
  document: ApplicationDocument | null;
  onClose: () => void;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!doc) {
      setBlobUrl(null);
      setError(null);
      return;
    }
    let active = true;
    let createdUrl: string | null = null;
    setLoading(true);
    setError(null);
    setBlobUrl(null);

    fetch(`/api/v1/applications/${applicationId}/documents/${doc.id}/content`, {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Unable to load file (HTTP ${res.status}).`);
        const blob = await res.blob();
        createdUrl = URL.createObjectURL(blob);
        if (active) setBlobUrl(createdUrl);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load preview.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [applicationId, doc]);

  const label = doc ? (REQUIRED_DOCUMENTS.find((d) => d.type === doc.doc_type)?.label ?? doc.doc_type) : "";
  const downloadHref = doc ? `/api/v1/applications/${applicationId}/documents/${doc.id}/content?download=1` : "#";

  return (
    <Dialog
      open={!!doc}
      onClose={onClose}
      title={label}
      description={doc ? `${doc.original_filename} · ${formatBytes(doc.file_size_bytes)} · Version ${doc.version}` : undefined}
    >
      <div className="space-y-4">
        {loading && <Spinner label="Loading secure document" />}
        {error && <Alert tone="error">{error}</Alert>}
        {blobUrl && doc && (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
            {doc.content_type === "application/pdf" ? (
              <iframe src={blobUrl} title={doc.original_filename} className="h-[60vh] w-full bg-white" />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={blobUrl} alt={doc.original_filename} className="mx-auto max-h-[60vh] w-auto object-contain" />
            )}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
          <div className="flex gap-2">
            {doc && (
              <a
                href={downloadHref}
                className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                <Download className="h-4 w-4" /> Download
              </a>
            )}
            {blobUrl && (
              <a
                href={blobUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" /> Open in tab
              </a>
            )}
          </div>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
