"use client";

import { KeyRound, RotateCcw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AdminConfigBundle, IntegrationsConfig, LmsConfig, PlatformConfig } from "@/lib/types";

export default function AdminIntegrationsPage() {
  return (
    <RequirePermission permission="config:manage">
      <ConfigCenterView />
    </RequirePermission>
  );
}

type SectionTab = "lms" | "integrations" | "platform";

function ConfigCenterView() {
  const [bundle, setBundle] = useState<AdminConfigBundle | null>(null);
  const [tab, setTab] = useState<SectionTab>("lms");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
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
  const [aiProvider, setAiProvider] = useState("local_heuristic");
  const [geminiModel, setGeminiModel] = useState("gemini-3.8-flash");
  const [geminiKeyInput, setGeminiKeyInput] = useState("");
  const [clearGeminiKey, setClearGeminiKey] = useState(false);
  const [ifscEnabled, setIfscEnabled] = useState(true);
  const [panProvider, setPanProvider] = useState("not_configured");
  const [bankProvider, setBankProvider] = useState("not_configured");
  const [digilockerProvider, setDigilockerProvider] = useState("not_configured");
  const [faceProvider, setFaceProvider] = useState("not_configured");

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

    setOcrProvider(b.integrations.ocr_provider);
    setAiProvider(b.integrations.ai_provider);
    setGeminiModel(b.integrations.gemini_model);
    setGeminiKeyInput("");
    setClearGeminiKey(false);
    setIfscEnabled(b.integrations.ifsc_lookup_enabled);
    setPanProvider(b.integrations.pan_verification_provider);
    setBankProvider(b.integrations.bank_verification_provider);
    setDigilockerProvider(b.integrations.digilocker_provider);
    setFaceProvider(b.integrations.face_match_provider);

    setPublicUrl(b.platform.public_app_url);
    setRequireVerify(b.platform.require_email_verification);
    setIdleMinutes(String(b.platform.session_idle_minutes));
    setMaxFailures(String(b.platform.login_max_failures));
    setLockoutMinutes(String(b.platform.login_lockout_minutes));
    setMaxUploadMb(String(b.platform.max_upload_size_mb));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<AdminConfigBundle>("/admin/config");
      hydrateForms(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load configuration.");
    } finally {
      setLoading(false);
    }
  }, [hydrateForms]);

  useEffect(() => {
    void load();
  }, [load]);

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
          ai_provider: aiProvider,
          gemini_model: geminiModel,
          gemini_api_key: geminiKeyInput.trim() || null,
          clear_gemini_api_key: clearGeminiKey,
          ifsc_lookup_enabled: ifscEnabled,
          pan_verification_provider: panProvider,
          bank_verification_provider: bankProvider,
          digilocker_provider: digilockerProvider,
          face_match_provider: faceProvider,
        }),
      });
      await load();
      setNotice("Saved verification & AI adapter configuration to PostgreSQL.");
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

  async function resetSection(section: SectionTab) {
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

  const activeSource =
    tab === "lms" ? bundle.lms : tab === "integrations" ? bundle.integrations : bundle.platform;

  return (
    <>
      <PageHeader
        title="Integrations & platform configuration"
        description="Configure external verification adapters, LMS training thresholds, and platform security parameters. Secrets are encrypted with Fernet at rest and never exposed in plain text."
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
        <CardHeader title="Live adapter health snapshot" />
        <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
          {bundle.integrations_health.map((item) => (
            <div key={item.key} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-xs font-semibold text-slate-800">{item.name}</p>
                <Badge
                  tone={
                    item.mode === "LIVE"
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
            </div>
          ))}
        </div>
      </Card>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["lms", "LMS configuration"],
              ["integrations", "Verification & AI"],
              ["platform", "Platform & security"],
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

        <div className="flex items-center gap-3 text-xs text-slate-500">
          <Badge tone={activeSource.source === "database" ? "brand" : "neutral"}>
            Source: {activeSource.source === "database" ? "PostgreSQL override" : ".env default"}
          </Badge>
          {activeSource.updated_at && <span>Updated {formatDateTime(activeSource.updated_at)}</span>}
        </div>
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
              <Field label="LMS API base URL" htmlFor="cfg-lms-url" hint="Required when using http_api.">
                <Input
                  id="cfg-lms-url"
                  value={lmsBaseUrl}
                  onChange={(e) => setLmsBaseUrl(e.target.value)}
                  placeholder="https://lms.partner.example/api"
                />
              </Field>
              <Field label="IRDAI POSP course code" htmlFor="cfg-lms-course">
                <Input id="cfg-lms-course" required value={lmsCourseCode} onChange={(e) => setLmsCourseCode(e.target.value)} />
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
                  step="0.5"
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
              <Field label="Exam cooldown after failure (hours)" htmlFor="cfg-lms-cooldown">
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
              <Field label="Sync retry base backoff (seconds)" htmlFor="cfg-lms-retry">
                <Input
                  id="cfg-lms-retry"
                  type="number"
                  min={10}
                  max={3600}
                  required
                  value={lmsRetryBase}
                  onChange={(e) => setLmsRetryBase(e.target.value)}
                />
              </Field>
              <Field label="Max sync attempts" htmlFor="cfg-lms-max-att">
                <Input
                  id="cfg-lms-max-att"
                  type="number"
                  min={1}
                  max={10}
                  required
                  value={lmsMaxAttempts}
                  onChange={(e) => setLmsMaxAttempts(e.target.value)}
                />
              </Field>
            </div>

            <div className="grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Field
                  label="LMS API key"
                  htmlFor="cfg-lms-key"
                  hint={
                    bundle.lms.has_api_key ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700">
                        <KeyRound className="h-3 w-3" /> Stored: {bundle.lms.api_key_hint ?? "set"}
                      </span>
                    ) : (
                      "Not set"
                    )
                  }
                >
                  <Input
                    id="cfg-lms-key"
                    type="password"
                    autoComplete="new-password"
                    value={lmsApiKeyInput}
                    onChange={(e) => setLmsApiKeyInput(e.target.value)}
                    placeholder="Enter new API key to replace"
                  />
                </Field>
                {bundle.lms.has_api_key && (
                  <label className="flex items-center gap-2 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={clearLmsApiKey}
                      onChange={(e) => setClearLmsApiKey(e.target.checked)}
                    />
                    Clear stored API key
                  </label>
                )}
              </div>

              <div className="space-y-2">
                <Field
                  label="LMS webhook HMAC secret"
                  htmlFor="cfg-lms-wh"
                  hint={
                    bundle.lms.has_webhook_secret ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700">
                        <KeyRound className="h-3 w-3" /> Stored: {bundle.lms.webhook_secret_hint ?? "set"}
                      </span>
                    ) : (
                      "Not set"
                    )
                  }
                >
                  <Input
                    id="cfg-lms-wh"
                    type="password"
                    autoComplete="new-password"
                    value={lmsWebhookSecretInput}
                    onChange={(e) => setLmsWebhookSecretInput(e.target.value)}
                    placeholder="Enter new webhook secret to replace"
                  />
                </Field>
                {bundle.lms.has_webhook_secret && (
                  <label className="flex items-center gap-2 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={clearLmsWebhookSecret}
                      onChange={(e) => setClearLmsWebhookSecret(e.target.checked)}
                    />
                    Clear stored webhook secret
                  </label>
                )}
              </div>
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
            title="Verification, OCR & advisory AI adapters"
            action={
              <Button variant="secondary" size="sm" onClick={() => resetSection("integrations")} disabled={saving}>
                <RotateCcw className="h-3.5 w-3.5" /> Reset to defaults
              </Button>
            }
          />
          <form className="space-y-5 p-5" onSubmit={saveIntegrations}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="OCR engine" htmlFor="cfg-ocr">
                <Select id="cfg-ocr" value={ocrProvider} onChange={(e) => setOcrProvider(e.target.value)}>
                  <option value="local_tesseract">Local Tesseract OCR</option>
                  <option value="none">Disabled</option>
                </Select>
              </Field>
              <Field label="AI explanation assistant" htmlFor="cfg-ai">
                <Select id="cfg-ai" value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}>
                  <option value="local_heuristic">Local deterministic explanations</option>
                  <option value="gemini">Google Gemini (advisory only)</option>
                </Select>
              </Field>
              <Field label="Gemini model" htmlFor="cfg-gemini-model">
                <Input id="cfg-gemini-model" value={geminiModel} onChange={(e) => setGeminiModel(e.target.value)} />
              </Field>
              <div className="space-y-2">
                <Field
                  label="Gemini API key"
                  htmlFor="cfg-gemini-key"
                  hint={
                    bundle.integrations.has_gemini_api_key ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700">
                        <KeyRound className="h-3 w-3" /> Stored: {bundle.integrations.gemini_api_key_hint ?? "set"}
                      </span>
                    ) : (
                      "Not set"
                    )
                  }
                >
                  <Input
                    id="cfg-gemini-key"
                    type="password"
                    autoComplete="new-password"
                    value={geminiKeyInput}
                    onChange={(e) => setGeminiKeyInput(e.target.value)}
                    placeholder="Enter new Gemini API key"
                  />
                </Field>
                {bundle.integrations.has_gemini_api_key && (
                  <label className="flex items-center gap-2 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={clearGeminiKey}
                      onChange={(e) => setClearGeminiKey(e.target.checked)}
                    />
                    Clear stored Gemini key
                  </label>
                )}
              </div>
              <Field label="PAN verification provider" htmlFor="cfg-pan">
                <Select id="cfg-pan" value={panProvider} onChange={(e) => setPanProvider(e.target.value)}>
                  <option value="not_configured">Not configured</option>
                  <option value="sandbox">Sandbox</option>
                  <option value="protean">Protean</option>
                  <option value="cashfree">Cashfree</option>
                </Select>
              </Field>
              <Field label="Bank penny-drop provider" htmlFor="cfg-bank">
                <Select id="cfg-bank" value={bankProvider} onChange={(e) => setBankProvider(e.target.value)}>
                  <option value="not_configured">Not configured</option>
                  <option value="sandbox">Sandbox</option>
                  <option value="razorpayx">RazorpayX</option>
                  <option value="cashfree">Cashfree</option>
                </Select>
              </Field>
              <Field label="DigiLocker provider" htmlFor="cfg-digilocker">
                <Select id="cfg-digilocker" value={digilockerProvider} onChange={(e) => setDigilockerProvider(e.target.value)}>
                  <option value="not_configured">Not configured</option>
                  <option value="sandbox">Sandbox</option>
                  <option value="negd_oauth">NeGD OAuth</option>
                </Select>
              </Field>
              <Field label="Face match & liveness provider" htmlFor="cfg-face">
                <Select id="cfg-face" value={faceProvider} onChange={(e) => setFaceProvider(e.target.value)}>
                  <option value="not_configured">Not configured</option>
                  <option value="sandbox">Sandbox</option>
                  <option value="aws_rekognition">AWS Rekognition</option>
                </Select>
              </Field>
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
    </>
  );
}
