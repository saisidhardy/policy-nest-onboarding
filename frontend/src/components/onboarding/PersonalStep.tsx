"use client";

import { useState } from "react";
import { Alert, Button, Card, CardHeader, Field, Input, Select } from "@/components/ui";
import type { ApplicationDetail, GenderType, LanguageCode } from "@/lib/types";

export function PersonalStep({
  application,
  saving,
  error,
  fieldErrors,
  onSave,
}: {
  application: ApplicationDetail;
  saving: boolean;
  error: string | null;
  fieldErrors: Record<string, string>;
  onSave: (payload: Record<string, unknown>, nextStep?: number) => Promise<void>;
}) {
  const [form, setForm] = useState({
    full_name: application.full_name ?? "",
    date_of_birth: application.date_of_birth ?? "",
    gender: (application.gender ?? "") as GenderType | "",
    father_or_spouse_name: application.father_or_spouse_name ?? "",
    mobile: application.mobile ?? "",
    email: application.email ?? "",
    pan_number: application.pan_number ?? "",
    aadhaar_last4: application.aadhaar_last4 ?? "",
    preferred_language: (application.preferred_language ?? "EN") as LanguageCode,
  });

  const payload = () => ({
    full_name: form.full_name || null,
    date_of_birth: form.date_of_birth || null,
    gender: form.gender || null,
    father_or_spouse_name: form.father_or_spouse_name || null,
    mobile: form.mobile || null,
    email: form.email || null,
    pan_number: form.pan_number ? form.pan_number.toUpperCase().trim() : null,
    aadhaar_last4: form.aadhaar_last4 ? form.aadhaar_last4.trim() : null,
    preferred_language: form.preferred_language,
  });

  return (
    <Card>
      <CardHeader
        title="Step 1: Personal details"
        description="Enter your details exactly as printed on your PAN card. PolicyNest only stores the last 4 digits of Aadhaar."
      />
      <form
        className="space-y-5 px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          void onSave(payload(), 2);
        }}
        noValidate
      >
        {error && <Alert tone="error">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name (as on PAN)" htmlFor="p-name" error={fieldErrors.full_name}>
            <Input
              id="p-name"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              invalid={!!fieldErrors.full_name}
              required
            />
          </Field>
          <Field label="Father or spouse name" htmlFor="p-father" error={fieldErrors.father_or_spouse_name}>
            <Input
              id="p-father"
              value={form.father_or_spouse_name}
              onChange={(e) => setForm({ ...form, father_or_spouse_name: e.target.value })}
              invalid={!!fieldErrors.father_or_spouse_name}
              required
            />
          </Field>
          <Field label="Date of birth" htmlFor="p-dob" error={fieldErrors.date_of_birth}>
            <Input
              id="p-dob"
              type="date"
              value={form.date_of_birth}
              onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
              invalid={!!fieldErrors.date_of_birth}
              required
            />
          </Field>
          <Field label="Gender" htmlFor="p-gender" error={fieldErrors.gender}>
            <Select
              id="p-gender"
              value={form.gender}
              onChange={(e) => setForm({ ...form, gender: e.target.value as GenderType | "" })}
            >
              <option value="">Select gender</option>
              <option value="FEMALE">Female</option>
              <option value="MALE">Male</option>
              <option value="OTHER">Other</option>
              <option value="PREFER_NOT_TO_SAY">Prefer not to say</option>
            </Select>
          </Field>
          <Field label="Mobile number" htmlFor="p-mobile" error={fieldErrors.mobile} hint="10-digit Indian mobile number">
            <Input
              id="p-mobile"
              type="tel"
              value={form.mobile}
              onChange={(e) => setForm({ ...form, mobile: e.target.value })}
              invalid={!!fieldErrors.mobile}
              required
            />
          </Field>
          <Field label="Email address" htmlFor="p-email" error={fieldErrors.email}>
            <Input
              id="p-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              invalid={!!fieldErrors.email}
              required
            />
          </Field>
          <Field label="PAN number" htmlFor="p-pan" error={fieldErrors.pan_number} hint="10 characters, e.g. ABCDE1234F">
            <Input
              id="p-pan"
              value={form.pan_number}
              maxLength={10}
              className="uppercase"
              onChange={(e) => setForm({ ...form, pan_number: e.target.value.toUpperCase() })}
              invalid={!!fieldErrors.pan_number}
              required
            />
          </Field>
          <Field
            label="Aadhaar (last 4 digits only)"
            htmlFor="p-aadhaar"
            error={fieldErrors.aadhaar_last4}
            hint="UIDAI data minimisation: never enter all 12 digits."
          >
            <Input
              id="p-aadhaar"
              inputMode="numeric"
              maxLength={4}
              placeholder="e.g. 7890"
              value={form.aadhaar_last4}
              onChange={(e) => setForm({ ...form, aadhaar_last4: e.target.value })}
              invalid={!!fieldErrors.aadhaar_last4}
              required
            />
          </Field>
          <Field label="Preferred communication language" htmlFor="p-lang" error={fieldErrors.preferred_language}>
            <Select
              id="p-lang"
              value={form.preferred_language}
              onChange={(e) => setForm({ ...form, preferred_language: e.target.value as LanguageCode })}
            >
              <option value="EN">English</option>
              <option value="HI">Hindi (हिन्दी)</option>
            </Select>
          </Field>
        </div>
        <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
          <Button type="button" variant="secondary" loading={saving} onClick={() => void onSave(payload(), 1)}>
            Save draft
          </Button>
          <Button type="submit" loading={saving}>
            Save & continue
          </Button>
        </div>
      </form>
    </Card>
  );
}
