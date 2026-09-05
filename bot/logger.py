import logging
from bot.config import LOG_CHANNEL_ID

logger = logging.getLogger("xtickerzbot")


async def log(bot, text: str):
    logger.info(text)  # always visible in console/journal, even if channel delivery fails
    if not LOG_CHANNEL_ID:
        return
    try:
        await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"couldn't deliver log to channel: {e}")
