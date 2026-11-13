import Link from "next/link";
import { FileCheck2, ShieldCheck, ScrollText } from "lucide-react";
import { Logo } from "@/components/Logo";

const pillars = [
  {
    icon: ShieldCheck,
    title: "Role-based access",
    body: "Applicants, reviewers, senior reviewers and administrators each see only what their role and attributes allow. The server enforces every check.",
  },
  {
    icon: FileCheck2,
    title: "Verifiable onboarding",
    body: "Identity, bank and education checks run through authorised provider adapters. When a provider is not configured, the platform says so instead of guessing.",
  },
  {
    icon: ScrollText,
    title: "Audit by default",
    body: "Sign-ins, permission denials and administrative changes are written to an append-only audit log.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Logo />
        <nav className="flex items-center gap-2 text-sm">
          <Link href="/verify-certificate" className="rounded-lg px-3 py-2 font-medium text-slate-700 hover:bg-slate-100">
            Verify Certificate
          </Link>
          <Link href="/login" className="rounded-lg px-4 py-2 font-medium text-slate-700 hover:bg-slate-100">
            Sign in
          </Link>
          <Link href="/register" className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white hover:bg-brand-800">
            Become a POSP
          </Link>
        </nav>
      </header>
      <main>
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-12 sm:pt-20">
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-700">POSP onboarding</p>
          <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            Become a Point of Sales Person with PolicyNest.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-slate-600">
            Create your account and verify your email to start. Document submission, verification and IRDAI training
            open as each onboarding stage goes live.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/register" className="rounded-lg bg-brand-700 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-800">
              Create your account
            </Link>
            <Link href="/login" className="rounded-lg border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-50">
              Staff sign in
            </Link>
          </div>
        </section>
        <section className="border-t border-slate-100 bg-slate-50">
          <div className="mx-auto grid max-w-6xl gap-6 px-6 py-14 md:grid-cols-3">
            {pillars.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-xl border border-slate-200 bg-white p-6">
                <Icon className="h-6 w-6 text-brand-700" aria-hidden />
                <h2 className="mt-4 font-semibold text-slate-900">{title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
      <footer className="mx-auto flex max-w-6xl items-center justify-between px-6 py-8 text-xs text-slate-500">
        <span>© {new Date().getFullYear()} PolicyNest Insurance Broking</span>
        <Link href="/verify-certificate" className="hover:underline">
          Public POSP Certificate Verification Portal
        </Link>
      </footer>
    </div>
  );
}
