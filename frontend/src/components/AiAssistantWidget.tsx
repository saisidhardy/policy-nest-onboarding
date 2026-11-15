"use client";

import clsx from "clsx";
import {
  Bot,
  Maximize2,
  Minimize2,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { usePathname } from "next/navigation";
import React, { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fireConfetti } from "@/lib/confetti";
import { sound } from "@/lib/soundFx";

interface Message {
  id: string;
  sender: "user" | "copilot";
  text: string;
  citations?: string[];
  timestamp: string;
  canAppeal?: boolean;
  appealPrefill?: string | null;
  voiceScript?: string;
}

interface BlockerItem {
  blocker_code: string;
  title: string;
  description: string;
  severity: string;
  suggested_action: string;
  manual_citation: string;
  can_appeal: boolean;
}

interface LiveState {
  has_application: boolean;
  application_id?: string | null;
  reference_code?: string | null;
  status?: string | null;
  priority_group: string;
  priority_group_label: string;
  current_stage: string;
  documents_completed_count: number;
  documents_total_count: number;
  missing_documents: string[];
  active_blockers: BlockerItem[];
  has_open_appeal: boolean;
  training_hours_completed: number;
  training_hours_required: number;
  days_remaining_before_expiry: number;
}

interface RAGResponse {
  query: string;
  answer: string;
  language: string;
  citations: string[];
  applicant_state: LiveState;
  can_appeal: boolean;
  appeal_prefill_reason?: string | null;
  appeal_guidance?: string | null;
  voice_script: string;
  latency_ms: number;
}

const MANUAL_SUGGESTED_PROMPTS = [
  {
    label: "📷 Blurry / Glare Photo Fix",
    query: "How do I take a photo without glare or blur per Manual rules?",
  },
  {
    label: "🏦 Joint Bank Account Rules",
    query: "Can I use a joint bank account where I am first holder?",
  },
  {
    label: "🪪 Name Spelling Variation",
    query: "Why was my name spelling flagged and what are the 8-tier non-auto-reject rules?",
  },
  {
    label: "🎓 NIOS / State Board Marksheet",
    query: "Is a Class 10 marksheet from NIOS or state board eligible for POSP?",
  },
  {
    label: "⏱️ 7-Day Document Expiration",
    query: "Why does the application expire in 7 days and do I need to upload all at once?",
  },
  {
    label: "🛡️ How to Raise a Formal Appeal",
    query: "How can I raise a formal appeal against a rejection to a human reviewer?",
  },
];

const CONTEXTUAL_PROMPTS: Record<string, { label: string; query: string }[]> = {
  bank: [
    { label: "🏦 Why account in my name?", query: "Why must the bank account be in my own name?" },
    { label: "👥 Can I use a joint account?", query: "Can I use a joint account where I am first holder?" },
    { label: "⚡ What is a penny-drop check?", query: "What is a penny-drop check and is ₹1 actually charged?" },
    { label: "📄 Can I use a bank statement?", query: "Can I use a bank statement instead of a cancelled cheque?" },
    { label: "🪪 PAN vs Bank name difference?", query: "What happens if my PAN name and bank account name differ slightly?" },
  ],
  documents: [
    { label: "❌ Why was my image rejected?", query: "Why was my document image flagged and how do I fix it?" },
    { label: "🪪 Which side of Aadhaar?", query: "Which side of Aadhaar is needed for front vs back?" },
    { label: "📎 Can I upload a PDF?", query: "Can I upload a PDF document instead of photo?" },
    { label: "👤 What happens in human review?", query: "What happens during human reviewer check and how long does it take?" },
    { label: "🔒 Is my full Aadhaar stored?", query: "Is my full 12-digit Aadhaar number stored in the database?" },
  ],
  training: [
    { label: "📚 15-Hour syllabus?", query: "What is covered in the 15-hour POSP IC-38 training?" },
    { label: "📝 Exam passing score?", query: "How many questions are on the POSP exam and what score is needed to pass?" },
    { label: "📜 Certificate issuance?", query: "When will my official digital POSP appointment certificate be issued?" },
  ],
};

export function AiAssistantWidget() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState<"EN" | "HI">("EN");
  const [loading, setLoading] = useState(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const [applicantState, setApplicantState] = useState<LiveState | null>(null);
  const [appealSubmitting, setAppealSubmitting] = useState(false);
  const [appealSuccessMsg, setAppealSuccessMsg] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init",
      sender: "copilot",
      text: "Hello! I am the PolicyNest InsurTech AI Copilot, grounded in the official POSP Recovery & Agent Action Manual, Quick-Start Handbook, and IRDAI 2016 regulations.\n\nI continuously monitor your application state and can help resolve any document, eligibility, or verification blockers.",
      citations: ["POSP Recovery Manual §1-7", "Quick-Start Handbook §1-4", "IRDAI POSP Guidelines 2016"],
      timestamp: "Just now",
      voiceScript: "Hello! I am your PolicyNest AI Copilot. I can help resolve any onboarding blockers or guide you through an appeal.",
    },
  ]);

  // Fetch applicant state on open
  useEffect(() => {
    if (!isOpen) return;

    // Load initial state from RAG state endpoint if available
    api<RAGResponse>("/rag/chat", {
      method: "POST",
      body: { query: "What is my current onboarding state and active blockers?", language },
    }).then(
      (res) => {
        if (res.applicant_state) {
          setApplicantState(res.applicant_state);
        }
      },
      () => {
        // Non-blocking fallback
      }
    );
  }, [isOpen, language]);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const q = (queryText || input).trim();
    if (!q || loading) return;

    sound.playClick();
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await api<RAGResponse>("/rag/chat", {
        method: "POST",
        body: {
          query: q,
          language,
          application_id: applicantState?.application_id || undefined,
        },
      });

      if (res.applicant_state) {
        setApplicantState(res.applicant_state);
      }

      const botMsg: Message = {
        id: `c-${Date.now()}`,
        sender: "copilot",
        text: res.answer,
        citations: res.citations,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        canAppeal: res.can_appeal,
        appealPrefill: res.appeal_prefill_reason,
        voiceScript: res.voice_script,
      };

      setMessages((prev) => [...prev, botMsg]);
      sound.playSuccess();
    } catch {
      // Local heuristic fallback grounded in manuals
      const fallbackMsg: Message = {
        id: `c-${Date.now()}`,
        sender: "copilot",
        text: "Under the POSP Recovery Manual:\n• Section 1: Upload documents one at a time within 7 days.\n• Section 2: Spelling differences, initials, and NIOS marksheets cannot be auto-rejected.\n• Section 3: Take photos in bright daylight with flash OFF showing all 4 corners.\n\nIf you are facing an unresolvable issue, you have the right to request a Senior Reviewer exception.",
        citations: ["Recovery Manual §1-3"],
        timestamp: "Just now",
        canAppeal: true,
        appealPrefill: "Requesting Senior Reviewer exception under Manual Rule 2.",
        voiceScript: "Take clear photos in bright daylight with flash turned off. You can also appeal to a senior reviewer.",
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleSpeak = (msg: Message) => {
    sound.playClick();
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      alert("Speech synthesis is not supported in this browser.");
      return;
    }

    if (speakingMsgId === msg.id) {
      window.speechSynthesis.cancel();
      setSpeakingMsgId(null);
      return;
    }

    window.speechSynthesis.cancel();
    const textToSpeak = msg.voiceScript || msg.text.replace(/[*#_`]/g, "").slice(0, 250);
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.lang = language === "HI" ? "hi-IN" : "en-IN";
    utterance.rate = 0.95;

    utterance.onstart = () => {
      setSpeakingMsgId(msg.id);
      sound.playScan();
    };

    utterance.onend = () => {
      setSpeakingMsgId(null);
      sound.playSuccess();
    };

    utterance.onerror = () => {
      setSpeakingMsgId(null);
    };

    window.speechSynthesis.speak(utterance);
  };

  const handleRaiseAppeal = async (prefillReason?: string | null) => {
    const reason = prefillReason || "Requesting Senior Reviewer exception under Manual Rule 2 (BLUE Indicator).";
    if (!applicantState?.application_id) {
      alert("No active application found to appeal. Please start or select an application.");
      return;
    }

    setAppealSubmitting(true);
    sound.playClick();

    try {
      // Submit appeal via statutory endpoint
      await api(`/rules/applications/${applicantState.application_id}/appeal`, {
        method: "POST",
        body: { appeal_reason: reason },
      });

      sound.playTrophy();
      fireConfetti();
      setAppealSuccessMsg("Formal appeal successfully submitted! Your file is now in the Senior Reviewer queue.");

      const confirmationMsg: Message = {
        id: `appeal-${Date.now()}`,
        sender: "copilot",
        text: `✅ **Formal Appeal Registered Successfully!**\n\nYour application has been prioritized in the Senior Reviewer Desk under the POSP Recovery Manual statutory guardrail. You will receive an SMS and WhatsApp alert as soon as the supervisor evaluates your file.`,
        citations: ["Recovery Manual §2 (BLUE Indicator)", "Statutory Appeal Rail §4.2"],
        timestamp: "Just now",
        voiceScript: "Your formal appeal has been submitted successfully and routed to the senior reviewer.",
      };

      setMessages((prev) => [...prev, confirmationMsg]);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to submit appeal.";
      alert(msg);
    } finally {
      setAppealSubmitting(false);
    }
  };

  return (
    <>
      {/* Floating launcher trigger */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => {
            sound.playClick();
            setIsOpen(true);
          }}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 rounded-full bg-gradient-to-r from-emerald-600 via-teal-600 to-brand-700 px-4 py-3 text-white shadow-2xl shadow-emerald-950/40 transition hover:scale-105 hover:from-emerald-500 hover:to-brand-600"
          aria-label="Open AI Onboarding Copilot"
        >
          <div className="relative">
            <Bot className="h-5 w-5" />
            <span className="absolute -top-1 -right-1 flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
          </div>
          <span className="text-xs font-bold tracking-wide">AI Copilot</span>
          <span className="rounded bg-white/20 px-1.5 py-0.5 text-[10px] font-mono font-semibold">RAG</span>
        </button>
      )}

      {/* Main Copilot Drawer / Modal */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="AI Onboarding Assistant"
          className={clsx(
            "fixed z-50 flex flex-col bg-slate-900 text-white shadow-2xl transition-all duration-200 border border-slate-700 rounded-2xl",
            isExpanded
              ? "bottom-4 right-4 top-4 left-4 sm:left-auto sm:w-[680px]"
              : "bottom-6 right-6 w-[94vw] sm:w-[460px] h-[640px] max-h-[90vh]"
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3 bg-slate-950/70 rounded-t-2xl">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold font-mono text-white">PolicyNest AI Copilot</h3>
                  <span className="rounded bg-emerald-900/60 border border-emerald-500/40 px-1.5 py-0.2 text-[9px] font-mono text-emerald-300 font-bold">
                    RAG MANUAL
                  </span>
                </div>
                <p className="text-[10px] text-slate-400">
                  Grounded in Recovery &amp; Quick-Start Handbooks
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {/* Language Switch */}
              <button
                type="button"
                onClick={() => {
                  sound.playClick();
                  setLanguage(language === "EN" ? "HI" : "EN");
                }}
                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[10px] font-bold text-emerald-400 transition"
                title="Toggle Language (English / हिंदी)"
              >
                {language === "EN" ? "हिंदी" : "EN"}
              </button>

              {/* Expand Toggle */}
              <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 rounded text-slate-400 hover:text-white"
                title={isExpanded ? "Collapse" : "Expand"}
              >
                {isExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
              </button>

              {/* Close */}
              <button
                type="button"
                onClick={() => {
                  sound.playClick();
                  setIsOpen(false);
                }}
                className="p-1 rounded text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Live Applicant Monitoring Banner */}
          {applicantState && (
            <div className="bg-slate-950 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2 truncate">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                <span className="font-mono text-slate-300 font-semibold truncate">
                  {applicantState.reference_code || "PN-DRAFT"}
                </span>
                <span className="text-slate-400">·</span>
                <span className="text-emerald-400 font-medium truncate">
                  {applicantState.priority_group_label}
                </span>
              </div>
              {applicantState.active_blockers.length > 0 && (
                <span className="rounded bg-amber-950/80 border border-amber-600/40 px-2 py-0.5 text-[10px] text-amber-300 font-bold flex-shrink-0">
                  {applicantState.active_blockers.length} Blockers Active
                </span>
              )}
            </div>
          )}

          {appealSuccessMsg && (
            <div className="bg-emerald-950/80 border-b border-emerald-500/40 px-4 py-2 text-[11px] text-emerald-300 font-medium">
              ✓ {appealSuccessMsg}
            </div>
          )}

          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
            {messages.map((m) => (
              <div
                key={m.id}
                className={clsx(
                  "flex flex-col gap-1.5",
                  m.sender === "user" ? "items-end" : "items-start"
                )}
              >
                <div
                  className={clsx(
                    "max-w-[88%] rounded-2xl px-4 py-3 leading-relaxed",
                    m.sender === "user"
                      ? "bg-gradient-to-r from-emerald-600 to-teal-700 text-white rounded-br-xs shadow-md shadow-emerald-950/30"
                      : "bg-slate-800 text-slate-200 rounded-bl-xs border border-slate-700"
                  )}
                >
                  <p className="whitespace-pre-line">{m.text}</p>

                  {/* Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-slate-700/60 flex flex-wrap gap-1.5">
                      {m.citations.map((c, i) => (
                        <span
                          key={i}
                          className="rounded bg-slate-900/80 px-1.5 py-0.5 text-[9px] font-mono text-emerald-400 border border-emerald-500/20"
                        >
                          📚 {c}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Interactive Appeal Action Card if Unresolvable */}
                  {m.canAppeal && (
                    <div className="mt-3 p-3 rounded-xl bg-amber-950/50 border border-amber-500/50 text-amber-200">
                      <div className="flex items-center gap-1.5 font-bold text-xs text-amber-400">
                        <ShieldAlert className="h-4 w-4" />
                        <span>Manual §2: Human Reviewer Appeal Option</span>
                      </div>
                      <p className="text-[11px] text-amber-300 mt-1 leading-normal">
                        Per Recovery Manual Rule 2 (BLUE Indicator), name variations, joint bank accounts, and NIOS marksheets require human reviewer judgment.
                      </p>
                      <button
                        type="button"
                        disabled={appealSubmitting}
                        onClick={() => handleRaiseAppeal(m.appealPrefill)}
                        className="mt-2 flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition shadow-md shadow-amber-950/40 disabled:opacity-50"
                      >
                        {appealSubmitting ? (
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="h-3.5 w-3.5" />
                        )}
                        <span>Raise Formal Appeal to Reviewer Desk</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Footer with timestamp and voice speak icon */}
                <div className="flex items-center gap-2 px-1 text-[10px] text-slate-500 font-mono">
                  <span>{m.timestamp}</span>
                  {m.sender === "copilot" && (
                    <button
                      type="button"
                      onClick={() => handleSpeak(m)}
                      className="hover:text-emerald-400 transition"
                      title={speakingMsgId === m.id ? "Stop Speech" : "Listen via Speech Synthesis"}
                    >
                      {speakingMsgId === m.id ? (
                        <VolumeX className="h-3 w-3 text-emerald-400 animate-pulse" />
                      ) : (
                        <Volume2 className="h-3 w-3" />
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-slate-400 text-xs py-2 px-3 bg-slate-800/40 rounded-xl border border-slate-800 w-fit">
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-emerald-400" />
                <span>Consulting POSP Recovery Manual &amp; State Rails...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Contextual & Manual Prompt Pills (Workstream M) */}
          <div className="px-4 py-2 border-t border-slate-800/60 bg-slate-950/40 flex items-center gap-2 overflow-x-auto no-scrollbar">
            {(pathname?.includes("/training")
              ? [...CONTEXTUAL_PROMPTS.training, ...MANUAL_SUGGESTED_PROMPTS]
              : pathname?.includes("/onboarding")
              ? [...CONTEXTUAL_PROMPTS.documents, ...CONTEXTUAL_PROMPTS.bank, ...MANUAL_SUGGESTED_PROMPTS]
              : MANUAL_SUGGESTED_PROMPTS
            ).map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleSend(p.query)}
                className="flex-shrink-0 px-2.5 py-1 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-medium transition border border-slate-700/60 whitespace-nowrap"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Chat Input Field */}
          <div className="p-3 border-t border-slate-800 bg-slate-950 rounded-b-2xl">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  language === "HI"
                    ? "कोई भी सवाल पूछें (उदा. नाम की वर्तनी, फोटो के नियम)..."
                    : "Ask about documents, blur fixes, joint accounts, appeals..."
                }
                className="flex-1 rounded-xl bg-slate-900 border border-slate-700 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white transition hover:from-emerald-600 hover:to-teal-700 disabled:opacity-40"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
