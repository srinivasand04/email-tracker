"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useRef } from "react";
import { CATEGORIES, UNCLASSIFIED } from "@/lib/categories";
import type { Filters as FilterValues } from "@/lib/queries";

export function Filters({ accounts, filters }: { accounts: string[]; filters: FilterValues }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const formRef = useRef<HTMLFormElement>(null);

  function apply() {
    const form = formRef.current;
    if (!form) return;
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form)) {
      if (typeof value === "string" && value.trim() && !(key === "status" && value === "unreviewed")) {
        params.set(key, value.trim());
      }
    }
    const query = params.toString();
    if (query !== searchParams.toString()) router.push(query ? `/?${query}` : "/");
  }

  const active = Boolean(
    filters.account || filters.category || filters.from || filters.to || filters.q || filters.status !== "unreviewed",
  );

  return (
    <form
      ref={formRef}
      className="filters"
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <label>
        <span>Account</span>
        <select name="account" defaultValue={filters.account ?? ""} onChange={apply}>
          <option value="">All accounts</option>
          {accounts.map((account) => (
            <option key={account} value={account}>
              {account}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Category</span>
        <select name="category" defaultValue={filters.category ?? ""} onChange={apply}>
          <option value="">Important (hides Everything else)</option>
          {CATEGORIES.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.label}
            </option>
          ))}
          <option value={UNCLASSIFIED}>Not classified yet</option>
        </select>
      </label>
      <label>
        <span>Show</span>
        <select name="status" defaultValue={filters.status} onChange={apply}>
          <option value="unreviewed">Not reviewed</option>
          <option value="reviewed">Reviewed</option>
          <option value="all">All</option>
        </select>
      </label>
      <label>
        <span>From</span>
        <input type="date" name="from" defaultValue={filters.from ?? ""} onChange={apply} />
      </label>
      <label>
        <span>To</span>
        <input type="date" name="to" defaultValue={filters.to ?? ""} onChange={apply} />
      </label>
      <label className="search">
        <span>Search</span>
        <input type="search" name="q" placeholder="Sender, subject, summary" defaultValue={filters.q ?? ""} />
      </label>
      <div className="filter-buttons">
        <button type="submit">Search</button>
        {active && (
          <button type="button" className="secondary" onClick={() => router.push("/")}>
            Clear
          </button>
        )}
      </div>
    </form>
  );
}
