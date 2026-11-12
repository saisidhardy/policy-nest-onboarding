"use client";

import { useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Badge, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { IntegrationStatus, SystemHealth } from "@/lib/types";

export default function SystemPage() {
  return (
    <RequirePermission permission="system:read">
      <SystemView />
    </RequirePermission>
  );
}

function statusBadge(i: IntegrationStatus) {
  if (i.status === "CONFIGURED") return i.mode === "SANDBOX" ? <Badge tone="warning">Sandbox (Simulated)</Badge> : <Badge tone="success">{i.mode === "LIVE" ? "Live" : "Local development"}</Badge>;
  if (i.status === "DEGRADED") return <Badge tone="warning">Degraded</Badge>;
  return <Badge tone="neutral">Not configured</Badge>;
}

function SystemView() {
  const [data, setData] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<SystemHealth>("/admin/system/health").then(setData, (e) => setError(e instanceof ApiError ? e.message : "Failed to load system status."));
  }, []);
  if (error) return <Alert tone="error">{error}</Alert>;
  if (!data) return <Spinner />;
  const db = data.database as { connected?: boolean; migration?: string; head?: string; migrations_current?: boolean };
  return (
    <>
      <PageHeader title="System status" description="Live health of platform dependencies and external integrations." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Platform" />
          <dl className="divide-y divide-slate-100 text-sm">
            <Item label="Overall">{data.status === "healthy" ? <Badge tone="success">Healthy</Badge> : <Badge tone="danger">{data.status}</Badge>}</Item>
            <Item label="Environment">{data.app_env}</Item>
            <Item label="Version">{data.version}</Item>
            <Item label="Database">{db.connected ? <Badge tone="success">Connected</Badge> : <Badge tone="danger">Unavailable</Badge>}</Item>
            <Item label="Schema">
              <span className="font-mono text-xs">{db.migration ?? "—"}</span>{" "}
              {db.migrations_current ? <Badge tone="success">Current</Badge> : <Badge tone="warning">Pending migration</Badge>}
            </Item>
          </dl>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Integrations" description="Providers without credentials are reported as not configured. Nothing is simulated." />
          <ul className="divide-y divide-slate-100">
            {data.integrations.map((i) => (
              <li key={i.key} className="flex flex-wrap items-start justify-between gap-3 px-5 py-3 text-sm">
                <div className="max-w-md">
                  <p className="font-medium text-slate-900">{i.name}</p>
                  <p className="text-slate-500">{i.detail}</p>
                </div>
                {statusBadge(i)}
              </li>
            ))}
          </ul>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title="Email deliveries (last 24 hours)" />
          <div className="flex flex-wrap gap-6 px-5 py-4 text-sm">
            {Object.keys(data.email_deliveries_last_24h).length === 0 ? (
              <p className="text-slate-500">No emails in the last 24 hours.</p>
            ) : (
              Object.entries(data.email_deliveries_last_24h).map(([k, v]) => (
                <div key={k}>
                  <p className="text-slate-500">{k}</p>
                  <p className="text-xl font-semibold text-slate-900">{v}</p>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-900">{children}</dd>
    </div>
  );
}
