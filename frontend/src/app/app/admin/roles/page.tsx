"use client";

import { Check, Minus, Pencil } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Badge, Button, Card, CardHeader, Dialog, Field, Input, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RoleDetail, RolesMatrix } from "@/lib/types";

export default function RolesPage() {
  return (
    <RequirePermission permission="roles:read">
      <RolesView />
    </RequirePermission>
  );
}

const ADMIN_FORBIDDEN = new Set([
  "application:decide",
  "application:decide_escalated",
  "fraud:review",
  "application:escalate",
]);

function RolesView() {
  const { can } = useAuth();
  const [data, setData] = useState<RolesMatrix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [editing, setEditing] = useState<RoleDetail | null>(null);
  const [selectedPerms, setSelectedPerms] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api<RolesMatrix>("/admin/roles");
      setData(res);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load roles.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function openEdit(r: RoleDetail) {
    setEditing(r);
    setSelectedPerms(new Set(r.permissions));
    setReason("");
    setEditError(null);
  }

  function togglePerm(code: string) {
    setSelectedPerms((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  async function saveRolePerms(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    setEditError(null);
    try {
      await api(`/admin/roles/${editing.code}/permissions`, {
        method: "PUT",
        body: JSON.stringify({
          permission_codes: [...selectedPerms].sort(),
          reason,
        }),
      });
      setNotice(`Updated permissions for ${editing.name}.`);
      setEditing(null);
      await load();
    } catch (e) {
      setEditError(e instanceof ApiError ? e.message : "Failed to update permissions.");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <Alert tone="error">{error}</Alert>;
  if (!data) return <Spinner />;
  const categories = [...new Set(data.permissions.map((p) => p.category))];
  const canEdit = can("config:manage");

  return (
    <>
      <PageHeader
        title="Roles & permissions"
        description="Roles grant permissions (RBAC). The server additionally enforces attribute rules (ABAC), Separation of Duties, and Admin lockout guards."
      />
      {notice && (
        <Alert tone="success" className="mb-4">
          {notice}
        </Alert>
      )}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.roles.map((r) => (
          <Card key={r.code} className="flex flex-col justify-between p-5">
            <div>
              <div className="flex items-center justify-between">
                <p className="font-semibold text-slate-900">{r.name}</p>
                <Badge tone={r.is_staff ? "brand" : "neutral"}>{r.is_staff ? "Staff" : "External"}</Badge>
              </div>
              <p className="mt-2 text-sm text-slate-600">{r.description}</p>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <p className="text-xs text-slate-500">
                {r.user_count} user{r.user_count === 1 ? "" : "s"} · {r.permissions.length} permissions
              </p>
              {canEdit && r.code !== "APPLICANT" && (
                <Button variant="secondary" size="sm" onClick={() => openEdit(r)}>
                  <Pencil className="h-3.5 w-3.5" /> Edit
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="Permission matrix" description="Administrators manage the platform but cannot decide applications (Separation of Duties)." />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-100 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 text-left font-medium">Permission</th>
                {data.roles.map((r) => (
                  <th key={r.code} className="px-3 py-3 text-center font-medium">
                    {r.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => (
                <CategoryRows key={cat} category={cat} data={data} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Dialog
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title={`Edit permissions — ${editing?.name ?? ""}`}
        description={
          editing?.code === "ADMIN"
            ? "ADMIN cannot receive case decision permissions (Separation of Duties) or lose core admin permissions."
            : "Adjust granted permissions for this staff role. All changes are recorded in the audit log."
        }
      >
        <form className="space-y-4" onSubmit={saveRolePerms}>
          {editError && <Alert tone="error">{editError}</Alert>}
          <div className="max-h-72 space-y-3 overflow-y-auto rounded-lg border border-slate-200 p-3">
            {categories.map((cat) => (
              <div key={cat}>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{cat}</p>
                <div className="space-y-1">
                  {data.permissions
                    .filter((p) => p.category === cat)
                    .map((p) => {
                      const blockedForAdmin = editing?.code === "ADMIN" && ADMIN_FORBIDDEN.has(p.code);
                      return (
                        <label
                          key={p.code}
                          className={`flex items-start gap-2 rounded px-2 py-1 text-xs ${
                            blockedForAdmin ? "opacity-50" : "hover:bg-slate-50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            disabled={blockedForAdmin}
                            checked={selectedPerms.has(p.code)}
                            onChange={() => togglePerm(p.code)}
                            className="mt-0.5"
                          />
                          <span>
                            <span className="font-mono font-medium text-slate-900">{p.code}</span> —{" "}
                            <span className="text-slate-600">{p.description}</span>
                          </span>
                        </label>
                      );
                    })}
                </div>
              </div>
            ))}
          </div>
          <Field label="Change reason" htmlFor="role-edit-reason" hint="Minimum 5 characters; logged in the audit trail.">
            <Input
              id="role-edit-reason"
              required
              minLength={5}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Align Reviewer permissions with audit policy"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Save permissions
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

function CategoryRows({ category, data }: { category: string; data: RolesMatrix }) {
  return (
    <>
      <tr className="bg-slate-50/60">
        <td colSpan={data.roles.length + 1} className="px-5 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          {category}
        </td>
      </tr>
      {data.permissions
        .filter((p) => p.category === category)
        .map((p) => (
          <tr key={p.code} className="border-t border-slate-100">
            <td className="px-5 py-3">
              <p className="font-mono text-xs text-slate-900">{p.code}</p>
              <p className="text-xs text-slate-500">{p.description}</p>
            </td>
            {data.roles.map((r) => (
              <td key={r.code} className="px-3 py-3 text-center">
                {r.permissions.includes(p.code) ? (
                  <Check className="mx-auto h-4 w-4 text-emerald-600" aria-label="Granted" />
                ) : (
                  <Minus className="mx-auto h-4 w-4 text-slate-300" aria-label="Not granted" />
                )}
              </td>
            ))}
          </tr>
        ))}
    </>
  );
}
