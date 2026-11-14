import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DecisionHistoryPanel } from "@/components/verification/DecisionHistoryPanel";
import type { ApplicationDecisionSummary } from "@/lib/types";

describe("DecisionHistoryPanel", () => {
  it("renders bilingual EN/HI rework checklist and in-place correction CTA on NEEDS_MORE_INFO", () => {
    const summary: ApplicationDecisionSummary = {
      application_id: "app-1",
      application_status: "NEEDS_MORE_INFO",
      resolution_kind: "CORRECTION",
      parent_application_id: null,
      rework_count: 0,
      active_ruleset_version: "3.2.0",
      latest_execution: {
        id: "exec-1",
        application_id: "app-1",
        ruleset_id: "rs-1",
        ruleset_version: "3.2.0",
        trigger_source: "MANUAL_EVALUATE",
        triggered_by_user_id: "u-1",
        outcome: "NEEDS_MORE_INFO",
        recommended_status: "NEEDS_MORE_INFO",
        eligibility_status: "PASS",
        completeness_status: "FAIL",
        consistency_status: "PASS",
        risk_level: "LOW",
        auto_pass_eligible: false,
        requires_human_review: false,
        reason_codes: ["IMAGE_BLURRY"],
        rule_results: [
          {
            rule_id: "DOC_QUALITY_AND_OCR",
            category: "COMPLETENESS",
            name: "Document Image Quality & Classification",
            status: "FAIL",
            severity: "REWORK",
            reason_code: "IMAGE_BLURRY",
            explanation: "PAN_CARD: quality IMAGE_BLURRY",
            evidence: {},
          },
        ],
        rework_items: [
          {
            doc_type: "PAN_CARD",
            reason_code: "IMAGE_BLURRY",
            title_en: "Document unclear or blurry",
            title_hi: "दस्तावेज़ धुंधला या अस्पष्ट है",
            action_en: "Re-upload a sharp, high-contrast photo.",
            action_hi: "अच्छी रोशनी में साफ फोटो दोबारा अपलोड करें।",
          },
        ],
        risk_indicators: [],
        summary: "Consolidated single-pass rework generated (1 item(s)).",
        executed_at: "2026-11-12T10:00:00Z",
      },
      execution_history: [],
      decisions: [],
      appeals: [],
    };

    render(<DecisionHistoryPanel summary={summary} onRefresh={vi.fn()} isApplicantOwner />);

    expect(screen.getByText(/Consolidated Rework Checklist/i)).toBeInTheDocument();
    expect(screen.getByText("Document unclear or blurry")).toBeInTheDocument();
    expect(screen.getByText("दस्तावेज़ धुंधला या अस्पष्ट है")).toBeInTheDocument();
    expect(screen.getByText(/WhatsApp Candidate/i)).toBeInTheDocument();
    expect(screen.getByText(/Copy SMS/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Fix & resubmit in-place \(Correction\)/i })).toHaveAttribute(
      "href",
      "/app/onboarding/app-1?step=5",
    );
  });

  it("highlights non-auto-reject NAME_MISMATCH guardrail and preserves Appeal vs Reapply separation on REJECTED", () => {
    const summary: ApplicationDecisionSummary = {
      application_id: "app-2",
      application_status: "REJECTED",
      resolution_kind: "INITIAL",
      parent_application_id: null,
      rework_count: 1,
      active_ruleset_version: "3.2.0",
      latest_execution: {
        id: "exec-2",
        application_id: "app-2",
        ruleset_id: "rs-1",
        ruleset_version: "3.2.0",
        trigger_source: "MANUAL_EVALUATE",
        triggered_by_user_id: "u-1",
        outcome: "HUMAN_REVIEW",
        recommended_status: "IN_REVIEW",
        eligibility_status: "PASS",
        completeness_status: "PASS",
        consistency_status: "HUMAN_REVIEW",
        risk_level: "LOW",
        auto_pass_eligible: false,
        requires_human_review: true,
        reason_codes: ["NAME_MISMATCH"],
        rule_results: [
          {
            rule_id: "CONSIST_NAME_AADHAAR_FRONT",
            category: "CONSISTENCY",
            name: "8-Tier Name Match (AADHAAR_FRONT)",
            status: "HUMAN_REVIEW",
            severity: "HUMAN_ONLY",
            reason_code: "NAME_MISMATCH",
            explanation: "Flagged for mandatory human review.",
            evidence: { non_auto_reject_guardrail: true },
          },
        ],
        rework_items: [],
        risk_indicators: [],
        summary: "Routed to mandatory human review (NAME_MISMATCH).",
        executed_at: "2026-11-12T10:00:00Z",
      },
      execution_history: [],
      decisions: [],
      appeals: [],
    };

    render(<DecisionHistoryPanel summary={summary} onRefresh={vi.fn()} isApplicantOwner canDecide />);

    expect(screen.getByText(/Non-auto-reject identity guardrail active/i)).toBeInTheDocument();
    expect(screen.getByText(/Path A: File Formal Appeal/i)).toBeInTheDocument();
    expect(screen.getByText(/Path B: Start New Linked Reapplication/i)).toBeInTheDocument();
    expect(screen.getByText(/Senior Reviewer required for override/i)).toBeInTheDocument();
  });
});
