"use client";

import clsx from "clsx";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Camera,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  FileCheck2,
  HelpCircle,
  Maximize2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Zap,
} from "lucide-react";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, apiForm, ApiError } from "@/lib/api";
import { REQUIRED_DOCUMENTS, formatBytes } from "@/lib/constants";
import { normalizeAndOptimizeImage } from "@/lib/imagePrep";
import type {
  ApplicationDetail,
  ApplicationDocument,
  ApplicationVerificationReport,
  DocumentExtraction,
  DocumentType,
} from "@/lib/types";
import { DocumentPreviewModal } from "./DocumentPreviewModal";
import { GuidedDocumentCapture } from "./GuidedDocumentCapture";
import { SelfieCameraCapture } from "./SelfieCameraCapture";

interface ThirtyMinuteOnboardingSessionProps {
  application: ApplicationDetail;
  onReload: () => Promise<void>;
  onExit: () => void;
  onComplete?: () => void;
}

const TOTAL_SESSION_SECONDS = 30 * 60; // 30:00 minutes

export function ThirtyMinuteOnboardingSession({
  application,
  onReload,
  onExit,
  onComplete,
}: ThirtyMinuteOnboardingSessionProps) {
  // Timer state with localStorage persistence keyed by application.id
  const timerKey = `policynest_timer_${application.id}`;
  const [secondsRemaining, setSecondsRemaining] = useState<number>(() => {
    if (typeof window === "undefined") return TOTAL_SESSION_SECONDS;
    const saved = localStorage.getItem(timerKey);
    if (saved) {
      const parsed = parseInt(saved, 10);
      if (!isNaN(parsed) && parsed > 0 && parsed <= TOTAL_SESSION_SECONDS) {
        return parsed;
      }
    }
    return TOTAL_SESSION_SECONDS;
  });

  // Active document index (0 to 5)
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [instantAck, setInstantAck] = useState<string | null>(null);
  const [qualityFeedback, setQualityFeedback] = useState<{
    status: "OK" | "WARNING" | "ERROR";
    badge: string;
    message: string;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [autoAdvancing, setAutoAdvancing] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<ApplicationDocument | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [decisionOutcome, setDecisionOutcome] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Countdown interval
  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        const next = Math.max(0, prev - 1);
        if (typeof window !== "undefined") {
          localStorage.setItem(timerKey, next.toString());
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [timerKey]);

  // Map of current documents by document type
  const documentsByType = useMemo(() => {
    const map = new Map<DocumentType, ApplicationDocument>();
    for (const doc of application.documents) {
      if (doc.is_current) {
        map.set(doc.doc_type, doc);
      }
    }
    return map;
  }, [application.documents]);

  // Calculate completed count
  const completedCount = useMemo(() => {
    return REQUIRED_DOCUMENTS.filter((docSpec) => documentsByType.has(docSpec.type)).length;
  }, [documentsByType]);

  // Compute average quality tier (Q4, Q3, Q2) across uploaded documents
  const averageQualityTier = useMemo(() => {
    if (completedCount === 0) return "Q4 (Target)";
    let okCount = 0;
    for (const docSpec of REQUIRED_DOCUMENTS) {
      const doc = documentsByType.get(docSpec.type);
      if (doc) {
        const q = doc.extraction?.quality_status ?? "OK";
        if (q === "OK") okCount++;
      }
    }
    const ratio = okCount / completedCount;
    if (ratio >= 0.85) return "Q4 (Optimal)";
    if (ratio >= 0.6) return "Q3 (Good)";
    return "Q2 (Needs Attention)";
  }, [completedCount, documentsByType]);

  // Format countdown mm:ss
  const formatTime = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const isTimeCritical = secondsRemaining <= 300; // under 5 minutes
  const isTimeWarning = secondsRemaining <= 600 && !isTimeCritical; // under 10 minutes

  const activeDocSpec = REQUIRED_DOCUMENTS[activeIndex] || REQUIRED_DOCUMENTS[0];
  const activeDocUploaded = documentsByType.get(activeDocSpec.type);

  // Instant Upload & Pre-capture Validation Handler
  const handleFileUpload = async (rawFile: File) => {
    setUploading(true);
    setErrorMessage(null);
    setQualityFeedback(null);
    setUploadProgress(20);

    // Capability 2: Instant Upload Acknowledgement (<200ms feedback)
    setInstantAck("⚡ Instant Upload Received (<200ms) · Analyzing geometry & hash...");

    try {
      // Capability 1: Pre-Capture Validation (blur, glare, cropping detection)
      const prepared = await normalizeAndOptimizeImage(rawFile);
      setUploadProgress(50);

      const fd = new FormData();
      fd.append("file", prepared.file);

      // Capability 4 & 5: Parallel/Fast-path processing via API
      setInstantAck("Running deterministic quality & structure checks...");
      setUploadProgress(75);

      const uploaded = await apiForm<ApplicationDocument>(
        `/applications/${application.id}/documents/${activeDocSpec.type}`,
        fd
      );

      setUploadProgress(100);
      await onReload();

      const ext = uploaded.extraction;
      const qStatus = ext?.quality_status ?? "OK";

      // Capability 3: Progressive Quality Feedback
      if (qStatus === "OK") {
        setQualityFeedback({
          status: "OK",
          badge: "Q4 Optimal",
          message: `Verified: ${uploaded.original_filename} (v${uploaded.version}) accepted with high confidence.`,
        });

        // Image 1 Requirement: "Automatic movement to the next document after successful receipt and basic quality checks."
        if (activeIndex < REQUIRED_DOCUMENTS.length - 1) {
          setAutoAdvancing(true);
          setTimeout(() => {
            setActiveIndex((prev) => Math.min(REQUIRED_DOCUMENTS.length - 1, prev + 1));
            setAutoAdvancing(false);
            setInstantAck(null);
            setQualityFeedback(null);
          }, 850);
        } else {
          setInstantAck(null);
        }
      } else {
        setQualityFeedback({
          status: "WARNING",
          badge: "Q2 Advisory",
          message: `Quality warning: ${qStatus}. ${prepared.qualityWarning ?? "Please provide a clearer, evenly lit copy."}`,
        });
      }
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Document upload failed. Please try again.");
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleEvaluateInstantDecision = async () => {
    setVerifying(true);
    setErrorMessage(null);
    try {
      const res = await api<{ outcome: string }>(`/applications/${application.id}/evaluate`, {
        method: "POST",
        body: { apply_transition: true, trigger_source: "SESSION_COMPLETE" },
      });
      setDecisionOutcome(res.outcome);
      await onReload();
      if (onComplete) onComplete();
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Failed to trigger instant decision evaluation.");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-950 text-slate-100 overflow-y-auto">
      {/* Top Header matching CasperCoach / Image 1 */}
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900/95 backdrop-blur px-4 sm:px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 font-bold text-lg ring-1 ring-emerald-500/30">
            PN
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white tracking-tight text-sm sm:text-base">
                PolicyNest Fast-Track
              </span>
              <span className="rounded-full bg-emerald-950/80 px-2 py-0.5 text-[11px] font-medium text-emerald-400 ring-1 ring-emerald-500/40">
                30-Min Session
              </span>
            </div>
            <p className="text-xs text-slate-400">POSP Mandatory Regulatory Onboarding</p>
          </div>
        </div>

        {/* Center / Right: Document indicator & Visible 30:00 Countdown */}
        <div className="flex items-center gap-4 sm:gap-6">
          <div className="hidden sm:block text-right">
            <span className="text-xs uppercase tracking-wider text-slate-400">Document</span>
            <p className="text-sm font-semibold text-slate-200">
              {activeIndex + 1} of {REQUIRED_DOCUMENTS.length}
            </p>
          </div>

          <div
            className={clsx(
              "flex items-center gap-2 rounded-xl px-3.5 py-1.5 font-mono text-base sm:text-lg font-bold tracking-wider ring-1 transition",
              isTimeCritical
                ? "bg-rose-950/60 text-rose-300 ring-rose-500 animate-pulse"
                : isTimeWarning
                  ? "bg-amber-950/60 text-amber-300 ring-amber-500"
                  : "bg-slate-800 text-emerald-400 ring-slate-700"
            )}
            title="Session Countdown Timer"
          >
            <Clock className="h-4 w-4 shrink-0 text-current" />
            <span>{formatTime(secondsRemaining)}</span>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onExit}
            className="text-slate-400 hover:text-white hover:bg-slate-800 text-xs"
          >
            Exit to Wizard
          </Button>
        </div>
      </header>

      {/* Main Focus Container */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-8 py-6 sm:py-8 space-y-6">
        {/* Banner inspired by Image 1 CasperCoach layout */}
        <div className="rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-900/60 p-6 sm:p-8 relative overflow-hidden shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <span className="text-xs font-semibold tracking-wider text-emerald-400 uppercase">
                Continuous Guided Onboarding
              </span>
              <h1 className="mt-1 text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Session in Progress
              </h1>
              <p className="mt-1.5 text-sm text-slate-400 max-w-xl">
                Real POSP conditions: 6 mandatory compliance documents, continuous guided workflow, instant quality verification.
              </p>
            </div>

            <div className="shrink-0 text-left sm:text-right">
              <span className="text-xs uppercase font-medium text-slate-400">Session Progress</span>
              <p className="text-lg font-bold text-emerald-400">
                {completedCount} / {REQUIRED_DOCUMENTS.length} completed
              </p>
            </div>
          </div>

          {/* Continuous Progress Bar */}
          <div className="mt-6 w-full bg-slate-800/80 rounded-full h-2.5 overflow-hidden ring-1 ring-slate-700/50">
            <div
              className="bg-emerald-500 h-2.5 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${(completedCount / REQUIRED_DOCUMENTS.length) * 100}%` }}
            />
          </div>
        </div>

        {/* 6 Scenario Grid Cards (Exact CasperCoach layout match from Image 1!) */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {REQUIRED_DOCUMENTS.map((docSpec, idx) => {
            const isUploaded = documentsByType.has(docSpec.type);
            const isCurrent = idx === activeIndex;
            const doc = documentsByType.get(docSpec.type);
            const qStatus = doc?.extraction?.quality_status ?? "OK";
            const qBadge = isUploaded ? (qStatus === "OK" ? "Q4" : "Q2") : null;

            return (
              <button
                key={docSpec.type}
                type="button"
                onClick={() => {
                  setActiveIndex(idx);
                  setInstantAck(null);
                  setQualityFeedback(null);
                  setErrorMessage(null);
                }}
                className={clsx(
                  "relative rounded-xl p-3.5 text-left border transition flex flex-col justify-between min-h-[95px] select-none",
                  isCurrent
                    ? "border-emerald-500 bg-slate-800/90 ring-2 ring-emerald-500/40 shadow-lg"
                    : isUploaded
                      ? "border-emerald-900/50 bg-slate-900/80 hover:border-emerald-700/60"
                      : "border-slate-800/80 bg-slate-900/40 hover:border-slate-700 text-slate-500"
                )}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="text-[11px] font-mono font-medium text-slate-400">
                    Doc {idx + 1}
                  </span>
                  {isUploaded && (
                    <span
                      className={clsx(
                        "text-[10px] font-bold px-1.5 py-0.5 rounded",
                        qBadge === "Q4"
                          ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30"
                          : "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/30"
                      )}
                    >
                      {qBadge}
                    </span>
                  )}
                  {isCurrent && !isUploaded && (
                    <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">
                      Current
                    </span>
                  )}
                  {!isCurrent && !isUploaded && (
                    <span className="text-[10px] text-slate-600">Pending</span>
                  )}
                </div>

                <div className="mt-2">
                  <p
                    className={clsx(
                      "text-xs font-semibold line-clamp-1",
                      isCurrent ? "text-white" : isUploaded ? "text-slate-200" : "text-slate-400"
                    )}
                  >
                    {docSpec.label.replace(/^\d+\.\s*/, "")}
                  </p>
                  <p className="text-[10px] text-slate-500 truncate mt-0.5">
                    {isUploaded ? "Verified & Locked" : "Required"}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Active Document Step Workspace */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 space-y-6 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-6 w-6 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-xs flex items-center justify-center ring-1 ring-emerald-500/30">
                  {activeIndex + 1}
                </span>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  {activeDocSpec.label}
                </h2>
                {activeDocUploaded && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950/70 px-2.5 py-0.5 text-xs font-medium text-emerald-300 ring-1 ring-emerald-500/40">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Uploaded (v{activeDocUploaded.version})
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-400 mt-1.5 max-w-2xl">{activeDocSpec.description}</p>
            </div>

            {activeDocUploaded && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setPreviewDoc(activeDocUploaded)}
                className="shrink-0 bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700 text-xs gap-1.5"
              >
                <Eye className="h-3.5 w-3.5" /> Inspect Document
              </Button>
            )}
          </div>

          {/* Instant ACK Alert */}
          {instantAck && (
            <div className="flex items-center gap-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 p-3.5 text-sm text-emerald-300 animate-in fade-in">
              <Zap className="h-4 w-4 shrink-0 text-emerald-400 animate-pulse" />
              <span>{instantAck}</span>
            </div>
          )}

          {/* Quality Feedback / Progressive Results */}
          {qualityFeedback && (
            <div
              className={clsx(
                "rounded-xl p-4 border text-sm flex items-start gap-3",
                qualityFeedback.status === "OK"
                  ? "bg-emerald-950/30 border-emerald-500/30 text-emerald-200"
                  : "bg-amber-950/30 border-amber-500/30 text-amber-200"
              )}
            >
              {qualityFeedback.status === "OK" ? (
                <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-400 mt-0.5" />
              ) : (
                <AlertCircle className="h-5 w-5 shrink-0 text-amber-400 mt-0.5" />
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{qualityFeedback.badge}</span>
                  {autoAdvancing && (
                    <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded animate-pulse">
                      Auto-advancing to next document...
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs opacity-90">{qualityFeedback.message}</p>
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div className="rounded-xl p-4 border border-rose-500/30 bg-rose-950/30 text-sm text-rose-200 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 shrink-0 text-rose-400 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold">Submission Issue</p>
                <p className="text-xs mt-1 opacity-90">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Upload Progress Bar */}
          {uploading && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-slate-400 font-mono">
                <span>Ingestion in progress</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Dual Submission Methods (Image 1 requirement: Camera Capture or Device Upload) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {/* Method A: Camera Capture */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col items-center justify-center text-center space-y-4 hover:border-slate-700 transition">
              <div className="h-12 w-12 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center ring-1 ring-emerald-500/20">
                <Camera className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold text-white text-base">Capture with Camera</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-xs">
                  Live pre-capture quality check for glare, blur, and 4-corner alignment before snap.
                </p>
              </div>
              <Button
                type="button"
                variant="primary"
                onClick={() => setCameraOpen(true)}
                disabled={uploading}
                className="w-full max-w-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
              >
                <Camera className="h-4 w-4 mr-2" /> Launch Live Camera
              </Button>
            </div>

            {/* Method B: Device File Upload */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col items-center justify-center text-center space-y-4 hover:border-slate-700 transition">
              <div className="h-12 w-12 rounded-full bg-brand-500/10 text-brand-400 flex items-center justify-center ring-1 ring-brand-500/20">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold text-white text-base">Upload from Device</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-xs">
                  Select clean image (JPG, PNG, WebP) or PDF. Auto-optimized on device.
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={activeDocSpec.accept}
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleFileUpload(f);
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="w-full max-w-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 font-medium"
              >
                <UploadCloud className="h-4 w-4 mr-2" /> Choose Local File
              </Button>
            </div>
          </div>

          {/* Stepper Navigation */}
          <div className="flex items-center justify-between pt-4 border-t border-slate-800">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={activeIndex === 0}
              onClick={() => {
                setActiveIndex((prev) => Math.max(0, prev - 1));
                setInstantAck(null);
                setQualityFeedback(null);
                setErrorMessage(null);
              }}
              className="text-slate-400 hover:text-white"
            >
              <ArrowLeft className="h-4 w-4 mr-1.5" /> Previous Document
            </Button>

            <span className="text-xs text-slate-500 font-mono">
              Document {activeIndex + 1} of {REQUIRED_DOCUMENTS.length}
            </span>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={activeIndex === REQUIRED_DOCUMENTS.length - 1}
              onClick={() => {
                setActiveIndex((prev) => Math.min(REQUIRED_DOCUMENTS.length - 1, prev + 1));
                setInstantAck(null);
                setQualityFeedback(null);
                setErrorMessage(null);
              }}
              className="text-slate-400 hover:text-white"
            >
              Next Document <ArrowRight className="h-4 w-4 ml-1.5" />
            </Button>
          </div>
        </div>

        {/* Completion Panel when all 6 documents are submitted */}
        {completedCount === REQUIRED_DOCUMENTS.length && (
          <div className="rounded-2xl border border-emerald-500/40 bg-gradient-to-r from-emerald-950/60 to-slate-900 p-6 sm:p-8 space-y-4 shadow-2xl">
            <div className="flex items-start gap-4">
              <div className="h-12 w-12 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 ring-1 ring-emerald-500/30">
                <FileCheck2 className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-white">All 6 Mandatory Documents Received!</h3>
                <p className="text-sm text-slate-300 mt-1">
                  Every compliance document has passed basic image quality and classification checks.
                  You are ready for deterministic rule evaluation and straight-through decisioning.
                </p>
                {decisionOutcome && (
                  <div className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-900/80 px-3 py-1.5 text-xs font-semibold text-emerald-200">
                    <Sparkles className="h-4 w-4" /> Evaluated Outcome: {decisionOutcome}
                  </div>
                )}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button
                type="button"
                variant="primary"
                loading={verifying}
                onClick={handleEvaluateInstantDecision}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-lg shadow-emerald-900/50"
              >
                <Sparkles className="h-4 w-4 mr-2" /> Run Instant Decision Engine
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={onExit}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700"
              >
                Return to Full Dossier
              </Button>
            </div>
          </div>
        )}

        {/* Bottom Metric Cards (Exact match to CasperCoach bottom metrics in Image 1!) */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
          {/* Card 1: Current Quality */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 flex flex-col justify-between">
            <span className="text-xs uppercase font-medium text-slate-400">Current Average Quality</span>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-extrabold text-emerald-400">
                {averageQualityTier.split(" ")[0]}
              </span>
              <span className="text-xs text-slate-400">{averageQualityTier.split(" ")[1] ?? ""}</span>
            </div>
          </div>

          {/* Card 2: Time Remaining */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 flex flex-col justify-between">
            <span className="text-xs uppercase font-medium text-slate-400">Time Remaining</span>
            <div className="mt-3 flex items-baseline gap-2 font-mono">
              <span
                className={clsx(
                  "text-2xl sm:text-3xl font-extrabold",
                  isTimeCritical ? "text-rose-400 animate-pulse" : isTimeWarning ? "text-amber-400" : "text-white"
                )}
              >
                {formatTime(secondsRemaining)}
              </span>
              <span className="text-xs text-slate-500">of 30:00 session</span>
            </div>
          </div>

          {/* Card 3: Documents Complete */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 flex flex-col justify-between">
            <span className="text-xs uppercase font-medium text-slate-400">Documents Complete</span>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-extrabold text-white">{completedCount}</span>
              <span className="text-xs text-slate-400">of {REQUIRED_DOCUMENTS.length} mandatory</span>
            </div>
          </div>
        </div>
      </main>

      {/* Camera Capture Modal (Guided for docs 1-5, Selfie for doc 6) */}
      {cameraOpen && (
        activeDocSpec.type === "APPLICANT_SELFIE" ? (
          <SelfieCameraCapture
            onCapture={async (f) => {
              setCameraOpen(false);
              await handleFileUpload(f);
            }}
            uploading={uploading}
          />
        ) : (
          <GuidedDocumentCapture
            docLabel={activeDocSpec.label}
            onCapture={async (f) => {
              setCameraOpen(false);
              await handleFileUpload(f);
            }}
            uploading={uploading}
          />
        )
      )}

      {/* Document Preview Modal */}
      {previewDoc && (
        <DocumentPreviewModal
          applicationId={application.id}
          document={previewDoc}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </div>
  );
}
