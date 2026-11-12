"use client";

import { Activity, KeyRound, RefreshCw, RotateCcw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  AdminConfigBundle,
  IntegrationProbe,
  IntegrationsConfig,
  IntegrationsMonitor,
  LmsConfig,
  PlatformConfig,
  SmsRetryOut,
} from "@/lib/types";

export default function AdminIntegrationsPage() {
  return (
    <RequirePermission permission="config:manage">
      <ConfigCenterView />
    </RequirePermission>
  );
}

type SectionTab = "lms" | "integrations" | "platform" | "monitor";

function SecretField({
  id,
  label,
  hasValue,
  hint,
  value,
  onChange,
  clearChecked,
  onClearChange,
  placeholder,
}: {
  id: string;
  label: string;
  hasValue: boolean;
  hint: string | null;
  value: string;
  onChange: (val: string) => void;
  clearChecked: boolean;
  onClearChange: (checked: boolean) => void;
  placeholder: string;
}) {
  return (
    <div className="space-y-2">
      <Field
        label={label}
        htmlFor={id}
        hint={
          hasValue ? (
            <span className="inline-flex items-center gap-1 text-emerald-700">
              <KeyRound className="h-3 w-3" /> Stored: {hint ?? "set"}
            </span>
          ) : (
            "Not set"
          )
        }
      >
        <Input
          id={id}
          type="password"
          autoComplete="new-password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      </Field>
      {hasValue && (
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input type="checkbox" checked={clearChecked} onChange={(e) => onClearChange(e.target.checked)} />
          Clear stored secret
        </label>
      )}
    </div>
  );
}

function ConfigCenterView() {
  const [bundle, setBundle] = useState<AdminConfigBundle | null>(null);
  const [monitor, setMonitor] = useState<IntegrationsMonitor | null>(null);
  const [tab, setTab] = useState<SectionTab>("lms");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [probing, setProbing] = useState(false);
  const [retryingSms, setRetryingSms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // LMS form state
  const [lmsProvider, setLmsProvider] = useState("not_configured");
  const [lmsBaseUrl, setLmsBaseUrl] = useState("");
  const [lmsCourseCode, setLmsCourseCode] = useState("IRDAI-POSP-15H");
  const [lmsRequiredHours, setLmsRequiredHours] = useState("15");
  const [lmsPassingPct, setLmsPassingPct] = useState("50");
  const [lmsTimeout, setLmsTimeout] = useState("8");
  const [lmsCooldown, setLmsCooldown] = useState("24");
  const [lmsValidityYears, setLmsValidityYears] = useState("3");
  const [lmsRetryBase, setLmsRetryBase] = useState("300");
  const [lmsMaxAttempts, setLmsMaxAttempts] = useState("5");
  const [lmsApiKeyInput, setLmsApiKeyInput] = useState("");
  const [clearLmsApiKey, setClearLmsApiKey] = useState(false);
  const [lmsWebhookSecretInput, setLmsWebhookSecretInput] = useState("");
  const [clearLmsWebhookSecret, setClearLmsWebhookSecret] = useState(false);

  // Integrations form state
  const [ocrProvider, setOcrProvider] = useState("local_tesseract");
  const [ocrBaseUrl, setOcrBaseUrl] = useState("");
  const [ocrKeyInput, setOcrKeyInput] = useState("");
  const [clearOcrKey, setClearOcrKey] = useState(false);

  const [aiProvider, setAiProvider] = useState("local_heuristic");
  const [geminiModel, setGeminiModel] = useState("gemini-3.8-flash");
  const [geminiKeyInput, setGeminiKeyInput] = useState("");
  const [clearGeminiKey, setClearGeminiKey] = useState(false);
  const [ifscEnabled, setIfscEnabled] = useState(true);

  const [panProvider, setPanProvider] = useState("not_configured");
  const [panBaseUrl, setPanBaseUrl] = useState("");
  const [panKeyInput, setPanKeyInput] = useState("");
  const [clearPanKey, setClearPanKey] = useState(false);

  const [bankProvider, setBankProvider] = useState("not_configured");
  const [bankBaseUrl, setBankBaseUrl] = useState("");
  const [bankKeyInput, setBankKeyInput] = useState("");
  const [clearBankKey, setClearBankKey] = useState(false);

  const [digilockerProvider, setDigilockerProvider] = useState("not_configured");
  const [digilockerBaseUrl, setDigilockerBaseUrl] = useState("");
  const [digilockerClientId, setDigilockerClientId] = useState("");
  const [digilockerSecretInput, setDigilockerSecretInput] = useState("");
  const [clearDigilockerSecret, setClearDigilockerSecret] = useState(false);

  const [faceProvider, setFaceProvider] = useState("not_configured");
  const [faceBaseUrl, setFaceBaseUrl] = useState("");
  const [faceKeyInput, setFaceKeyInput] = useState("");
  const [clearFaceKey, setClearFaceKey] = useState(false);

  const [smsProvider, setSmsProvider] = useState("not_configured");
  const [smsBaseUrl, setSmsBaseUrl] = useState("");
  const [smsSenderId, setSmsSenderId] = useState("");
  const [smsTimeout, setSmsTimeout] = useState("8");
  const [smsMaxAttempts, setSmsMaxAttempts] = useState("3");
  const [smsKeyInput, setSmsKeyInput] = useState("");
  const [clearSmsKey, setClearSmsKey] = useState(false);

  const [webhookSecretInput, setWebhookSecretInput] = useState("");
  const [clearWebhookSecret, setClearWebhookSecret] = useState(false);
  const [httpTimeout, setHttpTimeout] = useState("8");
  const [httpMaxRetries, setHttpMaxRetries] = useState("2");

  // Platform form state
  const [publicUrl, setPublicUrl] = useState("http://localhost:3000");
  const [requireVerify, setRequireVerify] = useState(true);
  const [idleMinutes, setIdleMinutes] = useState("30");
  const [maxFailures, setMaxFailures] = useState("5");
  const [lockoutMinutes, setLockoutMinutes] = useState("15");
  const [maxUploadMb, setMaxUploadMb] = useState("10");

  const hydrateForms = useCallback((b: AdminConfigBundle) => {
    setBundle(b);
    setLmsProvider(b.lms.lms_provider);
    setLmsBaseUrl(b.lms.lms_api_base_url ?? "");
    setLmsCourseCode(b.lms.lms_course_code);
    setLmsRequiredHours(String(b.lms.lms_required_hours));
    setLmsPassingPct(String(b.lms.lms_passing_score_pct));
    setLmsTimeout(String(b.lms.lms_timeout_seconds));
    setLmsCooldown(String(b.lms.lms_exam_cooldown_hours));
    setLmsValidityYears(String(b.lms.lms_certificate_validity_years));
    setLmsRetryBase(String(b.lms.lms_sync_retry_base_seconds));
    setLmsMaxAttempts(String(b.lms.lms_sync_max_attempts));
    setLmsApiKeyInput("");
    setClearLmsApiKey(false);
    setLmsWebhookSecretInput("");
    setClearLmsWebhookSecret(false);

    const ic = b.integrations;
    setOcrProvider(ic.ocr_provider);
    setOcrBaseUrl(ic.ocr_api_base_url ?? "");
    setOcrKeyInput("");
    setClearOcrKey(false);

    setAiProvider(ic.ai_provider);
    setGeminiModel(ic.gemini_model);
    setGeminiKeyInput("");
    setClearGeminiKey(false);
    setIfscEnabled(ic.ifsc_lookup_enabled);

    setPanProvider(ic.pan_verification_provider);
    setPanBaseUrl(ic.pan_api_base_url ?? "");
    setPanKeyInput("");
    setClearPanKey(false);

    setBankProvider(ic.bank_verification_provider);
    setBankBaseUrl(ic.bank_api_base_url ?? "");
    setBankKeyInput("");
    setClearBankKey(false);

    setDigilockerProvider(ic.digilocker_provider);
    setDigilockerBaseUrl(ic.digilocker_base_url ?? "");
    setDigilockerClientId(ic.digilocker_client_id ?? "");
    setDigilockerSecretInput("");
    setClearDigilockerSecret(false);

    setFaceProvider(ic.face_match_provider);
    setFaceBaseUrl(ic.face_api_base_url ?? "");
    setFaceKeyInput("");
    setClearFaceKey(false);

    setSmsProvider(ic.sms_provider);
    setSmsBaseUrl(ic.sms_api_base_url ?? "");
    setSmsSenderId(ic.sms_sender_id ?? "");
    setSmsTimeout(String(ic.sms_timeout_seconds));
    setSmsMaxAttempts(String(ic.sms_max_attempts));
    setSmsKeyInput("");
    setClearSmsKey(false);

    setWebhookSecretInput("");
    setClearWebhookSecret(false);
    setHttpTimeout(String(ic.integration_http_timeout_seconds));
    setHttpMaxRetries(String(ic.integration_http_max_retries));

    setPublicUrl(b.platform.public_app_url);
    setRequireVerify(b.platform.require_email_verification);
    setIdleMinutes(String(b.platform.session_idle_minutes));
    setMaxFailures(String(b.platform.login_max_failures));
    setLockoutMinutes(String(b.platform.login_lockout_minutes));
    setMaxUploadMb(String(b.platform.max_upload_size_mb));
  }, []);

  const loadMonitor = useCallback(async () => {
    try {
      const m = await api<IntegrationsMonitor>("/admin/integrations/monitor");
      setMonitor(m);
    } catch {
      // Non-fatal if monitor endpoint isn't needed on initial load
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, mon] = await Promise.all([
        api<AdminConfigBundle>("/admin/config"),
        api<IntegrationsMonitor>("/admin/integrations/monitor").catch(() => null),
      ]);
      hydrateForms(res);
      if (mon) setMonitor(mon);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load configuration.");
    } finally {
      setLoading(false);
    }
  }, [hydrateForms]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runProbes() {
    setProbing(true);
    setError(null);
    setNotice(null);
    try {
      const probes = await api<IntegrationProbe[]>("/admin/integrations/probe", { method: "POST" });
      await loadMonitor();
      setNotice(`Completed active health probes across ${probes.length} adapters.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to execute health probes.");
    } finally {
      setProbing(false);
    }
  }

  async function retryFailedSms() {
    setRetryingSms(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api<SmsRetryOut>("/admin/integrations/sms/retry-failed", { method: "POST" });
      await loadMonitor();
      setNotice(`SMS retry finished: ${res.succeeded} succeeded, ${res.failed} failed (${res.attempted} attempted).`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to retry SMS deliveries.");
    } finally {
      setRetryingSms(false);
    }
  }

  async function saveLms(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api<LmsConfig>("/admin/config/lms", {
        method: "PUT",
        body: JSON.stringify({
          lms_provider: lmsProvider,
          lms_api_base_url: lmsBaseUrl.trim() || null,
          lms_course_code: lmsCourseCode,
          lms_required_hours: Number(lmsRequiredHours),
          lms_passing_score_pct: Number(lmsPassingPct),
          lms_timeout_seconds: Number(lmsTimeout),
          lms_exam_cooldown_hours: Number(lmsCooldown),
          lms_certificate_validity_years: Number(lmsValidityYears),
          lms_sync_retry_base_seconds: Number(lmsRetryBase),
          lms_sync_max_attempts: Number(lmsMaxAttempts),
          lms_api_key: lmsApiKeyInput.trim() || null,
          clear_api_key: clearLmsApiKey,
          lms_webhook_secret: lmsWebhookSecretInput.trim() || null,
          clear_webhook_secret: clearLmsWebhookSecret,
        }),
      });
      await load();
      setNotice("Saved LMS configuration to PostgreSQL (secrets encrypted at rest).");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save LMS configuration.");
    } finally {
      setSaving(false);
    }
  }

  async function saveIntegrations(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api<IntegrationsConfig>("/admin/config/integrations", {
        method: "PUT",
        body: JSON.stringify({
          ocr_provider: ocrProvider,
          ocr_api_base_url: ocrBaseUrl.trim() || null,
          ocr_api_key: ocrKeyInput.trim() || null,
          clear_ocr_api_key: clearOcrKey,
          ai_provider: aiProvider,
          gemini_model: geminiModel,
          gemini_api_key: geminiKeyInput.trim() || null,
          clear_gemini_api_key: clearGeminiKey,
          ifsc_lookup_enabled: ifscEnabled,
          pan_verification_provider: panProvider,
          pan_api_base_url: panBaseUrl.trim() || null,
          pan_api_key: panKeyInput.trim() || null,
          clear_pan_api_key: clearPanKey,
          bank_verification_provider: bankProvider,
          bank_api_base_url: bankBaseUrl.trim() || null,
          bank_api_key: bankKeyInput.trim() || null,
          clear_bank_api_key: clearBankKey,
          digilocker_provider: digilockerProvider,
          digilocker_base_url: digilockerBaseUrl.trim() || null,
          digilocker_client_id: digilockerClientId.trim() || null,
          digilocker_client_secret: digilockerSecretInput.trim() || null,
          clear_digilocker_client_secret: clearDigilockerSecret,
          face_match_provider: faceProvider,
          face_api_base_url: faceBaseUrl.trim() || null,
          face_api_key: faceKeyInput.trim() || null,
          clear_face_api_key: clearFaceKey,
          sms_provider: smsProvider,
          sms_api_base_url: smsBaseUrl.trim() || null,
          sms_sender_id: smsSenderId.trim() || null,
          sms_timeout_seconds: Number(smsTimeout),
          sms_max_attempts: Number(smsMaxAttempts),
          sms_api_key: smsKeyInput.trim() || null,
          clear_sms_api_key: clearSmsKey,
          webhook_shared_secret: webhookSecretInput.trim() || null,
          clear_webhook_shared_secret: clearWebhookSecret,
          integration_http_timeout_seconds: Number(httpTimeout),
          integration_http_max_retries: Number(httpMaxRetries),
        }),
      });
      await load();
      setNotice("Saved verification, SMS, webhook & AI adapter configuration to PostgreSQL.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save integration configuration.");
    } finally {
      setSaving(false);
    }
  }

  async function savePlatform(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api<PlatformConfig>("/admin/config/platform", {
        method: "PUT",
        body: JSON.stringify({
          public_app_url: publicUrl,
          require_email_verification: requireVerify,
          session_idle_minutes: Number(idleMinutes),
          login_max_failures: Number(maxFailures),
          login_lockout_minutes: Number(lockoutMinutes),
          max_upload_size_mb: Number(maxUploadMb),
        }),
      });
      await load();
      setNotice("Saved platform security & upload configuration.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save platform configuration.");
    } finally {
      setSaving(false);
    }
  }

  async function resetSection(section: "lms" | "integrations" | "platform") {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await api<AdminConfigBundle>(`/admin/config/reset/${section}`, { method: "POST" });
      hydrateForms(updated);
      setNotice(`Cleared database overrides for "${section}" and reverted to environment defaults.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to reset configuration section.");
    } finally {
      setSaving(false);
    }
  }

  if (loading || !bundle) return <Spinner label="Loading configuration" />;

  const latestProbeByKey: Record<string, IntegrationProbe> = {};
  for (const p of monitor?.probes ?? []) {
    if (!latestProbeByKey[p.adapter_key]) latestProbeByKey[p.adapter_key] = p;
  }

  const activeSource =
    tab === "lms" ? bundle.lms : tab === "integrations" ? bundle.integrations : tab === "platform" ? bundle.platform : null;

  return (
    <>
      <PageHeader
        title="Integrations & platform configuration"
        description="Configure external verification adapters, SMS gateway, signed webhooks, LMS training thresholds, and platform security parameters. Secrets are encrypted with Fernet at rest and never exposed in plain text."
      />

      {notice && (
        <Alert tone="success" className="mb-4">
          {notice}
        </Alert>
      )}
      {error && (
        <Alert tone="error" className="mb-4">
          {error}
        </Alert>
      )}

      <Card className="mb-6">
        <CardHeader
          title="Live adapter health snapshot"
          action={
            <Button variant="secondary" size="sm" onClick={() => void runProbes()} loading={probing}>
              <Activity className="h-3.5 w-3.5" /> Run health probes
            </Button>
          }
        />
        <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
          {bundle.integrations_health.map((item) => {
            const probe = latestProbeByKey[item.key];
            return (
              <div key={item.key} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold text-slate-800">{item.name}</p>
                  <Badge
                    tone={
                      probe?.status === "DEGRADED"
                        ? "danger"
                        : item.mode === "LIVE"
                          ? "success"
                          : item.mode === "SANDBOX" || item.mode === "LOCAL_DEVELOPMENT"
                            ? "warning"
                            : "neutral"
                    }
                  >
                    {item.mode === "NONE" ? "UNCONFIGURED" : item.mode}
                  </Badge>
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] text-slate-500">{item.detail}</p>
                {probe && (
                  <p className="mt-1.5 text-[10px] text-slate-400">
                    Probe: {probe.status}
                    {probe.latency_ms !== null ? ` · ${probe.latency_ms} ms` : ""}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["lms", "LMS configuration"],
              ["integrations", "Verification, SMS & AI"],
              ["platform", "Platform & security"],
              ["monitor", "Deliveries & Webhooks"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                tab === key
                  ? "bg-brand-700 text-white"
                  : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {activeSource && (
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <Badge tone={activeSource.source === "database" ? "brand" : "neutral"}>
              Source: {activeSource.source === "database" ? "PostgreSQL override" : ".env default"}
            </Badge>
            {activeSource.updated_at && <span>Updated {formatDateTime(activeSource.updated_at)}</span>}
          </div>
        )}
      </div>

      {tab === "lms" && (
        <Card>
          <CardHeader
            title="LMS adapter & certification thresholds"
            action={
              <Button variant="secondary" size="sm" onClick={() => resetSection("lms")} disabled={saving}>
                <RotateCcw className="h-3.5 w-3.5" /> Reset to defaults
              </Button>
            }
          />
          <form className="space-y-5 p-5" onSubmit={saveLms}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="LMS provider mode" htmlFor="cfg-lms-provider">
                <Select id="cfg-lms-provider" value={lmsProvider} onChange={(e) => setLmsProvider(e.target.value)}>
                  <option value="not_configured">Not configured</option>
                  <option value="sandbox">Sandbox (non-production only)</option>
                  <option value="http_api">External HTTP LMS API</option>
                </Select>
              </Field>
              <Field label="LMS API base URL" htmlFor="cfg-lms-url">
                <Input
                  id="cfg-lms-url"
                  value={lmsBaseUrl}
                  onChange={(e) => setLmsBaseUrl(e.target.value)}
                  placeholder="https://lms.partner.example/api"
                />
              </Field>
              <Field label="Course code" htmlFor="cfg-lms-course">
                <Input
                  id="cfg-lms-course"
                  required
                  value={lmsCourseCode}
                  onChange={(e) => setLmsCourseCode(e.target.value)}
                />
              </Field>
              <Field label="Required training hours" htmlFor="cfg-lms-hours">
                <Input
                  id="cfg-lms-hours"
                  type="number"
                  step="0.5"
                  min={1}
                  max={100}
                  required
                  value={lmsRequiredHours}
                  onChange={(e) => setLmsRequiredHours(e.target.value)}
                />
              </Field>
              <Field label="Passing exam score (%)" htmlFor="cfg-lms-pass">
                <Input
                  id="cfg-lms-pass"
                  type="number"
                  step="1"
                  min={1}
                  max={100}
                  required
                  value={lmsPassingPct}
                  onChange={(e) => setLmsPassingPct(e.target.value)}
                />
              </Field>
              <Field label="HTTP timeout (seconds)" htmlFor="cfg-lms-timeout">
                <Input
                  id="cfg-lms-timeout"
                  type="number"
                  min={2}
                  max={120}
                  required
                  value={lmsTimeout}
                  onChange={(e) => setLmsTimeout(e.target.value)}
                />
              </Field>
              <Field label="Exam retake cooldown (hours)" htmlFor="cfg-lms-cooldown">
                <Input
                  id="cfg-lms-cooldown"
                  type="number"
                  min={0}
                  max={168}
                  required
                  value={lmsCooldown}
                  onChange={(e) => setLmsCooldown(e.target.value)}
                />
              </Field>
              <Field label="Certificate validity (years)" htmlFor="cfg-lms-validity">
                <Input
                  id="cfg-lms-validity"
                  type="number"
                  min={1}
                  max={20}
                  required
                  value={lmsValidityYears}
                  onChange={(e) => setLmsValidityYears(e.target.value)}
                />
              </Field>
              <Field label="Sync retry base delay (seconds)" htmlFor="cfg-lms-retry-base">
                <Input
                  id="cfg-lms-retry-base"
                  type="number"
                  min={10}
                  max={3600}
                  required
                  value={lmsRetryBase}
                  onChange={(e) => setLmsRetryBase(e.target.value)}
                />
              </Field>
              <Field label="Sync max attempts" htmlFor="cfg-lms-retry-max">
                <Input
                  id="cfg-lms-retry-max"
                  type="number"
                  min={1}
                  max={10}
                  required
                  value={lmsMaxAttempts}
                  onChange={(e) => setLmsMaxAttempts(e.target.value)}
                />
              </Field>

              <SecretField
                id="cfg-lms-key"
                label="LMS API bearer key"
                hasValue={bundle.lms.has_api_key}
                hint={bundle.lms.api_key_hint}
                value={lmsApiKeyInput}
                onChange={setLmsApiKeyInput}
                clearChecked={clearLmsApiKey}
                onClearChange={setClearLmsApiKey}
                placeholder="Enter new API key to replace"
              />
              <SecretField
                id="cfg-lms-wh"
                label="LMS webhook HMAC secret"
                hasValue={bundle.lms.has_webhook_secret}
                hint={bundle.lms.webhook_secret_hint}
                value={lmsWebhookSecretInput}
                onChange={setLmsWebhookSecretInput}
                clearChecked={clearLmsWebhookSecret}
                onClearChange={setClearLmsWebhookSecret}
                placeholder="Enter new webhook secret to replace"
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" loading={saving}>
                <Save className="h-4 w-4" /> Save LMS configuration
              </Button>
            </div>
          </form>
        </Card>
      )}

      {tab === "integrations" && (
        <Card>
          <CardHeader
            title="Verification, OCR, SMS gateway, webhooks & advisory AI adapters"
            action={
              <Button variant="secondary" size="sm" onClick={() => resetSection("integrations")} disabled={saving}>
                <RotateCcw className="h-3.5 w-3.5" /> Reset to defaults
              </Button>
            }
          />
          <form className="space-y-6 p-5" onSubmit={saveIntegrations}>
            <div>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">OCR & Advisory AI</h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="OCR engine" htmlFor="cfg-ocr">
                  <Select id="cfg-ocr" value={ocrProvider} onChange={(e) => setOcrProvider(e.target.value)}>
                    <option value="local_tesseract">Local Tesseract OCR</option>
                    <option value="http_ocr">External HTTP OCR API</option>
                    <option value="none">Disabled</option>
                  </Select>
                </Field>
                <Field label="HTTP OCR API endpoint" htmlFor="cfg-ocr-url">
                  <Input
                    id="cfg-ocr-url"
                    value={ocrBaseUrl}
                    onChange={(e) => setOcrBaseUrl(e.target.value)}
                    placeholder="https://ocr.vendor.example/extract"
                  />
                </Field>
                <SecretField
                  id="cfg-ocr-key"
                  label="HTTP OCR API key"
                  hasValue={bundle.integrations.has_ocr_api_key}
                  hint={bundle.integrations.ocr_api_key_hint}
                  value={ocrKeyInput}
                  onChange={setOcrKeyInput}
                  clearChecked={clearOcrKey}
                  onClearChange={setClearOcrKey}
                  placeholder="Enter new OCR API key"
                />
                <Field label="AI explanation assistant" htmlFor="cfg-ai">
                  <Select id="cfg-ai" value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}>
                    <option value="local_heuristic">Local deterministic explanations</option>
                    <option value="gemini">Google Gemini (advisory only)</option>
                  </Select>
                </Field>
                <Field label="Gemini model" htmlFor="cfg-gemini-model">
                  <Input id="cfg-gemini-model" value={geminiModel} onChange={(e) => setGeminiModel(e.target.value)} />
                </Field>
                <SecretField
                  id="cfg-gemini-key"
                  label="Gemini API key"
                  hasValue={bundle.integrations.has_gemini_api_key}
                  hint={bundle.integrations.gemini_api_key_hint}
                  value={geminiKeyInput}
                  onChange={setGeminiKeyInput}
                  clearChecked={clearGeminiKey}
                  onClearChange={setClearGeminiKey}
                  placeholder="Enter new Gemini API key"
                />
              </div>
            </div>

            <div className="border-t border-slate-100 pt-5">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                KYC, Bank & Biometric Providers
              </h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="PAN verification provider" htmlFor="cfg-pan">
                  <Select id="cfg-pan" value={panProvider} onChange={(e) => setPanProvider(e.target.value)}>
                    <option value="not_configured">Not configured</option>
                    <option value="sandbox">Sandbox</option>
                    <option value="protean">Protean</option>
                    <option value="cashfree">Cashfree</option>
                  </Select>
                </Field>
                <Field label="PAN API endpoint" htmlFor="cfg-pan-url">
                  <Input
                    id="cfg-pan-url"
                    value={panBaseUrl}
                    onChange={(e) => setPanBaseUrl(e.target.value)}
                    placeholder="https://pan.provider.example/verify"
                  />
                </Field>
                <SecretField
                  id="cfg-pan-key"
                  label="PAN API key"
                  hasValue={bundle.integrations.has_pan_api_key}
                  hint={bundle.integrations.pan_api_key_hint}
                  value={panKeyInput}
                  onChange={setPanKeyInput}
                  clearChecked={clearPanKey}
                  onClearChange={setClearPanKey}
                  placeholder="Enter PAN API key"
                />

                <Field label="Bank penny-drop provider" htmlFor="cfg-bank">
                  <Select id="cfg-bank" value={bankProvider} onChange={(e) => setBankProvider(e.target.value)}>
                    <option value="not_configured">Not configured</option>
                    <option value="sandbox">Sandbox</option>
                    <option value="razorpayx">RazorpayX</option>
                    <option value="cashfree">Cashfree</option>
                  </Select>
                </Field>
                <Field label="Bank verification endpoint" htmlFor="cfg-bank-url">
                  <Input
                    id="cfg-bank-url"
                    value={bankBaseUrl}
                    onChange={(e) => setBankBaseUrl(e.target.value)}
                    placeholder="https://bank.provider.example/penny-drop"
                  />
                </Field>
                <SecretField
                  id="cfg-bank-key"
                  label="Bank API key"
                  hasValue={bundle.integrations.has_bank_api_key}
                  hint={bundle.integrations.bank_api_key_hint}
                  value={bankKeyInput}
                  onChange={setBankKeyInput}
                  clearChecked={clearBankKey}
                  onClearChange={setClearBankKey}
                  placeholder="Enter Bank API key"
                />

                <Field label="DigiLocker provider" htmlFor="cfg-digilocker">
                  <Select
                    id="cfg-digilocker"
                    value={digilockerProvider}
                    onChange={(e) => setDigilockerProvider(e.target.value)}
                  >
                    <option value="not_configured">Not configured</option>
                    <option value="sandbox">Sandbox</option>
                    <option value="negd_oauth">NeGD OAuth</option>
                  </Select>
                </Field>
                <Field label="DigiLocker base URL" htmlFor="cfg-dl-url">
                  <Input
                    id="cfg-dl-url"
                    value={digilockerBaseUrl}
                    onChange={(e) => setDigilockerBaseUrl(e.target.value)}
                    placeholder="https://digilocker.meripehchaan.gov.in"
                  />
                </Field>
                <Field label="DigiLocker client ID" htmlFor="cfg-dl-client">
                  <Input
                    id="cfg-dl-client"
                    value={digilockerClientId}
                    onChange={(e) => setDigilockerClientId(e.target.value)}
                  />
                </Field>
                <SecretField
                  id="cfg-dl-secret"
                  label="DigiLocker client secret"
                  hasValue={bundle.integrations.has_digilocker_client_secret}
                  hint={bundle.integrations.digilocker_client_secret_hint}
                  value={digilockerSecretInput}
                  onChange={setDigilockerSecretInput}
                  clearChecked={clearDigilockerSecret}
                  onClearChange={setClearDigilockerSecret}
                  placeholder="Enter DigiLocker secret"
                />

                <Field label="Face match & liveness provider" htmlFor="cfg-face">
                  <Select id="cfg-face" value={faceProvider} onChange={(e) => setFaceProvider(e.target.value)}>
                    <option value="not_configured">Not configured</option>
                    <option value="sandbox">Sandbox</option>
                    <option value="aws_rekognition">AWS Rekognition</option>
                  </Select>
                </Field>
                <Field label="Face comparison endpoint" htmlFor="cfg-face-url">
                  <Input
                    id="cfg-face-url"
                    value={faceBaseUrl}
                    onChange={(e) => setFaceBaseUrl(e.target.value)}
                    placeholder="https://face.provider.example/compare"
                  />
                </Field>
                <SecretField
                  id="cfg-face-key"
                  label="Face API key"
                  hasValue={bundle.integrations.has_face_api_key}
                  hint={bundle.integrations.face_api_key_hint}
                  value={faceKeyInput}
                  onChange={setFaceKeyInput}
                  clearChecked={clearFaceKey}
                  onClearChange={setClearFaceKey}
                  placeholder="Enter Face API key"
                />
              </div>
            </div>

            <div className="border-t border-slate-100 pt-5">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                SMS Gateway, Inbound Webhooks & Transport Resilience
              </h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="SMS gateway provider" htmlFor="cfg-sms-provider">
                  <Select id="cfg-sms-provider" value={smsProvider} onChange={(e) => setSmsProvider(e.target.value)}>
                    <option value="not_configured">Not configured</option>
                    <option value="sandbox">Sandbox (non-production only)</option>
                    <option value="twilio">Twilio HTTP</option>
                    <option value="msg91">MSG91 HTTP</option>
                    <option value="webhook_http">Custom Webhook HTTP</option>
                  </Select>
                </Field>
                <Field label="SMS gateway endpoint" htmlFor="cfg-sms-url">
                  <Input
                    id="cfg-sms-url"
                    value={smsBaseUrl}
                    onChange={(e) => setSmsBaseUrl(e.target.value)}
                    placeholder="https://sms.provider.example/messages"
                  />
                </Field>
                <Field label="SMS sender ID" htmlFor="cfg-sms-sender">
                  <Input
                    id="cfg-sms-sender"
                    value={smsSenderId}
                    onChange={(e) => setSmsSenderId(e.target.value)}
                    placeholder="PLCNST"
                  />
                </Field>
                <SecretField
                  id="cfg-sms-key"
                  label="SMS API key / auth token"
                  hasValue={bundle.integrations.has_sms_api_key}
                  hint={bundle.integrations.sms_api_key_hint}
                  value={smsKeyInput}
                  onChange={setSmsKeyInput}
                  clearChecked={clearSmsKey}
                  onClearChange={setClearSmsKey}
                  placeholder="Enter SMS API key"
                />
                <Field label="SMS timeout (seconds)" htmlFor="cfg-sms-timeout">
                  <Input
                    id="cfg-sms-timeout"
                    type="number"
                    min={2}
                    max={60}
                    value={smsTimeout}
                    onChange={(e) => setSmsTimeout(e.target.value)}
                  />
                </Field>
                <Field label="SMS max attempts" htmlFor="cfg-sms-attempts">
                  <Input
                    id="cfg-sms-attempts"
                    type="number"
                    min={1}
                    max={5}
                    value={smsMaxAttempts}
                    onChange={(e) => setSmsMaxAttempts(e.target.value)}
                  />
                </Field>

                <SecretField
                  id="cfg-wh-secret"
                  label="Inbound verification webhook HMAC secret"
                  hasValue={bundle.integrations.has_webhook_shared_secret}
                  hint={bundle.integrations.webhook_shared_secret_hint}
                  value={webhookSecretInput}
                  onChange={setWebhookSecretInput}
                  clearChecked={clearWebhookSecret}
                  onClearChange={setClearWebhookSecret}
                  placeholder="Enter HMAC-SHA256 secret"
                />
                <Field label="Shared HTTP timeout (seconds)" htmlFor="cfg-http-timeout">
                  <Input
                    id="cfg-http-timeout"
                    type="number"
                    min={2}
                    max={60}
                    value={httpTimeout}
                    onChange={(e) => setHttpTimeout(e.target.value)}
                  />
                </Field>
                <Field label="Shared HTTP transient retries" htmlFor="cfg-http-retries">
                  <Input
                    id="cfg-http-retries"
                    type="number"
                    min={0}
                    max={5}
                    value={httpMaxRetries}
                    onChange={(e) => setHttpMaxRetries(e.target.value)}
                  />
                </Field>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={ifscEnabled} onChange={(e) => setIfscEnabled(e.target.checked)} />
              Enable public RBI / Razorpay IFSC directory lookup
            </label>

            <div className="flex justify-end">
              <Button type="submit" loading={saving}>
                <Save className="h-4 w-4" /> Save integrations config
              </Button>
            </div>
          </form>
        </Card>
      )}

      {tab === "platform" && (
        <Card>
          <CardHeader
            title="Platform, session & upload controls"
            action={
              <Button variant="secondary" size="sm" onClick={() => resetSection("platform")} disabled={saving}>
                <RotateCcw className="h-3.5 w-3.5" /> Reset to defaults
              </Button>
            }
          />
          <form className="space-y-5 p-5" onSubmit={savePlatform}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Public portal URL" htmlFor="cfg-public-url">
                <Input id="cfg-public-url" required value={publicUrl} onChange={(e) => setPublicUrl(e.target.value)} />
              </Field>
              <Field label="Session idle timeout (minutes)" htmlFor="cfg-idle">
                <Input
                  id="cfg-idle"
                  type="number"
                  min={5}
                  max={1440}
                  required
                  value={idleMinutes}
                  onChange={(e) => setIdleMinutes(e.target.value)}
                />
              </Field>
              <Field label="Login failure lockout threshold" htmlFor="cfg-fail-max">
                <Input
                  id="cfg-fail-max"
                  type="number"
                  min={3}
                  max={20}
                  required
                  value={maxFailures}
                  onChange={(e) => setMaxFailures(e.target.value)}
                />
              </Field>
              <Field label="Account lockout duration (minutes)" htmlFor="cfg-lockout-min">
                <Input
                  id="cfg-lockout-min"
                  type="number"
                  min={1}
                  max={240}
                  required
                  value={lockoutMinutes}
                  onChange={(e) => setLockoutMinutes(e.target.value)}
                />
              </Field>
              <Field label="Max upload file size (MB)" htmlFor="cfg-upload-mb">
                <Input
                  id="cfg-upload-mb"
                  type="number"
                  min={1}
                  max={50}
                  required
                  value={maxUploadMb}
                  onChange={(e) => setMaxUploadMb(e.target.value)}
                />
              </Field>
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={requireVerify} onChange={(e) => setRequireVerify(e.target.checked)} />
              Require email verification before onboarding actions
            </label>

            <div className="flex justify-end">
              <Button type="submit" loading={saving}>
                <Save className="h-4 w-4" /> Save platform settings
              </Button>
            </div>
          </form>
        </Card>
      )}

      {tab === "monitor" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-slate-600">
              Recent health probes, email & SMS dispatch records, and inbound verification/LMS webhook deliveries.
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => void loadMonitor()}>
                <RefreshCw className="h-3.5 w-3.5" /> Refresh monitor
              </Button>
              <Button variant="secondary" size="sm" onClick={() => void retryFailedSms()} loading={retryingSms}>
                Retry failed SMS
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader title="Recent active health probes" />
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Adapter</th>
                    <th className="px-4 py-2 font-semibold">Status</th>
                    <th className="px-4 py-2 font-semibold">Mode</th>
                    <th className="px-4 py-2 font-semibold">Latency</th>
                    <th className="px-4 py-2 font-semibold">Detail</th>
                    <th className="px-4 py-2 font-semibold">Checked at</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(monitor?.probes ?? []).map((p, idx) => (
                    <tr key={`${p.adapter_key}-${idx}`}>
                      <td className="px-4 py-2 font-mono font-medium text-slate-800">{p.adapter_key}</td>
                      <td className="px-4 py-2">
                        <Badge tone={p.status === "CONFIGURED" ? "success" : p.status === "DEGRADED" ? "danger" : "neutral"}>
                          {p.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-slate-600">{p.mode}</td>
                      <td className="px-4 py-2 text-slate-600">{p.latency_ms !== null ? `${p.latency_ms} ms` : "—"}</td>
                      <td className="px-4 py-2 text-slate-600">{p.detail}</td>
                      <td className="px-4 py-2 text-slate-500">{formatDateTime(p.checked_at)}</td>
                    </tr>
                  ))}
                  {(!monitor || monitor.probes.length === 0) && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No probes recorded yet. Click &ldquo;Run health probes&rdquo; above.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardHeader title="SMS notification deliveries" />
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Recipient</th>
                    <th className="px-4 py-2 font-semibold">Event</th>
                    <th className="px-4 py-2 font-semibold">Provider</th>
                    <th className="px-4 py-2 font-semibold">Status</th>
                    <th className="px-4 py-2 font-semibold">Attempts</th>
                    <th className="px-4 py-2 font-semibold">Vendor Ref / Error</th>
                    <th className="px-4 py-2 font-semibold">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(monitor?.sms_deliveries ?? []).map((s) => (
                    <tr key={s.id}>
                      <td className="px-4 py-2 font-mono text-slate-800">{s.recipient_mobile}</td>
                      <td className="px-4 py-2 text-slate-700">{s.event_type}</td>
                      <td className="px-4 py-2 text-slate-600">
                        {s.provider}
                        {s.is_simulated ? " (simulated)" : ""}
                      </td>
                      <td className="px-4 py-2">
                        <Badge
                          tone={
                            s.status === "SENT"
                              ? "success"
                              : s.status === "FAILED"
                                ? "danger"
                                : s.status === "SANDBOX_SIMULATED"
                                  ? "warning"
                                  : "neutral"
                          }
                        >
                          {s.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-slate-600">{s.attempts}</td>
                      <td className="px-4 py-2 text-slate-500">{s.provider_message_id ?? s.error ?? "—"}</td>
                      <td className="px-4 py-2 text-slate-500">{formatDateTime(s.created_at)}</td>
                    </tr>
                  ))}
                  {(!monitor || monitor.sms_deliveries.length === 0) && (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                        No SMS delivery attempts recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardHeader title="Inbound webhook deliveries" />
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Source</th>
                    <th className="px-4 py-2 font-semibold">Event ID</th>
                    <th className="px-4 py-2 font-semibold">Signature</th>
                    <th className="px-4 py-2 font-semibold">Status</th>
                    <th className="px-4 py-2 font-semibold">Application / Note</th>
                    <th className="px-4 py-2 font-semibold">Received</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(monitor?.webhook_deliveries ?? []).map((w) => (
                    <tr key={w.id}>
                      <td className="px-4 py-2 font-semibold uppercase text-slate-800">{w.source}</td>
                      <td className="px-4 py-2 font-mono text-slate-600">{w.external_event_id ?? "—"}</td>
                      <td className="px-4 py-2">
                        <Badge tone={w.signature_valid ? "success" : "danger"}>
                          {w.signature_valid ? "VALID" : "REJECTED"}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-slate-700">{w.processing_status}</td>
                      <td className="px-4 py-2 text-slate-500">{w.error_message ?? w.application_id ?? "—"}</td>
                      <td className="px-4 py-2 text-slate-500">{formatDateTime(w.received_at)}</td>
                    </tr>
                  ))}
                  {(!monitor || monitor.webhook_deliveries.length === 0) && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No inbound webhook calls received yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardHeader title="Email deliveries" />
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Recipient</th>
                    <th className="px-4 py-2 font-semibold">Template</th>
                    <th className="px-4 py-2 font-semibold">Provider</th>
                    <th className="px-4 py-2 font-semibold">Status</th>
                    <th className="px-4 py-2 font-semibold">Attempts</th>
                    <th className="px-4 py-2 font-semibold">Error / Sent</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(monitor?.email_deliveries ?? []).map((em) => (
                    <tr key={em.id}>
                      <td className="px-4 py-2 font-mono text-slate-800">{em.recipient}</td>
                      <td className="px-4 py-2 text-slate-700">{em.template}</td>
                      <td className="px-4 py-2 text-slate-600">{em.provider}</td>
                      <td className="px-4 py-2">
                        <Badge tone={em.status === "SENT" ? "success" : em.status === "FAILED" ? "danger" : "neutral"}>
                          {em.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-slate-600">{em.attempts}</td>
                      <td className="px-4 py-2 text-slate-500">
                        {em.error ?? (em.sent_at ? formatDateTime(em.sent_at) : "Queued")}
                      </td>
                    </tr>
                  ))}
                  {(!monitor || monitor.email_deliveries.length === 0) && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No email deliveries recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
