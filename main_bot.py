# main_bot.py (Webhook Version with Synchronous Init - Fixed Handler Placement)
import os
import logging
import asyncio
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder

# Імпортуємо наші конвертери
import currency_converter
import unit_converter

# --- Налаштування логування ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Функції-обробники команд (start, help_command, convert_command, unknown) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Надсилає привітальне повідомлення при команді /start."""
    user = update.effective_user
    # Додамо логування перед відправкою
    logger.info(f"Handling /start command for user {user.id}")
    try:
        await update.message.reply_html(
            f"Привіт, {user.mention_html()}!\n\n"
            f"Я бот-конвертер. Допоможу тобі конвертувати валюти та одиниці виміру.\n\n"
            f"<b>Як користуватися:</b>\n"
            f"Надішли повідомлення у форматі:\n"
            f"<code>/convert &lt;значення&gt; &lt;з_одиниці&gt; to &lt;в_одиницю&gt;</code>\n\n"
            f"<b>Приклади:</b>\n"
            f"<code>/convert 100 USD to UAH</code>\n"
            f"<code>/convert 5 km to m</code>\n"
            f"<code>/convert 10 kg to lb</code>\n\n"
            f"Використовуй команду /help для довідки.",
        )
        logger.info(f"Successfully replied to /start for user {user.id}")
    except Exception as e:
        logger.error(f"Error replying to /start for user {user.id}: {e}", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Надсилає довідкове повідомлення при команді /help."""
    logger.info(f"Handling /help command for user {update.effective_user.id}")
    try:
        await update.message.reply_text(
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
            "<b>Важливо:</b> Конвертація можлива тільки в межах однієї категорії (наприклад, метри в кілометри, але не кілограми в метри).",
            parse_mode='HTML'
        )
        logger.info(f"Successfully replied to /help for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error replying to /help for user {update.effective_user.id}: {e}", exc_info=True)


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду конвертації."""
    args = context.args
    user_id = update.effective_user.id
    logger.info(f"Handling /convert command for user {user_id} with args: {args}")

    if len(args) != 4 or args[2].lower() != 'to':
        try:
            await update.message.reply_text(
                "Неправильний формат команди. \n"
                "Використовуйте: `/convert <значення> <з_одиниці> to <в_одиницю>`\n"
                "Приклад: `/convert 100 USD to UAH`\n"
                "Спробуйте /help для довідки.",
            )
        except Exception as e:
             logger.error(f"Error sending format error message to user {user_id}: {e}", exc_info=True)
        return

    try:
        amount_str = args[0]
        from_unit = args[1]
        to_unit = args[3]
        amount = float(amount_str.replace(',', '.'))
    except ValueError:
        try:
            await update.message.reply_text(f"Помилка: '{amount_str}' не є дійсним числом.")
        except Exception as e:
            logger.error(f"Error sending ValueError message to user {user_id}: {e}", exc_info=True)
        return

    reply_text = ""
    # Спочатку спробуємо конвертувати як одиниці виміру
    unit_result = unit_converter.convert_units(amount, from_unit, to_unit)

    if unit_result is not None:
        reply_text = f"{amount} {from_unit.upper()} = {unit_result:.4f} {to_unit.upper()}"
    # Якщо не вдалося як одиниці, спробуємо як валюту
    elif len(from_unit) == 3 and len(to_unit) == 3 and from_unit.isalpha() and to_unit.isalpha():
        currency_result = currency_converter.convert_currency(amount, from_unit, to_unit)
        if currency_result is not None:
            reply_text = f"{amount} {from_unit.upper()} = {currency_result:.2f} {to_unit.upper()}"
        else:
            reply_text = (
                f"Не вдалося конвертувати {from_unit.upper()} в {to_unit.upper()}.\n"
                f"Перевірте правильність написання одиниць/валют або спробуйте /help."
            )
    else:
        reply_text = (
            f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'.\n"
            f"Перевірте правильність написання або спробуйте /help."
        )

    try:
        await update.message.reply_text(reply_text)
        logger.info(f"Successfully replied to /convert for user {user_id}")
    except Exception as e:
        logger.error(f"Error sending convert result to user {user_id}: {e}", exc_info=True)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє невідомі команди або звичайний текст."""
    user_id = update.effective_chat.id
    logger.info(f"Handling unknown command/text for chat {user_id}")
    try:
        await context.bot.send_message(chat_id=user_id,
                                    text="Вибачте, я не розумію цю команду. Спробуйте /help.")
    except Exception as e:
        logger.error(f"Error sending unknown command message to chat {user_id}: {e}", exc_info=True)


# --- Змінні середовища ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') # Потрібен для встановлення вебхука
PORT = int(os.environ.get('PORT', 8080))

# --- Глобальний об'єкт Application ---
application: Application | None = None
initialization_error: Exception | None = None

# --- Асинхронна функція для встановлення вебхука ---
async def setup_webhook(app: Application, webhook_url: str):
    """Встановлює URL вебхука для Telegram бота."""
    logger.info(f"Спроба встановити вебхук на URL: {webhook_url}")
    if not webhook_url:
        logger.error("ПОМИЛКА: WEBHOOK_URL порожній! Неможливо встановити вебхук.")
        return False
    try:
        await app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
        webhook_info = await app.bot.get_webhook_info()
        if webhook_info.url == webhook_url:
            logger.info(f"Вебхук успішно встановлено на {webhook_info.url}")
            return True
        else:
            logger.error(f"Не вдалося встановити вебхук. Поточний URL: {webhook_info.url}, очікуваний: {webhook_url}")
            return False
    except Exception as e:
        logger.error(f"ПОМИЛКА під час виклику set_webhook або get_webhook_info: {e}", exc_info=True)
        return False

# --- Синхронна ініціалізація при завантаженні модуля ---
def initialize_bot():
    global application, initialization_error
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN не знайдено. Бот не може бути ініціалізований.")
        initialization_error = RuntimeError("BOT_TOKEN не знайдено")
        return

    try:
        logger.info("Створення екземпляру Telegram Application...")
        application_builder = ApplicationBuilder().token(BOT_TOKEN)

        # Створюємо екземпляр Application СПОЧАТКУ
        application = application_builder.build()
        logger.info("Екземпляр Application створено.")

        # ДОДАЄМО ОБРОБНИКИ ДО СТВОРЕНОГО application
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("convert", convert_command))
        application.add_handler(MessageHandler(filters.COMMAND | filters.TEXT & ~filters.UpdateType.EDITED, unknown))
        logger.info("Обробники додані до Application.") # Виправлено лог

        # Запускаємо асинхронну ініціалізацію та встановлення вебхука в тимчасовому циклі
        logger.info("Запуск синхронної ініціалізації та встановлення вебхука...")
        # Використовуємо get_event_loop для сумісності
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError: # Якщо немає поточного циклу
             loop = asyncio.new_event_loop()
             asyncio.set_event_loop(loop)


        logger.info("Виклик application.initialize()...")
        loop.run_until_complete(application.initialize())
        logger.info("Application.initialize() завершено.")

        if WEBHOOK_URL:
            logger.info("Встановлення вебхука...")
            webhook_set_successfully = loop.run_until_complete(setup_webhook(application, WEBHOOK_URL))
            if not webhook_set_successfully:
                logger.warning("Не вдалося встановити вебхук під час ініціалізації.")
        else:
            logger.warning("Пропуск встановлення вебхука через відсутність WEBHOOK_URL.")

        # Закриваємо цикл, лише якщо ми його створили
        # if asyncio.get_event_loop() is loop:
        #     loop.close()
        #     logger.info("Синхронна ініціалізація завершена. Тимчасовий цикл закрито.")
        # Краще не закривати цикл тут, щоб уникнути проблем з Gunicorn/Flask

        logger.info("Синхронна ініціалізація завершена.")


    except Exception as e:
        logger.error(f"КРИТИЧНА ПОМИЛКА під час синхронної ініціалізації: {e}", exc_info=True)
        initialization_error = e
        application = None # Переконуємось, що application = None при помилці

# Викликаємо ініціалізацію одразу
initialize_bot()

# --- Визначення Flask App ---
flask_app = Flask(__name__)

# Зберігаємо посилання на application або помилку в конфіг Flask
if application:
    flask_app.config['TELEGRAM_APP'] = application
if initialization_error:
     flask_app.config['INIT_ERROR'] = initialization_error


# --- Обробники Flask (маршрути) ---
@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    """Обробляє вхідні оновлення Telegram через вебхук."""
    global application # Використовуємо глобальний application
    init_error = flask_app.config.get('INIT_ERROR')

    # Перевіряємо помилки ініціалізації
    if init_error:
         logger.error(f"Помилка ініціалізації перешкоджає обробці запиту: {init_error}")
         return Response(status=500) # Повертаємо помилку сервера
    if not application:
        logger.error("Помилка: Глобальний екземпляр Telegram Application не ініціалізовано!")
        return Response(status=500)

    # Перевіряємо, чи application ініціалізовано (на випадок, якщо initialize_bot не спрацював повністю)
    if not application.initialized:
        logger.warning("Application не було ініціалізовано раніше. Спроба ініціалізації зараз...")
        try:
            await application.initialize() # Спробуємо ініціалізувати асинхронно
            logger.info("Application успішно ініціалізовано в /webhook.")
        except Exception as e:
            logger.error(f"Помилка ініціалізації Application всередині /webhook: {e}", exc_info=True)
            return Response(status=500)

    logger.debug("Обробка запиту на /webhook...")
    try:
        update_data = request.get_json()
        if not update_data:
             logger.warning("Отримано порожні JSON дані на /webhook.")
             return Response(status=200)

        logger.info(f"Отримано оновлення: {update_data}")
        update = Update.de_json(update_data, application.bot)

        # Запускаємо обробку оновлення
        # Використовуємо create_task з поточного циклу подій
        loop = asyncio.get_running_loop()
        loop.create_task(application.process_update(update))

        logger.debug("Завдання process_update створено. Надсилання відповіді 200 OK до Telegram.")
        return Response(status=200)
    except Exception as e:
        logger.error(f"Неочікувана помилка обробки оновлення вебхука: {e}", exc_info=True)
        # Все одно повертаємо 200, щоб Telegram не надсилав це оновлення повторно
        return Response(status=200)


@flask_app.route("/")
@flask_app.route("/healthz")
def health_check():
    """Базовий маршрут для перевірки стану сервісу."""
    init_error = flask_app.config.get('INIT_ERROR')
    if init_error:
        logger.error(f"Health check failed due to initialization error: {init_error}")
        return f"Initialization Error: {init_error}", 500 # Повертаємо помилку, якщо ініціалізація не вдалась
    logger.info("Запит на перевірку стану (/ або /healthz)")
    return "OK", 200

# --- Немає потреби в main() чи asyncio.run() тут, Gunicorn запускає flask_app ---

