from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CROP_LABELS = {
    "left": "⬅️ left", "center": "◾ center", "right": "➡️ right",
    "top": "⬆️ top", "middle": "◾ middle", "bottom": "⬇️ bottom",
}

QUICK_EMOJIS = ["😀", "😂", "😍", "🔥", "💀", "🎉"]


def crop_choice_keyboard(job_id: str, options: list[str]) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(CROP_LABELS[opt], callback_data=f"crop:{job_id}:{opt}")
        for opt in options
    ]
    return InlineKeyboardMarkup([row])


def preview_keyboard(job_id: str, allow_redo: bool) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton("✅ add", callback_data=f"preview:{job_id}:add")]
    if allow_redo:
        row.append(InlineKeyboardButton("🔁 redo crop", callback_data=f"preview:{job_id}:redo"))
    row.append(InlineKeyboardButton("✕ cancel", callback_data=f"preview:{job_id}:cancel"))
    return InlineKeyboardMarkup([row])


def emoji_keyboard(job_id: str) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(e, callback_data=f"emoji:{job_id}:{e}") for e in QUICK_EMOJIS]
    return InlineKeyboardMarkup([row[:3], row[3:], [InlineKeyboardButton("🙂 default", callback_data=f"emoji:{job_id}:default")]])


def subscribe_keyboard(channel: str) -> InlineKeyboardMarkup:
    handle = channel.lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 join channel", url=f"https://t.me/{handle}")],
        [InlineKeyboardButton("✅ i've joined", callback_data="checksub")],
    ])


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("My Packs", callback_data="start:mypacks"), InlineKeyboardButton("Create", callback_data="start:create")],
        [InlineKeyboardButton("Stats", callback_data="start:stats"), InlineKeyboardButton("Help", callback_data="help:open")]
    ])


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="help:back")]
    ])


def packs_keyboard(packs: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for pack in packs:
        short = pack.split("_by_")[0].replace("_", " ")[:30]
        rows.append([InlineKeyboardButton(short or pack, callback_data=f"pack:view:{pack}")])
    rows.append([InlineKeyboardButton("Back", callback_data="help:back")])
    if not packs:
        rows = [[InlineKeyboardButton("Create", callback_data="start:create")], [InlineKeyboardButton("Back", callback_data="help:back")]]
    return InlineKeyboardMarkup(rows)


def pack_detail_keyboard(pack_name: str, is_hidden: bool) -> InlineKeyboardMarkup:
    hide_label = "Show" if is_hidden else "Hide"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Sticker", callback_data=f"pack:add:{pack_name}"), InlineKeyboardButton("Rename", callback_data=f"pack:rename:{pack_name}")],
        [InlineKeyboardButton("Set Frame", callback_data=f"pack:frame:{pack_name}"), InlineKeyboardButton("View Stats", callback_data=f"pack:stat:{pack_name}")],
        [InlineKeyboardButton("Transfer", callback_data=f"pack:transfer:{pack_name}"), InlineKeyboardButton(hide_label, callback_data=f"pack:hide:{pack_name}")],
        [InlineKeyboardButton("Back", callback_data="start:mypacks")]
    ])
