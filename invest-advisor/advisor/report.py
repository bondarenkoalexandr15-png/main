"""Форматирование отчёта советника (markdown / plain text)."""

from __future__ import annotations

from decimal import Decimal

from advisor.analytics import PortfolioAnalytics
from advisor.recommendations import Recommendation, Severity

_SEVERITY_LABEL = {
    Severity.CRITICAL: "КРИТИЧНО",
    Severity.WARNING: "ВНИМАНИЕ",
    Severity.INFO: "ИНФО",
}


def _pct(value: Decimal) -> str:
    return f"{value * 100:.1f}%"


def _money(value: Decimal, currency: str) -> str:
    return f"{value:,.2f} {currency}".replace(",", " ")


def _dist_lines(title: str, dist: dict[str, Decimal]) -> list[str]:
    lines = [f"### {title}"]
    if not dist:
        lines.append("- нет данных")
        return lines
    for key, weight in dist.items():
        lines.append(f"- {key}: {_pct(weight)}")
    return lines


def render_markdown(
    analytics: PortfolioAnalytics,
    recommendations: list[Recommendation],
) -> str:
    """Собрать markdown-отчёт."""
    cur = analytics.base_currency
    out: list[str] = []
    out.append("# Отчёт инвестиционного советника")
    out.append("")
    out.append(
        "> Только анализ и рекомендации. Советник не совершает сделок. "
        "Не является индивидуальной инвестиционной рекомендацией."
    )
    out.append("")
    out.append("## Обзор портфеля")
    out.append(f"- Общая стоимость: **{_money(analytics.total_value, cur)}**")
    out.append(f"- Денежная подушка (кэш): {_pct(analytics.cash_weight)}")
    out.append(f"- Число инвестиционных позиций: {len(analytics.positions)}")
    out.append(f"- Индекс концентрации (HHI): {analytics.hhi:.3f}")
    if analytics.top_position is not None:
        tp = analytics.top_position
        out.append(
            f"- Крупнейшая позиция: {tp.ticker} — {_pct(tp.weight)}"
        )
    out.append("")

    out.append("## Структура")
    out += _dist_lines("Аллокация по классам активов", analytics.allocation)
    out.append("")
    out += _dist_lines("По секторам", analytics.by_sector)
    out.append("")
    out += _dist_lines("По валютам", analytics.by_currency)
    out.append("")

    out.append("## Топ позиций")
    if analytics.positions:
        for w in analytics.positions[:10]:
            out.append(f"- {w.ticker} ({w.name}): {_pct(w.weight)}")
    else:
        out.append("- нет позиций")
    out.append("")

    out.append("## Рекомендации")
    for i, rec in enumerate(recommendations, start=1):
        label = _SEVERITY_LABEL[rec.severity]
        out.append(f"{i}. **[{label}] {rec.title}**")
        out.append(f"   - {rec.detail}")
    out.append("")

    return "\n".join(out)


def render_text(
    analytics: PortfolioAnalytics,
    recommendations: list[Recommendation],
) -> str:
    """Упрощённый текстовый вариант (для терминала)."""
    md = render_markdown(analytics, recommendations)
    # Убираем markdown-разметку, оставляя читаемый текст.
    return (
        md.replace("**", "")
        .replace("### ", "")
        .replace("## ", "")
        .replace("# ", "")
        .replace("> ", "")
    )
