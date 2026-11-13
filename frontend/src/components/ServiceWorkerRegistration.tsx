"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => {
          if (process.env.NODE_ENV !== "production") {
            // eslint-disable-next-line no-console
            console.log("PWA Service Worker registered with scope:", reg.scope);
          }
        })
        .catch(() => {
          // Graceful fallback if service workers are disabled or unsupported
        });
    }
  }, []);

  return null;
}
