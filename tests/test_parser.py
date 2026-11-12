from datetime import datetime, timezone

from ingest.parser import BODY_EXCERPT_CHARS, gmail_link, html_to_text, parse_message, should_skip

ACCOUNT = "me@example.com"


def test_recruiter_multipart_prefers_plain_text(fixture_message):
    email = parse_message(fixture_message("recruiter_multipart"), ACCOUNT)

    assert email.gmail_message_id == "18f0a1b2c3d4e5f6"
    assert email.gmail_thread_id == "18f0a1b2c3d4e5f0"
    assert email.sender_name == "Priya Raman"
    assert email.sender_email == "priya.raman@example-talent.com"  # lower-cased
    assert email.subject == "Senior Python Engineer role at Acme - quick chat?"
    assert email.received_at == datetime.fromtimestamp(1794300000, tz=timezone.utc)
    assert email.internal_date_ms == 1794300000000
    assert email.body_excerpt.startswith("Hi Sri, I came across your profile")
    assert "HTML version" not in email.body_excerpt
    assert "\n" not in email.body_excerpt  # whitespace collapsed
    assert email.gmail_labels == ["INBOX", "UNREAD", "CATEGORY_PERSONAL"]
    assert email.is_list_mail is False
    assert email.has_attachments is False


def test_html_only_mail_is_stripped_and_subject_decoded(fixture_message):
    email = parse_message(fixture_message("job_alert_html_only"), ACCOUNT)

    assert email.subject == "12 new jobs – Python Developer"  # RFC 2047 decoded
    assert email.sender_name == "LinkedIn Job Alerts"
    assert email.is_list_mail is True
    assert email.body_excerpt == "12 new jobs Python Developer & more Backend Engineer at Globex"
    assert "track()" not in email.body_excerpt
    assert "color:red" not in email.body_excerpt


def test_attachment_detected_in_nested_parts(fixture_message):
    email = parse_message(fixture_message("with_attachment"), ACCOUNT)

    assert email.has_attachments is True
    assert email.sender_name == ""
    assert email.sender_email == "hr@initech.example"
    assert email.body_excerpt == "Please find the offer letter attached."


def test_long_body_is_truncated_and_missing_subject_is_empty(fixture_message):
    email = parse_message(fixture_message("long_body_no_subject"), ACCOUNT)

    assert email.subject == ""
    assert email.snippet == ""
    assert len(email.body_excerpt) == BODY_EXCERPT_CHARS


def test_gmail_link_targets_the_right_account():
    assert (
        gmail_link("first.last+jobs@gmail.com", "abc123")
        == "https://mail.google.com/mail/?authuser=first.last%2Bjobs%40gmail.com#all/abc123"
    )


def test_should_skip():
    assert should_skip(["SENT"]) is True
    assert should_skip(["DRAFT"]) is True
    assert should_skip(["CHAT"]) is True
    assert should_skip(["SENT", "INBOX"]) is False  # mail sent to yourself
    assert should_skip(["INBOX", "UNREAD"]) is False
    assert should_skip([]) is False  # archived mail is still tracked


def test_html_to_text_handles_broken_html():
    assert "hello" in html_to_text("<div><p>hello<br><b>world")
