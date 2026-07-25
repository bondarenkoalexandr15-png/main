"""Работа с денежными величинами T-Invest API.

T-Invest отдаёт числа в формате Quotation / MoneyValue:
целая часть ``units`` (int) и дробная ``nano`` (1e-9).
Здесь — перевод в ``Decimal`` и обратно.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

NANO = Decimal(10) ** 9


def quotation_to_decimal(value: Mapping[str, object] | None) -> Decimal:
    """Преобразовать Quotation/MoneyValue ({units, nano}) в Decimal.

    ``None`` и пустое значение трактуются как ноль.
    """
    if not value:
        return Decimal(0)
    units = Decimal(int(str(value.get("units", 0))))
    nano = Decimal(int(str(value.get("nano", 0))))
    return units + nano / NANO


def decimal_to_quotation(value: Decimal) -> dict[str, int]:
    """Преобразовать Decimal обратно в Quotation ({units, nano})."""
    units = int(value)
    nano = int((value - units) * NANO)
    return {"units": units, "nano": nano}


def money_currency(value: Mapping[str, object] | None) -> str:
    """Достать код валюты из MoneyValue (пустая строка, если нет)."""
    if not value:
        return ""
    return str(value.get("currency", "")).upper()
