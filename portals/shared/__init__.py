"""Helpers every portal adapter can reuse. Not a portal: it defines no PORTAL, so the
registry skips it.

    browser         headless Chromium: launch, close_all, force_close
    session         saved cookies per portal, so repeat runs skip the sign-in code
    otp             reads a portal's emailed sign-in code from the mailbox
    keyword_filter  the keyword relevance filter; each portal keeps its own keywords.yaml

Owned by the Coordinator (docs/OWNERS.md). A change here affects every portal.
"""
