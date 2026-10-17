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
    const isProd = process.env.NODE_ENV === "production";

    // Next.js injects inline bootstrap/hydration scripts and the theme
    // bootstrap, so script-src needs 'unsafe-inline' here. That limits how much
    // this CSP buys against XSS, but the other directives close the sinks that
    // actually get abused: injected <object>/<embed>, <base> hijacking, framing
    // and form exfiltration. Moving to per-request nonces needs browser
    // testing, so it is deliberately not attempted blind.
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'self'",
      "form-action 'self'",
      // 'unsafe-eval' is only required by the dev server (Turbopack/HMR).
      `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      "connect-src 'self'",
      "manifest-src 'self'",
      "worker-src 'self'",
      // Only safe to force over TLS; it would break plain-http local dev.
      ...(isProd ? ["upgrade-insecure-requests"] : []),
    ].join("; ");

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
          { key: "Content-Security-Policy", value: csp },
          // Isolates the browsing context so a cross-origin opener cannot reach
          // this window via window.opener.
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
          // HSTS only over TLS, and only in production: sending it on plain-http
          // localhost would make the browser pin the dev origin to HTTPS.
          ...(isProd
            ? [
                {
                  key: "Strict-Transport-Security",
                  value: "max-age=31536000; includeSubDomains",
                },
              ]
            : []),
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