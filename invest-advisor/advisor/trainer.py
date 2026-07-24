"""Тренажёр торговли в песочнице T-Invest.

Учебный CLI поверх :class:`advisor.sandbox.SandboxClient`. Все сделки —
виртуальные (реальные деньги недоступны). Токен берётся из TINVEST_TOKEN.

Команды:
  open [--name N]      создать виртуальный счёт
  fund <сумма>         пополнить счёт виртуальными рублями
  quote <тикер>        текущая цена и размер лота
  buy <тикер> <лоты>   купить по рынку
  sell <тикер> <лоты>  продать по рынку
  portfolio            показать портфель и свободные деньги
  operations           история операций
  analyze              анализ виртуального портфеля советником
  reset                закрыть все счета песочницы и открыть новый

Примеры:
  python -m advisor.trainer open
  python -m advisor.trainer fund 1000000
  python -m advisor.trainer quote SBER
  python -m advisor.trainer buy SBER 5
  python -m advisor.trainer portfolio
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from advisor.analytics import analyze
from advisor.config import Settings
from advisor.money import quotation_to_decimal
from advisor.recommendations import build_recommendations
from advisor.report import render_text
from advisor.sandbox import SandboxClient, SandboxError


def _money(value: Decimal, currency: str = "RUB") -> str:
    return f"{value:,.2f} {currency}".replace(",", " ")


def _make_client(settings: Settings) -> SandboxClient:
    if not settings.token:
        raise SandboxError(
            "Не задан TINVEST_TOKEN. Задайте read-only токен T-Invest "
            "(в песочнице его достаточно для тренировочной торговли)."
        )
    return SandboxClient(settings.token, base_url=settings.base_url)


# --- команды --------------------------------------------------------------


def cmd_open(client: SandboxClient, args: argparse.Namespace) -> str:
    account_id = client.open_account(args.name)
    return f"Создан виртуальный счёт: {account_id}"


def cmd_fund(client: SandboxClient, args: argparse.Namespace) -> str:
    account_id = client.ensure_account()
    balance = client.pay_in(account_id, Decimal(str(args.amount)))
    return (
        f"Счёт {account_id} пополнен. Свободные деньги: "
        f"{_money(balance)}"
    )


def cmd_quote(client: SandboxClient, args: argparse.Namespace) -> str:
    instr = client.find_instrument(args.ticker)
    price = client.last_price(instr.figi)
    lot_cost = price * instr.lot
    return (
        f"{instr.ticker} ({instr.name})\n"
        f"  Цена: {_money(price, instr.currency)} за 1 бумагу\n"
        f"  Лот: {instr.lot} шт → 1 лот ≈ {_money(lot_cost, instr.currency)}"
    )


def _trade(
    client: SandboxClient, ticker: str, lots: int, *, buy: bool
) -> str:
    account_id = client.ensure_account()
    instr = client.find_instrument(ticker)
    result = (
        client.buy(account_id, instr.figi, lots)
        if buy
        else client.sell(account_id, instr.figi, lots)
    )
    verb = "Покупка" if buy else "Продажа"
    if not result.is_filled:
        return f"{verb} {instr.ticker}: статус {result.status} (не исполнено)."
    shares = result.lots_executed * instr.lot
    return (
        f"{verb} исполнена: {instr.ticker} × {shares} шт "
        f"({result.lots_executed} лот.)\n"
        f"  Цена сделки: {_money(result.price, result.currency)}\n"
        f"  Сумма: {_money(result.total_amount, result.currency)}\n"
        f"  Комиссия: {_money(result.commission, result.currency)}"
    )


def cmd_buy(client: SandboxClient, args: argparse.Namespace) -> str:
    return _trade(client, args.ticker, args.lots, buy=True)


def cmd_sell(client: SandboxClient, args: argparse.Namespace) -> str:
    return _trade(client, args.ticker, args.lots, buy=False)


def cmd_portfolio(client: SandboxClient, args: argparse.Namespace) -> str:
    account_id = client.ensure_account()
    raw = client.get_portfolio_raw(account_id)
    lines = [f"Портфель счёта {account_id}:"]
    total = quotation_to_decimal(raw.get("totalAmountPortfolio"))
    positions = raw.get("positions", [])
    if not positions:
        lines.append("  (пусто — пополните счёт и купите бумаги)")
    for p in positions:
        qty = quotation_to_decimal(p.get("quantity"))
        price = quotation_to_decimal(p.get("currentPrice"))
        value = qty * price
        ticker = p.get("ticker") or p.get("figi", "?")
        kind = p.get("instrumentType", "")
        if kind == "currency":
            lines.append(f"  💰 {ticker}: {_money(qty)} (свободные деньги)")
        else:
            yld = quotation_to_decimal(p.get("expectedYield"))
            lines.append(
                f"  📈 {ticker}: {qty} шт × {price} = {_money(value)} "
                f"(доходность {yld:+.2f}%)"
            )
    lines.append(f"Итого стоимость портфеля: {_money(total)}")
    return "\n".join(lines)


def cmd_operations(client: SandboxClient, args: argparse.Namespace) -> str:
    account_id = client.ensure_account()
    ops = client.get_operations(account_id)
    if not ops:
        return "Операций пока нет."
    lines = ["История операций (последние сверху):"]
    for op in reversed(ops[-20:]):
        date = str(op.get("date", ""))[:10]
        op_type = op.get("operationType", "")
        payment = quotation_to_decimal(op.get("payment"))
        ticker = op.get("figi", "")
        lines.append(f"  {date}  {op_type}  {ticker}  {_money(payment)}")
    return "\n".join(lines)


def cmd_analyze(client: SandboxClient, args: argparse.Namespace) -> str:
    account_id = client.ensure_account()
    settings = Settings.from_env()
    settings.use_sandbox = True
    from advisor.providers.tinkoff_rest import TinkoffRestProvider

    provider = TinkoffRestProvider(
        token=settings.token or "",
        base_url=settings.base_url,
        use_sandbox=True,
        base_currency=settings.base_currency,
    )
    portfolio = provider.get_portfolio(account_id)
    analytics = analyze(portfolio)
    recs = build_recommendations(analytics, settings.target, settings.limits)
    return render_text(analytics, recs)


def cmd_reset(client: SandboxClient, args: argparse.Namespace) -> str:
    removed = 0
    for acc in client.list_accounts():
        client.remove_account(str(acc["id"]))
        removed += 1
    new_id = client.open_account()
    return f"Удалено счетов: {removed}. Открыт новый: {new_id}"


_COMMANDS = {
    "open": cmd_open,
    "fund": cmd_fund,
    "quote": cmd_quote,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "portfolio": cmd_portfolio,
    "operations": cmd_operations,
    "analyze": cmd_analyze,
    "reset": cmd_reset,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="advisor.trainer",
        description="Тренажёр торговли в песочнице T-Invest (виртуальные деньги).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open", help="создать виртуальный счёт")
    p_open.add_argument("--name", default="Тренировочный счёт")

    p_fund = sub.add_parser("fund", help="пополнить виртуальными рублями")
    p_fund.add_argument("amount", type=float)

    p_quote = sub.add_parser("quote", help="цена и размер лота")
    p_quote.add_argument("ticker")

    p_buy = sub.add_parser("buy", help="купить по рынку")
    p_buy.add_argument("ticker")
    p_buy.add_argument("lots", type=int)

    p_sell = sub.add_parser("sell", help="продать по рынку")
    p_sell.add_argument("ticker")
    p_sell.add_argument("lots", type=int)

    sub.add_parser("portfolio", help="показать портфель")
    sub.add_parser("operations", help="история операций")
    sub.add_parser("analyze", help="анализ портфеля советником")
    sub.add_parser("reset", help="сбросить песочницу")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        client = _make_client(settings)
        handler = _COMMANDS[args.command]
        print(handler(client, args))
    except SandboxError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
