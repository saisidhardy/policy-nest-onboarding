"use client";

import clsx from "clsx";
import { BarChart3, ClipboardList, History, Network } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function ReviewPortalTabs() {
  const pathname = usePathname();
  const { can } = useAuth();

  const tabs = [
    { href: "/app/review", label: "Application Queue", icon: ClipboardList, show: can("application:review") },
    { href: "/app/review/history", label: "Review History", icon: History, show: can("application:review") },
    { href: "/app/review/analytics", label: "Operational Analytics", icon: BarChart3, show: can("analytics:read") },
    { href: "/app/review/fraud-graph", label: "Fraud Ring Network", icon: Network, show: can("application:review") },
  ].filter((t) => t.show);

  return (
    <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
      {tabs.map((tab) => {
        const active =
          tab.href === "/app/review"
            ? pathname === "/app/review"
            : pathname.startsWith(tab.href);
        const Icon = tab.icon;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition",
              active
                ? "bg-brand-700 text-white shadow-sm"
                : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
