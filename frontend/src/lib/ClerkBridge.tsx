"use client";

import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth } from "@clerk/nextjs";
import { useAuth } from "./auth";
import { api } from "./api";

export function ClerkBridge() {
  const { isSignedIn, userId } = useClerkAuth();
  const { me, refresh } = useAuth();
  const syncingRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isSignedIn || !userId || me || syncingRef.current === userId) return;

    syncingRef.current = userId;
    api("/auth/clerk/exchange", {
      method: "POST",
      body: { user_id: userId },
    })
      .then(() => refresh())
      .catch((err) => {
        console.warn("Clerk exchange failed:", err);
        syncingRef.current = null;
      });
  }, [isSignedIn, userId, me, refresh]);

  return null;
}
