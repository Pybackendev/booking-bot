import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "booking_bot.db")

# вебхук (нужно только на проде, для локального запуска можно не трогать)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # например, https://mybot.onrender.com
WEBHOOK_PATH = "/webhook"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 8080))  # Render сам подставляет свой PORT

# секретный "пароль" в пути эндпоинта напоминаний, чтобы его не мог дёрнуть кто попало
REMINDER_SECRET = os.getenv("REMINDER_SECRET", "change-me")

# список Telegram ID администраторов (просто впиши сюда нужные числа через запятую)
ADMIN_IDS = [1628478546]

WORK_HOUR_START = 10
WORK_HOUR_END = 18  # последняя запись в 17:00, слот час
SLOT_STEP_HOURS = 1

# на сколько дней вперёд можно записаться
DAYS_AHEAD = 7
