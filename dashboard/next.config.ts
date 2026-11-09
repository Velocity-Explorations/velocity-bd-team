import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The container runs .next/standalone/server.js (Dockerfile). `npm run dev` is unaffected.
  output: "standalone",
  // Profile pictures are re-encoded with sharp (David, 9 Nov 2026). The build's tracing copies sharp's .node file but
  // not the libvips libraries beside it, so the whole of sharp and its @img packages go in.
  outputFileTracingIncludes: { "/**": ["./node_modules/sharp/**/*", "./node_modules/@img/**/*"] },
  // The repo's own AGENTS.md governs agents here; dashboard/README.md carries the Next.js note.
  agentRules: false,
};

export default nextConfig;
