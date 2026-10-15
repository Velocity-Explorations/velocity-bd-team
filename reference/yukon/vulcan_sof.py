"""
Yukon — Vulcan SOF portal adapter
Scrapes open calls from the Vulcan SOF platform using Playwright.
Requires VULCAN_SOF_USERNAME + VULCAN_SOF_PASSWORD in configs/velocity/.env
OTP is auto-intercepted from david@velocityexplorations.com Gmail when required.

Authentication notes:
- Vulcan uses username/password + email OTP (2FA)
- Sessions persist within a single Playwright run
- When OTP is required, we intercept via gog gmail read
"""

import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

VULCAN_HOME = "https://vulcan-sof.com"
VULCAN_LOGIN = f"{VULCAN_HOME}/login/ng2/auth/login"
VULCAN_CALLS = f"{VULCAN_HOME}/login/ng2/search/calls"

VELOCITY_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "software", "data",
    "cyber", "cloud", "modernization", "command and control", "c2", "nlp",
    "autonomous", "autonomy", "digital", "information", "analytics", "agentic",
    "esof", "engage sof", "warfighter", "command",
    "joint", "experimentation", "experimentation",
    "it ", "computing", "algorithm", "automation", "intelligence", "document",
    "help desk", "privacy", "opsec", "c5isr", "isr", "sensor", "network",
    "communications", "pcte", "training system", "simulation",
]

# Persistent cookie storage to skip OTP on repeat logins
COOKIE_PATH = Path(__file__).parent.parent.parent / "data" / "vulcan_cookies.json"

# Module-level ref so we can force-close on thread timeout
_active_browser = None


def _load_creds() -> tuple:
    """Load Vulcan credentials from profile .env."""
    env_path = Path(__file__).parent.parent.parent / "configs" / "velocity" / ".env"
    username = password = ""
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("VULCAN_SOF_USERNAME="):
                username = line.split("=", 1)[1].strip()
            elif line.startswith("VULCAN_SOF_PASSWORD="):
                password = line.split("=", 1)[1].strip()
    return username, password


def _get_otp_from_gmail(max_wait: int = 90, sent_after: float = None) -> Optional[str]:
    """
    Wait for and retrieve the most recent Vulcan OTP from Gmail.
    sent_after: unix timestamp — only accept emails received after this time.
    Returns 6-digit code string, or None if timeout.
    """
    log.info("Waiting for Vulcan OTP in Gmail (max %ds)...", max_wait)
    deadline = time.time() + max_wait

    while time.time() < deadline:
        time.sleep(5)
        remaining = int(deadline - time.time())
        try:
            r = subprocess.run(
                ["gog", "gmail", "search",
                 "from:notifications@vulcan-sof.com subject:'Vulcan - OTP Code' newer_than:5m",
                 "--max", "1", "--account", "david@velocityexplorations.com"],
                capture_output=True, text=True, timeout=15
            )
        except subprocess.TimeoutExpired:
            log.warning("gog search timed out — retrying (%ds left)", remaining)
            continue
        except FileNotFoundError:
            log.error("gog CLI not found in PATH — cannot retrieve OTP")
            return None

        if r.returncode != 0:
            log.debug("gog search failed: %s", r.stderr[:100])
            continue

        lines = [l for l in r.stdout.splitlines()
                 if l.strip() and not l.startswith('#') and not l.startswith('ID')]
        if not lines:
            log.debug("No OTP emails yet (%ds left)", remaining)
            continue

        # Parse the email date and reject stale OTPs
        parts = lines[0].split()
        thread_id = parts[0]
        if sent_after and len(parts) >= 2:
            try:
                email_date_str = parts[1]
                email_dt = datetime.strptime(email_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                # gog only gives date precision — if the email is from a previous day, skip it
                sent_after_dt = datetime.fromtimestamp(sent_after, tz=timezone.utc)
                if email_dt.date() < sent_after_dt.date():
                    log.debug("Found OTP email from %s but login was triggered today — stale, skipping (%ds left)",
                              email_date_str, remaining)
                    continue
            except (ValueError, IndexError):
                pass  # can't parse date, proceed with the email

        try:
            r2 = subprocess.run(
                ["gog", "gmail", "read", thread_id, "--account", "david@velocityexplorations.com"],
                capture_output=True, text=True, timeout=15
            )
        except subprocess.TimeoutExpired:
            log.warning("gog read timed out — retrying (%ds left)", remaining)
            continue

        if r2.returncode != 0:
            log.debug("gog read failed: %s", r2.stderr[:100])
            continue

        codes = re.findall(r'YOUR AUTHENTICATION CODE:\s*(\d{6})', r2.stdout)
        if codes:
            log.info("Got OTP: %s", codes[-1])
            return codes[-1]
        else:
            log.debug("OTP email found but no code extracted — retrying (%ds left)", remaining)

    log.warning("OTP timeout — no code received within %ds", max_wait)
    return None


def _save_cookies(context):
    """Save browser cookies for session reuse."""
    try:
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        import json
        cookies = context.cookies()
        COOKIE_PATH.write_text(json.dumps(cookies))
        log.debug("Saved %d cookies to %s", len(cookies), COOKIE_PATH)
    except Exception as e:
        log.debug("Could not save cookies: %s", e)


def _load_cookies(context) -> bool:
    """Load saved cookies into browser context. Returns True if cookies were loaded."""
    try:
        if not COOKIE_PATH.exists():
            return False
        import json
        cookies = json.loads(COOKIE_PATH.read_text())
        if not cookies:
            return False
        context.add_cookies(cookies)
        log.debug("Loaded %d saved cookies", len(cookies))
        return True
    except Exception as e:
        log.debug("Could not load cookies: %s", e)
        return False


def _is_logged_in(page) -> bool:
    """Check if current page indicates a logged-in state."""
    url = page.url.lower()
    if "login" in url and "home" not in url:
        return False
    body = page.evaluate("() => document.body.innerText")
    if "sign in" in body.lower()[:200] or "log in" in body.lower()[:200]:
        return False
    return True


def _login(page, context, username: str, password: str) -> bool:
    """
    Log in to Vulcan SOF. Tries saved cookies first, then username/password + OTP.
    Returns True if login succeeded.
    """
    # Try cookie-based session restore first
    if _load_cookies(context):
        log.info("Trying saved session cookies...")
        try:
            page.goto(VULCAN_CALLS, timeout=20000)
            page.wait_for_timeout(3000)
            if _is_logged_in(page):
                log.info("Session restored from cookies — no OTP needed")
                return True
            log.info("Saved cookies expired — falling back to password login")
        except Exception as e:
            log.info("Cookie restore failed (%s) — falling back to password login", e)

    # Fresh login
    log.info("Navigating to Vulcan login page...")
    try:
        page.goto(VULCAN_LOGIN, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
    except Exception as e:
        log.error("Could not load login page: %s", e)
        return False

    # Inspect available inputs for debugging
    input_info = page.evaluate("""
        () => Array.from(document.querySelectorAll('input')).map(el => ({
            type: el.type, name: el.name, placeholder: el.placeholder,
            id: el.id, visible: el.offsetParent !== null,
            ariaLabel: el.getAttribute('aria-label') || '',
        }))
    """)
    log.info("Login page inputs: %s", input_info)

    # Find password input first — it's the most reliable anchor
    pass_input = page.query_selector("input[type='password']")

    # Find username/email input — try specific selectors
    user_input = (
        page.query_selector("input[type='email']")
        or page.query_selector("input[name*='email']")
        or page.query_selector("input[name*='user']")
        or page.query_selector("input[placeholder*='email' i]")
        or page.query_selector("input[placeholder*='user' i]")
        or page.query_selector("input[placeholder*='@']")
        or page.query_selector("input[autocomplete='username']")
        or page.query_selector("input[autocomplete='email']")
    )

    # Fallback: username is the input immediately before the password field
    if not user_input and pass_input:
        all_inputs = page.query_selector_all("input")
        log.info("Username selector missed — finding input before password (%d total inputs)", len(all_inputs))
        for idx, inp in enumerate(all_inputs):
            is_pass = inp.evaluate("(el, target) => el === target", pass_input)
            if is_pass and idx > 0:
                user_input = all_inputs[idx - 1]
                log.info("Using input[%d] as username (before password at [%d])", idx - 1, idx)
                break

    if not user_input or not pass_input:
        log.error("Could not find username/password inputs (user=%s, pass=%s)", bool(user_input), bool(pass_input))
        return False

    log.info("Entering username...")
    login_triggered_at = time.time()
    user_input.fill(username)

    # Password field may become visible after username is filled
    if not pass_input.is_visible():
        log.info("Password input not yet visible — waiting...")
        try:
            page.wait_for_selector("input[type='password']:visible", timeout=10000)
        except Exception:
            pass

    log.info("Entering password...")
    pass_input.fill(password)
    pass_input.press("Enter")
    log.info("Credentials submitted — waiting for response...")
    page.wait_for_timeout(3000)

    body_text = page.evaluate("() => document.body.innerText")
    page_url = page.url

    # Check if OTP is required
    if "passcode" in body_text.lower() or "one-time" in body_text.lower() or "verification" in body_text.lower():
        log.info("OTP required (page: %s) — intercepting from Gmail...", page_url)
        otp = _get_otp_from_gmail(max_wait=90, sent_after=login_triggered_at)
        if not otp:
            log.error("Could not retrieve OTP from Gmail — login aborted")
            return False

        # Find the OTP input — try specific selectors first, fall back to generic
        otp_input = (
            page.query_selector("input[name*='otp']")
            or page.query_selector("input[name*='code']")
            or page.query_selector("input[name*='passcode']")
            or page.query_selector("input[type='tel']")
            or page.query_selector("input[type='number']")
            or page.query_selector("input[type='text']")
            or page.query_selector("input")
        )
        if not otp_input:
            log.error("Could not find OTP input field on page")
            return False

        log.info("Entering OTP code...")
        otp_input.click()
        otp_input.triple_click()
        otp_input.type(otp, delay=80)
        page.wait_for_timeout(800)

        # Find and click the verify/submit button
        log.info("Clicking verify button...")
        clicked = page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button'));
                const verify = btns.find(b => {
                    const txt = b.innerText.trim().toLowerCase();
                    return txt === 'verify' || txt === 'verify code' || txt === 'submit'
                        || txt === 'confirm' || txt === 'continue';
                }) || btns.find(b => b.type === 'submit');
                if (verify) {
                    verify.disabled = false;
                    verify.removeAttribute('disabled');
                    verify.click();
                    return true;
                }
                return false;
            }
        """)
        if not clicked:
            log.warning("Could not find verify button — trying Enter key")
            otp_input.press("Enter")

        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        log.info("Post-OTP page URL: %s", page.url)

    if not _is_logged_in(page):
        body_preview = page.evaluate("() => document.body.innerText.slice(0, 300)")
        log.error("Login failed — still on login page after OTP. URL: %s, body: %s", page.url, body_preview[:150])
        return False

    # Save cookies for next time
    _save_cookies(context)
    log.info("Vulcan login successful")
    return True


def _is_relevant(title: str, description: str = "") -> bool:
    """Check if a call is potentially relevant to Velocity's lane."""
    text = (title + " " + description).lower()
    return any(kw in text for kw in VELOCITY_KEYWORDS)


def _scrape_call(page, url: str, title: str) -> Optional[Dict]:
    """Scrape details from a single call page."""
    try:
        page.goto(url, timeout=15000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        page.wait_for_timeout(1500)

        body = page.evaluate("() => document.body.innerText")

        due_match = re.search(r'Deadline[:\s]*([^\n]+(?:MDT|MST|EST|UTC|202[0-9]))', body)
        due_date = due_match.group(1).strip()[:40] if due_match else ""

        open_match = re.search(r'Open Date[:\s]*([^\n]+(?:MDT|MST|EST|UTC|202[0-9]))', body)
        posted_date = open_match.group(1).strip()[:40] if open_match else ""

        eng_match = re.search(r'Engagement Objectives?[:\s]*\n((?:[^\n]+\n?){1,5})', body)
        opp_type = eng_match.group(1).strip().split('\n')[0].strip()[:60] if eng_match else "Open Call"

        desc_patterns = [
            r'Bottom Line Upfront\s*\n+([\s\S]{100,600}?)(?:\n\n|\Z)',
            r'Problem Statement\s*\n+([\s\S]{100,600}?)(?:\n\n|\Z)',
        ]
        description = ""
        for pattern in desc_patterns:
            m = re.search(pattern, body)
            if m:
                description = m.group(1).strip()[:400]
                break

        uuid_match = re.search(r'collectionUuid=([a-f0-9-]{36})', url)
        call_id = f"vulcan-{uuid_match.group(1)}" if uuid_match else f"vulcan-{hash(url)}"

        return {
            "id": call_id,
            "title": title,
            "portal": "Vulcan SOF",
            "type": opp_type,
            "department": "USSOCOM / SOF Enterprise",
            "naics_code": "",
            "set_aside": "",
            "posted_date": posted_date,
            "due_date": due_date,
            "description": description or body[200:600].strip(),
            "url": url,
            "source_type": "regular",
        }
    except Exception as e:
        log.warning("Failed to scrape call %s: %s", title[:40], e)
        return None


def force_close():
    """Force-close the Playwright browser. Called from main.py on thread timeout."""
    global _active_browser
    if _active_browser:
        try:
            _active_browser.close()
            log.info("Force-closed orphaned Playwright browser")
        except Exception:
            pass
        _active_browser = None


def fetch(
    profile_naics: List[str] = None,
    profile_scrape_keywords: List[str] = None,
    **kwargs,
) -> List[Dict]:
    """Scrape open calls from Vulcan SOF."""
    global _active_browser

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    username, password = _load_creds()
    if not username or not password:
        log.error("VULCAN_SOF_USERNAME or VULCAN_SOF_PASSWORD not set")
        return []

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, timeout=15000)
        _active_browser = browser
        context = browser.new_context()
        page = context.new_page()

        try:
            if not _login(page, context, username, password):
                log.error("Vulcan SOF login failed — skipping")
                browser.close()
                _active_browser = None
                return []

            log.info("Fetching Vulcan SOF call listings...")
            page.goto(VULCAN_CALLS, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page.wait_for_timeout(3000)

            call_links = page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href*="collectionUuid"]')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href
                })).filter(a => a.text && a.href)
            """)

            log.info("Found %d calls on Vulcan SOF", len(call_links))

            log.info("Scraping %d call detail pages...", len(call_links))
            all_scraped = []
            for i, call in enumerate(call_links):
                opp = _scrape_call(page, call['href'], call['text'])
                if opp:
                    all_scraped.append(opp)
                if (i + 1) % 10 == 0:
                    log.info("  Scraped %d/%d calls...", i + 1, len(call_links))
                time.sleep(0.3)

            relevant_calls = [o for o in all_scraped
                              if _is_relevant(o['title'], o.get('description', ''))]
            log.info("Filtered to %d relevant calls (from %d scraped)", len(relevant_calls), len(all_scraped))
            results = relevant_calls

            # Save cookies after successful scrape
            _save_cookies(context)

        except Exception as e:
            log.error("Vulcan SOF scrape error: %s", e)
        finally:
            try:
                browser.close()
            except Exception:
                pass
            _active_browser = None

    log.info("Vulcan SOF: %d opportunities scraped", len(results))
    return results
