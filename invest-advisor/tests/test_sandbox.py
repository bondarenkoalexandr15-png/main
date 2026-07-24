"""Тесты клиента песочницы на фейковой HTTP-сессии (без сети)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from advisor.sandbox import SandboxClient, SandboxError


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict:
        return self._payload

    @property
    def text(self) -> str:
        return json.dumps(self._payload)


class _FakeSession:
    """Отдаёт заранее заданные ответы по имени метода в URL."""

    def __init__(self, responses: dict[str, dict], status: int = 200):
        self._responses = responses
        self._status = status
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, json=None, headers=None, timeout=None):  # noqa: A002
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, json))
        payload = self._responses.get(method, {})
        return _FakeResponse(payload, self._status)


def _client(responses: dict[str, dict], status: int = 200) -> tuple:
    session = _FakeSession(responses, status)
    client = SandboxClient("t.fake", session=session)
    return client, session


def test_ensure_account_uses_existing():
    client, session = _client(
        {"GetSandboxAccounts": {"accounts": [{"id": "acc-1"}]}}
    )
    assert client.ensure_account() == "acc-1"
    assert session.calls[0][0] == "GetSandboxAccounts"


def test_ensure_account_opens_when_empty():
    client, _ = _client(
        {
            "GetSandboxAccounts": {"accounts": []},
            "OpenSandboxAccount": {"accountId": "new-acc"},
        }
    )
    assert client.ensure_account() == "new-acc"


def test_pay_in_returns_balance():
    client, session = _client(
        {"SandboxPayIn": {"balance": {"units": "1000000", "nano": 0}}}
    )
    assert client.pay_in("acc-1", Decimal("1000000")) == Decimal(1000000)
    _, body = session.calls[0]
    assert body["amount"]["units"] == "1000000"
    assert body["amount"]["currency"] == "rub"


def test_find_instrument_prefers_tqbr_ticker():
    client, _ = _client(
        {
            "FindInstrument": {
                "instruments": [
                    {"figi": "X", "ticker": "SBER", "classCode": "SPB", "lot": 1},
                    {"figi": "Y", "ticker": "SBER", "classCode": "TQBR", "lot": 10},
                ]
            }
        }
    )
    instr = client.find_instrument("SBER")
    assert instr.figi == "Y"
    assert instr.lot == 10


def test_find_instrument_not_found_raises():
    client, _ = _client({"FindInstrument": {"instruments": []}})
    with pytest.raises(SandboxError):
        client.find_instrument("NOPE")


def test_buy_parses_order_result():
    client, session = _client(
        {
            "PostSandboxOrder": {
                "orderId": "o-1",
                "executionReportStatus": "EXECUTION_REPORT_STATUS_FILL",
                "lotsExecuted": "5",
                "totalOrderAmount": {"currency": "rub", "units": "1337", "nano": 0},
                "executedCommission": {"currency": "rub", "units": "0", "nano": 668625000},
                "executedOrderPrice": {"currency": "rub", "units": "267", "nano": 450000000},
            }
        }
    )
    res = client.buy("acc-1", "FIGI", 5)
    assert res.is_filled
    assert res.lots_executed == 5
    assert res.total_amount == Decimal(1337)
    assert res.price == Decimal("267.45")
    _, body = session.calls[0]
    assert body["direction"] == "ORDER_DIRECTION_BUY"
    assert body["orderType"] == "ORDER_TYPE_MARKET"


def test_buy_rejects_non_positive_lots():
    client, _ = _client({})
    with pytest.raises(SandboxError):
        client.buy("acc-1", "FIGI", 0)


def test_http_error_raises():
    client, _ = _client({"GetSandboxAccounts": {}}, status=500)
    with pytest.raises(SandboxError):
        client.list_accounts()


def test_missing_token_raises():
    with pytest.raises(SandboxError):
        SandboxClient("")
