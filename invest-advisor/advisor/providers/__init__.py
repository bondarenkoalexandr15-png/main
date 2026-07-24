"""Провайдеры данных портфеля."""

from advisor.providers.base import PortfolioProvider
from advisor.providers.mock import MockProvider

__all__ = ["PortfolioProvider", "MockProvider"]
