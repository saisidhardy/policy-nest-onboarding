"use client";

import { useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ReviewPortalTabs } from "@/components/review/ReviewPortalTabs";
import { Alert, Badge, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ReviewAnalytics } from "@/lib/types";

export default function OperationalAnalyticsPage() {
  return (
    <RequirePermission permission="analytics:read">
      <OperationalAnalyticsInner />
    </RequirePermission>
  );
}

function OperationalAnalyticsInner() {
  const { can } = useAuth();
  const [data, setData] = useState<ReviewAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<ReviewAnalytics>("/review/analytics").then(setData, (e) =>
      setError(e instanceof ApiError ? e.message : "Failed to load operational analytics."),
    );
  }, []);

  if (error) return <Alert tone="error">{error}</Alert>;
  if (!data) return <Spinner label="Aggregating operational metrics" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operational & Reviewer Productivity Analytics"
        description="Live PostgreSQL metrics scoped to your authorized region and clearance level."
      />
      {can("application:review") && <ReviewPortalTabs />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Submitted / Decided Pool" value={String(data.total_submitted_or_decided)} hint={`${data.open_appeals_count} open appeals · ${data.resolved_appeals_count} resolved`} />
        <MetricCard label="STP Auto-Pass Rate" value={`${data.stp_auto_pass_rate_pct}%`} hint="Evaluations qualifying for AUTO_PASS_ELIGIBLE" />
        <MetricCard label="Rework & Escalation Rates" value={`${data.rework_rate_pct}% / ${data.escalation_rate_pct}%`} hint={`${data.fraud_flagged_active_count} active fraud flags`} />
        <MetricCard
          label="Avg Turnaround (First Decision)"
          value={data.avg_turnaround_hours !== null ? `${data.avg_turnaround_hours} hrs` : "—"}
          hint="Submitted timestamp to first reviewer decision"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Application Status Distribution" />
          <div className="space-y-2.5 p-5 text-sm">
            {Object.entries(data.status_counts).length === 0 ? (
              <p className="text-slate-500">No applications recorded yet.</p>
            ) : (
              Object.entries(data.status_counts).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">{status}</span>
                  <Badge tone="neutral">{count}</Badge>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Latest Rule Engine Outcomes" />
          <div className="space-y-2.5 p-5 text-sm">
            {Object.entries(data.rule_outcome_counts).length === 0 ? (
              <p className="text-slate-500">No rule executions recorded yet.</p>
            ) : (
              Object.entries(data.rule_outcome_counts).map(([outcome, count]) => (
                <div key={outcome} className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">{outcome}</span>
                  <Badge tone="brand">{count}</Badge>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Reviewer Productivity & Override Breakdown"
          description="Decision, override, and OCR field-correction counts per authenticated reviewer."
        />
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2.5">Reviewer</th>
                <th className="px-4 py-2.5">Role</th>
                <th className="px-4 py-2.5">Decisions</th>
                <th className="px-4 py-2.5">Approvals</th>
                <th className="px-4 py-2.5">Rework</th>
                <th className="px-4 py-2.5">Rejects</th>
                <th className="px-4 py-2.5">Escalations</th>
                <th className="px-4 py-2.5">Overrides</th>
                <th className="px-4 py-2.5">OCR Corrections</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.reviewer_productivity.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-slate-500">
                    No reviewer decisions recorded yet.
                  </td>
                </tr>
              ) : (
                data.reviewer_productivity.map((r) => (
                  <tr key={r.user_id}>
                    <td className="px-4 py-2.5 font-medium text-slate-900">{r.full_name}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone="neutral">{r.role_code}</Badge>
                    </td>
                    <td className="px-4 py-2.5 font-semibold text-slate-900">{r.decisions_count}</td>
                    <td className="px-4 py-2.5 text-emerald-700">{r.approvals_count}</td>
                    <td className="px-4 py-2.5 text-amber-700">{r.rework_count}</td>
                    <td className="px-4 py-2.5 text-red-700">{r.rejections_count}</td>
                    <td className="px-4 py-2.5 text-slate-700">{r.escalations_count}</td>
                    <td className="px-4 py-2.5 text-brand-700">{r.overrides_count}</td>
                    <td className="px-4 py-2.5 text-slate-700">{r.field_corrections_count}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
    </Card>
  );
}
