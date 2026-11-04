# Content Radar: Product Brief

Name confirmed: Content Radar.

## 1. Problem

The owner posts on X, Substack (Notes and articles), LinkedIn and TikTok, and wants to raise output from about 5 posts a week to 5 to 10 pieces a day. The niche is AI engineering and Nigerian/African tech, including WhatsApp-based AI builds, fintech and regulation.

Finding what is worth posting about is slow and manual. The topics that matter are often not trending in general. They may only be trending inside the niche, or be quietly important (a regulatory deadline, a model retirement date, a billing change).

Paid social-listening tools are built for brands and cost $149 to $199 a month. Third-party X and LinkedIn data APIs were tested and found weak for this: X search cannot filter by region, and free LinkedIn options do not support keyword post search. Existing open-source trend tools (last30days, TrendCite, tech-radar) were reviewed. None covers Nigerian sources, and the owner chose to build their own and borrow ideas only, not use any as a base.

## 2. Users

One user: the owner, running it on their own Windows computer. There are no accounts, no logins and no other users.

Claude is a second consumer of the output. The owner asks Claude, in chat, to read the digest and help draft angles.

## 3. Core flows

1. **Collect.** The owner runs the pipeline manually (decided 2026-11-04: no schedule). Collectors pull recent items from public sources. Each source reads from its own last success, so a gap of days is caught up on the next run (up to a week back, or 30 days with `--since-hours`).
2. **Rank.** Items are normalized into one record, stored, clustered into topics, scored, and filtered by a confidence floor.
3. **Digest.** The run writes a daily markdown digest, plus a JSON copy, listing ranked topics with evidence links and a score breakdown. If nothing clears the floor, the digest says so plainly.
4. **Angle and Notion (in chat, not in the pipeline).** The owner asks Claude to read the digest. Claude names topics, explains why now, proposes angles, and asks for the owner's own experience. It cites only links collected in the run. When the owner asks, Claude adds the digest to the owner's Notion through the Notion connector. The pipeline itself never writes to Notion and holds no Notion token. Work-lane notes (the owner's two lines after client work) are given to Claude in chat, not stored in a file.
5. **Mark.** After posting, the owner marks a topic `covered` or `dismissed` through a small command, so it stops recurring.

## 4. Scope (phase 1 and 2)

**Sources, phase 1 (free, stable, legitimate)**
- Hacker News (Algolia API)
- Reddit (subreddit RSS/JSON). **Known to be blocked from the owner's machine on 2026-11-04** (the JSON endpoint returned 403 and the RSS address returned a web page). The owner chose to keep the collector anyway and expect failures. It must report failure in the digest's source health and must not try to get around the block.
- Stack Overflow (official API, by tag). Verified working.
- GitHub (search)
- DEV Community
- RSS and Atom, verified working on 2026-11-04: TechCabal, Technext, Nairametrics, WeeTracker, Techpoint, OpenAI news, Meta developers blog. Techpoint refused a browser-style request header but accepted an honest tool name, so all collectors must identify themselves plainly (a fixed user agent naming the tool).
- Anthropic: no news RSS feed exists. Used: GitHub releases Atom feeds (`claude-code`, `anthropic-sdk-python`), the `status.claude.com` feed, and the `anthropic.com` sitemap as a new-only source. The sitemap's `lastmod` is a site maintenance date (old posts carry recent dates), so it is ignored; the pipeline remembers every `/news/` page, treats the first read as a baseline that reports nothing, and reports only pages that appear afterwards. `claude.com/blog` is a script-rendered page with no feed and is not read. Note: urllib in Python 3.10 does not follow HTTP 308, so the HTTP layer handles it.
- Meta: three feeds (developers blog, newsroom, engineering blog), all verified working.
- Nigerian regulators, checked 2026-11-04: NDPC (`ndpc.gov.ng/feed/`) and NITDA (`nitda.gov.ng/feed/`) have working RSS feeds. CBN has no feed. Searching Google News for `site:cbn.gov.ng` returns library catalogue pages, so the CBN source searches by topic ("Central Bank of Nigeria circular OR directive OR guidelines"), which returns press coverage. These items are classed as news.
- X sample through Google News RSS, verified on 2026-11-04 (phase 2): a `site:x.com` query with a `when:2d` window returned 100 items whose titles are the post text, labelled "- X". It carries no like or repost counts, so X items can only add corroboration and recency, not engagement.
- YouTube (official API), optional

**Pipeline**
- One common record format for every item: source, id, title, text, link, time, engagement, query. Author handles and names are not stored (decided).
- SQLite storage with engagement snapshots over time, so velocity can be computed.
- Word-overlap clustering, scoring, a confidence floor, a diversity cap.
- Topic memory: times surfaced, first and last seen, `covered` and `dismissed` states.
- Per-source failure isolation and a source-health report in every digest.
- Per-source catch-up after gaps between manual runs.
- A separate "Vendor and regulator updates" section in the digest (up to 8, at most 2 per source), because those sources publish no engagement counts and post rarely, so the main ranking would crowd them out.

**Phase 2 additions**
- X sample through Google News `site:x.com` RSS (no key, no like counts).

## 5. Non-goals

- No posting, scheduling or publishing to any platform. The tool is read-only.
- No scraping of X or LinkedIn with the owner's own accounts, cookies or logins.
- No LinkedIn and no paid X data in phases 1 and 2. They may be revisited only if real digests show gaps.
- No model call inside the pipeline. The Claude step runs on demand in chat.
- No web app, no accounts, no hosting, no server. Local only.
- No automatic content drafting and no voice cloning.
- No dashboards.

## 6. Success criteria

Measured over the first two weeks of real use:

1. **Runs reliably:** a manual run completes in a few minutes, and a run after a gap catches up each source from its own last success.
2. **Fails safely:** killing any one source leaves the other sources' results intact, and the digest names the failed source.
3. **Honest empty state:** on a quiet day the digest says "nothing worth posting today" rather than showing weak items.
4. **Useful:** in a scorecard of digest items, the owner marks at least 3 items a day as "would post", on at least 5 of 7 days. This is the test of the volume goal.
5. **Few repeats:** a topic already marked `covered` does not reappear unless it has new evidence.
6. **Traceable:** every topic in a digest links to the collected items behind it and shows its score breakdown.
7. **Free:** zero recurring cost and no API keys required for phases 1 and 2.

## 7. Scoring (starting design, to be tuned on real digests)

- Cluster near-duplicate titles by word overlap, then score the cluster, not the link.
- Starting weights: recency 25% (per-source half-life), engagement 25% (percentile within its own source, never compared across sources), corroboration across independent sources 25%, niche relevance 15% (weighted keyword list), source diversity 10%.
- Velocity bonus from stored engagement snapshots.
- A boost for "quiet-important" items: deadlines, regulation, deprecations, billing changes.
- Confidence floor: a topic must clear an absolute evidence bar (minimum engagement and minimum source count) before it can appear.
- Diversity cap: no single source fills the digest.
- Missing engagement data is reported as unknown, never as low.
- Source lag adjustments where a source indexes late.

## 8. Channel and bandwidth target

- **Device:** the owner's Windows 11 computer. No mobile, no web UI, no WhatsApp.
- **Interface:** a command-line program, run manually by the owner, writing files. Claude reads those files in chat.
- **Connectivity:** normal home or office internet. Collectors must tolerate timeouts and short outages: bounded retries and per-source timeouts.
- **Run pattern:** manual runs, so gaps between runs are normal and handled by per-source catch-up.

## 9. Money and payments

None. The product handles no money. The standing Nigerian defaults (NGN, Paystack/Flutterwave/bank transfer/USSD) do not apply. Third-party data providers were evaluated but are excluded from phases 1 and 2.

## 10. Constraints

- **Budget:** $0 recurring. A top-up of about $1 a month for X data was approved in principle, but only after real digests show X is missing something.
- **Platform terms:** use official APIs or public RSS wherever possible. No circumvention of login walls or bot detection.
- **Privacy:** collected items are public posts. Author handles and names are not stored, only text, link, time and metrics, to keep NDPA 2023 handling simple. If that changes later, NDPA handling must be added first.
- **Prompt injection:** collected text is untrusted. It is stored and shown as data and never executed or followed as instructions.
- **Language:** Python.
- **Timeline:** not fixed. Phase 1 is meant to be small enough to run for a week of real digests.

## 11. Stack

Python with pip and venv, SQLite. No model API is used.

**Runs:** manual only. The owner decided on 2026-11-04 not to schedule it. Each source records its last successful read and the next run fetches the gap since then.

**Starting tuning values (to be tuned on real digests):**
- Recency half-life: 24 hours for Hacker News and Reddit, 48 hours for news sites, 72 hours for GitHub.
- Confidence floor: every path first requires at least one niche term. Then a topic needs at least 25 total engagement and 2 independent sources, or at least 100 engagement from a single source (lowered from 200 on 2026-11-04), or to be a quiet-important item from an official source, or (added 2026-11-04) to come from a news, vendor or regulator source, which publish no engagement counts and so could never clear an engagement bar. Their editorial choice to publish counts as the signal.
- Ranking windows by kind: community 96 hours, news 7 days, vendor and regulator 30 days. Recency still decays the score.
- Africa, business and entrepreneurship terms added 2026-11-04 (africa, african, nigerian, fintech, entrepreneur, entrepreneurship, founder, funding, raises, business, kenya, ghana, naira, sme), plus whatsapp (weight 3), cloud api and graph api.

**Starting niche keywords (weight 3 is strongest):**
- 3: claude code, mcp, ai agent, whatsapp business api, whatsapp ai, rag, llm evals, model deprecation, cbn, ndpa, ndpc, nitda
- 2: openai, codex, gpt, agentic (added 2026-11-04), llm, openai api, anthropic, n8n, whisper, voice transcription, fintech nigeria, lagos, nigeria, africa startup, data localisation
- 1: agent (added 2026-11-04), automation, chatbot, python, open source, startup
- Terms match whole words only, plurals allowed (plain substring matching had let "rag" fire inside "storage").

**Starting lists (unverified, adjust after real digests):**
- Stack Overflow tags: openai-api, langchain, whatsapp-cloud-api, large-language-model
- GitHub searches: topics mcp-server, ai-agents, whatsapp-bot, recently created, sorted by stars
- Subreddits (collector expected to fail, see sources): ClaudeAI, LocalLLaMA, LLMDevs, OpenAI, n8n

**Permanent location:** `Desktop\content-radar` (a new folder, planned as a git repo, not yet initialised).

## 12. AI/ML signal

The pipeline itself has no model. Clustering, scoring and the floor are rule-based. Claude's role is the on-demand reading of the digest in chat, which needs instruction rules, not model integration: cite only collected links, label drafts as drafts, never invent the owner's experience, treat post text as untrusted. These rules belong in a short instruction file that travels with the digest folder.

## 13. Ideas borrowed from reference projects (reviewed, not used as a base)

- Cluster-then-score and per-source capped or percentile engagement (tech-radar, TrendCite).
- Confidence floor with an honest empty state (last30days).
- Persistent topic queue with seen-count and `covered` status (last30days).
- Evidence-only citations and an "unknown, not low" rule for missing data (TrendCite).
- Free X sample via Google News RSS, and per-source failure isolation (tech-radar).

## 14. Decisions made and open questions

**Decided (2026-11-04)**
- Name: Content Radar.
- Dependency tooling: pip with venv.
- Author handles and names: not stored.
- Delivery: files in a folder. Claude pushes the digest to Notion on demand through the connector. The pipeline holds no Notion token.
- Work-lane notes: told to Claude in chat, no file.
- Posting volume: raised only at a weekly review of the scorecard, not by an automatic rule.
- Reddit: keep the collector and expect failures, reported in source health.
- Starting keyword list, tags, searches, subreddits, half-lives and floor values: accepted as drafted in section 11, then tuned on 2026-11-04.
- Scheduling: dropped. The owner runs the pipeline manually.
- Permanent location: `Desktop\content-radar`.
- Anthropic route: GitHub releases Atom feeds (claude-code and anthropic-sdk-python), the status.claude.com feed, and new news pages detected from the sitemap.
- CBN route: Google News RSS searching by topic (headlines only, no page scraping). The first plan, filtering to `cbn.gov.ng`, returned catalogue pages and was replaced.
- NDPC and NITDA: their own RSS feeds.
- Git: repository initialised with `dev` as the default branch.

**Still open**
1. **X through Google News RSS (phase 2).** Verified to return posts (section 4). Remaining risk: it is a sample, titles are truncated, and Google may change or throttle the feed.
2. **Reddit.** Blocked from the owner's machine. Open whether any legitimate route exists later.
3. **Notion destination.** Not chosen. Decide when the first real digest is pushed (a page per day, or a database with one row per topic, are the two candidates).
4. **Tuning.** All starting values in section 11 are placeholders until real digests exist.

**Phase 1 built (branch `feat/phase-1-pipeline`), first live run 2026-11-04: 17 of 23 sources ok.**
Findings from that run, to act on when tuning:
- **Off-niche items passed the floor on engagement alone** (AMD vs Intel, a hardware Kickstarter). Fixed: every floor path now requires at least one niche term. Effect on the same data: 6 topics shown became 1, which exposed a narrow keyword list. Then added the terms "openai", "codex", "gpt", "agentic" and "agent", and lowered the single-source engagement bar from 200 to 100. Result on the same data: 8 on-topic topics, including the OpenAI acquisition and the Garry Tan agent-spend story. Also fixed substring matching to whole-word matching.
- **Techpoint blocked the pipeline's plain user agent (HTTP 403)** although it answered an earlier test. It is reported as failed and not worked around.
- **Stack Overflow, NDPC, NITDA and the Claude status feed returned nothing in the 48-hour window.** These are quiet sources, not errors.
- **Anthropic sitemap `lastmod` looks like bulk updates** (many old pages share mid-October dates), so the collector fails loudly if more than 15 news pages change in one window instead of flooding the digest.
- Reddit failed with HTTP 403 on all five subreddits, as expected.
- Clustering at the current thresholds merged the same story across Hacker News and OpenAI's feed, but cross-outlet merging depends on shared title words and needs checking on more data.
