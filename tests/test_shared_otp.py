"""The shared emailed-code helper, exercised with a made-up portal's code mail."""
from __future__ import annotations

import email
import re
import time

import pytest

from portals.shared import otp

SOURCE = otp.OtpSource(
    portal="Example portal",
    sender="codes@example.invalid",
    subject="Your sign-in code",
    pattern=re.compile(r"CODE:\s*(\d{6})"),
    mailbox_key="EXAMPLE_OTP_MAILBOX",
)
BODY = "Hello\n\nCODE: 482913\n\nIt expires in 10 minutes."


def test_extract_code_uses_the_portals_pattern_and_takes_the_last_match() -> None:
    assert otp.extract_code(BODY, SOURCE.pattern) == "482913"
    assert otp.extract_code("CODE: 111111 then CODE:222222", SOURCE.pattern) == "222222"
    assert otp.extract_code("no code here 123456", SOURCE.pattern) is None
    assert otp.extract_code("", SOURCE.pattern) is None


def test_get_otp_returns_a_fresh_code_and_skips_stale_mail() -> None:
    sent_after = time.time()
    stale = otp.OtpMessage(body="CODE: 000000", received_at=sent_after - 120)
    fresh = otp.OtpMessage(body=BODY, received_at=sent_after + 10)
    calls: list[str] = []

    def fetch(mailbox: str) -> list[otp.OtpMessage]:
        calls.append(mailbox)
        return [fresh, stale] if len(calls) >= 2 else [stale]

    code = otp.get_otp(SOURCE, sent_after, max_wait=60, mailbox="box@example.invalid", fetch=fetch, sleep=lambda s: None)
    assert code == "482913"
    assert calls == ["box@example.invalid", "box@example.invalid"]


def test_get_otp_reads_the_mailbox_from_the_portals_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_OTP_MAILBOX", "from-config@example.invalid")
    seen: list[str] = []

    def fetch(mailbox: str) -> list[otp.OtpMessage]:
        seen.append(mailbox)
        return [otp.OtpMessage(body=BODY)]

    assert otp.get_otp(SOURCE, 0.0, max_wait=60, fetch=fetch, sleep=lambda s: None) == "482913"
    assert seen == ["from-config@example.invalid"]


def test_get_otp_keeps_polling_through_failures() -> None:
    attempts: list[int] = []

    def fetch(mailbox: str) -> list[otp.OtpMessage]:
        attempts.append(1)
        if len(attempts) == 1:
            raise FileNotFoundError("gog")
        if len(attempts) == 2:
            raise TimeoutError("slow mailbox")
        return [otp.OtpMessage(body=BODY)]

    assert otp.get_otp(SOURCE, 0.0, max_wait=60, mailbox="x", fetch=fetch, sleep=lambda s: None) == "482913"
    assert len(attempts) == 3


def test_get_otp_times_out_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 1000.0}

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    monkeypatch.setattr(otp.time, "time", lambda: clock["now"])
    assert otp.get_otp(SOURCE, 900.0, max_wait=12, mailbox="x", fetch=lambda m: [], sleep=sleep) is None


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
    out = "ID        DATE        FROM\n# comment\n19a2b3c  2026-10-16  codes@example.invalid  Your sign-in code\n"
    parsed = otp.parse_gog_search(out)
    assert len(parsed) == 1 and parsed[0][0] == "19a2b3c" and parsed[0][1] is not None


def test_gog_search_is_built_from_the_source(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def run_gog(args: list[str]) -> str:
        commands.append(args)
        return "19a2b3c  2026-10-16  codes@example.invalid\n" if args[1] == "search" else BODY

    monkeypatch.setattr(otp, "_run_gog", run_gog)
    messages = otp.fetch_via_gog(SOURCE, "box@example.invalid")
    assert commands[0][2] == "from:codes@example.invalid subject:'Your sign-in code' newer_than:5m"
    assert commands[1][:3] == ["gmail", "read", "19a2b3c"]
    assert otp.extract_code(messages[0].body, SOURCE.pattern) == "482913"


def test_imap_search_is_built_from_the_source(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeImap:
        last: "FakeImap"

        def __init__(self, host: str, timeout: int) -> None:
            FakeImap.last = self

        def login(self, user: str, password: str) -> None:
            self.user, self.password = user, password

        def select(self, box: str, readonly: bool) -> None:
            pass

        def search(self, charset: object, *criteria: str) -> tuple[str, list[bytes]]:
            self.criteria = criteria
            return "OK", [b"1"]

        def fetch(self, msg_id: bytes, what: str) -> tuple[str, list[tuple[bytes, bytes]]]:
            mail = "Date: Fri, 16 Oct 2026 12:00:00 +0000\nContent-Type: text/plain\n\n" + BODY
            return "OK", [(b"1", mail.encode())]

        def logout(self) -> None:
            pass

    settings = {"VELOCITY_GMAIL_APP_USERNAME": "account@example.invalid"}
    monkeypatch.setattr(otp.imaplib, "IMAP4_SSL", FakeImap)
    monkeypatch.setattr(otp, "get", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(otp, "require", lambda key: "abcd efgh ijkl mnop")
    messages = otp.fetch_via_imap(SOURCE, "box@example.invalid")
    assert FakeImap.last.criteria[:4] == ("FROM", '"codes@example.invalid"', "SUBJECT", '"Your sign-in code"')
    assert (FakeImap.last.user, FakeImap.last.password) == ("account@example.invalid", "abcdefghijklmnop")
    assert otp.extract_code(messages[0].body, SOURCE.pattern) == "482913"


def test_message_text_prefers_plain_then_strips_html() -> None:
    plain = email.message_from_string("Content-Type: text/plain\n\n" + BODY)
    assert "482913" in otp.message_text(plain)
    html = email.message_from_string("Content-Type: text/html\n\n<p>CODE:&nbsp;<b>482913</b></p>")
    assert otp.extract_code(otp.message_text(html), SOURCE.pattern) == "482913"


def test_default_fetcher_without_access_names_the_remedy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp.shutil, "which", lambda name: None)
    monkeypatch.setattr(otp, "get", lambda key, default=None: None)
    with pytest.raises(otp.ConfigError) as exc:
        otp.default_fetcher(SOURCE)
    assert "gog" in str(exc.value) and "VELOCITY_GMAIL_APP_PASSWORD" in str(exc.value)


def test_get_otp_stops_at_once_when_the_mailbox_refuses_its_password() -> None:
    """16 Nov 2026: Gmail refused the app password, and the wait retried it for the full 90 s, then said only that no
    code came. A refused password won't mend itself, so the wait ends at once and says what to fix."""
    calls: list[int] = []

    def fetch(mailbox: str) -> list[otp.OtpMessage]:
        calls.append(1)
        raise otp.MailboxRefused("Gmail rejected VELOCITY_GMAIL_APP_PASSWORD")

    with pytest.raises(otp.MailboxRefused) as refused:
        otp.get_otp(SOURCE, 0.0, max_wait=90, mailbox="x", fetch=fetch, sleep=lambda s: None)
    assert len(calls) == 1
    assert str(refused.value).startswith("Example portal asked for an emailed sign-in code, and Gmail rejected")


def test_an_imap_login_refusal_names_the_setting_and_never_its_value(monkeypatch: pytest.MonkeyPatch) -> None:
    class RefusingImap:
        def __init__(self, host: str, timeout: int) -> None:
            pass

        def login(self, user: str, password: str) -> None:
            raise otp.imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials (Failure)")

        def logout(self) -> None:
            pass

    monkeypatch.setattr(otp.imaplib, "IMAP4_SSL", RefusingImap)
    monkeypatch.setattr(otp, "get", lambda key, default=None: "account@example.invalid")
    monkeypatch.setattr(otp, "require", lambda key: "abcd efgh ijkl mnop")
    with pytest.raises(otp.MailboxRefused) as refused:
        otp.fetch_via_imap(SOURCE, "box@example.invalid")
    message = str(refused.value)
    assert "VELOCITY_GMAIL_APP_PASSWORD" in message and "app password" in message
    assert "abcd" not in message and "abcdefghijklmnop" not in message and "account@example.invalid" not in message
    whole = f"MailboxRefused: Vulcan SOF asked for an emailed sign-in code, and {message}"
    assert len(whole) <= 200 and whole.endswith("put it in .env")   # run.py keeps 200 characters of a run's error


# ---------------------------------------------------------------- Gmail API through the service account (16 Nov 2026)

def _raw(text: str) -> str:
    import base64

    mail = "Date: Mon, 16 Nov 2026 12:00:00 +0000\nContent-Type: text/plain\n\n" + text
    return base64.urlsafe_b64encode(mail.encode()).decode()


class _Req:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result, self.error = result, error

    def execute(self) -> object:
        if self.error:
            raise self.error
        return self.result


def _gmail(listing: _Req, asked: dict[str, object]) -> object:
    class Messages:
        def list(self, userId: str, q: str, maxResults: int) -> _Req:
            asked.update(user=userId, q=q, max=maxResults)
            return listing

        def get(self, userId: str, id: str, format: str) -> _Req:
            asked.update(format=format)
            return _Req({"id": id, "internalDate": "1794830400000", "raw": _raw(BODY)})

    class Users:
        def messages(self) -> Messages:
            return Messages()

    class Gmail:
        def users(self) -> Users:
            return Users()

    return Gmail()


def test_the_gmail_api_is_chosen_once_its_account_is_named(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """David, 16 Nov 2026: on Velocity's GKE the code is read through the Gmail API by the service account, which
    survives password changes; an app password stays the fallback until the admin's grant is in."""
    key = tmp_path / "key.json"
    key.write_text("{}", encoding="utf-8")
    settings = {"OTP_GMAIL_ACCOUNT": "bd@example.invalid", "GOOGLE_SERVICE_ACCOUNT_FILE": str(key), "VELOCITY_GMAIL_APP_PASSWORD": "x"}
    monkeypatch.setattr(otp.shutil, "which", lambda name: None)
    monkeypatch.setattr(otp, "get", lambda k, d=None: settings.get(k, d))
    assert otp.default_fetcher(SOURCE).func is otp.fetch_via_gmail_api
    del settings["OTP_GMAIL_ACCOUNT"]
    assert otp.default_fetcher(SOURCE).func is otp.fetch_via_imap
    settings["OTP_GMAIL_ACCOUNT"] = "bd@example.invalid"
    settings["GOOGLE_SERVICE_ACCOUNT_FILE"] = str(tmp_path / "missing.json")   # no key file: not the API
    assert otp.default_fetcher(SOURCE).func is otp.fetch_via_imap


def test_gmail_api_search_is_built_from_the_source_and_reads_the_code(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: dict[str, object] = {}
    seen: list[str] = []
    monkeypatch.setattr(otp, "get", lambda k, d=None: {"OTP_GMAIL_ACCOUNT": "bd@example.invalid"}.get(k, d))
    monkeypatch.setattr(otp, "gmail_service", lambda account: seen.append(account) or _gmail(_Req({"messages": [{"id": "m1"}]}), asked))
    messages = otp.fetch_via_gmail_api(SOURCE, "not-an-address")
    assert seen == ["bd@example.invalid"]   # the named account, whatever the portal's mailbox setting holds
    assert asked["user"] == "me" and asked["max"] == 3 and asked["format"] == "raw"
    assert asked["q"] == 'from:codes@example.invalid subject:"Your sign-in code" newer_than:1d'
    assert otp.extract_code(messages[0].body, SOURCE.pattern) == "482913"
    assert messages[0].received_at == 1794830400.0


def test_gmail_api_with_no_mail_is_an_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp, "get", lambda k, d=None: {"OTP_GMAIL_ACCOUNT": "bd@example.invalid"}.get(k, d))
    monkeypatch.setattr(otp, "gmail_service", lambda account: _gmail(_Req({"resultSizeEstimate": 0}), {}))
    assert otp.fetch_via_gmail_api(SOURCE, "x") == []


@pytest.mark.parametrize(("error", "says"), [
    (Exception("('unauthorized_client: Client is unauthorized to retrieve access tokens using this method', ...)"),
     "domain-wide delegation"),
    (Exception("<HttpError 403 ... Gmail API has not been used in project 123 before or it is disabled.>"), "Gmail API is off"),
])
def test_gmail_api_refusals_say_what_the_admin_must_do(monkeypatch: pytest.MonkeyPatch, error: Exception, says: str) -> None:
    monkeypatch.setattr(otp, "get", lambda k, d=None: {"OTP_GMAIL_ACCOUNT": "bd@example.invalid"}.get(k, d))
    monkeypatch.setattr(otp, "gmail_service", lambda account: _gmail(_Req(error=error), {}))
    with pytest.raises(otp.MailboxRefused) as refused:
        otp.fetch_via_gmail_api(SOURCE, "x")
    whole = f"MailboxRefused: Vulcan SOF asked for an emailed sign-in code, and {refused.value}"
    assert says in whole and len(whole) <= 200 and "bd@example.invalid" not in whole


def test_a_passing_gmail_api_error_keeps_the_wait_going(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(otp, "get", lambda k, d=None: {"OTP_GMAIL_ACCOUNT": "bd@example.invalid"}.get(k, d))
    monkeypatch.setattr(otp, "gmail_service", lambda account: _gmail(_Req(error=TimeoutError("slow")), {}))
    with pytest.raises(TimeoutError):   # get_otp logs it and polls again
        otp.fetch_via_gmail_api(SOURCE, "x")
