import pytest
from pydantic import ValidationError

from train_status_agent.models import (
    CommuteReport,
    LineStatus,
    format_line,
    format_report,
)

NEWS_URL = "https://example.pt/greve-mts"


def line(**fields) -> LineStatus:
    return LineStatus(**{"status": "ok", "summary": None, "advice": None, "strike_dates": None, "source_url": None} | fields)


def test_format_line_with_no_problem():
    assert format_line("🚇 MTS", line()) == "🚇 MTS: ✅ Sem perturbações hoje"


def test_format_line_shows_a_future_strike_with_its_link():
    assert format_line("🚇 MTS", line(strike_dates="16-18 nov", source_url=NEWS_URL)) == (
        f"🚇 MTS: ✅ Sem perturbações hoje · 📅 Greve 16-18 nov\n   🔗 {NEWS_URL}"
    )


def test_format_line_shows_a_problem_with_the_advice_before_the_link():
    problem = line(status="problem", summary="Comboios suprimidos", advice="Serviços mínimos às 7:30", source_url=NEWS_URL)
    assert format_line("🚆 Fertagus", problem) == (
        f"🚆 Fertagus: ⚠️ Comboios suprimidos\n   ↳ Serviços mínimos às 7:30\n   🔗 {NEWS_URL}"
    )


def test_format_line_still_warns_when_the_problem_has_no_summary():
    assert format_line("🚆 Fertagus", line(status="problem")) == "🚆 Fertagus: ⚠️ Perturbação hoje"


def test_format_line_trusts_the_status_over_the_summary():
    assert format_line("🚇 MTS", line(summary="Sem problemas", advice="Nada a fazer")) == "🚇 MTS: ✅ Sem perturbações hoje"


def test_format_line_hides_a_link_when_there_is_nothing_to_report():
    assert format_line("🚇 MTS", line(source_url=NEWS_URL)) == "🚇 MTS: ✅ Sem perturbações hoje"


def test_format_report_puts_mts_before_fertagus():
    report = CommuteReport(mts=line(), fertagus=line(status="problem", summary="Atrasos"))
    assert format_report(report) == "🚇 MTS: ✅ Sem perturbações hoje\n🚆 Fertagus: ⚠️ Atrasos"


def test_report_loads_from_valid_json():
    fields = '"summary": null, "advice": null, "strike_dates": null, "source_url": null'
    report = CommuteReport.model_validate_json(
        f'{{"mts": {{"status": "ok", {fields}}}, "fertagus": {{"status": "problem", {fields}}}}}'
    )
    assert report.mts.status == "ok"
    assert report.fertagus.status == "problem"


def test_report_rejects_an_unknown_status():
    with pytest.raises(ValidationError):
        line(status="maybe")


def test_report_rejects_a_missing_line():
    with pytest.raises(ValidationError):
        CommuteReport.model_validate({"mts": line().model_dump()})
