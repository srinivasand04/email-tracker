"use client";

import { useEffect, useState } from "react";

const FORMAT = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

/** Formats in the viewer's own time zone and locale; the server may be elsewhere. */
export function LocalTime({ iso }: { iso: string }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => setText(FORMAT.format(new Date(iso))), [iso]);
  return <time dateTime={iso}>{text ?? iso.slice(0, 10)}</time>;
}
