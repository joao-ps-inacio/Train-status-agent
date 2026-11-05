"""Ask Claude to search the web for strikes and disruptions on the commute."""

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
from anthropic.types import Message, WebSearchTool20250305Param

from train_status_agent.models import CommuteReport, LineStatus, format_report

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
- Use status "problem" only for a concrete problem affecting today. Ignore past strikes.
- If you find no problem for today, use status "ok". Missing information is never a problem.
- A strike scheduled within the next 14 days goes in strike_dates, even when status is "ok".
- Never tell the user to confirm, check or visit a website.
- Report Infraestruturas de Portugal problems under fertagus.
- Always search in Portuguese, and include a search for scheduled strikes ("greve") at MTS and at Fertagus.
"""

# Also matches bare domains, because Telegram turns "example.com" into a link.
INLINE_URL = re.compile(r"\b(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}\S*", re.IGNORECASE)

WEB_SEARCH_TOOL: WebSearchTool20250305Param = {
    "type": "web_search_20250305",
    "name": "web_search",
    # The model plans 5 searches: strikes and disruptions on each company, plus the track.
    # With fewer, the last ones are rejected, and a real strike or track problem can be missed.
    "max_uses": 5,
    "user_location": {"type": "approximate", "country": "PT", "timezone": "Europe/Lisbon"},
}


def build_system_prompt(now: datetime) -> str:
    return SYSTEM_PROMPT.format(today=now.strftime("%A, %d %B %Y"))


def search_result_urls(response: Message) -> set[str]:
    """Return the URL of every page the web search returned."""
    return {
        result.url
        for block in response.content
        if block.type == "web_search_tool_result" and isinstance(block.content, list)
        for result in block.content
    }


def remove_urls(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(INLINE_URL.sub("", text).split())


def clean_line(line: LineStatus, known_urls: set[str]) -> LineStatus:
    """Keep only links the search returned, so an invented or injected link never reaches Telegram."""
    source_url = line.source_url
    if source_url is not None and source_url not in known_urls:
        logger.warning("Dropped a link that is not in the search results: %s", source_url)
        source_url = None
    return line.model_copy(
        update={
            "summary": remove_urls(line.summary),
            "advice": remove_urls(line.advice),
            "strike_dates": remove_urls(line.strike_dates),
            "source_url": source_url,
        }
    )


def check_commute(client: anthropic.Anthropic) -> str:
    """Return a short summary of today's strikes or disruptions on the MTS and Fertagus."""
    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=build_system_prompt(datetime.now(TIMEZONE)),
        messages=[{"role": "user", "content": QUESTION}],
        tools=[WEB_SEARCH_TOOL],
        output_format=CommuteReport,
    )
    logger.info("Claude finished: stop_reason=%s, usage=%s", response.stop_reason, response.usage)

    report = response.parsed_output
    if report is None:
        logger.warning("Claude returned no report: stop_reason=%s", response.stop_reason)
        return ""

    known_urls = search_result_urls(response)
    return format_report(
        CommuteReport(mts=clean_line(report.mts, known_urls), fertagus=clean_line(report.fertagus, known_urls))
    )
