"use client";

import { Camera, Check, RefreshCw, RotateCcw, RotateCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Alert, Button } from "@/components/ui";
import { normalizeAndOptimizeImage } from "@/lib/imagePrep";

export function GuidedDocumentCapture({
  docLabel,
  onCapture,
  uploading,
}: {
  docLabel: string;
  onCapture: (file: File) => Promise<void>;
  uploading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamReady, setStreamReady] = useState(false);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [quarterTurns, setQuarterTurns] = useState(0);
  const [qualityWarning, setQualityWarning] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  function stopStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setStreamReady(false);
  }

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!open || rawFile) {
      stopStream();
      return;
    }
    let active = true;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access is not available in this browser. Use Upload file instead.");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
      .then((stream) => {
        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setStreamReady(true);
      })
      .catch(() => {
        if (active) {
          setError("Could not access your camera. Grant permission or use Upload file.");
        }
      });

    return () => {
      active = false;
      stopStream();
    };
  }, [open, rawFile]);

  function resetAll() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setRawFile(null);
    setQuarterTurns(0);
    setQualityWarning(null);
    setError(null);
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      setError("Unable to capture camera frame.");
      return;
    }
    const captured = new File([blob], `capture-${Date.now()}.jpg`, { type: "image/jpeg" });
    setPreparing(true);
    try {
      const prepped = await normalizeAndOptimizeImage(captured, { quarterTurns: 0 });
      setQualityWarning(prepped.qualityWarning);
      setRawFile(prepped.file);
      setQuarterTurns(0);
      setPreviewUrl(URL.createObjectURL(prepped.file));
    } finally {
      setPreparing(false);
    }
  }

  async function confirmUpload() {
    if (!rawFile) return;
    setPreparing(true);
    try {
      const finalPrep =
        quarterTurns !== 0
          ? await normalizeAndOptimizeImage(rawFile, { quarterTurns })
          : { file: rawFile, qualityWarning };
      await onCapture(finalPrep.file);
      resetAll();
      setOpen(false);
    } finally {
      setPreparing(false);
    }
  }

  if (!open) {
    return (
      <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(true)} disabled={uploading}>
        <Camera className="h-3.5 w-3.5" /> Guided camera
      </Button>
    );
  }

  return (
    <div className="mt-3 space-y-2.5 rounded-lg border border-brand-200 bg-brand-50/40 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-800">Guided capture · {docLabel}</p>
        <button
          type="button"
          onClick={() => {
            resetAll();
            setOpen(false);
          }}
          className="rounded p-1 text-slate-500 hover:bg-slate-200"
          aria-label="Close guided camera"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {!rawFile ? (
        <>
          <div className="relative overflow-hidden rounded-lg bg-slate-900">
            <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-5">
              <div className="h-full w-full max-w-md rounded-xl border-2 border-dashed border-emerald-400/90 shadow-[0_0_0_9999px_rgba(15,23,42,0.28)]" />
            </div>
            <p className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900/80 px-2.5 py-1 text-[11px] font-medium text-white">
              Align document corners inside the frame · avoid glare
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={() => void captureFrame()} loading={preparing} disabled={!streamReady}>
              <Camera className="h-3.5 w-3.5" /> Capture frame
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                resetAll();
                setOpen(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </>
      ) : (
        <>
          {qualityWarning && <Alert tone="warning">{qualityWarning}</Alert>}
          <div className="flex items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-slate-900 p-2">
            {previewUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={previewUrl}
                alt={`Captured ${docLabel}`}
                style={{ transform: `rotate(${quarterTurns * 90}deg)` }}
                className="max-h-56 w-auto rounded object-contain transition-transform duration-150"
              />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" onClick={() => void confirmUpload()} loading={uploading || preparing}>
              <Check className="h-3.5 w-3.5" /> Use &amp; upload
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setQuarterTurns((q) => (q + 3) % 4)}
              disabled={uploading || preparing}
            >
              <RotateCcw className="h-3.5 w-3.5" /> Rotate left
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setQuarterTurns((q) => (q + 1) % 4)}
              disabled={uploading || preparing}
            >
              <RotateCw className="h-3.5 w-3.5" /> Rotate right
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={resetAll} disabled={uploading || preparing}>
              <RefreshCw className="h-3.5 w-3.5" /> Retake
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
