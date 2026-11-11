"use client";

import { useState } from "react";
import { Alert, Button, Card, CardHeader, Field, Input, Select } from "@/components/ui";
import type { AccountType, ApplicationDetail } from "@/lib/types";

export function BankStep({
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
    account_holder_name: application.account_holder_name ?? application.full_name ?? "",
    bank_name: application.bank_name ?? "",
    branch_name: application.branch_name ?? "",
    ifsc_code: application.ifsc_code ?? "",
    account_number: "",
    account_type: (application.account_type ?? "SAVINGS") as AccountType,
    is_joint_account: application.is_joint_account,
    is_primary_holder: application.is_primary_holder,
  });

  const payload = () => {
    const body: Record<string, unknown> = {
      account_holder_name: form.account_holder_name || null,
      bank_name: form.bank_name || null,
      branch_name: form.branch_name || null,
      ifsc_code: form.ifsc_code ? form.ifsc_code.toUpperCase().trim() : null,
      account_type: form.account_type,
      is_joint_account: form.is_joint_account,
      is_primary_holder: form.is_primary_holder,
    };
    if (form.account_number.trim()) {
      body.account_number = form.account_number.trim();
    }
    return body;
  };

  return (
    <Card>
      <CardHeader
        title="Step 4: Bank payout details"
        description="Commission payouts must go to a bank account in your own name (joint accounts allowed only if you are the primary holder)."
      />
      <form
        className="space-y-5 px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          void onSave(payload(), 5);
        }}
        noValidate
      >
        {error && <Alert tone="error">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Account holder name" htmlFor="b-holder" error={fieldErrors.account_holder_name}>
            <Input
              id="b-holder"
              value={form.account_holder_name}
              onChange={(e) => setForm({ ...form, account_holder_name: e.target.value })}
              invalid={!!fieldErrors.account_holder_name}
            />
          </Field>
          <Field label="Bank name" htmlFor="b-bank" error={fieldErrors.bank_name}>
            <Input
              id="b-bank"
              value={form.bank_name}
              onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
              invalid={!!fieldErrors.bank_name}
            />
          </Field>
          <Field label="Branch name (optional)" htmlFor="b-branch" error={fieldErrors.branch_name}>
            <Input
              id="b-branch"
              value={form.branch_name}
              onChange={(e) => setForm({ ...form, branch_name: e.target.value })}
            />
          </Field>
          <Field label="IFSC code" htmlFor="b-ifsc" error={fieldErrors.ifsc_code} hint="11 characters, 5th character is 0 (e.g. HDFC0000240)">
            <Input
              id="b-ifsc"
              maxLength={11}
              className="uppercase"
              value={form.ifsc_code}
              onChange={(e) => setForm({ ...form, ifsc_code: e.target.value.toUpperCase() })}
              invalid={!!fieldErrors.ifsc_code}
            />
          </Field>
          <Field
            label="Bank account number"
            htmlFor="b-acct"
            error={fieldErrors.account_number}
            hint={
              application.has_account_number
                ? `Saved account: ${application.account_number_masked}. Leave blank to keep it, or enter a new number to update.`
                : "9 to 18 digits; encrypted at rest on the server."
            }
          >
            <Input
              id="b-acct"
              inputMode="numeric"
              placeholder={application.account_number_masked ?? "Enter bank account number"}
              value={form.account_number}
              onChange={(e) => setForm({ ...form, account_number: e.target.value })}
              invalid={!!fieldErrors.account_number}
            />
          </Field>
          <Field label="Account type" htmlFor="b-type" error={fieldErrors.account_type}>
            <Select
              id="b-type"
              value={form.account_type}
              onChange={(e) => setForm({ ...form, account_type: e.target.value as AccountType })}
            >
              <option value="SAVINGS">Savings</option>
              <option value="CURRENT">Current</option>
            </Select>
          </Field>
        </div>

        <div className="space-y-2 rounded-lg border border-slate-100 bg-slate-50 p-4">
          <label className="flex items-center gap-2.5 text-sm text-slate-800">
            <input
              type="checkbox"
              checked={form.is_joint_account}
              onChange={(e) => setForm({ ...form, is_joint_account: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-brand-700"
            />
            This is a joint bank account
          </label>
          {form.is_joint_account && (
            <label className="flex items-center gap-2.5 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={form.is_primary_holder}
                onChange={(e) => setForm({ ...form, is_primary_holder: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-brand-700"
              />
              I confirm that I am the primary (first) account holder
            </label>
          )}
        </div>

        <div className="flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onBack}>
              Back
            </Button>
            <Button type="button" variant="secondary" loading={saving} onClick={() => void onSave(payload(), 4)}>
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
