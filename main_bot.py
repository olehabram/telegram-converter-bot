# main_bot.py (Webhook Version)
import os
import logging
import asyncio
from flask import Flask, request, Response # Імпортуємо Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Імпортуємо наші конвертери
import currency_converter
import unit_converter

# --- Налаштування логування ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Встановлюємо рівень логування для httpx (використовується python-telegram-bot) на WARNING,
# щоб уникнути занадто детальних логів запитів
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Функції-обробники команд (start, help_command, convert_command, unknown) ---
# --- Залишаються без змін з вашого попереднього коду ---
# (Переконайтеся, що вони тут присутні у вашому файлі)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Надсилає привітальне повідомлення при команді /start."""
    user = update.effective_user
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Надсилає довідкове повідомлення при команді /help."""
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


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє команду конвертації."""
    args = context.args
    logger.info(f"Отримано команду /convert з аргументами: {args}")

    if len(args) != 4 or args[2].lower() != 'to':
        await update.message.reply_text(
            "Неправильний формат команди. \n"
            "Використовуйте: `/convert <значення> <з_одиниці> to <в_одиницю>`\n"
            "Приклад: `/convert 100 USD to UAH`\n"
            "Спробуйте /help для довідки.",
        )
        return

    try:
        amount_str = args[0]
        from_unit = args[1]
        to_unit = args[3]
        amount = float(amount_str.replace(',', '.'))
    except ValueError:
        await update.message.reply_text(f"Помилка: '{amount_str}' не є дійсним числом.")
        return

    # Спочатку спробуємо конвертувати як одиниці виміру
    unit_result = unit_converter.convert_units(amount, from_unit, to_unit)

    if unit_result is not None:
        await update.message.reply_text(f"{amount} {from_unit.upper()} = {unit_result:.4f} {to_unit.upper()}")
        return

    # Якщо не вдалося як одиниці, спробуємо як валюту
    if len(from_unit) == 3 and len(to_unit) == 3 and from_unit.isalpha() and to_unit.isalpha():
        currency_result = currency_converter.convert_currency(amount, from_unit, to_unit)

        if currency_result is not None:
            await update.message.reply_text(f"{amount} {from_unit.upper()} = {currency_result:.2f} {to_unit.upper()}")
        else:
            await update.message.reply_text(
                f"Не вдалося конвертувати {from_unit.upper()} в {to_unit.upper()}.\n"
                f"Перевірте правильність написання одиниць/валют або спробуйте /help."
            )
    else:
        await update.message.reply_text(
            f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'.\n"
            f"Перевірте правильність написання або спробуйте /help."
        )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє невідомі команди або звичайний текст."""
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Вибачте, я не розумію цю команду. Спробуйте /help.")


# --- Змінні середовища ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# Повна URL-адреса, куди Telegram надсилатиме оновлення (наприклад, https://your-app-name.onrender.com/webhook)
# Цю змінну потрібно буде встановити на платформі розгортання (Render, Railway)
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
# Порт, який надає платформа хостингу (Render/Railway часто використовують змінну PORT)
PORT = int(os.environ.get('PORT', 8080)) # Стандартний порт для веб-сервісів, якщо не вказано інше

# --- Налаштування програми бота ---
if not BOT_TOKEN:
    logger.critical("ПОМИЛКА: Не знайдено змінну середовища BOT_TOKEN!")
    exit() # Зупиняємо скрипт, якщо немає токена

# Створюємо екземпляр Application
application = Application.builder().token(BOT_TOKEN).build()

# --- Реєстрація обробників команд ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("convert", convert_command))
application.add_handler(MessageHandler(filters.COMMAND | filters.TEXT & ~filters.UpdateType.EDITED, unknown))

# --- Налаштування Flask App ---
flask_app = Flask(__name__)

@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    """Обробляє вхідні оновлення Telegram через вебхук."""
    logger.debug("Отримано запит на вебхук...")
    try:
        # Отримуємо дані оновлення з тіла запиту
        update_data = request.get_json()
        if not update_data:
             logger.warning("Отримано порожні JSON дані.")
             return Response(status=200) # Підтверджуємо отримання

        logger.info(f"Отримано оновлення: {update_data}")

        # Створюємо об'єкт Update
        update = Update.de_json(update_data, application.bot)

        # Обробляємо оновлення асинхронно, щоб не блокувати Flask
        # Це важливо, оскільки Telegram очікує швидку відповідь (200 OK)
        asyncio.create_task(application.process_update(update))

        # Негайно повертаємо відповідь 200 OK для Telegram
        logger.debug("Надіслано відповідь 200 OK до Telegram.")
        return Response(status=200)
    except Exception as e:
        logger.error(f"Помилка обробки оновлення вебхука: {e}", exc_info=True)
        # Все одно повертаємо 200, щоб Telegram не надсилав це оновлення повторно
        return Response(status=200)

@flask_app.route("/") # Додатковий маршрут для перевірки, чи працює веб-сервер
@flask_app.route("/healthz") # Стандартний маршрут для перевірки стану (health check)
def health_check():
    """Базовий маршрут для перевірки стану сервісу."""
    logger.info("Запит на перевірку стану (/ або /healthz)")
    return "OK", 200

# --- Функція для встановлення вебхука (асинхронна) ---
async def setup_webhook():
    """Встановлює URL вебхука для Telegram бота."""
    if not WEBHOOK_URL:
        logger.error("ПОМИЛКА: Не встановлено змінну середовища WEBHOOK_URL! Неможливо встановити вебхук.")
        return False

    logger.info(f"Встановлення вебхука на URL: {WEBHOOK_URL}")
    try:
        await application.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES # Отримувати всі типи оновлень
        )
        # Перевірка встановленого вебхука (опціонально, але корисно для діагностики)
        webhook_info = await application.bot.get_webhook_info()
        logger.info(f"Інформація про вебхук: {webhook_info}")
        if webhook_info.url == WEBHOOK_URL:
             logger.info("Вебхук успішно встановлено.")
             return True
        else:
             logger.error(f"Не вдалося встановити вебхук. Поточний URL: {webhook_info.url}")
             return False
    except Exception as e:
        logger.error(f"Помилка під час встановлення вебхука: {e}", exc_info=True)
        return False

# --- Основна функція запуску ---
def main() -> None:
    """Запускає встановлення вебхука та веб-сервер Flask."""

    # Запускаємо асинхронну функцію встановлення вебхука
    # Важливо: Це потрібно робити в event loop.
    # Якщо запускати через Gunicorn/Uvicorn, вони керують циклом подій.
    # Запуск setup_webhook() тут може бути проблематичним поза простим `python main_bot.py`.
    # Краще встановити вебхук один раз окремо або перевіряти його наявність.
    # Для спрощення, ми спробуємо запустити його тут.
    logger.info("Спроба встановити вебхук...")
    webhook_set_successfully = asyncio.run(setup_webhook())

    if not webhook_set_successfully:
         logger.warning("Не вдалося встановити вебхук при запуску. Перевірте URL та токен.")
         # Можна вирішити не запускати Flask, якщо вебхук не встановлено,
         # але часто краще запустити, щоб платформа не вважала сервіс несправним.
         # exit() # Розкоментуйте, якщо хочете зупинитись при помилці вебхука

    # Запускаємо веб-сервер Flask
    # УВАГА: Для продакшену використовуйте WSGI сервер типу Gunicorn або Uvicorn
    # Команда запуску буде вказана у Procfile або налаштуваннях платформи.
    # flask_app.run() підходить лише для локальної розробки.
    logger.info(f"Веб-сервер Flask готовий (для запуску використовуйте Gunicorn/Uvicorn)")
    # Наступний рядок потрібен лише якщо ви запускаєте скрипт напряму `python main_bot.py`
    # У продакшені його виконуватиме Gunicorn/Uvicorn
    # flask_app.run(host='0.0.0.0', port=PORT, debug=False)


# Цей блок виконається, тільки якщо скрипт запускається напряму.
# Gunicorn/Uvicorn імпортують `flask_app` і не виконають цей блок.
if __name__ == '__main__':
     logger.info("Запуск main()...")
     main()
     # У реальному розгортанні цей код не дійде до кінця,
     # бо Gunicorn/Uvicorn запустять `flask_app` напряму.
     # Якщо ви запускаєте локально `python main_bot.py`,
     # вам потрібно додати `flask_app.run()` в кінець `main()`
     # або запустити Flask окремо.
     logger.info("Запуск Flask для локальної розробки...")
     flask_app.run(host='0.0.0.0', port=PORT, debug=True) # debug=True для локальної розробки
