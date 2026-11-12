"use client";

import { History } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ReviewPortalTabs } from "@/components/review/ReviewPortalTabs";
import { Alert, Badge, Button, Card, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ReviewHistoryPage } from "@/lib/types";

export default function ReviewHistoryPage() {
  return (
    <RequirePermission permission="application:review">
      <ReviewHistoryInner />
    </RequirePermission>
  );
}

function ReviewHistoryInner() {
  const [data, setData] = useState<ReviewHistoryPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mineOnly, setMineOnly] = useState(false);
  const [decisionFilter, setDecisionFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    try {
      const res = await api<ReviewHistoryPage>("/review/history", {
        query: {
          mine_only: mineOnly,
          decision: decisionFilter !== "ALL" ? decisionFilter : undefined,
          page,
          page_size: 25,
        },
      });
      setData(res);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load review history.");
    }
  }, [mineOnly, decisionFilter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Reviewer Decision History"
        description="Immutable log of authenticated reviewer approvals, rework requests, rejections, escalations, and overrides within your jurisdiction."
      />
      <ReviewPortalTabs />

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={mineOnly}
              onChange={(e) => {
                setMineOnly(e.target.checked);
                setPage(1);
              }}
              className="h-4 w-4 rounded border-slate-300 text-brand-700"
            />
            Show my decisions only
          </label>
          <select
            aria-label="Filter by decision"
            value={decisionFilter}
            onChange={(e) => {
              setDecisionFilter(e.target.value);
              setPage(1);
            }}
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800"
          >
            <option value="ALL">All decision actions</option>
            <option value="APPROVE">APPROVE</option>
            <option value="NEEDS_MORE_INFO">NEEDS_MORE_INFO</option>
            <option value="ESCALATE">ESCALATE</option>
            <option value="REJECT">REJECT</option>
          </select>
        </div>

        {!data ? (
          <div className="p-6">
            <Spinner label="Loading decision history" />
          </div>
        ) : data.items.length === 0 ? (
          <div className="px-6 py-10 text-center text-sm text-slate-600">
            <History className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 font-medium text-slate-800">No review decisions recorded yet</p>
          </div>
        ) : (
          <>
            <div className="divide-y divide-slate-200">
              {data.items.map((item) => (
                <div key={item.decision_id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/app/review/${item.application_id}`} className="font-mono text-sm font-semibold text-brand-700 hover:underline">
                        {item.reference_code}
                      </Link>
                      <Badge
                        tone={
                          item.decision === "APPROVE"
                            ? "success"
                            : item.decision === "REJECT"
                              ? "danger"
                              : "warning"
                        }
                      >
                        {item.decision}
                      </Badge>
                      <span className="text-xs font-medium text-slate-700">
                        {item.previous_status} → {item.new_status}
                      </span>
                      {item.is_override && <Badge tone="brand">Override</Badge>}
                      {item.region && <Badge tone="neutral">{item.region}</Badge>}
                    </div>
                    <p className="text-sm text-slate-800">{item.reason_text}</p>
                    <p className="text-xs text-slate-500">
                      By <strong>{item.decided_by_name}</strong> ({item.decided_by_role}) ·{" "}
                      {formatDateTime(item.created_at)} · Applicant: {item.applicant_name || "Unknown"} · Codes:{" "}
                      {item.reason_codes.join(", ")}
                    </p>
                  </div>
                  <Link
                    href={`/app/review/${item.application_id}`}
                    className="inline-flex h-8 shrink-0 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Inspect case
                  </Link>
                </div>
              ))}
            </div>

            {data.total > data.page_size && (
              <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-xs text-slate-600">
                <span>
                  Page {data.page} · {data.total} total decisions
                </span>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={data.page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={data.page * data.page_size >= data.total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
