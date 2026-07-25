"""CLI инвестиционного советника.

Примеры:
  # Демонстрация на встроенном mock-портфеле (без токена и сети):
  python -m advisor --mock

  # Реальный портфель (read-only токен в TINVEST_TOKEN):
  python -m advisor

  # Песочница:
  TINVEST_USE_SANDBOX=1 python -m advisor
"""

from __future__ import annotations

import argparse
import sys

from advisor.analytics import analyze
from advisor.config import Settings
from advisor.providers.base import PortfolioProvider
from advisor.providers.mock import MockProvider
from advisor.recommendations import build_recommendations
from advisor.report import render_markdown, render_text


def _build_provider(settings: Settings, use_mock: bool) -> PortfolioProvider:
    if use_mock or not settings.token:
        return MockProvider()
    # Импорт здесь, чтобы mock-режим не требовал requests/сети.
    from advisor.providers.tinkoff_rest import TinkoffRestProvider

    return TinkoffRestProvider(
        token=settings.token,
        base_url=settings.base_url,
        use_sandbox=settings.use_sandbox,
        base_currency=settings.base_currency,
        proxy=settings.proxy,
    )


def build_report(settings: Settings, use_mock: bool, as_markdown: bool) -> str:
    provider = _build_provider(settings, use_mock)
    portfolio = provider.get_portfolio(settings.account_id)
    analytics = analyze(portfolio)
    recs = build_recommendations(analytics, settings.target, settings.limits)
    render = render_markdown if as_markdown else render_text
    return render(analytics, recs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="advisor",
        description="Инвестиционный советник (read-only) для T-Invest API.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="использовать встроенный демонстрационный портфель без сети",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="вывод в формате markdown (по умолчанию — текст)",
    )
    parser.add_argument(
        "--account-id",
        default=None,
        help="id счёта (по умолчанию берётся первый доступный)",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.account_id:
        settings.account_id = args.account_id

    use_mock = args.mock
    if not use_mock and not settings.token:
        print(
            "TINVEST_TOKEN не задан — запуск на демонстрационном портфеле. "
            "Для реального портфеля задайте read-only токен или укажите --mock.\n",
            file=sys.stderr,
        )
        use_mock = True

    try:
        report = build_report(settings, use_mock, args.markdown)
    except Exception as exc:  # noqa: BLE001 - показать пользователю причину
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
