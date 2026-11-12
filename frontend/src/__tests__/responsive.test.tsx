import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell, visibleNav } from "@/components/AppShell";

let mockPathname = "/app";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  api: vi.fn(async () => ({ items: [], total: 0, page: 1, page_size: 1, unread_count: 2 })),
}));

const mockAuthState = {
  me: {
    user: {
      id: "u-1",
      email: "admin@example.com",
      full_name: "Priya Admin",
      email_verified: true,
      role: { code: "ADMIN", name: "Administrator" },
    },
    permissions: [
      "profile:read",
      "users:read",
      "users:manage",
      "roles:read",
      "audit:read",
      "system:read",
      "config:manage",
    ],
  },
  logout: vi.fn(),
};

vi.mock("@/lib/auth", () => ({
  useAuth: () => mockAuthState,
}));

describe("Phase 9 Responsive Navigation & Viewport Layout", () => {
  beforeEach(() => {
    mockPathname = "/app";
  });

  function setViewport(width: number, height: number) {
    Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: width });
    Object.defineProperty(window, "innerHeight", { writable: true, configurable: true, value: height });
    window.dispatchEvent(new Event("resize"));
  }

  it("supports mobile (375px) drawer navigation open and close cleanly", async () => {
    setViewport(375, 812);
    render(
      <AppShell>
        <div>Mobile workspace body</div>
      </AppShell>,
    );

    const openBtn = screen.getByRole("button", { name: /Open menu/i });
    expect(openBtn).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Close menu/i })).not.toBeInTheDocument();

    fireEvent.click(openBtn);
    const closeBtn = await screen.findByRole("button", { name: /Close menu/i });
    expect(closeBtn).toBeInTheDocument();

    fireEvent.click(closeBtn);
    expect(screen.queryByRole("button", { name: /Close menu/i })).not.toBeInTheDocument();
  });

  it("renders tablet (768px) and desktop (1440px) shells without losing RBAC nav items", () => {
    for (const [w, h] of [
      [768, 1024],
      [1440, 900],
    ]) {
      setViewport(w, h);
      const { unmount } = render(
        <AppShell>
          <div>Viewport {w}px content</div>
        </AppShell>,
      );
      expect(screen.getByText(`Viewport ${w}px content`)).toBeInTheDocument();
      const adminItems = visibleNav(mockAuthState.me.permissions);
      expect(adminItems.some((item) => item.href === "/app/admin/integrations")).toBe(true);
      expect(adminItems.some((item) => item.href === "/app/onboarding")).toBe(false);
      unmount();
    }
  });
});
