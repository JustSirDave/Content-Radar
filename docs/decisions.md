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

## D-011 — X through Google News: keyword samples plus official accounts, counted as one publisher
Date: 2026-11-04 | Status: approved
Context: The owner wanted to see vendor announcements such as Anthropic's October recap. It was an X post from the Claude Code account, found in the Google News sample but below the floor, because an X post has no engagement counts and a single post alone cannot qualify.
Decision: Enable the X sample (pulled forward from phase 2). Keyword queries stay community kind. Searches scoped to official accounts (ClaudeDevs, claudeai, AnthropicAI, OpenAIDevs, MetaforDevs) are vendor kind and appear in the vendor and regulator section when on topic. All X queries count as one independent publisher so they cannot corroborate each other. "claude" added as a niche term.
Alternatives: Keep X off until phase 2 (hides official announcements); trust query count as corroboration (the same sample counted twice).

## D-012 — Vendor-only topics stay out of the main list
Date: 2026-11-04 | Status: approved
Context: Release notes (for example "Anthropic Python SDK release v2.5.0") and official-account posts took main-list slots, but they are updates to know about, not stories to write about.
Decision: A topic enters the main list only if a community or news source other than the X sample carries it. Topics carried only by vendors, regulators or X posts appear only in the vendor and regulator section.
Alternatives: Keep one mixed list (crowds out stories); exclude release feeds entirely (loses useful updates).

## D-013 — Score weights unchanged; collect marks to tune them on evidence
Date: 2026-11-04 | Status: approved
Context: The owner marked 12 main-list items from titles alone: 10 "post", 2 "no" (CBN data localisation advice, the naira budget story). They said the picks were quick reactions to titles and that they skipped two for having no angle of their own. That is too few misses, and too much about the owner, to fit five weights.
Decision: Leave the weights as they are. Add a `ratings` table (approved by the owner, SQL shown before it was added), a `rate` command that copies the topic's score parts from the latest digest, and a `weights` command that compares score parts for "post" against "no" once there are at least 5 of each.
Alternatives: Retune now on 12 title-based marks (would encode a guess); tune by hand without data.

## D-014 — Notion: one page per day, named by date, under one parent page
Date: 2026-11-05 | Status: approved
Context: The Notion destination was open. The owner chose to start with the simpler layout and review it after use.
Decision: Each pushed digest is a Notion sub-page named with its date (YYYY-MM-DD) under a parent page "Content Radar digests". Claude pushes on request; the pipeline still never writes to Notion. A database with one row per topic stays an option once the page layout has been tried.
Alternatives: A database row per topic (filters and statuses, but Notion and the local database would drift apart because nothing syncs back).

## D-015 — Digest topics are grouped into categories by rule
Date: 2026-11-05 | Status: approved
Context: The owner wanted the digest categorised. Claude had grouped one digest by hand when pushing it to Notion.
Decision: The pipeline assigns categories itself, from rules in `radar/config.py`. Main list: "Nigeria policy and economy", "Africa tech and business", "AI engineering and agents", "AI companies and models", chosen by the category with the most matched niche-term weight (ties go to the earlier category; no match shows as "Uncategorised"). Vendor and regulator section: grouped by source (Anthropic and Claude, OpenAI, Meta, Nigerian regulators; no match shows as "Other updates"). Each topic in the JSON digest carries its `category`. Tests check that every niche term has a category and every official source has a vendor group.
Alternatives: Group by hand when pushing (inconsistent between days); group by source only (misses the topic split the owner wants).

## D-016 — X and LinkedIn are an open workstream, not parked
Date: 2026-11-05 | Status: approved
Context: D-005 deferred X and LinkedIn data. The owner corrected that they are not parked. Today X is covered only by a Google News sample (text, no counts), and LinkedIn is not covered at all. Third-party data APIs were tested earlier and judged weak.
Decision: Treat both as work still to plan. No approach is chosen yet.
Alternatives: None decided.
