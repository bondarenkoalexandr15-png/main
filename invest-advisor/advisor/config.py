"""Конфигурация советника: параметры из окружения и целевая аллокация."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal

# Базовый адрес боевого REST API T-Invest.
PROD_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"
# Sandbox использует тот же хост, но методы сервиса SandboxService.
SANDBOX_BASE_URL = PROD_BASE_URL


@dataclass
class TargetAllocation:
    """Целевое распределение портфеля по классам активов (доли, сумма = 1).

    Значения по умолчанию — умеренно-консервативный профиль.
    Настраивается пользователем под свой риск-профиль.
    """

    shares: Decimal = Decimal("0.50")
    bonds: Decimal = Decimal("0.35")
    etf: Decimal = Decimal("0.10")
    cash: Decimal = Decimal("0.05")

    def as_map(self) -> dict[str, Decimal]:
        return {
            "shares": self.shares,
            "bonds": self.bonds,
            "etf": self.etf,
            "cash": self.cash,
        }


@dataclass
class RiskLimits:
    """Пороги, при превышении которых советник выдаёт предупреждение."""

    # Максимальная доля одного эмитента/инструмента в портфеле.
    max_single_position: Decimal = Decimal("0.15")
    # Максимальная доля одного сектора.
    max_single_sector: Decimal = Decimal("0.35")
    # Максимальное отклонение факт. аллокации от целевой (в п.п. доли).
    max_allocation_drift: Decimal = Decimal("0.10")
    # Минимальная доля кэша (ликвидная подушка).
    min_cash: Decimal = Decimal("0.02")
    # Максимальная доля одной валюты (валютный риск).
    max_single_currency: Decimal = Decimal("0.80")


@dataclass
class Settings:
    """Общие настройки запуска."""

    token: str | None = None
    account_id: str | None = None
    use_sandbox: bool = False
    base_currency: str = "RUB"
    proxy: str | None = None
    target: TargetAllocation = field(default_factory=TargetAllocation)
    limits: RiskLimits = field(default_factory=RiskLimits)

    @classmethod
    def from_env(cls) -> Settings:
        """Собрать настройки из переменных окружения.

        Поддерживаемые переменные:
          TINVEST_TOKEN         — токен доступа (лучше read-only);
          TINVEST_ACCOUNT_ID    — id счёта (если не задан, берётся первый);
          TINVEST_USE_SANDBOX   — "1"/"true" для песочницы;
          TINVEST_BASE_CURRENCY — базовая валюта отчёта (по умолчанию RUB);
          TINVEST_PROXY         — прокси для доступа к API
                                  (http://.. / https://.. / socks5://..),
                                  напр. для обхода гео-блокировки по IP.
        """
        use_sandbox = os.getenv("TINVEST_USE_SANDBOX", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(
            token=os.getenv("TINVEST_TOKEN") or None,
            account_id=os.getenv("TINVEST_ACCOUNT_ID") or None,
            use_sandbox=use_sandbox,
            base_currency=os.getenv("TINVEST_BASE_CURRENCY", "RUB").upper(),
            proxy=os.getenv("TINVEST_PROXY") or None,
        )

    @property
    def base_url(self) -> str:
        return SANDBOX_BASE_URL if self.use_sandbox else PROD_BASE_URL
