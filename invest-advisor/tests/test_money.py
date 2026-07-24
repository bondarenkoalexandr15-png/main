from decimal import Decimal

from advisor.money import (
    decimal_to_quotation,
    money_currency,
    quotation_to_decimal,
)


def test_quotation_to_decimal_basic():
    assert quotation_to_decimal({"units": 310, "nano": 500000000}) == Decimal("310.5")


def test_quotation_to_decimal_none_is_zero():
    assert quotation_to_decimal(None) == Decimal(0)
    assert quotation_to_decimal({}) == Decimal(0)


def test_decimal_to_quotation_roundtrip():
    q = decimal_to_quotation(Decimal("7150.25"))
    assert q["units"] == 7150
    assert quotation_to_decimal(q) == Decimal("7150.25")


def test_money_currency():
    assert money_currency({"currency": "rub", "units": 1}) == "RUB"
    assert money_currency(None) == ""
