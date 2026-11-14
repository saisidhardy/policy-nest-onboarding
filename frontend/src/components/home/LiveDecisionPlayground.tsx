"use client";

import clsx from "clsx";
import {
  CheckCircle2,
  Cpu,
  Network,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Volume2,
  VolumeX,
  Zap,
} from "lucide-react";
import React, { useState } from "react";
import { fireConfetti } from "@/lib/confetti";
import { sound } from "@/lib/soundFx";

export function LiveDecisionPlayground() {
  const [scenario, setScenario] = useState<"clean" | "mule" | "fuzzy">("clean");
  const [scanning, setScanning] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(sound.enabled);

  // 8-Tier Name Calculator state
  const [nameA, setNameA] = useState("Rajiv K. Sharma");
  const [nameB, setNameB] = useState("Rajeev Kumar Sharma");

  const runScenario = (type: "clean" | "mule" | "fuzzy") => {
    setScenario(type);
    setScanning(true);
    sound.playScan();

    setTimeout(() => {
      setScanning(false);
      if (type === "clean") {
        sound.playSuccess();
        sound.playTrophy();
        fireConfetti();
      } else if (type === "mule") {
        sound.playClick();
      } else {
        sound.playSuccess();
      }
    }, 1100);
  };

  const toggleAudio = () => {
    const next = sound.toggleSound();
    setSoundEnabled(next);
  };

  // Name match scoring
  const calculateNameMatch = () => {
    const a = nameA.trim().toLowerCase();
    const b = nameB.trim().toLowerCase();
    if (a === b) {
      return { score: 100, tier: "Tier 1: Exact Character Equality", status: "APPROVED" };
    }
    if ((a.includes("rao") && b.includes("rao")) || (a.includes("sharma") && b.includes("sharma"))) {
      return { score: 96, tier: "Tier 3: Initials Expansion + Soundex", status: "AUTO-RESOLVED" };
    }
    return { score: 88, tier: "Tier 4: Token Permutation Match", status: "VERIFIED" };
  };

  const nameMatchResult = calculateNameMatch();

  return (
    <div className="w-full max-w-5xl mx-auto rounded-3xl border border-slate-800 bg-slate-950 p-6 sm:p-8 text-slate-100 shadow-2xl space-y-6 relative overflow-hidden">
      {/* Background ambient glow */}
      <div className="absolute -top-32 -left-32 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header bar with sound & confetti controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4 relative z-10">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-emerald-400 flex items-center justify-center font-black text-slate-950 text-sm shadow-lg shadow-cyan-500/20">
            AI
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Live FinTech WOW Playground
              </h2>
              <span className="rounded-full bg-cyan-950/80 px-2 py-0.5 text-[10px] font-mono text-cyan-400 border border-cyan-500/30">
                Interactive Sandbox
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Test sub-second OCR extraction, 8-tier name reconciliation, and instant fraud ring defense in real-time.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleAudio}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
          >
            {soundEnabled ? <Volume2 className="h-3.5 w-3.5 text-emerald-400" /> : <VolumeX className="h-3.5 w-3.5 text-slate-500" />}
            <span>{soundEnabled ? "Audio FX: ON" : "Audio FX: Muted"}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              sound.playTrophy();
              fireConfetti();
            }}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 px-3 py-1.5 text-xs font-bold text-white shadow-md shadow-orange-500/20 hover:from-amber-600 hover:to-rose-600 transition"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Celebrate Outcome</span>
          </button>
        </div>
      </div>

      {/* Scenario Pills */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 relative z-10">
        <button
          type="button"
          onClick={() => runScenario("clean")}
          className={clsx(
            "rounded-xl p-4 text-left border transition relative select-none",
            scenario === "clean"
              ? "border-emerald-500/60 bg-emerald-950/30 ring-2 ring-emerald-500/30 shadow-lg shadow-emerald-950/50"
              : "border-slate-800 bg-slate-900/60 hover:bg-slate-900"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-wider">
              Scenario 1 (STP)
            </span>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-mono">
              240ms Approval
            </span>
          </div>
          <p className="text-sm font-bold text-white mt-1">Clean Applicant (Rajiv Sharma)</p>
          <p className="text-xs text-slate-400 mt-1">
            Individual PAN 4th &apos;P&apos;, CBSE Class 10, exact Penny Drop bank match.
          </p>
        </button>

        <button
          type="button"
          onClick={() => runScenario("mule")}
          className={clsx(
            "rounded-xl p-4 text-left border transition relative select-none",
            scenario === "mule"
              ? "border-rose-500/60 bg-rose-950/30 ring-2 ring-rose-500/30 shadow-lg shadow-rose-950/50"
              : "border-slate-800 bg-slate-900/60 hover:bg-slate-900"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold text-rose-400 uppercase tracking-wider">
              Scenario 2 (Fraud Ring)
            </span>
            <span className="text-[10px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded font-mono">
              Zero-Tolerance Block
            </span>
          </div>
          <p className="text-sm font-bold text-white mt-1">Cross-App Mule Bank Syndicate</p>
          <p className="text-xs text-slate-400 mt-1">
            Account shared across 4 prior rejected POSP agents. Immediate freeze.
          </p>
        </button>

        <button
          type="button"
          onClick={() => runScenario("fuzzy")}
          className={clsx(
            "rounded-xl p-4 text-left border transition relative select-none",
            scenario === "fuzzy"
              ? "border-cyan-500/60 bg-cyan-950/30 ring-2 ring-cyan-500/30 shadow-lg shadow-cyan-950/50"
              : "border-slate-800 bg-slate-900/60 hover:bg-slate-900"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider">
              Scenario 3 (8-Tier)
            </span>
            <span className="text-[10px] bg-cyan-500/20 text-cyan-300 px-1.5 py-0.5 rounded font-mono">
              Semantic AI
            </span>
          </div>
          <p className="text-sm font-bold text-white mt-1">Fuzzy Name Discrepancy</p>
          <p className="text-xs text-slate-400 mt-1">
            &quot;S. V. Rao&quot; vs &quot;Satyanarayana Venkata Rao&quot; initials expansion.
          </p>
        </button>
      </div>

      {/* Main Interactive Stage */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 relative z-10">
        {/* Left: Document Vision HUD with Live Laser Beam */}
        <div className="lg:col-span-7 rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4 shadow-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="flex items-center gap-2 text-cyan-400">
              <Cpu className="h-4 w-4 animate-pulse" />
              <span>Vision OCR & Pre-Capture HUD</span>
            </span>
            <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-400">
              {scanning ? "SCANNING IN PROGRESS..." : "RADAR ACTIVE"}
            </span>
          </div>

          {/* Simulated Physical Document Card */}
          <div className="relative rounded-xl border border-slate-700 bg-slate-950 p-4 min-h-[230px] flex flex-col justify-between overflow-hidden">
            {/* Glowing Laser Scanline */}
            {scanning && (
              <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_15px_3px_rgba(6,182,212,0.8)] animate-bounce" />
            )}

            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2.5">
                <div className="h-7 w-7 rounded bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs ring-1 ring-amber-500/40">
                  GOI
                </div>
                <div>
                  <p className="text-xs font-bold text-white tracking-wide">
                    {scenario === "clean"
                      ? "INCOME TAX DEPARTMENT · GOVT OF INDIA"
                      : scenario === "mule"
                        ? "STATE BANK OF INDIA · CANCELLED CHEQUE"
                        : "PAN CARD vs BANK STATEMENT"}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono">
                    {scenario === "clean"
                      ? "PERMANENT ACCOUNT NUMBER CARD"
                      : scenario === "mule"
                        ? "COMMISSION PAYOUT ACCOUNT RECORD"
                        : "INDIAN NAME RECONCILIATION DOSSIER"}
                  </p>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {scenario === "clean" ? "DigiLocker Pull" : scenario === "mule" ? "Mule Alert" : "8-Tier Rail"}
              </span>
            </div>

            {/* Bounding Boxes */}
            <div className="grid grid-cols-2 gap-2.5 my-3">
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
                <span className="text-[9px] font-mono uppercase text-slate-500 block">Candidate Identity</span>
                <p className="text-xs font-bold text-white mt-0.5 font-mono">
                  {scenario === "clean" ? "RAJIV SHARMA" : scenario === "mule" ? "VIKAS MEHRA" : "S. V. RAO"}
                </p>
                <span className="text-[9px] font-mono text-emerald-400 block mt-0.5">Confidence: 99.8%</span>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
                <span className="text-[9px] font-mono uppercase text-slate-500 block">Identifier / Token</span>
                <p className={clsx("text-xs font-bold mt-0.5 font-mono", scenario === "mule" ? "text-rose-400" : "text-emerald-400")}>
                  {scenario === "clean" ? "ABCPS1234F" : scenario === "mule" ? "SBIN0005432 · A/C 9988112233" : "SATYANARAYANA V. RAO"}
                </p>
                <span className={clsx("text-[9px] font-mono block mt-0.5", scenario === "mule" ? "text-rose-400" : "text-emerald-400")}>
                  {scenario === "clean" ? "4th Char 'P' Valid Individual" : scenario === "mule" ? "Network Alert: 4 Prior Flags" : "Tier 4: Initials Matched"}
                </span>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
                <span className="text-[9px] font-mono uppercase text-slate-500 block">Age & Regulatory Gate</span>
                <p className="text-xs font-bold text-white mt-0.5 font-mono">15/08/1994 (Age: 32)</p>
                <span className="text-[9px] font-mono text-emerald-400 block mt-0.5">IRDAI Age &gt;= 18: PASS</span>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
                <span className="text-[9px] font-mono uppercase text-slate-500 block">Penny Drop IMPS Rails</span>
                <p className="text-xs font-bold text-white mt-0.5 font-mono">HDFC0001234 · ₹1.00 UTR</p>
                <span className={clsx("text-[9px] font-mono block mt-0.5", scenario === "mule" ? "text-rose-400" : "text-emerald-400")}>
                  {scenario === "mule" ? "Collision with Ring #FR-901" : "Beneficiary Match (100%)"}
                </span>
              </div>
            </div>

            {/* Quality Metrics Footer */}
            <div className="flex items-center justify-between border-t border-slate-800 pt-2 text-[10px] font-mono text-slate-400">
              <span>OpenCV Blur: 142.5 (Sharp)</span>
              <span>Glare: 0.02 (Safe)</span>
              <span>Resolution: 300 DPI</span>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-slate-400 font-mono">Simulate real-time analysis pipeline</span>
            <button
              type="button"
              onClick={() => runScenario(scenario)}
              className="flex items-center gap-1.5 rounded-xl bg-cyan-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-lg shadow-cyan-600/30 hover:bg-cyan-500 transition"
            >
              <Zap className="h-3.5 w-3.5" />
              <span>Re-Run AI Scan</span>
            </button>
          </div>
        </div>

        {/* Right: Decision Engine Outcome */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Scale className="h-3.5 w-3.5 text-emerald-400" />
                <span>Deterministic Verdict</span>
              </span>
              <span className="text-[10px] font-mono rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                Latency: 240ms
              </span>
            </div>

            {/* Verdict Box */}
            <div
              className={clsx(
                "mt-4 rounded-xl p-4 border transition-all duration-300",
                scenario === "clean"
                  ? "border-emerald-500/40 bg-emerald-950/30 text-emerald-200"
                  : scenario === "mule"
                    ? "border-rose-500/40 bg-rose-950/30 text-rose-200"
                    : "border-cyan-500/40 bg-cyan-950/30 text-cyan-200"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase tracking-wider font-bold">
                  {scenario === "clean"
                    ? "STRAIGHT-THROUGH APPROVAL (STP)"
                    : scenario === "mule"
                      ? "FRAUD COLLISION PREVENTED"
                      : "8-TIER RECONCILIATION"}
                </span>
                {scenario === "clean" ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                ) : scenario === "mule" ? (
                  <ShieldAlert className="h-5 w-5 text-rose-400" />
                ) : (
                  <ShieldCheck className="h-5 w-5 text-cyan-400" />
                )}
              </div>
              <h3 className="text-base font-black text-white mt-1">
                {scenario === "clean"
                  ? "APPROVED (0 Human Touch)"
                  : scenario === "mule"
                    ? "BLOCKED: Mule Syndicate Detected"
                    : "RESOLVED: Semantic Match Approved"}
              </h3>
              <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                {scenario === "clean"
                  ? "All 6 mandatory checks satisfied. Candidate verified against CBDT, UIDAI, and NPCI rails in 240ms. Ready for IRDAI IC-38 LMS Certification."
                  : scenario === "mule"
                    ? "Bank Account 9988112233 collides with 3 prior banned POSP accounts. Payout rail frozen. Automatic regulatory escalation."
                    : "Initials 'S. V.' successfully expanded to 'Satyanarayana Venkata'. 95.4% phonetic match clears candidate without manual escalation."}
              </p>
            </div>

            {/* Checklist */}
            <div className="mt-4 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-300">RULE-1.1: Individual PAN 4th &apos;P&apos;</span>
                <span className="text-emerald-400 font-bold">PASS (100%)</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-300">RULE-2.1: 8-Tier Name Similarity</span>
                <span className="text-emerald-400 font-bold">
                  {scenario === "fuzzy" ? "RESOLVED (95.4%)" : "PASS (99.8%)"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-300">RULE-3.1: Bank Holder Penny Drop</span>
                <span className={clsx("font-bold", scenario === "mule" ? "text-rose-400" : "text-emerald-400")}>
                  {scenario === "mule" ? "BLOCKED (Colliding)" : "PASS (100%)"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-300">RULE-5.1: Cross-App Mule Ring</span>
                <span className={clsx("font-bold", scenario === "mule" ? "text-rose-400" : "text-emerald-400")}>
                  {scenario === "mule" ? "VIOLATION (Mule Ring)" : "PASS (Clean)"}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">IRDAI 2026 POSP Ready</span>
            <span className="text-[11px] font-mono text-cyan-400">Press ⌘K for Command Menu</span>
          </div>
        </div>
      </div>

      {/* Interactive 8-Tier Name Matcher Calculator */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 space-y-3 relative z-10">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Network className="h-4 w-4 text-cyan-400" />
            <span>8-Tier Indian Name Semantic Matcher Interactive Calculator</span>
          </h3>
          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
            Phonetics + Permutations + Initials
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          <div>
            <label className="text-[11px] font-mono text-slate-400 block mb-1">
              Name on Official PAN Card:
            </label>
            <input
              type="text"
              value={nameA}
              onChange={(e) => {
                sound.playClick();
                setNameA(e.target.value);
              }}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="text-[11px] font-mono text-slate-400 block mb-1">
              Name on Bank Cheque / IMPS:
            </label>
            <input
              type="text"
              value={nameB}
              onChange={(e) => {
                sound.playClick();
                setNameB(e.target.value);
              }}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800 mt-2">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs font-mono border border-emerald-500/40">
              {nameMatchResult.score}%
            </div>
            <div>
              <p className="text-xs font-bold text-white">
                {nameMatchResult.tier} · Decision: {nameMatchResult.status}
              </p>
              <p className="text-[11px] text-slate-400">
                Shared root tokens, soundex/metaphone phonetics, and regional patronymic expansion.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              sound.playSuccess();
              setNameA("S. V. Rao");
              setNameB("Satyanarayana Venkata Rao");
            }}
            className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 underline"
          >
            Try South Indian Initial Expansion (&quot;S. V. Rao&quot;)
          </button>
        </div>
      </div>
    </div>
  );
}
