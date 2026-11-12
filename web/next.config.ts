import type { NextConfig } from "next";
import path from "node:path";

// Share the repo's single .env (DATABASE_URL) instead of keeping a second copy here.
// Values already set in the environment win; nothing here is exposed to the browser.
try {
  process.loadEnvFile(path.join(__dirname, "..", ".env"));
} catch {
  // no .env: rely on the real environment (e.g. Vercel settings in Phase 4)
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
};

export default nextConfig;
