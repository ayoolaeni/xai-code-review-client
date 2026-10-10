"""Calculates invoice totals for the billing module."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

VAT_RATE = Decimal("0.075")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class LineItem:
    description: str
    unit_price: Decimal
    quantity: int


def line_total(item: LineItem) -> Decimal:
    """Price of one invoice line before tax."""
    if item.quantity < 0:
        raise ValueError("quantity cannot be negative")
    return (item.unit_price * item.quantity).quantize(CENT, rounding=ROUND_HALF_UP)


def invoice_total(items: list[LineItem]) -> dict[str, Decimal]:
    """Subtotal, VAT and grand total of an invoice."""
    subtotal = sum((line_total(item) for item in items), Decimal("0"))
    vat = (subtotal * VAT_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"subtotal": subtotal, "vat": vat, "total": subtotal + vat}
