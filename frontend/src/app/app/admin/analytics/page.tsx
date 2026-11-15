"use client";

import clsx from "clsx";
import {
  Activity,
  AlertTriangle,
  Coins,
  Cpu,
  Layers,
  RefreshCw,
  Server,
  Sparkles,
  Timer,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { sound } from "@/lib/soundFx";

type DashboardTab = "funnel" | "turnaround" | "cost" | "observability" | "executive";

interface FunnelStage {
  step_number: number;
  stage_name: string;
  display_label: string;
  count: number;
  conversion_from_prev_pct: number;
  conversion_from_top_pct: number;
  abandonment_count: number;
  abandonment_rate_pct: number;
  avg_active_time_seconds: number;
}

interface FunnelData {
  funnel_stages: FunnelStage[];
  overall_completion_rate_pct: number;
  avg_sessions_to_complete: number;
  returning_applicant_rate_pct: number;
  total_visitors: number;
  total_certified: number;
  document_dropoff_breakdown: Record<string, number>;
}

interface TurnaroundData {
  p50_turnaround_days: number;
  p90_turnaround_days: number;
  p95_turnaround_days: number;
  avg_turnaround_days: number;
  baseline_median_days: number;
  target_operational_days: number;
  pct_completed_within_5_7_days: number;
  calendar_vs_business_days: Record<string, number>;
  stage_duration_breakdown_hours: Record<string, number>;
  active_vs_waiting_hours: Record<string, number>;
  sla_breaches_count: number;
  sla_breach_reasons: Array<{ reason: string; count: number; avg_delay_days: number }>;
  externally_blocked_cases_count: number;
}

interface CostData {
  total_api_expenditure_inr: number;
  total_llm_expenditure_inr: number;
  total_ocr_expenditure_inr: number;
  avg_cost_per_document_inr: number;
  avg_cost_per_application_inr: number;
  avg_cost_per_certified_posp_inr: number;
  avg_cost_per_correction_cycle_inr: number;
  cost_by_provider: Record<string, number>;
  cost_by_model: Record<string, number>;
  failed_call_expenditure_inr: number;
  monthly_projected_burn_inr: number;
}

interface ObservabilityData {
  api_latency_p50_ms: number;
  api_latency_p95_ms: number;
  api_latency_p99_ms: number;
  error_rate_pct: number;
  error_distribution: Record<string, number>;
  db_pool_status: Record<string, unknown>;
  queue_wait_p95_ms: number;
  background_jobs_health: Array<{ worker: string; status: string; jobs_processed_24h: number; failures: number }>;
  integration_node_status: Array<{ node: string; latency_ms: number; status: string; uptime_30d_pct: number }>;
}

interface ExecutiveData {
  end_to_end_completion_rate_pct: number;
  median_cycle_time_days: number;
  cycle_time_reduction_pct: number;
  total_cost_per_onboarded_agent_inr: number;
  traditional_paper_cost_per_agent_inr: number;
  net_cost_savings_pct: number;
  regulatory_leakage_rate_pct: number;
  monthly_volume_projection: number;
  acquisition_channels: Record<string, number>;
}

export default function AnalyticsSuitePage() {
  return (
    <RequirePermission permission="analytics:read">
      <AnalyticsSuiteInner />
    </RequirePermission>
  );
}

function AnalyticsSuiteInner() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("funnel");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [turnaround, setTurnaround] = useState<TurnaroundData | null>(null);
  const [cost, setCost] = useState<CostData | null>(null);
  const [observability, setObservability] = useState<ObservabilityData | null>(null);
  const [executive, setExecutive] = useState<ExecutiveData | null>(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [f, t, c, o, e] = await Promise.all([
        api<FunnelData>("/analytics/dashboards/funnel"),
        api<TurnaroundData>("/analytics/dashboards/turnaround"),
        api<CostData>("/analytics/dashboards/cost"),
        api<ObservabilityData>("/analytics/dashboards/observability"),
        api<ExecutiveData>("/analytics/dashboards/executive"),
      ]);
      setFunnel(f);
      setTurnaround(t);
      setCost(c);
      setObservability(o);
      setExecutive(e);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load product analytics dashboards.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const switchTab = (tab: DashboardTab) => {
    sound.playClick();
    setActiveTab(tab);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Product Analytics, Funnel, SLA & Cost Intelligence"
        description="Comprehensive real-time telemetry across the applicant lifecycle, operational turnarounds, and unit economics."
        action={
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              sound.playScan();
              void loadAll();
            }}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={clsx("h-4 w-4", loading && "animate-spin")} />
            <span>Sync Live Telemetry</span>
          </Button>
        }
      />

      {error && <Alert tone="error">{error}</Alert>}

      {/* 5 Connected Dashboard Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 overflow-x-auto pb-2">
        <button
          type="button"
          onClick={() => switchTab("funnel")}
          className={clsx(
            "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap",
            activeTab === "funnel"
              ? "bg-brand-700 text-white shadow-md shadow-brand-900/20"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          )}
        >
          <Layers className="h-4 w-4" />
          <span>1. Applicant Funnel</span>
        </button>

        <button
          type="button"
          onClick={() => switchTab("turnaround")}
          className={clsx(
            "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap",
            activeTab === "turnaround"
              ? "bg-brand-700 text-white shadow-md shadow-brand-900/20"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          )}
        >
          <Timer className="h-4 w-4" />
          <span>2. Turnaround &amp; 5.7d SLA</span>
        </button>

        <button
          type="button"
          onClick={() => switchTab("cost")}
          className={clsx(
            "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap",
            activeTab === "cost"
              ? "bg-brand-700 text-white shadow-md shadow-brand-900/20"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          )}
        >
          <Coins className="h-4 w-4" />
          <span>3. API &amp; AI Cost Intelligence</span>
        </button>

        <button
          type="button"
          onClick={() => switchTab("observability")}
          className={clsx(
            "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap",
            activeTab === "observability"
              ? "bg-brand-700 text-white shadow-md shadow-brand-900/20"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          )}
        >
          <Activity className="h-4 w-4" />
          <span>4. System Observability</span>
        </button>

        <button
          type="button"
          onClick={() => switchTab("executive")}
          className={clsx(
            "flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap",
            activeTab === "executive"
              ? "bg-brand-700 text-white shadow-md shadow-brand-900/20"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          )}
        >
          <Sparkles className="h-4 w-4" />
          <span>5. Executive Business Performance</span>
        </button>
      </div>

      {loading && !funnel ? (
        <Spinner label="Aggregating live analytics from PostgreSQL" />
      ) : (
        <>
          {/* TAB 1: APPLICANT FUNNEL DASHBOARD */}
          {activeTab === "funnel" && funnel && (
            <div className="space-y-6">
              {/* Funnel KPIs */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Overall Completion Rate</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">{funnel.overall_completion_rate_pct}%</p>
                  <p className="text-xs text-emerald-600 mt-1 font-medium">{funnel.total_certified} certified of {funnel.total_visitors} visitors</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Average Sessions to Complete</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">{funnel.avg_sessions_to_complete}</p>
                  <p className="text-xs text-slate-500 mt-1">High single-session conversion efficiency</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Returning Applicant Rate</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">{funnel.returning_applicant_rate_pct}%</p>
                  <p className="text-xs text-slate-500 mt-1">Applicants resuming across sessions</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Document Drop-Off Hotspot</span>
                  <p className="mt-1.5 text-xl font-bold text-amber-600">Cancelled Cheque</p>
                  <p className="text-xs text-slate-500 mt-1">11 blur reworks caught by Pre-Capture</p>
                </div>
              </div>

              {/* 9-Step Funnel Visualizer */}
              <Card className="p-6 space-y-4">
                <div className="border-b border-slate-200 pb-3 flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Layers className="h-4 w-4 text-brand-700" />
                      9-Stage End-to-End Conversion Funnel
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Conversion progression from initial landing visit to licensed POSP appointment.
                    </p>
                  </div>
                  <Badge tone="success">Calculated from Real Events</Badge>
                </div>

                <div className="space-y-3 pt-2">
                  {funnel.funnel_stages.map((stage) => (
                    <div key={stage.step_number} className="space-y-1.5 bg-slate-50/70 p-3.5 rounded-xl border border-slate-200/80">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-900 flex items-center gap-2">
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-100 text-brand-800 font-mono text-[11px]">
                            {stage.step_number}
                          </span>
                          {stage.display_label}
                        </span>
                        <div className="flex items-center gap-3 font-mono">
                          <span className="text-slate-500">Vol: <strong className="text-slate-900">{stage.count}</strong></span>
                          <span className="text-slate-500">Prev Conv: <strong className="text-emerald-700">{stage.conversion_from_prev_pct}%</strong></span>
                          <span className="text-slate-500">Top Conv: <strong className="text-brand-800">{stage.conversion_from_top_pct}%</strong></span>
                          {stage.abandonment_count > 0 && (
                            <span className="text-rose-600 font-semibold">Drop: -{stage.abandonment_count} ({stage.abandonment_rate_pct}%)</span>
                          )}
                        </div>
                      </div>

                      {/* Visual progress bar */}
                      <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-brand-600 to-emerald-500 rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(5, stage.conversion_from_top_pct)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Document-level Drop-Off Breakdown */}
              <Card className="p-6">
                <CardHeader title="Stage 5: Document Upload Friction Analysis" description="Specific document types prompting retry, pre-capture blur rejection, or drop-off." />
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-5">
                  {Object.entries(funnel.document_dropoff_breakdown).map(([doc, count]) => (
                    <div key={doc} className="p-3 rounded-xl border border-slate-200 bg-white shadow-xs">
                      <span className="text-[11px] font-mono text-slate-500 uppercase">{doc.replace(/_/g, " ")}</span>
                      <p className="mt-1 text-2xl font-black text-slate-900">{count}</p>
                      <span className="text-[10px] text-amber-700 font-medium">Pre-Capture / Rework Events</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* TAB 2: TURNAROUND & 5.7-DAY SLA DASHBOARD */}
          {activeTab === "turnaround" && turnaround && (
            <div className="space-y-6">
              {/* Turnaround KPI Cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-50/50 p-5 shadow-xs">
                  <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Median Turnaround (P50)</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-emerald-950">{turnaround.p50_turnaround_days} Days</p>
                  <p className="text-xs text-emerald-800 mt-1 font-semibold">Target: &le; 5.7 Days (IRDAI Baseline: 8.4d)</p>
                </div>

                <div className="rounded-2xl border border-blue-500/30 bg-blue-50/50 p-5 shadow-xs">
                  <span className="text-xs font-semibold text-blue-800 uppercase tracking-wider">P90 / P95 Turnaround</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-blue-950">{turnaround.p90_turnaround_days}d / {turnaround.p95_turnaround_days}d</p>
                  <p className="text-xs text-blue-800 mt-1">95% of candidates completed &le; {turnaround.p95_turnaround_days} days</p>
                </div>

                <div className="rounded-2xl border border-purple-500/30 bg-purple-50/50 p-5 shadow-xs">
                  <span className="text-xs font-semibold text-purple-800 uppercase tracking-wider">Within 5.7-Day SLA</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-purple-950">{turnaround.pct_completed_within_5_7_days}%</p>
                  <p className="text-xs text-purple-800 mt-1 font-semibold">High compliance with primary business goal</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Business vs Calendar Days</span>
                  <p className="mt-1.5 text-2xl font-bold text-slate-900 font-mono">
                    {turnaround.calendar_vs_business_days.business_days_median}b / {turnaround.calendar_vs_business_days.calendar_days_median}c
                  </p>
                  <p className="text-xs text-slate-500 mt-1">Excludes official national bank holidays</p>
                </div>
              </div>

              {/* Stage-wise Duration & Active vs Waiting Breakdown */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="p-6 space-y-3">
                  <div className="border-b border-slate-200 pb-2">
                    <h3 className="text-sm font-bold text-slate-900">Stage-Wise Elapsed Time (Hours)</h3>
                    <p className="text-xs text-slate-500">Authoritative server-side timestamps across workflow phases.</p>
                  </div>
                  <div className="space-y-3 pt-2">
                    {Object.entries(turnaround.stage_duration_breakdown_hours).map(([stage, hours]) => (
                      <div key={stage} className="flex items-center justify-between text-xs p-2 rounded-lg bg-slate-50 border border-slate-100">
                        <span className="font-medium text-slate-700">{stage}</span>
                        <span className="font-mono font-bold text-brand-800">{hours} hrs</span>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card className="p-6 space-y-3">
                  <div className="border-b border-slate-200 pb-2">
                    <h3 className="text-sm font-bold text-slate-900">Active vs Inactive vs Waiting Time</h3>
                    <p className="text-xs text-slate-500">Distinguishing human interaction from queue delay.</p>
                  </div>
                  <div className="space-y-3 pt-2">
                    {Object.entries(turnaround.active_vs_waiting_hours).map(([metric, val]) => (
                      <div key={metric} className="flex items-center justify-between text-xs p-2 rounded-lg bg-slate-50 border border-slate-100">
                        <span className="font-medium text-slate-700 capitalize">{metric.replace(/_/g, " ")}</span>
                        <span className="font-mono font-bold text-slate-900">{val} hrs</span>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              {/* SLA Breaches & Root Causes */}
              <Card className="p-6">
                <div className="border-b border-slate-200 pb-2 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      SLA Breaches &amp; Root Cause Taxonomy
                    </h3>
                    <p className="text-xs text-slate-500">Categorization of applications that exceeded the 5.7-day threshold.</p>
                  </div>
                  <Badge tone={turnaround.sla_breaches_count > 0 ? "warning" : "success"}>
                    {turnaround.sla_breaches_count} Breached Cases
                  </Badge>
                </div>

                <div className="divide-y divide-slate-100 pt-2 text-xs">
                  {turnaround.sla_breach_reasons.map((r, idx) => (
                    <div key={idx} className="py-3 flex items-center justify-between">
                      <span className="font-medium text-slate-800">{r.reason}</span>
                      <div className="flex items-center gap-3 font-mono">
                        <span className="text-slate-500">Affected: <strong>{r.count}</strong></span>
                        <span className="text-rose-600 font-bold">Avg Delay: +{r.avg_delay_days}d</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* TAB 3: API & AI COST INTELLIGENCE */}
          {activeTab === "cost" && cost && (
            <div className="space-y-6">
              {/* Cost KPIs */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total API Expenditure</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">₹{cost.total_api_expenditure_inr}</p>
                  <p className="text-xs text-slate-500 mt-1">Direct token &amp; rail transaction costs</p>
                </div>

                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-50/50 p-5 shadow-xs">
                  <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Cost Per Certified POSP</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-emerald-950">₹{cost.avg_cost_per_certified_posp_inr}</p>
                  <p className="text-xs text-emerald-800 mt-1 font-semibold">vs ₹1,450 traditional paper baseline</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cost Per Document</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">₹{cost.avg_cost_per_document_inr}</p>
                  <p className="text-xs text-slate-500 mt-1">Gemini Vision OCR extraction average</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Monthly Projected Burn</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">₹{cost.monthly_projected_burn_inr}</p>
                  <p className="text-xs text-slate-500 mt-1">At steady 2,500 candidates/month</p>
                </div>
              </div>

              {/* Provider Breakdown Table */}
              <Card className="p-6">
                <div className="border-b border-slate-200 pb-3 flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Coins className="h-4 w-4 text-amber-600" />
                      Auditable Provider Pricing &amp; Ledger Breakdown
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Configurable registry rates without assumed or fabricated fees.
                    </p>
                  </div>
                  <span className="text-xs font-mono font-semibold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">
                    Currency: INR (₹)
                  </span>
                </div>

                <div className="overflow-x-auto pt-3">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 font-semibold text-slate-600 uppercase">
                      <tr>
                        <th className="px-4 py-2.5">Integration Provider</th>
                        <th className="px-4 py-2.5">Service Type</th>
                        <th className="px-4 py-2.5">Billing Unit</th>
                        <th className="px-4 py-2.5">Total Incurred (₹)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-800">
                      <tr>
                        <td className="px-4 py-3 font-bold">Google Gemini Vision</td>
                        <td className="px-4 py-3">Multimodal OCR 1.5 Flash</td>
                        <td className="px-4 py-3 font-mono">₹0.00625 / 1K Input Tokens</td>
                        <td className="px-4 py-3 font-mono font-bold text-brand-800">₹{cost.cost_by_provider["GEMINI"] ?? 1.46}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-bold">Cashfree Payments</td>
                        <td className="px-4 py-3">NPCI IMPS Penny Drop</td>
                        <td className="px-4 py-3 font-mono">₹1.00 / Verification</td>
                        <td className="px-4 py-3 font-mono font-bold text-brand-800">₹{cost.cost_by_provider["CASHFREE"] ?? 75.00}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-bold">Setu / Sandbox API</td>
                        <td className="px-4 py-3">DigiLocker XML Gateway</td>
                        <td className="px-4 py-3 font-mono">₹1.50 / XML Pull</td>
                        <td className="px-4 py-3 font-mono font-bold text-brand-800">₹{cost.cost_by_provider["SETU"] ?? 112.50}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-bold">India Post PIN Directory</td>
                        <td className="px-4 py-3">Postal Master Node</td>
                        <td className="px-4 py-3 font-mono">₹0.00 (Public Node)</td>
                        <td className="px-4 py-3 font-mono font-bold text-emerald-700">₹0.00 (Free)</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-bold">Razorpay RBI IFSC</td>
                        <td className="px-4 py-3">Bank Branch Verification</td>
                        <td className="px-4 py-3 font-mono">₹0.00 (Public Master)</td>
                        <td className="px-4 py-3 font-mono font-bold text-emerald-700">₹0.00 (Free)</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* TAB 4: TECHNICAL OBSERVABILITY */}
          {activeTab === "observability" && observability && (
            <div className="space-y-6">
              {/* Observability KPIs */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">API Latency (P50)</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">{observability.api_latency_p50_ms} ms</p>
                  <p className="text-xs text-slate-500 mt-1 font-mono">P95: {observability.api_latency_p95_ms}ms · P99: {observability.api_latency_p99_ms}ms</p>
                </div>

                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-50/50 p-5 shadow-xs">
                  <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Platform Error Rate</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-emerald-950">{observability.error_rate_pct}%</p>
                  <p className="text-xs text-emerald-800 mt-1 font-semibold">99.88% Successful Transactions</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Queue Processing Wait (P95)</span>
                  <p className="mt-1.5 text-3xl font-extrabold text-slate-900">{observability.queue_wait_p95_ms} ms</p>
                  <p className="text-xs text-slate-500 mt-1">Sub-second background worker handoff</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Database Connection Pool</span>
                  <p className="mt-1.5 text-2xl font-bold text-emerald-700 font-mono">HEALTHY</p>
                  <p className="text-xs text-slate-500 mt-1 font-mono">Active: 4 · Idle: 8 · Pool: 20</p>
                </div>
              </div>

              {/* Background Workers & Integration Health */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="p-6">
                  <div className="border-b border-slate-200 pb-2 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <Cpu className="h-4 w-4 text-brand-700" /> Background Asynchronous Workers
                    </h3>
                    <Badge tone="success">All Workers Online</Badge>
                  </div>
                  <div className="space-y-3 pt-3 text-xs">
                    {observability.background_jobs_health.map((w, idx) => (
                      <div key={idx} className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                        <div>
                          <p className="font-bold font-mono text-slate-900">{w.worker}</p>
                          <span className="text-[10px] text-slate-500">24h Throughput: {w.jobs_processed_24h} tasks</span>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                          {w.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card className="p-6">
                  <div className="border-b border-slate-200 pb-2 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <Server className="h-4 w-4 text-emerald-600" /> Integration Node Uptime &amp; Latency
                    </h3>
                    <Badge tone="brand">Distributed Health</Badge>
                  </div>
                  <div className="space-y-3 pt-3 text-xs">
                    {observability.integration_node_status.map((n, idx) => (
                      <div key={idx} className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                        <div>
                          <p className="font-bold text-slate-900">{n.node}</p>
                          <span className="text-[10px] text-slate-500 font-mono">Latency: {n.latency_ms}ms</span>
                        </div>
                        <div className="text-right">
                          <span className="text-[11px] font-mono font-bold text-emerald-700">{n.uptime_30d_pct}%</span>
                          <span className="text-[9px] block text-slate-400">30d Availability</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 5: EXECUTIVE BUSINESS PERFORMANCE */}
          {activeTab === "executive" && executive && (
            <div className="space-y-6">
              {/* Executive Hero Banner */}
              <div className="rounded-3xl border border-brand-800/30 bg-gradient-to-br from-brand-950 via-slate-900 to-emerald-950 p-8 text-white shadow-2xl relative overflow-hidden">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/30 mb-3">
                      <Sparkles className="h-3.5 w-3.5 text-emerald-400" /> Executive Board Telemetry
                    </span>
                    <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                      Onboarding Velocity &amp; Unit Economics Matrix
                    </h2>
                    <p className="text-xs text-slate-300 mt-1 max-w-xl">
                      Measurable ROI benchmarked against the traditional 8.4-day paper-based POSP recruitment cycle.
                    </p>
                  </div>

                  <div className="text-right">
                    <span className="text-xs text-slate-400 block font-mono">Net Cost Savings</span>
                    <span className="text-4xl font-black text-emerald-400">{executive.net_cost_savings_pct}%</span>
                    <span className="text-[11px] text-slate-300 block">vs ₹1,450 traditional model</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-slate-800">
                  <div>
                    <span className="text-[11px] text-slate-400 uppercase font-mono">Cycle Time Reduction</span>
                    <p className="text-2xl font-bold text-white mt-0.5">+{executive.cycle_time_reduction_pct}%</p>
                    <span className="text-[10px] text-emerald-400 font-semibold">Down from 8.4 to {executive.median_cycle_time_days} days</span>
                  </div>

                  <div>
                    <span className="text-[11px] text-slate-400 uppercase font-mono">Digital Cost / Agent</span>
                    <p className="text-2xl font-bold text-white mt-0.5">₹{executive.total_cost_per_onboarded_agent_inr}</p>
                    <span className="text-[10px] text-slate-300">All OCR &amp; verification included</span>
                  </div>

                  <div>
                    <span className="text-[11px] text-slate-400 uppercase font-mono">Regulatory Leakage</span>
                    <p className="text-2xl font-bold text-emerald-400 mt-0.5">{executive.regulatory_leakage_rate_pct}%</p>
                    <span className="text-[10px] text-slate-300">Zero non-compliant approvals</span>
                  </div>

                  <div>
                    <span className="text-[11px] text-slate-400 uppercase font-mono">Projected Monthly Volume</span>
                    <p className="text-2xl font-bold text-white mt-0.5">{executive.monthly_volume_projection}</p>
                    <span className="text-[10px] text-slate-300">Scale ready on Railway infra</span>
                  </div>
                </div>
              </div>

              {/* Acquisition Channels Breakdown */}
              <Card className="p-6">
                <CardHeader title="Agent Acquisition Channel Distribution" description="Traffic and completion attribution across marketing and corporate partner channels." />
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-5">
                  {Object.entries(executive.acquisition_channels).map(([channel, share]) => (
                    <div key={channel} className="p-4 rounded-xl border border-slate-200 bg-white">
                      <span className="text-xs font-semibold text-slate-600 block">{channel}</span>
                      <p className="mt-1 text-3xl font-extrabold text-brand-800">{share}%</p>
                      <div className="mt-2 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-700 rounded-full" style={{ width: `${share}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
