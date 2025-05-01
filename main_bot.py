# main_bot.py (Webhook Version - ASGI Wrapper + PTB Timeouts + Async Currency - Lazy Async Init)
import os
import logging
import asyncio
import json
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ApplicationBuilder
)
from telegram.request import HTTPXRequest
from asgiref.wsgi import WsgiToAsgi
import currency_converter
import unit_converter

# --- Налаштування логування ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Зменшуємо рівень логування для бібліотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING) # Змінено на WARNING
logging.getLogger("telegram.bot").setLevel(logging.WARNING) # Змінено на WARNING
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("asgiref").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Змінні середовища ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8080))

# --- Глобальні змінні ---
application: Application | None = None
initialization_error: Exception | None = None
init_lock = asyncio.Lock() # Блокування для асинхронної ініціалізації
is_async_initialized = False # Прапорець, що асинхронна частина виконана

# --- Обробники команд ---
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
        # Логуємо помилку, яка виникає при відправці
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
        from_unit = " ".join(args[1:-2]).strip().lower() # Конвертуємо в нижній регістр одразу
        to_unit = args[-1].strip().lower() # Конвертуємо в нижній регістр одразу
        amount = float(amount_str.replace(',', '.'))
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
        # Передаємо вже в нижньому регістрі
        unit_result = unit_converter.convert_units(amount, from_unit, to_unit)
        if unit_result is not None:
            logger.info(f"Unit conversion successful: {amount} {from_unit} -> {unit_result} {to_unit}")
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

    # Якщо одиниці не конвертувалися, спроба конвертації валюти (асинхронна функція)
    if not conversion_done:
        # Перевірка, чи схоже на коди валют (3 літери)
        # Використовуємо оригінальні аргументи для перевірки формату, але конвертуємо з from_unit.upper()
        original_from_unit = " ".join(args[1:-2]).strip()
        original_to_unit = args[-1].strip()
        is_potential_currency = (len(original_from_unit) == 3 and original_from_unit.isalpha() and
                                 len(original_to_unit) == 3 and original_to_unit.isalpha())

        logger.debug(f"Unit conversion failed or skipped, attempting currency conversion for: '{original_from_unit}' -> '{original_to_unit}' (Potential Currency: {is_potential_currency})")

        if is_potential_currency:
            try:
                # Викликаємо асинхронну функцію конвертації валют, передаючи ВЕЛИКІ літери
                currency_result = await currency_converter.convert_currency(amount, original_from_unit.upper(), original_to_unit.upper())
                if currency_result is not None:
                    logger.info(f"Currency conversion successful: {amount} {original_from_unit.upper()} -> {currency_result} {original_to_unit.upper()}")
                    reply_text = f"{amount} {original_from_unit.upper()} = {currency_result:.2f} {original_to_unit.upper()}"
                    conversion_done = True
                else:
                    logger.warning(f"Currency conversion function returned None for {original_from_unit.upper()} -> {original_to_unit.upper()}")
                    reply_text = (
                        f"Не вдалося конвертувати валюту {original_from_unit.upper()} в {original_to_unit.upper()}.\n"
                        f"Перевірте правильність кодів валют або спробуйте пізніше."
                    )
                    conversion_done = True # Помилка конвертації, але оброблено
            except Exception as e:
                logger.error(f"!!! EXCEPTION during currency conversion call for user {user_id} !!!: {e}", exc_info=True)
                reply_text = "Виникла внутрішня помилка при конвертації валюти."
                conversion_done = True # Помилка конвертації, але оброблено
        else:
             # Якщо не схоже на валюту і одиниці не розпізнались
             logger.warning(f"Could not recognize units/currency: '{from_unit}' or '{to_unit}' for user {user_id}")
             reply_text = (
                 f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'.\n"
                 f"Перевірте правильність написання або спробуйте /help."
             )
             conversion_done = True # Помилка розпізнавання, але оброблено

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
    """Встановлює вебхук для Telegram."""
    if not url:
        logger.error("WEBHOOK_URL не задано в змінних середовища!")
        return False
    logger.info(f"Attempting to set webhook to URL: {url}")
    try:
        await app.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        info = await app.bot.get_webhook_info()
        if info.url == url:
            logger.info(f"Webhook successfully set to {info.url}")
            if info.last_error_date:
                 last_error_ts = info.last_error_date.strftime('%Y-%m-%d %H:%M:%S') if info.last_error_date else 'N/A'
                 logger.warning(f"Webhook info reports previous error: Date={last_error_ts}, Message='{info.last_error_message}'")
            return True
        else:
            logger.error(f"Failed to set webhook. Current URL reported by Telegram: '{info.url}', Expected: '{url}'")
            return False
    except Exception as e:
        logger.error(f"CRITICAL ERROR during set_webhook/get_webhook_info: {e}", exc_info=True)
        return False

# --- Ініціалізація Telegram Application (Синхронна частина) ---
def initialize_telegram_app_sync() -> Application | None:
    """Створює та налаштовує об'єкт Application (без async initialize)."""
    global initialization_error
    logger.info("Initializing Telegram Application (sync part)...")
    if not BOT_TOKEN:
        initialization_error = RuntimeError("BOT_TOKEN не знайдено в змінних середовища!")
        logger.critical(initialization_error)
        return None
    try:
        request_settings = HTTPXRequest(
            connect_timeout=10.0,
            read_timeout=20.0,
            pool_timeout=15.0
        )
        logger.info("Configured PTB Request with custom timeouts.")

        builder = ApplicationBuilder().token(BOT_TOKEN).request(request_settings)
        app = builder.build()

        # Додаємо обробники
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("convert", convert_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
        app.add_handler(MessageHandler(filters.COMMAND, unknown))

        logger.info("Command and message handlers added.")
        initialization_error = None # Скидаємо помилку, якщо синхронна частина пройшла
        return app
    except Exception as e:
        initialization_error = e
        logger.critical(f"CRITICAL ERROR during Telegram Application sync setup: {e}", exc_info=True)
        return None

# --- Асинхронна частина ініціалізації ---
async def initialize_bot_async(app: Application) -> bool:
    """Виконує асинхронну ініціалізацію Application та встановлення вебхука."""
    global initialization_error, is_async_initialized
    logger.info("Starting async initialization (initialize, set_webhook)...")
    try:
        await app.initialize()
        logger.info("Telegram Application initialized successfully (async).")
        webhook_ok = await setup_webhook(app, WEBHOOK_URL)
        if not webhook_ok:
            logger.error("Webhook setup failed during async initialization.")
            # Не встановлюємо initialization_error, щоб дозволити спробувати ще раз?
            # Або встановити, щоб health check показував помилку? Поки не встановлюємо.
            return False # Позначаємо, що ініціалізація не завершена
        logger.info("Async initialization completed successfully.")
        is_async_initialized = True # Позначаємо, що все готово
        initialization_error = None # Якщо все добре, скидаємо помилку
        return True
    except Exception as e:
        logger.critical(f"CRITICAL ERROR during async application initialize/webhook setup: {e}", exc_info=True)
        initialization_error = e # Зберігаємо помилку
        is_async_initialized = False # Позначаємо, що не готово
        return False


# --- Flask App та маршрути ---
flask_app = Flask(__name__)

# Створюємо об'єкт Application синхронно при старті Flask
logger.info("Creating Telegram Application object synchronously...")
application = initialize_telegram_app_sync()
# Зберігаємо початковий стан у конфіг Flask
flask_app.config['TELEGRAM_APP'] = application
flask_app.config['INIT_ERROR'] = initialization_error
logger.info(f"Sync initialization finished. App object created: {application is not None}. Initial error: {initialization_error}")


@flask_app.route("/", methods=["GET", "HEAD"] )
@flask_app.route("/healthz", methods=["GET", "HEAD"])
def health_check():
    """Перевірка стану для Render."""
    # Перевіряємо помилку, що могла виникнути під час СИНХРОННОЇ ініціалізації
    sync_err = flask_app.config.get('INIT_ERROR')
    app_inst = flask_app.config.get('TELEGRAM_APP')
    status_code = 200
    message = "OK"

    if sync_err:
        logger.error(f"Health check failed due to sync initialization error: {sync_err}")
        status_code = 500
        message = f"Initialization Error: {sync_err}"
    elif not app_inst:
         logger.error("Health check failed: Telegram Application instance is missing.")
         status_code = 500
         message = "Error: Bot application not available"
    # Додатково можна перевіряти is_async_initialized, якщо потрібно сигналізувати,
    # що бот ще не готовий приймати запити (але Render може вважати це помилкою)
    elif not is_async_initialized:
        logger.warning("Health check: Bot async initialization is not yet complete.")
        # Повертаємо 200, щоб Render не перезапускав, але логуємо
        message = "OK (Initializing)"

    logger.info(f"Health check result: Status={status_code}, Message='{message}'")
    return message, status_code

@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    """Обробляє вхідні оновлення Telegram."""
    global application, initialization_error, is_async_initialized, init_lock
    app_inst = flask_app.config.get('TELEGRAM_APP') # Отримуємо з конфігу

    # Перевірка, чи був створений об'єкт Application взагалі
    if not app_inst:
        init_err = flask_app.config.get('INIT_ERROR', 'Unknown sync init error')
        logger.error(f"Webhook request received, but Application object is missing. Error: {init_err}")
        return Response(status=500)

    # --- Лінива асинхронна ініціалізація ---
    if not is_async_initialized:
        async with init_lock:
            # Перевіряємо ще раз всередині блокування, раптом інший запит вже ініціалізував
            if not is_async_initialized:
                logger.info("Performing lazy async initialization on first webhook request...")
                init_success = await initialize_bot_async(app_inst)
                if not init_success:
                    err = initialization_error or "Unknown async init error"
                    logger.error(f"Async initialization failed during webhook processing. Error: {err}")
                    # Зберігаємо помилку в конфіг Flask, щоб health check її бачив
                    flask_app.config['INIT_ERROR'] = initialization_error
                    return Response(status=500) # Повертаємо помилку, ініціалізація не вдалася
                else:
                    # Якщо ініціалізація пройшла успішно, оновлюємо конфіг
                     flask_app.config['INIT_ERROR'] = None
            # Якщо ми тут, значить is_async_initialized тепер True
    # -----------------------------------------

    # Якщо ми дійшли сюди, значить is_async_initialized == True
    logger.debug("--> Processing incoming request on /webhook...")
    update = None
    try:
        raw_data = request.get_data() # Синхронно
        if not raw_data:
             logger.warning("Received empty request body on /webhook.")
             return Response(status=200)

        try:
            data = json.loads(raw_data)
            logger.debug(f"Webhook received JSON data: {data}")
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON from webhook request: {json_err}. Raw data: {raw_data[:200]}...")
            return Response(status=400)

        update = Update.de_json(data, app_inst.bot)
        logger.info(f"Calling application.process_update for update_id: {update.update_id}...")

        await app_inst.process_update(update)

        logger.info(f"Finished application.process_update for update_id: {update.update_id}.")
        return Response(status=200)

    except Exception as e:
        update_id_str = f"update_id: {update.update_id}" if update else "update data unavailable"
        logger.error(f"!!! UNEXPECTED ERROR processing webhook update ({update_id_str}) !!!: {e}", exc_info=True)
        return Response(status=200) # Повертаємо 200, щоб Telegram не повторював

# --- Обгортка Flask -> ASGI ---
asgi_app = WsgiToAsgi(flask_app)
logger.info("Flask app wrapped with WsgiToAsgi for ASGI compatibility.")

# --- Запуск (для локального тестування) ---
# if __name__ == "__main__":
#     import uvicorn
#     logger.info("Starting Uvicorn development server (for local testing only)...")
#     uvicorn.run(
#         "main_bot:asgi_app",
#         host="0.0.0.0",
#         port=PORT,
#         log_level="info",
#         reload=True
#      )
