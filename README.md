# Booking Bot · Запись клиентов в Telegram

Telegram-бот для мастеров, салонов и небольших сервисов. Клиент выбирает удобное время, получает подтверждение и напоминания. Администратор управляет записями и расписанием прямо в Telegram.

**Python · aiogram 3 · SQLite · aiosqlite · FSM · aiohttp**

## Возможности

**Для клиента**
- Выбор даты и свободного времени через inline-кнопки.
- Подтверждение, просмотр и отмена своей записи.
- Напоминания примерно за сутки и за два часа до визита.
- Одна активная запись на клиента.

**Для администратора**
- Список записей на сегодня и ближайшие 14 дней.
- Отмена отдельной записи с уведомлением клиента.
- Открытие и закрытие дней для новых записей.
- Добавление и исключение временных слотов.
- Массовая отмена записей на день с уведомлениями.
- Чёрный список клиентов и снятие блокировки.

## Быстрый старт

Нужны Python 3.11+ и токен Telegram-бота от BotFather.

```bash
git clone https://github.com/Pybackendev/booking-bot.git
cd booking-bot
python -m venv .venv
```

Активируйте окружение: Windows PowerShell — `.\.venv\Scripts\Activate.ps1`, Linux/macOS — `source .venv/bin/activate`.

```bash
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env`, заполните `BOT_TOKEN`. В `config.py` укажите **свой числовой Telegram ID в списке `ADMIN_IDS`**. Отдельной переменной `ADMIN_ID` в текущем коде нет.

```bash
python bot.py
```

Откройте бота и отправьте `/start`. Аккаунт из `ADMIN_IDS` увидит меню администратора; для проверки записи используйте другой аккаунт.

## Настройки

| Параметр | Назначение |
| --- | --- |
| `BOT_TOKEN` | Токен Telegram-бота |
| `DB_PATH` | Путь к SQLite; по умолчанию `booking_bot.db` |
| `WEBHOOK_URL` | Публичный HTTPS-адрес; пустое значение включает polling |
| `PORT` | Порт webhook-сервера; по умолчанию `8080` |
| `REMINDER_SECRET` | Секрет HTTP-эндпоинта напоминаний |

В `config.py`: `WORK_HOUR_START=10`, `WORK_HOUR_END=18`, шаг — один час; запись доступна на семь дней вперёд. Время рассчитывается по часам сервера, поэтому его часовой пояс должен соответствовать расписанию бизнеса.

## Развёртывание

В polling-режиме напоминания проверяются каждые пять минут. При заполненном `WEBHOOK_URL` бот принимает webhook на `/webhook`; внешний планировщик должен регулярно вызывать `GET /reminders/{secret}`, где `secret` — значение `REMINDER_SECRET`. Проверка доступности: `GET /`.

SQLite создаётся автоматически. Для сохранения записей при обновлении сервиса храните файл базы на постоянном диске. Не публикуйте `.env`, токены и рабочую БД.

## Структура

```text
bot.py               # запуск, polling/webhook, HTTP-эндпоинты
handlers_client.py   # запись и отмена
handlers_admin.py    # записи, расписание, чёрный список
keyboards.py         # меню и inline-кнопки
states.py            # FSM записи
reminders.py         # напоминания
db.py               # SQLite и запросы
config.py            # настройки
```

## Автор

[Pybackendev](https://github.com/Pybackendev) · [Связаться на Freelancehunt](https://freelancehunt.com/freelancer/Pybackendev.html)


