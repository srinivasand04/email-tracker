"""Classifier logic with a fake Claude client. No network, no database."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ingest.classify import (
    BODY_CHARS_FOR_MODEL,
    CATEGORIES,
    MODEL,
    OUTPUT_SCHEMA,
    EmailToClassify,
    build_user_message,
    classify_by_rules,
    classify_pending,
    classify_with_model,
)

RECRUITER = EmailToClassify(
    id=1,
    account_email="me@example.com",
    sender_name="Priya Raman",
    sender_email="priya@example-talent.com",
    subject="Senior Python Engineer role at Acme",
    snippet="Hi, I came across your profile",
    body_excerpt="Hi, I came across your profile. " * 200,
    is_list_mail=False,
    gmail_labels=["INBOX"],
)
ALERT = replace(
    RECRUITER, id=2, sender_name="LinkedIn Job Alerts", sender_email="JobAlerts-NoReply@linkedin.com",
    subject="12 new jobs for Python Developer", is_list_mail=True,
)


def response(payload: dict | None = None, stop_reason: str = "end_turn", text: str | None = None):
    body = text if text is not None else json.dumps(payload)
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=body)])


class FakeMessages:
    def __init__(self, reply) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply(kwargs) if callable(self.reply) else self.reply


class FakeStore:
    def __init__(self, emails) -> None:
        self.emails = list(emails)
        self.saved: dict[int, object] = {}

    def unclassified_emails(self, limit=None):
        return [e for e in self.emails if e.id not in self.saved][:limit]

    def save_classification(self, email_id, result) -> None:
        self.saved.setdefault(email_id, result)


def test_rules_match_known_bulk_senders_case_insensitively():
    result = classify_by_rules(ALERT)
    assert result.category == "job_alerts"
    assert result.priority == "low"
    assert result.classified_by == "rules"
    assert result.summary == "12 new jobs for Python Developer"


def test_rules_leave_unknown_senders_to_the_model():
    assert classify_by_rules(RECRUITER) is None


def test_user_message_contains_only_what_is_needed():
    message = build_user_message(RECRUITER)
    assert "Priya Raman <priya@example-talent.com>" in message
    assert "<subject>Senior Python Engineer role at Acme</subject>" in message
    body = message.split("<body_start>")[1].split("</body_start>")[0]
    assert len(body) == BODY_CHARS_FOR_MODEL


def test_model_request_uses_haiku_low_effort_and_the_schema():
    messages = FakeMessages(response({
        "category": "direct_opportunity", "priority": "high",
        "summary": "Recruiter at Acme asks about a Senior Python role; reply to book a call",
        "reason": "personal recruiter message",
    }))

    result = classify_with_model(RECRUITER, messages)

    assert result.category == "direct_opportunity"
    assert result.priority == "high"
    assert result.classified_by == "llm"
    call = messages.calls[0]
    assert call["model"] == MODEL == "claude-haiku-5-5"
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"]["schema"] is OUTPUT_SCHEMA
    assert "thinking" not in call and "temperature" not in call


def test_schema_lists_every_category():
    assert OUTPUT_SCHEMA["properties"]["category"]["enum"] == list(CATEGORIES)


def test_refusal_is_stored_as_needs_manual_check():
    result = classify_with_model(RECRUITER, FakeMessages(response(stop_reason="refusal", text="")))
    assert result.category == "other"
    assert result.priority == "medium"
    assert "declined" in result.reason


def test_invalid_output_raises():
    with pytest.raises(RuntimeError):
        classify_with_model(RECRUITER, FakeMessages(response(text="not json")))
    with pytest.raises(RuntimeError):
        classify_with_model(RECRUITER, FakeMessages(response({
            "category": "made_up", "priority": "high", "summary": "x", "reason": "y",
        })))


def test_summary_is_kept_to_one_line():
    result = classify_with_model(RECRUITER, FakeMessages(response({
        "category": "personal", "priority": "low", "summary": "line one\nline two", "reason": "r",
    })))
    assert result.summary == "line one line two"


def test_classify_pending_without_api_key_runs_rules_only():
    store = FakeStore([RECRUITER, ALERT])

    result = classify_pending(store, messages=None)

    assert (result.by_rules, result.by_model, result.left_unclassified) == (1, 0, 1)
    assert set(store.saved) == {ALERT.id}


def test_classify_pending_with_model_and_a_failure():
    other = replace(RECRUITER, id=3, subject="boom")

    def reply(kwargs):
        if "boom" in kwargs["messages"][0]["content"]:
            raise RuntimeError("API down")
        return response({"category": "personal", "priority": "medium", "summary": "s", "reason": "r"})

    store = FakeStore([RECRUITER, ALERT, other])
    result = classify_pending(store, FakeMessages(reply))

    assert (result.by_rules, result.by_model, result.failed) == (1, 1, 1)
    assert set(store.saved) == {RECRUITER.id, ALERT.id}
    # a rerun only retries the failed one
    assert [e.id for e in store.unclassified_emails()] == [3]
