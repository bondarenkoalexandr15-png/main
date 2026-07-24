from decimal import Decimal

from advisor.analytics import analyze, herfindahl_index
from advisor.models import AssetKind, Portfolio, Position


def _p(ticker, kind, value, currency="RUB", sector="s", country="RU"):
    return Position(
        figi=ticker,
        ticker=ticker,
        name=ticker,
        kind=kind,
        quantity=Decimal(1),
        price=Decimal(value),
        value=Decimal(value),
        currency=currency,
        sector=sector,
        country=country,
    )


def _portfolio():
    return Portfolio(
        account_id="a",
        base_currency="RUB",
        positions=[
            _p("A", AssetKind.SHARE, 50, sector="tech"),
            _p("B", AssetKind.BOND, 30, sector="gov"),
            _p("C", AssetKind.CURRENCY, 20, sector="cash"),
        ],
    )


def test_total_and_cash():
    a = analyze(_portfolio())
    assert a.total_value == Decimal(100)
    assert a.cash_weight == Decimal("0.20")


def test_allocation_buckets():
    a = analyze(_portfolio())
    assert a.allocation["shares"] == Decimal("0.50")
    assert a.allocation["bonds"] == Decimal("0.30")
    assert a.allocation["cash"] == Decimal("0.20")


def test_sector_excludes_cash():
    a = analyze(_portfolio())
    assert "cash" not in a.by_sector
    assert a.by_sector["tech"] == Decimal("0.50")


def test_top_position_is_largest_non_cash():
    a = analyze(_portfolio())
    assert a.top_position is not None
    assert a.top_position.ticker == "A"


def test_hhi_single_asset_is_one():
    assert herfindahl_index([Decimal(1)]) == Decimal(1)


def test_empty_portfolio():
    a = analyze(Portfolio(account_id="a", base_currency="RUB", positions=[]))
    assert a.total_value == Decimal(0)
    assert a.top_position is None
    assert a.cash_weight == Decimal(0)
