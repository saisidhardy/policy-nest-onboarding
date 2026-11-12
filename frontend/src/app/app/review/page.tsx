"use client";

import { FileCheck2, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { Alert, Badge, Card, Input, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ApplicationSummary } from "@/lib/types";

export default function ReviewerQueuePage() {
  return (
    <RequirePermission permission="application:review">
      <ReviewerQueueInner />
    </RequirePermission>
  );
}

function ReviewerQueueInner() {
  const [items, setItems] = useState<ApplicationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    api<ApplicationSummary[]>("/applications").then(setItems, (e) => {
      setError(e instanceof ApiError ? e.message : "Failed to load regional applications.");
      setItems([]);
    });
  }, []);

  const filtered = useMemo(() => {
    if (!items) return [];
    const q = search.trim().toLowerCase();
    return items.filter((a) => {
      if (statusFilter !== "ALL" && a.status !== statusFilter) return false;
      if (!q) return true;
      return (
        a.reference_code.toLowerCase().includes(q) ||
        (a.full_name ?? "").toLowerCase().includes(q) ||
        (a.region ?? "").toLowerCase().includes(q)
      );
    });
  }, [items, search, statusFilter]);

  return (
    <>
      <PageHeader
        title="Document Intelligence Desk"
        description="Inspect OCR extractions, image quality metrics, masked Aadhaar previews, and correct extracted fields within your jurisdiction."
      />
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              aria-label="Search applications"
              placeholder="Search ref, name, region..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800"
          >
            <option value="ALL">All statuses</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="REWORK_SUBMITTED">Rework submitted</option>
            <option value="DRAFT">Draft</option>
          </select>
        </div>

        {!items ? (
          <div className="p-6">
            <Spinner label="Loading regional applications" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-10 text-center text-sm text-slate-600">
            <FileCheck2 className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 font-medium text-slate-800">No applications match your filter</p>
            <p className="mt-1 text-xs text-slate-500">Applications visible to your assigned region and clearance level appear here.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {filtered.map((app) => (
              <div key={app.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-slate-900">{app.reference_code}</span>
                    <ApplicationStatusBadge status={app.status} />
                    {app.region && <Badge tone="neutral">{app.region}</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{app.full_name || "Draft applicant"}</p>
                  <p className="text-xs text-slate-500">
                    {app.completeness.uploaded_document_count} / {app.completeness.required_document_count} docs ·{" "}
                    {app.submitted_at ? `Submitted ${formatDateTime(app.submitted_at)}` : `Saved ${formatDateTime(app.last_saved_at)}`}
                  </p>
                </div>
                <Link
                  href={`/app/review/${app.id}`}
                  className="inline-flex h-9 items-center justify-center rounded-lg border border-brand-700 bg-brand-700 px-3.5 text-sm font-medium text-white hover:bg-brand-800"
                >
                  Inspect verification
                </Link>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
