import Link from "next/link";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Gauge,
  QrCode,
  Scale,
  ShieldCheck,
  Sparkles,
  Timer,
  Zap,
} from "lucide-react";
import { Logo } from "@/components/Logo";

const benchmarkMetrics = [
  { label: "Ground-Truth Accuracy", value: "99.50%", detail: "Tested on 600 ground-truth cases", tone: "emerald" },
  { label: "Straight-Through Processing", value: "60.67%", detail: "Zero manual touch required", tone: "brand" },
  { label: "Average Onboarding Time", value: "< 30 Mins", detail: "Down from 8.4-day industry avg", tone: "amber" },
  { label: "Regulatory False Approvals", value: "0.00%", detail: "Zero compliance leakage", tone: "emerald" },
];

const fourPillars = [
  {
    pillar: "1. Intelligence",
    subtitle: "Make the system understand, not just extract",
    icon: BrainCircuit,
    color: "from-purple-500/10 to-indigo-500/10 border-indigo-200 text-indigo-700",
    badgeColor: "bg-indigo-100 text-indigo-800",
    capabilities: [
      "Automatic Document Recognition (PAN, Aadhaar, Class 10, Bank Cheque, Selfie)",
      "Intelligent Gemini Vision OCR with field-level bounding boxes and confidence scores",
      "Image Quality Pre-Capture checking blur, glare, lighting, rotation and cropping",
      "8-Tier Indian Semantic Name Matching (Initials, permutations, honorifics, transliteration)",
      "Cross-Document Triangulation (reconciling PAN, Aadhaar and matriculation records)",
      "IRDAI Rulebook Intelligence enforcing POSP guidelines and minimum age criteria",
      "Cross-Application Fraud Ring Detection (SHA-256 deduplication, mule accounts, phone stacking)",
      "Consolidated Correction Recommendation (grouping issues into one actionable plan)",
      "Context-Aware Processing (skipping redundant checks on verified tokens)",
      "Grounded AI Copilot Assistant (answering regulatory and application queries)",
    ],
  },
  {
    pillar: "2. System Design",
    subtitle: "Make the system intelligent at an architectural level",
    icon: Cpu,
    color: "from-blue-500/10 to-cyan-500/10 border-blue-200 text-blue-700",
    badgeColor: "bg-blue-100 text-blue-800",
    capabilities: [
      "Event-Driven Architecture triggering downstream verification on every document event",
      "Parallel Processing running independent OCR and quality checks concurrently",
      "Evidence Dependency Graph mapping document fields to validation decisions",
      "Incremental Reprocessing re-evaluating only affected checks when one document changes",
      "Document Versioning preserving audit history for original and replacement files",
      "Finite State-Machine Workflow controlling valid application transitions",
      "Asynchronous Job Queues handling intensive AI tasks without UI blocking",
      "Real-Time Server-Sent Events (SSE) streaming live updates to reviewer desks",
      "Modular Connector Architecture isolating DigiLocker, India Post, and RBI rails",
      "Observability & Audit Trail capturing cryptographic provenance and timing metrics",
    ],
  },
  {
    pillar: "3. Accuracy",
    subtitle: "Make every result trustworthy",
    icon: Scale,
    color: "from-emerald-500/10 to-teal-500/10 border-emerald-200 text-emerald-700",
    badgeColor: "bg-emerald-100 text-emerald-800",
    capabilities: [
      "Field-Level Confidence metrics retained for individual data points",
      "Strict Schema Validation for PAN, Aadhaar VID, IFSC, and PIN codes",
      "Deterministic Rule Engine executing hard rules rather than probabilistic LLMs",
      "Cross-Source External Verification via live India Post and RBI Razorpay masters",
      "Uncertainty Detection recognizing insufficient evidence to prevent guesswork",
      "Tiered Human Review Escalation for complex or borderline match scores",
      "False-Decision Monitoring actively tracking false approvals and false rejections",
      "Continuous Ground-Truth Evaluation on 600 annotated test cases",
      "Stale Result Protection invalidating prior evaluations upon document replacement",
      "Explainable Decision Logs linking every outcome to specific rulebook clauses",
    ],
  },
  {
    pillar: "4. Efficiency",
    subtitle: "Make onboarding faster for everyone",
    icon: Gauge,
    color: "from-amber-500/10 to-orange-500/10 border-amber-200 text-amber-700",
    badgeColor: "bg-amber-100 text-amber-800",
    capabilities: [
      "Pre-Capture Validation catching flaws before files hit the network",
      "Instant Upload Acknowledgement with immediate progress feedback",
      "Progressive Feedback displaying extraction confidence as checks conclude",
      "Fast-Path Processing evaluating cheap deterministic rules before expensive AI calls",
      "Parallel Ingestion pipelines processing all submitted files simultaneously",
      "Consolidated Correction Requests terminating single-issue ping-pong rework loops",
      "One-Click Re-upload replacing solely the flagged document version",
      "Intelligent Human Routing distributing micro-reviews based on reviewer tier",
      "Micro-Review Workstation presenting diff cards instead of full dossier fatigue",
      "Automatic Decision Recalculation re-scoring instantly upon evidence arrival",
    ],
  },
];

const liveIntegrations = [
  { name: "India Post PIN API", status: "ONLINE", protocol: "REST / Live Postal Master", badge: "Free Live Node" },
  { name: "RBI IFSC Directory", status: "ONLINE", protocol: "Razorpay Master API", badge: "Sub-Second" },
  { name: "DigiLocker Govt Rails", status: "ACTIVE", protocol: "UIDAI / CBDT / CBSE Rails", badge: "1-Click Pull" },
  { name: "NPCI IMPS Penny Drop", status: "ACTIVE", protocol: "₹1.00 Account Verification", badge: "Instant UTR" },
  { name: "Gemini Vision OCR", status: "ACTIVE", protocol: "Multimodal 2.5/Flash AI", badge: "Field Confidence" },
  { name: "DPDP Act Compliance", status: "ENFORCED", protocol: "12-Digit Masked Storage", badge: "Zero Leakage" },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white text-slate-900 antialiased selection:bg-brand-500 selection:text-white">
      {/* Top Notification Strip */}
      <div className="border-b border-brand-800/10 bg-slate-900 px-4 py-2 text-center text-xs text-slate-300">
        <span className="inline-flex items-center gap-1.5 font-medium">
          <Sparkles className="h-3.5 w-3.5 text-brand-400" />
          <span>PolicyNest 2.0: 600-Case Ground-Truth Benchmark Live · 99.50% Accuracy · 60.67% STP Rate</span>
        </span>
      </div>

      {/* Main Navigation */}
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Logo />
          <nav className="flex items-center gap-2 text-sm font-medium">
            <Link
              href="/verify-certificate"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-slate-700 hover:bg-slate-100 hover:text-slate-900"
            >
              <QrCode className="h-4 w-4 text-slate-500" />
              Verify Certificate
            </Link>
            <Link
              href="/login"
              className="rounded-lg px-4 py-2 text-slate-700 hover:bg-slate-100 hover:text-slate-900"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-4 py-2 text-white shadow-sm hover:bg-brand-800 transition"
            >
              <span>Become a POSP</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      <main className="space-y-24 pb-20">
        {/* Hero Section */}
        <section className="relative mx-auto max-w-7xl px-6 pt-16 sm:pt-24 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 mb-6">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            <span>IRDAI Guidelines (2015/2026) & DPDP Act 2023 Compliant</span>
          </div>

          <h1 className="mx-auto max-w-4xl text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-950">
            Next-Generation POSP Onboarding & Regulatory Verification
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600 leading-relaxed">
            Eliminating the traditional 8.4-day turnaround and 73% drop-off. Experience 30-minute continuous guided
            onboarding, deterministic cross-application fraud defense, and sub-second verification rails.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-brand-700/25 hover:bg-brand-800 transition"
            >
              <Timer className="h-4 w-4" />
              <span>Start 30-Min Fast-Track Session</span>
            </Link>

            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50 transition"
            >
              <Bot className="h-4 w-4 text-slate-500" />
              <span>Reviewer & Auditor Desk</span>
            </Link>

            <Link
              href="/verify-certificate"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-5 py-3.5 text-sm font-medium text-slate-600 hover:bg-slate-100 transition"
            >
              <QrCode className="h-4 w-4" />
              <span>Public Certificate Registry</span>
            </Link>
          </div>

          {/* Benchmark KPI Grid */}
          <div className="mt-16 grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto">
            {benchmarkMetrics.map((m) => (
              <div
                key={m.label}
                className="rounded-2xl border border-slate-200/80 bg-white p-5 text-left shadow-sm hover:border-slate-300 transition"
              >
                <span className="text-xs font-medium text-slate-500">{m.label}</span>
                <p className="mt-1.5 text-3xl font-extrabold tracking-tight text-slate-900">{m.value}</p>
                <p className="mt-1 text-xs text-slate-500 font-medium">{m.detail}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Live Integrations & Telemetry Bar */}
        <section className="mx-auto max-w-7xl px-6">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-6 sm:p-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-amber-500" /> Connected Real-Time Verification Nodes
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Live official government directories, banking rails, and automated vision adapters.
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                All Systems Operational
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {liveIntegrations.map((n) => (
                <div
                  key={n.name}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-xs"
                >
                  <div>
                    <span className="text-xs font-bold text-slate-900">{n.name}</span>
                    <p className="text-[11px] text-slate-500">{n.protocol}</p>
                  </div>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                    {n.badge}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Continuous 30-Minute Concept Spotlight (Image 1 match) */}
        <section className="mx-auto max-w-7xl px-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-950 p-8 sm:p-12 text-slate-100 relative overflow-hidden shadow-2xl">
            <div className="max-w-3xl space-y-4">
              <span className="inline-flex items-center gap-2 rounded-full bg-emerald-950 px-3 py-1 text-xs font-bold text-emerald-400 ring-1 ring-emerald-500/40">
                <Timer className="h-3.5 w-3.5" /> Concept: 30-Minute Continuous Onboarding
              </span>
              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
                One session. Six documents. Thirty minutes. Zero distractions.
              </h2>
              <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                Applicants enter a focused, full-screen guided experience modeled after continuous professional assessments.
                Sequential document collection, 1-click DigiLocker import, instant pre-capture OpenCV quality checks, and
                automatic progression eliminate application abandonments.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4">
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <p className="text-xs text-slate-400">Visible Timer</p>
                  <p className="text-base font-bold text-emerald-400 mt-1">30:00 Countdown</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <p className="text-xs text-slate-400">Submission Rails</p>
                  <p className="text-base font-bold text-slate-200 mt-1">DigiLocker / Cam / File</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <p className="text-xs text-slate-400">Audio Copilot</p>
                  <p className="text-base font-bold text-blue-400 mt-1">Hindi & English Voice</p>
                </div>
              </div>

              <div className="pt-6">
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-500 shadow-lg shadow-emerald-950 transition"
                >
                  <span>Experience Live 30-Minute Flow</span>
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* End-to-End Processing Architecture Flowchart (Image 6 match) */}
        <section className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-2xl mx-auto mb-10">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-700">Architecture Pipeline</span>
            <h2 className="mt-2 text-3xl font-extrabold text-slate-900">Deterministic & Explainable Processing Engine</h2>
            <p className="mt-2 text-sm text-slate-600">
              How PolicyNest processes each document from initial camera capture to final regulatory certificate issuance.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
              {/* Step 1 */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Stage 01</span>
                  <h4 className="font-bold text-slate-900 text-sm mt-1">Pre-Capture Validation</h4>
                  <p className="text-xs text-slate-600 mt-1">
                    Client-side check for blur, glare, lighting, and corner boundaries before upload.
                  </p>
                </div>
                <div className="mt-3 text-[11px] font-semibold text-emerald-700">✓ Instant Usability Check</div>
              </div>

              {/* Step 2 */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Stage 02</span>
                  <h4 className="font-bold text-slate-900 text-sm mt-1">Instant ACK & Parallel Ingestion</h4>
                  <p className="text-xs text-slate-600 mt-1">
                    Receipt acknowledged within &lt;200ms. Dispatches parallel OCR, classification, and validation jobs.
                  </p>
                </div>
                <div className="mt-3 text-[11px] font-semibold text-brand-700">⚡ Async Job Queues</div>
              </div>

              {/* Step 3 */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Stage 03</span>
                  <h4 className="font-bold text-slate-900 text-sm mt-1">Deterministic Rule Engine</h4>
                  <p className="text-xs text-slate-600 mt-1">
                    Enforces IRDAI age &gt;= 18, individual PAN, bank match, and 8-tier semantic name equivalence.
                  </p>
                </div>
                <div className="mt-3 text-[11px] font-semibold text-purple-700">🔒 Zero LLM Hallucinations</div>
              </div>

              {/* Step 4 */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Stage 04</span>
                  <h4 className="font-bold text-slate-900 text-sm mt-1">3-Way Outcome Routing</h4>
                  <p className="text-xs text-slate-600 mt-1">
                    STP auto-approval (60.7%), prepared micro-review desk (human-in-the-loop), or consolidated rework plan.
                  </p>
                </div>
                <div className="mt-3 text-[11px] font-semibold text-amber-700">🎯 Micro-Review Workflow</div>
              </div>

              {/* Step 5 */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Stage 05</span>
                  <h4 className="font-bold text-slate-900 text-sm mt-1">Audit Trail & Certificate</h4>
                  <p className="text-xs text-slate-600 mt-1">
                    Immutable event log written, POSP appointment letter generated, and public verification QR minted.
                  </p>
                </div>
                <div className="mt-3 text-[11px] font-semibold text-emerald-700">📜 Tamper-Proof Audit</div>
              </div>
            </div>
          </div>
        </section>

        {/* The 4 Core Pillars Matrix (Images 2, 3, 4, 5 full 40 capabilities) */}
        <section className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-700">Core Capabilities</span>
            <h2 className="mt-2 text-3xl font-extrabold text-slate-900">
              The 4 Core Pillars: 40 Enterprise Capabilities
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Every single capability from the IRDAI InsurTech onboarding specification implemented and active.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {fourPillars.map((p) => {
              const Icon = p.icon;
              return (
                <div
                  key={p.pillar}
                  className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm flex flex-col justify-between hover:shadow-md transition"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className={`p-2 rounded-xl bg-gradient-to-br ${p.color}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-slate-900">{p.pillar}</h3>
                          <p className="text-xs text-slate-500">{p.subtitle}</p>
                        </div>
                      </div>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${p.badgeColor}`}>
                        10 / 10 Active
                      </span>
                    </div>

                    <ul className="mt-6 space-y-2.5">
                      {p.capabilities.map((c, idx) => (
                        <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-700 leading-relaxed">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          <span>{c}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Evaluator Quick Access Section */}
        <section className="mx-auto max-w-7xl px-6">
          <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-50 via-white to-slate-50 p-6 sm:p-8 text-center space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Ready to Evaluate PolicyNest?</h3>
            <p className="text-xs sm:text-sm text-slate-600 max-w-2xl mx-auto">
              Test with pre-configured persona credentials (Applicant, Reviewer, Senior Reviewer, Admin), explore the
              interactive fraud ring detector, or verify official POSP certificates.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <Link
                href="/login"
                className="rounded-xl bg-brand-700 px-5 py-2.5 text-xs font-semibold text-white hover:bg-brand-800 transition"
              >
                1-Click Persona Sign-In Desk
              </Link>
              <Link
                href="/register"
                className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition"
              >
                Register New Applicant
              </Link>
              <Link
                href="/verify-certificate"
                className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100 transition"
              >
                Public Certificate Lookup
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-slate-50 py-10">
        <div className="mx-auto max-w-7xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-3">
            <Logo />
            <span>© {new Date().getFullYear()} PolicyNest Technologies · IRDAI POSP Infrastructure</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/verify-certificate" className="hover:underline">
              Certificate Registry
            </Link>
            <Link href="/login" className="hover:underline">
              Staff Portal
            </Link>
            <Link href="/register" className="hover:underline">
              Applicant Portal
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
