from __future__ import annotations

import email
import time

import pytest

from portals.vulcan_sof import otp

BODY = "Hello\n\nYOUR AUTHENTICATION CODE: 482913\n\nThis code expires in 10 minutes."


def test_extract_code_last_match_and_none() -> None:
    assert otp.extract_code(BODY) == "482913"
    assert otp.extract_code("YOUR AUTHENTICATION CODE: 111111 ... YOUR AUTHENTICATION CODE:222222") == "222222"
    assert otp.extract_code("no code here 123456") is None
    assert otp.extract_code("") is None


def test_get_otp_returns_fresh_code_and_skips_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_after = time.time()
    stale = otp.OtpMessage(body="YOUR AUTHENTICATION CODE: 000000", received_at=sent_after - 120)
    fresh = otp.OtpMessage(body=BODY, received_at=sent_after + 10)
    calls: list[int] = []

    def fetch(mailbox: str) -> list[otp.OtpMessage]:
        calls.append(1)
        return [fresh, stale] if len(calls) >= 2 else [stale]

    code = otp.get_otp(sent_after, max_wait=60, mailbox="x@example.invalid", fetch=fetch, sleep=lambda s: None)
    assert code == "482913"
    assert len(calls) == 2


def test_get_otp_keeps_polling_through_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def fetch(mailbox: str) -> list[otp.OtpMessage]:
        attempts.append(1)
        if len(attempts) == 1:
            raise FileNotFoundError("gog")
        if len(attempts) == 2:
            raise TimeoutError("slow mailbox")
        return [otp.OtpMessage(body=BODY)]

    assert otp.get_otp(0.0, max_wait=60, mailbox="x", fetch=fetch, sleep=lambda s: None) == "482913"
    assert len(attempts) == 3


def test_get_otp_times_out_to_none() -> None:
    clock = {"now": 1000.0}

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    import portals.vulcan_sof.otp as mod
    original = mod.time.time
    mod.time.time = lambda: clock["now"]   # type: ignore[assignment]
    try:
        assert mod.get_otp(900.0, max_wait=12, mailbox="x", fetch=lambda m: [], sleep=sleep) is None
    finally:
        mod.time.time = original   # type: ignore[assignment]


def test_day_precision_staleness() -> None:
    noon = 1_760_616_000.0   # 2026-10-16T12:00:00Z
    midnight_same_day = 1_760_572_800.0
    yesterday = midnight_same_day - 86_400
    assert otp.is_stale(otp.OtpMessage(body="", received_at=midnight_same_day, day_precision=True), noon) is False
    assert otp.is_stale(otp.OtpMessage(body="", received_at=yesterday, day_precision=True), noon) is True
    assert otp.is_stale(otp.OtpMessage(body="", received_at=noon - 1), noon) is False   # within clock skew
    assert otp.is_stale(otp.OtpMessage(body="", received_at=noon - 120), noon) is True
    assert otp.is_stale(otp.OtpMessage(body="", received_at=None), noon) is False


def test_parse_gog_search() -> None:
    out = "ID        DATE        FROM\n# comment\n19a2b3c  2026-10-16  notifications@vulcan-sof.com  Vulcan - OTP Code\n"
    parsed = otp.parse_gog_search(out)
    assert len(parsed) == 1 and parsed[0][0] == "19a2b3c" and parsed[0][1] is not None


def test_message_text_prefers_plain_then_strips_html() -> None:
    plain = email.message_from_string("Content-Type: text/plain\n\n" + BODY)
    assert "482913" in otp.message_text(plain)
    html = email.message_from_string(
        "Content-Type: text/html\n\n<p>YOUR AUTHENTICATION CODE:&nbsp;<b>482913</b></p>"
    )
    assert otp.extract_code(otp.message_text(html)) == "482913"


def test_default_fetcher_without_access_names_remedy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp.shutil, "which", lambda name: None)
    monkeypatch.setattr(otp, "get", lambda key, default=None: None)
    with pytest.raises(otp.ConfigError) as exc:
        otp.default_fetcher()
    assert "gog" in str(exc.value) and "VELOCITY_GMAIL_APP_PASSWORD" in str(exc.value)
