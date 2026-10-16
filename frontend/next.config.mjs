// ---------------------------------------------------------------------------
// Multi-stage build so `standalone` exists for the runtime image.
//
// `distDir` is the safety valve that keeps `npm run dev` and `npm run build`
// from trampling each other. Both Next commands write compiled output into
// `distDir`, so a build run while `next dev` is serving will overwrite the dev
// server's artefacts and leave it answering from stale pages that no longer
// match the source.
//
// `scripts/dev.mjs` points dev at `.next-dev`, leaving `.next` to the build.
// The production path is deliberately untouched: `next build` still writes
// `.next`, because Dockerfile and `scripts/start-standalone.mjs` both expect
// `.next/standalone` and `.next/static`.
// ---------------------------------------------------------------------------
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  distDir: process.env.NEXT_DIST_DIR || ".next",
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  // Without this, Turbopack guesses the workspace root by scanning for
  // lockfiles. A stray package-lock.json anywhere above `frontend/` makes it
  // pick the wrong root and emit a warning on every start.
  turbopack: {
    root: dirname(fileURLToPath(import.meta.url)),
  },
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [{ protocol: "https", hostname: "**" }],
    dangerouslyAllowSVG: false,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
        ],
      },
    ];
  },
  async rewrites() {
    const api = process.env.API_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default nextConfig;