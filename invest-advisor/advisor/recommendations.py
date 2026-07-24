"""Движок рекомендаций на правилах.

На вход — аналитика портфеля и настройки (целевая аллокация, риск-лимиты).
На выход — список рекомендаций с уровнем важности и пояснением.
Движок ничего не исполняет; он только советует.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from advisor.analytics import PortfolioAnalytics
from advisor.config import RiskLimits, TargetAllocation


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


_SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


@dataclass
class Recommendation:
    severity: Severity
    title: str
    detail: str


def _pct(value: Decimal) -> str:
    return f"{value * 100:.1f}%"


def _concentration_recs(
    analytics: PortfolioAnalytics, limits: RiskLimits
) -> list[Recommendation]:
    recs: list[Recommendation] = []

    top = analytics.top_position
    if top is not None and top.weight > limits.max_single_position:
        recs.append(
            Recommendation(
                Severity.WARNING,
                f"Высокая концентрация в одной позиции: {top.ticker}",
                f"Доля {top.ticker} = {_pct(top.weight)} при лимите "
                f"{_pct(limits.max_single_position)}. Рассмотрите частичное "
                "сокращение и распределение в недостающие классы активов.",
            )
        )

    for sector, weight in analytics.by_sector.items():
        if weight > limits.max_single_sector:
            recs.append(
                Recommendation(
                    Severity.WARNING,
                    f"Перекос по сектору: {sector}",
                    f"На сектор «{sector}» приходится {_pct(weight)} при лимите "
                    f"{_pct(limits.max_single_sector)}. Портфель уязвим к "
                    "отраслевым рискам — добавьте активы других секторов.",
                )
            )
            break

    for currency, weight in analytics.by_currency.items():
        if weight > limits.max_single_currency:
            recs.append(
                Recommendation(
                    Severity.INFO,
                    f"Высокая доля одной валюты: {currency}",
                    f"{_pct(weight)} портфеля в {currency}. Для снижения "
                    "валютного риска рассмотрите валютную диверсификацию.",
                )
            )
            break

    return recs


def _allocation_recs(
    analytics: PortfolioAnalytics,
    target: TargetAllocation,
    limits: RiskLimits,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    target_map = target.as_map()
    for bucket, target_share in target_map.items():
        actual = analytics.allocation.get(bucket, Decimal(0))
        drift = actual - target_share
        if abs(drift) > limits.max_allocation_drift:
            direction = "выше" if drift > 0 else "ниже"
            action = "сократить" if drift > 0 else "нарастить"
            recs.append(
                Recommendation(
                    Severity.WARNING,
                    f"Отклонение аллокации: {bucket}",
                    f"Факт {_pct(actual)} против цели {_pct(target_share)} "
                    f"({direction} на {_pct(abs(drift))}). Рекомендуется "
                    f"{action} долю «{bucket}» для ребалансировки.",
                )
            )
    return recs


def _cash_recs(
    analytics: PortfolioAnalytics, limits: RiskLimits
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    if analytics.cash_weight < limits.min_cash:
        recs.append(
            Recommendation(
                Severity.INFO,
                "Малая денежная подушка",
                f"Кэш = {_pct(analytics.cash_weight)} (< "
                f"{_pct(limits.min_cash)}). Небольшой резерв ликвидности "
                "помогает докупать активы на просадках без продаж.",
            )
        )
    return recs


def _diversification_recs(
    analytics: PortfolioAnalytics,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    # HHI > 0.2 обычно трактуется как высокая концентрация.
    if analytics.hhi > Decimal("0.20"):
        recs.append(
            Recommendation(
                Severity.WARNING,
                "Низкая диверсификация (высокий HHI)",
                f"Индекс концентрации HHI = {analytics.hhi:.3f} (> 0.200). "
                "Портфель сконцентрирован в небольшом числе позиций — "
                "увеличьте число независимых активов.",
            )
        )
    n_positions = len(analytics.positions)
    if 0 < n_positions < 5:
        recs.append(
            Recommendation(
                Severity.INFO,
                "Мало позиций в портфеле",
                f"Всего {n_positions} инвестиционных позиций. Для устойчивой "
                "диверсификации обычно рекомендуется 8–15+ независимых активов.",
            )
        )
    return recs


def build_recommendations(
    analytics: PortfolioAnalytics,
    target: TargetAllocation,
    limits: RiskLimits,
) -> list[Recommendation]:
    """Собрать полный список рекомендаций, отсортированный по важности."""
    recs: list[Recommendation] = []
    recs += _allocation_recs(analytics, target, limits)
    recs += _concentration_recs(analytics, limits)
    recs += _diversification_recs(analytics)
    recs += _cash_recs(analytics, limits)

    if not recs:
        recs.append(
            Recommendation(
                Severity.INFO,
                "Портфель сбалансирован",
                "Существенных отклонений от целевой аллокации и риск-лимитов "
                "не выявлено. Продолжайте периодический контроль и "
                "ребалансировку.",
            )
        )

    recs.sort(key=lambda r: _SEVERITY_ORDER[r.severity])
    return recs
