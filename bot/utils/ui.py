from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


def bold(text: str) -> str:
    return f"**{text}**"


def italic(text: str) -> str:
    return f"*{text}*"


def bold_italic(text: str) -> str:
    return f"***{text}***"


def header(icon: str, title: str) -> str:
    return f"{icon} {bold(title)}"


def plain_header(icon: str, title: str) -> str:
    """Заголовок без * и ** (для экранов без parse_mode)."""
    return f"{icon} {title}"


def money(amount: Decimal | float | int, symbol: str) -> str:
    if isinstance(amount, Decimal):
        v = float(amount)
    else:
        v = float(amount)
    if v.is_integer():
        return f"{int(v)} {symbol}"
    return f"{v:.2f} {symbol}"


def format_price_integer_ru(amount: Decimal | float | int) -> str:
    """Цена в разделе услуг: только целое число и суффикс « р» (без копеек)."""
    if isinstance(amount, Decimal):
        n = int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        n = int(round(float(amount)))
    return f"{n} р"


def dt_human(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def date_human(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


def time_human(dt: datetime) -> str:
    return dt.strftime("%H:%M")


@dataclass(frozen=True)
class Screen:
    title: str
    body: str

    def render(self) -> str:
        if not self.body.strip():
            return f"{self.title}\n\n"
        return f"{self.title}\n\n{self.body}"


def screen(title: str, body_lines: list[str] | None = None) -> str:
    body = "\n".join(body_lines or [])
    return Screen(title=title, body=body).render()

