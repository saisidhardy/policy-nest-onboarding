"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  ShieldAlert,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { sound } from "@/lib/soundFx";

export interface OnboardingAssistantHUDProps {
  applicationId?: string;
  referenceCode?: string;
  status?: string;
  currentStep?: number;
  totalSteps?: number;
  completedDocsCount?: number;
  missingDocs?: string[];
  blockerMessage?: string;
  onOpenChat?: (prefillQuery?: string) => void;
  onRaiseAppeal?: () => void;
}

export function OnboardingAssistantHUD({
  referenceCode = "PN-2026-INTAKE",
  status = "DRAFT",
  currentStep = 1,
  totalSteps = 6,
  completedDocsCount = 0,
  missingDocs = [],
  blockerMessage,
  onOpenChat,
  onRaiseAppeal,
}: OnboardingAssistantHUDProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [language, setLanguage] = useState<"EN" | "HI">("EN");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Map to the 5 Manual Stages
  const stages = [
    { num: 1, label: "01 Upload", desc: "6 Clear Documents (7-day timer)", active: currentStep <= 6 && status === "DRAFT" },
    { num: 2, label: "02 KYC Review", desc: "Instant Verification & Review", active: status === "SUBMITTED" || status === "IN_REVIEW" || status === "NEEDS_MORE_INFO" || status === "REJECTED" },
    { num: 3, label: "03 15-Hr LMS", desc: "Mandatory IC-38 Modules", active: status === "KYC_APPROVED" || status === "TRAINING_IN_PROGRESS" },
    { num: 4, label: "04 POSP Exam", desc: "Statutory Online Test", active: false },
    { num: 5, label: "05 Certificate", desc: "Cryptographic Accreditation", active: status === "CERTIFIED" },
  ];

  // Visual Direction Guidance derived from Recovery & Quick-Start Manuals
  let guidanceText = "";
  let voiceText = "";

  if (status === "REJECTED") {
    guidanceText = "Your application was rejected on eligibility. Under Recovery Manual §2, legitimate name variations and joint accounts must not be auto-rejected. You have the right to raise a formal appeal.";
    voiceText = language === "HI"
      ? "आपकी पात्रता अस्वीकृत हुई है। नियमावली नियम दो के तहत नाम की वर्तनी और संयुक्त बैंक खाते को सीधे खारिज नहीं किया जा सकता। आप अपील कर सकते हैं।"
      : "Your application was rejected. Under POSP Recovery Manual Section 2, spelling variations and joint accounts cannot be auto-rejected. You can raise a formal appeal.";
  } else if (status === "NEEDS_MORE_INFO") {
    guidanceText = "Correction Requested: Check the specific remarks below. Per Manual Rule 3: Take daylight photos with flash OFF, showing all 4 corners.";
    voiceText = language === "HI"
      ? "सुधार अनुरोध: कृपया फ़्लैश बंद करके साफ़ दिन के उजाले में फोटो लें और चारों कोने दिखाएं।"
      : "Correction requested. Please take photos in bright daylight with flash turned off, showing all four corners.";
  } else if (status === "KYC_APPROVED" || status === "TRAINING_IN_PROGRESS") {
    guidanceText = "KYC Verified! Next step per Manual §4: Complete your 15-hour POSP training to unlock the online examination.";
    voiceText = language === "HI"
      ? "बधाई! आपका सत्यापन पूर्ण हो गया है। अब पंद्रह घंटे का प्रशिक्षण पूरा करें।"
      : "Congratulations! KYC is verified. Your next step is to complete the 15-hour training modules.";
  } else if (status === "CERTIFIED") {
    guidanceText = "Congratulations! You are an officially certified POSP. Download your certificate or contact sales support.";
    voiceText = language === "HI"
      ? "बधाई हो! आपका ऑनबोर्डिंग पूर्ण हो गया है और आप प्रमाणित पी ओ एस पी बन चुके हैं।"
      : "Congratulations! You are officially a certified POSP. Your onboarding is complete.";
  } else {
    const missingStr = missingDocs.length > 0 ? ` (Pending: ${missingDocs.map((d) => d.replace("_", " ")).join(", ")})` : "";
    guidanceText = `Stage 1 Intake: ${completedDocsCount} of ${totalSteps} documents uploaded${missingStr}. Per Quick-Start Step 3: Flash OFF, all 4 corners visible, daylight photo. Form expires in 7 days.`;
    voiceText = language === "HI"
      ? `दस्तावेज़ अपलोड: आपने ${totalSteps} में से ${completedDocsCount} दस्तावेज़ अपलोड किए हैं। फ़्लैश बंद रखें और साफ़ फोटो अपलोड करें।`
      : `Intake stage: You have completed ${completedDocsCount} of ${totalSteps} documents. Keep flash off and ensure all four corners are visible.`;
  }

  // Animated soundwave canvas when speaking
  useEffect(() => {
    if (!speaking) {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let phase = 0;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#10b981";
      ctx.beginPath();

      const sliceWidth = canvas.width / 30;
      for (let i = 0; i < 30; i++) {
        const x = i * sliceWidth;
        const amplitude = Math.sin(phase + i * 0.4) * 8 * Math.sin((i / 30) * Math.PI);
        const y = canvas.height / 2 + amplitude;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      phase += 0.2;
      animationFrameRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [speaking]);

  // Handle Speech Synthesis
  const handleToggleVoice = () => {
    sound.playClick();
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      alert("Speech synthesis is not supported in this browser.");
      return;
    }

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(voiceText);
    utterance.lang = language === "HI" ? "hi-IN" : "en-IN";
    utterance.rate = 0.95;
    utterance.pitch = 1.05;

    utterance.onstart = () => {
      setSpeaking(true);
      sound.playScan();
    };

    utterance.onend = () => {
      setSpeaking(false);
      sound.playSuccess();
    };

    utterance.onerror = () => {
      setSpeaking(false);
    };

    window.speechSynthesis.speak(utterance);
  };

  return (
    <aside
      aria-label="AI Onboarding Assistant HUD"
      className="mb-6 rounded-2xl border border-slate-200/80 bg-gradient-to-br from-slate-900 via-slate-900 to-brand-950 p-4 text-white shadow-xl shadow-slate-950/20"
    >
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 font-mono">
                AI Onboarding Assistant
              </span>
              <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                {referenceCode}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Grounded in POSP Recovery &amp; Quick-Start Handbooks · Real-Time Guidance
            </p>
          </div>
        </div>

        {/* Audio controls & collapse */}
        <div className="flex items-center gap-2">
          {/* Language Toggle */}
          <div className="flex items-center rounded-lg bg-slate-800 p-0.5 text-[10px] font-semibold">
            <button
              type="button"
              onClick={() => {
                sound.playClick();
                setLanguage("EN");
              }}
              className={clsx(
                "px-2 py-0.5 rounded transition",
                language === "EN" ? "bg-emerald-500 text-slate-950" : "text-slate-400 hover:text-white"
              )}
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => {
                sound.playClick();
                setLanguage("HI");
              }}
              className={clsx(
                "px-2 py-0.5 rounded transition",
                language === "HI" ? "bg-emerald-500 text-slate-950" : "text-slate-400 hover:text-white"
              )}
            >
              हिंदी
            </button>
          </div>

          {/* Voice Prompt Button */}
          <button
            type="button"
            onClick={handleToggleVoice}
            className={clsx(
              "flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition border",
              speaking
                ? "bg-emerald-500 text-slate-950 border-emerald-400 shadow-md shadow-emerald-500/30"
                : "bg-slate-800 hover:bg-slate-700 text-emerald-400 border-slate-700"
            )}
          >
            {speaking ? <VolumeX className="h-3.5 w-3.5 animate-pulse" /> : <Volume2 className="h-3.5 w-3.5" />}
            <span>{speaking ? (language === "HI" ? "रोकें" : "Stop Voice") : (language === "HI" ? "आवाज़ सुनें" : "Listen Guidance")}</span>
          </button>

          {/* Animated Waveform Canvas */}
          {speaking && (
            <canvas ref={canvasRef} width={60} height={20} className="rounded bg-slate-950/60" />
          )}

          {/* Collapse Toggle */}
          <button
            type="button"
            onClick={() => {
              sound.playClick();
              setCollapsed(!collapsed);
            }}
            className="p-1 rounded text-slate-400 hover:text-white"
            title={collapsed ? "Expand Assistant" : "Collapse Assistant"}
          >
            {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="pt-3 space-y-3">
          {/* 5-Stage Path to Certification (From Quick-Start Handbook Step 4) */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {stages.map((st) => (
              <div
                key={st.num}
                className={clsx(
                  "p-2 rounded-xl border text-xs transition",
                  st.active
                    ? "bg-emerald-950/40 border-emerald-500/60 text-emerald-200"
                    : "bg-slate-800/40 border-slate-800 text-slate-400"
                )}
              >
                <div className="flex items-center justify-between font-mono font-bold text-[11px]">
                  <span>{st.label}</span>
                  {st.active && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />}
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">{st.desc}</p>
              </div>
            ))}
          </div>

          {/* Visual Guidance Banner */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-800/80 border border-slate-700/80">
            <div className="flex items-start gap-2.5">
              <Sparkles className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-slate-200 font-medium leading-relaxed">
                  {guidanceText}
                </p>
                {blockerMessage && (
                  <p className="text-[11px] text-amber-300 font-mono mt-1 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" /> {blockerMessage}
                  </p>
                )}
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-center">
              {status === "REJECTED" && onRaiseAppeal && (
                <button
                  type="button"
                  onClick={() => {
                    sound.playClick();
                    onRaiseAppeal();
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-500 hover:bg-amber-600 text-slate-950 transition shadow-md shadow-amber-500/20"
                >
                  <ShieldAlert className="h-3.5 w-3.5" />
                  <span>Raise Formal Appeal</span>
                </button>
              )}

              {onOpenChat && (
                <button
                  type="button"
                  onClick={() => {
                    sound.playClick();
                    onOpenChat("What should I do for my current blockers?");
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-md shadow-emerald-700/30"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  <span>Ask AI Copilot</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
