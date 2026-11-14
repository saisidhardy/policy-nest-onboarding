"use client";

import clsx from "clsx";
import {
  ArrowRight,
  Bot,
  Command,
  FileCheck2,
  Lock,
  Network,
  QrCode,
  Search,
  Sparkles,
  Timer,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fireConfetti } from "@/lib/confetti";
import { sound } from "@/lib/soundFx";

interface ActionItem {
  id: string;
  category: "Navigation" | "Actions" | "Personas" | "Tools";
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  perform: () => void;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [soundActive, setSoundActive] = useState(sound.enabled);
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
        sound.playClick();
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const actions: ActionItem[] = [
    {
      id: "session-start",
      category: "Actions",
      title: "Start 30-Minute Fast-Track Onboarding",
      subtitle: "Full-screen guided session for 6 mandatory documents",
      icon: Timer,
      badge: "Fast-Track",
      perform: () => {
        sound.playScan();
        router.push("/app/onboarding");
      },
    },
    {
      id: "fraud-graph",
      category: "Navigation",
      title: "Open Fraud Ring Network Studio",
      subtitle: "Visual link analysis for mule banks and SIM stacking",
      icon: Network,
      badge: "AI Defense",
      perform: () => {
        sound.playClick();
        router.push("/app/review/fraud-graph");
      },
    },
    {
      id: "verify-cert",
      category: "Navigation",
      title: "Public POSP Certificate Verifier",
      subtitle: "Zero-auth registry lookup with sample credential",
      icon: QrCode,
      perform: () => {
        sound.playClick();
        router.push("/verify-certificate");
      },
    },
    {
      id: "confetti",
      category: "Tools",
      title: "Trigger Dopamine Celebration",
      subtitle: "Full-screen particle physics confetti burst",
      icon: Sparkles,
      badge: "Dopamine FX",
      perform: () => {
        sound.playTrophy();
        fireConfetti();
      },
    },
    {
      id: "toggle-sound",
      category: "Tools",
      title: soundActive ? "Mute FinTech Sound FX" : "Enable FinTech Sound FX",
      subtitle: soundActive ? "Disable tactile UI clicks and chimes" : "Enable synthesized Web Audio clicks & chimes",
      icon: soundActive ? VolumeX : Volume2,
      badge: soundActive ? "ON" : "OFF",
      perform: () => {
        const newState = sound.toggleSound();
        setSoundActive(newState);
      },
    },
    {
      id: "persona-applicant",
      category: "Personas",
      title: "Switch to Applicant Persona",
      subtitle: "Sign in as Rajiv Sharma (Fresh Candidate)",
      icon: Bot,
      perform: () => {
        sound.playSuccess();
        router.push("/login?persona=applicant");
      },
    },
    {
      id: "persona-reviewer",
      category: "Personas",
      title: "Switch to Reviewer Ops Persona",
      subtitle: "Sign in as Priya Nair (Operations Desk)",
      icon: FileCheck2,
      perform: () => {
        sound.playSuccess();
        router.push("/login?persona=reviewer");
      },
    },
    {
      id: "persona-admin",
      category: "Personas",
      title: "Switch to System Administrator",
      subtitle: "Sign in as Vikram Malhotra (Full Clearance)",
      icon: Lock,
      perform: () => {
        sound.playSuccess();
        router.push("/login?persona=admin");
      },
    },
  ];

  const filtered = actions.filter(
    (a) =>
      a.title.toLowerCase().includes(query.toLowerCase()) ||
      a.subtitle.toLowerCase().includes(query.toLowerCase()) ||
      a.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (action: ActionItem) => {
    action.perform();
    setOpen(false);
  };

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const handleNav = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length));
        sound.playClick();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length));
        sound.playClick();
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        handleSelect(filtered[selectedIndex]);
      }
    };
    window.addEventListener("keydown", handleNav);
    return () => window.removeEventListener("keydown", handleNav);
  }, [open, filtered, selectedIndex]);

  return (
    <>
      {/* Floating Pill / Trigger button in the bottom left */}
      <button
        type="button"
        onClick={() => {
          setOpen(true);
          sound.playClick();
        }}
        className="fixed bottom-6 left-6 z-40 hidden sm:flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-900/90 px-3.5 py-2 text-xs font-medium text-slate-300 shadow-xl backdrop-blur-md hover:border-slate-500 hover:text-white transition"
        title="Open Command Menu (⌘K or Ctrl+K)"
      >
        <Command className="h-3.5 w-3.5 text-cyan-400" />
        <span>Command Menu</span>
        <kbd className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-400 border border-slate-700">
          ⌘K
        </kbd>
      </button>

      {/* Raycast-style Palette Modal */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-slate-950/70 backdrop-blur-md animate-in fade-in duration-150">
          <div
            className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900/95 shadow-2xl overflow-hidden text-slate-100 flex flex-col ring-1 ring-cyan-500/20"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search Input Bar */}
            <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-3.5">
              <Search className="h-4 w-4 text-cyan-400 shrink-0" />
              <input
                autoFocus
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type a command, search routes, or switch personas..."
                className="w-full bg-transparent text-sm font-medium text-white placeholder-slate-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded p-1 text-slate-500 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Actions List */}
            <div className="max-h-96 overflow-y-auto p-2 divide-y divide-slate-800/40">
              {filtered.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500">
                  No matching commands found.
                </div>
              ) : (
                filtered.map((action, idx) => {
                  const Icon = action.icon;
                  const isSelected = idx === selectedIndex;
                  return (
                    <div
                      key={action.id}
                      onClick={() => handleSelect(action)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={clsx(
                        "flex items-center justify-between rounded-xl px-3 py-2.5 cursor-pointer transition select-none",
                        isSelected
                          ? "bg-slate-800 text-white shadow-sm ring-1 ring-cyan-500/30"
                          : "text-slate-300 hover:bg-slate-800/50"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={clsx(
                            "flex h-8 w-8 items-center justify-center rounded-lg",
                            isSelected
                              ? "bg-cyan-500/20 text-cyan-300"
                              : "bg-slate-800 text-slate-400"
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold">{action.title}</span>
                            {action.badge && (
                              <span className="rounded bg-slate-800/80 px-1.5 py-0.2 text-[9px] font-mono text-cyan-300 ring-1 ring-cyan-500/30">
                                {action.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">{action.subtitle}</p>
                        </div>
                      </div>

                      <ArrowRight
                        className={clsx(
                          "h-3.5 w-3.5 transition",
                          isSelected ? "text-cyan-400 translate-x-0.5" : "text-transparent"
                        )}
                      />
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer hints */}
            <div className="flex items-center justify-between border-t border-slate-800 bg-slate-950/60 px-4 py-2 text-[10px] font-mono text-slate-500">
              <div className="flex items-center gap-3">
                <span>↑↓ Navigate</span>
                <span>↵ Execute</span>
                <span>ESC Close</span>
              </div>
              <span className="text-cyan-400/80">PolicyNest Command Rail</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
