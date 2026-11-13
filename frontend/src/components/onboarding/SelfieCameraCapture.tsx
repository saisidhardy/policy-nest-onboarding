"use client";

import { Camera, RefreshCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Alert, Button } from "@/components/ui";

export function SelfieCameraCapture({
  onCapture,
  uploading,
}: {
  onCapture: (file: File) => Promise<void>;
  uploading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamReady, setStreamReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  function stopStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setStreamReady(false);
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
      .getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false })
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

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      setError("Unable to capture image frame.");
      return;
    }
    const file = new File([blob], `selfie-${Date.now()}.jpg`, { type: "image/jpeg" });
    await onCapture(file);
    setOpen(false);
  }

  if (!open) {
    return (
      <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(true)} disabled={uploading}>
        <Camera className="h-4 w-4" /> Take selfie with camera
      </Button>
    );
  }

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-slate-700">Live camera capture</p>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded p-1 text-slate-500 hover:bg-slate-200"
          aria-label="Close camera"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="relative overflow-hidden rounded-lg bg-slate-900">
        <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-4/5 w-36 rounded-[50%] border-2 border-dashed border-emerald-400/90 shadow-[0_0_0_9999px_rgba(15,23,42,0.22)] sm:w-44" />
        </div>
        <p className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900/80 px-2.5 py-0.5 text-[11px] font-medium text-white">
          Center your face in the oval with even light
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={takePhoto} loading={uploading} disabled={!streamReady}>
          <Camera className="h-4 w-4" /> Capture & upload
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(false)}>
          <RefreshCw className="h-4 w-4" /> Cancel
        </Button>
      </div>
    </div>
  );
}
