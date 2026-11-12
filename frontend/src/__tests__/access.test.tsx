import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { visibleNav } from "@/components/AppShell";
import { RequirePermission } from "@/components/RequirePermission";
import { passwordChecks } from "@/components/PasswordField";
import { safeNext } from "@/lib/format";
import { userStatus } from "@/lib/userStatus";
import type { AdminUser } from "@/lib/types";

const can = vi.fn();
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can }) }));

describe("navigation visibility", () => {
  it("shows applicant onboarding items and hides admin sections without admin permissions", () => {
    const applicant = visibleNav(["profile:read", "profile:update", "application:create", "application:read_own"]).map(
      (i) => i.label,
    );
    expect(applicant).toEqual(["Overview", "Onboarding", "My applications", "Notifications", "Account & security"]);
    const admin = visibleNav(["profile:read", "users:read", "roles:read", "audit:read", "system:read"]).map((i) => i.label);
    expect(admin).toContain("Users");
    expect(admin).toContain("Audit log");
    expect(admin).toContain("System status");
    expect(admin).not.toContain("Onboarding");
    expect(admin).not.toContain("Document review");
    const reviewer = visibleNav(["profile:read", "application:read_any", "application:review"]).map((i) => i.label);
    expect(reviewer).toContain("Document review");
  });
});

describe("RequirePermission", () => {
  it("renders children when permitted and access denied otherwise", () => {
    can.mockReturnValue(true);
    const { rerender } = render(<RequirePermission permission="audit:read">secret</RequirePermission>);
    expect(screen.getByText("secret")).toBeInTheDocument();
    can.mockReturnValue(false);
    rerender(<RequirePermission permission="audit:read">secret</RequirePermission>);
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(screen.getByText("Access denied")).toBeInTheDocument();
  });
});

describe("helpers", () => {
  it("only allows in-app redirect targets", () => {
    expect(safeNext("/app/admin/users")).toBe("/app/admin/users");
    expect(safeNext("https://evil.example")).toBe("/app");
    expect(safeNext("//evil.example")).toBe("/app");
    expect(safeNext(null)).toBe("/app");
  });

  it("evaluates password checks", () => {
    expect(passwordChecks("short1", 12).every((c) => c.ok)).toBe(false);
    expect(passwordChecks("LongEnoughPass1", 12).every((c) => c.ok)).toBe(true);
  });

  it("derives user status with deactivation taking precedence", () => {
    const base = { is_active: true, locked_until: null, invitation_pending: false, email_verified: true } as AdminUser;
    expect(userStatus(base).label).toBe("Active");
    expect(userStatus({ ...base, email_verified: false }).label).toBe("Unverified");
    expect(userStatus({ ...base, invitation_pending: true, email_verified: false }).label).toBe("Invited");
    expect(userStatus({ ...base, locked_until: new Date(Date.now() + 60000).toISOString() }).label).toBe("Locked");
    expect(userStatus({ ...base, is_active: false, locked_until: new Date(Date.now() + 60000).toISOString() }).label).toBe("Deactivated");
  });
});
