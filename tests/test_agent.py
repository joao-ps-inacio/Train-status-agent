from datetime import datetime

from anthropic.types import (
    Message,
    ServerToolUseBlock,
    TextBlock,
    Usage,
    WebSearchResultBlock,
    WebSearchToolResultBlock,
    WebSearchToolResultError,
)

from train_status_agent.agent import (
    TIMEZONE,
    build_system_prompt,
    drop_unknown_links,
    extract_final_answer,
    search_result_urls,
)

NEWS_URL = "https://example.pt/greve-mts"


def text(value: str) -> TextBlock:
    return TextBlock(type="text", text=value)


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


def test_extract_final_answer_skips_text_before_the_last_search():
    message = response(
        text("Vou pesquisar."),
        *search(NEWS_URL),
        text("Agora a Fertagus."),
        *search(NEWS_URL),
        text("🚇 MTS: ✅ Sem notícias de perturbações"),
    )
    assert extract_final_answer(message) == "🚇 MTS: ✅ Sem notícias de perturbações"


def test_extract_final_answer_joins_the_text_blocks_after_the_search():
    message = response(*search(NEWS_URL), text("🚇 MTS: ⚠️ Greve "), text("(CNN)\n"), text("🚆 Fertagus: ✅"))
    assert extract_final_answer(message) == "🚇 MTS: ⚠️ Greve (CNN)\n🚆 Fertagus: ✅"


def test_extract_final_answer_without_a_search_returns_all_text():
    assert extract_final_answer(response(text("🚇 MTS: ✅"))) == "🚇 MTS: ✅"


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


def test_drop_unknown_links_keeps_links_from_the_search():
    answer = f"🚇 MTS: ⚠️ Greve (CNN)\n   ↳ Ver mts.pt\n   🔗 {NEWS_URL}"
    assert drop_unknown_links(answer, {NEWS_URL}) == answer


def test_drop_unknown_links_removes_invented_links():
    answer = "🚇 MTS: ⚠️ Greve (CNN)\n   🔗 https://inventado.pt/noticia\n🚆 Fertagus: ✅"
    assert drop_unknown_links(answer, {NEWS_URL}) == "🚇 MTS: ⚠️ Greve (CNN)\n🚆 Fertagus: ✅"


def test_build_system_prompt_includes_today():
    prompt = build_system_prompt(datetime(2026, 10, 26, 7, 0, tzinfo=TIMEZONE))
    assert "26 October 2026" in prompt
