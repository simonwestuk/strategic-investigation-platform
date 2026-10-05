import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the container image (see Dockerfile).
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not write AGENTS.md / CLAUDE.md into the app directory during `next dev`.
  agentRules: false,
};

export default nextConfig;
