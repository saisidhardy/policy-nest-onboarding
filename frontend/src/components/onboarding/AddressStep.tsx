"use client";

import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Alert, Button, Card, CardHeader, Field, Input, Select } from "@/components/ui";
import { INDIAN_STATES } from "@/lib/constants";
import type { ApplicationDetail } from "@/lib/types";

export function AddressStep({
  application,
  saving,
  error,
  fieldErrors,
  onSave,
  onBack,
}: {
  application: ApplicationDetail;
  saving: boolean;
  error: string | null;
  fieldErrors: Record<string, string>;
  onSave: (payload: Record<string, unknown>, nextStep?: number) => Promise<void>;
  onBack: () => void;
}) {
  const [page, setPage] = useState<1 | 2>(1);
  const [pinNotice, setPinNotice] = useState<string | null>(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [form, setForm] = useState({
    address_line1: application.address_line1 ?? "",
    address_line2: application.address_line2 ?? "",
    city: application.city ?? "",
    district: application.district ?? "",
    state: application.state ?? "",
    pincode: application.pincode ?? "",
    same_as_permanent: application.same_as_permanent,
    permanent_address_line1: application.permanent_address_line1 ?? "",
    permanent_address_line2: application.permanent_address_line2 ?? "",
    permanent_city: application.permanent_city ?? "",
    permanent_state: application.permanent_state ?? "",
    permanent_pincode: application.permanent_pincode ?? "",
  });

  const handlePincodeLookup = async (pin: string) => {
    setForm((prev) => ({ ...prev, pincode: pin }));
    if (pin.length === 6 && /^\d{6}$/.test(pin)) {
      setPinLoading(true);
      setPinNotice(null);
      try {
        const res = await fetch(`https://api.postalpincode.in/pincode/${pin}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data[0]?.Status === "Success" && data[0]?.PostOffice?.length > 0) {
            const po = data[0].PostOffice[0];
            const dist = po.District || "";
            const st = po.State || "";
            const matchedState = INDIAN_STATES.find(
              (s) => s.toLowerCase() === st.toLowerCase()
            ) ?? st;
            setForm((prev) => ({
              ...prev,
              district: prev.district || dist,
              state: prev.state || matchedState,
              city: prev.city || po.Name || dist,
            }));
            setPinNotice(`✓ India Post Verified: ${dist}, ${matchedState} (${po.Name})`);
          }
        }
      } catch {
        // Fallback silently if offline
      } finally {
        setPinLoading(false);
      }
    }
  };

  const payload = () => ({
    address_line1: form.address_line1 || null,
    address_line2: form.address_line2 || null,
    city: form.city || null,
    district: form.district || null,
    state: form.state || null,
    pincode: form.pincode || null,
    same_as_permanent: form.same_as_permanent,
    ...(form.same_as_permanent
      ? {}
      : {
          permanent_address_line1: form.permanent_address_line1 || null,
          permanent_address_line2: form.permanent_address_line2 || null,
          permanent_city: form.permanent_city || null,
          permanent_state: form.permanent_state || null,
          permanent_pincode: form.permanent_pincode || null,
        }),
  });

  const handleNextPage = async () => {
    await onSave(payload(), 2);
    setPage(2);
  };

  return (
    <Card>
      <CardHeader
        title="Step 2: Address details"
        description={
          page === 1
            ? "Page 1 of 2: Current residential address. Enter your 6-digit PIN code to auto-detect City and State."
            : "Page 2 of 2: Permanent legal address and territorial jurisdiction."
        }
        action={
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
            <span>Page {page} of 2</span>
          </div>
        }
      />

      {/* Sub-page Navigation Tabs */}
      <div className="flex border-b border-slate-100 bg-slate-50/50 px-5 pt-3 text-xs font-semibold">
        <button
          type="button"
          onClick={() => setPage(1)}
          className={`pb-2.5 px-3 border-b-2 transition ${
            page === 1
              ? "border-brand-700 text-brand-800 font-bold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          1. Residential Address
        </button>
        <button
          type="button"
          onClick={() => setPage(2)}
          className={`pb-2.5 px-3 border-b-2 transition ${
            page === 2
              ? "border-brand-700 text-brand-800 font-bold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          2. Permanent Address
        </button>
      </div>

      <form
        className="space-y-5 px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (page === 1) {
            void handleNextPage();
          } else {
            void onSave(payload(), 3);
          }
        }}
        noValidate
      >
        {error && <Alert tone="error">{error}</Alert>}

        {/* Page 1: Residential Address */}
        {page === 1 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Field
                  label="PIN code"
                  htmlFor="a-pin"
                  error={fieldErrors.pincode}
                  hint={
                    pinNotice ? (
                      <span className="font-medium text-emerald-700">{pinNotice}</span>
                    ) : pinLoading ? (
                      "Verifying with India Post..."
                    ) : (
                      "6-digit PIN code (auto-detects District & State via India Post)"
                    )
                  }
                >
                  <Input
                    id="a-pin"
                    inputMode="numeric"
                    maxLength={6}
                    value={form.pincode}
                    onChange={(e) => void handlePincodeLookup(e.target.value)}
                    invalid={!!fieldErrors.pincode}
                    required
                  />
                </Field>
              </div>

              <div className="sm:col-span-2">
                <Field label="Address line 1 (Flat/House/Street)" htmlFor="a-l1" error={fieldErrors.address_line1}>
                  <Input
                    id="a-l1"
                    value={form.address_line1}
                    onChange={(e) => setForm({ ...form, address_line1: e.target.value })}
                    invalid={!!fieldErrors.address_line1}
                    required
                  />
                </Field>
              </div>

              <div className="sm:col-span-2">
                <Field label="Address line 2 (Area/Landmark - optional)" htmlFor="a-l2" error={fieldErrors.address_line2}>
                  <Input
                    id="a-l2"
                    value={form.address_line2}
                    onChange={(e) => setForm({ ...form, address_line2: e.target.value })}
                    invalid={!!fieldErrors.address_line2}
                  />
                </Field>
              </div>

              <Field label="City / Town" htmlFor="a-city" error={fieldErrors.city}>
                <Input
                  id="a-city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  invalid={!!fieldErrors.city}
                  required
                />
              </Field>

              <Field label="District" htmlFor="a-district" error={fieldErrors.district}>
                <Input
                  id="a-district"
                  value={form.district}
                  onChange={(e) => setForm({ ...form, district: e.target.value })}
                  invalid={!!fieldErrors.district}
                  required
                />
              </Field>

              <div className="sm:col-span-2">
                <Field label="State / Union Territory" htmlFor="a-state" error={fieldErrors.state}>
                  <Select id="a-state" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })}>
                    <option value="">Select state or UT</option>
                    {INDIAN_STATES.map((st) => (
                      <option key={st} value={st}>
                        {st}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </div>

            <div className="pt-2">
              <label className="flex items-center gap-2.5 text-sm font-medium text-slate-800 p-3 rounded-xl border border-slate-200 bg-slate-50/70 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.same_as_permanent}
                  onChange={(e) => setForm({ ...form, same_as_permanent: e.target.checked })}
                  className="h-4 w-4 rounded border-slate-300 text-brand-700"
                />
                <span>My permanent address is identical to my current residential address above</span>
              </label>
            </div>

            <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={onBack}>
                  <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Step 1
                </Button>
                <Button type="button" variant="ghost" loading={saving} onClick={() => void onSave(payload(), 2)}>
                  Save draft
                </Button>
              </div>
              <Button type="button" onClick={() => void handleNextPage()} loading={saving}>
                <span>Next: Permanent Address (Page 2 of 2)</span>
                <ArrowRight className="h-4 w-4 ml-1.5" />
              </Button>
            </div>
          </div>
        )}

        {/* Page 2: Permanent Address */}
        {page === 2 && (
          <div className="space-y-4 animate-fadeIn">
            {form.same_as_permanent ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-2">
                <div className="flex items-center gap-2 text-emerald-900 font-bold text-sm">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span>Permanent address verified as identical to residential</span>
                </div>
                <p className="text-xs text-emerald-800 leading-relaxed">
                  Your permanent address record will use: <strong>{form.address_line1 || "Line 1"}, {form.city || "City"}, {form.state || "State"} - {form.pincode || "PIN"}</strong>.
                  Your operational onboarding region is determined by {form.state || "your state"}.
                </p>
                <button
                  type="button"
                  onClick={() => setForm({ ...form, same_as_permanent: false })}
                  className="text-xs font-semibold text-emerald-700 hover:underline pt-1"
                >
                  Need to specify a different permanent address? Click here.
                </button>
              </div>
            ) : (
              <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Field label="Permanent address line 1" htmlFor="pa-l1" error={fieldErrors.permanent_address_line1}>
                    <Input
                      id="pa-l1"
                      value={form.permanent_address_line1}
                      onChange={(e) => setForm({ ...form, permanent_address_line1: e.target.value })}
                      invalid={!!fieldErrors.permanent_address_line1}
                    />
                  </Field>
                </div>
                <div className="sm:col-span-2">
                  <Field label="Permanent address line 2 (optional)" htmlFor="pa-l2" error={fieldErrors.permanent_address_line2}>
                    <Input
                      id="pa-l2"
                      value={form.permanent_address_line2}
                      onChange={(e) => setForm({ ...form, permanent_address_line2: e.target.value })}
                    />
                  </Field>
                </div>
                <Field label="Permanent city" htmlFor="pa-city" error={fieldErrors.permanent_city}>
                  <Input
                    id="pa-city"
                    value={form.permanent_city}
                    onChange={(e) => setForm({ ...form, permanent_city: e.target.value })}
                    invalid={!!fieldErrors.permanent_city}
                  />
                </Field>
                <Field label="Permanent state / UT" htmlFor="pa-state" error={fieldErrors.permanent_state}>
                  <Select
                    id="pa-state"
                    value={form.permanent_state}
                    onChange={(e) => setForm({ ...form, permanent_state: e.target.value })}
                  >
                    <option value="">Select state or UT</option>
                    {INDIAN_STATES.map((st) => (
                      <option key={st} value={st}>
                        {st}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Permanent PIN code" htmlFor="pa-pin" error={fieldErrors.permanent_pincode}>
                  <Input
                    id="pa-pin"
                    inputMode="numeric"
                    maxLength={6}
                    value={form.permanent_pincode}
                    onChange={(e) => setForm({ ...form, permanent_pincode: e.target.value })}
                    invalid={!!fieldErrors.permanent_pincode}
                  />
                </Field>
              </div>
            )}

            <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={() => setPage(1)}>
                  <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Page 1
                </Button>
                <Button type="button" variant="ghost" loading={saving} onClick={() => void onSave(payload(), 2)}>
                  Save draft
                </Button>
              </div>
              <Button type="submit" loading={saving}>
                Save & continue to Step 3
              </Button>
            </div>
          </div>
        )}
      </form>
    </Card>
  );
}
