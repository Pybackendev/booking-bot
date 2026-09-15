import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import db
from config import (
    BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT, REMINDER_SECRET
)
from handlers_client import router as client_router
from handlers_admin import router as admin_router
from reminders import check_and_send_reminders

logging.basicConfig(level=logging.INFO)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(client_router)
    dp.include_router(admin_router)
    return dp


# ---------- локальный запуск (polling) ----------

async def reminder_loop(bot: Bot):
    """Локальный планировщик: проверяет напоминания раз в 5 минут.
    На проде эту же проверку дёргает внешний cron через HTTP-эндпоинт (см. ниже)."""
    while True:
        try:
            await check_and_send_reminders(bot)
        except Exception:
            logging.exception("Ошибка при проверке напоминаний")
        await asyncio.sleep(300)


async def run_polling():
    await db.init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    asyncio.create_task(reminder_loop(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


# ---------- прод-запуск (webhook, для Render) ----------

async def reminder_endpoint(request: web.Request):
    """Дёргается внешним cron (cron-job.org), чтобы проверить и разослать напоминания."""
    secret = request.match_info.get("secret")
    if secret != REMINDER_SECRET:
        return web.Response(status=403, text="forbidden")

    bot: Bot = request.app["bot"]
    try:
        await check_and_send_reminders(bot)
    except Exception:
        logging.exception("Ошибка при проверке напоминаний")
        return web.Response(status=500, text="error")
    return web.Response(status=200, text="ok")


async def health_check(request: web.Request):
    return web.Response(status=200, text="alive")


async def on_startup(app: web.Application):
    await db.init_db()
    bot: Bot = app["bot"]
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}", drop_pending_updates=True)


def run_webhook():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    app = web.Application()
    app["bot"] = bot

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    app.router.add_get(f"/reminders/{{secret}}", reminder_endpoint)
    app.router.add_get("/", health_check)

    app.on_startup.append(on_startup)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    if WEBHOOK_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())
