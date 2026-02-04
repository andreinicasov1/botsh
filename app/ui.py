from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Calendar"), KeyboardButton(text="🧰 Set job start date")],
            [KeyboardButton(text="🎓 Uni schedule"), KeyboardButton(text="➕ Add event")],
            [KeyboardButton(text="🔔 Notification settings"), KeyboardButton(text="🗑 Delete")],
            [KeyboardButton(text="ℹ️ Help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Alege o opțiune…",
    )

def reminder_kb(prefix: str):
    # prefix examples:
    # - "ev" for event reminder choice
    # - "notify_uni" for uni notify setting
    # - "notify_evd" for event default setting
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="OFF (fără)", callback_data=f"{prefix}:off")],
        [InlineKeyboardButton(text="15 min", callback_data=f"{prefix}:15m"),
         InlineKeyboardButton(text="30 min", callback_data=f"{prefix}:30m")],
        [InlineKeyboardButton(text="3 ore", callback_data=f"{prefix}:3h"),
         InlineKeyboardButton(text="1 zi", callback_data=f"{prefix}:1d")],
    ])

def settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Uni notify", callback_data="set:uni"),
         InlineKeyboardButton(text="📌 Event default", callback_data="set:event")],
    ])

def delete_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Delete event (by ID)", callback_data="del:event")],
        [InlineKeyboardButton(text="🗑 Delete uni pair (by ID)", callback_data="del:pair")],
        [InlineKeyboardButton(text="🧹 Clear ALL uni pairs", callback_data="del:clearpairs")],
    ])

def uni_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add pair", callback_data="uni:add"),
         InlineKeyboardButton(text="📋 List pairs", callback_data="uni:list")],
        [InlineKeyboardButton(text="✏️ Edit pair (by ID)", callback_data="uni:edit"),
         InlineKeyboardButton(text="🗑 Delete pair (by ID)", callback_data="uni:del")],
        [InlineKeyboardButton(text="🧹 Clear schedule", callback_data="uni:clear")],
    ])

def dow_kb(prefix: str):
    days = [("Lu", "mon"), ("Ma", "tue"), ("Mi", "wed"), ("Jo", "thu"), ("Vi", "fri"), ("Sa", "sat"), ("Du", "sun")]
    rows = []
    for i in range(0, 7, 2):
        row = []
        for j in range(i, min(i+2, 7)):
            row.append(InlineKeyboardButton(text=days[j][0], callback_data=f"{prefix}:{days[j][1]}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
