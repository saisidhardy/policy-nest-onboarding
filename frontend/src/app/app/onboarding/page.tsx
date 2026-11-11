"use client";

import { PlayCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Button, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REQUIRED_DOCUMENTS } from "@/lib/constants";
import type { ApplicationDetail } from "@/lib/types";

export default function OnboardingIndexPage() {
  return (
    <RequirePermission permission="application:create">
      <OnboardingEntry />
    </RequirePermission>
  );
}

function OnboardingEntry() {
  const { me } = useAuth();
  const router = useRouter();
  const [current, setCurrent] = useState<ApplicationDetail | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!me?.user.email_verified) {
      setCurrent(null);
      return;
    }
    api<ApplicationDetail | null>("/applications/current").then(
      (app) => {
        if (app && (app.status === "DRAFT" || app.status === "NEEDS_MORE_INFO")) {
          router.replace(`/app/onboarding/${app.id}`);
          return;
        }
        setCurrent(app);
      },
      (e) => {
        setError(e instanceof ApiError ? e.message : "Could not check your application status.");
        setCurrent(null);
      },
    );
  }, [me?.user.email_verified, router]);

  async function startNew() {
    setCreating(true);
    setError(null);
    try {
      const created = await api<ApplicationDetail>("/applications", { method: "POST", body: {} });
      router.replace(`/app/onboarding/${created.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start application.");
      setCreating(false);
    }
  }

  if (current === undefined) return <Spinner label="Checking your application" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="POSP Onboarding"
        description="Complete your details and upload all 6 required documents to submit your application."
      />
      {error && <Alert tone="error">{error}</Alert>}

      {!me?.user.email_verified ? (
        <Alert tone="warning" title="Email verification required">
          Confirm your email address first before starting a POSP onboarding application.
        </Alert>
      ) : current ? (
        <Card>
          <CardHeader title={`Application ${current.reference_code}`} description="Your application has already been submitted." />
          <div className="space-y-4 px-5 py-5 text-sm text-slate-600">
            <p>
              Current status: <strong>{current.status}</strong>. You can view your submitted details, documents, and complete event timeline on the tracking page.
            </p>
            <Link
              href={`/app/applications/${current.id}`}
              className="inline-flex h-10 items-center rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-800"
            >
              Track application
            </Link>
          </div>
        </Card>
      ) : (
        <Card>
          <CardHeader title="Start a new onboarding application" description="Your draft saves automatically at every step so you can resume anytime." />
          <div className="space-y-5 px-5 py-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {REQUIRED_DOCUMENTS.map((doc) => (
                <div key={doc.type} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-900">{doc.label}</p>
                  <p className="mt-1 text-xs text-slate-600">{doc.description}</p>
                </div>
              ))}
            </div>
            <Button onClick={startNew} loading={creating}>
              <PlayCircle className="h-4 w-4" /> Start onboarding application
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
