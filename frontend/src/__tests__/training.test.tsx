import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TrainingStatusPanel } from "@/components/training/TrainingStatusPanel";

const mockApi = vi.fn();
vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => mockApi(...args),
  ApiError: class ApiError extends Error {},
}));

const baseRecord = {
  id: "tr-1",
  application_id: "app-1",
  reference_code: "APP-260001",
  applicant_name: "Kavita Nair",
  application_status: "KYC_APPROVED",
  eligibility_status: "ELIGIBLE",
  eligibility_reason: "KYC approved.",
  lms_provider: "not_configured",
  is_simulated: false,
  external_enrollment_id: null,
  lms_launch_url: null,
  enrollment_status: "NOT_ENROLLED",
  required_hours: 15,
  completed_hours: 0,
  progress_pct: 0,
  module_progress: [
    { code: "MOD-1", title: "Fundamentals", required_hours: 2.5, logged_hours: 0, completed: false },
  ],
  enrolled_at: null,
  started_at: null,
  completed_at: null,
  exam_status: "NOT_ELIGIBLE",
  exam_score_pct: null,
  exam_attempts: 0,
  last_exam_at: null,
  next_exam_eligible_at: null,
  certification_status: "NOT_CERTIFIED",
  certificate_number: null,
  certified_at: null,
  certificate_valid_until: null,
  sync_status: "IDLE",
  sync_attempts: 0,
  max_sync_attempts: 5,
  last_sync_at: null,
  next_retry_at: null,
  last_error_code: null,
  last_error_message: null,
  updated_at: "2026-11-12T10:00:00Z",
  adapter_status: {
    key: "lms",
    name: "LMS training & certification sync",
    provider: "not_configured",
    status: "NOT_CONFIGURED",
    mode: "NONE",
    webhook_configured: false,
    detail: "External LMS URL and credentials are not configured.",
  },
  sync_logs: [],
};

describe("TrainingStatusPanel", () => {
  beforeEach(() => {
    mockApi.mockReset();
  });

  it("discloses unconfigured LMS adapter status without fabricating certification", async () => {
    mockApi.mockResolvedValueOnce(baseRecord);

    render(<TrainingStatusPanel applicationId="app-1" />);

    expect(await screen.findByText(/LMS Not Configured/i)).toBeInTheDocument();
    expect(screen.getByText(/External LMS URL and credentials are not configured/i)).toBeInTheDocument();
    expect(screen.queryByText(/Non-Production Sandbox Controls/i)).not.toBeInTheDocument();
  });

  it("displays retry error state and triggers retry endpoint when requested", async () => {
    const failedRecord = {
      ...baseRecord,
      lms_provider: "http_api",
      external_enrollment_id: "EXT-99",
      enrollment_status: "IN_PROGRESS",
      completed_hours: 7.5,
      progress_pct: 50,
      sync_status: "RETRY_PENDING",
      sync_attempts: 2,
      last_error_code: "LMS_HTTP_503",
      last_error_message: "External LMS returned HTTP 503.",
      adapter_status: {
        ...baseRecord.adapter_status,
        provider: "http_api",
        status: "CONFIGURED",
        mode: "LIVE",
        detail: "External LMS REST adapter configured.",
      },
    };
    const recoveredRecord = {
      ...failedRecord,
      sync_status: "SYNCED",
      sync_attempts: 0,
      last_error_code: null,
      last_error_message: null,
    };

    mockApi.mockResolvedValueOnce(failedRecord).mockResolvedValueOnce(recoveredRecord);

    render(<TrainingStatusPanel applicationId="app-1" />);

    expect(await screen.findByText(/LMS_HTTP_503/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Retry Failed Sync/i }));

    await waitFor(() => {
      expect(mockApi).toHaveBeenLastCalledWith("/applications/app-1/training/retry", { method: "POST" });
    });
  });
});
