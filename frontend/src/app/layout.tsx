import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { AuthProvider } from "@/lib/auth";
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
        <AuthProvider>
          <I18nProvider>
            <ServiceWorkerRegistration />
            {children}
          </I18nProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
