"""Аналитика портфеля: аллокация, концентрация, риск-метрики."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from advisor.models import AssetKind, Portfolio, Position

# Соответствие класса актива категориям целевой аллокации.
_ALLOCATION_BUCKET = {
    AssetKind.SHARE: "shares",
    AssetKind.BOND: "bonds",
    AssetKind.ETF: "etf",
    AssetKind.CURRENCY: "cash",
    AssetKind.FUTURES: "shares",
    AssetKind.OPTION: "shares",
    AssetKind.SP: "shares",
    AssetKind.UNKNOWN: "shares",
}


def _share(part: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal(0)
    return part / total


def _group_sum(
    positions: list[Position], key, total: Decimal
) -> dict[str, Decimal]:
    """Сгруппировать позиции по ключу и вернуть доли (сортировка по убыванию)."""
    acc: dict[str, Decimal] = {}
    for p in positions:
        k = key(p)
        acc[k] = acc.get(k, Decimal(0)) + p.value
    shares = {k: _share(v, total) for k, v in acc.items()}
    return dict(sorted(shares.items(), key=lambda kv: kv[1], reverse=True))


@dataclass
class PositionWeight:
    ticker: str
    name: str
    weight: Decimal


@dataclass
class PortfolioAnalytics:
    """Результат анализа портфеля (все веса — доли от общей стоимости)."""

    total_value: Decimal
    base_currency: str
    allocation: dict[str, Decimal] = field(default_factory=dict)
    by_sector: dict[str, Decimal] = field(default_factory=dict)
    by_currency: dict[str, Decimal] = field(default_factory=dict)
    by_country: dict[str, Decimal] = field(default_factory=dict)
    positions: list[PositionWeight] = field(default_factory=list)
    cash_weight: Decimal = Decimal(0)
    hhi: Decimal = Decimal(0)  # индекс Херфиндаля-Хиршмана (концентрация)
    top_position: PositionWeight | None = None


def herfindahl_index(weights: list[Decimal]) -> Decimal:
    """Индекс Херфиндаля-Хиршмана: сумма квадратов долей.

    ~0 — хорошо диверсифицировано, 1 — всё в одном активе.
    """
    return sum((w * w for w in weights), Decimal(0))


def analyze(portfolio: Portfolio) -> PortfolioAnalytics:
    """Посчитать аналитику по портфелю."""
    total = portfolio.total_value
    positions = portfolio.positions

    allocation: dict[str, Decimal] = {}
    for p in positions:
        bucket = _ALLOCATION_BUCKET.get(p.kind, "shares")
        allocation[bucket] = allocation.get(bucket, Decimal(0)) + _share(
            p.value, total
        )

    invested = [p for p in positions if not p.is_cash]
    by_sector = _group_sum(invested, lambda p: p.sector, total)
    by_currency = _group_sum(positions, lambda p: p.currency, total)
    by_country = _group_sum(invested, lambda p: p.country, total)

    weights = [
        PositionWeight(p.ticker, p.name, _share(p.value, total))
        for p in positions
        if not p.is_cash
    ]
    weights.sort(key=lambda w: w.weight, reverse=True)

    hhi = herfindahl_index([w.weight for w in weights])

    return PortfolioAnalytics(
        total_value=total,
        base_currency=portfolio.base_currency,
        allocation=dict(
            sorted(allocation.items(), key=lambda kv: kv[1], reverse=True)
        ),
        by_sector=by_sector,
        by_currency=by_currency,
        by_country=by_country,
        positions=weights,
        cash_weight=_share(portfolio.cash_value, total),
        hhi=hhi,
        top_position=weights[0] if weights else None,
    )
