"""Провайдер поверх официального REST API T-Invest (read-only).

Используются только методы чтения:
  - UsersService/GetAccounts (или SandboxService/GetSandboxAccounts);
  - OperationsService/GetPortfolio (или SandboxService/GetSandboxPortfolio);
  - InstrumentsService/GetInstrumentBy — для обогащения тикером/сектором.

Никакие торговые методы (выставление/отмена заявок) не вызываются.
"""

from __future__ import annotations

from typing import Any

import requests

from advisor.models import AssetKind, Portfolio, Position
from advisor.money import money_currency, quotation_to_decimal

_CONTRACT = "tinkoff.public.invest.api.contract.v1"

_KIND_BY_INSTRUMENT_TYPE = {
    "share": AssetKind.SHARE,
    "bond": AssetKind.BOND,
    "etf": AssetKind.ETF,
    "currency": AssetKind.CURRENCY,
    "futures": AssetKind.FUTURES,
    "option": AssetKind.OPTION,
    "sp": AssetKind.SP,
}


class TinkoffRestError(RuntimeError):
    """Ошибка обращения к REST API T-Invest."""


class TinkoffRestProvider:
    """Read-only клиент T-Invest REST API."""

    def __init__(
        self,
        token: str,
        base_url: str,
        *,
        use_sandbox: bool = False,
        base_currency: str = "RUB",
        timeout: float = 30.0,
        proxy: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise TinkoffRestError("Не задан токен T-Invest (TINVEST_TOKEN).")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._use_sandbox = use_sandbox
        self._base_currency = base_currency.upper()
        self._timeout = timeout
        self._session = session or requests.Session()
        if proxy:
            self._session.proxies.update({"http": proxy, "https": proxy})
        self._instrument_cache: dict[str, dict[str, Any]] = {}

    # --- низкоуровневый вызов --------------------------------------------

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
            raise TinkoffRestError(f"Сетевая ошибка при вызове {method}: {exc}") from exc
        if resp.status_code == 401:
            raise TinkoffRestError(
                "401 Unauthorized: неверный или просроченный токен."
            )
        if resp.status_code >= 400:
            raise TinkoffRestError(
                f"{method} вернул HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    # --- публичные методы -------------------------------------------------

    def list_accounts(self) -> list[str]:
        if self._use_sandbox:
            data = self._call("SandboxService", "GetSandboxAccounts", {})
        else:
            data = self._call("UsersService", "GetAccounts", {})
        return [acc["id"] for acc in data.get("accounts", [])]

    def get_portfolio(self, account_id: str | None = None) -> Portfolio:
        if account_id is None:
            accounts = self.list_accounts()
            if not accounts:
                raise TinkoffRestError("Нет доступных счетов для этого токена.")
            account_id = accounts[0]

        payload = {"accountId": account_id, "currency": self._base_currency}
        if self._use_sandbox:
            data = self._call("SandboxService", "GetSandboxPortfolio", payload)
        else:
            data = self._call("OperationsService", "GetPortfolio", payload)

        positions = [
            self._parse_position(raw) for raw in data.get("positions", [])
        ]
        return Portfolio(
            account_id=account_id,
            base_currency=self._base_currency,
            positions=positions,
        )

    # --- разбор ответа ----------------------------------------------------

    def _parse_position(self, raw: dict[str, Any]) -> Position:
        figi = str(raw.get("figi", ""))
        instrument_type = str(raw.get("instrumentType", "")).lower()
        kind = _KIND_BY_INSTRUMENT_TYPE.get(instrument_type, AssetKind.UNKNOWN)

        quantity = quotation_to_decimal(raw.get("quantity"))
        price = quotation_to_decimal(raw.get("currentPrice"))
        currency = money_currency(raw.get("currentPrice")) or self._base_currency
        expected_yield = quotation_to_decimal(raw.get("expectedYield"))
        value = quantity * price

        meta = self._instrument_meta(figi, kind)
        return Position(
            figi=figi,
            ticker=meta.get("ticker", figi),
            name=meta.get("name", figi),
            kind=kind,
            quantity=quantity,
            price=price,
            value=value,
            currency=currency,
            sector=meta.get("sector", "unknown"),
            country=meta.get("country", "unknown"),
            expected_yield=expected_yield,
        )

    def _instrument_meta(self, figi: str, kind: AssetKind) -> dict[str, str]:
        """Обогатить позицию тикером/сектором. Best-effort: при ошибке — пусто."""
        if not figi:
            return {}
        if figi in self._instrument_cache:
            return self._instrument_cache[figi]
        meta: dict[str, str] = {}
        if kind == AssetKind.CURRENCY:
            self._instrument_cache[figi] = meta
            return meta
        try:
            data = self._call(
                "InstrumentsService",
                "GetInstrumentBy",
                {"idType": "INSTRUMENT_ID_TYPE_FIGI", "id": figi},
            )
            instr = data.get("instrument", {})
            meta = {
                "ticker": str(instr.get("ticker", figi)),
                "name": str(instr.get("name", figi)),
                "sector": str(instr.get("sector", "unknown")) or "unknown",
                "country": str(instr.get("countryOfRisk", "unknown")) or "unknown",
            }
        except TinkoffRestError:
            meta = {}
        self._instrument_cache[figi] = meta
        return meta
