"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, Spinner } from "@/components/ui";
import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import type { CertificateVerification } from "@/lib/types";

export default function VerifyCertificatePage() {
  const [number, setNumber] = useState("");
  const [result, setResult] = useState<CertificateVerification | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function verify(value: string) {
    const normalized = value.trim().toUpperCase();
    if (!normalized) return;
    setLoading(true);
    setMessage(null);
    setResult(null);
    try {
      setResult(await api<CertificateVerification>(`/training/certificates/${encodeURIComponent(normalized)}`));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Certificate could not be verified.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("number") ?? "";
    if (initial) {
      setNumber(initial);
      void verify(initial);
    }
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    void verify(number);
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10">
      <div className="mx-auto max-w-xl space-y-6">
        <div className="flex items-center justify-between"><Logo /><Link className="text-sm font-medium text-brand-700" href="/">Home</Link></div>
        <Card>
          <CardHeader title="Verify a PolicyNest certificate" description="Enter the certificate number printed on the PDF. No sign-in is required." />
          <form className="space-y-4 p-5" onSubmit={submit}>
            <Field label="Certificate number" htmlFor="certificate-number">
              <Input id="certificate-number" required autoComplete="off" placeholder="IRDAI-POSP-2026-..." value={number} onChange={(event) => setNumber(event.target.value.toUpperCase())} />
            </Field>
            <Button type="submit" loading={loading}>Verify certificate</Button>
          </form>
        </Card>
        {loading && <Spinner />}
        {message && <Alert tone="error">{message}</Alert>}
        {result && <Card>
          <CardHeader title="Certificate record" action={<Badge tone={result.status === "ACTIVE" ? "success" : "danger"}>{result.status}</Badge>} />
          <dl className="grid gap-4 p-5 text-sm sm:grid-cols-2">
            <div><dt className="text-slate-500">Certificate</dt><dd className="mt-1 font-medium text-slate-900">{result.certificate_number}</dd></div>
            <div><dt className="text-slate-500">Candidate</dt><dd className="mt-1 font-medium text-slate-900">{result.candidate_name}</dd></div>
            <div><dt className="text-slate-500">Issued</dt><dd className="mt-1 font-medium text-slate-900">{new Date(result.issued_at).toLocaleDateString()}</dd></div>
            <div className="sm:col-span-2"><dt className="text-slate-500">Integrity seal</dt><dd className="mt-1 break-all font-mono text-xs text-slate-700">{result.seal_sha256}</dd></div>
          </dl>
        </Card>}
        <Alert tone="warning">This verifies the PolicyNest training record only. It does not replace authorization by the regulated entity.</Alert>
      </div>
    </main>
  );
}
