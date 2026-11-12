import { Suspense } from "react";
import Link from "next/link";
import { EmailCard, type CardEmail } from "./components/EmailCard";
import { Filters } from "./components/Filters";
import { LocalTime } from "./components/LocalTime";
import { MarkGroupReviewed } from "./components/MarkGroupReviewed";
import {
  CATEGORIES,
  COLLAPSED,
  IMPORTANT_CATEGORIES,
  PRIORITY_RANK,
  UNCLASSIFIED,
  categoryLabel,
  categoryRank,
} from "@/lib/categories";
import {
  EMAIL_LIMIT,
  listAccounts,
  listEmails,
  parseFilters,
  recordVisit,
  syncInfo,
  type EmailRow,
  type Filters as FilterValues,
} from "@/lib/queries";

export const dynamic = "force-dynamic";

type Group = { category: string | null; emails: CardEmail[] };

function isImportant(email: CardEmail): boolean {
  return email.priority === "high" || IMPORTANT_CATEGORIES.includes(email.category ?? "");
}

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
      // new mail first, then by priority, then newest
      emails: group.emails.sort(
        (a, b) =>
          Number(b.isNew) - Number(a.isNew) ||
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

function Section({
  title,
  hint,
  groups,
  collapse,
}: {
  title: string;
  hint: string;
  groups: Group[];
  collapse: readonly string[];
}) {
  if (groups.length === 0) return null;
  const total = groups.reduce((n, g) => n + g.emails.length, 0);
  return (
    <section className="section">
      <h2>
        {title} <span className="count">{total}</span>
      </h2>
      <p className="hint">{hint}</p>
      {groups.map((group) => {
        const unreviewed = group.emails.filter((e) => !e.reviewed).map((e) => e.id);
        const fresh = group.emails.filter((e) => e.isNew).length;
        return (
          <details
            key={group.category ?? "none"}
            className="group"
            open={!collapse.includes(group.category ?? "")}
          >
            <summary>
              <span className="group-title">{categoryLabel(group.category)}</span>
              <span className="count">{group.emails.length}</span>
              {fresh > 0 && <span className="badge new">{fresh} new</span>}
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

function CategoryChips({ cards, filters }: { cards: CardEmail[]; filters: FilterValues }) {
  const counts = new Map<string, number>();
  for (const card of cards) {
    const key = card.category ?? UNCLASSIFIED;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const chips = [
    ...CATEGORIES.map((c) => ({ slug: c.slug as string, label: c.short })),
    { slug: UNCLASSIFIED, label: "Not classified" },
  ].filter((c) => counts.has(c.slug));
  if (chips.length === 0 || filters.category) return null;

  const href = (slug: string) => {
    const params = new URLSearchParams();
    if (filters.account) params.set("account", filters.account);
    if (filters.status !== "unreviewed") params.set("status", filters.status);
    if (filters.from) params.set("from", filters.from);
    if (filters.to) params.set("to", filters.to);
    if (filters.q) params.set("q", filters.q);
    params.set("category", slug);
    return `/?${params}`;
  };

  return (
    <nav className="chips" aria-label="Counts by category">
      {chips.map((chip) => (
        <Link key={chip.slug} href={href(chip.slug)} className="chip">
          {chip.label} <span className="count">{counts.get(chip.slug)}</span>
        </Link>
      ))}
    </nav>
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
  const important = cards.filter(isImportant);
  const rest = cards.filter((c) => !isImportant(c));
  const newCount = cards.filter((c) => c.isNew).length;
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
          {previousVisit && ` · ${newCount} new since your last visit`}
          {failing.length > 0 && <span className="warning"> · Sync failing for {failing.join(", ")}</span>}
        </p>
      </header>

      <Suspense>
        <Filters accounts={accounts} filters={filters} />
      </Suspense>
      <CategoryChips cards={cards} filters={filters} />

      {cards.length === 0 && <p className="empty">Nothing here. You are all caught up.</p>}
      {rows.length === EMAIL_LIMIT && (
        <p className="meta">Showing the newest {EMAIL_LIMIT}. Narrow the filters to see older mail.</p>
      )}

      <Section
        title="Most important"
        hint="Recruiters, applications and interviews, and anything marked high priority."
        groups={groupByCategory(important)}
        collapse={[]}
      />
      <Section
        title="Everything else"
        hint="Check the category of each one; change it with the dropdown if it is wrong."
        groups={groupByCategory(rest)}
        collapse={COLLAPSED}
      />
    </main>
  );
}
