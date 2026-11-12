"""Classifier logic with fake model backends. No network, no database."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ingest import config
from ingest.classify import (
    ANTHROPIC_MODEL,
    BODY_CHARS_FOR_MODEL,
    CATEGORIES,
    OLLAMA_BODY_CHARS,
    OUTPUT_SCHEMA,
    EmailToClassify,
    ModelBackend,
    build_user_message,
    choose_backend,
    classify_by_rules,
    classify_pending,
    classify_with_model,
    classify_with_ollama,
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
PROMO = replace(
    RECRUITER, id=4, sender_name="Shop", sender_email="news@shop.example", subject="50% off this weekend",
    snippet="Big sale", is_list_mail=True, gmail_labels=["INBOX", "CATEGORY_PROMOTIONS"],
)
GOOD_JSON = {"category": "direct_opportunity", "priority": "high",
             "summary": "Recruiter at Acme asks about a Senior Python role", "reason": "personal recruiter message"}


# --- rules -------------------------------------------------------------------------

def test_rules_match_known_bulk_senders_case_insensitively():
    result = classify_by_rules(ALERT)
    assert (result.category, result.priority, result.classified_by) == ("job_alerts", "low", "rules")
    assert result.summary == "12 new jobs for Python Developer"


def test_rules_company_job_notifications():
    email = replace(RECRUITER, sender_email="cmacgm-jobnotification@noreply12.jobs2web.com", subject="New jobs")
    assert classify_by_rules(email).category == "company_postings"


def test_rules_promotions_without_job_words_are_other():
    assert classify_by_rules(PROMO).category == "other"


@pytest.mark.parametrize("subject", ["Nouvelles offres d'emploi", "Join our Talent Community", "Your application"])
def test_rules_never_hide_promotions_that_mention_jobs(subject):
    assert classify_by_rules(replace(PROMO, subject=subject)) is None


def test_rules_leave_unknown_senders_to_the_model():
    assert classify_by_rules(RECRUITER) is None
    # not a list mail: a person writing, even if Gmail calls it a promotion
    assert classify_by_rules(replace(PROMO, is_list_mail=False)) is None


# --- prompt --------------------------------------------------------------------------

def test_user_message_contains_only_what_is_needed():
    message = build_user_message(RECRUITER)
    assert "Priya Raman <priya@example-talent.com>" in message
    assert "<subject>Senior Python Engineer role at Acme</subject>" in message
    body = message.split("<body_start>")[1].split("</body_start>")[0]
    assert len(body) == BODY_CHARS_FOR_MODEL


def test_schema_lists_every_category():
    assert OUTPUT_SCHEMA["properties"]["category"]["enum"] == list(CATEGORIES)


# --- Ollama backend --------------------------------------------------------------------

def test_ollama_request_and_parsing():
    calls = []

    def post(url, payload, timeout):
        calls.append((url, payload))
        return {"message": {"content": json.dumps(GOOD_JSON)}}

    result = classify_with_ollama(RECRUITER, model="qwen3:8b", base_url="http://localhost:11434/", post=post)

    assert result.category == "direct_opportunity" and result.classified_by == "llm"
    url, payload = calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload["model"] == "qwen3:8b"
    assert payload["format"] is OUTPUT_SCHEMA
    assert payload["think"] is False and payload["stream"] is False
    body = payload["messages"][1]["content"].split("<body_start>")[1].split("</body_start>")[0]
    assert len(body) == OLLAMA_BODY_CHARS


def test_ollama_bad_output_raises():
    with pytest.raises(RuntimeError):
        classify_with_ollama(RECRUITER, post=lambda *a: {"message": {"content": "sure! here it is"}})


def test_choose_backend(monkeypatch):
    import ingest.classify as classify

    monkeypatch.setattr(classify, "ollama_running", lambda *a: True)
    assert choose_backend("auto").name == "ollama qwen3:8b"
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    assert choose_backend("ollama").name == "ollama qwen3:4b"
    assert choose_backend("rules") is None

    monkeypatch.setattr(classify, "ollama_running", lambda *a: False)
    assert choose_backend("auto") is None  # falls back to rules only
    with pytest.raises(config.ConfigError):
        choose_backend("ollama")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        choose_backend("anthropic")
    with pytest.raises(config.ConfigError):
        choose_backend("something")


# --- Anthropic backend (optional) -------------------------------------------------------

def response(payload=None, stop_reason="end_turn", text=None):
    body = text if text is not None else json.dumps(payload)
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=body)])


class FakeMessages:
    def __init__(self, reply) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply


def test_anthropic_request_uses_haiku_low_effort_and_the_schema():
    messages = FakeMessages(response(GOOD_JSON))
    assert classify_with_model(RECRUITER, messages).priority == "high"
    call = messages.calls[0]
    assert call["model"] == ANTHROPIC_MODEL == "claude-haiku-5-5"
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}}


def test_anthropic_refusal_is_stored_as_needs_manual_check():
    result = classify_with_model(RECRUITER, FakeMessages(response(stop_reason="refusal", text="")))
    assert (result.category, result.priority) == ("other", "medium")


def test_invalid_category_raises():
    with pytest.raises(RuntimeError):
        classify_with_model(RECRUITER, FakeMessages(response({**GOOD_JSON, "category": "made_up"})))


def test_summary_is_kept_to_one_line():
    result = classify_with_model(RECRUITER, FakeMessages(response({**GOOD_JSON, "summary": "one\ntwo"})))
    assert result.summary == "one two"


# --- classify_pending --------------------------------------------------------------------

class FakeStore:
    def __init__(self, emails) -> None:
        self.emails = list(emails)
        self.saved: dict[int, object] = {}

    def unclassified_emails(self, limit=None):
        return [e for e in self.emails if e.id not in self.saved][:limit]

    def save_classification(self, email_id, result) -> None:
        self.saved.setdefault(email_id, result)


def test_classify_pending_rules_only():
    store = FakeStore([RECRUITER, ALERT, PROMO])
    result = classify_pending(store, backend=None)
    assert (result.by_rules, result.by_model, result.left_unclassified) == (2, 0, 1)
    assert set(store.saved) == {ALERT.id, PROMO.id}


def test_classify_pending_with_model_and_a_failure():
    broken = replace(RECRUITER, id=3, subject="boom")

    def classify(email):
        if email.subject == "boom":
            raise RuntimeError("model down")
        return classify_with_model(email, FakeMessages(response(GOOD_JSON)))

    progress = []
    store = FakeStore([RECRUITER, ALERT, broken])
    result = classify_pending(store, ModelBackend("fake", classify, workers=2), progress=lambda d, t: progress.append((d, t)))

    assert (result.by_rules, result.by_model, result.failed, result.left_unclassified) == (1, 1, 1, 1)
    assert progress[-1] == (2, 2)
    assert [e.id for e in store.unclassified_emails()] == [3]  # a rerun retries only the failed one
