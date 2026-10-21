import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The container runs .next/standalone/server.js (Dockerfile). `npm run dev` is unaffected.
  output: "standalone",
  // The repo's own AGENTS.md governs agents here; dashboard/README.md carries the Next.js note.
  agentRules: false,
};

export default nextConfig;
