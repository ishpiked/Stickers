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
