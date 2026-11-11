import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import type { ApplicationDetail } from "@/lib/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
}));

function makeApp(overrides: Partial<ApplicationDetail> = {}): ApplicationDetail {
  return {
    id: "app-uuid-1",
    reference_code: "APP-260001",
    user_id: "user-uuid-1",
    status: "DRAFT",
    current_step: 1,
    region: null,
    sensitivity: 1,
    preferred_language: "EN",
    channel: "SELF_SERVICE",
    full_name: "Asha Verma",
    date_of_birth: null,
    gender: null,
    father_or_spouse_name: null,
    mobile: "9876543210",
    email: "asha@example.com",
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
    account_holder_name: "Asha Verma",
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
    last_saved_at: "2026-11-11T12:00:00Z",
    created_at: "2026-11-11T12:00:00Z",
    updated_at: "2026-11-11T12:00:00Z",
    documents: [],
    document_history: [],
    events: [],
    completeness: {
      sections: { personal: false, address: false, education: false, bank: false, documents: false, declarations: false },
      missing_fields: ["Date of birth", "PAN number"],
      missing_documents: ["PAN_CARD", "AADHAAR_FRONT", "AADHAAR_BACK", "CLASS_10_MARKSHEET", "BANK_DOCUMENT", "APPLICANT_SELFIE"],
      uploaded_document_count: 0,
      required_document_count: 6,
      completed_sections: 0,
      total_sections: 6,
      ready_to_submit: false,
    },
    ...overrides,
  };
}

describe("OnboardingWizard", () => {
  beforeEach(() => {
    push.mockReset();
    vi.restoreAllMocks();
  });

  it("resumes at the saved step and persists personal details on save & continue", async () => {
    const initial = makeApp({ current_step: 1 });
    const updated = makeApp({ current_step: 2, pan_number: "ABCDE1234F", aadhaar_last4: "7890" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(updated), { status: 200 }));
    const onUpdated = vi.fn();

    render(<OnboardingWizard application={initial} onUpdated={onUpdated} onReload={vi.fn()} />);

    expect(screen.getByText("Step 1: Personal details")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("PAN number"), "abcde1234f");
    await userEvent.type(screen.getByLabelText("Aadhaar (last 4 digits only)"), "7890");
    await userEvent.click(screen.getByRole("button", { name: "Save & continue" }));

    await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(updated));
    expect(await screen.findByText("Step 2: Address details")).toBeInTheDocument();

    const sentBody = JSON.parse(fetchMock.mock.calls[0][1]!.body as string);
    expect(sentBody.pan_number).toBe("ABCDE1234F");
    expect(sentBody.aadhaar_last4).toBe("7890");
    expect(sentBody.current_step).toBe(2);
  });

  it("renders all 6 required document slots when resumed on step 5", () => {
    render(<OnboardingWizard application={makeApp({ current_step: 5 })} onUpdated={vi.fn()} onReload={vi.fn()} />);

    expect(screen.getByText("1. PAN Card")).toBeInTheDocument();
    expect(screen.getByText("2. Aadhaar Front")).toBeInTheDocument();
    expect(screen.getByText("3. Aadhaar Back")).toBeInTheDocument();
    expect(screen.getByText("4. Class 10 Marksheet")).toBeInTheDocument();
    expect(screen.getByText("5. Cancelled Cheque / Bank Proof")).toBeInTheDocument();
    expect(screen.getByText("6. Applicant Selfie")).toBeInTheDocument();
  });
});
