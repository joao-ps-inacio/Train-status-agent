"""Ask Claude to search the web for strikes and disruptions on the commute."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
from anthropic.types import Message

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 6000
TIMEZONE = ZoneInfo("Europe/Lisbon")

QUESTION = "Is there any disruption on my commute today, or a strike scheduled within the next 14 days?"

SYSTEM_PROMPT = """\
You check the user's public transport before they leave for work.
Today is {today}.

The user's commute:
- Metro Sul do Tejo (MTS), from the Corroios Casa do Povo stop to Corroios station.
- Fertagus train from Corroios to Sete Rios, arriving before 8:10.

Use web search to find strikes or disruptions (breakdowns, delays, track restrictions)
on Fertagus, Infraestruturas de Portugal (which manages the Fertagus track) and MTS.
Prefer official sources (fertagus.pt, mts.pt, infraestruturasdeportugal.pt)
and Portuguese newspapers.

Rules:
- Use ⚠️ only for a concrete problem affecting today. Ignore past strikes.
- If you find no problem for today, use ✅. Never use ⚠️ because information is missing.
- Never tell the user to confirm, check or visit a website.
- Report Infraestruturas de Portugal problems on the Fertagus line.
- Write the message in European Portuguese, using the exact labels below.

Reply ONLY in this format, with no introduction or conclusion:
🚇 MTS: <status>
🚆 Fertagus: <status>

<status> is one of:
- ✅ Sem perturbações hoje
- ⚠️ <today's problem in at most 8 words>

If a strike is scheduled within the next 14 days, add it at the end of that company's line:
 · 📅 Greve <dates>

Below a line with ⚠️ or 📅, add:
   🔗 <news URL, copied exactly from the search results>

Below a line with ⚠️, if you know the minimum services or an alternative, add before the link:
   ↳ <minimum services or alternative, at most 10 words>

Example:
🚇 MTS: ✅ Sem perturbações hoje · 📅 Greve 16-18 nov
   🔗 https://exemplo.pt/noticia-da-greve
🚆 Fertagus: ✅ Sem perturbações hoje
"""

LINK_PREFIX = "🔗"

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
    "user_location": {"type": "approximate", "country": "PT", "timezone": "Europe/Lisbon"},
}


def build_system_prompt(now: datetime) -> str:
    return SYSTEM_PROMPT.format(today=now.strftime("%A, %d %B %Y"))


def extract_final_answer(response: Message) -> str:
    """Return only the text after the last web search, skipping Claude's "let me search..." remarks."""
    last_search = max(
        (i for i, block in enumerate(response.content) if block.type == "web_search_tool_result"),
        default=-1,
    )
    final_blocks = response.content[last_search + 1:]
    return "".join(block.text for block in final_blocks if block.type == "text").strip()


def search_result_urls(response: Message) -> set[str]:
    """Return the URL of every page the web search returned."""
    return {
        result.url
        for block in response.content
        if block.type == "web_search_tool_result" and isinstance(block.content, list)
        for result in block.content
    }


def drop_unknown_links(answer: str, known_urls: set[str]) -> str:
    """Remove link lines whose URL is not a search result, so a mistyped or invented link never reaches Telegram."""
    kept = []
    for line in answer.splitlines():
        stripped = line.strip()
        if stripped.startswith(LINK_PREFIX) and stripped.removeprefix(LINK_PREFIX).strip() not in known_urls:
            logger.warning("Dropped a link that is not in the search results: %s", stripped)
            continue
        kept.append(line)
    return "\n".join(kept)


def check_commute(client: anthropic.Anthropic) -> str:
    """Return a short summary of today's strikes or disruptions on the MTS and Fertagus."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=build_system_prompt(datetime.now(TIMEZONE)),
        messages=[{"role": "user", "content": QUESTION}],
        tools=[WEB_SEARCH_TOOL],
    )
    logger.info("Claude finished: stop_reason=%s, usage=%s", response.stop_reason, response.usage)
    return drop_unknown_links(extract_final_answer(response), search_result_urls(response))
