import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from ingest.gmail_client import RATE_LIMIT_WAITS, execute_with_backoff, is_rate_limit


def http_error(status: int, reason: str) -> HttpError:
    body = ('{"error": {"message": "x", "errors": [{"reason": "%s"}]}}' % reason).encode()
    return HttpError(Response({"status": status}), body)


class FakeRequest:
    def __init__(self, failures: list[Exception], result="ok") -> None:
        self.failures = list(failures)
        self.result = result
        self.calls = 0

    def execute(self, num_retries=0):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return self.result


def test_is_rate_limit():
    assert is_rate_limit(http_error(429, "rateLimitExceeded"))
    assert is_rate_limit(http_error(403, "rateLimitExceeded"))
    assert is_rate_limit(http_error(403, "userRateLimitExceeded"))
    assert not is_rate_limit(http_error(403, "insufficientPermissions"))
    assert not is_rate_limit(http_error(404, "notFound"))
    assert not is_rate_limit(RuntimeError("boom"))


def test_waits_and_retries_on_rate_limit():
    request = FakeRequest([http_error(403, "rateLimitExceeded"), http_error(429, "rateLimitExceeded")])
    waits = []

    assert execute_with_backoff(request, sleep=waits.append) == "ok"
    assert request.calls == 3
    assert waits == list(RATE_LIMIT_WAITS[:2])


def test_other_errors_are_raised_immediately():
    request = FakeRequest([http_error(403, "insufficientPermissions")])
    waits = []

    with pytest.raises(HttpError):
        execute_with_backoff(request, sleep=waits.append)
    assert request.calls == 1 and waits == []


def test_gives_up_after_all_waits():
    request = FakeRequest([http_error(429, "rateLimitExceeded")] * (len(RATE_LIMIT_WAITS) + 1))

    with pytest.raises(HttpError):
        execute_with_backoff(request, sleep=lambda s: None)
    assert request.calls == len(RATE_LIMIT_WAITS) + 1
