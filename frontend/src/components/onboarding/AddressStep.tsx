"use client";

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

  return (
    <Card>
      <CardHeader
        title="Step 2: Address details"
        description="Provide your current residential address. Your state determines your operational onboarding region."
      />
      <form
        className="space-y-5 px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          void onSave(payload(), 3);
        }}
        noValidate
      >
        {error && <Alert tone="error">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Address line 1" htmlFor="a-l1" error={fieldErrors.address_line1}>
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
            <Field label="Address line 2 (optional)" htmlFor="a-l2" error={fieldErrors.address_line2}>
              <Input
                id="a-l2"
                value={form.address_line2}
                onChange={(e) => setForm({ ...form, address_line2: e.target.value })}
                invalid={!!fieldErrors.address_line2}
              />
            </Field>
          </div>
          <Field label="City / Town" htmlFor="a-city" error={fieldErrors.city}>
            <Input id="a-city" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} invalid={!!fieldErrors.city} required />
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
          <Field label="PIN code" htmlFor="a-pin" error={fieldErrors.pincode} hint="6-digit Indian postal PIN">
            <Input
              id="a-pin"
              inputMode="numeric"
              maxLength={6}
              value={form.pincode}
              onChange={(e) => setForm({ ...form, pincode: e.target.value })}
              invalid={!!fieldErrors.pincode}
              required
            />
          </Field>
        </div>

        <label className="flex items-center gap-2.5 text-sm font-medium text-slate-800">
          <input
            type="checkbox"
            checked={form.same_as_permanent}
            onChange={(e) => setForm({ ...form, same_as_permanent: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 text-brand-700"
          />
          Permanent address is the same as my current residential address
        </label>

        {!form.same_as_permanent && (
          <div className="grid gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2">
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
            <Button type="button" variant="secondary" onClick={onBack}>
              Back
            </Button>
            <Button type="button" variant="secondary" loading={saving} onClick={() => void onSave(payload(), 2)}>
              Save draft
            </Button>
          </div>
          <Button type="submit" loading={saving}>
            Save & continue
          </Button>
        </div>
      </form>
    </Card>
  );
}
