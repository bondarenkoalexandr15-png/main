"""Тесты веб-тренажёра: маршруты Flask с подменённым клиентом песочницы."""

from __future__ import annotations

from decimal import Decimal

import advisor.webapp as webapp
from advisor.config import Settings
from advisor.sandbox import Instrument, OrderResult


class _FakeClient:
    def __init__(self) -> None:
        self.bought: list[tuple[str, int]] = []

    def ensure_account(self) -> str:
        return "acc-1"

    def list_accounts(self):
        return [{"id": "acc-1"}]

    def open_account(self, name: str = "x") -> str:
        return "acc-2"

    def remove_account(self, account_id: str) -> None:
        pass

    def pay_in(self, account_id: str, amount: Decimal, currency: str = "rub") -> Decimal:
        return amount

    def find_instrument(self, query: str, kind: str = "INSTRUMENT_TYPE_SHARE") -> Instrument:
        return Instrument(figi="FG1", ticker=query.upper(), name="Тест", lot=1, currency="RUB")

    def last_price(self, figi: str) -> Decimal:
        return Decimal("100.5")

    def buy(self, account_id: str, figi: str, lots: int) -> OrderResult:
        self.bought.append((figi, lots))
        return OrderResult(
            order_id="o1",
            status="EXECUTION_REPORT_STATUS_FILL",
            lots_executed=lots,
            total_amount=Decimal("100.5") * lots,
            commission=Decimal("0.05"),
            price=Decimal("100.5"),
            currency="RUB",
        )

    def get_portfolio_raw(self, account_id: str, currency: str = "RUB"):
        return {
            "totalAmountPortfolio": {"units": "1000", "nano": 0},
            "positions": [
                {
                    "instrumentType": "currency",
                    "quantity": {"units": "900", "nano": 0},
                },
                {
                    "instrumentType": "share",
                    "ticker": "SBER",
                    "quantity": {"units": "1", "nano": 0},
                    "currentPrice": {"units": "100", "nano": 0},
                    "expectedYield": {"units": "0", "nano": 0},
                },
            ],
        }


def _app(monkeypatch):
    monkeypatch.setattr(webapp, "SandboxClient", lambda *a, **k: _FakeClient())
    app = webapp.create_app(Settings(token="t.fake"))
    app.testing = True
    return app


def test_index_ok(monkeypatch):
    client = _app(monkeypatch).test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Тренажёр-брокер" in resp.get_data(as_text=True)


def test_state(monkeypatch):
    client = _app(monkeypatch).test_client()
    data = client.post("/api/state").get_json()
    assert data["cash"] == 900.0
    assert data["positions"][0]["ticker"] == "SBER"


def test_quote(monkeypatch):
    client = _app(monkeypatch).test_client()
    data = client.post("/api/quote", json={"ticker": "sber"}).get_json()
    assert data["ticker"] == "SBER"
    assert data["price"] == 100.5


def test_buy(monkeypatch):
    client = _app(monkeypatch).test_client()
    data = client.post("/api/buy", json={"ticker": "SBER", "lots": 3}).get_json()
    assert data["shares"] == 3
    assert data["amount"] == 301.5


def test_missing_token_returns_error(monkeypatch):
    monkeypatch.setattr(webapp, "SandboxClient", lambda *a, **k: _FakeClient())
    app = webapp.create_app(Settings(token=None))
    app.testing = True
    resp = app.test_client().post("/api/state")
    assert resp.status_code == 400
    assert "error" in resp.get_json()
