import { describe, expect, it } from "vitest";
import { extractAutofillFromReport, normalizeDobForPatch, normalizeIndianStateForPatch } from "@/lib/autofill";
import type { ApplicationDetail, ApplicationVerificationReport } from "@/lib/types";

function emptyApplication(overrides: Partial<ApplicationDetail> = {}): ApplicationDetail {
  return {
    id: "app-1",
    reference_code: "APP-260001",
    user_id: "u-1",
    status: "DRAFT",
    current_step: 5,
    region: null,
    sensitivity: 2,
    preferred_language: "EN",
    channel: "WEB",
    full_name: null,
    date_of_birth: null,
    gender: null,
    father_or_spouse_name: null,
    mobile: null,
    email: null,
    pan_number: null,
    aadhaar_last4: null,
    address_line1: null,
    address_line2: null,
    city: null,
    district: null,
    state: null,
    pincode: null,
    same_as_permanent: true,
    permanent_address_line1: null,
    permanent_address_line2: null,
    permanent_city: null,
    permanent_state: null,
    permanent_pincode: null,
    education_level: null,
    board_name: null,
    school_or_university: null,
    passing_year: null,
    roll_number: null,
    result_status: null,
    percentage_or_cgpa: null,
    account_holder_name: null,
    bank_name: null,
    branch_name: null,
    ifsc_code: null,
    account_number_last4: null,
    account_number_masked: null,
    has_account_number: false,
    account_type: "SAVINGS",
    is_joint_account: false,
    is_primary_holder: true,
    consent_terms: false,
    consent_kyc_processing: false,
    declaration_no_other_posp: false,
    declared_at: null,
    submitted_at: null,
    last_saved_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    documents: [],
    document_history: [],
    events: [],
    completeness: {
      sections: {
        personal: false,
        address: false,
        education: false,
        bank: false,
        documents: false,
        declarations: false,
      },
      missing_fields: [],
      missing_documents: [],
      uploaded_document_count: 0,
      required_document_count: 6,
      completed_sections: 0,
      total_sections: 6,
      ready_to_submit: false,
    },
    ...overrides,
  };
}

describe("document-first autofill", () => {
  it("normalizes Indian dates and states cleanly", () => {
    expect(normalizeDobForPatch("14/05/1998")).toBe("1998-05-14");
    expect(normalizeDobForPatch("1998-05-14")).toBe("1998-05-14");
    expect(normalizeDobForPatch("31/02/1998")).toBeNull();
    expect(normalizeIndianStateForPatch("maharashtra")).toBe("Maharashtra");
    expect(normalizeIndianStateForPatch("TS")).toBe("Telangana");
  });

  it("extracts valid fields across PAN, Aadhaar, Marksheet, Bank, and IFSC lookup without overwriting existing values", () => {
    const app = emptyApplication({ full_name: "Existing User Name" });
    const report: ApplicationVerificationReport = {
      application_id: "app-1",
      reference_code: "APP-260001",
      status: "DRAFT",
      extractions: [
        {
          id: "ext-pan",
          document_id: "d-pan",
          doc_type: "PAN_CARD",
          application_id: "app-1",
          ocr_engine: "GEMINI_VISION",
          ai_assistant_provider: "gemini",
          predicted_doc_type: "PAN_CARD",
          classification_confidence: 0.99,
          classification_match: true,
          quality_status: "OK",
          blur_score: 120,
          glare_ratio: 0.01,
          edge_clip_ratio: 0,
          face_detected: true,
          ocr_confidence: 0.95,
          raw_ocr_text_masked: "",
          extracted_fields: {
            full_name: "Rohan Sharma",
            father_or_spouse_name: "Rajesh Sharma",
            date_of_birth: "12/08/1996",
            pan_number: "abcde1234f",
          },
          missing_fields: [],
          ai_explanation: null,
          aadhaar_masked_applied: false,
          has_redacted_image: false,
          reviewer_corrected_fields: null,
          effective_fields: {
            full_name: "Rohan Sharma",
            father_or_spouse_name: "Rajesh Sharma",
            date_of_birth: "12/08/1996",
            pan_number: "abcde1234f",
          },
          corrected_by_user_id: null,
          corrected_at: null,
          processed_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "ext-ab",
          document_id: "d-ab",
          doc_type: "AADHAAR_BACK",
          application_id: "app-1",
          ocr_engine: "GEMINI_VISION",
          ai_assistant_provider: "gemini",
          predicted_doc_type: "AADHAAR_BACK",
          classification_confidence: 0.98,
          classification_match: true,
          quality_status: "OK",
          blur_score: 110,
          glare_ratio: 0.01,
          edge_clip_ratio: 0,
          face_detected: false,
          ocr_confidence: 0.94,
          raw_ocr_text_masked: "",
          extracted_fields: {},
          missing_fields: [],
          ai_explanation: null,
          aadhaar_masked_applied: true,
          has_redacted_image: true,
          reviewer_corrected_fields: null,
          effective_fields: {
            aadhaar_last4: "4321",
            address_summary: "Flat 402, MG Road, Pune",
            city: "Pune",
            district: "Pune",
            state: "maharashtra",
            pincode: "411001",
          },
          corrected_by_user_id: null,
          corrected_at: null,
          processed_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "ext-bank",
          document_id: "d-bank",
          doc_type: "BANK_DOCUMENT",
          application_id: "app-1",
          ocr_engine: "GEMINI_VISION",
          ai_assistant_provider: "gemini",
          predicted_doc_type: "BANK_DOCUMENT",
          classification_confidence: 0.97,
          classification_match: true,
          quality_status: "OK",
          blur_score: 110,
          glare_ratio: 0.01,
          edge_clip_ratio: 0,
          face_detected: false,
          ocr_confidence: 0.94,
          raw_ocr_text_masked: "",
          extracted_fields: {},
          missing_fields: [],
          ai_explanation: null,
          aadhaar_masked_applied: false,
          has_redacted_image: false,
          reviewer_corrected_fields: null,
          effective_fields: {
            ifsc_code: "hdfc0000240",
            account_number: "123456789012",
          },
          corrected_by_user_id: null,
          corrected_at: null,
          processed_at: "2026-01-01T00:00:00Z",
        },
      ],
      checks: [
        {
          id: "chk-ifsc",
          application_id: "app-1",
          check_type: "EXTERNAL_IFSC_DIRECTORY",
          target_doc_type: "BANK_DOCUMENT",
          status: "PASSED",
          origin: "LIVE_API",
          provider_name: "Razorpay IFSC",
          provider_reference: "HDFC0000240",
          is_simulated: false,
          confidence: 1,
          details: { bank: "HDFC Bank", branch: "Fort Mumbai" },
          explanation: "Verified",
          checked_at: "2026-01-01T00:00:00Z",
        },
      ],
      corrections: [],
      summary: {
        documents_processed: 3,
        quality_passed: 3,
        quality_warn: 0,
        quality_failed: 0,
        checks_passed: 1,
        checks_warn: 0,
        checks_needs_info: 0,
        checks_failed: 0,
        checks_not_configured: 0,
        advisory_note: "",
      },
    };

    const result = extractAutofillFromReport(app, report);
    expect(result.patch.full_name).toBeUndefined(); // preserved existing name
    expect(result.patch.pan_number).toBe("ABCDE1234F");
    expect(result.patch.date_of_birth).toBe("1996-08-12");
    expect(result.patch.father_or_spouse_name).toBe("Rajesh Sharma");
    expect(result.patch.aadhaar_last4).toBe("4321");
    expect(result.patch.state).toBe("Maharashtra");
    expect(result.patch.pincode).toBe("411001");
    expect(result.patch.ifsc_code).toBe("HDFC0000240");
    expect(result.patch.bank_name).toBe("HDFC Bank");
    expect(result.patch.branch_name).toBe("Fort Mumbai");
    expect(result.patch.account_number).toBe("123456789012");
  });
});
