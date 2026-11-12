import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminIntegrationsPage from "@/app/app/admin/integrations/page";
import AdminReviewersPage from "@/app/app/admin/reviewers/page";
import type { AdminConfigBundle, ReviewerWorkload, RolesMatrix } from "@/lib/types";

const mockApi = vi.fn();

vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => mockApi(...args),
  ApiError: class ApiError extends Error {
    code = "ERROR";
  },
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    can: (perm: string) => ["users:manage", "config:manage", "system:read"].includes(perm),
  }),
}));

const SAMPLE_BUNDLE: AdminConfigBundle = {
  lms: {
    lms_provider: "sandbox",
    lms_api_base_url: null,
    lms_course_code: "IRDAI-POSP-15H",
    lms_required_hours: 15,
    lms_passing_score_pct: 50,
    lms_timeout_seconds: 8,
    lms_exam_cooldown_hours: 24,
    lms_certificate_validity_years: 3,
    lms_sync_retry_base_seconds: 300,
    lms_sync_max_attempts: 5,
    has_api_key: true,
    api_key_hint: "••••9876",
    has_webhook_secret: false,
    webhook_secret_hint: null,
    source: "database",
    updated_at: "2026-11-12T10:00:00Z",
  },
  integrations: {
    ocr_provider: "local_tesseract",
    ai_provider: "local_heuristic",
    gemini_model: "gemini-3.8-flash",
    has_gemini_api_key: false,
    gemini_api_key_hint: null,
    ifsc_lookup_enabled: true,
    pan_verification_provider: "not_configured",
    bank_verification_provider: "not_configured",
    digilocker_provider: "not_configured",
    face_match_provider: "not_configured",
    source: "environment",
    updated_at: null,
  },
  platform: {
    public_app_url: "http://localhost:3000",
    require_email_verification: true,
    session_idle_minutes: 30,
    login_max_failures: 5,
    login_lockout_minutes: 15,
    max_upload_size_mb: 10,
    source: "environment",
    updated_at: null,
  },
  integrations_health: [
    {
      key: "lms",
      name: "POSP Training LMS",
      status: "CONFIGURED",
      mode: "SANDBOX",
      detail: "Sandbox active.",
    },
  ],
};

describe("Phase 7 Admin Portal", () => {
  beforeEach(() => {
    mockApi.mockReset();
  });

  it("renders masked secret hints and saves LMS configuration", async () => {
    mockApi.mockImplementation(async (path: string, opts?: { method?: string }) => {
      if (path === "/admin/config" && !opts?.method) return SAMPLE_BUNDLE;
      if (path === "/admin/config/lms" && opts?.method === "PUT") return SAMPLE_BUNDLE.lms;
      return SAMPLE_BUNDLE;
    });

    render(<AdminIntegrationsPage />);

    expect(await screen.findByText(/Integrations & platform configuration/i)).toBeInTheDocument();
    expect(screen.getByText(/Stored: ••••9876/)).toBeInTheDocument();
    expect(screen.getByText(/PostgreSQL override/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Save LMS configuration/i }));

    await waitFor(() => {
      expect(mockApi).toHaveBeenCalledWith(
        "/admin/config/lms",
        expect.objectContaining({ method: "PUT" }),
      );
    });
    expect(await screen.findByText(/Saved LMS configuration to PostgreSQL/i)).toBeInTheDocument();
  });

  it("renders reviewer workloads and disables reassign when queue is empty", async () => {
    const reviewers: ReviewerWorkload[] = [
      {
        id: "r1",
        email: "rev1@example.com",
        full_name: "Arun Menon",
        role: "REVIEWER",
        region: "SOUTH",
        clearance_level: 2,
        is_active: true,
        email_verified: true,
        active_assigned_count: 3,
        escalated_assigned_count: 1,
        decisions_made_count: 14,
        overrides_count: 2,
        corrections_requested_count: 4,
        last_login_at: null,
      },
      {
        id: "r2",
        email: "rev2@example.com",
        full_name: "Priya Nair",
        role: "SENIOR_REVIEWER",
        region: "ALL",
        clearance_level: 3,
        is_active: true,
        email_verified: true,
        active_assigned_count: 0,
        escalated_assigned_count: 0,
        decisions_made_count: 20,
        overrides_count: 5,
        corrections_requested_count: 1,
        last_login_at: null,
      },
    ];
    const matrix: RolesMatrix = {
      roles: [],
      permissions: [],
      regions: ["NORTH", "SOUTH", "EAST", "WEST", "ALL"],
    };

    mockApi.mockImplementation(async (path: string) => {
      if (path.startsWith("/admin/reviewers")) return reviewers;
      if (path === "/admin/roles") return matrix;
      return null;
    });

    render(<AdminReviewersPage />);

    expect(await screen.findByText("Arun Menon")).toBeInTheDocument();
    expect(screen.getByText("1 escalated")).toBeInTheDocument();
    const reassignButtons = screen.getAllByRole("button", { name: /Reassign/i });
    expect(reassignButtons[0]).not.toBeDisabled();
    expect(reassignButtons[1]).toBeDisabled();
  });
});
