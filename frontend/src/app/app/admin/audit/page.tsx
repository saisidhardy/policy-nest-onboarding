"use client";

import { Download } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Button, Card, Input, PageHeader, Pagination, Select, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { AuditLog, Page } from "@/lib/types";
import { AuditTable } from "./AuditTable";

export default function AuditPage() {
  return (
    <RequirePermission permission="audit:read">
      <Suspense>
        <AuditLogView />
      </Suspense>
    </RequirePermission>
  );
}

function AuditLogView() {
  const params = useSearchParams();
  const router = useRouter();
  const filters = {
    action: params.get("action") ?? "",
    outcome: params.get("outcome") ?? "",
    actor: params.get("actor") ?? "",
    page: Number(params.get("page") ?? 1),
  };
  const [draft, setDraft] = useState(filters);
  const [data, setData] = useState<Page<AuditLog> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = params.toString();

  useEffect(() => {
    const ctrl = new AbortController();
    setData(null);
    api<Page<AuditLog>>("/admin/audit-logs", {
      query: { action: filters.action, outcome: filters.outcome, actor: filters.actor, page: filters.page },
      signal: ctrl.signal,
    }).then(setData, (e) => {
      if (e?.name !== "AbortError") setError(e instanceof ApiError ? e.message : "Failed to load audit log.");
    });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  function apply(next: Partial<typeof filters>) {
    const merged = { ...filters, ...next };
    const qs = new URLSearchParams();
    Object.entries(merged).forEach(([k, v]) => {
      if (v && !(k === "page" && v === 1)) qs.set(k, String(v));
    });
    router.push(`/app/admin/audit${qs.toString() ? `?${qs}` : ""}`);
  }

  return (
    <>
      <PageHeader title="Audit log" description="Append-only record of authentication, authorisation and administrative events. Entries cannot be edited or deleted." />
      <Card>
        <form
          className="flex flex-wrap items-end gap-3 border-b border-slate-100 px-5 py-4"
          onSubmit={(e) => {
            e.preventDefault();
            apply({ ...draft, page: 1 });
          }}
        >
          <div className="w-48">
            <label htmlFor="f-action" className="mb-1 block text-xs font-medium text-slate-600">Action starts with</label>
            <Input id="f-action" placeholder="auth.login" value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })} />
          </div>
          <div className="w-56">
            <label htmlFor="f-actor" className="mb-1 block text-xs font-medium text-slate-600">Actor email</label>
            <Input id="f-actor" value={draft.actor} onChange={(e) => setDraft({ ...draft, actor: e.target.value })} />
          </div>
          <div className="w-40">
            <label htmlFor="f-outcome" className="mb-1 block text-xs font-medium text-slate-600">Outcome</label>
            <Select id="f-outcome" value={draft.outcome} onChange={(e) => setDraft({ ...draft, outcome: e.target.value })}>
              <option value="">Any</option>
              <option value="SUCCESS">Success</option>
              <option value="FAILURE">Failure</option>
              <option value="DENIED">Denied</option>
            </Select>
          </div>
          <Button type="submit">Filter</Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setDraft({ action: "", outcome: "", actor: "", page: 1 });
              router.push("/app/admin/audit");
            }}
          >
            Clear
          </Button>
          <div className="ml-auto">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                const qs = new URLSearchParams();
                if (draft.action) qs.set("action", draft.action);
                if (draft.outcome) qs.set("outcome", draft.outcome);
                if (draft.actor) qs.set("actor", draft.actor);
                window.open(`/api/v1/admin/audit-logs/export?${qs.toString()}`, "_blank");
              }}
            >
              <Download className="h-4 w-4" /> Export Regulatory CSV
            </Button>
          </div>
        </form>
        {error && <Alert tone="error" className="m-5">{error}</Alert>}
        {!data ? (
          <Spinner />
        ) : (
          <>
            <AuditTable items={data.items} />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => apply({ page: p })} />
          </>
        )}
      </Card>
    </>
  );
}
