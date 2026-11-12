"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Alert, Badge, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { AdminStats, Me } from "@/lib/types";
import { AuditTable } from "./admin/audit/AuditTable";

export default function OverviewPage() {
  return (
    <Suspense>
      <Overview />
    </Suspense>
  );
}

function Overview() {
  const { me } = useAuth();
  const welcome = useSearchParams().get("welcome") === "1";
  if (!me) return null;
  const firstName = me.user.full_name.split(" ")[0];
  return (
    <>
      <PageHeader title={`Welcome, ${firstName}`} description={`Signed in as ${me.user.role.name}.`} />
      {welcome && (
        <Alert tone="success" className="mb-6" title="Account created">
          Your applicant account is ready. Verify your email to continue.
        </Alert>
      )}
      {me.user.role.code === "ADMIN" ? <AdminOverview /> : <MemberOverview me={me} />}
    </>
  );
}

function Stat({ label, value, href }: { label: string; value: number | string; href?: string }) {
  const body = (
    <Card className="p-5 transition hover:border-brand-200">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

function AdminOverview() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<AdminStats>("/admin/stats").then(setStats, (e) => setError(e instanceof ApiError ? e.message : "Failed to load statistics."));
  }, []);
  if (error) return <Alert tone="error">{error}</Alert>;
  if (!stats) return <Spinner />;
  const total = Object.values(stats.users_by_role).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total users" value={total} href="/app/admin/users" />
        <Stat label="Active sessions" value={stats.active_sessions} />
        <Stat label="Registrations (7 days)" value={stats.registrations_last_7_days} />
        <Stat label="Failed sign-ins (24h)" value={stats.failed_logins_last_24h} href="/app/admin/audit?action=auth.login&outcome=FAILURE" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Users by role" />
          <dl className="divide-y divide-slate-100">
            {Object.entries(stats.users_by_role).map(([role, n]) => (
              <div key={role} className="flex justify-between px-5 py-3 text-sm">
                <dt className="text-slate-600">{role.replace("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</dt>
                <dd className="font-medium text-slate-900">{n}</dd>
              </div>
            ))}
            <div className="flex justify-between px-5 py-3 text-sm">
              <dt className="text-slate-600">Unverified email</dt>
              <dd className="font-medium text-slate-900">{stats.unverified_users}</dd>
            </div>
            <div className="flex justify-between px-5 py-3 text-sm">
              <dt className="text-slate-600">Pending invitations</dt>
              <dd className="font-medium text-slate-900">{stats.pending_invitations}</dd>
            </div>
            <div className="flex justify-between px-5 py-3 text-sm">
              <dt className="text-slate-600">Deactivated</dt>
              <dd className="font-medium text-slate-900">{stats.inactive_users}</dd>
            </div>
          </dl>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Recent activity" action={<Link href="/app/admin/audit" className="text-sm font-medium text-brand-700 hover:underline">View audit log</Link>} />
          <AuditTable items={stats.recent_audit} compact />
        </Card>
      </div>
    </div>
  );
}

const STAGES: Record<string, { title: string; body: string }> = {
  APPLICANT: {
    title: "Onboarding application",
    body: "Create your application, upload the six required documents, submit for review, then complete training and the assessment.",
  },
  REVIEWER: {
    title: "Review queue",
    body: "Open the review queue to inspect, correct, approve, reject or escalate applications within your assigned scope.",
  },
  SENIOR_REVIEWER: {
    title: "Escalations and fraud desk",
    body: "Open the review queue to handle escalated and higher-sensitivity cases within your clearance.",
  },
};

function MemberOverview({ me }: { me: Me }) {
  const stage = STAGES[me.user.role.code];
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader title="Account status" />
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label="Email">
            {me.user.email} {me.user.email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Not verified</Badge>}
          </Row>
          <Row label="Mobile">{me.user.mobile ?? <span className="text-slate-400">Not provided</span>}</Row>
          <Row label="Role">{me.user.role.name}</Row>
          {me.user.role.code !== "APPLICANT" && (
            <>
              <Row label="Region scope">{me.user.region ?? <span className="text-slate-400">Not assigned</span>}</Row>
              <Row label="Clearance level">{me.user.clearance_level}</Row>
            </>
          )}
          <Row label="Session expires">{formatDateTime(me.session_expires_at)}</Row>
        </dl>
      </Card>
      {stage && (
        <Card>
          <CardHeader title={stage.title} />
          <div className="space-y-3 px-5 py-4 text-sm text-slate-600">
            <Badge tone="success">Available</Badge>
            <p>{stage.body}</p>
          </div>
        </Card>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-4 px-5 py-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2 flex flex-wrap items-center gap-2 text-slate-900">{children}</dd>
    </div>
  );
}
