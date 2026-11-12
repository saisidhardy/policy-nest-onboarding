"use client";

import { CheckCircle2, Lock, Plus, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { RuleSet } from "@/lib/types";

export default function BusinessRulesPage() {
  return (
    <RequirePermission permission="config:manage">
      <BusinessRulesInner />
    </RequirePermission>
  );
}

function BusinessRulesInner() {
  const [rulesets, setRulesets] = useState<RuleSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [version, setVersion] = useState("3.3.0");
  const [name, setName] = useState("PS-01 Strict Operations Thresholds");
  const [description, setDescription] = useState("");
  const [minOcrConfidence, setMinOcrConfidence] = useState("0.75");
  const [facePassThreshold, setFacePassThreshold] = useState("0.75");
  const [faceReworkThreshold, setFaceReworkThreshold] = useState("0.60");
  const [maxReworkCycles, setMaxReworkCycles] = useState("2");
  const [autoApproveEnabled, setAutoApproveEnabled] = useState(true);
  const [autoRejectStatutory, setAutoRejectStatutory] = useState(true);
  const [activateImmediately, setActivateImmediately] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await api<RuleSet[]>("/rulesets");
      setRulesets(list);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load rule versions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createVersion(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const activeCfg = rulesets.find((r) => r.is_active)?.rules_config;
      const created = await api<RuleSet>("/rulesets", {
        method: "POST",
        body: {
          version: version.trim(),
          name: name.trim(),
          description: description.trim() || null,
          activate_immediately: activateImmediately,
          rules_config: {
            ...(activeCfg ?? {}),
            min_age_years: 18,
            min_ocr_confidence: Number(minOcrConfidence),
            face_match_auto_pass_threshold: Number(facePassThreshold),
            face_match_rework_threshold: Number(faceReworkThreshold),
            max_rework_cycles_before_human: Number(maxReworkCycles),
            auto_approve_enabled: autoApproveEnabled,
            auto_reject_statutory: autoRejectStatutory,
            never_auto_reject_name_mismatch: true,
          },
        },
      });
      setNotice(`Created RuleSet v${created.version}${created.is_active ? " and activated it" : " (draft)"}.`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create rule version.");
    } finally {
      setSaving(false);
    }
  }

  async function activate(id: string, ver: string) {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api<RuleSet>(`/rulesets/${id}/activate`, { method: "POST" });
      setNotice(`Activated RuleSet v${ver}.`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to activate rule version.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Spinner label="Loading PolicyNest business rules" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Business Rules & Policy Versioning"
        description="Configure deterministic PS-01 onboarding thresholds. Safety invariant: Tier 7 NAME_MISMATCH never auto-rejects."
      />

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title="RuleSet Versions"
            description="Only one version is active at any time. Every RuleExecution records the exact ruleset version used."
          />
          <div className="divide-y divide-slate-100">
            {rulesets.map((rs) => (
              <div key={rs.id} className="space-y-2 p-5 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <SlidersHorizontal className="h-4 w-4 text-brand-700" />
                    <span className="font-semibold text-slate-900">
                      v{rs.version} · {rs.name}
                    </span>
                    {rs.is_active ? <Badge tone="success">ACTIVE</Badge> : <Badge tone="neutral">{rs.status}</Badge>}
                  </div>
                  {!rs.is_active && (
                    <Button size="sm" variant="secondary" loading={saving} onClick={() => activate(rs.id, rs.version)}>
                      <CheckCircle2 className="h-3.5 w-3.5" /> Activate
                    </Button>
                  )}
                </div>
                {rs.description && <p className="text-xs text-slate-600">{rs.description}</p>}
                <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                  <span className="rounded bg-slate-100 px-2 py-0.5">
                    OCR floor: {rs.rules_config.min_ocr_confidence}
                  </span>
                  <span className="rounded bg-slate-100 px-2 py-0.5">
                    Face pass: {rs.rules_config.face_match_auto_pass_threshold}
                  </span>
                  <span className="rounded bg-slate-100 px-2 py-0.5">
                    Max reworks: {rs.rules_config.max_rework_cycles_before_human}
                  </span>
                  <span className="rounded bg-slate-100 px-2 py-0.5">
                    Auto-approve: {rs.rules_config.auto_approve_enabled ? "ON" : "HUMAN ONLY"}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-amber-900">
                    <Lock className="h-3 w-3" /> NAME_MISMATCH auto-reject: LOCKED OFF
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Created {formatDateTime(rs.created_at)}
                  {rs.activated_at ? ` · Activated ${formatDateTime(rs.activated_at)}` : ""}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Create New Version" description="Publish a draft or activate immediately." />
          <form onSubmit={createVersion} className="space-y-4 p-5">
            <Field label="Version tag" htmlFor="rs-ver">
              <Input id="rs-ver" value={version} onChange={(e) => setVersion(e.target.value)} required />
            </Field>
            <Field label="Version name" htmlFor="rs-name">
              <Input id="rs-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Field label="Change notes" htmlFor="rs-desc">
              <Input
                id="rs-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Reason for threshold update…"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Min OCR confidence" htmlFor="rs-ocr">
                <Input
                  id="rs-ocr"
                  type="number"
                  step="0.05"
                  min="0.4"
                  max="0.99"
                  value={minOcrConfidence}
                  onChange={(e) => setMinOcrConfidence(e.target.value)}
                />
              </Field>
              <Field label="Max rework loops" htmlFor="rs-rework">
                <Input
                  id="rs-rework"
                  type="number"
                  min="1"
                  max="5"
                  value={maxReworkCycles}
                  onChange={(e) => setMaxReworkCycles(e.target.value)}
                />
              </Field>
              <Field label="Face auto-pass" htmlFor="rs-fpass">
                <Input
                  id="rs-fpass"
                  type="number"
                  step="0.05"
                  min="0.5"
                  max="0.99"
                  value={facePassThreshold}
                  onChange={(e) => setFacePassThreshold(e.target.value)}
                />
              </Field>
              <Field label="Face rework floor" htmlFor="rs-frew">
                <Input
                  id="rs-frew"
                  type="number"
                  step="0.05"
                  min="0.3"
                  max="0.85"
                  value={faceReworkThreshold}
                  onChange={(e) => setFaceReworkThreshold(e.target.value)}
                />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={autoApproveEnabled}
                onChange={(e) => setAutoApproveEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-700"
              />
              Enable auto-pass STP to KYC_APPROVED
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={autoRejectStatutory}
                onChange={(e) => setAutoRejectStatutory(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-700"
              />
              Auto-reject statutory failures (Underage / Invalid PAN)
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={activateImmediately}
                onChange={(e) => setActivateImmediately(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-700"
              />
              Activate immediately on save
            </label>
            <Button type="submit" loading={saving} className="w-full">
              <Plus className="h-4 w-4" /> Save rulebook version
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
