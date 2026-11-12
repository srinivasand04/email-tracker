"use client";

import { useTransition } from "react";
import { setManyReviewed } from "@/app/actions";

export function MarkGroupReviewed({ ids }: { ids: string[] }) {
  const [pending, startTransition] = useTransition();
  if (ids.length === 0) return null;
  return (
    <button
      type="button"
      className="link-button"
      disabled={pending}
      onClick={(event) => {
        event.preventDefault();
        startTransition(() => setManyReviewed(ids));
      }}
    >
      {pending ? "Saving..." : `Mark ${ids.length} reviewed`}
    </button>
  );
}
