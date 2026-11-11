"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ApplicationTracker } from "@/components/onboarding/ApplicationTracker";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { Alert, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { ApplicationDetail } from "@/lib/types";

export default function OnboardingApplicationPage() {
  return (
    <RequirePermission permission="application:create">
      <OnboardingLoader />
    </RequirePermission>
  );
}

function OnboardingLoader() {
  const { id } = useParams<{ id: string }>();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api<ApplicationDetail>(`/applications/${id}`);
      setApp(data);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load onboarding application.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <Alert tone="error">{error}</Alert>
        <Link href="/app" className="text-sm font-medium text-brand-700 hover:underline">
          Back to dashboard
        </Link>
      </div>
    );
  }
  if (!app) return <Spinner label="Loading application" />;

  if (app.status !== "DRAFT" && app.status !== "NEEDS_MORE_INFO") {
    return (
      <div className="space-y-6">
        <PageHeader
          title={`Application ${app.reference_code}`}
          description="This application is locked while in progress or finalized."
          action={
            <Link
              href={`/app/applications/${app.id}`}
              className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              Open full details
            </Link>
          }
        />
        <ApplicationTracker application={app} />
      </div>
    );
  }

  return <OnboardingWizard application={app} onUpdated={setApp} onReload={load} />;
}
