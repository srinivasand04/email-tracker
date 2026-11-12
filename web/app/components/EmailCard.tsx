"use client";

import { useTransition } from "react";
import { setCategory, setReviewed } from "@/app/actions";
import { CATEGORIES } from "@/lib/categories";
import { LocalTime } from "./LocalTime";

export type CardEmail = {
  id: string;
  account: string;
  accountIndex: number;
  sender: string;
  senderEmail: string;
  subject: string;
  summary: string | null;
  reason: string | null;
  category: string | null;
  priority: string | null;
  classifiedBy: string | null;
  receivedAt: string;
  gmailLink: string;
  reviewed: boolean;
  isNew: boolean;
};

export function EmailCard({ email }: { email: CardEmail }) {
  const [pending, startTransition] = useTransition();
  const accountLabel = email.account.split("@")[0];

  return (
    <article className={`card${email.reviewed ? " reviewed" : ""}${pending ? " pending" : ""}`}>
      <header className="card-top">
        <span className={`badge account-${email.accountIndex % 4}`} title={email.account}>
          {accountLabel}
        </span>
        {email.priority && <span className={`badge priority-${email.priority}`}>{email.priority}</span>}
        {email.isNew && <span className="badge new">new</span>}
        <LocalTime iso={email.receivedAt} />
      </header>

      <p className="sender" title={email.senderEmail}>
        {email.sender || email.senderEmail}
      </p>
      <h3 className="subject">{email.subject || "(no subject)"}</h3>
      {email.summary && <p className="summary">{email.summary}</p>}
      {email.reason && (
        <p className="reason">
          {email.classifiedBy === "user" ? "Category set by you" : `Why: ${email.reason}`}
        </p>
      )}

      <footer className="card-actions">
        <a className="button" href={email.gmailLink} target="_blank" rel="noopener noreferrer">
          Open in Gmail
        </a>
        <button
          type="button"
          className="secondary"
          disabled={pending}
          onClick={() => startTransition(() => setReviewed(email.id, !email.reviewed))}
        >
          {email.reviewed ? "Mark not reviewed" : "Mark reviewed"}
        </button>
        <label className="category-select">
          <span className="visually-hidden">Category</span>
          <select
            value={email.category ?? ""}
            disabled={pending}
            onChange={(event) => {
              const value = event.target.value;
              if (value) startTransition(() => setCategory(email.id, value));
            }}
          >
            {!email.category && <option value="">Not classified yet</option>}
            {CATEGORIES.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.short}
              </option>
            ))}
          </select>
        </label>
      </footer>
    </article>
  );
}
