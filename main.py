from telegram import BotCommand
from telegram.ext import Application

from bot.config import BOT_TOKEN
from bot.handlers import register_handlers, error_handler


async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Open the bot"),
        BotCommand("help", "Show all commands"),
        BotCommand("newpack", "Create a new pack"),
        BotCommand("mypacks", "List your packs"),
        BotCommand("cancel", "Cancel current action"),
    ])
    await app.bot.set_my_short_description("Create custom Telegram sticker packs in seconds.")
    await app.bot.set_my_description(
        "Xtickerz converts photos, GIFs and videos into high quality Telegram stickers. "
        "Create and manage packs with simple buttons. No manual editing required."
    )


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    register_handlers(app)
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
