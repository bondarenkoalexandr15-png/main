"""Доменные модели портфеля, независимые от источника данных."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class AssetKind(str, Enum):
    """Класс актива в портфеле."""

    SHARE = "share"
    BOND = "bond"
    ETF = "etf"
    CURRENCY = "currency"
    FUTURES = "futures"
    OPTION = "option"
    SP = "sp"  # структурная нота / прочее
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Position:
    """Одна позиция в портфеле.

    ``value`` — рыночная стоимость позиции в валюте инструмента,
    приведённая к базовой валюте портфеля вызывающей стороной
    (см. :class:`Portfolio`). Здесь хранится уже приведённое значение.
    """

    figi: str
    ticker: str
    name: str
    kind: AssetKind
    quantity: Decimal
    price: Decimal
    value: Decimal
    currency: str
    sector: str = "unknown"
    country: str = "unknown"
    expected_yield: Decimal = Decimal(0)

    @property
    def is_cash(self) -> bool:
        return self.kind == AssetKind.CURRENCY


@dataclass
class Portfolio:
    """Портфель: набор позиций в единой базовой валюте."""

    account_id: str
    base_currency: str
    positions: list[Position] = field(default_factory=list)

    @property
    def total_value(self) -> Decimal:
        return sum((p.value for p in self.positions), Decimal(0))

    @property
    def invested_value(self) -> Decimal:
        """Стоимость без учёта денежных остатков."""
        return sum(
            (p.value for p in self.positions if not p.is_cash),
            Decimal(0),
        )

    @property
    def cash_value(self) -> Decimal:
        return sum(
            (p.value for p in self.positions if p.is_cash),
            Decimal(0),
        )
