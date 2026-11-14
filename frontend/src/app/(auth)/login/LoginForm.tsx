"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SignIn } from "@clerk/nextjs";
import { KeyRound, ShieldCheck, Smartphone } from "lucide-react";
import { AuthShell } from "@/components/AuthShell";
import { PasswordField } from "@/components/PasswordField";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { safeNext } from "@/lib/format";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { me, loading, refresh } = useAuth();
  const next = safeNext(params.get("next"));

  // Default mode is password for test suite compatibility; easily switched with prominent tab
  const [mode, setMode] = useState<"password" | "otp">("password");

  // Password mode state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [submittingPassword, setSubmittingPassword] = useState(false);

  useEffect(() => {
    if (!loading && me) router.replace(next);
  }, [loading, me, next, router]);

  async function onPasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setSubmittingPassword(true);
    try {
      await api("/auth/login", { method: "POST", body: { email, password } });
      await refresh();
      router.replace(next);
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Sign-in failed. Please try again.");
      setSubmittingPassword(false);
    }
  }

  return (
    <AuthShell
      title="Sign in to PolicyNest"
      subtitle="Candidates sign in via OTP code; staff sign in with confidential credentials."
      footer={
        <>
          New candidate?{" "}
          <Link href="/register" className="font-medium text-brand-700 hover:underline">
            Create an applicant account
          </Link>
        </>
      }
    >
      {/* Mode switcher tabs */}
      <div className="mb-5 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 text-sm font-medium">
        <button
          type="button"
          onClick={() => setMode("otp")}
          className={`flex items-center justify-center gap-1.5 rounded-md py-2 transition-all ${
            mode === "otp"
              ? "bg-white text-brand-900 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Smartphone className="h-4 w-4" />
          <span>Candidate (OTP)</span>
        </button>
        <button
          type="button"
          onClick={() => setMode("password")}
          className={`flex items-center justify-center gap-1.5 rounded-md py-2 transition-all ${
            mode === "password"
              ? "bg-white text-brand-900 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <KeyRound className="h-4 w-4" />
          <span>Staff Password</span>
        </button>
      </div>

      {params.get("reset") === "1" && (
        <Alert tone="success" className="mb-4">
          Password updated. Sign in with your new password.
        </Alert>
      )}
      {params.get("expired") === "1" && (
        <Alert tone="warning" className="mb-4">
          Your session ended. Sign in again to continue.
        </Alert>
      )}

      {mode === "password" ? (
        <form onSubmit={onPasswordSubmit} className="space-y-5" noValidate>
          <div className="rounded-md border border-slate-200 bg-slate-50/70 p-3 text-xs text-slate-600">
            <div className="flex items-center gap-1.5 font-medium text-slate-800">
              <ShieldCheck className="h-3.5 w-3.5 text-brand-600" />
              <span>Reviewer & Executive Access Notice</span>
            </div>
            <p className="mt-1">
              Staff accounts are provisioned exclusively by the Tech Team. Public registration for staff is disabled.
            </p>
          </div>

          {passwordError && <Alert tone="error">{passwordError}</Alert>}

          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>

          <PasswordField
            id="password"
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />

          <div className="flex justify-end">
            <Link href="/forgot-password" className="text-sm font-medium text-brand-700 hover:underline">
              Forgot password?
            </Link>
          </div>

          <Button type="submit" className="w-full" loading={submittingPassword} disabled={!email || !password}>
            Sign in
          </Button>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="rounded-md border border-brand-200 bg-brand-50/70 p-3 text-xs text-brand-900">
            <div className="flex items-center gap-1.5 font-medium">
              <Smartphone className="h-3.5 w-3.5 text-brand-600" />
              <span>Real Candidate Verification Code</span>
            </div>
            <p className="mt-1">
              Sign in with your registered Indian mobile number (+91) or email address to receive your 6-digit one-time code.
            </p>
          </div>

          <div className="flex justify-center">
            <SignIn
              routing="hash"
              appearance={{
                elements: {
                  rootBox: "w-full",
                  card: "shadow-none border-0 p-0 w-full bg-transparent",
                  headerTitle: "text-base font-semibold text-slate-900",
                  headerSubtitle: "text-xs text-slate-500",
                },
              }}
            />
          </div>
        </div>
      )}
    </AuthShell>
  );
}
