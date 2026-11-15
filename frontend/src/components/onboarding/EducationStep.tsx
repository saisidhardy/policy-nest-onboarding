"use client";

import { ArrowLeft, ArrowRight, GraduationCap } from "lucide-react";
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
  const [page, setPage] = useState<1 | 2>(1);
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

  const handleNextPage = async () => {
    await onSave(payload(), 3);
    setPage(2);
  };

  return (
    <Card>
      <CardHeader
        title="Step 3: Education details"
        description={
          page === 1
            ? "Page 1 of 2: Highest educational qualification and institution details."
            : "Page 2 of 2: Class 10 examination board, roll number, and statutory passing status."
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
          1. Qualification Level
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
          2. Board & Marksheet Details
        </button>
      </div>

      <form
        className="space-y-5 px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (page === 1) {
            void handleNextPage();
          } else {
            void onSave(payload(), 4);
          }
        }}
        noValidate
      >
        {error && <Alert tone="error">{error}</Alert>}

        {/* Page 1: Qualification & Institution */}
        {page === 1 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Highest education level" htmlFor="e-level" error={fieldErrors.education_level}>
                <Select
                  id="e-level"
                  value={form.education_level}
                  onChange={(e) => setForm({ ...form, education_level: e.target.value as EducationLevelType | "" })}
                >
                  <option value="">Select qualification</option>
                  <option value="CLASS_10">Class 10 (Secondary School)</option>
                  <option value="CLASS_12">Class 12 (Higher Secondary)</option>
                  <option value="GRADUATE">Graduate (Bachelor&apos;s)</option>
                  <option value="POST_GRADUATE">Post-graduate (Master&apos;s)</option>
                </Select>
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
            </div>

            <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-3.5 text-xs text-blue-950 flex items-start gap-2">
              <GraduationCap className="h-4 w-4 text-blue-700 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">IRDAI Requirement: </span>
                You must have passed Class 10 (matriculation) from a recognized Central or State Board. Higher degrees are welcome but Class 10 certificate is mandatory for age & education verification.
              </div>
            </div>

            <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={onBack}>
                  <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Step 2
                </Button>
                <Button type="button" variant="ghost" loading={saving} onClick={() => void onSave(payload(), 3)}>
                  Save draft
                </Button>
              </div>
              <Button type="button" onClick={() => void handleNextPage()} loading={saving}>
                <span>Next: Board details (Page 2 of 2)</span>
                <ArrowRight className="h-4 w-4 ml-1.5" />
              </Button>
            </div>
          </div>
        )}

        {/* Page 2: Board, Roll No, Result */}
        {page === 2 && (
          <div className="space-y-4 animate-fadeIn">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Class 10 Board"
                htmlFor="e-board"
                error={fieldErrors.board_name}
                hint="e.g. CBSE, ICSE, NIOS, Maharashtra State Board"
              >
                <Input
                  id="e-board"
                  value={form.board_name}
                  onChange={(e) => setForm({ ...form, board_name: e.target.value })}
                  invalid={!!fieldErrors.board_name}
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
                  <option value="PASS">Pass (Eligible for POSP)</option>
                  <option value="FAIL">Fail (Not eligible)</option>
                  <option value="AWAITING">Awaiting result</option>
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
                <Button type="button" variant="secondary" onClick={() => setPage(1)}>
                  <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Page 1
                </Button>
                <Button type="button" variant="ghost" loading={saving} onClick={() => void onSave(payload(), 3)}>
                  Save draft
                </Button>
              </div>
              <Button type="submit" loading={saving}>
                Save & continue to Step 4
              </Button>
            </div>
          </div>
        )}
      </form>
    </Card>
  );
}
