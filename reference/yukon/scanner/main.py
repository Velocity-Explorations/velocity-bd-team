"""
Yukon — Government Procurement Portal Scanner
Usage:
  python scanner/main.py --profile velocity
  python scanner/main.py --profile velocity --dry-run
  python scanner/main.py --profile velocity --cadence nightly
  python scanner/main.py --all

Debug / troubleshooting:
  python scanner/main.py --profile velocity --portal sam_gov --no-review --dry-run
  YUKON_SAM_MAX_PAGES=1 python scanner/main.py --profile velocity --portal sam_gov --dry-run
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scanner.profile import load_profile, list_profiles
from scanner.dedup import DedupStore
from scanner.filter import filter_opportunities
from scanner.alert import send_alerts, send_slack_alerts, _format_opp
from scanner.velocity_scorer import score_opportunities as velocity_score_opportunities
from scanner.profile_scorer import score_opportunities as profile_score_opportunities
from scanner.scorer import rank_opportunities, top_picks  # fallback
from scanner.review import review_opportunities
from scanner.summarize import summarize_opportunities
from scanner.sheet import append_opportunities, write_forecast, write_forecasts
from scanner.api_sink import start_run, complete_run, ingest_opportunities, report_progress, post_raw_listings, update_listing_status
from scanner.forecast_xref import run_crossref
from typing import List
from scanner.portals import sam_gov, nstxl, diu, bidnet, space_florida, nasa_forecast, vulcan_sof, iarpa, afwerx, ac_cto, doe_sbir, space_force

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("yukon")

DISCORD_API = "https://discord.com/api/v10"


def _post_top5(picks: List, channel_id: str, dry_run: bool):
    """Post the Top 5 curated picks as a single Discord summary message."""
    import requests, os, time
    from pathlib import Path
    from dotenv import load_dotenv

    if not picks:
        return

    lines = ["🏔️ **Yukon Top 5 — Today's Best Picks**\n"]
    for i, opp in enumerate(picks, 1):
        title = opp.get("title", "?")[:80]
        portal = opp.get("portal", "?")
        due = opp.get("due_date", "") or "TBD"
        score = opp.get("yukon_score", "?")
        reasoning = opp.get("yukon_reasoning", "")
        url = opp.get("url", "")

        lines.append(f"**#{i} — {title}**")
        lines.append(f"Portal: {portal} | Due: {due} | Score: {score}")
        lines.append(f"Why: {reasoning}")
        if url:
            lines.append(f"🔗 <{url}>")
        lines.append("")

    message = "\n".join(lines)

    if dry_run:
        print("\n" + "="*60)
        print("TOP 5 PICKS (dry run)")
        print("="*60)
        print(message)
        return

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        log.error("Top 5: no Discord bot token found")
        return

    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    url_api = f"{DISCORD_API}/channels/{channel_id}/messages"
    resp = requests.post(url_api, headers=headers, json={"content": message}, timeout=10)
    if resp.status_code != 200:
        log.error(f"Top 5 post failed: {resp.status_code}")



def run_profile(
    profile_name: str,
    cadence_filter: str,
    dry_run: bool,
    dedup: DedupStore,
    sheet_only: bool = False,
    portal_filter: str = None,
    use_llm: bool = True,
    sam_resume: bool = False,
    sam_reset_checkpoint: bool = False,
    skip_fetch: bool = False,
):
    log.info(f"=== Running profile: {profile_name} ===")
    if portal_filter:
        log.info(f"Portal filter: {portal_filter}")
    if not use_llm:
        log.info("LLM review: DISABLED (--no-review)")

    try:
        profile = load_profile(profile_name, PROJECT_ROOT)
    except FileNotFoundError as e:
        log.error(str(e))
        return 0, 0, 0

    new_count = 0
    seen_count = 0
    skipped_count = 0
    all_new_opps = []  # Collect all new opps across portals for scoring
    profile_start = time.monotonic()

    # Create API run upfront for live progress tracking
    api_run_id = start_run(profile_name, metadata={
        "cadence": cadence_filter,
        "portal_filter": portal_filter,
        "dry_run": dry_run,
    }, profile=profile_name) if not dry_run else None
    if api_run_id:
        report_progress(api_run_id, "started", status="running",
                        message=f"Starting scan for profile: {profile_name}")

    for portal in profile.portals:
        # Portal filter (--portal flag)
        if portal_filter and portal.id != portal_filter:
            log.debug(f"Skipping {portal.name} (portal filter: {portal_filter})")
            skipped_count += 1
            continue

        # Cadence filter
        if cadence_filter != "all" and portal.cadence != cadence_filter:
            log.debug(f"Skipping {portal.name} (cadence={portal.cadence}, filter={cadence_filter})")
            skipped_count += 1
            continue

        log.info(f"── Portal: {portal.name} ({portal.cadence}) ──")
        if api_run_id:
            report_progress(api_run_id, "portal_start", portal=portal.name, status="running",
                            message=f"Scanning {portal.name}")

        # ── Phase: FETCH ──
        fetch_cache_dir = PROJECT_ROOT / "data" / "fetch_cache"
        fetch_cache_file = fetch_cache_dir / f"{profile_name}_{portal.id}.json"

        if skip_fetch:
            if fetch_cache_file.exists():
                with open(fetch_cache_file) as f:
                    opps = json.load(f)
                log.info(f"  FETCH (cached): loaded {len(opps)} raw opps from {fetch_cache_file.name}")
            else:
                log.warning(f"  FETCH (cached): no cache file for {portal.id}, skipping portal")
                skipped_count += 1
                continue
        else:
            t0 = time.monotonic()

            def _do_fetch():
                if portal.id == "sam_gov":
                    api_key = os.environ.get("SAM_GOV_API_KEY")
                    return sam_gov.fetch(
                        profile_naics=profile.naics,
                        api_key=api_key,
                        resume=sam_resume,
                        reset_checkpoint=sam_reset_checkpoint,
                    )
                elif portal.id == "nstxl":
                    return nstxl.fetch(profile_keywords=profile.keywords)
                elif portal.id == "diu":
                    return diu.fetch(profile_keywords=profile.scrape_keywords)
                elif portal.id in ("bidnet_colorado", "bidnet_florida"):
                    return bidnet.fetch(url=portal.url)
                elif portal.id == "space_florida":
                    return space_florida.fetch(profile_keywords=profile.scrape_keywords)
                elif portal.id == "nasa_forecast":
                    return nasa_forecast.fetch(profile_naics=profile.naics, profile_scrape_keywords=profile.scrape_keywords)
                elif portal.id == "vulcan_sof":
                    return vulcan_sof.fetch(profile_naics=profile.naics, profile_scrape_keywords=profile.scrape_keywords)
                elif portal.id == "iarpa":
                    return iarpa.fetch()
                elif portal.id == "strikewerx":
                    return afwerx.fetch()
                elif portal.id == "ac_cto":
                    return ac_cto.fetch()
                elif portal.id == "doe_sbir":
                    return doe_sbir.fetch()
                elif portal.id == "space_force":
                    return space_force.fetch()
                return None

            # SAM.gov manages its own per-request timeouts and key rotation internally;
            # wrapping it in a ThreadPoolExecutor timeout kills it mid-fetch (~11min total).
            # Other portals get a safety timeout: 5 min for Playwright, 2 min for HTTP scrapers.
            try:
                if portal.id == "sam_gov":
                    opps = _do_fetch()
                else:
                    fetch_timeout = 300 if portal.id in ("vulcan_sof", "iarpa") else 120
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_do_fetch)
                        opps = future.result(timeout=fetch_timeout)
                if opps is None:
                    log.info(f"Skipping {portal.name} — adapter not yet implemented")
                    skipped_count += 1
                    continue
            except FuturesTimeout:
                log.error(f"  FETCH TIMEOUT: {portal.name} exceeded {fetch_timeout}s — skipping")
                if portal.id == "vulcan_sof":
                    try:
                        vulcan_sof.force_close()
                    except Exception:
                        pass
                if api_run_id:
                    report_progress(api_run_id, "fetch", portal=portal.name, count=0, status="error",
                                    message=f"Timeout after {fetch_timeout}s — portal skipped")
                skipped_count += 1
                continue
            except Exception as e:
                log.error(f"  FETCH ERROR: {portal.name} — {e}")
                if api_run_id:
                    report_progress(api_run_id, "fetch", portal=portal.name, count=0, status="error",
                                    message=f"Error: {str(e)[:200]}")
                skipped_count += 1
                continue

            log.info(f"  FETCH: {len(opps)} raw opps ({time.monotonic() - t0:.1f}s)")
            if api_run_id:
                report_progress(api_run_id, "fetch", portal=portal.name, count=len(opps),
                                message=f"Fetched {len(opps)} raw opportunities from {portal.name}")

            # Cache raw fetch results for --skip-fetch reruns
            fetch_cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                with open(fetch_cache_file, "w") as f:
                    json.dump(opps, f)
                log.info(f"  FETCH: cached {len(opps)} opps to {fetch_cache_file.name}")
            except Exception as e:
                log.warning(f"  FETCH: failed to cache opps: {e}")

            # Save raw listings for audit trail
            if api_run_id and opps and not dry_run:
                post_raw_listings(opps, portal.name, scan_run_id=api_run_id, profile=profile_name)

        # ── Phase: FILTER ──
        t0 = time.monotonic()
        filtered = filter_opportunities(opps, profile, portal_id=portal.id)
        log.info(f"  FILTER: {len(filtered)} passed of {len(opps)} ({time.monotonic() - t0:.1f}s)")
        if api_run_id:
            report_progress(api_run_id, "filter", portal=portal.name, count=len(filtered),
                            message=f"{len(filtered)} of {len(opps)} passed filtering",
                            detail={"raw": len(opps), "passed": len(filtered)})

        # Update raw listing statuses for filtered-out opps
        if api_run_id and not dry_run:
            rejected_opps = [o for o in opps if o not in filtered]
            if rejected_opps:
                updates = [{
                    "portal": portal.name,
                    "nativeId": o.get("id", ""),
                    "filterResult": "filtered",
                    "filterReason": o.get("_filter_reason", ""),
                } for o in rejected_opps]
                update_listing_status(updates, api_run_id)

        # ── Phase: ATTACHMENTS (SAM.gov only) ──
        pre_attachment_opps = []
        if portal.id == "sam_gov" and filtered:
            from scanner.attachments import enrich_with_attachments, cleanup_rejected
            t0 = time.monotonic()
            pre_attachment_opps = list(filtered)
            att_key = os.environ.get("SAM_GOV_RFP_AGENT_KEY", "")
            if not att_key:
                env_path = os.path.join(os.path.dirname(__file__), "..", "configs", "velocity", ".env")
                env_path = os.path.normpath(env_path)
                if os.path.exists(env_path):
                    for line in open(env_path).read().splitlines():
                        if line.strip().startswith("SAM_GOV_RFP_AGENT_KEY="):
                            att_key = line.strip().split("=", 1)[1].strip()
                            break
            att_api_keys = [att_key] if att_key else sam_gov._load_api_keys()
            enrich_with_attachments(filtered, att_api_keys)
            enriched = sum(1 for o in filtered if o.get("attachment_text"))
            log.info(f"  ATTACHMENTS: {enriched}/{len(filtered)} opps enriched ({time.monotonic() - t0:.1f}s)")
            if api_run_id:
                report_progress(api_run_id, "attachments", portal=portal.name, count=enriched,
                                message=f"{enriched}/{len(filtered)} opps enriched with attachment text")

        # ── Phase: REVIEW ──
        t0 = time.monotonic()
        pre_review = list(filtered)
        filtered = review_opportunities(filtered, use_llm=use_llm, profile=profile_name)
        log.info(f"  REVIEW: {len(filtered)} passed ({time.monotonic() - t0:.1f}s)")
        if api_run_id:
            report_progress(api_run_id, "review", portal=portal.name, count=len(filtered),
                            message=f"{len(filtered)} passed LLM review")

        # Update raw listing statuses for review-rejected opps
        if api_run_id and not dry_run:
            reviewed_out = [o for o in pre_review if o not in filtered]
            if reviewed_out:
                updates = [{
                    "portal": portal.name,
                    "nativeId": o.get("id", ""),
                    "filterResult": "reviewed_out",
                    "filterReason": "LLM review rejected",
                } for o in reviewed_out]
                update_listing_status(updates, api_run_id)

        # ── Cleanup rejected attachment files ──
        if pre_attachment_opps:
            rejected_att = [o for o in pre_attachment_opps if o not in filtered]
            cleanup_rejected(rejected_att)
            kept = sum(1 for o in filtered if o.get("_attachment_paths"))
            log.info(f"  ATTACHMENTS: kept files for {kept} valid opps, cleaned up {len(rejected_att)} rejected")

        # ── Phase: DEDUP ──
        t0 = time.monotonic()
        new_opps = []
        portal_seen = 0
        deduped_opps = []
        for opp in filtered:
            opp_id = opp.get("id", "")
            if not opp_id:
                continue
            if dedup.is_seen(opp_id, profile_name):
                seen_count += 1
                portal_seen += 1
                deduped_opps.append(opp)
            else:
                new_opps.append(opp)
        log.info(f"  DEDUP: {len(new_opps)} new, {portal_seen} already seen ({time.monotonic() - t0:.1f}s)")
        if api_run_id:
            report_progress(api_run_id, "dedup", portal=portal.name, count=len(new_opps),
                            message=f"{len(new_opps)} new, {portal_seen} already seen",
                            detail={"new": len(new_opps), "seen": portal_seen})

        # Update raw listing statuses for deduped opps
        if api_run_id and not dry_run and deduped_opps:
            updates = [{
                "portal": portal.name,
                "nativeId": o.get("id", ""),
                "filterResult": "deduped",
                "filterReason": "already seen in previous run",
            } for o in deduped_opps]
            update_listing_status(updates, api_run_id)

        # Opps go to Inbox sheet ONLY — no direct Slack/Discord alerts.
        # Slack alerts fire AFTER dpw reviews + approves via process_inbox.py.
        if new_opps:
            # Mark as seen
            if not dry_run:
                for opp in new_opps:
                    dedup.mark_seen(
                        opp_id=opp["id"],
                        portal=opp["portal"],
                        title=opp.get("title", ""),
                        url=opp.get("url", ""),
                        profile=profile_name,
                    )

            new_count += len(new_opps)
            all_new_opps.extend(new_opps)

    # Split forecast opps from regular opps
    forecast_opps = [o for o in all_new_opps if o.get("source_type") == "forecast"]
    regular_opps = [o for o in all_new_opps if o.get("source_type") != "forecast"]

    # ── Phase: SCORE ──
    if regular_opps:
        t0 = time.monotonic()
        log.info(f"── Scoring {len(regular_opps)} new opportunities ──")
        if profile_name == "velocity":
            ranked = velocity_score_opportunities(regular_opps)
        else:
            ranked = profile_score_opportunities(regular_opps, profile_name, profile=profile, project_root=PROJECT_ROOT)
        log.info(f"  SCORE: done ({time.monotonic() - t0:.1f}s)")
        if api_run_id:
            report_progress(api_run_id, "score", count=len(ranked),
                            message=f"Scored {len(ranked)} opportunities",
                            detail={"top_score": ranked[0].get("yukon_score") if ranked else None})

        # ── Phase: SUMMARIZE ──
        t0 = time.monotonic()
        ranked = summarize_opportunities(ranked)
        log.info(f"  SUMMARIZE: done ({time.monotonic() - t0:.1f}s)")
        if api_run_id:
            report_progress(api_run_id, "summarize", count=len(ranked),
                            message=f"Summarized {len(ranked)} opportunity descriptions")

        # ── Phase: INGEST (API + Sheet) ──
        t0 = time.monotonic()

        # POST to Yukon Prospector API
        log.info("── Ingesting to Yukon Prospector API ──")
        if api_run_id:
            report_progress(api_run_id, "ingest", status="running",
                            message=f"Ingesting {len(ranked)} opportunities to database")
        api_written = ingest_opportunities(ranked, scan_run_id=api_run_id, dry_run=dry_run, profile=profile_name)
        log.info(f"  API: {api_written} opportunities ingested ({time.monotonic() - t0:.1f}s)")

        # Mark ingested opps in raw listings
        if api_run_id and not dry_run:
            updates = [{
                "portal": o.get("portal", ""),
                "nativeId": o.get("id", ""),
                "filterResult": "ingested",
                "filterReason": "",
            } for o in ranked]
            update_listing_status(updates, api_run_id)

        # Also write to Google Sheet (legacy — can be removed once web UI is primary)
        t0 = time.monotonic()
        log.info("── Writing to Google Sheet ──")
        append_opportunities(ranked, dry_run=dry_run)
        log.info(f"  SHEET: {len(ranked)} rows written ({time.monotonic() - t0:.1f}s)")

        # Post Top 5 to Discord as curated summary (skip in sheet-only mode)
        if not sheet_only:
            picks = ranked[:5]
            log.info(f"Posting Top 5 picks to Discord...")
            _post_top5(picks, profile.discord_channel, dry_run=dry_run)

    # Write forecast opps to Forecasts tab
    if forecast_opps:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log.info(f"── Writing {len(forecast_opps)} forecasts ──")
        written = write_forecasts(forecast_opps, today, dry_run=dry_run)
        log.info(f"  FORECAST SHEET: {written} rows written")

        # Run SAM.gov cross-reference after writing new forecasts
        log.info("── SAM.gov cross-reference ──")
        try:
            xref_result = run_crossref(profile_name, dry_run=dry_run)
            if xref_result:
                matched, no_match, total = xref_result
                log.info(f"  XREF: {matched}/{total} forecasts found as live solicitations on SAM.gov")
        except Exception as e:
            log.warning(f"Cross-reference failed (non-fatal): {e}")

    elapsed = time.monotonic() - profile_start
    log.info(f"=== Profile {profile_name} complete: {new_count} new, {seen_count} seen, {skipped_count} skipped ({elapsed:.1f}s) ===")

    if api_run_id:
        report_progress(api_run_id, "complete", count=new_count,
                        message=f"Scan complete: {new_count} new, {seen_count} seen, {skipped_count} skipped ({elapsed:.0f}s)",
                        detail={"new": new_count, "seen": seen_count, "skipped": skipped_count, "elapsed_s": round(elapsed, 1)})
        complete_run(api_run_id, status="completed")

    return new_count, seen_count, skipped_count


def _post_discord_summary(message: str):
    """Post completion summary directly to the #yukon thread — bypass cron delivery."""
    import requests
    from pathlib import Path

    YUKON_THREAD = "1483788952640159824"
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        log.error("No Discord bot token — cannot post summary to #yukon")
        return

    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    url = f"{DISCORD_API}/channels/{YUKON_THREAD}/messages"
    resp = requests.post(url, headers=headers, json={"content": message}, timeout=10)
    if resp.status_code == 200:
        log.info("Completion summary posted to #yukon thread")
    else:
        log.error(f"Summary post failed: {resp.status_code} {resp.text[:100]}")

def main():
    # ── Run lock — prevent double execution ──────────────────────────────────
    import fcntl
    lock_path = PROJECT_ROOT / "data" / "yukon.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("⚠️  Yukon is already running (lock held). Exiting to prevent double run.")
        log.warning("Yukon already running — exiting (lock held at %s)", lock_path)
        sys.exit(0)
    # ─────────────────────────────────────────────────────────────────────────

    # Load profile env vars (SAM_GOV_API_KEY, SLACK_WEBHOOK_BD_PROSPECTOR, etc.)
    from dotenv import load_dotenv
    _profile_env = PROJECT_ROOT / "configs" / "velocity" / ".env"
    if _profile_env.exists():
        load_dotenv(_profile_env)

    parser = argparse.ArgumentParser(
        description="🏔️ Yukon — Government Procurement Portal Scanner"
    )
    parser.add_argument("--profile", help="Profile name (folder under configs/)")
    parser.add_argument("--all", action="store_true", help="Run all profiles")
    parser.add_argument("--dry-run", action="store_true", help="Print alerts, don't post to Discord")
    parser.add_argument("--sheet-only", action="store_true", help="Write to sheet only, skip Discord and Slack alerts")
    parser.add_argument(
        "--cadence",
        choices=["nightly", "weekly", "all"],
        default="all",
        help="Only run portals with this cadence (default: all)",
    )
    parser.add_argument(
        "--portal",
        help="Run only this portal (e.g. sam_gov, nstxl, diu)",
    )
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Skip LLM review (Stage 2) — blocklist still runs",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume supported portal fetches from checkpoint state when available",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Clear existing checkpoint state before running supported portal fetches",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetch stage, load raw opps from last cached fetch (data/fetch_cache/)",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run score calibration from triage data after scan completes",
    )
    args = parser.parse_args()

    if not args.profile and not args.all:
        parser.print_help()
        sys.exit(1)

    if args.dry_run:
        log.info("DRY RUN — no Discord messages will be sent")
    if args.no_review:
        log.info("LLM review DISABLED via --no-review")
    if args.portal:
        log.info(f"Portal filter: --portal {args.portal}")
    if args.resume:
        log.info("Checkpoint resume ENABLED")
    if args.reset_checkpoint:
        log.info("Checkpoint reset requested before run")
    if args.skip_fetch:
        log.info("Fetch stage SKIPPED — loading from cached fetch results")

    dedup = DedupStore(PROJECT_ROOT / "data" / "seen_opps.db")

    if args.all:
        profiles = list_profiles(PROJECT_ROOT)
        if not profiles:
            log.error("No profiles found in configs/")
            sys.exit(1)
        log.info(f"Running all profiles: {profiles}")
    else:
        profiles = [args.profile]

    total_new = total_seen = total_skipped = 0

    for profile_name in profiles:
        n, s, sk = run_profile(
            profile_name,
            args.cadence,
            args.dry_run,
            dedup,
            sheet_only=getattr(args, 'sheet_only', False),
            portal_filter=args.portal,
            use_llm=not args.no_review,
            sam_resume=args.resume,
            sam_reset_checkpoint=args.reset_checkpoint,
            skip_fetch=args.skip_fetch,
        )
        total_new += n
        total_seen += s
        total_skipped += sk

    # Run calibration if requested
    if getattr(args, 'calibrate', False):
        from scanner.calibration import generate_calibration
        log.info("── Running score calibration ──")
        for profile_name in profiles:
            try:
                cal = generate_calibration(profile_name, PROJECT_ROOT)
                if cal:
                    log.info(f"  Calibration for {profile_name}: {cal['sample_size']} decisions, "
                             f"{len(cal['keyword_adjustments'])} keyword adjustments")
                else:
                    log.info(f"  Calibration skipped for {profile_name} (insufficient data)")
            except Exception as e:
                log.error(f"  Calibration failed for {profile_name}: {e}")

    # dpw's Discord user ID — mention triggers a notification
    DPW_MENTION = "<@345965141612953600>"

    # Key rotation summary — show which keys were used and request counts
    from scanner.portals import sam_gov as _sam_gov
    key_info = ""
    if _sam_gov._requests_used > 0:
        keys_used = _sam_gov._load_api_keys()
        key_count = len(keys_used)
        key_info = f"\n- SAM.gov API: {_sam_gov._requests_used} requests used"
        if key_count > 1:
            key_info += f" ({key_count} keys available for rotation)"

    resume_info = ""
    if args.resume and _sam_gov._resume_loaded:
        skipped = _sam_gov._resume_skipped_ptypes
        cleared = _sam_gov._resume_cleared
        resume_info = f"\n- SAM.gov resume: skipped {len(skipped)} completed ptype(s) {skipped}, checkpoint {'cleared' if cleared else 'retained'}"

    summary = (
        f"{DPW_MENTION} 🏔️ **Yukon nightly scan complete**\n"
        f"- New opps: {total_new} | Already seen: {total_seen} | Portals skipped: {total_skipped}"
        f"{key_info}"
        f"{resume_info}"
    )
    if total_new > 0:
        summary += "\n- Review sheet: <https://docs.google.com/spreadsheets/d/1loGmTp3jxfKqT9z5dfoYg9NAdliRXsccq7QtmdjYOw0/edit>"
    print(f"\n{summary}")
    if not args.dry_run and not getattr(args, 'sheet_only', False):
        _post_discord_summary(summary)


if __name__ == "__main__":
    main()
