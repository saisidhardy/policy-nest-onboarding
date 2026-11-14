"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { KeyRound, ShieldCheck, Smartphone } from "lucide-react";
import { AuthShell } from "@/components/AuthShell";
import { PasswordField } from "@/components/PasswordField";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { safeNext } from "@/lib/format";

interface OtpSendResponse {
  success: boolean;
  delivery_channel: string;
  destination_masked: string;
  message: string;
  cooldown_seconds: number;
}

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

  // OTP mode state
  const [identifier, setIdentifier] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpNotice, setOtpNotice] = useState<string | null>(null);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [sendingOtp, setSendingOtp] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);

  useEffect(() => {
    if (!loading && me) router.replace(next);
  }, [loading, me, next, router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((c) => (c > 1 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

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

  async function onSendOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!identifier.trim()) return;
    setOtpError(null);
    setSendingOtp(true);
    try {
      const res = await api<OtpSendResponse>("/auth/otp/send", {
        method: "POST",
        body: { identifier: identifier.trim() },
      });
      setOtpSent(true);
      setOtpNotice(res.message);
      setCooldown(res.cooldown_seconds || 60);
      setOtpCode("");
    } catch (err) {
      setOtpError(err instanceof ApiError ? err.message : "Failed to send code. Please try again.");
    } finally {
      setSendingOtp(false);
    }
  }

  async function onVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!otpCode.trim()) return;
    setOtpError(null);
    setVerifyingOtp(true);
    try {
      await api("/auth/otp/verify", {
        method: "POST",
        body: { identifier: identifier.trim(), code: otpCode.trim() },
      });
      await refresh();
      router.replace(next);
    } catch (err) {
      setOtpError(err instanceof ApiError ? err.message : "Verification failed. Please check the code.");
      setVerifyingOtp(false);
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
          {otpError && <Alert tone="error">{otpError}</Alert>}
          {otpNotice && <Alert tone="success">{otpNotice}</Alert>}

          {!otpSent ? (
            <form onSubmit={onSendOtp} className="space-y-4">
              <Field
                label="Email or Indian Mobile Number"
                htmlFor="identifier"
                hint="Enter your registered email address or 10-digit mobile number (+91)."
              >
                <Input
                  id="identifier"
                  type="text"
                  placeholder="e.g. candidate@example.com or 9876543210"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  autoComplete="username"
                  required
                />
              </Field>

              <Button type="submit" className="w-full" loading={sendingOtp} disabled={!identifier.trim()}>
                Send Verification Code
              </Button>
            </form>
          ) : (
            <form onSubmit={onVerifyOtp} className="space-y-4">
              <Field
                label="6-Digit Verification Code"
                htmlFor="otpCode"
                hint={`Code dispatched to ${identifier}. Valid for 10 minutes.`}
              >
                <Input
                  id="otpCode"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="Enter 6-digit code"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                  autoComplete="one-time-code"
                  className="text-center font-mono text-lg tracking-widest"
                  required
                />
              </Field>

              <Button
                type="submit"
                className="w-full"
                loading={verifyingOtp}
                disabled={otpCode.trim().length !== 6}
              >
                Verify & Continue
              </Button>

              <div className="flex items-center justify-between text-xs text-slate-500">
                <button
                  type="button"
                  onClick={() => {
                    setOtpSent(false);
                    setOtpNotice(null);
                    setOtpError(null);
                    setOtpCode("");
                  }}
                  className="font-medium text-slate-700 hover:underline"
                >
                  Change Email / Phone
                </button>
                <button
                  type="button"
                  onClick={onSendOtp}
                  disabled={cooldown > 0 || sendingOtp}
                  className={`font-medium ${
                    cooldown > 0 ? "text-slate-400" : "text-brand-700 hover:underline"
                  }`}
                >
                  {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </AuthShell>
  );
}
