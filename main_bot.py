# main_bot.py (Webhook Version - ASGI Wrapper + PTB Timeouts + Async Currency - Enhanced Logging - Fixed AttributeError & TypeError)
import os
import logging
import asyncio
import json # Додано для обробки JSONDecodeError
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ApplicationBuilder
)
# Використовуємо HTTPXRequest для налаштування таймаутів
from telegram.request import HTTPXRequest
# Використовуємо WsgiToAsgi для сумісності Flask з ASGI сервером (Uvicorn)
from asgiref.wsgi import WsgiToAsgi

# Імпортуємо конвертери
# Переконайся, що currency_converter.py містить АСИНХРОННУ версію
import currency_converter
import unit_converter     # Цей залишається синхронним

# --- Налаштування логування ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Зміни на logging.DEBUG для детальніших логів
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)
logging.getLogger("telegram.bot").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("asgiref").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Змінні середовища ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8080)) # Render надасть змінну PORT

# --- Глобальні змінні ---
application: Application | None = None
initialization_error: Exception | None = None

# --- Обробники команд ---
# (Код обробників залишається без змін)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(f"--> Entering /start handler for user {user.id}")
    reply_content = (
        f"Привіт, {user.mention_html()}!\n\n"
        f"Я бот-конвертер. Допоможу тобі конвертувати валюти та одиниці виміру.\n\n"
        f"<b>Як користуватися:</b>\n"
        f"Надішли повідомлення у форматі:\n"
        f"<code>/convert &lt;значення&gt; &lt;з_одиниці&gt; to &lt;в_одиницю&gt;</code>\n\n"
        f"<b>Приклади:</b>\n"
        f"<code>/convert 100 USD to UAH</code>\n"
        f"<code>/convert 5 km to m</code>\n"
        f"<code>/convert 15 yd to ft</code>\n\n"
        f"Використовуй команду /help для довідки."
    )
    try:
        await update.message.reply_html(reply_content)
        logger.info(f"<-- Successfully sent /start reply to user {user.id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending /start reply to user {user.id} !!!: {e}", exc_info=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"--> Entering /help handler for user {user_id}")
    help_text = (
        "<b>Інструкція з використання:</b>\n\n"
        "Щоб конвертувати, надішли команду у форматі:\n"
        "<code>/convert &lt;значення&gt; &lt;з_одиниці&gt; to &lt;в_одиницю&gt;</code>\n\n"
        "<b>Приклади:</b>\n"
        "  <code>/convert 100 USD to UAH</code>  (валюта)\n"
        "  <code>/convert 5 km to m</code>      (довжина)\n"
        "  <code>/convert 10 kg to lb</code>      (маса)\n"
        "  <code>/convert 2.5 l to ml</code>      (об'єм)\n\n"
        "<b>Підтримувані валюти (деякі):</b> USD, EUR, UAH, GBP, PLN, CAD, JPY тощо (список може змінюватися залежно від API).\n\n"
        "<b>Підтримувані одиниці:</b>\n"
        "  Довжина: mm, cm, m, km, in, ft, yd, mi\n"
        "  Маса: mg, g, kg, t, oz, lb\n"
        "  Об'єм: ml, l, m3, gal\n\n"
        "<b>Важливо:</b> Конвертація можлива тільки в межах однієї категорії."
    )
    try:
        await update.message.reply_html(help_text)
        logger.info(f"<-- Successfully sent /help reply to user {user_id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending /help reply to user {user_id} !!!: {e}", exc_info=True)

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    user_id = update.effective_user.id
    logger.info(f"--> Entering /convert handler for user {user_id} with args: {args}")

    if not args or len(args) < 4 or args[-2].lower() != 'to':
        logger.warning(f"Invalid /convert format from user {user_id}. Args: {args}")
        try:
            await update.message.reply_text(
                "Неправильний формат. Використовуйте: `/convert <значення> <з> to <в>`\n"
                "Приклад: `/convert 100 USD to UAH`"
            )
        except Exception as e:
            logger.error(f"Error sending format error message for /convert to user {user_id}: {e}", exc_info=True)
        return

    try:
        amount_str = args[0]
        # Об'єднуємо всі частини "з", якщо їх більше однієї (наприклад, "cubic meter")
        from_unit = " ".join(args[1:-2]).strip()
        to_unit = args[-1].strip()
        amount = float(amount_str.replace(',', '.')) # Дозволяємо кому як десятковий роздільник
        logger.debug(f"Parsed conversion: {amount} '{from_unit}' -> '{to_unit}'")
    except ValueError:
        logger.warning(f"Invalid number format '{amount_str}' from user {user_id}")
        try:
            await update.message.reply_text(f"Помилка: '{amount_str}' не є дійсним числом.")
        except Exception as e:
            logger.error(f"Error sending ValueError message for /convert to user {user_id}: {e}", exc_info=True)
        return
    except Exception as e:
        logger.error(f"Unexpected error parsing /convert args for user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Виникла помилка при обробці вашого запиту.")
        except Exception as e_reply:
             logger.error(f"Error sending generic parsing error message to user {user_id}: {e_reply}", exc_info=True)
        return

    reply_text = ""
    conversion_done = False

    # Спроба конвертації одиниць (синхронна функція)
    logger.debug(f"Attempting unit conversion for: {amount} '{from_unit}' -> '{to_unit}'")
    try:
        unit_result = unit_converter.convert_units(amount, from_unit, to_unit)
        if unit_result is not None:
            logger.info(f"Unit conversion successful: {amount} {from_unit} -> {unit_result} {to_unit}")
            # Форматування результату (ціле число або з 4 знаками після коми)
            if unit_result == int(unit_result):
                reply_text = f"{amount} {from_unit.upper()} = {int(unit_result)} {to_unit.upper()}"
            else:
                reply_text = f"{amount} {from_unit.upper()} = {unit_result:.4f} {to_unit.upper()}"
            conversion_done = True
        else:
             logger.debug(f"Unit conversion returned None (likely not units or incompatible).")
    except Exception as e:
        logger.error(f"!!! EXCEPTION during unit conversion call for user {user_id} !!!: {e}", exc_info=True)
        reply_text = "Виникла внутрішня помилка при конвертації одиниць."
        # Не встановлюємо conversion_done = True, щоб спробувати валюту, якщо помилка була некритичною

    # Якщо одиниці не конвертувалися, спроба конвертації валюти (асинхронна функція)
    if not conversion_done:
        # Перевірка, чи схоже на коди валют (3 літери)
        is_potential_currency = (len(from_unit) == 3 and from_unit.isalpha() and len(to_unit) == 3 and to_unit.isalpha())
        logger.debug(f"Unit conversion failed or skipped, attempting currency conversion for: '{from_unit}' -> '{to_unit}' (Potential Currency: {is_potential_currency})")

        if is_potential_currency:
            try:
                # Викликаємо асинхронну функцію конвертації валют
                currency_result = await currency_converter.convert_currency(amount, from_unit, to_unit)
                if currency_result is not None:
                    logger.info(f"Currency conversion successful: {amount} {from_unit.upper()} -> {currency_result} {to_unit.upper()}")
                    reply_text = f"{amount} {from_unit.upper()} = {currency_result:.2f} {to_unit.upper()}"
                    conversion_done = True
                else:
                    # Функція повернула None, ймовірно, не знайшла курс
                    logger.warning(f"Currency conversion function returned None for {from_unit.upper()} -> {to_unit.upper()}")
                    reply_text = (
                        f"Не вдалося конвертувати валюту {from_unit.upper()} в {to_unit.upper()}.\n"
                        f"Перевірте правильність кодів валют або спробуйте пізніше."
                    )
                    # Встановлюємо conversion_done = True, щоб не показувати повідомлення "не вдалося розпізнати"
                    conversion_done = True
            except Exception as e:
                logger.error(f"!!! EXCEPTION during currency conversion call for user {user_id} !!!: {e}", exc_info=True)
                reply_text = "Виникла внутрішня помилка при конвертації валюти."
                # Встановлюємо conversion_done = True, щоб не показувати повідомлення "не вдалося розпізнати"
                conversion_done = True
        else:
            # Якщо не схоже на валюту і одиниці не розпізнались
             logger.warning(f"Could not recognize units/currency: '{from_unit}' or '{to_unit}' for user {user_id}")
             reply_text = (
                 f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'.\n"
                 f"Перевірте правильність написання або спробуйте /help."
             )
             conversion_done = True # Вважаємо обробленим, хоч і з помилкою розпізнавання

    # Якщо жодна конвертація не вдалася і немає специфічного повідомлення про помилку
    if not conversion_done and not reply_text:
         logger.error(f"Conversion failed for unknown reason for user {user_id}. Args: {args}")
         reply_text = "Не вдалося виконати конвертацію. Перевірте формат запиту та одиниці/валюти."

    # Надсилання відповіді
    try:
        await update.message.reply_text(reply_text)
        logger.info(f"<-- Successfully sent /convert reply to user {user_id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending final /convert reply to user {user_id} !!!: {e}", exc_info=True)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"--> Handling unknown command/text from chat {update.effective_chat.id}")
    try:
        await update.message.reply_text("Невідома команда або формат. Спробуйте /help.")
        logger.info(f"<-- Sent 'unknown command' message to chat {update.effective_chat.id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION sending 'unknown command' message to chat {update.effective_chat.id} !!!: {e}", exc_info=True)

# --- Налаштування вебхука ---
async def setup_webhook(app: Application, url: str) -> bool:
    if not url:
        logger.error("WEBHOOK_URL не задано в змінних середовища!")
        return False
    logger.info(f"Attempting to set webhook to URL: {url}")
    try:
        # drop_pending_updates=True - важливо, щоб пропустити старі оновлення при перезапуску
        await app.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        # Перевіряємо, чи вебхук дійсно встановлено
        info = await app.bot.get_webhook_info()
        if info.url == url:
            logger.info(f"Webhook successfully set to {info.url}")
            if info.last_error_date:
                 # Логуємо, якщо Telegram повідомляє про попередні помилки доставки
                 last_error_ts = info.last_error_date.strftime('%Y-%m-%d %H:%M:%S') if info.last_error_date else 'N/A'
                 logger.warning(f"Webhook info reports previous error: Date={last_error_ts}, Message='{info.last_error_message}'")
            return True
        else:
            logger.error(f"Failed to set webhook. Current URL reported by Telegram: '{info.url}', Expected: '{url}'")
            return False
    except Exception as e:
        logger.error(f"CRITICAL ERROR during set_webhook/get_webhook_info: {e}", exc_info=True)
        return False

# --- Ініціалізація Telegram Application ---
def initialize_telegram_app() -> Application | None:
    global initialization_error
    logger.info("Initializing Telegram Application...")
    if not BOT_TOKEN:
        initialization_error = RuntimeError("BOT_TOKEN не знайдено в змінних середовища!")
        logger.critical(initialization_error)
        return None
    try:
        # Налаштовуємо таймаути для HTTP-запитів до Telegram API
        request_settings = HTTPXRequest(
            connect_timeout=10.0, # Таймаут на підключення
            read_timeout=20.0,    # Таймаут на читання відповіді
            pool_timeout=15.0     # Таймаут на очікування з'єднання з пулу
        )
        # ВИПРАВЛЕНО: Просто логуємо факт налаштування, не намагаючись читати атрибути
        logger.info("Configured PTB Request with custom timeouts.")

        builder = ApplicationBuilder().token(BOT_TOKEN).request(request_settings)
        app = builder.build()

        # Додаємо обробники
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("convert", convert_command))
        # Обробник для невідомих текстових повідомлень (не команд)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
        # Обробник для невідомих команд
        app.add_handler(MessageHandler(filters.COMMAND, unknown))

        logger.info("Command and message handlers added.")
        return app
    except Exception as e:
        initialization_error = e
        logger.critical(f"CRITICAL ERROR during Telegram Application setup: {e}", exc_info=True)
        return None

# --- Асинхронне завантаження та налаштування ---
async def startup():
    global application, initialization_error
    logger.info("Початок асинхронної ініціалізації (startup)...")
    application = initialize_telegram_app()
    if application:
        logger.info("Initializing Telegram Application object...")
        try:
            # Асинхронна ініціалізація Application (важливо для деяких компонентів PTB)
            await application.initialize()
            logger.info("Telegram Application initialized successfully.")
            # Встановлюємо вебхук
            webhook_ok = await setup_webhook(application, WEBHOOK_URL)
            if not webhook_ok:
                logger.warning("Webhook setup failed or WEBHOOK_URL not provided. Bot might not receive updates.")
                # Можна встановити помилку, якщо вебхук критичний
                # initialization_error = RuntimeError("Webhook setup failed")
                # application = None # Або не скидати, якщо хочемо спробувати працювати без вебхука (неможливо на Render)
        except Exception as e:
            logger.critical(f"CRITICAL ERROR during async application initialize/webhook setup: {e}", exc_info=True)
            initialization_error = e
            application = None # Помилка ініціалізації - додаток не готовий
    else:
        logger.critical("Telegram Application object could not be created (check previous logs for errors).")
        # initialization_error вже має бути встановлено в initialize_telegram_app

    # Зберігаємо стан у конфіг Flask (доступно в запитах)
    flask_app.config['TELEGRAM_APP'] = application
    flask_app.config['INIT_ERROR'] = initialization_error
    logger.info(f"Асинхронна ініціалізація (startup) завершена. App available: {application is not None}. Init error: {initialization_error}")

# --- Flask App та маршрути ---
flask_app = Flask(__name__)

# Запускаємо асинхронну ініціалізацію ПЕРЕД створенням маршрутів,
# щоб application та initialization_error були доступні
try:
    logger.info("Starting asyncio.run(startup()) during Flask app creation...")
    # Використовуємо asyncio.run для запуску асинхронної функції startup
    # Це блокує до завершення startup
    asyncio.run(startup())
    logger.info("asyncio.run(startup()) finished.")
except Exception as e:
     # Логуємо критичну помилку, якщо сам запуск startup не вдався
     logger.critical(f"CRITICAL ERROR running asyncio.run(startup): {e}", exc_info=True)
     if not initialization_error: # Якщо помилка не була встановлена всередині startup
          initialization_error = e
     # Забезпечуємо, що стан помилки збережено в конфігу Flask
     flask_app.config['INIT_ERROR'] = initialization_error
     flask_app.config['TELEGRAM_APP'] = None

@flask_app.route("/", methods=["GET", "HEAD"] )
@flask_app.route("/healthz", methods=["GET", "HEAD"])
def health_check():
    """Перевірка стану для Render."""
    # Отримуємо стан з конфігу Flask
    err = flask_app.config.get('INIT_ERROR')
    app_inst = flask_app.config.get('TELEGRAM_APP')
    webhook_info = None

    status_code = 200
    message = "OK"

    if err:
        logger.error(f"Health check failed due to initialization error: {err}")
        status_code = 500
        message = f"Initialization Error: {err}"
    elif not app_inst:
         logger.error("Health check failed: Telegram Application instance is missing.")
         status_code = 500
         message = "Error: Bot application not available"
    else:
        # Якщо є додаток, спробуємо отримати інфо про вебхук (але це синхронний хендлер!)
        # Краще перевіряти статус вебхука асинхронно, якщо це можливо,
        # але для простої перевірки можна просто підтвердити, що об'єкт app існує.
        logger.info("Health check requested - Application instance exists.")
        # Можна додати перевірку info = await app_inst.bot.get_webhook_info()
        # але це вимагатиме зробити health_check асинхронним, що ускладнить

    logger.info(f"Health check result: Status={status_code}, Message='{message}'")
    return message, status_code

@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    """Обробляє вхідні оновлення Telegram."""
    # Отримуємо стан з конфігу Flask
    err = flask_app.config.get('INIT_ERROR')
    app_inst = flask_app.config.get('TELEGRAM_APP')

    # Перевіряємо, чи ініціалізація пройшла успішно
    if err or not app_inst:
        logger.error(f"Webhook request received, but initialization failed or app not available. Error: {err}")
        # Повертаємо 500, щоб сигналізувати про проблему
        return Response(status=500)

    logger.debug("--> Processing incoming request on /webhook...")
    update = None
    try:
        # Отримуємо тіло запиту як байти (синхронно)
        # ВИПРАВЛЕНО: Прибрали await
        raw_data = request.get_data()
        if not raw_data:
             logger.warning("Received empty request body on /webhook.")
             return Response(status=200) # Порожній запит - ігноруємо

        # Декодуємо JSON вручну
        try:
            data = json.loads(raw_data)
            logger.debug(f"Webhook received JSON data: {data}") # Логуємо отримані дані (обережно з токенами!)
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON from webhook request: {json_err}. Raw data: {raw_data[:200]}...") # Показуємо початок сирих даних
            return Response(status=400) # Поганий запит

        # Десеріалізуємо Update
        update = Update.de_json(data, app_inst.bot)
        logger.info(f"Calling application.process_update for update_id: {update.update_id}...")

        # Запускаємо обробку оновлення
        await app_inst.process_update(update)

        logger.info(f"Finished application.process_update for update_id: {update.update_id}.")
        # Повертаємо 200 OK, щоб Telegram знав, що ми отримали оновлення
        return Response(status=200)

    except Exception as e:
        # Логуємо будь-які інші неочікувані помилки під час обробки
        update_id_str = f"update_id: {update.update_id}" if update else "update data unavailable"
        logger.error(f"!!! UNEXPECTED ERROR processing webhook update ({update_id_str}) !!!: {e}", exc_info=True)
        # Все одно повертаємо 200 OK, щоб Telegram не намагався повторно надіслати це ж оновлення
        # Якщо тут повертати 500, Telegram буде повторювати запит, що може призвести до циклу помилок
        return Response(status=200)

# --- Обгортка Flask -> ASGI ---
# Створюємо ASGI-сумісний об'єкт з нашого Flask додатка
asgi_app = WsgiToAsgi(flask_app)
logger.info("Flask app wrapped with WsgiToAsgi for ASGI compatibility.")

# --- Запуск (для локального тестування) ---
# Цей блок не буде виконуватися на Render, там використовується команда запуску Gunicorn
# if __name__ == "__main__":
#     import uvicorn
#     logger.info("Starting Uvicorn development server (for local testing only)...")
#     # Запускаємо ASGI додаток за допомогою Uvicorn
#     uvicorn.run(
#         "main_bot:asgi_app",
#         host="0.0.0.0",
#         port=PORT,
#         log_level="info",
#         reload=True # Додано для зручності розробки (автоперезавантаження при зміні коду)
#      )
