"use client";

import { useState } from "react";
import { Alert, Button, Card, CardHeader, Field, Input, Select } from "@/components/ui";
import type { ApplicationDetail, EducationLevelType, ResultStatusType } from "@/lib/types";

export function EducationStep({
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
    education_level: (application.education_level ?? "") as EducationLevelType | "",
    board_name: application.board_name ?? "",
    school_or_university: application.school_or_university ?? "",
    passing_year: application.passing_year ? String(application.passing_year) : "",
    roll_number: application.roll_number ?? "",
    result_status: (application.result_status ?? "") as ResultStatusType | "",
    percentage_or_cgpa: application.percentage_or_cgpa ?? "",
  });

  const payload = () => ({
    education_level: form.education_level || null,
    board_name: form.board_name || null,
    school_or_university: form.school_or_university || null,
    passing_year: form.passing_year ? Number(form.passing_year) : null,
    roll_number: form.roll_number || null,
    result_status: form.result_status || null,
    percentage_or_cgpa: form.percentage_or_cgpa || null,
  });

  return (
    <Card>
      <CardHeader
        title="Step 3: Education details"
        description="IRDAI requires at least Class 10 pass from a recognised board (CBSE, CISCE, NIOS, or State Board)."
      />
      <form
        className="space-y-5 px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          void onSave(payload(), 4);
        }}
        noValidate
      >
        {error && <Alert tone="error">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Highest education level" htmlFor="e-level" error={fieldErrors.education_level}>
            <Select
              id="e-level"
              value={form.education_level}
              onChange={(e) => setForm({ ...form, education_level: e.target.value as EducationLevelType | "" })}
            >
              <option value="">Select qualification</option>
              <option value="CLASS_10">Class 10 (Secondary)</option>
              <option value="CLASS_12">Class 12 (Higher Secondary)</option>
              <option value="GRADUATE">Graduate</option>
              <option value="POST_GRADUATE">Post-graduate</option>
            </Select>
          </Field>
          <Field label="Class 10 Board" htmlFor="e-board" error={fieldErrors.board_name} hint="e.g. CBSE, ICSE, NIOS, Maharashtra State Board">
            <Input
              id="e-board"
              value={form.board_name}
              onChange={(e) => setForm({ ...form, board_name: e.target.value })}
              invalid={!!fieldErrors.board_name}
            />
          </Field>
          <Field label="School / Institution name" htmlFor="e-school" error={fieldErrors.school_or_university}>
            <Input
              id="e-school"
              value={form.school_or_university}
              onChange={(e) => setForm({ ...form, school_or_university: e.target.value })}
              invalid={!!fieldErrors.school_or_university}
            />
          </Field>
          <Field label="Class 10 passing year" htmlFor="e-year" error={fieldErrors.passing_year}>
            <Input
              id="e-year"
              type="number"
              min={1950}
              max={2030}
              value={form.passing_year}
              onChange={(e) => setForm({ ...form, passing_year: e.target.value })}
              invalid={!!fieldErrors.passing_year}
            />
          </Field>
          <Field label="Class 10 roll / registration number" htmlFor="e-roll" error={fieldErrors.roll_number}>
            <Input
              id="e-roll"
              value={form.roll_number}
              onChange={(e) => setForm({ ...form, roll_number: e.target.value })}
              invalid={!!fieldErrors.roll_number}
            />
          </Field>
          <Field label="Class 10 result status" htmlFor="e-result" error={fieldErrors.result_status}>
            <Select
              id="e-result"
              value={form.result_status}
              onChange={(e) => setForm({ ...form, result_status: e.target.value as ResultStatusType | "" })}
            >
              <option value="">Select result</option>
              <option value="PASS">Pass</option>
              <option value="FAIL">Fail</option>
              <option value="AWAITING">Awaiting</option>
            </Select>
          </Field>
          <Field label="Percentage / CGPA (optional)" htmlFor="e-score" error={fieldErrors.percentage_or_cgpa}>
            <Input
              id="e-score"
              placeholder="e.g. 84% or 8.6 CGPA"
              value={form.percentage_or_cgpa}
              onChange={(e) => setForm({ ...form, percentage_or_cgpa: e.target.value })}
            />
          </Field>
        </div>

        <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onBack}>
              Back
            </Button>
            <Button type="button" variant="secondary" loading={saving} onClick={() => void onSave(payload(), 3)}>
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
