"""Regenerate tests/fixtures/*.json:  python tests/make_fixtures.py

The fixtures mimic Gmail API `users.messages.get(format="full")` responses.
All content is invented; no real mail is stored in this repo.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def b64(text: str) -> str:
    # Gmail returns base64url, usually without padding
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def part(mime: str, text: str) -> dict:
    return {"mimeType": mime, "filename": "", "body": {"size": len(text), "data": b64(text)}}


def headers(**values: str) -> list[dict]:
    return [{"name": name.replace("_", "-"), "value": value} for name, value in values.items()]


MESSAGES = {
    "recruiter_multipart": {
        "id": "18f0a1b2c3d4e5f6",
        "threadId": "18f0a1b2c3d4e5f0",
        "labelIds": ["INBOX", "UNREAD", "CATEGORY_PERSONAL"],
        "snippet": "Hi Sri, I came across your profile and wanted to reach out about a Senior Python role",
        "internalDate": "1794300000000",
        "payload": {
            "mimeType": "multipart/alternative",
            "filename": "",
            "headers": headers(
                From='"Priya Raman" <Priya.Raman@Example-Talent.com>',
                To="me@example.com",
                Subject="Senior Python Engineer role at Acme - quick chat?",
                Date="Thu, 12 Nov 2026 10:00:00 +0530",
            ),
            "body": {"size": 0},
            "parts": [
                part(
                    "text/plain",
                    "Hi Sri,\r\n\r\nI came across your profile and wanted to reach out about a "
                    "Senior Python role at Acme in Bengaluru.\r\n\r\nAre you free for a call this week?\r\n\r\nPriya",
                ),
                part("text/html", "<html><body><p>HTML version that should be ignored</p></body></html>"),
            ],
        },
    },
    "job_alert_html_only": {
        "id": "18f0b00000000001",
        "threadId": "18f0b00000000001",
        "labelIds": ["INBOX", "CATEGORY_UPDATES"],
        "snippet": "12 new jobs for Python Developer",
        "internalDate": "1794303600000",
        "payload": {
            "mimeType": "text/html",
            "filename": "",
            "headers": headers(
                From="LinkedIn Job Alerts <jobalerts-noreply@linkedin.example>",
                Subject="=?UTF-8?B?MTIgbmV3IGpvYnMg4oCTIFB5dGhvbiBEZXZlbG9wZXI=?=",
                List_Unsubscribe="<https://linkedin.example/unsub>",
            ),
            "body": {
                "size": 1,
                "data": b64(
                    "<html><head><title>Jobs</title><style>p{color:red}</style></head><body>"
                    "<script>track()</script>"
                    "<h1>12 new jobs</h1><p>Python&nbsp;Developer &amp; more</p>"
                    "<a href='https://linkedin.example/jobs/1'>Backend Engineer‌ at Globex</a>"
                    "</body></html>"
                ),
            },
        },
    },
    "with_attachment": {
        "id": "18f0c00000000002",
        "threadId": "18f0c00000000002",
        "labelIds": ["INBOX", "IMPORTANT"],
        "snippet": "Please find the offer letter attached.",
        "internalDate": "1794307200000",
        "payload": {
            "mimeType": "multipart/mixed",
            "filename": "",
            "headers": headers(From="hr@initech.example", Subject="Offer letter"),
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "filename": "",
                    "body": {"size": 0},
                    "parts": [part("text/plain", "Please find the offer letter attached.")],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "offer.pdf",
                    "body": {"attachmentId": "ANGjdJ8fake", "size": 52311},
                },
            ],
        },
    },
    "sent_by_me": {
        "id": "18f0d00000000003",
        "threadId": "18f0a1b2c3d4e5f0",
        "labelIds": ["SENT"],
        "snippet": "Thanks Priya, Thursday works.",
        "internalDate": "1794310800000",
        "payload": {
            "mimeType": "text/plain",
            "filename": "",
            "headers": headers(From="me@example.com", Subject="Re: Senior Python Engineer role"),
            "body": {"size": 1, "data": b64("Thanks Priya, Thursday works.")},
        },
    },
    "long_body_no_subject": {
        "id": "18f0e00000000004",
        "threadId": "18f0e00000000004",
        "labelIds": ["INBOX"],
        "snippet": "",
        "internalDate": "1794314400000",
        "payload": {
            "mimeType": "text/plain",
            "filename": "",
            "headers": headers(From="billing@utility.example"),
            "body": {"size": 1, "data": b64("Your bill is ready. " * 500)},
        },
    },
}


if __name__ == "__main__":
    FIXTURES.mkdir(exist_ok=True)
    for name, message in MESSAGES.items():
        (FIXTURES / f"{name}.json").write_text(json.dumps(message, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(MESSAGES)} fixtures to {FIXTURES}")
