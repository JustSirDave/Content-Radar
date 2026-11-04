"""Starting values from docs/brief.md section 11. All are placeholders to tune on real digests."""

from __future__ import annotations

USER_AGENT = "ContentRadar/0.1 (personal research tool; read-only)"
HTTP_TIMEOUT_SECONDS = 20
HTTP_RETRIES = 2

DEFAULT_LOOKBACK_HOURS = 48  # used when a source has never succeeded
MAX_LOOKBACK_HOURS = 24 * 7  # catch-up never reaches further back than a week
OVERLAP_HOURS = 1  # re-read a little before the last success so nothing slips through
RANK_WINDOW_HOURS = 96  # items older than this are not ranked

# Niche keywords: weight 3 is strongest.
NICHE_TERMS: dict[str, int] = {
    "claude code": 3, "mcp": 3, "ai agent": 3, "whatsapp business api": 3,
    "whatsapp ai": 3, "rag": 3, "llm evals": 3, "model deprecation": 3,
    "cbn": 3, "ndpa": 3, "ndpc": 3, "nitda": 3,
    "llm": 2, "openai api": 2, "anthropic": 2, "n8n": 2, "whisper": 2,
    "voice transcription": 2, "fintech nigeria": 2, "lagos": 2, "nigeria": 2,
    "africa startup": 2, "data localisation": 2, "data localization": 2,
    "automation": 1, "chatbot": 1, "python": 1, "open source": 1, "startup": 1,
}
NICHE_SATURATION = 6  # matched weight at which relevance reaches 1.0

# Items that matter without spiking: deadlines, regulation, retirements, billing.
QUIET_IMPORTANT_TERMS = (
    "deprecat", "retire", "sunset", "shut down", "shutdown", "deadline", "effective",
    "circular", "directive", "guideline", "regulation", "compliance", "billing",
    "pricing change", "will be removed", "end of life",
)
OFFICIAL_KINDS = {"vendor", "regulator", "news"}

# Half-life in hours, by source prefix.
HALF_LIFE_HOURS: dict[str, float] = {
    "hackernews": 24, "reddit": 24, "devto": 48, "stackoverflow": 48,
    "rss": 48, "gnews": 48, "anthropic_sitemap": 48, "github": 72,
}

# Score weights (sum to 1.0). Missing components are dropped and the rest renormalised.
WEIGHTS = {
    "recency": 0.25, "engagement": 0.25, "corroboration": 0.25,
    "relevance": 0.15, "diversity": 0.10,
}
VELOCITY_MAX_BONUS = 8.0
VELOCITY_SATURATION_PER_HOUR = 10.0
QUIET_IMPORTANT_BONUS = 10.0

CLUSTER_JACCARD = 0.35
CLUSTER_MIN_SHARED_TOKENS = 3

# Confidence floor.
FLOOR_MIN_ENGAGEMENT = 25.0
FLOOR_MIN_SOURCES = 2
FLOOR_SINGLE_SOURCE_ENGAGEMENT = 200.0

TOP_N = 12
MAX_SOURCE_SHARE = 0.4  # no single source may fill more than this share of the digest

TOPIC_MATCH_JACCARD = 0.5
TOPIC_MEMORY_DAYS = 14

# --- Sources -------------------------------------------------------------------------

# (name, url, kind, title_prefix)
FEEDS: list[tuple[str, str, str, str]] = [
    ("techcabal", "https://techcabal.com/feed/", "news", ""),
    ("techpoint", "https://techpoint.africa/feed/", "news", ""),
    ("technext", "https://technext24.com/feed/", "news", ""),
    ("nairametrics", "https://nairametrics.com/feed/", "news", ""),
    ("weetracker", "https://weetracker.com/feed/", "news", ""),
    ("openai_news", "https://openai.com/news/rss.xml", "vendor", ""),
    ("meta_dev_blog", "https://developers.facebook.com/blog/feed/", "vendor", "Meta developers: "),
    ("ndpc", "https://ndpc.gov.ng/feed/", "regulator", ""),
    ("nitda", "https://nitda.gov.ng/feed/", "regulator", ""),
    ("claude_code_releases", "https://github.com/anthropics/claude-code/releases.atom", "vendor", "Claude Code release: "),
    ("anthropic_sdk_python_releases", "https://github.com/anthropics/anthropic-sdk-python/releases.atom", "vendor", "Anthropic Python SDK release: "),
    ("claude_status", "https://status.claude.com/history.rss", "vendor", "Claude status: "),
]

ANTHROPIC_SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"
SITEMAP_BULK_UPDATE_LIMIT = 15  # more changed news pages than this in one window means bulk lastmod

STACKOVERFLOW_TAGS = ["openai-api", "langchain", "whatsapp-cloud-api", "large-language-model"]
GITHUB_TOPICS = ["mcp-server", "ai-agents", "whatsapp-bot"]
DEVTO_TAGS = ["ai", "llm", "mcp", "whatsapp", "nigeria"]
SUBREDDITS = ["ClaudeAI", "LocalLLaMA", "LLMDevs", "OpenAI", "n8n"]
HACKERNEWS_QUERIES = [
    "claude code", "mcp", "ai agent", "whatsapp", "rag", "llm evals", "anthropic",
    "openai", "nigeria", "africa", "n8n", "model deprecation",
]

# Google News RSS queries: (name, query, kind, enabled). X sample is phase 2 and off.
GOOGLE_NEWS_QUERIES: list[tuple[str, str, str, bool]] = [
    ("cbn", "site:cbn.gov.ng", "regulator", True),
    ("x_claude_code", 'site:x.com "claude code"', "community", False),
    ("x_ai_agents", 'site:x.com "ai agents"', "community", False),
    ("x_whatsapp_ai", 'site:x.com "whatsapp" "ai"', "community", False),
]
