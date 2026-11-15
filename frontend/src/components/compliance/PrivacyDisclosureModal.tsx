"use client";

import {
  EyeOff,
  Lock,
  Server,
  Shield,
  Smartphone,
  Users,
  X,
} from "lucide-react";
import React from "react";
import { Button } from "@/components/ui";

export interface PrivacyDisclosureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PrivacyDisclosureModal({ isOpen, onClose }: PrivacyDisclosureModalProps) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacy-disclosure-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-xl border border-slate-200 space-y-5 text-slate-800">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-800 font-bold">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h2 id="privacy-disclosure-title" className="text-lg font-bold text-slate-900">
                Privacy, Security & Data Protection
              </h2>
              <p className="text-xs text-slate-500">
                Statutory compliance with DPDP Act 2023, UIDAI Aadhaar Regulations, and IRDAI standards
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 text-xs text-slate-600 leading-relaxed">
          {/* Section 1: Storage & Encryption */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
              <Lock className="h-4 w-4 text-brand-700" />
              <span>How your documents are stored and encrypted</span>
            </div>
            <p>
              Your documents are uploaded over TLS 1.3 encrypted HTTPS connections directly to secure private cloud storage. All files are encrypted at rest using industry-standard AES-256 encryption. Files are never stored in public buckets and are only accessible through short-lived (15-minute) authenticated presigned URLs.
            </p>
          </div>

          {/* Section 2: Aadhaar Masking */}
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-emerald-950 text-sm">
              <EyeOff className="h-4 w-4 text-emerald-700" />
              <span>Aadhaar data minimization and masking</span>
            </div>
            <p className="text-emerald-900">
              In accordance with UIDAI regulations and the Digital Personal Data Protection (DPDP) Act 2023, PolicyNest automatically masks the first 8 digits of your Aadhaar number during ingestion. Only the last 4 digits (e.g., XXXX-XXXX-1234) are stored for audit and verification purposes. Your full 12-digit Aadhaar number is never stored in plaintext database records.
            </p>
          </div>

          {/* Section 3: AI Copilot Privacy */}
          <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-indigo-950 text-sm">
              <Server className="h-4 w-4 text-indigo-700" />
              <span>How AI assistance handles your information</span>
            </div>
            <p className="text-indigo-900">
              The PolicyNest AI Copilot is grounded strictly in the official POSP Recovery and Quick-Start manual rules. <strong>No document images, full government ID numbers, or bank account credentials are ever sent to external AI models.</strong> The assistant only receives your current stage and validation status to provide contextual guidance.
            </p>
          </div>

          {/* Section 4: Human Review & Access Control */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
              <Users className="h-4 w-4 text-blue-700" />
              <span>Who can access your application</span>
            </div>
            <p>
              Only authorized compliance officers and certified KYC reviewers with verified role-based access control (RBAC) permissions can view your application details. Every access event and document inspection is logged permanently in an immutable audit ledger.
            </p>
          </div>

          {/* Section 5: Shared Devices */}
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-amber-950 text-sm">
              <Smartphone className="h-4 w-4 text-amber-700" />
              <span>Using PolicyNest on a shared or public computer</span>
            </div>
            <p className="text-amber-900">
              Because your draft saves continuously to your authenticated cloud account, always tap <strong>Sign Out</strong> in the top navigation when using a cyber café, shared mobile device, or office kiosk. Signing out completely destroys all local session tokens.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-slate-100">
          <span className="text-[11px] text-slate-500">
            PolicyNest InsurTech Platform · Certified IRDAI Compliance Architecture
          </span>
          <Button type="button" variant="primary" size="sm" onClick={onClose}>
            I understand
          </Button>
        </div>
      </div>
    </div>
  );
}
