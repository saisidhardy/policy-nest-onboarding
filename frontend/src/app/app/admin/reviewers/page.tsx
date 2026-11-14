"use client";

import { ArrowRightLeft, Check, Copy, KeyRound, ShieldAlert, Sliders, UserCheck, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ReassignWorkloadOut, ReviewerWorkload, RolesMatrix } from "@/lib/types";

export default function AdminReviewersPage() {
  return (
    <RequirePermission permission="users:manage">
      <ReviewersView />
    </RequirePermission>
  );
}

function ReviewersView() {
  const [reviewers, setReviewers] = useState<ReviewerWorkload[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [regionFilter, setRegionFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [scopeTarget, setScopeTarget] = useState<ReviewerWorkload | null>(null);
  const [scopeRegion, setScopeRegion] = useState("");
  const [scopeClearance, setScopeClearance] = useState("1");
  const [scopeActive, setScopeActive] = useState(true);
  const [scopeSaving, setScopeSaving] = useState(false);
  const [scopeError, setScopeError] = useState<string | null>(null);

  const [reassignSource, setReassignSource] = useState<ReviewerWorkload | null>(null);
  const [reassignDestId, setReassignDestId] = useState("");
  const [reassignReason, setReassignReason] = useState("");
  const [reassignSaving, setReassignSaving] = useState(false);
  const [reassignError, setReassignError] = useState<string | null>(null);

  const [provisionOpen, setProvisionOpen] = useState(false);
  const [provisionForm, setProvisionForm] = useState({
    full_name: "",
    email: "",
    role: "REVIEWER" as "REVIEWER" | "SENIOR_REVIEWER" | "ADMIN",
    region: "ALL",
    clearance_level: 1,
    initial_password: "",
    auto_generate_password: true,
  });
  const [provisionSaving, setProvisionSaving] = useState(false);
  const [provisionError, setProvisionError] = useState<string | null>(null);
  const [provisionResult, setProvisionResult] = useState<{
    full_name: string;
    email: string;
    role: string;
    generated_secret?: string | null;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (regionFilter) params.set("region", regionFilter);
    if (roleFilter) params.set("role", roleFilter);
    const qs = params.toString();
    try {
      const [rows, matrix] = await Promise.all([
        api<ReviewerWorkload[]>(`/admin/reviewers${qs ? `?${qs}` : ""}`),
        api<RolesMatrix>("/admin/roles"),
      ]);
      setReviewers(rows);
      setRegions(matrix.regions);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load reviewer workloads.");
    } finally {
      setLoading(false);
    }
  }, [regionFilter, roleFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  function openScope(r: ReviewerWorkload) {
    setScopeTarget(r);
    setScopeRegion(r.region ?? "");
    setScopeClearance(String(r.clearance_level));
    setScopeActive(r.is_active);
    setScopeError(null);
  }

  async function saveScope(e: React.FormEvent) {
    e.preventDefault();
    if (!scopeTarget) return;
    setScopeSaving(true);
    setScopeError(null);
    try {
      await api(`/admin/users/${scopeTarget.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          region: scopeRegion || null,
          clearance_level: Number(scopeClearance),
          is_active: scopeActive,
        }),
      });
      setNotice(`Updated reviewer scope for ${scopeTarget.full_name}.`);
      setScopeTarget(null);
      await load();
    } catch (e) {
      setScopeError(e instanceof ApiError ? e.message : "Failed to update reviewer.");
    } finally {
      setScopeSaving(false);
    }
  }

  function openReassign(r: ReviewerWorkload) {
    setReassignSource(r);
    setReassignDestId("");
    setReassignReason("");
    setReassignError(null);
  }

  async function submitReassign(e: React.FormEvent) {
    e.preventDefault();
    if (!reassignSource) return;
    setReassignSaving(true);
    setReassignError(null);
    try {
      const res = await api<ReassignWorkloadOut>(`/admin/reviewers/${reassignSource.id}/reassign-workload`, {
        method: "POST",
        body: JSON.stringify({
          target_reviewer_id: reassignDestId || null,
          reason: reassignReason,
        }),
      });
      setNotice(
        `Reassigned ${res.reassigned_count} active case(s) from ${reassignSource.full_name}${
          res.target_reviewer_id ? "" : " back to the unassigned queue"
        }.`,
      );
      setReassignSource(null);
      await load();
    } catch (e) {
      setReassignError(e instanceof ApiError ? e.message : "Failed to reassign workload.");
    } finally {
      setReassignSaving(false);
    }
  }

  async function submitProvision(e: React.FormEvent) {
    e.preventDefault();
    setProvisionSaving(true);
    setProvisionError(null);
    try {
      const res = await api<{
        id: string;
        email: string;
        full_name: string;
        role: { code: string; name: string };
        generated_secret?: string | null;
      }>("/admin/users", {
        method: "POST",
        body: {
          full_name: provisionForm.full_name.trim(),
          email: provisionForm.email.trim(),
          role: provisionForm.role,
          region: provisionForm.region || null,
          clearance_level: Number(provisionForm.clearance_level),
          initial_password: provisionForm.auto_generate_password ? undefined : (provisionForm.initial_password || undefined),
          auto_generate_password: provisionForm.auto_generate_password,
        },
      });
      setProvisionResult({
        full_name: res.full_name,
        email: res.email,
        role: res.role.name,
        generated_secret: res.generated_secret,
      });
      setProvisionOpen(false);
      setNotice(`Staff account provisioned for ${res.full_name} (${res.role.name}).`);
      await load();
    } catch (err) {
      setProvisionError(err instanceof ApiError ? err.message : "Failed to provision staff account.");
    } finally {
      setProvisionSaving(false);
    }
  }

  const totalActive = reviewers.reduce((sum, r) => sum + r.active_assigned_count, 0);
  const totalEscalated = reviewers.reduce((sum, r) => sum + r.escalated_assigned_count, 0);
  const activeReviewers = reviewers.filter((r) => r.is_active);

  return (
    <>
      <PageHeader
        title="Reviewer & Staff Operations"
        description="Monitor reviewer capacity, provision confidential staff credentials, and manage regional workloads."
        action={
          <Button onClick={() => setProvisionOpen(true)}>
            <UserPlus className="mr-1.5 h-4 w-4" />
            Provision Staff Account
          </Button>
        }
      />

      {notice && (
        <Alert tone="success" className="mb-4">
          {notice}
        </Alert>
      )}
      {error && (
        <Alert tone="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs font-medium text-slate-500">Review staff</p>
          <p className="mt-1 text-2xl font-semibold text-slate-900">{reviewers.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs font-medium text-slate-500">Active reviewers</p>
          <p className="mt-1 text-2xl font-semibold text-emerald-700">{activeReviewers.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs font-medium text-slate-500">Assigned queue</p>
          <p className="mt-1 text-2xl font-semibold text-brand-700">{totalActive}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs font-medium text-slate-500">Escalated assigned</p>
          <p className="mt-1 text-2xl font-semibold text-amber-700">{totalEscalated}</p>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Reviewer roster & workload"
          action={
            <div className="flex flex-wrap gap-2">
              <Select
                aria-label="Filter by role"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="w-40"
              >
                <option value="">All roles</option>
                <option value="REVIEWER">Reviewer</option>
                <option value="SENIOR_REVIEWER">Senior Reviewer</option>
              </Select>
              <Select
                aria-label="Filter by region"
                value={regionFilter}
                onChange={(e) => setRegionFilter(e.target.value)}
                className="w-36"
              >
                <option value="">All regions</option>
                {regions.map((rg) => (
                  <option key={rg} value={rg}>
                    {rg}
                  </option>
                ))}
              </Select>
            </div>
          }
        />

        {loading ? (
          <div className="p-8">
            <Spinner label="Loading reviewers" />
          </div>
        ) : reviewers.length === 0 ? (
          <EmptyState title="No reviewers match the filters">
            Invite or assign REVIEWER / SENIOR_REVIEWER accounts under User management.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-100 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">Reviewer</th>
                  <th className="px-3 py-3 text-left font-medium">Role &amp; scope</th>
                  <th className="px-3 py-3 text-right font-medium">Active queue</th>
                  <th className="px-3 py-3 text-right font-medium">Decisions / overrides</th>
                  <th className="px-3 py-3 text-left font-medium">Status</th>
                  <th className="px-5 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {reviewers.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3.5">
                      <p className="font-medium text-slate-900">{r.full_name}</p>
                      <p className="text-xs text-slate-500">{r.email}</p>
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        Last login: {r.last_login_at ? formatDateTime(r.last_login_at) : "Never"}
                      </p>
                    </td>
                    <td className="px-3 py-3.5">
                      <Badge tone={r.role === "SENIOR_REVIEWER" ? "brand" : "neutral"}>
                        {r.role === "SENIOR_REVIEWER" ? "Senior Reviewer" : "Reviewer"}
                      </Badge>
                      <p className="mt-1 text-xs text-slate-600">
                        Region: <strong>{r.region ?? "Unassigned"}</strong> · L{r.clearance_level}
                      </p>
                    </td>
                    <td className="px-3 py-3.5 text-right">
                      <span className="font-semibold text-slate-900">{r.active_assigned_count}</span>
                      {r.escalated_assigned_count > 0 && (
                        <p className="text-xs text-amber-700">{r.escalated_assigned_count} escalated</p>
                      )}
                    </td>
                    <td className="px-3 py-3.5 text-right text-slate-700">
                      <p>
                        {r.decisions_made_count} decided · {r.overrides_count} override{r.overrides_count === 1 ? "" : "s"}
                      </p>
                      <p className="text-xs text-slate-500">{r.corrections_requested_count} field corrections</p>
                    </td>
                    <td className="px-3 py-3.5">
                      <Badge tone={r.is_active ? "success" : "danger"}>{r.is_active ? "Active" : "Inactive"}</Badge>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="inline-flex flex-wrap justify-end gap-2">
                        <Button variant="secondary" size="sm" onClick={() => openScope(r)}>
                          <Sliders className="h-3.5 w-3.5" /> Scope
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={r.active_assigned_count === 0}
                          onClick={() => openReassign(r)}
                        >
                          <ArrowRightLeft className="h-3.5 w-3.5" /> Reassign
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Dialog
        open={Boolean(scopeTarget)}
        onClose={() => setScopeTarget(null)}
        title={`Edit scope — ${scopeTarget?.full_name ?? ""}`}
        description="Update reviewer region coverage, clearance tier, or activation status."
      >
        <form className="space-y-4" onSubmit={saveScope}>
          {scopeError && <Alert tone="error">{scopeError}</Alert>}
          <Field label="Assigned region" htmlFor="rev-scope-region">
            <Select id="rev-scope-region" value={scopeRegion} onChange={(e) => setScopeRegion(e.target.value)}>
              <option value="">Unassigned</option>
              {regions.map((rg) => (
                <option key={rg} value={rg}>
                  {rg}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Clearance level (1–3)" htmlFor="rev-scope-clearance">
            <Select id="rev-scope-clearance" value={scopeClearance} onChange={(e) => setScopeClearance(e.target.value)}>
              <option value="1">Level 1 — Standard</option>
              <option value="2">Level 2 — High sensitivity</option>
              <option value="3">Level 3 — Maximum clearance</option>
            </Select>
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={scopeActive} onChange={(e) => setScopeActive(e.target.checked)} />
            Account active (can receive queue assignments)
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setScopeTarget(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={scopeSaving}>
              <UserCheck className="h-4 w-4" /> Save scope
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={Boolean(reassignSource)}
        onClose={() => setReassignSource(null)}
        title={`Reassign workload — ${reassignSource?.full_name ?? ""}`}
        description={`Move all ${reassignSource?.active_assigned_count ?? 0} active assigned application(s) to another active reviewer or return to the unassigned pool.`}
      >
        <form className="space-y-4" onSubmit={submitReassign}>
          {reassignError && <Alert tone="error">{reassignError}</Alert>}
          {reassignSource && reassignSource.escalated_assigned_count > 0 && (
            <Alert tone="warning">
              This reviewer holds {reassignSource.escalated_assigned_count} escalated case(s). Select an active Senior Reviewer or return to the unassigned pool.
            </Alert>
          )}
          <Field label="Target reviewer" htmlFor="reassign-target">
            <Select id="reassign-target" value={reassignDestId} onChange={(e) => setReassignDestId(e.target.value)}>
              <option value="">Return to unassigned queue</option>
              {activeReviewers
                .filter((cand) => cand.id !== reassignSource?.id)
                .map((cand) => (
                  <option key={cand.id} value={cand.id}>
                    {cand.full_name} ({cand.role === "SENIOR_REVIEWER" ? "Senior" : "Reviewer"} · {cand.region ?? "No region"} · {cand.active_assigned_count} active)
                  </option>
                ))}
            </Select>
          </Field>
          <Field label="Audit reason" htmlFor="reassign-reason" hint="Minimum 5 characters; recorded on each application timeline and audit log.">
            <Input
              id="reassign-reason"
              required
              minLength={5}
              value={reassignReason}
              onChange={(e) => setReassignReason(e.target.value)}
              placeholder="e.g., Balancing South region SLA backlog"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setReassignSource(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={reassignSaving}>
              Confirm reassignment
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Provision Staff Account Dialog */}
      <Dialog
        open={provisionOpen}
        onClose={() => setProvisionOpen(false)}
        title="Provision Confidential Staff Account"
        description="Create an internal Reviewer, Senior Reviewer / Executive, or Tech Admin account with confidential login credentials."
      >
        <form className="space-y-4" onSubmit={submitProvision} noValidate>
          {provisionError && <Alert tone="error">{provisionError}</Alert>}

          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            <div className="flex items-center gap-1.5 font-medium text-slate-800">
              <ShieldAlert className="h-3.5 w-3.5 text-brand-600" />
              <span>Restricted Staff Onboarding</span>
            </div>
            <p className="mt-1">
              Reviewers and Executives cannot self-register. Only the Tech Team can provision these roles.
            </p>
          </div>

          <Field label="Full Name" htmlFor="staff-name">
            <Input
              id="staff-name"
              required
              value={provisionForm.full_name}
              onChange={(e) => setProvisionForm({ ...provisionForm, full_name: e.target.value })}
              placeholder="e.g. Neha Verma"
            />
          </Field>

          <Field label="Work Email" htmlFor="staff-email">
            <Input
              id="staff-email"
              type="email"
              required
              value={provisionForm.email}
              onChange={(e) => setProvisionForm({ ...provisionForm, email: e.target.value })}
              placeholder="e.g. reviewer.ops@policynest.com"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Staff Role" htmlFor="staff-role">
              <Select
                id="staff-role"
                value={provisionForm.role}
                onChange={(e) =>
                  setProvisionForm({
                    ...provisionForm,
                    role: e.target.value as "REVIEWER" | "SENIOR_REVIEWER" | "ADMIN",
                    clearance_level: e.target.value === "REVIEWER" ? 1 : 3,
                  })
                }
              >
                <option value="REVIEWER">Reviewer (Verification Officer)</option>
                <option value="SENIOR_REVIEWER">Senior Reviewer (Operations Executive)</option>
                <option value="ADMIN">Platform Administrator (Tech Team)</option>
              </Select>
            </Field>

            <Field label="Assigned Region" htmlFor="staff-region">
              <Select
                id="staff-region"
                value={provisionForm.region}
                onChange={(e) => setProvisionForm({ ...provisionForm, region: e.target.value })}
              >
                <option value="ALL">All Regions (National)</option>
                {regions.map((rg) => (
                  <option key={rg} value={rg}>
                    {rg}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label="Clearance Level" htmlFor="staff-clearance" hint="Level 1: standard; Level 3: senior escalations & fraud referrals">
            <Select
              id="staff-clearance"
              value={String(provisionForm.clearance_level)}
              onChange={(e) => setProvisionForm({ ...provisionForm, clearance_level: Number(e.target.value) })}
            >
              <option value="1">Level 1 - Verification Officer</option>
              <option value="2">Level 2 - Supervisor</option>
              <option value="3">Level 3 - Senior Executive & Fraud Clearance</option>
            </Select>
          </Field>

          <div className="rounded-md border border-slate-200 p-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={provisionForm.auto_generate_password}
                onChange={(e) => setProvisionForm({ ...provisionForm, auto_generate_password: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="font-medium">Auto-generate secure 16-character temporary secret</span>
            </label>

            {!provisionForm.auto_generate_password && (
              <div className="mt-3">
                <Field label="Custom Initial Password" htmlFor="staff-custom-pwd">
                  <Input
                    id="staff-custom-pwd"
                    type="password"
                    value={provisionForm.initial_password}
                    onChange={(e) => setProvisionForm({ ...provisionForm, initial_password: e.target.value })}
                    placeholder="Enter confidential password"
                  />
                </Field>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setProvisionOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              loading={provisionSaving}
              disabled={!provisionForm.full_name || !provisionForm.email}
            >
              Create Staff Login
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Secret Credentials Modal */}
      {provisionResult && (
        <Dialog
          open={!!provisionResult}
          onClose={() => {
            setProvisionResult(null);
            setCopied(false);
          }}
          title="Confidential Staff Credentials Generated"
          description="Securely share these credentials with the designated officer. They can sign in immediately."
        >
          <div className="space-y-4">
            <div className="rounded-md border border-brand-200 bg-brand-50/50 p-4 text-sm">
              <div className="space-y-2">
                <div className="flex justify-between border-b border-brand-100 pb-2">
                  <span className="text-slate-600">Officer Name:</span>
                  <span className="font-semibold text-slate-900">{provisionResult.full_name}</span>
                </div>
                <div className="flex justify-between border-b border-brand-100 pb-2">
                  <span className="text-slate-600">Assigned Role:</span>
                  <span className="font-semibold text-brand-700">{provisionResult.role}</span>
                </div>
                <div className="flex justify-between border-b border-brand-100 pb-2">
                  <span className="text-slate-600">Login Email:</span>
                  <span className="font-mono text-slate-900">{provisionResult.email}</span>
                </div>
                {provisionResult.generated_secret && (
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-slate-600">Confidential Secret:</span>
                    <code className="rounded bg-white px-2.5 py-1 font-mono text-sm font-bold text-brand-900 shadow-sm border border-brand-200">
                      {provisionResult.generated_secret}
                    </code>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  const text = `PolicyNest Staff Account\nRole: ${provisionResult.role}\nEmail: ${provisionResult.email}\nSecret Password: ${provisionResult.generated_secret ?? "Pending Invite Link"}\nLogin Portal: /login`;
                  void navigator.clipboard.writeText(text);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 3000);
                }}
              >
                {copied ? <Check className="mr-1.5 h-4 w-4 text-emerald-600" /> : <Copy className="mr-1.5 h-4 w-4" />}
                {copied ? "Copied to Clipboard" : "Copy Credentials"}
              </Button>
              <Button
                type="button"
                onClick={() => {
                  setProvisionResult(null);
                  setCopied(false);
                }}
              >
                Done
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  );
}
