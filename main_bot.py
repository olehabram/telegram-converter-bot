# main_bot.py (Webhook Version - ASGI Wrapper + PTB Timeouts + Async Currency)
import os
import logging
import asyncio
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
# Зменшуємо "шум" від бібліотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)
logging.getLogger("telegram.bot").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("asgiref").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Змінні середовища ---
# Переконайся, що ці змінні встановлені на Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# WEBHOOK_URL має бути повним URL: https://your-app-name.onrender.com/webhook
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8080)) # Render надає порт через $PORT

# --- Глобальні змінні ---
application: Application | None = None
initialization_error: Exception | None = None

# --- Обробники команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /start."""
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
    """Обробник команди /help."""
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
    """Обробник команди /convert."""
    args = context.args # Використовуємо context.args для отримання аргументів команди
    user_id = update.effective_user.id
    logger.info(f"--> Entering /convert handler for user {user_id} with args: {args}")

    # Перевірка формату: /convert <значення> <з> to <в>
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

    # Парсинг аргументів
    try:
        amount_str = args[0]
        # Одиниця "з" може складатися з кількох слів
        from_unit = " ".join(args[1:-2])
        to_unit = args[-1]
        amount = float(amount_str.replace(',', '.'))
        logger.debug(f"Parsed conversion: {amount} '{from_unit}' -> '{to_unit}'")
    except ValueError:
        logger.warning(f"Invalid number format '{amount_str}' from user {user_id}")
        try:
            await update.message.reply_text(f"Помилка: '{amount_str}' не є дійсним числом.")
        except Exception as e:
            logger.error(f"Error sending ValueError message for /convert to user {user_id}: {e}", exc_info=True)
        return
    except Exception as e: # Інші можливі помилки парсингу
        logger.error(f"Unexpected error parsing /convert args for user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Виникла помилка при обробці вашого запиту.")
        except Exception as e_reply:
             logger.error(f"Error sending generic parsing error message to user {user_id}: {e_reply}", exc_info=True)
        return

    reply_text = ""
    conversion_done = False

    # 1. Спроба конвертації одиниць (синхронна функція)
    logger.debug(f"Attempting unit conversion for: {amount} '{from_unit}' -> '{to_unit}'")
    unit_result = unit_converter.convert_units(amount, from_unit, to_unit)
    if unit_result is not None:
        logger.info(f"Unit conversion successful: {amount} {from_unit} -> {unit_result} {to_unit}")
        # Форматуємо результат, прибираючи зайві нулі для цілих чисел
        if unit_result == int(unit_result):
            reply_text = f"{amount} {from_unit.upper()} = {int(unit_result)} {to_unit.upper()}"
        else:
            reply_text = f"{amount} {from_unit.upper()} = {unit_result:.4f} {to_unit.upper()}"
        conversion_done = True

    # 2. Якщо не одиниці, спроба конвертації валют (асинхронна функція)
    if not conversion_done:
        logger.debug(f"Unit conversion failed, attempting currency conversion for: '{from_unit}' -> '{to_unit}'")
        # Перевіряємо, чи схоже на коди валют (3 літери)
        is_potential_currency = (len(from_unit) == 3 and from_unit.isalpha() and len(to_unit) == 3 and to_unit.isalpha())
        if is_potential_currency:
            try:
                # --- ВИКЛИКАЄМО АСИНХРОННИЙ КОНВЕРТЕР ВАЛЮТ ---
                currency_result = await currency_converter.convert_currency(amount, from_unit, to_unit)
                # ---------------------------------------------
                if currency_result is not None:
                    # Лог успіху вже є всередині convert_currency
                    reply_text = f"{amount} {from_unit.upper()} = {currency_result:.2f} {to_unit.upper()}"
                    conversion_done = True
                else:
                    # Лог помилки вже є всередині convert_currency або get_exchange_rates
                    logger.warning(f"Currency conversion function returned None for {from_unit} -> {to_unit}")
                    reply_text = (
                        f"Не вдалося конвертувати валюту {from_unit.upper()} в {to_unit.upper()}.\n"
                        f"Перевірте правильність кодів валют або спробуйте /help."
                    )
            except Exception as e:
                logger.error(f"!!! EXCEPTION during currency conversion call for user {user_id} !!!: {e}", exc_info=True)
                reply_text = "Виникла внутрішня помилка при конвертації валюти."
        else:
             # Якщо не схоже на валюту і не одиниця виміру
            logger.warning(f"Could not recognize units/currency: '{from_unit}' or '{to_unit}' for user {user_id}")
            reply_text = (
                f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'.\n"
                f"Перевірте правильність написання або спробуйте /help."
            )

    # Якщо так і не вдалося нічого сконвертувати (малоймовірно, але можливо)
    if not conversion_done and not reply_text:
         reply_text = "Не вдалося виконати конвертацію. Перевірте формат запиту."

    # Надсилаємо фінальну відповідь
    try:
        await update.message.reply_text(reply_text)
        logger.info(f"<-- Successfully sent /convert reply to user {user_id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending final /convert reply to user {user_id} !!!: {e}", exc_info=True)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник для невідомих команд або простого тексту."""
    logger.info(f"--> Handling unknown command/text from chat {update.effective_chat.id}")
    try:
        await update.message.reply_text("Невідома команда або формат. Спробуйте /help.")
        logger.info(f"<-- Sent 'unknown command' message to chat {update.effective_chat.id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION sending 'unknown command' message to chat {update.effective_chat.id} !!!: {e}", exc_info=True)

# --- Налаштування вебхука ---
async def setup_webhook(app: Application, url: str) -> bool:
    """Встановлює вебхук для бота."""
    if not url:
        logger.error("WEBHOOK_URL не задано в змінних середовища!")
        return False
    logger.info(f"Attempting to set webhook to URL: {url}")
    try:
        # Встановлюємо вебхук з видаленням очікуючих оновлень (опційно, але корисно при перезапуску)
        await app.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        info = await app.bot.get_webhook_info()
        if info.url == url:
            logger.info(f"Webhook successfully set to {info.url}")
            if info.last_error_date:
                 logger.warning(f"Webhook info reports previous error date: {info.last_error_date}, message: {info.last_error_message}")
            return True
        else:
            logger.error(f"Failed to set webhook. Current URL: '{info.url}', Expected: '{url}'")
            return False
    except Exception as e:
        logger.error(f"CRITICAL ERROR during set_webhook/get_webhook_info: {e}", exc_info=True)
        return False

# --- Ініціалізація Telegram Application ---
def initialize_telegram_app() -> Application | None:
    """Створює та налаштовує екземпляр Telegram Application."""
    global initialization_error
    logger.info("Initializing Telegram Application...")
    if not BOT_TOKEN:
        initialization_error = RuntimeError("BOT_TOKEN не знайдено")
        logger.critical(initialization_error)
        return None
    try:
        # Налаштування таймаутів для HTTP-запитів бібліотеки
        request_settings = HTTPXRequest(
            connect_timeout=10.0,
            read_timeout=20.0,
            pool_timeout=15.0
        )
        logger.info("Configured PTB Request with custom timeouts.")

        # Створюємо Application
        builder = ApplicationBuilder().token(BOT_TOKEN).request(request_settings)
        app = builder.build()

        # Додаємо обробники
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("convert", convert_command))
        # Обробник для простого тексту (не команд)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
        # Обробник для невідомих команд (має бути останнім)
        app.add_handler(MessageHandler(filters.COMMAND, unknown))

        logger.info("Command and message handlers added.")
        return app
    except Exception as e:
        initialization_error = e
        logger.critical(f"CRITICAL ERROR during Telegram Application setup: {e}", exc_info=True)
        return None

# --- Асинхронне завантаження та налаштування ---
async def startup():
    """Виконує асинхронну ініціалізацію бота та вебхука."""
    global application, initialization_error
    logger.info("Початок асинхронної ініціалізації (startup)...")
    application = initialize_telegram_app()
    if application:
        logger.info("Initializing Telegram Application object...")
        try:
            # Важливо: application.initialize() готує об'єкт до роботи
            await application.initialize()
            logger.info("Telegram Application initialized successfully.")
            # Встановлення вебхука ПІСЛЯ ініціалізації
            webhook_ok = await setup_webhook(application, WEBHOOK_URL)
            if not webhook_ok:
                logger.warning("Webhook setup failed or URL not provided.")
                # Розгляньте можливість встановлення initialization_error тут, якщо вебхук критичний
                # initialization_error = RuntimeError("Failed to set webhook")
        except Exception as e:
            logger.critical(f"CRITICAL ERROR during async application initialize/webhook setup: {e}", exc_info=True)
            initialization_error = e
            application = None # Робимо недоступним при помилці
    else:
        logger.critical("Telegram Application object could not be created.")

    # Зберігаємо стан у конфіг Flask для перевірки стану
    flask_app.config['TELEGRAM_APP'] = application
    flask_app.config['INIT_ERROR'] = initialization_error
    logger.info("Асинхронна ініціалізація (startup) завершена.")

# --- Flask App та маршрути ---
flask_app = Flask(__name__) # Створюємо Flask app

# Запускаємо асинхронну ініціалізацію ПЕРЕД створенням маршрутів
try:
    logger.info("Starting asyncio.run(startup())...")
    asyncio.run(startup())
    logger.info("asyncio.run(startup()) finished.")
except Exception as e:
     logger.critical(f"CRITICAL ERROR running asyncio.run(startup): {e}", exc_info=True)
     if not initialization_error:
          initialization_error = e
     flask_app.config['INIT_ERROR'] = initialization_error
     flask_app.config['TELEGRAM_APP'] = None # Явно вказуємо, що додаток не готовий

# Маршрут для перевірки стану (health check)
@flask_app.route("/", methods=["GET", "HEAD"] )
@flask_app.route("/healthz", methods=["GET", "HEAD"])
def health_check():
    """Перевіряє, чи бот ініціалізовано."""
    err = flask_app.config.get('INIT_ERROR')
    app_inst = flask_app.config.get('TELEGRAM_APP')
    if err:
        logger.error(f"Health check failed due to initialization error: {err}")
        return f"Initialization Error: {err}", 500
    elif not app_inst:
         logger.error("Health check failed: Telegram Application instance is missing.")
         return "Error: Bot application not available", 500
    else:
        logger.info("Health check requested - OK")
        return "OK", 200

# Маршрут для отримання вебхуків від Telegram
@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    """Обробляє вхідні оновлення Telegram."""
    err = flask_app.config.get('INIT_ERROR')
    app_inst = flask_app.config.get('TELEGRAM_APP')

    # Перевірка ініціалізації
    if err or not app_inst:
        logger.error(f"Webhook request received, but initialization failed or app not available. Error: {err}")
        return Response(status=500)

    # Обробка запиту
    logger.debug("--> Processing incoming request on /webhook...")
    update = None # Ініціалізуємо update
    try:
        # Використовуємо await для асинхронного Flask
        data = await request.get_json()
        if not data:
            logger.warning("Received empty JSON data on /webhook.")
            return Response(status=200) # Відповідь ОК, щоб Telegram не повторював

        update = Update.de_json(data, app_inst.bot)
        logger.info(f"Calling application.process_update for update_id: {update.update_id}...")
        # --- ВИКОРИСТОВУЄМО process_update ---
        await app_inst.process_update(update)
        # -----------------------------------
        logger.info(f"Finished application.process_update for update_id: {update.update_id}.")
        return Response(status=200) # Завжди повертаємо 200 OK для Telegram

    except Exception as e:
        update_id_str = f"update_id: {update.update_id}" if update else "update data unavailable"
        logger.error(f"!!! UNEXPECTED ERROR processing webhook update ({update_id_str}) !!!: {e}", exc_info=True)
        # Все одно повертаємо 200, щоб Telegram не надсилав це оновлення повторно
        return Response(status=200)

# Обгортка Flask -> ASGI для Gunicorn + Uvicorn
# Gunicorn буде використовувати 'asgi_app'
asgi_app = WsgiToAsgi(flask_app)
logger.info("Flask app wrapped with WsgiToAsgi for ASGI compatibility.")

# --- Запуск (для локального тестування) ---
# if __name__ == "__main__":
#     import uvicorn
#     logger.info("Starting Uvicorn development server (for local testing only)...")
#     # Запускаємо asgi_app, а не flask_app
#     uvicorn.run("main_bot:asgi_app", host="0.0.0.0", port=PORT, log_level="info")

