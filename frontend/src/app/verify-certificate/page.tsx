"use client";

import { CheckCircle2, Printer, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { LanguageToggle } from "@/components/LanguageToggle";
import { Alert, Badge, Button, Card, Field, Input, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { CertificateVerification } from "@/lib/types";

export default function VerifyCertificatePage() {
  const [number, setNumber] = useState("");
  const [result, setResult] = useState<CertificateVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function verify(value: string) {
    const normalized = value.trim().toUpperCase();
    if (!normalized) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api<CertificateVerification>(
        `/training/certificates/${encodeURIComponent(normalized)}`
      );
      setResult(res);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 404
          ? `Certificate "${normalized}" was not found in the national registry. Please check the code printed on the document.`
          : err instanceof Error
          ? err.message
          : "Certificate could not be verified."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      const initial = new URLSearchParams(window.location.search).get("number") ?? "";
      if (initial) {
        setNumber(initial);
        void verify(initial);
      }
    }
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    void verify(number);
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-2xl space-y-6">
        {/* Navigation & Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-4 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-700 text-white font-bold shadow">
              PN
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                PolicyNest
              </span>
              <span className="ml-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                POSP Registry
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <LanguageToggle />
            <Link
              href="/"
              className="text-xs font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-400"
            >
              Home
            </Link>
          </div>
        </div>

        {/* Verification Card */}
        <Card className="p-6 shadow-sm">
          <div className="mb-4">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Verify POSP Training Certificate
            </h1>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Enter the unique certificate registration code printed on the candidate&apos;s completion certificate or scan the QR code. No sign-in required.
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <Field label="Certificate Number" htmlFor="cert-number" hint="e.g. POSP-2026-CERT-8841">
              <div className="relative">
                <Input
                  id="cert-number"
                  required
                  autoComplete="off"
                  placeholder="POSP-2026-CERT-..."
                  value={number}
                  onChange={(e) => setNumber(e.target.value.toUpperCase())}
                  className="font-mono uppercase tracking-wider pr-10"
                />
                <Search className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
              </div>
            </Field>

            <div className="flex gap-2">
              <Button type="submit" loading={loading} className="w-full sm:w-auto">
                <ShieldCheck className="h-4 w-4" />
                Verify Certificate
              </Button>
              {number && (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setNumber("");
                    setResult(null);
                    setError(null);
                  }}
                >
                  Clear
                </Button>
              )}
            </div>
          </form>
        </Card>

        {loading && (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        )}

        {error && (
          <Alert tone="error">
            <div className="flex items-start gap-2">
              <ShieldAlert className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          </Alert>
        )}

        {/* Certificate Verification Details Card */}
        {result && (
          <Card className="overflow-hidden border-2 border-emerald-500/40 p-6 shadow-md dark:border-emerald-500/30">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-emerald-700 uppercase tracking-wider dark:text-emerald-400">
                    Official Verification Verified
                  </div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                    {result.candidate_name}
                  </div>
                </div>
              </div>
              <Badge tone={result.status === "ACTIVE" ? "success" : "danger"}>
                {result.status === "ACTIVE" ? "VALID & ACTIVE" : result.status}
              </Badge>
            </div>

            <dl className="mt-4 grid gap-4 text-xs sm:grid-cols-2">
              <div>
                <dt className="text-slate-500 dark:text-slate-400">Certificate Code</dt>
                <dd className="mt-1 font-mono font-bold text-slate-900 dark:text-white">
                  {result.certificate_number}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500 dark:text-slate-400">Authorized Candidate</dt>
                <dd className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {result.candidate_name}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500 dark:text-slate-400">Mandatory Course</dt>
                <dd className="mt-1 font-medium text-slate-800 dark:text-slate-200">
                  {result.course_title} ({result.course_code})
                </dd>
              </div>

              <div>
                <dt className="text-slate-500 dark:text-slate-400">Completed Training & Exam</dt>
                <dd className="mt-1 font-medium text-slate-800 dark:text-slate-200">
                  {result.completed_hours} Hours • Score: {result.exam_score_pct ? `${result.exam_score_pct}%` : "Passed"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500 dark:text-slate-400">Issued Date</dt>
                <dd className="mt-1 font-medium text-slate-800 dark:text-slate-200">
                  {new Date(result.issued_at).toLocaleDateString("en-IN", {
                    day: "2-digit",
                    month: "long",
                    year: "numeric",
                  })}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500 dark:text-slate-400">Validity Expiration</dt>
                <dd className="mt-1 font-medium text-slate-800 dark:text-slate-200">
                  {result.valid_until
                    ? new Date(result.valid_until).toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                      })
                    : "Standard 3-Year Regulatory Term"}
                </dd>
              </div>

              <div className="sm:col-span-2 rounded-lg bg-slate-100 p-3 font-mono text-[11px] text-slate-600 dark:bg-slate-900 dark:text-slate-400">
                <span className="font-semibold block text-slate-700 dark:text-slate-300">
                  Cryptographic Integrity Seal:
                </span>
                <span className="break-all">{result.seal_sha256}</span>
              </div>
            </dl>

            <div className="mt-5 flex justify-end gap-2 border-t border-slate-200 pt-4 dark:border-slate-800">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  if (typeof window !== "undefined") window.print();
                }}
              >
                <Printer className="h-3.5 w-3.5" />
                Print Verification Record
              </Button>
            </div>
          </Card>
        )}

        <Alert tone="info">
          <div className="text-xs text-slate-600 dark:text-slate-300">
            <strong>Statutory Disclosure:</strong> This public register verifies successful completion of the IRDAI mandatory 15-hour Point of Sales Person (POSP) training and assessment pursuant to the Insurance Regulatory and Development Authority of India guidelines.
          </div>
        </Alert>
      </div>
    </main>
  );
}
