// Must match the CHECK constraint in db/migrations/001_init.sql.
// Order = display order: job-related categories always come first.
export const CATEGORIES = [
  { slug: "direct_opportunity", label: "Direct job opportunity", short: "Opportunity" },
  { slug: "application_update", label: "Application / interview update", short: "Application" },
  { slug: "company_postings", label: "Company job postings", short: "Company jobs" },
  { slug: "job_alerts", label: "Job alerts", short: "Job alerts" },
  { slug: "visa_government", label: "Visa / government", short: "Visa / gov" },
  { slug: "finance_bills", label: "Finance and bills", short: "Finance" },
  { slug: "security_account", label: "Security and account", short: "Security" },
  { slug: "personal", label: "Personal / needs reply", short: "Personal" },
  { slug: "other", label: "Everything else", short: "Other" },
] as const;

export type CategorySlug = (typeof CATEGORIES)[number]["slug"];

export const UNCLASSIFIED = "unclassified";

export function isCategory(value: string | undefined | null): value is CategorySlug {
  return CATEGORIES.some((c) => c.slug === value);
}

export function categoryLabel(slug: string | null): string {
  return CATEGORIES.find((c) => c.slug === slug)?.label ?? "Not classified yet";
}

export function categoryRank(slug: string | null): number {
  const index = CATEGORIES.findIndex((c) => c.slug === slug);
  return index === -1 ? CATEGORIES.length : index;
}

export const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

// Shown collapsed by default
export const COLLAPSED: readonly string[] = ["job_alerts"];
// Hidden unless chosen in the category filter
export const HIDDEN_BY_DEFAULT: readonly string[] = ["other"];
