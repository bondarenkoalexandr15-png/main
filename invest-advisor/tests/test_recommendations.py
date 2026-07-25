from decimal import Decimal

from advisor.analytics import analyze
from advisor.config import RiskLimits, TargetAllocation
from advisor.models import AssetKind, Portfolio, Position
from advisor.providers.mock import sample_portfolio
from advisor.recommendations import Severity, build_recommendations


def _p(ticker, kind, value, sector="s", currency="RUB"):
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
    )


def test_balanced_portfolio_has_ok_message():
    # Портфель по целевой аллокации: каждая позиция < 15%, секторы разные,
    # валюты диверсифицированы (RUB < 80%).
    positions = [
        _p("S1", AssetKind.SHARE, 10, sector="a"),
        _p("S2", AssetKind.SHARE, 10, sector="b"),
        _p("S3", AssetKind.SHARE, 10, sector="c", currency="USD"),
        _p("S4", AssetKind.SHARE, 10, sector="d", currency="USD"),
        _p("S5", AssetKind.SHARE, 10, sector="e", currency="USD"),
        _p("B1", AssetKind.BOND, 12, sector="gov1"),
        _p("B2", AssetKind.BOND, 12, sector="gov2"),
        _p("B3", AssetKind.BOND, 11, sector="gov3"),
        _p("E1", AssetKind.ETF, 10, sector="div"),
        _p("CASH", AssetKind.CURRENCY, 5, sector="cash"),
    ]
    portfolio = Portfolio("a", "RUB", positions)
    analytics = analyze(portfolio)
    recs = build_recommendations(analytics, TargetAllocation(), RiskLimits())
    assert len(recs) == 1
    assert recs[0].title == "Портфель сбалансирован"


def test_detects_single_position_concentration():
    positions = [
        _p("BIG", AssetKind.SHARE, 80, sector="a"),
        _p("SMALL", AssetKind.BOND, 20, sector="gov"),
    ]
    analytics = analyze(Portfolio("a", "RUB", positions))
    recs = build_recommendations(analytics, TargetAllocation(), RiskLimits())
    titles = [r.title for r in recs]
    assert any("Высокая концентрация в одной позиции" in t for t in titles)


def test_mock_portfolio_yields_recommendations():
    analytics = analyze(sample_portfolio())
    recs = build_recommendations(analytics, TargetAllocation(), RiskLimits())
    # Демонстрационный портфель намеренно перекошен → должны быть warnings.
    assert any(r.severity == Severity.WARNING for r in recs)


def test_recommendations_sorted_by_severity():
    analytics = analyze(sample_portfolio())
    recs = build_recommendations(analytics, TargetAllocation(), RiskLimits())
    order = [r.severity for r in recs]
    crit = [i for i, s in enumerate(order) if s == Severity.CRITICAL]
    warn = [i for i, s in enumerate(order) if s == Severity.WARNING]
    info = [i for i, s in enumerate(order) if s == Severity.INFO]
    if warn and info:
        assert max(warn) < min(info)
    if crit and warn:
        assert max(crit) < min(warn)
