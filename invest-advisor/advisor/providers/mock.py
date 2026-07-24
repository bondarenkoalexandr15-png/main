"""Mock-провайдер: отдаёт заранее заданный портфель без сети и токена.

Используется для локального запуска, демонстрации и тестов.
Портфель намеренно несбалансирован (перекос в один сектор и большая
доля одной позиции), чтобы движок рекомендаций было что советовать.
"""

from __future__ import annotations

from decimal import Decimal

from advisor.models import AssetKind, Portfolio, Position


def _pos(
    ticker: str,
    name: str,
    kind: AssetKind,
    quantity: str,
    price: str,
    currency: str,
    sector: str,
    country: str,
) -> Position:
    q = Decimal(quantity)
    p = Decimal(price)
    return Position(
        figi=f"MOCK-{ticker}",
        ticker=ticker,
        name=name,
        kind=kind,
        quantity=q,
        price=p,
        value=q * p,
        currency=currency,
        sector=sector,
        country=country,
    )


def sample_portfolio(account_id: str = "mock-account") -> Portfolio:
    """Демонстрационный портфель в рублях."""
    positions = [
        _pos("SBER", "Сбербанк", AssetKind.SHARE, "600", "310.50", "RUB",
             "financials", "RU"),
        _pos("GAZP", "Газпром", AssetKind.SHARE, "500", "165.20", "RUB",
             "energy", "RU"),
        _pos("LKOH", "Лукойл", AssetKind.SHARE, "20", "7150.00", "RUB",
             "energy", "RU"),
        _pos("ROSN", "Роснефть", AssetKind.SHARE, "300", "560.00", "RUB",
             "energy", "RU"),
        _pos("YNDX", "Яндекс", AssetKind.SHARE, "40", "3900.00", "RUB",
             "technology", "RU"),
        _pos("SU26240", "ОФЗ 26240", AssetKind.BOND, "150", "780.00", "RUB",
             "government", "RU"),
        _pos("TBRU", "Т-Облигации", AssetKind.ETF, "500", "112.40", "RUB",
             "diversified", "RU"),
        _pos("RUB", "Рубли", AssetKind.CURRENCY, "35000", "1", "RUB",
             "cash", "RU"),
    ]
    return Portfolio(
        account_id=account_id,
        base_currency="RUB",
        positions=positions,
    )


class MockProvider:
    """Провайдер, возвращающий демонстрационный портфель."""

    def __init__(self, portfolio: Portfolio | None = None) -> None:
        self._portfolio = portfolio or sample_portfolio()

    def list_accounts(self) -> list[str]:
        return [self._portfolio.account_id]

    def get_portfolio(self, account_id: str | None = None) -> Portfolio:
        return self._portfolio
