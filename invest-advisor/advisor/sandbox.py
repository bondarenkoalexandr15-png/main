"""Клиент песочницы (Sandbox) T-Invest для тренировки торговли.

Песочница — виртуальный контур: сделки исполняются по реальным ценам, но
на виртуальные деньги. Здесь собраны методы, нужные для обучения:
открыть счёт, пополнить, узнать цену, купить/продать, посмотреть портфель
и историю операций.

В отличие от :mod:`advisor.providers.tinkoff_rest` (только чтение), этот
модуль умеет выставлять заявки — но ИСКЛЮЧИТЕЛЬНО в песочнице
(методы SandboxService), реальные деньги здесь недоступны в принципе.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests

from advisor.config import PROD_BASE_URL
from advisor.money import quotation_to_decimal

_CONTRACT = "tinkoff.public.invest.api.contract.v1"

DIRECTION_BUY = "ORDER_DIRECTION_BUY"
DIRECTION_SELL = "ORDER_DIRECTION_SELL"


class SandboxError(RuntimeError):
    """Ошибка обращения к песочнице T-Invest."""


@dataclass
class Instrument:
    figi: str
    ticker: str
    name: str
    lot: int
    currency: str


@dataclass
class OrderResult:
    order_id: str
    status: str
    lots_executed: int
    total_amount: Decimal
    commission: Decimal
    price: Decimal
    currency: str

    @property
    def is_filled(self) -> bool:
        return self.status == "EXECUTION_REPORT_STATUS_FILL"


class SandboxClient:
    """Клиент песочницы T-Invest (виртуальная торговля)."""

    def __init__(
        self,
        token: str,
        base_url: str = PROD_BASE_URL,
        *,
        timeout: float = 30.0,
        proxy: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise SandboxError("Не задан токен T-Invest (TINVEST_TOKEN).")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        if proxy:
            self._session.proxies.update({"http": proxy, "https": proxy})

    def _call(self, service: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{_CONTRACT}.{service}/{method}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            resp = self._session.post(
                url, json=payload, headers=headers, timeout=self._timeout
            )
        except requests.RequestException as exc:  # pragma: no cover - сеть
            raise SandboxError(f"Сетевая ошибка при вызове {method}: {exc}") from exc
        if resp.status_code == 401:
            raise SandboxError("401 Unauthorized: неверный или просроченный токен.")
        if resp.status_code >= 400:
            raise SandboxError(
                f"{method} вернул HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    # --- счёт -------------------------------------------------------------

    def open_account(self, name: str = "Тренировочный счёт") -> str:
        data = self._call("SandboxService", "OpenSandboxAccount", {"name": name})
        return str(data["accountId"])

    def list_accounts(self) -> list[dict[str, Any]]:
        data = self._call("SandboxService", "GetSandboxAccounts", {})
        return list(data.get("accounts", []))

    def ensure_account(self) -> str:
        """Вернуть id первого счёта песочницы; если нет — открыть новый."""
        accounts = self.list_accounts()
        if accounts:
            return str(accounts[0]["id"])
        return self.open_account()

    def remove_account(self, account_id: str) -> None:
        self._call(
            "SandboxService", "CloseSandboxAccount", {"accountId": account_id}
        )

    def pay_in(
        self, account_id: str, amount: Decimal, currency: str = "rub"
    ) -> Decimal:
        units = int(amount)
        nano = int((amount - units) * (Decimal(10) ** 9))
        data = self._call(
            "SandboxService",
            "SandboxPayIn",
            {
                "accountId": account_id,
                "amount": {
                    "currency": currency.lower(),
                    "units": str(units),
                    "nano": nano,
                },
            },
        )
        return quotation_to_decimal(data.get("balance"))

    # --- инструменты и цены ----------------------------------------------

    def find_instrument(
        self, query: str, kind: str = "INSTRUMENT_TYPE_SHARE"
    ) -> Instrument:
        data = self._call(
            "InstrumentsService",
            "FindInstrument",
            {
                "query": query,
                "instrumentKind": kind,
                "apiTradeAvailableFlag": True,
            },
        )
        items = data.get("instruments", [])
        if not items:
            raise SandboxError(f"Инструмент не найден: {query!r}")
        # Приоритет точному совпадению тикера на основном режиме торгов.
        upper = query.upper()
        chosen = next(
            (
                i
                for i in items
                if i.get("ticker", "").upper() == upper
                and i.get("classCode") == "TQBR"
            ),
            None,
        )
        if chosen is None:
            chosen = next(
                (i for i in items if i.get("ticker", "").upper() == upper),
                items[0],
            )
        return Instrument(
            figi=str(chosen["figi"]),
            ticker=str(chosen.get("ticker", "")),
            name=str(chosen.get("name", "")),
            lot=int(chosen.get("lot", 1)),
            currency=str(chosen.get("currency", "rub")).upper(),
        )

    def last_price(self, figi: str) -> Decimal:
        data = self._call("MarketDataService", "GetLastPrices", {"figi": [figi]})
        prices = data.get("lastPrices", [])
        if not prices:
            raise SandboxError(f"Нет цены для {figi}")
        return quotation_to_decimal(prices[0].get("price"))

    # --- торговля ---------------------------------------------------------

    def _post_market_order(
        self, account_id: str, figi: str, lots: int, direction: str
    ) -> OrderResult:
        if lots <= 0:
            raise SandboxError("Количество лотов должно быть положительным.")
        data = self._call(
            "SandboxService",
            "PostSandboxOrder",
            {
                "accountId": account_id,
                "figi": figi,
                "quantity": str(lots),
                "direction": direction,
                "orderType": "ORDER_TYPE_MARKET",
                "orderId": str(uuid.uuid4()),
            },
        )
        return OrderResult(
            order_id=str(data.get("orderId", "")),
            status=str(data.get("executionReportStatus", "")),
            lots_executed=int(data.get("lotsExecuted", 0)),
            total_amount=quotation_to_decimal(data.get("totalOrderAmount")),
            commission=quotation_to_decimal(data.get("executedCommission")),
            price=quotation_to_decimal(data.get("executedOrderPrice")),
            currency=str(
                (data.get("totalOrderAmount") or {}).get("currency", "rub")
            ).upper(),
        )

    def buy(self, account_id: str, figi: str, lots: int) -> OrderResult:
        return self._post_market_order(account_id, figi, lots, DIRECTION_BUY)

    def sell(self, account_id: str, figi: str, lots: int) -> OrderResult:
        return self._post_market_order(account_id, figi, lots, DIRECTION_SELL)

    # --- состояние --------------------------------------------------------

    def get_portfolio_raw(
        self, account_id: str, currency: str = "RUB"
    ) -> dict[str, Any]:
        return self._call(
            "SandboxService",
            "GetSandboxPortfolio",
            {"accountId": account_id, "currency": currency},
        )

    def get_operations(self, account_id: str) -> list[dict[str, Any]]:
        data = self._call(
            "SandboxService",
            "GetSandboxOperations",
            {"accountId": account_id, "state": "OPERATION_STATE_EXECUTED"},
        )
        return list(data.get("operations", []))
