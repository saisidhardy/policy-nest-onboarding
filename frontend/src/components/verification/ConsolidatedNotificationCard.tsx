"use client";

import { Check, Copy, MessageSquare, Share2, Volume2, VolumeX } from "lucide-react";
import { useState } from "react";
import { Badge, Button } from "@/components/ui";
import { sound } from "@/lib/soundFx";

export interface ConsolidatedNotificationCardProps {
  candidateName: string;
  referenceCode: string;
  reworkItems: Array<{
    title_en: string;
    title_hi: string;
    action_en: string;
    action_hi: string;
    doc_type?: string | null;
  }>;
  reuploadUrl: string;
}

export function ConsolidatedNotificationCard({
  candidateName,
  referenceCode,
  reworkItems,
  reuploadUrl,
}: ConsolidatedNotificationCardProps) {
  const [lang, setLang] = useState<"EN" | "HI">("EN");
  const [copiedKind, setCopiedKind] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState(false);

  if (!reworkItems || reworkItems.length === 0) return null;

  // Build the full multi-point WhatsApp message (friendly, compliant, zero PII)
  const isEn = lang === "EN";
  const greeting = isEn ? `Dear ${candidateName},` : `प्रिय ${candidateName},`;
  const intro = isEn
    ? `Regarding your PolicyNest POSP application (${referenceCode}), our automated verification requires an update for ${reworkItems.length} document(s):`
    : `आपके PolicyNest POSP आवेदन (${referenceCode}) के लिए सत्यापन को पूरा करने हेतु ${reworkItems.length} दस्तावेज़ों में सुधार आवश्यक है:`;

  const itemsText = reworkItems
    .map((it, idx) => {
      const title = isEn ? it.title_en : it.title_hi;
      const action = isEn ? it.action_en : it.action_hi;
      return `${idx + 1}. *${title}*\n   👉 ${action}`;
    })
    .join("\n\n");

  const closing = isEn
    ? `Upload fixes in 1 pass here: ${reuploadUrl}\n(Documents expire after 7 days if unsubmitted)`
    : `सुधार यहाँ अपलोड करें: ${reuploadUrl}\n(दस्तावेज़ जमा न होने पर 7 दिनों में आवेदन समाप्त हो जाता है)`;

  const fullWhatsAppMessage = `${greeting}\n\n${intro}\n\n${itemsText}\n\n${closing}`;

  // Telecom DLT-compliant <= 160 characters single-segment SMS
  // Format: PolicyNest: Action required on POSP App {ref}. Please update {docCount} document(s) at {link}. Helpline: 1800-NEST
  const shortSms = `PolicyNest: Action required on POSP App ${referenceCode}. Please update ${reworkItems.length} document(s) at ${reuploadUrl}. Call 1800-NEST.`;
  const smsLength = shortSms.length;

  const handleCopy = async (text: string, kind: string) => {
    try {
      await navigator.clipboard.writeText(text);
      sound.playClick();
      setCopiedKind(kind);
      setTimeout(() => setCopiedKind(null), 2500);
    } catch {
      // ignore clipboard error
    }
  };

  const handleOpenWhatsApp = () => {
    sound.playClick();
    const encoded = encodeURIComponent(fullWhatsAppMessage);
    const waUrl = `https://wa.me/?text=${encoded}`;
    window.open(waUrl, "_blank", "noopener,noreferrer");
  };

  const handleSpeak = () => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    const textToRead = `${greeting}. ${intro}. ${reworkItems.map((it) => (isEn ? it.title_en : it.title_hi)).join(". ")}. ${closing}`;
    const utterance = new SpeechSynthesisUtterance(textToRead);
    utterance.lang = isEn ? "en-IN" : "hi-IN";
    utterance.rate = 0.95;

    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  return (
    <div className="rounded-xl border border-amber-200/90 bg-gradient-to-br from-amber-50/80 via-white to-amber-50/40 p-5 shadow-sm dark:border-amber-900/40 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-200/60 pb-3 dark:border-amber-900/40">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Single-Pass WhatsApp & SMS Rework Dispatcher
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Rulebook §8 & Recovery Manual §3 compliant consolidated notification
            </p>
          </div>
        </div>

        {/* Language & Voice toggles */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs font-semibold dark:border-slate-800 dark:bg-slate-950">
            <button
              type="button"
              onClick={() => {
                setLang("EN");
                sound.playClick();
              }}
              className={`rounded-md px-2.5 py-1 transition-colors ${
                isEn ? "bg-brand-700 text-white shadow-xs" : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
              }`}
            >
              English
            </button>
            <button
              type="button"
              onClick={() => {
                setLang("HI");
                sound.playClick();
              }}
              className={`rounded-md px-2.5 py-1 transition-colors ${
                !isEn ? "bg-brand-700 text-white shadow-xs" : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
              }`}
            >
              हिन्दी
            </button>
          </div>

          <button
            type="button"
            onClick={handleSpeak}
            className={`inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium transition-colors ${
              speaking
                ? "border-rose-400 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
            }`}
            title="Read aloud notification in selected language"
          >
            {speaking ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5 text-brand-700" />}
            {speaking ? "Stop" : "Read Aloud"}
          </button>
        </div>
      </div>

      {/* Visual Phone Mockup */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {/* Phone Preview */}
        <div className="lg:col-span-2">
          <div className="rounded-xl border border-slate-300 bg-slate-100/80 p-3 shadow-inner dark:border-slate-800 dark:bg-slate-950">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2 text-xs font-semibold text-slate-600 dark:border-slate-800 dark:text-slate-400">
              <span>📱 Candidate Message Preview</span>
              <span className="text-[11px] font-normal text-slate-400">Encrypted · No Raw PII</span>
            </div>
            <div className="mt-3 rounded-lg bg-emerald-50 p-3.5 text-xs font-mono leading-relaxed text-slate-800 shadow-xs dark:bg-emerald-950/40 dark:text-emerald-200">
              <pre className="whitespace-pre-wrap font-sans text-xs">{fullWhatsAppMessage}</pre>
            </div>
          </div>
        </div>

        {/* Action Panel */}
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs shadow-xs dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between font-semibold text-slate-900 dark:text-slate-100">
              <span>Direct WhatsApp Dispatch</span>
              <Badge tone="success">1-Click</Badge>
            </div>
            <p className="mt-1 text-slate-500 dark:text-slate-400">
              Pre-populates a verified WhatsApp message directly on the candidate&apos;s phone.
            </p>
            <Button
              type="button"
              className="mt-3 w-full gap-1.5 bg-emerald-600 font-semibold text-white hover:bg-emerald-700"
              onClick={handleOpenWhatsApp}
            >
              <Share2 className="h-3.5 w-3.5" /> Open in WhatsApp
            </Button>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs shadow-xs dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between font-semibold text-slate-900 dark:text-slate-100">
              <span>DLT 160-Char SMS</span>
              <span className={`font-mono font-bold ${smsLength <= 160 ? "text-emerald-600" : "text-rose-600"}`}>
                {smsLength}/160 chars
              </span>
            </div>
            <div className="mt-2 rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-700 dark:bg-slate-950 dark:text-slate-300">
              {shortSms}
            </div>
            <button
              type="button"
              onClick={() => handleCopy(shortSms, "sms")}
              className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white py-1.5 text-xs font-medium text-slate-700 shadow-xs hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {copiedKind === "sms" ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
              {copiedKind === "sms" ? "SMS Copied to Clipboard!" : "Copy 160-Char SMS"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
