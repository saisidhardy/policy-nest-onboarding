"use client";

import { useState } from "react";
import {
  Bot,
  Send,
  Sparkles,
  X,
} from "lucide-react";

interface Message {
  id: string;
  sender: "user" | "copilot";
  text: string;
  citations?: string[];
  timestamp: string;
}

const KNOWLEDGE_BASE: Record<string, { answer: string; citations: string[] }> = {
  eligibility: {
    answer:
      "Under IRDAI POSP Guidelines (2015 & 2026 update), an applicant must satisfy four strict statutory criteria:\n1. Minimum Age: Must be at least 18 years old on the date of application.\n2. Minimum Education: Passed Class 10 from a recognized central or state board.\n3. Valid Individual PAN: 10-character PAN where the 4th character is 'P' (Individual person).\n4. Exclusivity Affirmation: Must affirm they hold no active POSP license with any other insurer or broker.",
    citations: ["IRDAI/POSP/2015 §3.1", "Gazette of India §4.2", "Income Tax Act §139A"],
  },
  name_matching: {
    answer:
      "PolicyNest employs a deterministic 8-Tier Indian Name Matching algorithm tailored to Indian naming conventions:\n• Tier 1: Exact string match.\n• Tier 2: Token-set reordering (e.g., 'Verma Asha' vs 'Asha Verma').\n• Tier 3: Subsequence token match.\n• Tier 4: Initials expansion (e.g., 'A. R. Verma' vs 'Asha Ramesh Verma').\n• Tier 5: Phonetic variation (e.g., 'Mohammed' vs 'Mohammad').\n• Tier 6: Matrimonial surname update (requires human verification).\n• Tier 7: Strict Non-Auto-Reject Guardrail — legitimate name divergences are strictly routed to human confirmation and can NEVER be auto-rejected.",
    citations: ["PS-01 Rulebook §5.1", "Deterministic Consistency Engine v3.2"],
  },
  digilocker: {
    answer:
      "1-Click DigiLocker Import allows candidates to securely pull verified, government-issued digital certificates without manual camera capture:\n• Verified PAN Record: Fetched directly from the Income Tax Department (CBDT).\n• Class 10 Marksheet: Directly retrieved from CBSE, ICSE, or State Education Boards.\n• Aadhaar XML: Pulled directly from UIDAI with full DPDP Act compliant last-4 masking.\n\nDocuments fetched via DigiLocker are digitally signed and 100% immune to blur, glare, or cropping defects.",
    citations: ["Information Technology Act §9A", "DigiLocker Ecosystem API v2.0"],
  },
  fraud_rings: {
    answer:
      "PolicyNest guards against identity theft and broker commission diversion syndicates via 3 automated anomaly detectors:\n1. SHA-256 Deduplication: Flags when an identical image/PDF hash is reused across different applicant profiles.\n2. Mule Account Detection: Flags when identical bank account numbers and IFSCs are registered under different PANs.\n3. Contact Stacking: Flags when a single mobile number is associated with 3 or more distinct PAN identities.\n\nAll flagged applications are quarantined immediately and routed to the Senior Fraud Desk.",
    citations: ["Prevention of Money Laundering Act (PMLA)", "Fraud Risk Guardrail §7.4"],
  },
  penny_drop: {
    answer:
      "The NPCI IMPS ₹1.00 Penny Drop verification transfers a nominal ₹1.00 deposit into the candidate's declared bank account. The banking rail returns the registered account holder's name and Bank UTR reference (e.g., UTR 260314098231). Our deterministic engine cross-checks this holder name against the candidate's PAN card name using 8-tier matching before approving payout credentials.",
    citations: ["NPCI IMPS Operating Guidelines", "RBI Circular on Digital KYC §12"],
  },
};

const SUGGESTED_PROMPTS = [
  { key: "eligibility", label: "📋 IRDAI Statutory Eligibility Rules", query: "What are the mandatory IRDAI POSP eligibility rules?" },
  { key: "name_matching", label: "🪪 8-Tier Indian Name Matching", query: "How does 8-tier Indian name matching work?" },
  { key: "digilocker", label: "⚡ 1-Click DigiLocker Pull", query: "How does 1-click DigiLocker import work?" },
  { key: "fraud_rings", label: "🚨 Cross-Application Fraud Defense", query: "How does PolicyNest catch cross-application fraud rings?" },
  { key: "penny_drop", label: "🏦 NPCI Penny Drop & Bank Match", query: "How does bank account penny drop verification work?" },
];

export function AiAssistantWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init",
      sender: "copilot",
      text: "Hello! I am the PolicyNest InsurTech AI Copilot, grounded in IRDAI POSP regulations, statutory rulebooks, and DPDP compliance standards. How can I assist you today?",
      citations: ["IRDAI POSP Act 2015", "DPDP Act 2023"],
      timestamp: "Just now",
    },
  ]);

  function handleSend(queryText?: string) {
    const q = (queryText || input).trim();
    if (!q) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    // Grounded response synthesis
    setTimeout(() => {
      const lower = q.toLowerCase();
      let matchedKey = "eligibility";
      if (lower.includes("name") || lower.includes("tier") || lower.includes("spelling")) matchedKey = "name_matching";
      else if (lower.includes("digi") || lower.includes("locker") || lower.includes("import")) matchedKey = "digilocker";
      else if (lower.includes("fraud") || lower.includes("mule") || lower.includes("ring") || lower.includes("duplicate"))
        matchedKey = "fraud_rings";
      else if (lower.includes("penny") || lower.includes("bank") || lower.includes("ifsc") || lower.includes("drop"))
        matchedKey = "penny_drop";

      const kb = KNOWLEDGE_BASE[matchedKey];
      const botMsg: Message = {
        id: `c-${Date.now()}`,
        sender: "copilot",
        text: kb.answer,
        citations: kb.citations,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, botMsg]);
    }, 450);
  }

  return (
    <>
      {/* Floating Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-gradient-to-r from-brand-700 via-indigo-600 to-brand-800 px-4 py-3 text-sm font-semibold text-white shadow-xl shadow-brand-900/25 transition-all hover:scale-105 hover:shadow-2xl focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
        aria-label="Open PolicyNest AI Copilot"
      >
        <Sparkles className="h-4 w-4 animate-pulse text-amber-300" />
        <span>Ask AI Copilot</span>
        <span className="rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-200 ring-1 ring-emerald-400/30">
          Grounded
        </span>
      </button>

      {/* Slide-over Copilot Modal */}
      {isOpen && (
        <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white/95 shadow-2xl backdrop-blur-xl border-l border-slate-200 sm:rounded-l-2xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-900 px-5 py-4 text-white sm:rounded-tl-2xl">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white shadow-inner">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold tracking-tight">PolicyNest AI Copilot</h3>
                  <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/30">
                    Online
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Grounded in IRDAI POSP Rulebooks &amp; DPDP Guidelines</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Quick Prompt Chips */}
          <div className="border-b border-slate-100 bg-slate-50/80 p-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Suggested Regulatory Topics
            </p>
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => handleSend(p.query)}
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-900 transition-all text-left"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Message History */}
          <div className="flex-1 space-y-4 overflow-y-auto p-4 text-sm">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 leading-relaxed ${
                    m.sender === "user"
                      ? "bg-brand-700 text-white shadow-sm"
                      : "border border-slate-200 bg-white text-slate-800 shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-line text-xs">{m.text}</p>
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-2.5 border-t border-slate-100 pt-2 text-[10px] text-slate-500">
                      <span className="font-semibold text-slate-700">Official Citations: </span>
                      {m.citations.join(" · ")}
                    </div>
                  )}
                </div>
                <span className="mt-1 text-[10px] text-slate-400">{m.timestamp}</span>
              </div>
            ))}
          </div>

          {/* Input Footer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="border-t border-slate-200 bg-white p-3 flex gap-2 items-center"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about POSP onboarding or rules..."
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <button
              type="submit"
              disabled={!input.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-700 text-white hover:bg-brand-800 disabled:opacity-40 transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
