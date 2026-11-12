import "server-only";
import { db } from "./db";
import { UNCLASSIFIED, isCategory } from "./categories";

export type EmailRow = {
  id: string;
  account: string;
  sender_name: string;
  sender_email: string;
  subject: string;
  summary: string | null;
  reason: string | null;
  category: string | null;
  priority: string | null;
  classified_by: string | null;
  received_at: Date;
  created_at: Date;
  gmail_link: string;
  reviewed: boolean;
};

export type Filters = {
  account?: string;
  category?: string;
  status: "unreviewed" | "reviewed" | "all";
  from?: string;
  to?: string;
  q?: string;
};

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function parseFilters(params: Record<string, string | string[] | undefined>): Filters {
  const one = (key: string) => {
    const value = params[key];
    const text = (Array.isArray(value) ? value[0] : value)?.trim();
    return text ? text : undefined;
  };
  const status = one("status");
  const category = one("category");
  const from = one("from");
  const to = one("to");
  return {
    account: one("account"),
    category: category === UNCLASSIFIED || isCategory(category) ? category : undefined,
    status: status === "reviewed" || status === "all" ? status : "unreviewed",
    from: from && DATE.test(from) ? from : undefined,
    to: to && DATE.test(to) ? to : undefined,
    q: one("q")?.slice(0, 200),
  };
}

export const EMAIL_LIMIT = 1000;

export async function listEmails(filters: Filters): Promise<EmailRow[]> {
  const where: string[] = [];
  const args: unknown[] = [];
  const arg = (value: unknown) => {
    args.push(value);
    return `$${args.length}`;
  };

  if (filters.account) where.push(`a.email = ${arg(filters.account)}`);
  if (filters.category === UNCLASSIFIED) where.push("e.category IS NULL");
  else if (filters.category) where.push(`e.category = ${arg(filters.category)}`);
  if (filters.status === "unreviewed") where.push("NOT e.reviewed");
  if (filters.status === "reviewed") where.push("e.reviewed");
  if (where.length === 0) where.push("TRUE");
  if (filters.from) where.push(`e.received_at >= ${arg(filters.from)}::date`);
  if (filters.to) where.push(`e.received_at < ${arg(filters.to)}::date + 1`);
  if (filters.q) {
    const pattern = arg(`%${filters.q.replace(/[\\%_]/g, (c) => "\\" + c)}%`);
    where.push(
      `(e.subject ILIKE ${pattern} OR e.sender_name ILIKE ${pattern} OR e.sender_email ILIKE ${pattern}` +
        ` OR e.summary ILIKE ${pattern} OR e.snippet ILIKE ${pattern})`,
    );
  }

  const { rows } = await db().query<EmailRow>(
    `SELECT e.id::text, a.email AS account, e.sender_name, e.sender_email, e.subject, e.summary,
            e.reason, e.category, e.priority, e.classified_by, e.received_at, e.created_at,
            e.gmail_link, e.reviewed
     FROM emails e JOIN accounts a ON a.id = e.account_id
     WHERE ${where.join(" AND ")}
     ORDER BY e.received_at DESC
     LIMIT ${EMAIL_LIMIT}`,
    args,
  );
  return rows;
}

export async function listAccounts(): Promise<string[]> {
  const { rows } = await db().query<{ email: string }>("SELECT email FROM accounts ORDER BY id");
  return rows.map((r) => r.email);
}

export type SyncInfo = { account: string; last_synced_at: Date | null; last_status: string | null };

export async function syncInfo(): Promise<SyncInfo[]> {
  const { rows } = await db().query<SyncInfo>(
    `SELECT a.email AS account, s.last_synced_at, s.last_status
     FROM accounts a LEFT JOIN sync_state s ON s.account_id = a.id ORDER BY a.id`,
  );
  return rows;
}

const SESSION_GAP_MINUTES = 30;

/**
 * Records this visit and returns when the previous visit ended.
 * A new "visit" starts after 30 minutes without opening the page.
 */
export async function recordVisit(): Promise<Date | null> {
  const pool = db();
  const { rows } = await pool.query<{ key: string; value: Date | null }>(
    "SELECT key, value FROM app_state WHERE key IN ('visit_current', 'visit_previous')",
  );
  const current = rows.find((r) => r.key === "visit_current")?.value ?? null;
  let previous = rows.find((r) => r.key === "visit_previous")?.value ?? null;
  const now = new Date();

  if (!current || now.getTime() - current.getTime() > SESSION_GAP_MINUTES * 60_000) {
    previous = current;
    await pool.query(
      `INSERT INTO app_state (key, value) VALUES ('visit_previous', $1)
       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`,
      [previous],
    );
  }
  await pool.query(
    `INSERT INTO app_state (key, value) VALUES ('visit_current', now())
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`,
  );
  return previous;
}
