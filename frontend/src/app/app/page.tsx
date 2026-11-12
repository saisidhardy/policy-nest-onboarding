"use client";

import { ArrowRight, Bell, CheckCircle2, FileCheck2, FolderKanban, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApplicationStatusBadge } from "@/components/onboarding/ApplicationTracker";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REQUIRED_DOCUMENTS, WIZARD_STEPS } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import type { AdminStats, ApplicationDetail, Me, NotificationsPage } from "@/lib/types";
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
      {me.user.role.code === "ADMIN" ? (
        <AdminOverview />
      ) : me.user.role.code === "APPLICANT" ? (
        <ApplicantDashboard me={me} />
      ) : (
        <StaffOverview me={me} />
      )}
    </>
  );
}

function ApplicantDashboard({ me }: { me: Me }) {
  const router = useRouter();
  const [app, setApp] = useState<ApplicationDetail | null | undefined>(undefined);
  const [notifications, setNotifications] = useState<NotificationsPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    api<NotificationsPage>("/notifications", { query: { page_size: 4 } }).then(setNotifications, () => {});
    if (!me.user.email_verified) {
      setApp(null);
      return;
    }
    api<ApplicationDetail | null>("/applications/current").then(setApp, (e) => {
      setError(e instanceof ApiError ? e.message : "Failed to load your application.");
      setApp(null);
    });
  }, [me.user.email_verified]);

  async function startApplication() {
    setStarting(true);
    setError(null);
    try {
      const created = await api<ApplicationDetail>("/applications", { method: "POST", body: {} });
      router.push(`/app/onboarding/${created.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to start onboarding application.");
      setStarting(false);
    }
  }

  const currentStepTitle = app ? (WIZARD_STEPS.find((s) => s.step === app.current_step)?.title ?? `Step ${app.current_step}`) : "";

  return (
    <div className="space-y-6">
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="POSP Onboarding Application"
            description="Complete your profile sections and upload all 6 statutory documents."
            action={app ? <ApplicationStatusBadge status={app.status} /> : undefined}
          />
          <div className="p-5">
            {app === undefined ? (
              <Spinner label="Loading application" />
            ) : !me.user.email_verified ? (
              <div className="space-y-3 text-sm text-slate-600">
                <p>Verify your email address using the link sent to <strong>{me.user.email}</strong> to unlock application creation and document uploads.</p>
                <p>Meanwhile, you can update your profile and preferred language under Account &amp; security.</p>
                <Link
                  href="/app/account"
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 hover:bg-slate-50"
                >
                  Manage profile
                </Link>
              </div>
            ) : !app ? (
              <div className="space-y-4">
                <p className="text-sm text-slate-600">
                  Start your IRDAI Point of Sales Person (POSP) onboarding application. You can save your progress as a draft at any step and resume anytime.
                </p>
                <ul className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                  {REQUIRED_DOCUMENTS.map((doc) => (
                    <li key={doc.type} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                      <FileCheck2 className="h-4 w-4 text-brand-700" />
                      <span>{doc.label}</span>
                    </li>
                  ))}
                </ul>
                <Button onClick={startApplication} loading={starting}>
                  <PlayCircle className="h-4 w-4" /> Start POSP application
                </Button>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50 p-4">
                  <div>
                    <p className="text-xs font-medium text-slate-500">Reference ID</p>
                    <p className="text-lg font-semibold text-slate-900">{app.reference_code}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500">Progress</p>
                    <p className="text-sm font-semibold text-slate-900">
                      {app.completeness.completed_sections}/{app.completeness.total_sections} sections ·{" "}
                      {app.completeness.uploaded_document_count}/{app.completeness.required_document_count} documents
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500">Last saved</p>
                    <p className="text-sm text-slate-700">{formatDateTime(app.last_saved_at)}</p>
                  </div>
                </div>

                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-brand-700 transition-all"
                    style={{ width: `${Math.round((app.completeness.completed_sections / app.completeness.total_sections) * 100)}%` }}
                  />
                </div>

                {app.status === "DRAFT" || app.status === "NEEDS_MORE_INFO" ? (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-slate-600">
                      Resume at <strong>Step {app.current_step}: {currentStepTitle}</strong>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Link
                        href={`/app/applications/${app.id}`}
                        className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 hover:bg-slate-50"
                      >
                        <FolderKanban className="h-4 w-4" /> View details &amp; history
                      </Link>
                      <Link
                        href={`/app/onboarding/${app.id}`}
                        className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-800"
                      >
                        Resume application <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm text-emerald-800">
                      <CheckCircle2 className="h-4 w-4" />
                      <span>Submitted on {formatDateTime(app.submitted_at)}.</span>
                    </div>
                    <Link
                      href={`/app/applications/${app.id}`}
                      className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-800"
                    >
                      Track status &amp; history <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Notifications"
              action={
                <Link href="/app/notifications" className="text-xs font-medium text-brand-700 hover:underline">
                  View all
                </Link>
              }
            />
            {!notifications ? (
              <Spinner />
            ) : notifications.items.length === 0 ? (
              <p className="px-5 py-6 text-sm text-slate-500">No notifications yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {notifications.items.map((n) => (
                  <li key={n.id} className="px-5 py-3 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-slate-900">{n.title}</p>
                      {!n.is_read && <Badge tone="brand">New</Badge>}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-xs text-slate-600">{n.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Account summary"
              action={
                <Link href="/app/account" className="text-xs font-medium text-brand-700 hover:underline">
                  Edit
                </Link>
              }
            />
            <dl className="divide-y divide-slate-100 text-xs">
              <Row label="Email">
                {me.user.email}{" "}
                {me.user.email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Unverified</Badge>}
              </Row>
              <Row label="Mobile">{me.user.mobile ?? "Not provided"}</Row>
              <Row label="Language">{me.user.preferred_language === "HI" ? "Hindi" : "English"}</Row>
            </dl>
          </Card>
        </div>
      </div>
    </div>
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
          <CardHeader
            title="Recent activity"
            action={
              <Link href="/app/admin/audit" className="text-sm font-medium text-brand-700 hover:underline">
                View audit log
              </Link>
            }
          />
          <AuditTable items={stats.recent_audit} compact />
        </Card>
      </div>
    </div>
  );
}

const STAFF_STAGES: Record<string, { title: string; body: string }> = {
  REVIEWER: {
    title: "Document intelligence desk",
    body: "Inspect OCR extractions, CV image quality, redacted Aadhaar previews, cross-document checks, and correct extracted fields. Full decision routing arrives in Phase 5.",
  },
  SENIOR_REVIEWER: {
    title: "Document intelligence & escalations",
    body: "Inspect regional applications, OCR extractions, redacted Aadhaar copies, and extracted field corrections. Escalation decisions arrive in Phase 5.",
  },
};

function StaffOverview({ me }: { me: Me }) {
  const stage = STAFF_STAGES[me.user.role.code];
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
          <Row label="Region scope">{me.user.region ?? <span className="text-slate-400">Not assigned</span>}</Row>
          <Row label="Clearance level">{me.user.clearance_level}</Row>
          <Row label="Session expires">{formatDateTime(me.session_expires_at)}</Row>
        </dl>
      </Card>
      {stage && (
        <Card>
          <CardHeader title={stage.title} />
          <div className="space-y-3 px-5 py-4 text-sm text-slate-600">
            <Badge tone="brand">Phase 3 Live</Badge>
            <p>{stage.body}</p>
            <div className="flex flex-col gap-2 pt-1">
              <Link
                href="/app/review"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
              >
                <FileCheck2 className="h-4 w-4" /> Open document review desk <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link href="/app/notifications" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:underline">
                <Bell className="h-4 w-4" /> Notifications
              </Link>
            </div>
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
      <dd className="col-span-2 text-slate-900">{children}</dd>
    </div>
  );
}
