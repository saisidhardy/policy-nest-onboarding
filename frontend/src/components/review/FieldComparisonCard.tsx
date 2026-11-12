"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge, Card, CardHeader } from "@/components/ui";
import type { ApplicationDetail, ApplicationVerificationReport } from "@/lib/types";

interface ComparisonRow {
  label: string;
  submitted: string | null;
  sourceLabel: string;
  extracted: string | null;
}

function normVal(v: string | null | undefined): string {
  return (v ?? "").trim().toUpperCase().replace(/\s+/g, " ");
}

export function FieldComparisonCard({
  application,
  report,
}: {
  application: ApplicationDetail;
  report: ApplicationVerificationReport | null;
}) {
  const byDoc = new Map((report?.extractions ?? []).map((e) => [e.doc_type, e.effective_fields ?? {}]));
  const pan = byDoc.get("PAN_CARD") ?? {};
  const aadhaarF = byDoc.get("AADHAAR_FRONT") ?? {};
  const marksheet = byDoc.get("CLASS_10_MARKSHEET") ?? {};
  const bank = byDoc.get("BANK_DOCUMENT") ?? {};

  const rows: ComparisonRow[] = [
    { label: "Full name (vs PAN)", submitted: application.full_name, sourceLabel: "PAN_CARD", extracted: pan.full_name ?? null },
    { label: "Full name (vs Aadhaar)", submitted: application.full_name, sourceLabel: "AADHAAR_FRONT", extracted: aadhaarF.full_name ?? null },
    { label: "Full name (vs Class 10)", submitted: application.full_name, sourceLabel: "CLASS_10_MARKSHEET", extracted: marksheet.full_name ?? null },
    { label: "Date of birth (vs PAN)", submitted: application.date_of_birth, sourceLabel: "PAN_CARD", extracted: pan.dob ?? null },
    { label: "Date of birth (vs Aadhaar)", submitted: application.date_of_birth, sourceLabel: "AADHAAR_FRONT", extracted: aadhaarF.dob ?? null },
    { label: "PAN number", submitted: application.pan_number, sourceLabel: "PAN_CARD", extracted: pan.pan_number ?? null },
    {
      label: "Aadhaar last 4",
      submitted: application.aadhaar_last4 ? `XXXX-XXXX-${application.aadhaar_last4}` : null,
      sourceLabel: "AADHAAR_FRONT",
      extracted: aadhaarF.aadhaar_last4 ? `XXXX-XXXX-${aadhaarF.aadhaar_last4}` : null,
    },
    { label: "Education board", submitted: application.board_name, sourceLabel: "CLASS_10_MARKSHEET", extracted: marksheet.board_name ?? null },
    { label: "Bank IFSC code", submitted: application.ifsc_code, sourceLabel: "BANK_DOCUMENT", extracted: bank.ifsc_code ?? null },
    { label: "Account holder name", submitted: application.account_holder_name, sourceLabel: "BANK_DOCUMENT", extracted: bank.full_name ?? null },
  ];

  return (
    <Card>
      <CardHeader
        title="Submitted vs Extracted Field Comparison"
        description="Side-by-side comparison of applicant baseline values against OCR & reviewer-corrected fields."
      />
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2.5">Field</th>
              <th className="px-4 py-2.5">Submitted Baseline</th>
              <th className="px-4 py-2.5">Extracted / Corrected</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => {
              const subN = normVal(row.submitted);
              const extN = normVal(row.extracted);
              const matched = Boolean(subN && extN && subN === extN);
              const missing = !extN;
              return (
                <tr key={row.label} className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-medium text-slate-900">
                    {row.label}
                    <span className="ml-2 text-[11px] font-normal text-slate-400">{row.sourceLabel}</span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">{row.submitted || <span className="text-slate-400">—</span>}</td>
                  <td className="px-4 py-2.5 text-slate-900">{row.extracted || <span className="text-slate-400">Not extracted</span>}</td>
                  <td className="px-4 py-2.5">
                    {missing ? (
                      <Badge tone="neutral">Missing OCR</Badge>
                    ) : matched ? (
                      <Badge tone="success">
                        <CheckCircle2 className="mr-1 h-3 w-3" /> Exact match
                      </Badge>
                    ) : (
                      <Badge tone="warning">
                        <AlertTriangle className="mr-1 h-3 w-3" /> Differs
                      </Badge>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
