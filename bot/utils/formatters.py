from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from bot.utils.ru_labels import time_slot_status_ru


_MONTHS_RU = {
    1: "ЯНВАРЯ",
    2: "ФЕВРАЛЯ",
    3: "МАРТА",
    4: "АПРЕЛЯ",
    5: "МАЯ",
    6: "ИЮНЯ",
    7: "ИЮЛЯ",
    8: "АВГУСТА",
    9: "СЕНТЯБРЯ",
    10: "ОКТЯБРЯ",
    11: "НОЯБРЯ",
    12: "ДЕКАБРЯ",
}

_WEEKDAYS_RU = {
    0: "ПОНЕДЕЛЬНИК",
    1: "ВТОРНИК",
    2: "СРЕДА",
    3: "ЧЕТВЕРГ",
    4: "ПЯТНИЦА",
    5: "СУББОТА",
    6: "ВОСКРЕСЕНЬЕ",
}


def _line(width: int = 31) -> str:
    return "═" * width


def format_day_title(d: date) -> str:
    return f"📅 {d.day:02d} {_MONTHS_RU.get(d.month, str(d.month))} {d.year} ({_WEEKDAYS_RU.get(d.weekday(), '')})"


def format_day_section_header(d: date) -> str:
    sep = _line()
    return f"{sep}\n{format_day_title(d)}\n{sep}\n"


@dataclass(frozen=True)
class StatusView:
    emoji: str
    text: str


def status_view(*, status: str, is_confirmed: bool) -> StatusView:
    if status == "active":
        return StatusView("✅", "Подтверждена" if is_confirmed else "Активна")
    if status == "pending_confirmation":
        return StatusView("⏳", time_slot_status_ru("pending_confirmation"))
    if status == "cancelled":
        return StatusView("❌", time_slot_status_ru("cancelled"))
    if status == "rescheduled":
        return StatusView("🔁", time_slot_status_ru("rescheduled"))
    if status == "completed":
        return StatusView("✨", time_slot_status_ru("completed"))
    return StatusView("❓", time_slot_status_ru(status))


def format_time_range(start: datetime, *, duration_min: int | None) -> str:
    if not duration_min:
        end = start + timedelta(hours=1)
    else:
        end = start + timedelta(minutes=duration_min)
    return f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"


def format_booking_box(
    idx: int,
    *,
    client_username: str | None,
    client_label: str,
    service_name: str,
    time_range: str,
    status: StatusView,
) -> str:
    title = f"┌─── ЗАПИСЬ №{idx} ───┐"
    bottom = "└──────────────────┘"
    # Keep width visually stable with short lines (Telegram is proportional font, but still readable)
    lines = [
        title,
        "│ 👤 Клиент        │",
        f"│ {client_username or client_label:<15}│",
        f"│ 📋 {service_name:<12}│" if len(service_name) <= 12 else f"│ 📋 {service_name[:12]}… │",
        f"│ 🕐 {time_range:<12}│",
        f"│ {status.emoji} {status.text:<12}│",
        bottom,
        "",
    ]
    return "\n".join(lines)


def format_day_bookings(
    d: date,
    *,
    bookings: list[dict],
    active_total: int | None = None,
) -> str:
    """
    bookings item dict fields expected:
    - client_username (str|None)
    - client_label (str)
    - service_name (str)
    - time_range (str)
    - status (StatusView)
    """
    if not bookings:
        return f"{format_day_section_header(d)}Нет записей на этот день\n"

    out = [format_day_section_header(d)]
    for i, b in enumerate(bookings, start=1):
        out.append(
            format_booking_box(
                i,
                client_username=b.get("client_username"),
                client_label=b.get("client_label") or "—",
                service_name=b.get("service_name") or "—",
                time_range=b.get("time_range") or "—",
                status=b["status"],
            )
        )
    total = active_total if active_total is not None else len(bookings)
    sep = _line()
    word = _plural_ru(total, "активная запись", "активные записи", "активных записей")
    out.append(f"{sep}\n📊 Итого: {total} {word}\n{sep}")
    return "\n".join(out)


_NUMBER_EMOJI = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}


def _plural_ru(n: int, one: str, two: str, many: str) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 19:
        return many
    if n1 == 1:
        return one
    if 2 <= n1 <= 4:
        return two
    return many


def format_appointments_compact(
    d: date,
    *,
    items: list[dict],
    total: int | None = None,
) -> str:
    """
    Compact horizontal format.

    items dict expected fields:
    - client (str)  -> display name, e.g. "@username" or "ID 123"
    - service_name (str)
    - time_range (str)  -> "22:00-23:00" (no spaces)
    - status_emoji (str) -> "✅" or "⏳"
    """
    header = format_day_title(d)
    if not items:
        return f"{header}\n\nНет записей на этот день"

    lines: list[str] = [header, ""]
    for i, it in enumerate(items, start=1):
        num = _NUMBER_EMOJI.get(i, f"{i}️⃣")
        client = it.get("client") or "—"
        svc = it.get("service_name") or "—"
        tr = (it.get("time_range") or "—").replace(" ", "")
        st = it.get("status_emoji") or "⏳"
        lines.append(f"{num} {client}")
        lines.append(f"   📋 {svc} | 🕐 {tr} | {st}")
        lines.append("")

    cnt = total if total is not None else len(items)
    word = _plural_ru(cnt, "запись", "записи", "записей")
    lines.append(f"📊 Итого: {cnt} {word}")
    return "\n".join(lines).rstrip()
