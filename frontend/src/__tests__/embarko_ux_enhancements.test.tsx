import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BeforeYouStartGuide } from "@/components/onboarding/BeforeYouStartGuide";
import { DocumentReadinessChecklist } from "@/components/onboarding/DocumentReadinessChecklist";
import { PhotoCoachingCard } from "@/components/onboarding/PhotoCoachingCard";
import { DocumentFeedbackCard } from "@/components/onboarding/DocumentFeedbackCard";
import { KeepTheseReadyPanel } from "@/components/onboarding/KeepTheseReadyPanel";
import { PrivacyDisclosureModal } from "@/components/compliance/PrivacyDisclosureModal";
import {
  APPLICANT_SAFE_STATUS_MAP,
  DOCUMENT_GUIDANCE_MAP,
  JOURNEY_STAGES,
} from "@/lib/documentGuidance";
import type { ApplicationDetail, ApplicationDocument } from "@/lib/types";

function mockApplication(overrides: Partial<ApplicationDetail> = {}): ApplicationDetail {
  return {
    id: "app-test-123",
    reference_code: "APP-2026-TEST",
    user_id: "user-1",
    status: "DRAFT",
    current_step: 1,
    region: "WEST",
    sensitivity: 1,
    preferred_language: "EN",
    channel: "SELF_SERVICE",
    full_name: "Rahul Sharma",
    date_of_birth: "1994-08-15",
    gender: "MALE",
    father_or_spouse_name: "Suresh Sharma",
    mobile: "9876543210",
    email: "rahul@example.com",
    pan_number: "ABCPS1234F",
    aadhaar_last4: "4321",
    address_line1: "123 MG Road",
    address_line2: null,
    city: "Mumbai",
    district: "Mumbai Suburban",
    state: "Maharashtra",
    pincode: "400001",
    same_as_permanent: true,
    permanent_address_line1: null,
    permanent_address_line2: null,
    permanent_city: null,
    permanent_state: null,
    permanent_pincode: null,
    education_level: "CLASS_10",
    board_name: "Maharashtra State Board",
    school_or_university: "St. Xavier's",
    passing_year: 2010,
    roll_number: "MSB-890123",
    result_status: "PASS",
    percentage_or_cgpa: "78%",
    account_holder_name: "Rahul Sharma",
    bank_name: "State Bank of India",
    branch_name: "Fort",
    ifsc_code: "SBIN0000691",
    account_number_last4: "5678",
    account_number_masked: "XXXXXXXXXX5678",
    has_account_number: true,
    account_type: "SAVINGS",
    is_joint_account: false,
    is_primary_holder: true,
    consent_terms: true,
    consent_kyc_processing: true,
    declaration_no_other_posp: true,
    declared_at: "2026-11-15T12:00:00Z",
    submitted_at: null,
    last_saved_at: "2026-11-15T12:00:00Z",
    created_at: "2026-11-15T10:00:00Z",
    updated_at: "2026-11-15T12:00:00Z",
    documents: [],
    document_history: [],
    events: [],
    completeness: {
      sections: { personal: true, address: true, education: true, bank: true, documents: false, declarations: false },
      missing_fields: [],
      missing_documents: ["PAN_CARD", "AADHAAR_FRONT", "AADHAAR_BACK", "CLASS_10_MARKSHEET", "BANK_DOCUMENT", "APPLICANT_SELFIE"],
      uploaded_document_count: 0,
      required_document_count: 6,
      completed_sections: 4,
      total_sections: 6,
      ready_to_submit: false,
    },
    ...overrides,
  };
}

describe("Embarko UX Enhancements & Preventative Guidance Suite", () => {
  // Test 1 & 2 & 3: Before You Start Preparation Guide
  describe("Workstream A: BeforeYouStartGuide", () => {
    it("renders the 6 required documents, progressive disclosure tabs, and start CTA", async () => {
      const onStart = vi.fn();
      render(<BeforeYouStartGuide application={mockApplication()} onStartOrResume={onStart} />);

      expect(screen.getByText("Get ready for your POSP onboarding")).toBeInTheDocument();
      expect(screen.getByText("Estimated time: ~15 mins")).toBeInTheDocument();
      expect(screen.getByText("Autosaves across devices")).toBeInTheDocument();

      // Check all 6 documents are listed
      expect(screen.getByText("PAN Card")).toBeInTheDocument();
      expect(screen.getByText("Aadhaar Front")).toBeInTheDocument();
      expect(screen.getByText("Aadhaar Back")).toBeInTheDocument();
      expect(screen.getByText("Class 10 Certificate")).toBeInTheDocument();
      expect(screen.getByText("Bank Proof")).toBeInTheDocument();
      expect(screen.getByText("Selfie Portrait")).toBeInTheDocument();

      // Click Start Application
      const startBtn = screen.getByRole("button", { name: /Start Application|Continue to Application/i });
      await userEvent.click(startBtn);
      expect(onStart).toHaveBeenCalled();
    });

    it("supports switching tabs to 'How Onboarding Works' and 'Privacy & Saving Guarantee'", async () => {
      render(<BeforeYouStartGuide application={mockApplication()} onStartOrResume={vi.fn()} />);

      // Switch to How Onboarding Works
      await userEvent.click(screen.getByRole("button", { name: "2. How Onboarding Works" }));
      expect(screen.getByText("The 6-stage certification journey")).toBeInTheDocument();
      expect(screen.getByText("Your details")).toBeInTheDocument();
      expect(screen.getByText("Certificate")).toBeInTheDocument();

      // Switch to Privacy & Saving Guarantee
      await userEvent.click(screen.getByRole("button", { name: "3. Privacy & Saving Guarantee" }));
      expect(screen.getByText("How your data is protected")).toBeInTheDocument();
      expect(screen.getByText("Aadhaar Data Minimization")).toBeInTheDocument();
      expect(screen.getByText("AES-256 Storage & Signed URLs")).toBeInTheDocument();
      expect(screen.getByText("AI Copilot Privacy Boundary")).toBeInTheDocument();
    });
  });

  // Test 4 & 5: Centralized Document Guidance & Photo Coaching
  describe("Workstream C & D: Centralized Document Guidance & Photo Coaching", () => {
    it("provides comprehensive typed requirements for all 6 documents", () => {
      const docTypes = Object.keys(DOCUMENT_GUIDANCE_MAP);
      expect(docTypes).toHaveLength(6);

      // Verify PAN requirements
      const pan = DOCUMENT_GUIDANCE_MAP.PAN_CARD;
      expect(pan.applicantLabel).toContain("Permanent Account Number");
      expect(pan.mustShow.length).toBeGreaterThan(3);
      expect(pan.photoGuidance.length).toBeGreaterThan(2);
      expect(pan.acceptedFormats).toContain("PDF");
      expect(pan.acceptedFormats).toContain("JPG");

      // Verify Aadhaar masking guidance
      const aadhaarFront = DOCUMENT_GUIDANCE_MAP.AADHAAR_FRONT;
      expect(aadhaarFront.privacyNotes.join(" ")).toContain("masks the first 8 digits");
    });

    it("renders DocumentReadinessChecklist with all 6 items and expands photography guidance on click", async () => {
      render(<DocumentReadinessChecklist documents={[]} showExpandableGuidance={true} />);
      expect(screen.getByText("PAN Card")).toBeInTheDocument();
      expect(screen.getByText("Aadhaar Front")).toBeInTheDocument();

      // Expand first document guidance
      const toggleBtn = screen.getByLabelText("Toggle guidance for PAN Card");
      await userEvent.click(toggleBtn);

      expect(screen.getByText("Why this is required:")).toBeInTheDocument();
      expect(screen.getByText("What must be visible:")).toBeInTheDocument();
      expect(screen.getByText("Photography coaching:")).toBeInTheDocument();
    });

    it("renders PhotoCoachingCard with 4 key coaching rules and document-specific tips", () => {
      render(<PhotoCoachingCard docType="PAN_CARD" />);
      expect(screen.getByText(/Good photos pass first time/i)).toBeInTheDocument();
      expect(screen.getByText("1. Bright Daylight")).toBeInTheDocument();
      expect(screen.getByText("2. Flash OFF")).toBeInTheDocument();
      expect(screen.getByText("3. All 4 Corners")).toBeInTheDocument();
      expect(screen.getByText("4. Flat & Clear")).toBeInTheDocument();
    });
  });

  // Test 6 & 7: Immediate Document Feedback & Human Review States
  describe("Workstream E & K: Immediate Document Feedback & Plain-Language Human Review", () => {
    it("renders structured correction feedback card on image quality failure", () => {
      const onFix = vi.fn();
      render(
        <DocumentFeedbackCard
          docType="PAN_CARD"
          qualityStatus="IMAGE_GLARE"
          onUploadBetterImage={onFix}
        />
      );

      expect(screen.getByText("PAN Card needs a clearer image")).toBeInTheDocument();
      expect(screen.getByText("What we found:")).toBeInTheDocument();
      expect(screen.getByText("Why this matters:")).toBeInTheDocument();
      expect(screen.getByText("How to fix it:")).toBeInTheDocument();
      expect(screen.getByText(/Turn flash OFF on your camera/i)).toBeInTheDocument();

      const uploadBetterBtn = screen.getByRole("button", { name: /Upload a better image/i });
      uploadBetterBtn.click();
      expect(onFix).toHaveBeenCalled();
    });

    it("renders reassuring human review state without technical error jargon", () => {
      render(
        <DocumentFeedbackCard
          docType="CLASS_10_MARKSHEET"
          uploadState="HUMAN_REVIEW"
        />
      );

      expect(screen.getByText("Sent to a reviewer")).toBeInTheDocument();
      expect(screen.getByText(/You do not need to do anything right now/i)).toBeInTheDocument();
      expect(screen.getByText(/within 24–48 hours/i)).toBeInTheDocument();
    });
  });

  // Test 8: Contextual "Keep These Ready" Side Panel
  describe("Workstream I: Contextual Keep These Ready Panel", () => {
    it("displays the 6 documents and their live readiness states", () => {
      const docs: ApplicationDocument[] = [
        {
          id: "doc-1",
          application_id: "app-1",
          doc_type: "PAN_CARD",
          version: 1,
          is_current: true,
          status: "VERIFIED",
          original_filename: "pan.jpg",
          content_type: "image/jpeg",
          file_size_bytes: 500000,
          sha256_hash: "abcdef123456",
          storage_provider: "s3",
          notes: null,
          created_at: "2026-11-15T12:00:00Z",
          updated_at: "2026-11-15T12:00:00Z",
        },
      ];

      render(<KeepTheseReadyPanel currentStep={2} documents={docs} />);

      expect(screen.getByText("Keep these ready")).toBeInTheDocument();
      expect(screen.getByText("1 of 6 documents uploaded")).toBeInTheDocument();
      expect(screen.getByText("Verified automatically")).toBeInTheDocument();
      expect(screen.getAllByText("Needed in Step 5").length).toBeGreaterThan(0);
    });
  });

  // Test 9: Plain-Language Status & Journey Mapping
  describe("Workstream F & S: Plain-Language Status & 6-Stage Journey Mapping", () => {
    it("maps all statutory status codes to applicant-safe labels and next-step actions", () => {
      expect(APPLICANT_SAFE_STATUS_MAP.DRAFT.applicantLabel).toBe("Application in progress");
      expect(APPLICANT_SAFE_STATUS_MAP.SUBMITTED.applicantLabel).toBe("Application submitted");
      expect(APPLICANT_SAFE_STATUS_MAP.IN_REVIEW.applicantLabel).toBe("Sent to a reviewer");
      expect(APPLICANT_SAFE_STATUS_MAP.NEEDS_MORE_INFO.applicantLabel).toBe("Correction required");
      expect(APPLICANT_SAFE_STATUS_MAP.KYC_APPROVED.applicantLabel).toBe("Verified automatically");
      expect(APPLICANT_SAFE_STATUS_MAP.CERTIFIED.applicantLabel).toBe("Certified POSP Agent");

      // Verify the 6 journey stages
      expect(JOURNEY_STAGES).toHaveLength(6);
      expect(JOURNEY_STAGES.map((s) => s.applicantLabel)).toEqual([
        "Your details",
        "Documents",
        "Verification",
        "Training",
        "Exam",
        "Certificate",
      ]);
    });
  });

  // Test 10: Privacy Disclosure Experience
  describe("Workstream J: Real Railway Privacy Disclosure Modal", () => {
    it("renders modal with AES-256, UIDAI Aadhaar masking, and AI Copilot boundary disclosures", () => {
      const onClose = vi.fn();
      render(<PrivacyDisclosureModal isOpen={true} onClose={onClose} />);

      expect(screen.getByText("Privacy, Security & Data Protection")).toBeInTheDocument();
      expect(screen.getByText("How your documents are stored and encrypted")).toBeInTheDocument();
      expect(screen.getByText("Aadhaar data minimization and masking")).toBeInTheDocument();
      expect(screen.getByText("How AI assistance handles your information")).toBeInTheDocument();

      const btn = screen.getByRole("button", { name: "I understand" });
      btn.click();
      expect(onClose).toHaveBeenCalled();
    });
  });
});
