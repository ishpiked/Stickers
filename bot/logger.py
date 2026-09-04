from bot.config import LOG_CHANNEL_ID


async def log(bot, text: str):
    if not LOG_CHANNEL_ID:
        return
    try:
        await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")
    except Exception:
        pass
