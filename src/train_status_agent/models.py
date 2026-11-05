"""The report Claude must return, and how it becomes the Telegram message."""

from typing import Literal

from pydantic import BaseModel, Field

NO_DISRUPTION = "Sem perturbações hoje"
UNSPECIFIED_PROBLEM = "Perturbação hoje"


class LineStatus(BaseModel):
    status: Literal["ok", "problem"] = Field(description='"problem" only for a concrete problem affecting today.')
    summary: str | None = Field(
        description="Today's problem in at most 8 words, in European Portuguese. Null when status is ok."
    )
    advice: str | None = Field(
        description="Minimum services or an alternative, in at most 10 words, in European Portuguese. Null if unknown."
    )
    strike_dates: str | None = Field(
        description='Only the dates of a strike scheduled within the next 14 days, for example "16-18 nov". Null if none.'
    )
    source_url: str | None = Field(
        description="News URL for the problem or strike, copied exactly from the search results. Null if there is none."
    )


class CommuteReport(BaseModel):
    mts: LineStatus
    fertagus: LineStatus


def format_line(label: str, line: LineStatus) -> str:
    has_problem = line.status == "problem"
    headline = f"⚠️ {line.summary or UNSPECIFIED_PROBLEM}" if has_problem else f"✅ {NO_DISRUPTION}"
    if line.strike_dates:
        headline += f" · 📅 Greve {line.strike_dates}"

    lines = [f"{label}: {headline}"]
    if has_problem and line.advice:
        lines.append(f"   ↳ {line.advice}")
    if line.source_url and (has_problem or line.strike_dates):
        lines.append(f"   🔗 {line.source_url}")
    return "\n".join(lines)


def format_report(report: CommuteReport) -> str:
    return "\n".join([format_line("🚇 MTS", report.mts), format_line("🚆 Fertagus", report.fertagus)])
