from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

CYCLE = ["WORK_DAY", "WORK_NIGHT", "OFF_DAY_1", "OFF_DAY_2"]

@dataclass
class ShiftInfo:
    kind: str
    start: datetime | None
    end: datetime | None

def cycle_kind(anchor_work_day: date, d: date) -> str:
    delta = (d - anchor_work_day).days
    return CYCLE[delta % 4]

def shift_for_date(anchor_work_day: date, d: date) -> ShiftInfo:
    kind = cycle_kind(anchor_work_day, d)
    if kind == "WORK_DAY":
        return ShiftInfo(kind, datetime.combine(d, time(7, 0)), datetime.combine(d, time(19, 0)))
    if kind == "WORK_NIGHT":
        return ShiftInfo(kind, datetime.combine(d, time(19, 0)), datetime.combine(d + timedelta(days=1), time(7, 0)))
    return ShiftInfo(kind, None, None)

def week_range(any_day: date):
    start = any_day - timedelta(days=any_day.weekday())
    end = start + timedelta(days=6)
    return start, end

def dow_str(d: date) -> str:
    return ["mon","tue","wed","thu","fri","sat","sun"][d.weekday()]
