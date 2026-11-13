"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker
        .register("/sw.js")
        .then(() => {
          // Service worker active
        })
        .catch(() => {
          // Graceful fallback if service workers are disabled or unsupported
        });
    }
  }, []);

  return null;
}
