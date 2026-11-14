"use client";

import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  GraduationCap,
  LogOut,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  User,
  UserCheck,
} from "lucide-react";
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
  category: "candidate" | "ops" | "admin";
}

const DEMO_PERSONAS: DemoPersona[] = [
  {
    label: "STP Candidate",
    role: "Candidate",
    email: "posp_stp@policynest.demo",
    route: "/app",
    description: "Auto-approved, 0 mismatch",
    category: "candidate",
  },
  {
    label: "Rework Required",
    role: "Candidate",
    email: "posp_rework@policynest.demo",
    route: "/app",
    description: "Bilingual EN/HI correction checklist",
    category: "candidate",
  },
  {
    label: "Fraud Investigation",
    role: "Candidate",
    email: "posp_fraud@policynest.demo",
    route: "/app",
    description: "Biometric mismatch & fraud flagged",
    category: "candidate",
  },
  {
    label: "Adverse Appeal",
    role: "Candidate",
    email: "posp_appeal@policynest.demo",
    route: "/app",
    description: "Gazetted marriage name appeal",
    category: "candidate",
  },
  {
    label: "LMS In-Progress",
    role: "Candidate",
    email: "posp_training@policynest.demo",
    route: "/app",
    description: "15h training 56% completed",
    category: "candidate",
  },
  {
    label: "Certified POSP",
    role: "Candidate",
    email: "posp_certified@policynest.demo",
    route: "/app",
    description: "Exam 88%, IRDAI certificate issued",
    category: "candidate",
  },
  {
    label: "Reviewer Desk",
    role: "Operations",
    email: "reviewer@policynest.demo",
    route: "/app/review",
    description: "SLA queue, SLA alerts & doc review",
    category: "ops",
  },
  {
    label: "Ops Executive",
    role: "Operations",
    email: "executive@policynest.demo",
    route: "/app/review?tab=escalated",
    description: "Senior escalations & fraud clearance",
    category: "ops",
  },
  {
    label: "Tech Team Admin",
    role: "Admin",
    email: "admin@policynest.demo",
    route: "/app/admin/reviewers",
    description: "Staff provisioning & system config",
    category: "admin",
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

  function getPersonaIcon(persona: DemoPersona) {
    if (persona.category === "admin") return <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />;
    if (persona.category === "ops") return <UserCheck className="h-3.5 w-3.5 text-amber-600" />;
    if (persona.label.includes("Fraud")) return <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />;
    if (persona.label.includes("Rework")) return <RefreshCw className="h-3.5 w-3.5 text-orange-600" />;
    if (persona.label.includes("Appeal")) return <Scale className="h-3.5 w-3.5 text-purple-600" />;
    if (persona.label.includes("LMS")) return <BookOpen className="h-3.5 w-3.5 text-indigo-600" />;
    if (persona.label.includes("Certified")) return <GraduationCap className="h-3.5 w-3.5 text-teal-600" />;
    return <User className="h-3.5 w-3.5 text-blue-600" />;
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
        <div className="w-84 rounded-2xl bg-white p-4 shadow-2xl ring-1 ring-slate-900/10">
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

          <div className="mt-3 max-h-72 overflow-y-auto space-y-1.5 pr-1">
            {DEMO_PERSONAS.map((p) => {
              const isCurrent = me?.user.email.toLowerCase() === p.email.toLowerCase();
              const isLoading = switching === p.email;
              return (
                <button
                  key={p.email}
                  type="button"
                  disabled={isLoading}
                  onClick={() => switchPersona(p)}
                  className={`flex w-full items-center justify-between rounded-lg border px-2.5 py-2 text-left text-xs transition ${
                    isCurrent
                      ? "border-brand-500 bg-brand-50/50 text-brand-900"
                      : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
                    {getPersonaIcon(p)}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold text-slate-900">{p.label}</p>
                      <p className="truncate text-[10px] text-slate-500">{p.description}</p>
                    </div>
                  </div>
                  {isLoading ? (
                    <span className="text-[10px] text-slate-400">Loading...</span>
                  ) : isCurrent ? (
                    <span className="text-[10px] font-bold text-brand-700">Active</span>
                  ) : (
                    <span className="text-[10px] font-medium text-slate-400">Switch →</span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="mt-3 border-t border-slate-100 pt-2 space-y-1">
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
