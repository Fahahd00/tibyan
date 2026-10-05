import path from "node:path";
import type { NextConfig } from "next";

// The browser always calls same-origin /api/*; Next.js forwards it to the API gateway.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:4000";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  poweredByHeader: false,
  experimental: {
    // The /api rewrite proxy defaults to 30 s; LLM-mode answers (generation + verification) can take longer.
    proxyTimeout: 180_000,
  },
  reactStrictMode: true,
  async redirects() {
    return [{ source: "/", destination: "/ar", permanent: false }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
