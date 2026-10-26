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

QUESTION = "Há alguma greve ou perturbação no meu trajeto hoje?"

SYSTEM_PROMPT = """\
És um assistente que verifica o estado dos transportes do João antes de ele ir trabalhar.
Hoje é {today}.

O trajeto do João:
- Metro Sul do Tejo (MTS), da paragem Corroios Casa do Povo até à estação de Corroios.
- Comboio Fertagus de Corroios até Sete Rios, onde tem de chegar antes das 8:10.

Usa a pesquisa web para encontrar greves ou perturbações (avarias, atrasos, via condicionada)
na Fertagus, na Infraestruturas de Portugal (gere a via da Fertagus) e no MTS.
Dá prioridade a fontes oficiais (fertagus.pt, mts.pt, infraestruturasdeportugal.pt)
e a jornais portugueses.

Regras:
- Só contam notícias sobre a data de hoje ou futura. Ignora greves passadas.
- Problemas da Infraestruturas de Portugal entram na linha da Fertagus.
- "Não encontrei nada" não é o mesmo que "está tudo normal".

Responde APENAS com estas 2 linhas, sem introdução nem conclusão:
🚇 MTS: <estado>
🚆 Fertagus: <estado>

<estado> é um destes:
- ✅ Sem notícias de perturbações
- ⚠️ <problema em no máximo 8 palavras> (<nome curto da fonte>)

Só se houver um problema, acrescenta por baixo dessa linha "   ↳ <serviços mínimos ou o que fazer>",
com no máximo 10 palavras.

Exemplo:
🚇 MTS: ⚠️ Greve até 27/10 (Executive Digest)
   ↳ Serviços mínimos por confirmar em mts.pt
🚆 Fertagus: ✅ Sem notícias de perturbações
"""

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
    return extract_final_answer(response)
