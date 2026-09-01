import pytest

import http_util
from http_util import RateLimiter, RiskControlError, backoff_sequence, request_with_retry


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_backoff_sequence_values():
    assert backoff_sequence("normal") == [1.0, 2.0, 4.0]
    assert backoff_sequence("risk") == [3.0, 6.0, 12.0]


def test_limiter_escalates_on_failure_and_resets_on_success():
    lim = RateLimiter(base=0.5, max_=2.0, sleep=lambda s: None)
    lim.on_failure()
    lim.on_failure()
    lim.on_failure()
    assert lim._current == 2.0  # 封顶
    lim.on_success()
    assert lim._current == 0.5  # 成功后归位


def test_retry_normal_then_success(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_request(method, url, **kw):
        calls["n"] += 1
        return FakeResp(500) if calls["n"] < 3 else FakeResp(200, {"ok": 1})

    monkeypatch.setattr(http_util.requests, "request", fake_request)
    resp = request_with_retry("GET", "http://x", sleep=sleeps.append,
                              limiter=RateLimiter(base=0, max_=2, sleep=lambda s: None))
    assert resp.json() == {"ok": 1}
    assert sleeps == [1.0, 2.0]


def test_risk_backoff_sequence_on_412(monkeypatch):
    sleeps = []

    def fake_request(method, url, **kw):
        return FakeResp(412)

    monkeypatch.setattr(http_util.requests, "request", fake_request)
    lim = RateLimiter(base=0.5, max_=2, sleep=lambda s: None)
    with pytest.raises(RiskControlError):
        request_with_retry("GET", "http://x", sleep=sleeps.append, limiter=lim)
    assert sleeps == [3.0, 6.0, 12.0]
    assert lim._current == 2.0  # 终态失败后保持上限，不复位（规格 §4 成功后归位）


def test_risk_check_on_json_code(monkeypatch):
    sleeps = []

    def fake_request(method, url, **kw):
        return FakeResp(200, {"code": -412})

    monkeypatch.setattr(http_util.requests, "request", fake_request)
    with pytest.raises(RiskControlError):
        request_with_retry("GET", "http://x", sleep=sleeps.append,
                           risk_check=lambda r: r.json().get("code") == -412,
                           limiter=RateLimiter(base=0, max_=2, sleep=lambda s: None))
    assert sleeps == [3.0, 6.0, 12.0]


def test_raises_after_max_retries(monkeypatch):
    def fake_request(method, url, **kw):
        return FakeResp(502)

    monkeypatch.setattr(http_util.requests, "request", fake_request)
    with pytest.raises(RuntimeError):
        request_with_retry("GET", "http://x", sleep=lambda s: None,
                           limiter=RateLimiter(base=0, max_=2, sleep=lambda s: None))


def test_retry_on_request_exception(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_request(method, url, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise http_util.requests.ConnectionError("boom")
        return FakeResp(200, {"ok": 1})

    monkeypatch.setattr(http_util.requests, "request", fake_request)
    resp = request_with_retry("GET", "http://x", sleep=sleeps.append,
                              limiter=RateLimiter(base=0, max_=2, sleep=lambda s: None))
    assert resp.json() == {"ok": 1}
    assert sleeps == [1.0, 2.0]


def test_passes_json_payload_through(monkeypatch):
    captured = {}

    def fake_request(method, url, **kw):
        captured.update(kw)
        return FakeResp(200, {"ok": 1})

    monkeypatch.setattr(http_util.requests, "request", fake_request)
    request_with_retry("POST", "http://x", json={"model": "m1"},
                       limiter=RateLimiter(base=0, max_=2, sleep=lambda s: None))
    assert captured["json"] == {"model": "m1"}
