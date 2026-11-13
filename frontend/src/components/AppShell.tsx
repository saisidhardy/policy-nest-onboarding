"use client";

import clsx from "clsx";
import {
  BarChart3,
  Bell,
  FileCheck2,
  FolderKanban,
  Gauge,
  GraduationCap,
  KeyRound,
  LogOut,
  Menu,
  Plug,
  ScrollText,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  UserCheck,
  UserCircle,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { NotificationsPage } from "@/lib/types";
import { Logo } from "./Logo";
import { Badge } from "./ui";
import { VerificationBanner } from "./VerificationBanner";
import { LanguageToggle } from "./LanguageToggle";
import { useI18n } from "@/lib/i18n";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  permission?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/app", label: "Overview", icon: Gauge },
  { href: "/app/onboarding", label: "Onboarding", icon: FileCheck2, permission: "application:create" },
  { href: "/app/applications", label: "My applications", icon: FolderKanban, permission: "application:read_own" },
  { href: "/app/review", label: "Document review", icon: ShieldCheck, permission: "application:review" },
  { href: "/app/review/analytics", label: "Ops analytics", icon: BarChart3, permission: "analytics:read" },
  { href: "/app/training", label: "Training & LMS", icon: GraduationCap, permission: "profile:read" },
  { href: "/app/notifications", label: "Notifications", icon: Bell, permission: "profile:read" },
  { href: "/app/account", label: "Account & security", icon: UserCircle, permission: "profile:read" },
  { href: "/app/admin/users", label: "Users", icon: Users, permission: "users:read" },
  { href: "/app/admin/reviewers", label: "Reviewers", icon: UserCheck, permission: "users:manage" },
  { href: "/app/admin/applications", label: "Applications", icon: FolderKanban, permission: "config:manage" },
  { href: "/app/admin/roles", label: "Roles & permissions", icon: KeyRound, permission: "roles:read" },
  { href: "/app/admin/rules", label: "Business rules", icon: SlidersHorizontal, permission: "config:manage" },
  { href: "/app/admin/integrations", label: "Integrations & LMS", icon: Plug, permission: "config:manage" },
  { href: "/app/admin/audit", label: "Audit log", icon: ScrollText, permission: "audit:read" },
  { href: "/app/admin/system", label: "System status", icon: Server, permission: "system:read" },
];

export function visibleNav(permissions: string[]): NavItem[] {
  return NAV_ITEMS.filter((i) => !i.permission || permissions.includes(i.permission));
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, logout } = useAuth();
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const navLabels: Record<string, string> = {
    "/app": t.nav.overview,
    "/app/onboarding": t.nav.onboarding,
    "/app/applications": t.nav.myApplications,
    "/app/review": t.nav.review,
    "/app/review/analytics": t.nav.analytics,
    "/app/training": t.nav.training,
    "/app/notifications": t.nav.notifications,
    "/app/account": t.nav.account,
    "/app/admin/users": t.nav.adminUsers,
    "/app/admin/reviewers": t.nav.adminReviewers,
    "/app/admin/applications": t.nav.adminApplications,
    "/app/admin/roles": t.nav.adminRoles,
    "/app/admin/rules": t.nav.adminRules,
    "/app/admin/integrations": t.nav.adminIntegrations,
    "/app/admin/audit": t.nav.adminAudit,
    "/app/admin/system": t.nav.adminSystem,
  };

  useEffect(() => {
    if (!me) return;
    let active = true;
    api<NotificationsPage>("/notifications", { query: { page_size: 1 } }).then(
      (res) => {
        if (active) setUnreadCount(res.unread_count);
      },
      () => {
        /* ignore transient poll error */
      },
    );
    return () => {
      active = false;
    };
  }, [me, pathname]);

  if (!me) return null;
  const items = visibleNav(me.permissions);

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  const nav = (
    <nav className="flex flex-1 flex-col gap-1 px-3" aria-label="Main">
      {items.map(({ href, label, icon: Icon }) => {
        const active = href === "/app" ? pathname === "/app" : pathname.startsWith(href);
        const showBadge = href === "/app/notifications" && unreadCount > 0;
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setOpen(false)}
            aria-current={active ? "page" : undefined}
            className={clsx(
              "flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm font-medium",
              active ? "bg-brand-50 text-brand-800" : "text-slate-700 hover:bg-slate-100",
            )}
          >
            <span className="flex items-center gap-3">
              <Icon className="h-4 w-4" />
              {navLabels[href] || label}
            </span>
            {showBadge && (
              <span className="rounded-full bg-brand-700 px-2 py-0.5 text-xs font-semibold text-white">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  const userBlock = (
    <div className="border-t border-slate-200 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-800">
          {me.user.full_name
            .split(" ")
            .map((p) => p[0])
            .slice(0, 2)
            .join("")}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900">{me.user.full_name}</p>
          <p className="truncate text-xs text-slate-500">{me.user.email}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Badge tone="brand">
          <ShieldCheck className="mr-1 h-3 w-3" />
          {me.user.role.name}
        </Badge>
        <button
          onClick={signOut}
          className="inline-flex items-center gap-1.5 rounded px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        >
          <LogOut className="h-4 w-4" /> {t.nav.signOut}
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex items-center justify-between px-6 py-4">
          <Link href="/app">
            <Logo />
          </Link>
          <LanguageToggle />
        </div>
        {nav}
        {userBlock}
      </aside>
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <Link href="/app">
          <Logo />
        </Link>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <button onClick={() => setOpen(true)} className="rounded p-2 text-slate-700 hover:bg-slate-100" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </header>
      {open && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-white">
            <div className="flex items-center justify-between px-6 py-5">
              <Logo />
              <button onClick={() => setOpen(false)} className="rounded p-1 text-slate-600 hover:bg-slate-100" aria-label="Close menu">
                <X className="h-5 w-5" />
              </button>
            </div>
            {nav}
            {userBlock}
          </aside>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
        {process.env.NEXT_PUBLIC_APP_ENV === "staging" && (
          <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-xs text-amber-900">
            <strong>Staging · Simulated Sandbox Mode:</strong> External government/vendor APIs (PAN, Penny Drop, DigiLocker, LMS) run simulated responses for QA testing. Use{" "}
            <a href="https://policynest-web.embarko.app" className="underline font-semibold">
              Production
            </a>{" "}
            for live records.
          </div>
        )}
        {!me.user.email_verified && <VerificationBanner />}
        {children}
      </main>
    </div>
  );
}
