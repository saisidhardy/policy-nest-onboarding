"use client";

import { useCallback, useEffect, useState } from "react";
import { PasswordField } from "@/components/PasswordField";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { describeUserAgent, formatDateTime } from "@/lib/format";
import type { LanguageCode, Message, SessionInfo } from "@/lib/types";

export default function AccountPage() {
  return (
    <>
      <PageHeader title="Account & security" description="Manage your profile, language preference, password and signed-in devices." />
      <div className="grid gap-6 lg:grid-cols-2">
        <ProfileCard />
        <PasswordCard />
        <div className="lg:col-span-2">
          <SessionsCard />
        </div>
      </div>
    </>
  );
}

function ProfileCard() {
  const { me, refresh } = useAuth();
  const [fullName, setFullName] = useState(me?.user.full_name ?? "");
  const [mobile, setMobile] = useState(me?.user.mobile ?? "");
  const [preferredLanguage, setPreferredLanguage] = useState<LanguageCode>(me?.user.preferred_language ?? "EN");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (me) {
      setFullName(me.user.full_name);
      setMobile(me.user.mobile ?? "");
      setPreferredLanguage(me.user.preferred_language ?? "EN");
    }
  }, [me]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    setStatus(null);
    try {
      await api("/account/profile", {
        method: "PATCH",
        body: { full_name: fullName, mobile: mobile || null, preferred_language: preferredLanguage },
      });
      await refresh();
      setStatus({ tone: "success", text: "Profile saved." });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        setStatus({ tone: "error", text: err.message });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Profile" description="Your email address can only be changed by an administrator." />
      <form onSubmit={save} className="space-y-4 px-5 py-5" noValidate>
        {status && <Alert tone={status.tone}>{status.text}</Alert>}
        <Field label="Email" htmlFor="profile-email">
          <Input id="profile-email" value={me?.user.email ?? ""} disabled />
        </Field>
        <Field label="Full name" htmlFor="profile-name" error={errors.full_name}>
          <Input id="profile-name" value={fullName} onChange={(e) => setFullName(e.target.value)} invalid={!!errors.full_name} />
        </Field>
        <Field label="Mobile number" htmlFor="profile-mobile" error={errors.mobile} hint="10-digit Indian mobile number. Leave blank to remove.">
          <Input id="profile-mobile" type="tel" value={mobile} onChange={(e) => setMobile(e.target.value)} invalid={!!errors.mobile} />
        </Field>
        <Field label="Preferred notification language" htmlFor="profile-language">
          <Select
            id="profile-language"
            value={preferredLanguage}
            onChange={(e) => setPreferredLanguage(e.target.value as LanguageCode)}
          >
            <option value="EN">English</option>
            <option value="HI">Hindi (हिन्दी)</option>
          </Select>
        </Field>
        <Button type="submit" loading={saving}>
          Save profile
        </Button>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    setStatus(null);
    try {
      const res = await api<Message>("/auth/change-password", { method: "POST", body: { current_password: current, new_password: next } });
      setStatus({ tone: "success", text: res.message });
      setCurrent("");
      setNext("");
    } catch (err) {
      if (err instanceof ApiError) {
        const fe = err.fieldErrors;
        setErrors({ new: fe.password ?? fe.new_password ?? "" });
        setStatus({ tone: "error", text: err.message });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Change password" description="Changing your password signs out your other sessions." />
      <form onSubmit={save} className="space-y-4 px-5 py-5" noValidate>
        {status && <Alert tone={status.tone}>{status.text}</Alert>}
        <PasswordField id="current-password" label="Current password" value={current} onChange={setCurrent} autoComplete="current-password" />
        <PasswordField id="new-password" label="New password" value={next} onChange={setNext} autoComplete="new-password" showChecks error={errors.new || undefined} />
        <Button type="submit" loading={saving} disabled={!current || !next}>
          Update password
        </Button>
      </form>
    </Card>
  );
}

function SessionsCard() {
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api<SessionInfo[]>("/auth/sessions").then(setSessions, (e) => setError(e instanceof ApiError ? e.message : "Failed to load sessions."));
  }, []);
  useEffect(load, [load]);

  async function revoke(id: string) {
    setBusy(id);
    try {
      await api(`/auth/sessions/${id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to sign out session.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader title="Signed-in devices" description="Sessions expire after inactivity or 12 hours, whichever comes first." />
      {error && <Alert tone="error" className="m-5">{error}</Alert>}
      {!sessions ? (
        <Spinner />
      ) : (
        <ul className="divide-y divide-slate-100">
          {sessions.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 text-sm">
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium text-slate-900">{describeUserAgent(s.user_agent)}</p>
                  {s.current && <Badge tone="success">Current session</Badge>}
                </div>
                <p className="mt-0.5 text-slate-500">
                  IP {s.ip_address ?? "unknown"} · Last active {formatDateTime(s.last_seen_at)} · Expires {formatDateTime(s.expires_at)}
                </p>
              </div>
              {!s.current && (
                <Button variant="secondary" size="sm" loading={busy === s.id} onClick={() => revoke(s.id)}>
                  Sign out
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
