"use client";

import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { Alert, Button, Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { ApplicationDetail, ApplicationSummary } from "@/lib/types";

export default function ApplicationsListPage() {
  return (
    <RequirePermission permission="application:read_own">
      <ApplicationsListView />
    </RequirePermission>
  );
}

function ApplicationsListView() {
  const { me } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<ApplicationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!me?.user.email_verified) {
      setItems([]);
      return;
    }
    api<ApplicationSummary[]>("/applications").then(setItems, (e) => {
      setError(e instanceof ApiError ? e.message : "Failed to load applications.");
      setItems([]);
    });
  }, [me?.user.email_verified]);

  async function startNew() {
    setCreating(true);
    setError(null);
    try {
      const created = await api<ApplicationDetail>("/applications", { method: "POST", body: {} });
      router.push(`/app/onboarding/${created.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start new application.");
      setCreating(false);
    }
  }

  const hasActive = items?.some((a) => a.status !== "WITHDRAWN" && a.status !== "REJECTED") ?? false;

  return (
    <>
      <PageHeader
        title="My applications"
        description="Track active drafts, submitted applications, and your onboarding history."
        action={
          me?.user.email_verified && !hasActive ? (
            <Button onClick={startNew} loading={creating}>
              <Plus className="h-4 w-4" /> Start application
            </Button>
          ) : undefined
        }
      />
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}
      {!me?.user.email_verified ? (
        <Alert tone="warning" title="Email verification required">
          Verify your email address to create and view onboarding applications.
        </Alert>
      ) : !items ? (
        <Spinner label="Loading applications" />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState title="No applications yet">
            <p className="mb-4">Start your POSP onboarding application to enter details and upload documents.</p>
            <Button onClick={startNew} loading={creating}>
              Start POSP application
            </Button>
          </EmptyState>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const editable = item.status === "DRAFT" || item.status === "NEEDS_MORE_INFO";
            return (
              <Card key={item.id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <p className="text-base font-semibold text-slate-900">{item.reference_code}</p>
                      <ApplicationStatusBadge status={item.status} />
                    </div>
                    <p className="text-xs text-slate-500">
                      {item.completeness.completed_sections}/{item.completeness.total_sections} sections ·{" "}
                      {item.completeness.uploaded_document_count}/{item.completeness.required_document_count} documents ·{" "}
                      Last saved {formatDateTime(item.last_saved_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={`/app/applications/${item.id}`}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 hover:bg-slate-50"
                    >
                      Track &amp; history
                    </Link>
                    {editable && (
                      <Link
                        href={`/app/onboarding/${item.id}`}
                        className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-700 px-3 text-sm font-medium text-white hover:bg-brand-800"
                      >
                        Resume step {item.current_step} <ArrowRight className="h-4 w-4" />
                      </Link>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
