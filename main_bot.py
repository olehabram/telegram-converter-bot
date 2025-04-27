# main_bot.py
import os  # Імпортуємо модуль для роботи з операційною системою (для змінних середовища)
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Імпортуємо наші конвертери (config.py більше не потрібен тут)
import currency_converter
import unit_converter

# Налаштування логування для відстеження роботи бота та можливих помилок
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Функції-обробники команд (залишаються без змін) ---

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
            # parse_mode='MarkdownV2' # Markdown може конфліктувати з деякими символами, HTML надійніший
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
        # Повідомлення про очікування (можна прибрати, якщо конвертація швидка)
        # await update.message.reply_text("Спроба конвертації валюти...") 
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


# --- Основна функція запуску бота ---

def main() -> None:
    """Запускає бота."""
    # --- Змінено: Отримання токена зі змінної середовища ---
    bot_token = os.environ.get('BOT_TOKEN') 
    if not bot_token:
        # Логуємо помилку, якщо токен не знайдено
        logger.critical("ПОМИЛКА: Не знайдено змінну середовища BOT_TOKEN! Бот не може запуститися.")
        # Можна додати sys.exit(1) якщо потрібно завершити програму з кодом помилки
        return # Зупиняємо виконання функції main

    logger.info("Токен бота успішно отримано зі змінної середовища.")

    # Створюємо Application та передаємо йому токен бота.
    application = Application.builder().token(bot_token).build() 
    # --- Кінець змін ---

    # Реєструємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", convert_command))

    # Реєструємо обробник для невідомих команд/повідомлень
    # Важливо, щоб цей обробник був ОСТАННІМ серед MessageHandler'ів
    application.add_handler(MessageHandler(filters.COMMAND | filters.TEXT & ~filters.UpdateType.EDITED, unknown))

    # Запускаємо бота доки користувач не натисне Ctrl+C
    logger.info("Бот запускається...")
    print("Бот запускається...") # Повідомлення для користувача в консолі
    application.run_polling()
    logger.info("Бот зупинено.")
    print("Бот зупинено.") # Повідомлення для користувача в консолі


if __name__ == '__main__':
    main()
