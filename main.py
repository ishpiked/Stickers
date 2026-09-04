from telegram.ext import Application

from bot.config import BOT_TOKEN
from bot.handlers import register_handlers, error_handler


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    register_handlers(app)
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
