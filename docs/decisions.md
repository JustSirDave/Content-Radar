# Decisions Log

## D-001 — Build a custom local pipeline, no existing tool as a base
Date: 2026-11-04 | Status: approved
Context: Third-party X and LinkedIn data APIs were tested or researched and found weak for this niche (X search has no region filter; free LinkedIn options lack keyword post search). Existing open-source trend tools were reviewed.
Decision: Build a custom pipeline. Borrow ideas only from last30days, TrendCite and tech-radar.
Alternatives: Use last30days as the engine (rejected by the owner, who wants no base project); paid listening tools such as BuzzSumo or Brand24 (built for brands, $149 to $199 a month).
Sources: https://github.com/mvanhorn/last30days-skill, https://github.com/Abaco3300/trendcite, https://github.com/AboALhasanx/tech-radar

## D-002 — Python, local runs, Claude on demand
Date: 2026-11-04 | Status: approved (the scheduling part is superseded by D-008)
Context: The owner wants zero recurring cost and no keys to manage.
Decision: Python with pip and venv, SQLite, Windows Task Scheduler every 4 hours with catch-up. No model call in the pipeline. Claude reads the digest on demand in chat.
Alternatives: TypeScript (fewer text-processing libraries); GitHub Actions (rejected, owner chose local); Anthropic API inside the pipeline (rejected for cost and key management).

## D-003 — Delivery to Notion through Claude, not the pipeline
Date: 2026-11-04 | Status: approved
Context: The owner wants digests in Notion. A direct write from the pipeline needs a stored Notion integration token.
Decision: The pipeline writes files only. Claude adds the digest to Notion on request through the connector.
Alternatives: Pipeline writes to Notion itself (needs a token, breaks the no-keys goal).

## D-004 — Do not store author handles or names
Date: 2026-11-04 | Status: approved
Context: Collected items are public posts, but handles and names are personal data under NDPA 2023.
Decision: Store only text, link, time, engagement metrics and the query that found the item.
Alternatives: Store handles to see who drives a topic (rejected for added NDPA handling).

## D-005 — X and LinkedIn deferred; keep Reddit collector despite blocking
Date: 2026-11-04 | Status: approved
Context: Sorsa results were poor for Africa. LinkedIn free options do not support keyword post search. Reddit blocked unauthenticated requests from the owner's machine on 2026-11-04.
Decision: No LinkedIn or paid X in phases 1 and 2. X sample through Google News RSS is a phase 2 candidate (verified on 2026-11-04 to return post text, with no engagement counts). Keep the Reddit collector, report failures in source health, and do not circumvent the block.
Alternatives: Drop Reddit (the recommended option, not chosen by the owner); Reddit official API (needs approval and a key).

## D-006 — Routes for sources without a news feed (Anthropic, CBN)
Date: 2026-11-04 | Status: approved
Context: Anthropic has no news RSS feed (four guessed addresses returned 404). CBN has no feed either. NDPC and NITDA do.
Decision: Anthropic uses the GitHub releases Atom feeds (claude-code, anthropic-sdk-python), the status.claude.com feed, and new news pages detected from anthropic.com/sitemap.xml. CBN uses Google News RSS filtered to cbn.gov.ng (later changed: that returned library catalogue pages, so it now searches by topic, "Central Bank of Nigeria circular OR directive OR guidelines"). NDPC and NITDA use their own feeds.
Alternatives: Parse CBN's HTML circulars page (exact titles, but breaks when the layout changes); Anthropic GitHub and status feeds only (misses model and product announcements).

## D-007 — Git repository on dev, docs committed first
Date: 2026-11-04 | Status: approved
Context: The owner asked for the repo to be initialised now.
Decision: Initialise git in Desktop\content-radar with dev as the default branch and commit the docs. Nothing is pushed. The owner opens and merges pull requests.
Alternatives: Wait until the first build task (rejected by the owner).

## D-008 — Manual runs only, no schedule
Date: 2026-11-04 | Status: approved
Context: The owner prefers to run the pipeline by hand.
Decision: No Windows scheduled task. The scheduler script was removed. Per-source catch-up stays, because gaps of days between manual runs are normal.
Alternatives: Windows Task Scheduler every 4 hours (the earlier plan, in D-002).

## D-009 — News, vendor and regulator items pass the floor on editorial signal, in their own section
Date: 2026-11-04 | Status: approved
Context: The first digests showed no Africa, business, Meta or Anthropic news. News sites, vendors and regulators publish no engagement counts, so a single source could never clear an engagement-based floor, and low-engagement items from rare sources were crowded out of the top 12.
Decision: Items from news, vendor and regulator sources pass the floor if they match a niche term. Africa, business, WhatsApp and entrepreneurship terms were added. Vendor and regulator items are shown in a separate section (up to 8, at most 2 per source) with a 30-day window.
Alternatives: Lower the engagement bar for everything (would let noise through); leave as is (hid exactly the sources the owner wants).

## D-010 — Anthropic news detected by first-seen pages, not by sitemap dates
Date: 2026-11-04 | Status: approved
Context: Anthropic has no news feed. Its sitemap `lastmod` carries site maintenance dates (old posts such as "Claude's constitution" had recent dates), so dates cannot identify new posts.
Decision: Remember every `/news/` page. The first read is a baseline and reports nothing. Later runs report only pages not seen before. Posts published before the baseline are not recovered automatically.
Alternatives: Trust `lastmod` (flooded the digest with old posts); read `claude.com/blog` (script-rendered, no feed).
