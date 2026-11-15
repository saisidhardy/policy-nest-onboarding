"use client";

import clsx from "clsx";
import {
  CheckCheck,
  MessageSquare,
  Send,
  ShieldCheck,
  Smartphone,
  Sparkles,
  X,
} from "lucide-react";
import React, { useState } from "react";
import { Button } from "@/components/ui";
import { fireConfetti } from "@/lib/confetti";
import { sound } from "@/lib/soundFx";

interface WhatsAppDispatchSimulatorProps {
  isOpen: boolean;
  onClose: () => void;
  candidateName?: string;
  mobile?: string;
  referenceCode?: string;
}

type TemplateType = "rework" | "approved" | "cert";

export function WhatsAppDispatchSimulator({
  isOpen,
  onClose,
  candidateName = "Rajiv Sharma",
  mobile = "+91 98765 43210",
  referenceCode = "PN-2026-8819",
}: WhatsAppDispatchSimulatorProps) {
  const [channel, setChannel] = useState<"whatsapp" | "sms">("whatsapp");
  const [template, setTemplate] = useState<TemplateType>("approved");
  const [dispatched, setDispatched] = useState(false);
  const [dispatchTime, setDispatchTime] = useState<string>("Just now");
  const [readState, setReadState] = useState<"sent" | "delivered" | "read">("read");

  if (!isOpen) return null;

  const handleDispatch = () => {
    sound.playClick();
    sound.playScan();
    setDispatched(false);

    setTimeout(() => {
      setDispatched(true);
      setDispatchTime(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
      setReadState("sent");

      setTimeout(() => {
        setReadState("delivered");
        setTimeout(() => {
          setReadState("read");
          sound.playSuccess();
          if (template === "cert" || template === "approved") {
            sound.playTrophy();
            fireConfetti();
          }
        }, 600);
      }, 500);
    }, 400);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-900 text-slate-100 shadow-2xl overflow-hidden flex flex-col">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 font-bold">
              <MessageSquare className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                WhatsApp Business & DLT SMS Dispatch Console
              </h2>
              <p className="text-xs text-slate-400">
                Simulate real-time candidate omni-channel regulatory messaging
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Channel & Template Selectors */}
        <div className="bg-slate-900/90 p-4 border-b border-slate-800 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  sound.playClick();
                  setChannel("whatsapp");
                }}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition",
                  channel === "whatsapp"
                    ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/40"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                )}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span>WhatsApp Business API</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  sound.playClick();
                  setChannel("sms");
                }}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition",
                  channel === "sms"
                    ? "bg-cyan-600 text-white shadow-md shadow-cyan-900/40"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                )}
              >
                <Smartphone className="h-3.5 w-3.5" />
                <span>TRAI DLT SMS Rail</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              {dispatched && (
                <span className="text-[11px] font-mono text-emerald-400 font-semibold">
                  ✓ Meta API 200 OK
                </span>
              )}
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleDispatch}
                className="gap-1.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-bold text-xs shadow-lg shadow-emerald-900/30"
              >
                <Send className="h-3.5 w-3.5" />
                <span>Simulate Send / Push</span>
              </Button>
            </div>
          </div>

          {/* Template pills */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 text-[11px] font-mono">Template:</span>
            <button
              type="button"
              onClick={() => {
                sound.playClick();
                setTemplate("approved");
              }}
              className={clsx(
                "px-2.5 py-1 rounded text-xs font-medium transition",
                template === "approved"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-500/40"
                  : "bg-slate-800/60 text-slate-400 hover:text-white"
              )}
            >
              1. STP Approved (Start IC-38)
            </button>

            <button
              type="button"
              onClick={() => {
                sound.playClick();
                setTemplate("rework");
              }}
              className={clsx(
                "px-2.5 py-1 rounded text-xs font-medium transition",
                template === "rework"
                  ? "bg-amber-950 text-amber-300 border border-amber-500/40"
                  : "bg-slate-800/60 text-slate-400 hover:text-white"
              )}
            >
              2. Document Rework Alert
            </button>

            <button
              type="button"
              onClick={() => {
                sound.playClick();
                setTemplate("cert");
              }}
              className={clsx(
                "px-2.5 py-1 rounded text-xs font-medium transition",
                template === "cert"
                  ? "bg-cyan-950 text-cyan-300 border border-cyan-500/40"
                  : "bg-slate-800/60 text-slate-400 hover:text-white"
              )}
            >
              3. License Issued (Form 1-A)
            </button>
          </div>
        </div>

        {/* Live Device Phone Frame */}
        <div className="p-5 flex justify-center bg-slate-950/60">
          <div className="w-full max-w-md rounded-3xl border-4 border-slate-800 bg-slate-900 overflow-hidden shadow-2xl">
            
            {channel === "whatsapp" ? (
              /* WhatsApp Screen */
              <div className="flex flex-col h-[400px]">
                {/* WhatsApp Top Bar */}
                <div className="bg-[#1f2c34] px-4 py-3 flex items-center justify-between border-b border-slate-700">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-full bg-emerald-600 flex items-center justify-center font-bold text-xs text-white">
                      PN
                    </div>
                    <div>
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-bold text-white">PolicyNest Official</span>
                        <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                      </div>
                      <p className="text-[10px] text-emerald-400 font-mono">Official Regulatory Account</p>
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">{mobile}</span>
                </div>

                {/* WhatsApp Chat Area */}
                <div className="flex-1 p-4 bg-[#0b141a] overflow-y-auto space-y-3 flex flex-col justify-end">
                  <div className="text-center">
                    <span className="text-[10px] bg-slate-800/80 text-slate-400 px-2 py-0.5 rounded font-mono">
                      TODAY · VERIFIED BUSINESS API
                    </span>
                  </div>

                  {/* Message Bubble */}
                  <div className="bg-[#005c4b] text-white p-3.5 rounded-2xl rounded-tl-none max-w-[88%] self-start shadow-md space-y-2 text-xs">
                    <p className="font-semibold text-emerald-200">
                      Namaste {candidateName}! 🙏
                    </p>

                    {template === "approved" && (
                      <p className="text-slate-100 leading-relaxed text-[11px]">
                        Your POSP application <span className="font-mono font-bold text-white">{referenceCode}</span> has achieved <span className="font-bold text-emerald-300">Straight-Through Approval</span> in 240ms! All KYC records match official government databases.
                        <br /><br />
                        Please complete your mandatory 15-Hour IC-38 LMS modules to receive your certificate.
                      </p>
                    )}

                    {template === "rework" && (
                      <p className="text-slate-100 leading-relaxed text-[11px]">
                        Our AI pre-capture detected that your uploaded <span className="font-bold text-amber-300">Cancelled Cheque</span> has a quality alert (Blur Score: 18.2).
                        <br /><br />
                        Please tap below to re-upload a clear copy in &lt; 2 minutes so your approval is not delayed.
                      </p>
                    )}

                    {template === "cert" && (
                      <p className="text-slate-100 leading-relaxed text-[11px]">
                        Congratulations! You have successfully passed the IRDAI IC-38 assessment with a score of <span className="font-bold text-emerald-300">94.5%</span>.
                        <br /><br />
                        Your official Appointment Certificate <span className="font-mono font-bold text-white">POSP-2026-CERT-9081</span> has been sealed. Tap below to download.
                      </p>
                    )}

                    {/* Interactive Action Buttons */}
                    <div className="space-y-1.5 pt-1 border-t border-emerald-700/60">
                      {template === "approved" && (
                        <button
                          type="button"
                          className="w-full bg-[#007a64] hover:bg-[#009176] text-white text-[11px] font-bold py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition"
                        >
                          <Sparkles className="h-3.5 w-3.5" /> Start IC-38 Modules (15h)
                        </button>
                      )}
                      {template === "rework" && (
                        <button
                          type="button"
                          className="w-full bg-amber-600 hover:bg-amber-500 text-white text-[11px] font-bold py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition"
                        >
                          ⚡ 1-Click Re-Upload Cheque
                        </button>
                      )}
                      {template === "cert" && (
                        <button
                          type="button"
                          className="w-full bg-cyan-600 hover:bg-cyan-500 text-white text-[11px] font-bold py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition"
                        >
                          📜 Download IRDAI Certificate
                        </button>
                      )}
                    </div>

                    <div className="flex items-center justify-end gap-1 text-[9px] text-slate-300 font-mono pt-1">
                      <span>{dispatchTime}</span>
                      {readState === "sent" ? (
                        <span className="text-slate-400">✓</span>
                      ) : (
                        <CheckCheck className={clsx("h-3 w-3", readState === "read" ? "text-cyan-400" : "text-slate-400")} />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* DLT SMS Screen */
              <div className="flex flex-col h-[400px] bg-slate-950 text-slate-100 p-4 justify-between">
                <div>
                  <div className="border-b border-slate-800 pb-2.5 flex items-center justify-between text-xs font-mono">
                    <span className="font-bold text-cyan-400">TRAI DLT Sender: POLNST-TR</span>
                    <span className="text-slate-500 text-[10px]">Entity: 11071618293041</span>
                  </div>

                  <div className="mt-4 bg-slate-900 border border-slate-800 p-3.5 rounded-2xl text-xs space-y-2">
                    <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                      <span>Govt DLT Approved Header</span>
                      <span>{dispatchTime}</span>
                    </div>

                    {template === "approved" && (
                      <p className="text-slate-200 leading-relaxed font-sans text-[11px]">
                        Dear {candidateName}, your POSP application ({referenceCode}) is approved by PolicyNest. Complete your 15-hr IRDAI IC-38 training at: https://policynest.in/lms/{referenceCode} - POLNST
                      </p>
                    )}

                    {template === "rework" && (
                      <p className="text-slate-200 leading-relaxed font-sans text-[11px]">
                        Dear {candidateName}, your bank cheque upload requires replacement. Please update in &lt; 2 mins at: https://policynest.in/rework/{referenceCode} - POLNST
                      </p>
                    )}

                    {template === "cert" && (
                      <p className="text-slate-200 leading-relaxed font-sans text-[11px]">
                        Dear {candidateName}, congratulations! Your IRDAI POSP Certificate POSP-2026-CERT-9081 is active. Download at: https://policynest.in/cert/9081 - POLNST
                      </p>
                    )}

                    <div className="pt-2 border-t border-slate-800 text-[9px] font-mono text-slate-500 flex items-center justify-between">
                      <span>GSM 7-bit Encoding</span>
                      <span className="text-emerald-400 font-bold">142 / 160 Characters (1 SMS)</span>
                    </div>
                  </div>
                </div>

                <div className="text-center text-[10px] text-slate-500 font-mono">
                  Delivered via Bharti Airtel / Jio DLT Telephony Gateway
                </div>
              </div>
            )}

          </div>
        </div>

        {/* Footer info */}
        <div className="border-t border-slate-800 bg-slate-950 px-5 py-3 flex items-center justify-between text-xs text-slate-400">
          <span className="font-mono text-[11px]">
            Candidate Mobile: <strong className="text-white">{mobile}</strong>
          </span>
          <span className="text-[11px] text-emerald-400 flex items-center gap-1 font-mono">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Webhook Dispatcher Online
          </span>
        </div>

      </div>
    </div>
  );
}
