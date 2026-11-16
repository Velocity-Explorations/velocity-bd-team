# DSIP: the Defense Department's SBIR and STTR topics

DSIP, the DoD SBIR/STTR Innovation Portal (dodsbirsttr.mil), publishes every DoD SBIR and STTR topic. Each topic is a
call of its own (David, 16 Nov 2026): portal `DSIP`, id `dsip-<topic number in lower case>`, title `<topic number>
<topic title>`, reviewed by Claude and Grok like any call. The AFWERX and SpaceWERX cycle listings stay as umbrella
calls for each release.

## Where the topics come from

DSIP's robots.txt forbids automated access (`Disallow: /` for every agent, checked 16 Nov 2026), and the repository
does not work around a site's block (PRO-536). That rules out any robot on DSIP, a browser driven by an AI included.
So:

1. SBIR.gov's copy. SBIR.gov copies the agencies' topics and its robots.txt allows `/topics`. Each scan reads its list
   of open Department of War topics (`https://www.sbir.gov/topics?status=Open&agency[DOD]=DOD`, ten a page), then each
   topic's page: title, funding agency, topic and solicitation numbers, program, status, release, open and close
   dates, and description. One request a second, about 90 a scan. SBIR.gov says its copies "are not necessarily the
   latest"; the official topic, its questions and answers, and the submission are on DSIP.
2. DSIP's own DOCX, dropped by a person. SBIR.gov can miss a whole release: on 16 Nov 2026 it had all 79 topics of
   Release 2 (27.BZ and 27.TZ) and none of the 23 of Release 1 (27.BZ, 27.BX and 27.TZ). For such a release a person opens DSIP's topic search
   (https://www.dodsbirsttr.mil/topics-app/), downloads each topic with Download Topic Details as DOCX, and saves the
   files in `data/dsip/inbox`. The next scan (Sunday 22:00), or `python run.py --portal dsip`, makes each a call with
   the same id SBIR.gov's copy would get; read files move to `data/dsip/imported`, and files that are not topics to
   `data/dsip/unreadable`. A DOCX has no dates: they come from the AFWERX or SpaceWERX cycle that names its release.
   Where both sources have a topic, SBIR.gov's copy is read last and kept.
3. The watch. After each scan, every open AFWERX or SpaceWERX SBIR or STTR cycle that has been released is checked for
   topics: one DSIP call whose topic number names one of its solicitations and its release. A cycle with none raises a
   Slack alert naming it and the drop folder.

## Topic numbers

Since FY27 a topic number reads component, year, solicitation code, release, track and serial: `DAF27BZ02-DV023` is
the Department of the Air Force, solicitation 27.BZ, Release 2. A code starting B is SBIR and T is STTR; a track
starting D is Direct to Phase II and N is Phase I. Components: ARM Army, DAF Air Force and Space Force, DON Navy, DPA
DARPA, DTR DTRA, MDA Missile Defense Agency, OSW Office of the Secretary of War, SOC SOCOM, and others. Topics numbered
the older way (`HR0011SB20264-01`) take their agency, program and solicitation from SBIR.gov's page.

## The calls

- `due_date` is the close date (DSIP closes at 12:00 p.m. ET); `posted_date` the pre-release date.
- `url` is SBIR.gov's page for the topic, readable without an account; a dropped DOCX topic links DSIP's topic search.
- The description opens with a line naming the program, phase, component, solicitation, release and dates, then the
  topic's description (from a DOCX: objective, description, Phase I and Phase II).
- `extra` keys, all `dsip_`: `dsip_topic`, `dsip_solicitation`, `dsip_release`, `dsip_component`, `dsip_program`,
  `dsip_phase`, `dsip_pre_release`, `dsip_open`, `dsip_source` (`SBIR.gov` or `DSIP DOCX`), `dsip_sbirgov_id`,
  `dsip_itar`, `dsip_cmmc` and `dsip_keywords` (from a DOCX only), and `dsip_closed`. A stored topic past its close
  date is marked closed on the next scan, since SBIR.gov stops listing it.
- Keywords: broad `sbir` and `sttr`, which every description has, so both judges rate every topic. The blocklist is
  empty: the other portals' would drop topics that mention repair or spare parts.

## How to respond

Through DSIP before the topic closes: find the topic in DSIP's topic search, read its solicitation's instructions, and
submit the proposal there. Submitting needs a DSIP account. Questions to a topic's author go through DSIP's topic
Q&A.
