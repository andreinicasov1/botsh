import os
import asyncio
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import pytz

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import db
from .schedule_logic import week_range, shift_for_date, dow_str
from .reminders import parse_reminders, reminder_times
from .ui import main_menu_kb, reminder_kb, dow_kb, settings_kb, delete_kb, uni_menu_kb
from .states import JobStart, AddEvent, UniWizard, DeleteById

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TZ = os.getenv("TZ", "Europe/Chisinau")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN lipsește. Pune-l în .env (vezi .env.example)")

tz = pytz.timezone(TZ)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=tz)

def fmt_shift(kind: str) -> str:
    return {
        "WORK_DAY": "🟡 Job (Zi 07:00–19:00)",
        "WORK_NIGHT": "🔵 Job (Noapte 19:00–07:00)",
        "OFF_DAY_1": "🟢 Liber (Zi liberă 1)",
        "OFF_DAY_2": "🟢 Liber (Zi liberă 2)",
    }.get(kind, kind)

async def ensure_user_from_msg(message: Message) -> int:
    user_id = message.from_user.id
    db.ensure_user(user_id, TZ)
    return user_id

def ensure_anchor(user_id: int) -> str:
    anchor = db.get_job_anchor(user_id)
    if not anchor:
        today = datetime.now(tz).date().isoformat()
        db.set_job_anchor(user_id, today)
        anchor = today
    return anchor

def _valid_time(t: str) -> bool:
    try:
        datetime.strptime(t, "%H:%M")
        return True
    except ValueError:
        return False

# ---------- START / HELP ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = await ensure_user_from_msg(message)
    anchor = ensure_anchor(user_id)
    _, uni_n, ev_n = db.get_user_settings(user_id)
    await message.answer(
        "✅ Bot pornit.\n"
        f"📌 Job start date (WORK_DAY): {anchor}\n"
        f"🔔 Uni notify: {uni_n} | Event default: {ev_n}\n"
        "Ciclu: DAY → NIGHT → OFF1 → OFF2 → repeat.\n\n"
        "Alege din butoane 👇",
        reply_markup=main_menu_kb(),
    )

@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Help")
async def cmd_help(message: Message):
    await message.answer(
        "🆘 Ajutor\n\n"
        "📅 Calendar – arată săptămâna\n"
        "🧰 Set job start date – setezi data (WORK_DAY)\n"
        "🎓 Uni schedule – add/list/edit/delete/clear\n"
        "➕ Add event – adaugi eveniment cu reminder\n"
        "🔔 Notification settings – setezi notificări (uni + events)\n"
        "🗑 Delete – ștergere după ID\n\n"
        "Comenzi rapide:\n"
        "/deleteevent ID\n"
        "/deletepair ID\n"
        "/clearpairs\n",
        reply_markup=main_menu_kb(),
    )

# ---------- Calendar ----------
@dp.message(Command("calendar"))
@dp.message(F.text == "📅 Calendar")
async def calendar_view(message: Message):
    user_id = await ensure_user_from_msg(message)
    anchor_str = ensure_anchor(user_id)
    anchor = date.fromisoformat(anchor_str)

    today = datetime.now(tz).date()
    start, end = week_range(today)

    pairs = db.list_pairs(user_id)
    pair_map = {}
    for pid, dow, st, en, subj, room in pairs:
        pair_map.setdefault(dow, []).append((pid, st, en, subj, room))

    events = db.list_events(
        user_id,
        from_iso=datetime.combine(start, datetime.min.time()).isoformat(timespec="seconds"),
        to_iso=datetime.combine(end, datetime.max.time()).isoformat(timespec="seconds"),
    )
    event_map = {}
    for eid, title, start_iso, loc, rem in events:
        dt0 = datetime.fromisoformat(start_iso)
        event_map.setdefault(dt0.date(), []).append((dt0.strftime("%H:%M"), title))

    day_names = ["Lu","Ma","Mi","Jo","Vi","Sa","Du"]
    lines = [f"📅 Săptămâna: {start.isoformat()} → {end.isoformat()}"]
    for i in range(7):
        d = start + timedelta(days=i)
        shift = shift_for_date(anchor, d)
        lines.append(f"\n<b>{d.isoformat()}</b> ({day_names[d.weekday()]})")
        lines.append(fmt_shift(shift.kind))

        dow = dow_str(d)
        if dow in pair_map:
            for pid, st, en, subj, room in pair_map[dow]:
                room_txt = f" ({room})" if room else ""
                lines.append(f"🎓 #{pid} {st}-{en} {subj}{room_txt}")

        if d in event_map:
            for t, title in event_map[d]:
                lines.append(f"📌 {t} {title}")

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_menu_kb())

# ---------- Job start date ----------
@dp.message(F.text == "🧰 Set job start date")
async def set_job_start(message: Message, state: FSMContext):
    await ensure_user_from_msg(message)
    await state.set_state(JobStart.waiting_date)
    await message.answer(
        "📌 Trimite data de start pentru grafic (WORK_DAY).\n"
        "Format: <b>YYYY-MM-DD</b> (ex: <b>2026-02-04</b>)",
        parse_mode="HTML",
    )

@dp.message(JobStart.waiting_date)
async def job_start_date_input(message: Message, state: FSMContext):
    user_id = await ensure_user_from_msg(message)
    txt = (message.text or "").strip()
    try:
        d = date.fromisoformat(txt)
    except ValueError:
        await message.answer("❌ Data invalidă. Exemplu: 2026-02-04")
        return
    db.set_job_anchor(user_id, d.isoformat())
    await state.clear()
    await message.answer(f"✅ Setat! Job start date (WORK_DAY) = {d.isoformat()}", reply_markup=main_menu_kb())

# ---------- Notification settings (FIXED prefixes) ----------
@dp.message(F.text == "🔔 Notification settings")
async def notif_settings(message: Message):
    user_id = await ensure_user_from_msg(message)
    _, uni_n, ev_n = db.get_user_settings(user_id)
    await message.answer(
        f"🔔 Setări notificări\n\n"
        f"🎓 Uni notify: <b>{uni_n}</b>\n"
        f"📌 Event default: <b>{ev_n}</b>\n\n"
        "Alege ce vrei să schimbi:",
        parse_mode="HTML",
        reply_markup=settings_kb(),
    )

@dp.callback_query(F.data == "set:uni")
async def pick_uni_notify(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    await callback.message.answer(
        "Alege cu cât timp înainte pentru perechi (universitate):",
        reply_markup=reminder_kb("notify_uni"),
    )
    await callback.answer()

@dp.callback_query(F.data == "set:event")
async def pick_event_default(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    await callback.message.answer(
        "Alege default reminder pentru evenimente noi:",
        reply_markup=reminder_kb("notify_evd"),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("notify_uni:"))
async def set_uni_notify(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    val = callback.data.split(":", 1)[1]
    db.set_user_uni_notify(user_id, val)
    await callback.message.answer(f"✅ Uni notify setat: <b>{val}</b>", parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("notify_evd:"))
async def set_event_default(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    val = callback.data.split(":", 1)[1]
    db.set_user_event_notify(user_id, val)
    await callback.message.answer(f"✅ Event default setat: <b>{val}</b>", parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer()

# ---------- Add event ----------
@dp.message(F.text == "➕ Add event")
async def add_event_start(message: Message, state: FSMContext):
    await ensure_user_from_msg(message)
    await state.set_state(AddEvent.waiting_title)
    await message.answer("➕ Scrie titlul evenimentului (ex: Barber):")

@dp.message(AddEvent.waiting_title)
async def add_event_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("❌ Titlul nu poate fi gol. Scrie ex: Barber")
        return
    await state.update_data(title=title)
    await state.set_state(AddEvent.waiting_datetime)
    await message.answer(
        "Acum trimite doar <b>data și ora</b>.\n"
        "Format: <b>YYYY-MM-DD HH:MM</b> (ex: <b>2026-02-05 16:00</b>)",
        parse_mode="HTML",
    )

@dp.message(AddEvent.waiting_datetime)
async def add_event_datetime(message: Message, state: FSMContext):
    user_id = await ensure_user_from_msg(message)
    txt = (message.text or "").strip()
    try:
        dt = datetime.strptime(txt, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Format invalid. Exemplu: 2026-02-05 16:00")
        return
    await state.update_data(dt=dt.isoformat(timespec="seconds"))
    _, _, default_ev = db.get_user_settings(user_id)
    await state.set_state(AddEvent.waiting_reminder)
    await message.answer(
        f"🔔 Reminder pentru acest event? (default: {default_ev})",
        reply_markup=reminder_kb("ev"),
    )

@dp.callback_query(F.data.startswith("ev:"), AddEvent.waiting_reminder)
async def add_event_reminder(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)

    chosen = callback.data.split(":", 1)[1]
    data = await state.get_data()
    title = data["title"]
    start_iso = data["dt"]

    reminders = None if chosen == "off" else chosen

    event_id = db.add_event(user_id, title, start_iso, None, reminders)
    await schedule_event_reminders(user_id, event_id)

    await state.clear()
    await callback.message.answer(
        f"✅ Eveniment salvat: <b>{title}</b> la <b>{datetime.fromisoformat(start_iso).strftime('%Y-%m-%d %H:%M')}</b>\n"
        f"Remind: <b>{'OFF' if reminders is None else reminders}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()

# ---------- Uni schedule ----------
@dp.message(F.text == "🎓 Uni schedule")
async def uni_menu(message: Message):
    await ensure_user_from_msg(message)
    await message.answer("🎓 Uni schedule:", reply_markup=uni_menu_kb())

@dp.callback_query(F.data == "uni:list")
async def uni_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    rows = db.list_pairs(user_id)
    if not rows:
        await callback.message.answer("Nu ai perechi salvate.")
        await callback.answer()
        return
    lines = ["🎓 Perechi (cu ID):"]
    for pid, dow, st, en, subj, room in rows:
        room_txt = f" ({room})" if room else ""
        lines.append(f"- #{pid} {dow}: {st}-{en} {subj}{room_txt}")
    await callback.message.answer("\n".join(lines), reply_markup=main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data == "uni:add")
async def uni_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UniWizard.mode)
    await state.update_data(mode="add")
    await state.set_state(UniWizard.waiting_dow)
    await callback.message.answer("Alege ziua:", reply_markup=dow_kb("udow"))
    await callback.answer()

@dp.callback_query(F.data == "uni:edit")
async def uni_edit_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UniWizard.waiting_pair_id)
    await state.update_data(mode="edit")
    await callback.message.answer("✏️ Trimite ID-ul perechii pe care vrei s-o modifici (ex: 12).")
    await callback.answer()

@dp.message(UniWizard.waiting_pair_id)
async def uni_edit_pair_id(message: Message, state: FSMContext):
    await ensure_user_from_msg(message)
    txt = (message.text or "").strip()
    if not txt.isdigit():
        await message.answer("❌ Trimite un ID numeric (ex: 12).")
        return
    await state.update_data(pair_id=int(txt))
    await state.set_state(UniWizard.waiting_dow)
    await message.answer("Alege noua zi:", reply_markup=dow_kb("udow"))

@dp.callback_query(F.data.startswith("udow:"), UniWizard.waiting_dow)
async def uni_dow(callback: CallbackQuery, state: FSMContext):
    dow = callback.data.split(":", 1)[1]
    await state.update_data(dow=dow)
    await state.set_state(UniWizard.waiting_start)
    await callback.message.answer("Ora început (HH:MM). Ex: 08:30")
    await callback.answer()

@dp.message(UniWizard.waiting_start)
async def uni_start_time(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not _valid_time(t):
        await message.answer("❌ Ora invalidă. Format: HH:MM (ex: 08:30)")
        return
    await state.update_data(start=t)
    await state.set_state(UniWizard.waiting_end)
    await message.answer("Ora sfârșit (HH:MM). Ex: 10:00")

@dp.message(UniWizard.waiting_end)
async def uni_end_time(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not _valid_time(t):
        await message.answer("❌ Ora invalidă. Format: HH:MM (ex: 10:00)")
        return
    await state.update_data(end=t)
    await state.set_state(UniWizard.waiting_subject_room)
    await message.answer("Scrie materia și (opțional) sala. Ex: Matematica sala204")

@dp.message(UniWizard.waiting_subject_room)
async def uni_subject_room(message: Message, state: FSMContext):
    user_id = await ensure_user_from_msg(message)
    txt = (message.text or "").strip()
    if not txt:
        await message.answer("❌ Scrie măcar materia.")
        return
    parts = txt.split()
    subject = parts[0]
    room = " ".join(parts[1:]) if len(parts) > 1 else None

    data = await state.get_data()
    mode = data.get("mode", "add")
    dow = data["dow"]
    st = data["start"]
    en = data["end"]

    if mode == "edit":
        pair_id = data.get("pair_id")
        ok = db.update_pair(user_id, pair_id, dow, st, en, subject, room)
        await message.answer("✅ Pereche modificată." if ok else "❌ Nu am găsit perechea cu acest ID.", reply_markup=main_menu_kb())
    else:
        pid = db.add_pair(user_id, dow, st, en, subject, room)
        await message.answer(f"✅ Pereche adăugată (#{pid}).", reply_markup=main_menu_kb())

    await state.clear()

@dp.callback_query(F.data == "uni:del")
async def uni_del_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DeleteById.waiting_pair_id)
    await callback.message.answer("🗑 Trimite ID-ul perechii de șters (ex: 12).")
    await callback.answer()

@dp.message(DeleteById.waiting_pair_id)
async def uni_del_pair_id(message: Message, state: FSMContext):
    user_id = await ensure_user_from_msg(message)
    txt = (message.text or "").strip()
    if not txt.isdigit():
        await message.answer("❌ ID invalid. Exemplu: 12")
        return
    ok = db.delete_pair(user_id, int(txt))
    await state.clear()
    await message.answer("✅ Șters." if ok else "❌ Nu am găsit perechea cu acest ID.", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "uni:clear")
async def uni_clear(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    n = db.clear_pairs(user_id)
    await callback.message.answer(f"✅ Orar șters. Perechi eliminate: {n}", reply_markup=main_menu_kb())
    await callback.answer()

# ---------- Delete menu ----------
@dp.message(F.text == "🗑 Delete")
async def delete_menu(message: Message):
    await ensure_user_from_msg(message)
    await message.answer("🗑 Ștergere:", reply_markup=delete_kb())

@dp.callback_query(F.data == "del:event")
async def del_event_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DeleteById.waiting_event_id)
    await callback.message.answer("Trimite ID-ul eventului de șters (ex: 3).")
    await callback.answer()

@dp.message(DeleteById.waiting_event_id)
async def del_event_id(message: Message, state: FSMContext):
    user_id = await ensure_user_from_msg(message)
    txt = (message.text or "").strip()
    if not txt.isdigit():
        await message.answer("❌ ID invalid. Exemplu: 3")
        return
    ok = db.delete_event(user_id, int(txt))
    await state.clear()
    await message.answer("✅ Event șters." if ok else "❌ Nu am găsit eventul cu acest ID.", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "del:pair")
async def del_pair_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DeleteById.waiting_pair_id)
    await callback.message.answer("Trimite ID-ul perechii de șters (ex: 12).")
    await callback.answer()

@dp.callback_query(F.data == "del:clearpairs")
async def del_clear_pairs(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.ensure_user(user_id, TZ)
    n = db.clear_pairs(user_id)
    await callback.message.answer(f"✅ Orar șters. Perechi eliminate: {n}", reply_markup=main_menu_kb())
    await callback.answer()

# Commands
@dp.message(Command("deleteevent"))
async def cmd_deleteevent(message: Message):
    user_id = await ensure_user_from_msg(message)
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Format: /deleteevent 3")
        return
    ok = db.delete_event(user_id, int(parts[1]))
    await message.answer("✅ Event șters." if ok else "❌ Nu am găsit eventul.")

@dp.message(Command("deletepair"))
async def cmd_deletepair(message: Message):
    user_id = await ensure_user_from_msg(message)
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Format: /deletepair 12")
        return
    ok = db.delete_pair(user_id, int(parts[1]))
    await message.answer("✅ Pereche ștearsă." if ok else "❌ Nu am găsit perechea.")

@dp.message(Command("clearpairs"))
async def cmd_clearpairs(message: Message):
    user_id = await ensure_user_from_msg(message)
    n = db.clear_pairs(user_id)
    await message.answer(f"✅ Orar șters. Perechi eliminate: {n}")

# ---------- Scheduler ----------
async def schedule_event_reminders(user_id: int, event_id: int):
    row = db.get_event(user_id, event_id)
    if not row:
        return
    _, title, start_iso, loc, reminders_str = row
    if not reminders_str:
        return
    event_dt = datetime.fromisoformat(start_iso)
    reminders = parse_reminders(reminders_str)
    now_naive = datetime.now(tz).replace(tzinfo=None)

    for r_dt in reminder_times(event_dt, reminders):
        if r_dt <= now_naive:
            continue
        job_id = f"remE:{user_id}:{event_id}:{int(r_dt.timestamp())}"
        if scheduler.get_job(job_id):
            continue
        scheduler.add_job(
            send_event_reminder,
            "date",
            id=job_id,
            run_date=tz.localize(r_dt),
            args=[user_id, event_id],
            misfire_grace_time=3600,
        )

async def send_event_reminder(user_id: int, event_id: int):
    row = db.get_event(user_id, event_id)
    if not row:
        return
    _, title, start_iso, loc, reminders_str = row
    event_dt = datetime.fromisoformat(start_iso)
    await bot.send_message(user_id, f"⏰ Reminder (event): {title}\n🗓 {event_dt.strftime('%Y-%m-%d %H:%M')}")

async def schedule_today_uni_reminders():
    from .db import get_conn
    with get_conn() as conn:
        users = conn.execute("SELECT user_id, timezone, uni_notify FROM users").fetchall()

    for user_id, user_tz, uni_notify in users:
        if (uni_notify or "30m") == "off":
            continue
        try:
            tz_u = pytz.timezone(user_tz or TZ)
        except Exception:
            tz_u = tz

        today_u = datetime.now(tz_u).date()
        dow = dow_str(today_u)

        pairs = [p for p in db.list_pairs(user_id) if p[1] == dow]
        if not pairs:
            continue

        lead_list = parse_reminders(uni_notify)
        if not lead_list:
            continue
        lead = lead_list[0]

        for pid, _, st, en, subj, room in pairs:
            try:
                start_time = datetime.strptime(st, "%H:%M").time()
            except ValueError:
                continue
            pair_start = datetime.combine(today_u, start_time)
            remind_at = pair_start - lead

            now_naive = datetime.now(tz_u).replace(tzinfo=None)
            if remind_at <= now_naive:
                continue

            job_id = f"remU:{user_id}:{today_u.isoformat()}:{pid}:{int(remind_at.timestamp())}"
            if scheduler.get_job(job_id):
                continue

            scheduler.add_job(
                send_uni_reminder,
                "date",
                id=job_id,
                run_date=tz_u.localize(remind_at),
                args=[user_id, pid, subj, st, en, room],
                misfire_grace_time=1800,
            )

async def send_uni_reminder(user_id: int, pair_id: int, subj: str, st: str, en: str, room: str):
    room_txt = f" ({room})" if room else ""
    await bot.send_message(user_id, f"🎓 Reminder (uni): #{pair_id} {st}-{en} {subj}{room_txt}")

async def nightly_uni_check():
    from .db import get_conn
    with get_conn() as conn:
        users = conn.execute("SELECT user_id, timezone FROM users").fetchall()

    for user_id, user_tz in users:
        try:
            tz_u = pytz.timezone(user_tz or TZ)
        except Exception:
            tz_u = tz

        now_u = datetime.now(tz_u)
        tomorrow = now_u.date() + timedelta(days=1)

        anchor_str = db.get_job_anchor(user_id)
        if not anchor_str:
            anchor_str = now_u.date().isoformat()
            db.set_job_anchor(user_id, anchor_str)
        anchor = date.fromisoformat(anchor_str)

        kind = shift_for_date(anchor, tomorrow).kind
        if kind not in ("OFF_DAY_1", "OFF_DAY_2"):
            continue

        dow = dow_str(tomorrow)
        pairs = [p for p in db.list_pairs(user_id) if p[1] == dow]
        if not pairs:
            continue

        lines = ["✅ Mâine ești LIBER și ai universitate:"]
        for pid, _, st, en, subj, room in pairs:
            room_txt = f" ({room})" if room else ""
            lines.append(f"🎓 #{pid} {st}-{en} {subj}{room_txt}")
        await bot.send_message(user_id, "\n".join(lines))

async def on_startup():
    db.init_db()
    scheduler.start()

    scheduler.add_job(
        nightly_uni_check,
        CronTrigger(hour=20, minute=0),
        id="nightly_uni_check",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        schedule_today_uni_reminders,
        CronTrigger(hour=0, minute=5),
        id="schedule_today_uni_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    await schedule_today_uni_reminders()

    from .db import get_conn
    with get_conn() as conn:
        user_ids = [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]
    now_naive = datetime.now(tz).replace(tzinfo=None)
    for uid in user_ids:
        for eid, *_ in db.list_events(uid, from_iso=now_naive.isoformat(timespec="seconds")):
            await schedule_event_reminders(uid, eid)

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
