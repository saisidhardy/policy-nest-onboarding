import { existsSync, readFileSync } from "node:fs";
import type { NextConfig } from "next";

// Hosts that cannot inject build-time env vars (e.g. Embarko) get the backend address from backend-url.txt.
function backendUrl(): string {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL;
  if (existsSync("backend-url.txt")) return readFileSync("backend-url.txt", "utf8").trim();
  return "http://localhost:8000";
}

const backend = backendUrl();

const nextConfig: NextConfig = {
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health/:path*", destination: `${backend}/health/:path*` },
      { source: "/health", destination: `${backend}/health` },
    ];
  },
};

export default nextConfig;
