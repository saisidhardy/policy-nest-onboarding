"use client";

import { Check, CheckCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Pagination, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { NotificationsPage } from "@/lib/types";

export default function NotificationsPageView() {
  const [data, setData] = useState<NotificationsPage | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    api<NotificationsPage>("/notifications", { query: { unread_only: unreadOnly, page, page_size: 15 } }).then(
      (d) => {
        setData(d);
        setError(null);
      },
      (e) => setError(e instanceof ApiError ? e.message : "Failed to load notifications."),
    );
  }, [unreadOnly, page]);

  useEffect(() => {
    load();
  }, [load]);

  async function markOne(id: string) {
    setBusyId(id);
    try {
      await api(`/notifications/${id}/read`, { method: "POST" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to mark notification read.");
    } finally {
      setBusyId(null);
    }
  }

  async function markAll() {
    setBusyId("all");
    try {
      await api("/notifications/read-all", { method: "POST" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to mark notifications read.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Notifications"
        description="Updates on your onboarding application, uploaded documents, and account."
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              variant={unreadOnly ? "primary" : "secondary"}
              size="sm"
              onClick={() => {
                setUnreadOnly((v) => !v);
                setPage(1);
              }}
            >
              {unreadOnly ? "Showing unread" : "Unread only"}
            </Button>
            {data && data.unread_count > 0 && (
              <Button variant="secondary" size="sm" loading={busyId === "all"} onClick={markAll}>
                <CheckCheck className="h-4 w-4" /> Mark all read
              </Button>
            )}
          </div>
        }
      />

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <Card>
        {!data ? (
          <Spinner label="Loading notifications" />
        ) : data.items.length === 0 ? (
          <EmptyState title={unreadOnly ? "No unread notifications" : "No notifications yet"} />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {data.items.map((n) => (
                <li key={n.id} className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
                  <div className="max-w-2xl space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900">{n.title}</p>
                      <Badge tone={n.is_read ? "neutral" : "brand"}>{n.is_read ? "Read" : "Unread"}</Badge>
                    </div>
                    <p className="text-sm text-slate-600">{n.body}</p>
                    <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-slate-500">
                      <span>{formatDateTime(n.created_at)}</span>
                      {n.action_url && (
                        <Link href={n.action_url} className="font-medium text-brand-700 hover:underline">
                          Open
                        </Link>
                      )}
                    </div>
                  </div>
                  {!n.is_read && (
                    <Button variant="secondary" size="sm" loading={busyId === n.id} onClick={() => void markOne(n.id)}>
                      <Check className="h-3.5 w-3.5" /> Mark read
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
