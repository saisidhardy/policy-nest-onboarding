"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { PasswordField } from "@/components/PasswordField";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuthConfig } from "@/lib/useAuthConfig";

export function RegisterForm() {
  const router = useRouter();
  const { me, loading, refresh } = useAuth();
  const config = useAuthConfig();
  const [form, setForm] = useState({ full_name: "", email: "", mobile: "", password: "", accept_terms: false });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && me) router.replace("/app");
  }, [loading, me, router]);

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    setSubmitting(true);
    try {
      await api("/auth/register", { method: "POST", body: { ...form, mobile: form.mobile || null } });
      await refresh();
      router.replace("/app?welcome=1");
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors(err.fieldErrors);
        setError(err.message);
      } else {
        setError("Registration failed. Please try again.");
      }
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your applicant account"
      subtitle="You'll verify your email next. Staff accounts are created by an administrator."
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className="font-medium text-brand-700 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        <div className="rounded-md border border-slate-200 bg-slate-50/80 p-3 text-xs text-slate-600">
          <span className="font-semibold text-slate-800">Candidate Onboarding Only:</span> This registration form is strictly for POSP applicants. Verification Officers, Operations Executives, and Supervisors are provisioned directly by the Platform Tech Team.
        </div>
        {error && <Alert tone="error">{error}</Alert>}
        {config && !config.email_delivery_configured && (
          <Alert tone="warning" title="Email delivery is not configured">
            Your account will be created, but the verification email cannot be sent until an administrator configures email delivery.
          </Alert>
        )}
        <Field label="Full name (as on PAN)" htmlFor="full_name" error={fieldErrors.full_name}>
          <Input id="full_name" autoComplete="name" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} invalid={!!fieldErrors.full_name} required />
        </Field>
        <Field label="Email" htmlFor="email" error={fieldErrors.email}>
          <Input id="email" type="email" autoComplete="email" value={form.email} onChange={(e) => set("email", e.target.value)} invalid={!!fieldErrors.email} required />
        </Field>
        <Field label="Mobile number (optional)" htmlFor="mobile" error={fieldErrors.mobile} hint="10-digit Indian mobile number">
          <Input id="mobile" type="tel" inputMode="tel" autoComplete="tel-national" value={form.mobile} onChange={(e) => set("mobile", e.target.value)} invalid={!!fieldErrors.mobile} />
        </Field>
        <PasswordField
          id="password"
          label="Password"
          value={form.password}
          onChange={(v) => set("password", v)}
          autoComplete="new-password"
          error={fieldErrors.password}
          showChecks
          minLength={config?.password_min_length}
        />
        <div className="space-y-1.5">
          <label className="flex items-start gap-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={form.accept_terms}
              onChange={(e) => set("accept_terms", e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700"
            />
            <span>I agree to the terms of use and consent to PolicyNest processing my details for POSP onboarding.</span>
          </label>
          {fieldErrors.accept_terms && <p className="text-sm text-red-700">{fieldErrors.accept_terms}</p>}
        </div>
        <Button type="submit" className="w-full" loading={submitting} disabled={!form.accept_terms}>
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
