"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/lib/db";
import { isCategory } from "@/lib/categories";

function emailId(id: string): string {
  if (!/^\d+$/.test(id)) throw new Error("Invalid email id");
  return id;
}

export async function setReviewed(id: string, reviewed: boolean): Promise<void> {
  await db().query(
    `UPDATE emails SET reviewed = $2, reviewed_at = CASE WHEN $2 THEN now() END, updated_at = now()
     WHERE id = $1`,
    [emailId(id), reviewed],
  );
  revalidatePath("/");
}

export async function setManyReviewed(ids: string[]): Promise<void> {
  const clean = ids.filter((id) => /^\d+$/.test(id));
  if (clean.length === 0) return;
  await db().query(
    `UPDATE emails SET reviewed = TRUE, reviewed_at = now(), updated_at = now()
     WHERE id = ANY($1::bigint[]) AND NOT reviewed`,
    [clean],
  );
  revalidatePath("/");
}

/** A correction from the user. classified_by = 'user' means the classifier never touches it again. */
export async function setCategory(id: string, category: string): Promise<void> {
  if (!isCategory(category)) throw new Error("Unknown category");
  await db().query(
    `UPDATE emails
     SET category = $2, classified_by = 'user', classified_at = now(), body_excerpt = NULL,
         priority = COALESCE(priority, 'medium'),
         reason = 'Set by you', updated_at = now()
     WHERE id = $1`,
    [emailId(id), category],
  );
  revalidatePath("/");
}
