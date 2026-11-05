from datetime import datetime
from types import SimpleNamespace

from anthropic.types import (
    Message,
    ServerToolUseBlock,
    Usage,
    WebSearchResultBlock,
    WebSearchToolResultBlock,
    WebSearchToolResultError,
)

from train_status_agent.agent import (
    MODEL,
    QUESTION,
    TIMEZONE,
    WEB_SEARCH_TOOL,
    build_system_prompt,
    check_commute,
    clean_line,
    remove_urls,
    search_result_urls,
)
from train_status_agent.models import CommuteReport, LineStatus

NEWS_URL = "https://example.pt/greve-mts"
INVENTED_URL = "https://inventado.pt/noticia"


def search(*urls: str) -> list:
    """A web search call followed by the pages it returned."""
    return [
        ServerToolUseBlock(type="server_tool_use", id="srvtoolu_1", name="web_search", input={"query": "greve"}),
        WebSearchToolResultBlock(
            type="web_search_tool_result",
            tool_use_id="srvtoolu_1",
            content=[
                WebSearchResultBlock(type="web_search_result", url=url, title="Notícia", encrypted_content="x")
                for url in urls
            ],
        ),
    ]


def response(*blocks) -> Message:
    return Message(
        id="msg_1",
        type="message",
        role="assistant",
        model="claude-haiku-5-5",
        content=list(blocks),
        usage=Usage(input_tokens=1, output_tokens=1),
    )


def line(**fields) -> LineStatus:
    return LineStatus(**{"status": "ok", "summary": None, "advice": None, "strike_dates": None, "source_url": None} | fields)


def fake_client(report: CommuteReport | None, *blocks) -> SimpleNamespace:
    """A stand-in for anthropic.Anthropic that records each call and returns the given report."""
    calls: list[dict] = []

    def parse(**kwargs) -> SimpleNamespace:
        calls.append(kwargs)
        message = response(*blocks)
        return SimpleNamespace(content=message.content, usage=message.usage, stop_reason="end_turn", parsed_output=report)

    return SimpleNamespace(messages=SimpleNamespace(parse=parse), calls=calls)


def test_search_result_urls_collects_every_result():
    message = response(*search(NEWS_URL, "https://example.pt/outra"), *search("https://example.pt/terceira"))
    assert search_result_urls(message) == {NEWS_URL, "https://example.pt/outra", "https://example.pt/terceira"}


def test_search_result_urls_ignores_failed_searches():
    failed = WebSearchToolResultBlock(
        type="web_search_tool_result",
        tool_use_id="srvtoolu_1",
        content=WebSearchToolResultError(type="web_search_tool_result_error", error_code="max_uses_exceeded"),
    )
    assert search_result_urls(response(failed)) == set()


def test_build_system_prompt_includes_today():
    prompt = build_system_prompt(datetime(2026, 10, 26, 7, 0, tzinfo=TIMEZONE))
    assert "26 October 2026" in prompt


def test_remove_urls_keeps_text_and_removes_every_kind_of_link():
    assert remove_urls(f"Vê {NEWS_URL} agora") == "Vê agora"
    assert remove_urls("Vê www.exemplo.pt agora") == "Vê agora"
    assert remove_urls("Vê exemplo.com/oferta agora") == "Vê agora"


def test_remove_urls_keeps_dates_and_times():
    assert remove_urls("16-18 nov às 8.30h") == "16-18 nov às 8.30h"


def test_remove_urls_keeps_none():
    assert remove_urls(None) is None


def test_clean_line_keeps_a_link_from_the_search():
    assert clean_line(line(source_url=NEWS_URL), {NEWS_URL}).source_url == NEWS_URL


def test_clean_line_drops_a_link_not_in_the_search():
    assert clean_line(line(source_url=INVENTED_URL), {NEWS_URL}).source_url is None


def test_clean_line_removes_links_from_the_text_fields():
    dirty = line(status="problem", summary=f"Atrasos {INVENTED_URL}", advice=f"Vê {INVENTED_URL}", strike_dates="16 nov evil.com")
    clean = clean_line(dirty, set())
    assert (clean.summary, clean.advice, clean.strike_dates) == ("Atrasos", "Vê", "16 nov")


def test_check_commute_asks_for_a_report_with_web_search():
    client = fake_client(CommuteReport(mts=line(), fertagus=line()))

    check_commute(client)

    call = client.calls[0]
    assert call["model"] == MODEL
    assert call["tools"] == [WEB_SEARCH_TOOL]
    assert call["output_format"] is CommuteReport
    assert call["messages"] == [{"role": "user", "content": QUESTION}]
    assert "Today is" in call["system"]


def test_check_commute_formats_the_report_and_keeps_links_from_the_search():
    report = CommuteReport(mts=line(strike_dates="16-18 nov", source_url=NEWS_URL), fertagus=line())

    assert check_commute(fake_client(report, *search(NEWS_URL))) == (
        f"🚇 MTS: ✅ Sem perturbações hoje · 📅 Greve 16-18 nov\n   🔗 {NEWS_URL}\n🚆 Fertagus: ✅ Sem perturbações hoje"
    )


def test_check_commute_removes_an_injected_link_on_either_line():
    report = CommuteReport(
        mts=line(status="problem", summary="Greve", source_url=INVENTED_URL),
        fertagus=line(status="problem", summary=f"Atrasos {INVENTED_URL}"),
    )

    assert check_commute(fake_client(report, *search(NEWS_URL))) == "🚇 MTS: ⚠️ Greve\n🚆 Fertagus: ⚠️ Atrasos"


def test_check_commute_returns_nothing_when_there_is_no_report():
    assert check_commute(fake_client(None)) == ""
