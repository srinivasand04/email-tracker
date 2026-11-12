import { Suspense } from "react";
import { EmailCard, type CardEmail } from "./components/EmailCard";
import { Filters } from "./components/Filters";
import { LocalTime } from "./components/LocalTime";
import { MarkGroupReviewed } from "./components/MarkGroupReviewed";
import { COLLAPSED, PRIORITY_RANK, categoryLabel, categoryRank } from "@/lib/categories";
import {
  EMAIL_LIMIT,
  listAccounts,
  listEmails,
  parseFilters,
  recordVisit,
  syncInfo,
  type EmailRow,
} from "@/lib/queries";

export const dynamic = "force-dynamic";

type Group = { category: string | null; emails: CardEmail[] };

function groupByCategory(emails: CardEmail[]): Group[] {
  const groups = new Map<string, Group>();
  for (const email of emails) {
    const key = email.category ?? "";
    if (!groups.has(key)) groups.set(key, { category: email.category, emails: [] });
    groups.get(key)!.emails.push(email);
  }
  return [...groups.values()]
    .sort((a, b) => categoryRank(a.category) - categoryRank(b.category))
    .map((group) => ({
      ...group,
      emails: group.emails.sort(
        (a, b) =>
          (PRIORITY_RANK[a.priority ?? ""] ?? 3) - (PRIORITY_RANK[b.priority ?? ""] ?? 3) ||
          b.receivedAt.localeCompare(a.receivedAt),
      ),
    }));
}

function toCard(row: EmailRow, accounts: string[], previousVisit: Date | null): CardEmail {
  return {
    id: row.id,
    account: row.account,
    accountIndex: Math.max(0, accounts.indexOf(row.account)),
    sender: row.sender_name,
    senderEmail: row.sender_email,
    subject: row.subject,
    summary: row.summary,
    reason: row.reason,
    category: row.category,
    priority: row.priority,
    classifiedBy: row.classified_by,
    receivedAt: row.received_at.toISOString(),
    gmailLink: row.gmail_link,
    reviewed: row.reviewed,
    isNew: previousVisit !== null && row.created_at > previousVisit,
  };
}

function Section({ title, groups }: { title: string; groups: Group[] }) {
  if (groups.length === 0) return null;
  const total = groups.reduce((n, g) => n + g.emails.length, 0);
  return (
    <section className="section">
      <h2>
        {title} <span className="count">{total}</span>
      </h2>
      {groups.map((group) => {
        const unreviewed = group.emails.filter((e) => !e.reviewed).map((e) => e.id);
        return (
          <details
            key={group.category ?? "none"}
            className="group"
            open={!COLLAPSED.includes(group.category ?? "")}
          >
            <summary>
              <span className="group-title">{categoryLabel(group.category)}</span>
              <span className="count">{group.emails.length}</span>
              <MarkGroupReviewed ids={unreviewed} />
            </summary>
            <div className="cards">
              {group.emails.map((email) => (
                <EmailCard key={email.id} email={email} />
              ))}
            </div>
          </details>
        );
      })}
    </section>
  );
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filters = parseFilters(await searchParams);
  const [previousVisit, accounts, rows, syncs] = await Promise.all([
    recordVisit(),
    listAccounts(),
    listEmails(filters),
    syncInfo(),
  ]);
  const cards = rows.map((row) => toCard(row, accounts, previousVisit));
  const fresh = cards.filter((c) => c.isNew);
  const earlier = previousVisit ? cards.filter((c) => !c.isNew) : cards;
  const lastSync = syncs
    .map((s) => s.last_synced_at)
    .filter((d): d is Date => d !== null)
    .sort((a, b) => b.getTime() - a.getTime())[0];
  const failing = syncs.filter((s) => s.last_status === "error").map((s) => s.account);

  return (
    <main>
      <header className="page-header">
        <h1>Email Tracker</h1>
        <p className="meta">
          {lastSync ? (
            <>
              Last sync <LocalTime iso={lastSync.toISOString()} />
            </>
          ) : (
            "Not synced yet"
          )}
          {failing.length > 0 && <span className="warning"> · Sync failing for {failing.join(", ")}</span>}
        </p>
      </header>

      <Suspense>
        <Filters accounts={accounts} filters={filters} />
      </Suspense>

      {cards.length === 0 && <p className="empty">Nothing here. You are all caught up.</p>}
      {rows.length === EMAIL_LIMIT && (
        <p className="meta">Showing the newest {EMAIL_LIMIT}. Narrow the filters to see older mail.</p>
      )}

      <Section title="New since your last visit" groups={groupByCategory(fresh)} />
      <Section title={previousVisit ? "Earlier" : "All mail"} groups={groupByCategory(earlier)} />
    </main>
  );
}
