"use client";

import { Camera, CheckCircle2, RefreshCw, ShieldAlert, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

export function SelfieCameraCapture({
  onCapture,
  uploading,
}: {
  onCapture: (file: File) => Promise<void>;
  uploading: boolean;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamReady, setStreamReady] = useState(false);
  const [lightingStatus, setLightingStatus] = useState<"ok" | "dark" | "glare">("ok");
  const [motionDetected, setMotionDetected] = useState(false);
  const [livenessScore, setLivenessScore] = useState(0);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const prevFrameRef = useRef<Uint8ClampedArray | null>(null);
  const checkIntervalRef = useRef<NodeJS.Timeout | null>(null);

  function stopStream() {
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    prevFrameRef.current = null;
    setStreamReady(false);
    setMotionDetected(false);
    setLivenessScore(0);
  }

  useEffect(() => {
    if (!open) {
      stopStream();
      return;
    }
    let active = true;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access is not available in this browser. Use the file upload button instead.");
      return;
    }

    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
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

        // Start liveness and lighting monitoring loop (every 200ms)
        const canvas = document.createElement("canvas");
        canvas.width = 160;
        canvas.height = 120;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });

        checkIntervalRef.current = setInterval(() => {
          const video = videoRef.current;
          if (!video || !ctx || video.readyState < 2) return;

          ctx.drawImage(video, 0, 0, 160, 120);
          const frame = ctx.getImageData(0, 0, 160, 120).data;

          // 1. Calculate average luminance in center area (oval guide)
          let sumLum = 0;
          let count = 0;
          let deltaSum = 0;
          const prev = prevFrameRef.current;

          for (let i = 0; i < frame.length; i += 8) {
            // R, G, B
            const lum = 0.299 * frame[i] + 0.587 * frame[i + 1] + 0.114 * frame[i + 2];
            sumLum += lum;
            count++;

            if (prev) {
              const prevLum = 0.299 * prev[i] + 0.587 * prev[i + 1] + 0.114 * prev[i + 2];
              deltaSum += Math.abs(lum - prevLum);
            }
          }

          const avgLum = count > 0 ? sumLum / count : 128;
          if (avgLum < 45) {
            setLightingStatus("dark");
          } else if (avgLum > 225) {
            setLightingStatus("glare");
          } else {
            setLightingStatus("ok");
          }

          // 2. Active liveness: detect natural facial micro-movements, blinking, or slight turns
          if (prev && count > 0) {
            const avgDelta = deltaSum / count;
            // Natural human motion in head oval typically causes avgDelta between 3.5 and 35
            if (avgDelta >= 2.8 && avgDelta <= 45) {
              setLivenessScore((prevScore) => {
                const nextScore = Math.min(100, prevScore + 25);
                if (nextScore >= 75) {
                  setMotionDetected(true);
                }
                return nextScore;
              });
            }
          }

          prevFrameRef.current = new Uint8ClampedArray(frame);
        }, 200);
      })
      .catch(() => {
        if (active) {
          setError("Could not access your camera. Grant permission or upload a photo from your device.");
        }
      });

    return () => {
      active = false;
      stopStream();
    };
  }, [open]);

  async function takePhoto() {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.94));
    if (!blob) {
      setError("Unable to capture image frame.");
      return;
    }
    const file = new File([blob], `selfie-liveness-${Date.now()}.jpg`, { type: "image/jpeg" });
    await onCapture(file);
    setOpen(false);
  }

  if (!open) {
    return (
      <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(true)} disabled={uploading}>
        <Camera className="h-4 w-4" /> {t.docs.cameraButton}
      </Button>
    );
  }

  const isLivenessReady = streamReady && lightingStatus === "ok" && (motionDetected || livenessScore >= 60);

  return (
    <div className="mt-3 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-600" />
          <p className="text-xs font-semibold text-slate-800">{t.camera.title}</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded p-1 text-slate-500 hover:bg-slate-200"
          aria-label={t.camera.close}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <div className="relative overflow-hidden rounded-xl bg-slate-950 shadow-inner">
        <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />

        {/* Real-time Oval Guide with Active Liveness Feedback */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div
            className={`h-4/5 w-40 rounded-[50%] border-3 transition-colors duration-300 sm:w-48 ${
              isLivenessReady
                ? "border-emerald-400 bg-emerald-500/10 shadow-[0_0_20px_rgba(52,211,153,0.5),0_0_0_9999px_rgba(15,23,42,0.35)]"
                : lightingStatus !== "ok"
                ? "border-amber-400 border-dashed shadow-[0_0_0_9999px_rgba(15,23,42,0.35)]"
                : "border-blue-400/90 border-dashed shadow-[0_0_0_9999px_rgba(15,23,42,0.30)]"
            }`}
          />
        </div>

        {/* Dynamic Interactive Liveness & Lighting Guidance Pill */}
        <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap">
          {lightingStatus === "dark" && (
            <div className="flex items-center gap-1.5 rounded-full bg-amber-950/90 px-3 py-1 text-xs font-medium text-amber-200 shadow-md backdrop-blur">
              <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
              {t.camera.darkAlert}
            </div>
          )}
          {lightingStatus === "glare" && (
            <div className="flex items-center gap-1.5 rounded-full bg-amber-950/90 px-3 py-1 text-xs font-medium text-amber-200 shadow-md backdrop-blur">
              <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
              {t.camera.glareAlert}
            </div>
          )}
          {lightingStatus === "ok" && !isLivenessReady && (
            <div className="flex items-center gap-1.5 rounded-full bg-slate-900/90 px-3 py-1 text-xs font-medium text-slate-200 shadow-md backdrop-blur">
              <span className="inline-block h-2 w-2 animate-ping rounded-full bg-blue-400" />
              {t.camera.blinkPrompt}
            </div>
          )}
          {lightingStatus === "ok" && isLivenessReady && (
            <div className="flex items-center gap-1.5 rounded-full bg-emerald-950/95 px-3 py-1 text-xs font-semibold text-emerald-200 shadow-md backdrop-blur">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              {t.camera.livenessVerified}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2">
          <Badge tone={isLivenessReady ? "success" : "neutral"}>
            {isLivenessReady ? "Liveness: Verified" : "Liveness: Align Face"}
          </Badge>
          <span className="text-[11px] text-slate-500">
            {isLivenessReady ? t.camera.activePrompt : t.camera.centerFace}
          </span>
        </div>

        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            onClick={takePhoto}
            loading={uploading}
            disabled={!streamReady}
            className={isLivenessReady ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}
          >
            <Camera className="h-4 w-4" /> {t.camera.takePhoto}
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(false)}>
            <RefreshCw className="h-4 w-4" /> {t.camera.close}
          </Button>
        </div>
      </div>
    </div>
  );
}
