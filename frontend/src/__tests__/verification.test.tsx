import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VerificationReportPanel } from "@/components/verification/VerificationReportPanel";
import type { ApplicationVerificationReport } from "@/lib/types";

function makeReport(overrides: Partial<ApplicationVerificationReport> = {}): ApplicationVerificationReport {
  return {
    application_id: "app-uuid-1",
    reference_code: "APP-260001",
    status: "SUBMITTED",
    extractions: [
      {
        id: "ext-pan-1",
        document_id: "doc-pan-1",
        doc_type: "PAN_CARD",
        application_id: "app-uuid-1",
        ocr_engine: "LOCAL_TESSERACT",
        ai_assistant_provider: "LOCAL_HEURISTIC",
        predicted_doc_type: "PAN_CARD",
        classification_confidence: 0.94,
        classification_match: true,
        quality_status: "OK",
        blur_score: 612.4,
        glare_ratio: 0.01,
        edge_clip_ratio: 0.02,
        face_detected: null,
        ocr_confidence: 0.89,
        raw_ocr_text_masked: "INCOME TAX DEPARTMENT ABCPD1234F ASHA VERMA",
        extracted_fields: { pan_number: "ABCPD1234F", full_name: "ASHA K VERMA" },
        missing_fields: ["dob"],
        ai_explanation: "PAN layout detected cleanly; DOB missing from cropped scan.",
        aadhaar_masked_applied: false,
        has_redacted_image: false,
        reviewer_corrected_fields: null,
        effective_fields: { pan_number: "ABCPD1234F", full_name: "ASHA K VERMA" },
        corrected_by_user_id: null,
        corrected_at: null,
        processed_at: "2026-11-12T08:00:00Z",
      },
      {
        id: "ext-aadhaar-1",
        document_id: "doc-aadhaar-1",
        doc_type: "AADHAAR_FRONT",
        application_id: "app-uuid-1",
        ocr_engine: "LOCAL_TESSERACT",
        ai_assistant_provider: "LOCAL_HEURISTIC",
        predicted_doc_type: "AADHAAR_FRONT",
        classification_confidence: 0.91,
        classification_match: true,
        quality_status: "IMAGE_BLURRY",
        blur_score: 28.5,
        glare_ratio: 0.02,
        edge_clip_ratio: 0.01,
        face_detected: null,
        ocr_confidence: 0.62,
        raw_ocr_text_masked: "UIDAI XXXX-XXXX-9012",
        extracted_fields: { aadhaar_last4: "9012" },
        missing_fields: ["full_name", "dob"],
        ai_explanation: "Aadhaar number masked cleanly; scan sharpness below threshold.",
        aadhaar_masked_applied: true,
        has_redacted_image: true,
        reviewer_corrected_fields: null,
        effective_fields: { aadhaar_last4: "9012" },
        corrected_by_user_id: null,
        corrected_at: null,
        processed_at: "2026-11-12T08:00:00Z",
      },
    ],
    checks: [
      {
        id: "chk-1",
        application_id: "app-uuid-1",
        check_type: "PAN_FORMAT",
        target_doc_type: "PAN_CARD",
        status: "PASSED",
        origin: "DETERMINISTIC_RULE",
        provider_name: "policynest_rules",
        provider_reference: null,
        is_simulated: false,
        confidence: 1.0,
        details: { holder_type: "P" },
        explanation: "PAN format and individual holder code ('P') verified.",
        checked_at: "2026-11-12T08:00:00Z",
      },
      {
        id: "chk-2",
        application_id: "app-uuid-1",
        check_type: "EXTERNAL_PAN",
        target_doc_type: "PAN_CARD",
        status: "NOT_CONFIGURED",
        origin: "UNCONFIGURED",
        provider_name: "pan_verification",
        provider_reference: null,
        is_simulated: false,
        confidence: null,
        details: {},
        explanation: "Authorized PAN registry provider is not configured.",
        checked_at: "2026-11-12T08:00:00Z",
      },
    ],
    corrections: [],
    summary: {
      documents_processed: 2,
      quality_passed: 1,
      quality_warn: 0,
      quality_failed: 1,
      checks_passed: 1,
      checks_warn: 0,
      checks_needs_info: 0,
      checks_failed: 0,
      checks_not_configured: 1,
      advisory_note: "OCR and AI outputs assist extraction only.",
    },
    ...overrides,
  };
}

describe("VerificationReportPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
    };
  });

  it("renders quality flags, Aadhaar masking, provenance labels, and governance notice", () => {
    render(<VerificationReportPanel report={makeReport()} />);

    expect(screen.getByText("Quality OK")).toBeInTheDocument();
    expect(screen.getByText("Too blurry")).toBeInTheDocument();
    expect(screen.getByText("Aadhaar masked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View redacted Aadhaar/i })).toBeInTheDocument();
    expect(screen.getByText(/Origin: Deterministic rule/)).toBeInTheDocument();
    expect(screen.getByText(/Origin: Adapter not configured/)).toBeInTheDocument();
    expect(screen.getByText(/never auto-approve or reject/i)).toBeInTheDocument();
  });

  it("validates 12-digit Aadhaar prohibition and submits reviewer field correction", async () => {
    const baseReport = makeReport();
    const updatedReport = makeReport({
      corrections: [
        {
          id: "corr-1",
          extraction_id: "ext-pan-1",
          application_id: "app-uuid-1",
          document_id: "doc-pan-1",
          field_name: "full_name",
          old_value: "ASHA K VERMA",
          new_value: "ASHA VERMA",
          reason: "Confirmed directly on uploaded PAN image",
          corrected_by_user_id: "rev-1",
          created_at: "2026-11-12T08:05:00Z",
        },
      ],
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(updatedReport), { status: 200 }));
    const onReportChange = vi.fn();

    render(<VerificationReportPanel report={baseReport} onReportChange={onReportChange} canCorrectFields />);

    const correctBtns = screen.getAllByRole("button", { name: /Correct fields/i });
    await userEvent.click(correctBtns[0]);

    const valInput = screen.getByLabelText("Corrected value");
    const reasonInput = screen.getByLabelText("Audit reason");

    // Client-side guard against typing 12-digit Aadhaar numbers
    await userEvent.clear(valInput);
    await userEvent.type(valInput, "4812 9304 9012");
    await userEvent.type(reasonInput, "Testing prohibition");
    await userEvent.click(screen.getByRole("button", { name: /Save correction/i }));
    expect(await screen.findByText(/Never enter a 12-digit Aadhaar number/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    // Valid reviewer correction
    await userEvent.clear(valInput);
    await userEvent.type(valInput, "ASHA VERMA");
    await userEvent.clear(reasonInput);
    await userEvent.type(reasonInput, "Confirmed directly on uploaded PAN image");
    await userEvent.click(screen.getByRole("button", { name: /Save correction/i }));

    await waitFor(() => expect(onReportChange).toHaveBeenCalledWith(updatedReport));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/applications/app-uuid-1/documents/doc-pan-1/fields");
    expect(init?.method).toBe("PATCH");
  });
});
