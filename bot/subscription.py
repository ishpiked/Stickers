from telegram.error import TelegramError
from bot import state


async def is_subscribed(bot, user_id: int) -> bool:
    channel = state.get_settings()["force_sub_channel"]
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError:
        # bot isn't in the channel / channel is wrong -- fail open rather than
        # locking everyone out over a misconfigured setting
        return True
