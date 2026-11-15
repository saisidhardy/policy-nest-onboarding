"use client";

import {
  Camera,
  FileCheck,
  Maximize2,
  Sparkles,
  Sun,
  ZapOff,
} from "lucide-react";
import React from "react";
import { DOCUMENT_GUIDANCE_MAP } from "@/lib/documentGuidance";
import type { DocumentType } from "@/lib/types";

export interface PhotoCoachingCardProps {
  docType?: DocumentType;
  compact?: boolean;
}

export function PhotoCoachingCard({ docType, compact = false }: PhotoCoachingCardProps) {
  const guide = docType ? DOCUMENT_GUIDANCE_MAP[docType] : null;

  if (compact) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-950 flex items-start gap-2.5">
        <Sparkles className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-bold text-amber-900">Good photos pass the first time</p>
          <p className="text-amber-800">
            Daylight, flash OFF, all 4 corners visible, flat surface. Avoid shadows or fingers covering text.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-brand-200 bg-gradient-to-br from-brand-50/50 to-emerald-50/30 p-4 space-y-3 text-xs text-slate-700 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-700 text-white">
            <Camera className="h-4 w-4" />
          </div>
          <div>
            <h4 className="font-bold text-slate-900">
              {guide ? `Photography Coaching · ${guide.shortLabel}` : "Photography Coaching"}
            </h4>
            <p className="text-[11px] text-slate-500">
              Good photos pass first time: Follow these 4 simple steps to ensure automatic verification without reviewer delay
            </p>
          </div>
        </div>
        <span className="rounded-full bg-emerald-100 text-emerald-800 font-bold px-2.5 py-0.5 text-[10px]">
          99% Pass Rate
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 pt-1">
        <div className="rounded-lg border border-slate-200 bg-white p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 font-bold text-slate-900">
            <Sun className="h-3.5 w-3.5 text-amber-600" />
            <span>1. Bright Daylight</span>
          </div>
          <p className="text-[11px] text-slate-600">
            Photograph in natural daylight or under a desk lamp. Avoid deep shadows across the text.
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 font-bold text-slate-900">
            <ZapOff className="h-3.5 w-3.5 text-rose-600" />
            <span>2. Flash OFF</span>
          </div>
          <p className="text-[11px] text-slate-600">
            Turn camera flash off. Laminated PAN and Aadhaar cards reflect flash glare and wash out numbers.
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 font-bold text-slate-900">
            <Maximize2 className="h-3.5 w-3.5 text-blue-600" />
            <span>3. All 4 Corners</span>
          </div>
          <p className="text-[11px] text-slate-600">
            Ensure all 4 outer borders of the document are visible. Do not crop tightly into the text.
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 font-bold text-slate-900">
            <FileCheck className="h-3.5 w-3.5 text-emerald-600" />
            <span>4. Flat & Clear</span>
          </div>
          <p className="text-[11px] text-slate-600">
            Lay document flat on a dark table. Do not hold it with fingers covering name or numbers.
          </p>
        </div>
      </div>

      {guide && guide.photoGuidance.length > 0 && (
        <div className="rounded-lg border border-slate-200/80 bg-white/80 p-2.5 space-y-1">
          <p className="font-bold text-slate-900">Document-specific tip:</p>
          <ul className="list-disc pl-4 space-y-0.5 text-slate-600 text-[11px]">
            {guide.photoGuidance.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
