from datetime import datetime, timedelta
import re

def parse_reminders(s: str | None) -> list[timedelta]:
    if not s:
        return []
    parts = [p.strip().lower() for p in s.split(",") if p.strip()]
    out: list[timedelta] = []
    for p in parts:
        m = re.fullmatch(r"(\d+)([dhm])", p)
        if not m:
            continue
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "d":
            out.append(timedelta(days=n))
        elif unit == "h":
            out.append(timedelta(hours=n))
        else:
            out.append(timedelta(minutes=n))
    out.sort(reverse=True)
    return out

def reminder_times(event_dt: datetime, reminders: list[timedelta]) -> list[datetime]:
    return [event_dt - r for r in reminders]
