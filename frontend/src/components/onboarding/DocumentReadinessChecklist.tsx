"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CreditCard,
  FileBadge,
  FileCheck,
  FileSpreadsheet,
  FileText,
  HelpCircle,
  Info,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import React, { useState } from "react";
import {
  DOCUMENT_GUIDANCE_MAP,
  type DocumentRequirement,
} from "@/lib/documentGuidance";
import type { ApplicationDocument, DocumentType } from "@/lib/types";

export interface DocumentReadinessChecklistProps {
  documents?: ApplicationDocument[];
  compact?: boolean;
  onOpenHelp?: (docType: DocumentType) => void;
  onSelectDocument?: (docType: DocumentType) => void;
  showExpandableGuidance?: boolean;
}

const DOC_ORDER: DocumentType[] = [
  "PAN_CARD",
  "AADHAAR_FRONT",
  "AADHAAR_BACK",
  "CLASS_10_MARKSHEET",
  "BANK_DOCUMENT",
  "APPLICANT_SELFIE",
];

export function DocumentReadinessChecklist({
  documents = [],
  compact = false,
  onOpenHelp,
  onSelectDocument,
  showExpandableGuidance = true,
}: DocumentReadinessChecklistProps) {
  const [expandedDoc, setExpandedDoc] = useState<DocumentType | null>(null);

  // Map documents by doc_type
  const docMap = new Map<DocumentType, ApplicationDocument>();
  for (const doc of documents) {
    if (doc.is_current) {
      docMap.set(doc.doc_type, doc);
    }
  }

  const getDocStatus = (type: DocumentType) => {
    const doc = docMap.get(type);
    if (!doc) {
      return {
        label: "Ready to upload",
        state: "PENDING" as const,
        badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
        icon: FileText,
      };
    }
    const st = doc.status?.toUpperCase() || "";
    if (st === "VERIFIED" || st === "VALIDATED") {
      return {
        label: "Verified automatically",
        state: "VERIFIED" as const,
        badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
        icon: CheckCircle2,
      };
    }
    if (st === "NEEDS_MORE_INFO" || st === "CORRECTION_REQUIRED" || st === "REJECTED") {
      return {
        label: "Clearer image required",
        state: "CORRECTION" as const,
        badgeClass: "bg-amber-50 text-amber-800 border-amber-300",
        icon: AlertTriangle,
      };
    }
    if (st === "IN_REVIEW" || st === "HUMAN_REVIEW") {
      return {
        label: "Sent to a reviewer",
        state: "REVIEW" as const,
        badgeClass: "bg-sky-50 text-sky-800 border-sky-200",
        icon: ShieldCheck,
      };
    }
    return {
      label: "Uploaded — processing",
      state: "UPLOADED" as const,
      badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
      icon: FileCheck,
    };
  };

  const getDocIcon = (type: DocumentType) => {
    switch (type) {
      case "PAN_CARD":
        return CreditCard;
      case "AADHAAR_FRONT":
      case "AADHAAR_BACK":
        return FileBadge;
      case "CLASS_10_MARKSHEET":
        return FileText;
      case "BANK_DOCUMENT":
        return FileSpreadsheet;
      case "APPLICANT_SELFIE":
        return Camera;
      default:
        return FileText;
    }
  };

  return (
    <div className="space-y-3" aria-label="Six mandatory compliance documents checklist">
      {DOC_ORDER.map((type, idx) => {
        const guide: DocumentRequirement = DOCUMENT_GUIDANCE_MAP[type];
        const status = getDocStatus(type);
        const IconComponent = getDocIcon(type);
        const isExpanded = expandedDoc === type;

        return (
          <div
            key={type}
            className={clsx(
              "rounded-xl border transition-all duration-150",
              status.state === "VERIFIED"
                ? "border-emerald-200 bg-emerald-50/20"
                : status.state === "CORRECTION"
                ? "border-amber-300 bg-amber-50/20"
                : "border-slate-200 bg-white hover:border-slate-300"
            )}
          >
            <div className="flex items-center justify-between p-3.5 sm:p-4">
              <div
                className="flex items-center gap-3 min-w-0 cursor-pointer flex-1"
                onClick={() => {
                  if (onSelectDocument) {
                    onSelectDocument(type);
                  } else if (showExpandableGuidance) {
                    setExpandedDoc(isExpanded ? null : type);
                  }
                }}
              >
                <div
                  className={clsx(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-sm font-semibold",
                    status.state === "VERIFIED"
                      ? "border-emerald-300 bg-emerald-100 text-emerald-800"
                      : status.state === "CORRECTION"
                      ? "border-amber-300 bg-amber-100 text-amber-900"
                      : "border-slate-200 bg-slate-100 text-slate-700"
                  )}
                >
                  <IconComponent className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-500">#{idx + 1}</span>
                    <h4 className="truncate text-sm font-bold text-slate-900">
                      {guide.shortLabel}
                    </h4>
                  </div>
                  {!compact && (
                    <p className="mt-0.5 line-clamp-1 text-xs text-slate-600">
                      {guide.purpose}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 ml-3">
                <span
                  className={clsx(
                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
                    status.badgeClass
                  )}
                >
                  <status.icon className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">{status.label}</span>
                </span>

                {showExpandableGuidance && (
                  <button
                    type="button"
                    onClick={() => setExpandedDoc(isExpanded ? null : type)}
                    aria-expanded={isExpanded}
                    aria-label={`Toggle guidance for ${guide.shortLabel}`}
                    className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
                  >
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Expandable Guidance Drawer */}
            {showExpandableGuidance && isExpanded && (
              <div className="border-t border-slate-100 bg-slate-50/70 p-4 space-y-3.5 text-xs text-slate-700 rounded-b-xl animate-fadeIn">
                <div className="rounded-lg bg-blue-50/80 border border-blue-200 p-2.5 text-blue-950 flex items-start gap-2">
                  <Info className="h-4 w-4 text-blue-700 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Why this is required: </span>
                    {guide.whyNeeded}
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <p className="font-bold text-slate-900 flex items-center gap-1.5">
                      <FileCheck className="h-3.5 w-3.5 text-emerald-600" /> What must be visible:
                    </p>
                    <ul className="list-disc pl-4 space-y-1 text-slate-600">
                      {guide.mustShow.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="space-y-1.5">
                    <p className="font-bold text-slate-900 flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-amber-600" /> Photography coaching:
                    </p>
                    <ul className="list-disc pl-4 space-y-1 text-slate-600">
                      {guide.photoGuidance.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-1">
                  <p className="font-bold text-slate-900">Common rejection reasons to avoid:</p>
                  <ul className="list-disc pl-4 space-y-0.5 text-slate-600">
                    {guide.commonProblems.map((prob, i) => (
                      <li key={i}>{prob}</li>
                    ))}
                  </ul>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-200/60 text-[11px] text-slate-500">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-slate-400" />
                    <span>Accepted: {guide.acceptedFormats.join(", ")} (up to 10 MB)</span>
                  </div>
                  {onOpenHelp && (
                    <button
                      type="button"
                      onClick={() => onOpenHelp(type)}
                      className="font-semibold text-brand-700 hover:text-brand-800 hover:underline flex items-center gap-1"
                    >
                      <HelpCircle className="h-3 w-3" /> Ask Copilot about this document
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
