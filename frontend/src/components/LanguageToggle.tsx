"use client";

import { Languages } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export function LanguageToggle({ className }: { className?: string }) {
  const { locale, setLocale } = useI18n();

  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white/90 px-2.5 py-1 text-xs shadow-sm backdrop-blur transition hover:border-slate-400 ${className ?? ""}`}
      role="group"
      aria-label="Language selector"
    >
      <Languages className="h-3.5 w-3.5 text-blue-600" />
      <button
        type="button"
        onClick={() => setLocale("en")}
        className={`rounded px-1.5 py-0.5 font-medium transition ${
          locale === "en"
            ? "bg-blue-600 text-white shadow-xs"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        English
      </button>
      <span className="text-slate-300">|</span>
      <button
        type="button"
        onClick={() => setLocale("hi")}
        className={`rounded px-1.5 py-0.5 font-medium transition ${
          locale === "hi"
            ? "bg-blue-600 text-white shadow-xs"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        हिंदी
      </button>
    </div>
  );
}
