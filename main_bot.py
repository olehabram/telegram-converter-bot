# main_bot.py (Webhook Version - Refactored Initialization)
import os
import logging
import asyncio
from flask import Flask, request, Response
from telegram import Update, Bot # Додано Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder, ExtBot # Додано ExtBot

# Імпортуємо наші конвертери
import currency_converter
import unit_converter

# --- Налаштування логування ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Встановіть logging.DEBUG для більш детальних логів
)
# Зменшуємо рівень логування для бібліотек, які можуть бути "галасливими"
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO) # Можна змінити на WARNING
logging.getLogger("telegram.bot").setLevel(logging.INFO) # Можна змінити на WARNING
logging.getLogger("asyncio").setLevel(logging.INFO) # Можна змінити на WARNING

logger = logging.getLogger(__name__)

# --- Змінні середовища ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') # Потрібен для встановлення вебхука
PORT = int(os.environ.get('PORT', 8080)) # Render зазвичай надає порт через змінну PORT

# --- Глобальний об'єкт Application (ініціалізується пізніше) ---
application: Application | None = None
initialization_error: Exception | None = None

# --- Функції-обробники команд (start, help_command, convert_command, unknown) ---
# (Залишаються без змін, але додамо трохи логування для діагностики)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Надсилає привітальне повідомлення при команді /start."""
    user = update.effective_user
    logger.info(f"--> Entering /start handler for user {user.id}") # Лог входу
    reply_content = (
        f"Привіт, {user.mention_html()}!\n\n"
        f"Я бот-конвертер. Допоможу тобі конвертувати валюти та одиниці виміру.\n\n"
        f"<b>Як користуватися:</b>\n"
        f"Надішли повідомлення у форматі:\n"
        f"<code>/convert &lt;значення&gt; &lt;з_одиниці&gt; to &lt;в_одиницю&gt;</code>\n\n"
        f"<b>Приклади:</b>\n"
        f"<code>/convert 100 USD to UAH</code>\n"
        f"<code>/convert 5 km to m</code>\n"
        f"<code>/convert 10 kg to lb</code>\n\n"
        f"Використовуй команду /help для довідки."
    )
    logger.debug(f"Preparing to send /start reply to user {user.id}")
    try:
        await update.message.reply_html(reply_content)
        logger.info(f"<-- Successfully sent /start reply to user {user.id}") # Лог успіху
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending /start reply to user {user.id} !!!: {e}", exc_info=True)
        # Спробуємо надіслати просте повідомлення про помилку
        try:
            await update.message.reply_text("Вибачте, сталася помилка при обробці команди /start.")
        except Exception as inner_e:
            logger.error(f"!!! FAILED even to send error message for /start to user {user.id} !!!: {inner_e}", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Надсилає довідкове повідомлення при команді /help."""
    user_id = update.effective_user.id
    logger.info(f"--> Entering /help handler for user {user_id}") # Лог входу
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
        "  Довжина: mm, cm, m, km, in, ft, mi\n"
        "  Маса: mg, g, kg, t, oz, lb\n"
        "  Об'єм: ml, l, m3, gal\n\n"
        "<b>Важливо:</b> Конвертація можлива тільки в межах однієї категорії (наприклад, метри в кілометри, але не кілограми в метри)."
    )
    logger.debug(f"Preparing to send /help reply to user {user_id}")
    try:
        await update.message.reply_html(help_text)
        logger.info(f"<-- Successfully sent /help reply to user {user_id}") # Лог успіху
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending /help reply to user {user_id} !!!: {e}", exc_info=True)
        try:
            await update.message.reply_text("Вибачте, сталася помилка при обробці команди /help.")
        except Exception as inner_e:
            logger.error(f"!!! FAILED even to send error message for /help to user {user_id} !!!: {inner_e}", exc_info=True)


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду конвертації."""
    args = context.args
    user_id = update.effective_user.id
    logger.info(f"--> Entering /convert handler for user {user_id} with args: {args}") # Лог входу

    if not args or len(args) < 3 or args[-2].lower() != 'to': # Гнучкіша перевірка
        logger.warning(f"Invalid /convert format from user {user_id}. Args: {args}")
        try:
            await update.message.reply_text(
                "Неправильний формат команди. \n"
                "Використовуйте: `/convert <значення> <з_одиниці> to <в_одиницю>`\n"
                "Приклад: `/convert 100 USD to UAH`\n"
                "Спробуйте /help для довідки.",
            )
        except Exception as e:
             logger.error(f"Error sending format error message for /convert to user {user_id}: {e}", exc_info=True)
        return

    try:
        # Об'єднуємо можливі частини значення та одиниць
        amount_str = args[0]
        from_unit = args[1]
        to_unit = args[-1] # Остання частина - цільова одиниця

        # Якщо між значенням і 'to' більше одного слова, об'єднуємо їх у from_unit
        if len(args) > 4:
             from_unit = " ".join(args[1:-2]) # Все між значенням і 'to'

        amount = float(amount_str.replace(',', '.'))
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
        except Exception: pass # Ignore if we can't even send this
        return


    reply_text = ""
    logger.debug(f"Attempting unit conversion for: {amount} {from_unit} -> {to_unit}")
    # Спочатку спробуємо конвертувати як одиниці виміру
    unit_result = unit_converter.convert_units(amount, from_unit, to_unit)

    if unit_result is not None:
        logger.info(f"Unit conversion successful: {amount} {from_unit} -> {unit_result} {to_unit}")
        # Форматуємо результат, уникаючи зайвих нулів для цілих чисел
        if unit_result == int(unit_result):
             reply_text = f"{amount} {from_unit.upper()} = {int(unit_result)} {to_unit.upper()}"
        else:
             reply_text = f"{amount} {from_unit.upper()} = {unit_result:.4f} {to_unit.upper()}"
    else:
        logger.debug(f"Unit conversion failed, attempting currency conversion for: {from_unit} -> {to_unit}")
        # Якщо не вдалося як одиниці, спробуємо як валюту (перевірка на 3 літери)
        # Перевіряємо, чи ОБИДВІ одиниці схожі на коди валют
        is_potential_currency = (
            len(from_unit) == 3 and from_unit.isalpha() and
            len(to_unit) == 3 and to_unit.isalpha()
        )
        if is_potential_currency:
            currency_result = currency_converter.convert_currency(amount, from_unit, to_unit)
            if currency_result is not None:
                logger.info(f"Currency conversion successful: {amount} {from_unit} -> {currency_result} {to_unit}")
                reply_text = f"{amount} {from_unit.upper()} = {currency_result:.2f} {to_unit.upper()}"
            else:
                logger.warning(f"Currency conversion failed for {from_unit} -> {to_unit}")
                reply_text = (
                    f"Не вдалося конвертувати валюту {from_unit.upper()} в {to_unit.upper()}.\n"
                    f"Перевірте правильність кодів валют або спробуйте /help."
                )
        else:
            # Якщо не схоже на валюту і не одиниця виміру
            logger.warning(f"Could not recognize units/currency: '{from_unit}' or '{to_unit}'")
            reply_text = (
                f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'.\n"
                f"Перевірте правильність написання або спробуйте /help."
            )

    logger.debug(f"Preparing to send /convert result to user {user_id}: '{reply_text}'")
    try:
        await update.message.reply_text(reply_text)
        logger.info(f"<-- Successfully sent /convert reply to user {user_id}") # Лог успіху
    except Exception as e:
        logger.error(f"!!! EXCEPTION while sending /convert reply to user {user_id} !!!: {e}", exc_info=True)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє невідомі команди або звичайний текст."""
    user_id = update.effective_chat.id
    logger.info(f"--> Handling unknown command/text for chat {user_id}") # Лог входу
    try:
        await context.bot.send_message(chat_id=user_id,
                                    text="Вибачте, я не розумію цю команду. Спробуйте /help.")
        logger.info(f"<-- Sent 'unknown command' message to chat {user_id}")
    except Exception as e:
        logger.error(f"!!! EXCEPTION sending 'unknown command' message to chat {user_id} !!!: {e}", exc_info=True)

# --- Асинхронна функція для встановлення вебхука ---
async def setup_bot_webhook(app: Application, webhook_url: str):
    """Встановлює URL вебхука для Telegram бота."""
    logger.info(f"Attempting to set webhook to URL: {webhook_url}")
    if not webhook_url:
        logger.error("CRITICAL: WEBHOOK_URL is empty! Cannot set webhook.")
        return False
    try:
        # Встановлюємо вебхук
        await app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            # drop_pending_updates=True # Розкоментуйте, якщо хочете ігнорувати старі оновлення при перезапуску
        )
        # Перевіряємо, чи вебхук встановлено правильно
        webhook_info = await app.bot.get_webhook_info()
        if webhook_info.url == webhook_url:
            logger.info(f"Webhook successfully set to {webhook_info.url}")
            if webhook_info.last_error_date:
                 logger.warning(f"Webhook info reports last error date: {webhook_info.last_error_date}, message: {webhook_info.last_error_message}")
            return True
        else:
            logger.error(f"Failed to set webhook. Current URL: '{webhook_info.url}', Expected: '{webhook_url}'")
            # Спробуємо видалити старий вебхук, якщо він є
            logger.info("Attempting to delete existing webhook...")
            if await app.bot.delete_webhook():
                 logger.info("Existing webhook deleted. Try deploying again or setting manually.")
            else:
                 logger.warning("Failed to delete existing webhook.")
            return False
    except Exception as e:
        logger.error(f"CRITICAL ERROR during set_webhook/get_webhook_info: {e}", exc_info=True)
        return False

# --- Ініціалізація програми ---
def initialize_telegram_app() -> Application | None:
    """Створює та налаштовує екземпляр Telegram Application."""
    global initialization_error
    logger.info("Initializing Telegram Application...")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not found. Bot cannot start.")
        initialization_error = RuntimeError("BOT_TOKEN not found")
        return None

    try:
        # Створюємо ApplicationBuilder
        builder = ApplicationBuilder().token(BOT_TOKEN)
        # Можна додати налаштування, наприклад, ліміти з'єднань:
        # builder.pool_timeout(30).connect_timeout(30).read_timeout(30)

        # Створюємо екземпляр Application
        app = builder.build()
        logger.info("Telegram Application instance created.")

        # Додаємо обробники
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("convert", convert_command))
        # Обробник для невідомих команд повинен бути останнім
        app.add_handler(MessageHandler(filters.COMMAND | filters.TEXT & ~filters.UpdateType.EDITED, unknown))
        logger.info("Command and message handlers added.")

        return app

    except Exception as e:
        logger.critical(f"CRITICAL ERROR during Telegram Application setup: {e}", exc_info=True)
        initialization_error = e
        return None

# --- Створення Flask App ---
flask_app = Flask(__name__)

# --- Асинхронна функція для запуску перед першим запитом ---
async def startup():
    """Виконує асинхронну ініціалізацію бота."""
    global application, initialization_error
    logger.info("Running async startup tasks...")

    application = initialize_telegram_app() # Створюємо та налаштовуємо обробники

    if application:
        logger.info("Initializing Telegram Application object...")
        try:
            await application.initialize() # Асинхронна ініціалізація PTB
            logger.info("Telegram Application initialized successfully.")

            # Встановлення вебхука (якщо URL задано)
            if WEBHOOK_URL:
                 webhook_set = await setup_bot_webhook(application, WEBHOOK_URL)
                 if not webhook_set:
                      logger.warning("Webhook setup failed during startup. Bot might not receive updates.")
                      # Можна встановити помилку, якщо вебхук критичний
                      # initialization_error = RuntimeError("Failed to set webhook")
            else:
                 logger.warning("WEBHOOK_URL not set. Skipping webhook setup. Bot will not receive updates via webhook.")
                 # initialization_error = RuntimeError("WEBHOOK_URL is required for webhook mode")

        except Exception as e:
            logger.critical(f"CRITICAL ERROR during async application initialize/webhook setup: {e}", exc_info=True)
            initialization_error = e
            application = None # Зробити недоступним, якщо ініціалізація не вдалась
    else:
        logger.critical("Telegram Application object could not be created. Check previous logs.")
        # initialization_error вже має бути встановлено в initialize_telegram_app

    # Зберігаємо стан у конфіг Flask (на випадок, якщо потрібно)
    flask_app.config['TELEGRAM_APP'] = application
    flask_app.config['INIT_ERROR'] = initialization_error
    logger.info("Async startup tasks finished.")


# --- Реєстрація асинхронної функції запуску ---
# Flask < 2.3 використовує before_first_request (синхронний)
# Flask >= 2.3 використовує @flask_app.before_app_request або @flask_app.cli.command("init-bot")
# Найпростіший варіант для Gunicorn з Uvicorn - запустити startup() перед запуском Flask app.
# Ми запустимо його вручну перед створенням маршрутів.

# Запускаємо асинхронну ініціалізацію
try:
    logger.info("Starting asyncio.run(startup())...")
    asyncio.run(startup())
    logger.info("asyncio.run(startup()) finished.")
except Exception as e:
     logger.critical(f"CRITICAL ERROR running asyncio.run(startup): {e}", exc_info=True)
     # Переконуємось, що помилка зафіксована
     if not initialization_error:
          initialization_error = e
     flask_app.config['INIT_ERROR'] = initialization_error
     flask_app.config['TELEGRAM_APP'] = None # Явно вказуємо, що додаток не готовий


# --- Обробники Flask (маршрути) ---
@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    """Обробляє вхідні оновлення Telegram через вебхук."""
    # Отримуємо application та помилку з конфігу, встановлені під час startup
    current_app = flask_app.config.get('TELEGRAM_APP')
    init_error = flask_app.config.get('INIT_ERROR')

    # Перевіряємо помилки ініціалізації
    if init_error:
         logger.error(f"Webhook request received, but initialization failed: {init_error}")
         return Response(status=500, response=f"Bot initialization error: {init_error}")
    if not current_app:
        logger.error("Webhook request received, but Telegram Application is not available!")
        return Response(status=500, response="Bot application not initialized")

    logger.debug("--> Processing incoming request on /webhook...")
    try:
        update_data = request.get_json()
        if not update_data:
             logger.warning("Received empty JSON data on /webhook.")
             # Повертаємо 200, щоб Telegram не повторював порожній запит
             return Response(status=200)

        # Логуємо частину даних для діагностики (не повний update_data, щоб уникнути чутливої інформації в логах)
        log_data_snippet = str(update_data)[:200] # Перші 200 символів
        logger.info(f"Received update data (snippet): {log_data_snippet}...")

        # Десеріалізуємо оновлення
        update = Update.de_json(update_data, current_app.bot)
        logger.debug(f"Update deserialized successfully for update_id: {update.update_id}")

        # Обробляємо оновлення
        logger.info(f"Calling application.process_update for update_id: {update.update_id}...")
        await current_app.process_update(update)
        logger.info(f"Finished application.process_update for update_id: {update.update_id}.")

        logger.debug("<-- Finished processing /webhook request. Sending 200 OK.")
        return Response(status=200) # Завжди повертаємо 200 OK для Telegram

    except Exception as e:
        update_id = "N/A"
        try:
            # Спробуємо отримати update_id з даних, якщо можливо
            if isinstance(update_data, dict):
                update_id = update_data.get('update_id', 'N/A')
        except Exception: pass
        logger.error(f"!!! UNEXPECTED ERROR processing webhook update (update_id: {update_id}) !!!: {e}", exc_info=True)
        # Все одно повертаємо 200, щоб Telegram не надсилав це оновлення повторно
        return Response(status=200)


@flask_app.route("/")
@flask_app.route("/healthz")
def health_check():
    """Базовий маршрут для перевірки стану сервісу."""
    init_error = flask_app.config.get('INIT_ERROR')
    app_instance = flask_app.config.get('TELEGRAM_APP')

    if init_error:
        logger.error(f"Health check failed due to initialization error: {init_error}")
        return f"Initialization Error: {init_error}", 500
    elif not app_instance:
         logger.error("Health check failed: Telegram Application instance is missing.")
         return "Error: Bot application not available", 500
    else:
        logger.info("Health check requested (/ or /healthz) - OK")
        return "OK", 200

# --- Запуск Flask (для локального тестування, не для Gunicorn) ---
# if __name__ == "__main__":
#     logger.info("Starting Flask development server (for local testing only)...")
#     # Зауважте: цей спосіб запуску може не повністю імітувати Gunicorn/Uvicorn
#     flask_app.run(host='0.0.0.0', port=PORT, debug=False) # debug=True може викликати подвійну ініціалізацію
