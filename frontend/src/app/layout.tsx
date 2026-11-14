import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { DemoPersonaSwitcher } from "@/components/DemoPersonaSwitcher";
import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { AuthProvider } from "@/lib/auth";
import { ClerkBridge } from "@/lib/ClerkBridge";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const viewport: Viewport = {
  themeColor: "#102C57",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: { default: "PolicyNest", template: "%s · PolicyNest" },
  description: "PolicyNest POSP onboarding platform",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <ClerkProvider
          publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "pk_test_ZXhjaXRpbmctbGFtcHJleS00NzY0LmNsZXJrLmFjY291bnRzLmRldiQ"}
        >
          <AuthProvider>
            <ClerkBridge />
            <I18nProvider>
              <ServiceWorkerRegistration />
              {children}
              <DemoPersonaSwitcher />
            </I18nProvider>
          </AuthProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}