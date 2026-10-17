"""Vulcan SOF's code mail, read with the shared emailed-code helper."""
from __future__ import annotations

import email

from portals.shared import otp
from portals.vulcan_sof.auth import VULCAN_OTP

BODY = "Hello\n\nYOUR AUTHENTICATION CODE: 482913\n\nThis code expires in 10 minutes."


def test_vulcan_code_mail_settings() -> None:
    assert VULCAN_OTP.sender == "notifications@vulcan-sof.com"
    assert VULCAN_OTP.subject == "Vulcan - OTP Code"
    assert VULCAN_OTP.mailbox_key == "VULCAN_OTP_MAILBOX"


def test_vulcan_pattern_reads_its_code_mail() -> None:
    assert otp.extract_code(BODY, VULCAN_OTP.pattern) == "482913"
    assert otp.extract_code("YOUR AUTHENTICATION CODE: 111111 ... YOUR AUTHENTICATION CODE:222222", VULCAN_OTP.pattern) == "222222"
    assert otp.extract_code("no code here 123456", VULCAN_OTP.pattern) is None
    html = email.message_from_string("Content-Type: text/html\n\n<p>YOUR AUTHENTICATION CODE:&nbsp;<b>482913</b></p>")
    assert otp.extract_code(otp.message_text(html), VULCAN_OTP.pattern) == "482913"
