from __future__ import annotations

from decimal import Decimal

from bot.repositories.discounts import DiscountRepository


def _to_decimal(v: Decimal | float | int) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def get_active_discount_for_username(username: str | None):
    if not username:
        return None
    return DiscountRepository().get_active_for_username(username.lstrip("@"))


def apply_discount(
    amount: Decimal | float | int,
    *,
    username: str | None,
    service_id: int | None = None,
) -> tuple[Decimal, str | None]:
    """
    Returns: (final_amount, human_label)
    If no discount => (amount, None)
    """
    repo = DiscountRepository()
    discount = repo.get_active_for_username(username.lstrip("@")) if username else None
    base = _to_decimal(amount)
    if not discount:
        return base, None

    # Applicability check for "selected" discounts
    if discount.applies_to == "selected":
        if service_id is None:
            return base, None
        selected = set(repo.get_selected_service_ids(discount.id))
        if service_id not in selected:
            return base, None

    value = _to_decimal(discount.amount_value)
    if discount.amount_type == "percent":
        pct = max(Decimal("0"), min(Decimal("100"), value))
        final = base * (Decimal("100") - pct) / Decimal("100")
        return final.quantize(Decimal("0.01")), f"{pct.normalize()}%"
    if discount.amount_type == "fixed":
        final = base - value
        if final < 0:
            final = Decimal("0")
        return final.quantize(Decimal("0.01")), f"-{value.normalize()}"
    return base, None

