"""Интерфейс провайдера портфеля."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from advisor.models import Portfolio


@runtime_checkable
class PortfolioProvider(Protocol):
    """Источник данных портфеля.

    Любой провайдер (реальный REST, sandbox, mock) обязан уметь:
    - вернуть список доступных счётов;
    - вернуть портфель по счёту.
    """

    def list_accounts(self) -> list[str]:
        """Вернуть id доступных счетов."""
        ...

    def get_portfolio(self, account_id: str | None = None) -> Portfolio:
        """Вернуть портфель по счёту (или по первому доступному)."""
        ...
