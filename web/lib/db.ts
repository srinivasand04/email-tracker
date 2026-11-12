import "server-only";
import { Pool } from "pg";

declare global {
  // Reuse one pool across hot reloads in development
  var __emailTrackerPool: Pool | undefined;
}

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set. It is read from the repository's .env file.");
  }
  return new Pool({ connectionString, max: 3 });
}

export function db(): Pool {
  globalThis.__emailTrackerPool ??= createPool();
  return globalThis.__emailTrackerPool;
}
