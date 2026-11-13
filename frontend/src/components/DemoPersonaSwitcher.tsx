"use client";

import { ChevronDown, ChevronUp, ExternalLink, LogOut, ShieldCheck, Sparkles, User, UserCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface DemoPersona {
  label: string;
  role: string;
  email: string;
  route: string;
  description: string;
}

const DEMO_PERSONAS: DemoPersona[] = [
  {
    label: "STP Applicant",
    role: "Candidate",
    email: "posp_stp@policynest.demo",
    route: "/app",
    description: "Auto-approved POSP candidate",
  },
  {
    label: "Reviewer Desk",
    role: "Operations",
    email: "reviewer@policynest.demo",
    route: "/app/review",
    description: "SLA review queue & doc inspect",
  },
  {
    label: "Compliance Admin",
    role: "Admin",
    email: "admin@policynest.demo",
    route: "/app/admin/audit",
    description: "Regulatory audit export & logs",
  },
];

export function DemoPersonaSwitcher() {
  const router = useRouter();
  const { me, refresh, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [switching, setSwitching] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function switchPersona(persona: DemoPersona) {
    setSwitching(persona.email);
    setErrorMsg(null);
    try {
      await api("/auth/login", {
        method: "POST",
        body: {
          email: persona.email,
          password: "Demo@PolicyNest2026!",
        },
      });
      await refresh();
      router.push(persona.route);
    } catch {
      setErrorMsg(`Failed to switch to ${persona.label}. Ensure demo scenarios are seeded.`);
    } finally {
      setSwitching(null);
    }
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 print:hidden font-sans">
      {!isOpen ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2 rounded-full bg-slate-900/95 px-3.5 py-2 text-xs font-semibold text-white shadow-lg ring-1 ring-white/20 backdrop-blur transition hover:bg-slate-800"
        >
          <Sparkles className="h-3.5 w-3.5 text-amber-400" />
          <span>Demo Personas</span>
          {me && (
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">
              {me.user.role.code}
            </span>
          )}
          <ChevronUp className="h-3 w-3 text-slate-400" />
        </button>
      ) : (
        <div className="w-80 rounded-2xl bg-white p-4 shadow-2xl ring-1 ring-slate-900/10">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-900">Demo Persona Switcher</p>
                <p className="text-[10px] text-slate-500">1-click login for evaluation</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>

          {me && (
            <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-2 text-xs">
              <div className="min-w-0 flex-1 pr-2">
                <p className="truncate font-semibold text-slate-800">{me.user.email}</p>
                <span className="inline-block rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-medium text-brand-800">
                  {me.user.role.code}
                </span>
              </div>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.push("/login");
                }}
                className="flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium text-rose-600 hover:bg-rose-50"
              >
                <LogOut className="h-3 w-3" />
                Sign out
              </button>
            </div>
          )}

          {errorMsg && (
            <p className="mt-2 rounded bg-rose-50 p-2 text-[11px] text-rose-700">{errorMsg}</p>
          )}

          <div className="mt-3 space-y-1.5">
            {DEMO_PERSONAS.map((p) => {
              const isCurrent = me?.user.email.toLowerCase() === p.email.toLowerCase();
              const isLoading = switching === p.email;
              return (
                <button
                  key={p.email}
                  type="button"
                  disabled={isLoading}
                  onClick={() => switchPersona(p)}
                  className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-xs transition ${
                    isCurrent
                      ? "border-brand-500 bg-brand-50/50 text-brand-900"
                      : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {p.role === "Candidate" && <User className="h-3.5 w-3.5 text-blue-600" />}
                    {p.role === "Operations" && <UserCheck className="h-3.5 w-3.5 text-amber-600" />}
                    {p.role === "Admin" && <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />}
                    <div>
                      <p className="font-semibold text-slate-900">{p.label}</p>
                      <p className="text-[10px] text-slate-500">{p.description}</p>
                    </div>
                  </div>
                  {isLoading ? (
                    <span className="text-[10px] text-slate-400">Loading...</span>
                  ) : isCurrent ? (
                    <span className="text-[10px] font-bold text-brand-700">Active</span>
                  ) : (
                    <span className="text-[10px] font-medium text-slate-400 group-hover:text-slate-600">Switch →</span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="mt-3 border-t border-slate-100 pt-2">
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                router.push("/verify-certificate?number=POSP-2026-CERT-8841");
              }}
              className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[11px] font-medium text-slate-600 hover:bg-slate-50"
            >
              <span>Verify IRDAI Certificate</span>
              <ExternalLink className="h-3 w-3 text-slate-400" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
