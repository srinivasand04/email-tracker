"""Turn a Gmail API message resource (format=full) into a flat record.

Pure functions, no network or database access, so they are easy to test.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr
from html.parser import HTMLParser
from urllib.parse import quote

BODY_EXCERPT_CHARS = 2000


@dataclass(frozen=True)
class ParsedEmail:
    gmail_message_id: str
    gmail_thread_id: str
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    internal_date_ms: int
    snippet: str
    body_excerpt: str
    gmail_labels: list[str]
    is_list_mail: bool
    has_attachments: bool
    gmail_link: str


def should_skip(label_ids: list[str]) -> bool:
    """Drafts, chats and mail the user sent themselves are not tracked."""
    labels = set(label_ids)
    if labels & {"DRAFT", "CHAT"}:
        return True
    return "SENT" in labels and "INBOX" not in labels


def gmail_link(account_email: str, thread_id: str) -> str:
    """Deep link that opens the thread in the right account, on phone and laptop."""
    return f"https://mail.google.com/mail/?authuser={quote(account_email)}#all/{thread_id}"


def parse_message(message: dict, account_email: str) -> ParsedEmail:
    payload = message.get("payload") or {}
    headers = _headers(payload)
    sender_name, sender_email = parseaddr(_decode_header(headers.get("from", "")))
    internal_date_ms = int(message["internalDate"])

    return ParsedEmail(
        gmail_message_id=message["id"],
        gmail_thread_id=message.get("threadId", message["id"]),
        sender_name=_clean(sender_name),
        sender_email=sender_email.strip().lower(),
        subject=_clean(_decode_header(headers.get("subject", ""))),
        received_at=datetime.fromtimestamp(internal_date_ms / 1000, tz=timezone.utc),
        internal_date_ms=internal_date_ms,
        snippet=_clean(message.get("snippet", "")),
        body_excerpt=extract_body_text(payload)[:BODY_EXCERPT_CHARS],
        gmail_labels=list(message.get("labelIds", [])),
        is_list_mail="list-unsubscribe" in headers or "list-id" in headers,
        has_attachments=_has_attachments(payload),
        gmail_link=gmail_link(account_email, message.get("threadId", message["id"])),
    )


def extract_body_text(payload: dict) -> str:
    """Readable body text: prefer text/plain, fall back to stripped text/html."""
    plain: list[str] = []
    html: list[str] = []
    for part in _walk(payload):
        if part.get("filename"):
            continue
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            plain.append(_decode_body(data))
        elif mime == "text/html":
            html.append(_decode_body(data))
    if plain and any(text.strip() for text in plain):
        return _clean("\n".join(plain))
    return _clean(html_to_text("\n".join(html)))


def html_to_text(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    stripper.close()
    return stripper.text()


# --- helpers -----------------------------------------------------------------


def _headers(payload: dict) -> dict[str, str]:
    """Header name (lower-cased) -> value. The first occurrence wins."""
    result: dict[str, str] = {}
    for header in payload.get("headers", []):
        result.setdefault(header.get("name", "").lower(), header.get("value", ""))
    return result


def _decode_header(value: str) -> str:
    """Decode RFC 2047 encoded words (=?UTF-8?B?...?=) if present."""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _walk(part: dict):
    yield part
    for child in part.get("parts", []) or []:
        yield from _walk(child)


def _decode_body(data: str) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def _has_attachments(payload: dict) -> bool:
    return any(
        part.get("filename") and (part.get("body") or {}).get("attachmentId")
        for part in _walk(payload)
    )


_INVISIBLE = re.compile("[​‌‍⁠﻿­͏]")
_WHITESPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    """Collapse whitespace and drop zero-width padding and NUL bytes (Postgres rejects NUL)."""
    text = _INVISIBLE.sub("", text.replace("\x00", ""))
    return _WHITESPACE.sub(" ", text).strip()


class _HTMLStripper(HTMLParser):
    _SKIP = {"script", "style", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        else:
            self._chunks.append(" ")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        else:
            self._chunks.append(" ")

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)
