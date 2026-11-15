"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Radio,
  Zap,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { sound } from "@/lib/soundFx";
import type { ReviewQueueItem, ReviewSlaStatus } from "@/lib/types";

interface SlaBreachRadarCockpitProps {
  sla: ReviewSlaStatus | null;
  items: ReviewQueueItem[];
  onFilterUrgent: () => void;
  onAutoEscalate?: () => void;
}

export function SlaBreachRadarCockpit({
  sla,
  items,
  onFilterUrgent,
  onAutoEscalate,
}: SlaBreachRadarCockpitProps) {
  const [seconds, setSeconds] = useState(0);

  // Live second ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Compute live age distribution across the 30-minute regulatory ceiling
  const now = Date.now();
  let safeCount = 0;
  let warnCount = 0;
  let criticalCount = 0;
  let oldestWaitMins = sla?.max_wait_minutes ?? 0;

  items.forEach((item) => {
    const created = new Date(item.submitted_at || item.last_saved_at).getTime();
    const waitMins = Math.max(0, Math.floor((now - created) / 60000));
    if (waitMins > oldestWaitMins) oldestWaitMins = waitMins;

    if (waitMins < 15) {
      safeCount++;
    } else if (waitMins <= 25) {
      warnCount++;
    } else {
      criticalCount++;
    }
  });

  const hasCritical = criticalCount > 0 || (sla?.status === "BREACHED");

  return (
    <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-950 p-5 text-slate-100 shadow-xl space-y-4 relative overflow-hidden">
      {/* Background radial accent */}
      <div className={clsx(
        "absolute -right-20 -top-20 w-60 h-60 rounded-full blur-3xl pointer-events-none transition-all duration-700",
        hasCritical ? "bg-rose-500/20" : "bg-emerald-500/10"
      )} />

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3 relative z-10">
        <div className="flex items-center gap-2.5">
          <div className={clsx(
            "h-8 w-8 rounded-lg flex items-center justify-center font-bold text-xs ring-1",
            hasCritical
              ? "bg-rose-500/20 text-rose-400 ring-rose-500/40 animate-pulse"
              : "bg-emerald-500/20 text-emerald-400 ring-emerald-500/40"
          )}>
            <Radio className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-1.5">
                30-Minute Regulatory SLA Radar
              </h2>
              <span className={clsx(
                "rounded-full px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider",
                hasCritical
                  ? "bg-rose-950 text-rose-300 border border-rose-500/40 animate-pulse"
                  : "bg-emerald-950 text-emerald-300 border border-emerald-500/40"
              )}>
                {hasCritical ? "BREACH ALERT ACTIVE" : "SLA OPERATIONAL (< 30 MINS)"}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Real-time monitoring of reviewer micro-desks to eliminate candidate drop-offs.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-slate-400">
            Oldest Wait: <strong className={clsx("font-bold", oldestWaitMins > 25 ? "text-rose-400" : "text-white")}>{oldestWaitMins}m</strong>
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">
            Target: <strong className="text-emerald-400">&lt; 30 mins</strong>
          </span>
        </div>
      </div>

      {/* SLA Tiers Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 relative z-10">
        
        {/* Tier 1: Safe Zone (< 15 mins) */}
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3.5 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Safe Zone (&lt; 15 mins)</span>
            </div>
            <p className="mt-1 text-2xl font-black text-white">{safeCount}</p>
            <p className="text-[10px] text-emerald-400/80 font-mono mt-0.5">&gt; 15 mins remaining to SLA</p>
          </div>
          <span className="text-xs font-bold text-emerald-400 bg-emerald-950/80 px-2 py-1 rounded border border-emerald-800/40 font-mono">
            NORMAL
          </span>
        </div>

        {/* Tier 2: Warning Zone (15 - 25 mins) */}
        <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-3.5 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5 text-amber-400 text-xs font-semibold">
              <Clock className="h-3.5 w-3.5" />
              <span>Warning Zone (15-25m)</span>
            </div>
            <p className="mt-1 text-2xl font-black text-white">{warnCount}</p>
            <p className="text-[10px] text-amber-400/80 font-mono mt-0.5">5-15 mins remaining to SLA</p>
          </div>
          <span className="text-xs font-bold text-amber-400 bg-amber-950/80 px-2 py-1 rounded border border-amber-800/40 font-mono">
            ATTENTION
          </span>
        </div>

        {/* Tier 3: Critical Zone (> 25 mins) */}
        <div className={clsx(
          "rounded-xl border p-3.5 flex items-center justify-between transition-all",
          criticalCount > 0
            ? "border-rose-500/60 bg-rose-950/40 ring-1 ring-rose-500/40 animate-pulse"
            : "border-slate-800 bg-slate-900/60"
        )}>
          <div>
            <div className="flex items-center gap-1.5 text-rose-400 text-xs font-semibold">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Critical Risk (&gt; 25 mins)</span>
            </div>
            <p className="mt-1 text-2xl font-black text-rose-300">{criticalCount}</p>
            <p className="text-[10px] text-rose-400/80 font-mono mt-0.5">Breach imminent or exceeded</p>
          </div>
          {criticalCount > 0 ? (
            <button
              type="button"
              onClick={() => {
                sound.playScan();
                onFilterUrgent();
              }}
              className="text-[11px] font-bold text-white bg-rose-600 hover:bg-rose-500 px-2.5 py-1 rounded transition shadow-md shadow-rose-900/50"
            >
              Filter Now
            </button>
          ) : (
            <span className="text-xs font-bold text-slate-500 bg-slate-800 px-2 py-1 rounded font-mono">
              ZERO RISKS
            </span>
          )}
        </div>

      </div>

      {/* Action Footer */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-1 border-t border-slate-800/80 text-xs relative z-10">
        <div className="flex items-center gap-2 text-slate-400 font-mono text-[11px]">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Live Ticker: {seconds}s active session · 45s backend synchronization</span>
        </div>

        <div className="flex items-center gap-2">
          {onAutoEscalate && (
            <button
              type="button"
              onClick={() => {
                sound.playSuccess();
                onAutoEscalate();
              }}
              className="flex items-center gap-1.5 bg-brand-700 hover:bg-brand-600 text-white font-semibold text-xs px-3 py-1.5 rounded-lg shadow-sm transition"
            >
              <Zap className="h-3.5 w-3.5" />
              <span>Fast-Track Escalation Protocol</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
