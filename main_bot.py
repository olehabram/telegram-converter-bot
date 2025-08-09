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

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("telegram.bot").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("asgiref").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Environment ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8080))

# --- Global vars ---
application: Application | None = None
initialization_error: Exception | None = None
init_lock = asyncio.Lock()
is_async_initialized = False

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    reply_content = (
        f"Привіт, {user.mention_html()}!\n\n"
        f"Я бот-конвертер. Допоможу тобі конвертувати валюти та одиниці виміру.\n\n"
        f"<b>Як користуватися:</b>\n"
        f"Надішли повідомлення у форматі:\n"
        f"<code>100 USD to UAH</code> або <code>5 km to m</code>\n\n"
        f"Використовуй команду /help для довідки."
    )
    await update.message.reply_html(reply_content)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "<b>Інструкція з використання:</b>\n\n"
        "Щоб конвертувати, надішли повідомлення у форматі:\n"
        "<code>100 USD to UAH</code> або <code>5 km to m</code>\n\n"
        "<b>Підтримувані одиниці:</b> mm, cm, m, km, in, ft, yd, mi, mg, g, kg, t, oz, lb, ml, l, m3, gal\n"
        "<b>Підтримувані валюти:</b> USD, EUR, UAH, GBP, PLN, CAD, JPY тощо."
    )
    await update.message.reply_html(help_text)

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or len(args) < 4 or args[-2].lower() != 'to':
        await update.message.reply_text(
            "Неправильний формат. Використовуйте: `<значення> <з> to <в>`\n"
            "Приклад: `100 USD to UAH`",
            parse_mode="Markdown"
        )
        return
    try:
        amount = float(args[0].replace(',', '.'))
        from_unit = " ".join(args[1:-2]).strip().lower()
        to_unit = args[-1].strip().lower()
    except ValueError:
        await update.message.reply_text(f"Помилка: '{args[0]}' не є дійсним числом.")
        return

    reply_text = ""
    conversion_done = False

    try:
        unit_result = unit_converter.convert_units(amount, from_unit, to_unit)
        if unit_result is not None:
            if unit_result == int(unit_result):
                reply_text = f"{amount} {from_unit.upper()} = {int(unit_result)} {to_unit.upper()}"
            else:
                reply_text = f"{amount} {from_unit.upper()} = {unit_result:.4f} {to_unit.upper()}"
            conversion_done = True
    except Exception:
        reply_text = "Виникла внутрішня помилка при конвертації одиниць."

    if not conversion_done:
        if len(args[1]) == 3 and len(args[-1]) == 3:
            currency_result = await currency_converter.convert_currency(
                amount, from_unit.upper(), to_unit.upper()
            )
            if currency_result is not None:
                reply_text = f"{amount} {from_unit.upper()} = {currency_result:.2f} {to_unit.upper()}"
                conversion_done = True
            else:
                reply_text = (
                    f"Не вдалося конвертувати валюту {from_unit.upper()} в {to_unit.upper()}."
                )
                conversion_done = True
        else:
            reply_text = (
                f"Не вдалося розпізнати одиниці/валюти: '{from_unit}' або '{to_unit}'."
            )
            conversion_done = True

    if not reply_text:
        reply_text = "Не вдалося виконати конвертацію."

    await update.message.reply_text(reply_text)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Невідома команда або формат. Спробуйте /help.")

# --- Webhook setup ---
async def setup_webhook(app: Application, url: str) -> bool:
    if not url:
        logger.error("WEBHOOK_URL не задано!")
        return False
    await app.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    return True

# --- Init ---
def initialize_telegram_app_sync() -> Application | None:
    global initialization_error
    if not BOT_TOKEN:
        initialization_error = RuntimeError("BOT_TOKEN не знайдено!")
        return None
    try:
        request_settings = HTTPXRequest(connect_timeout=10.0, read_timeout=20.0, pool_timeout=15.0)
        builder = ApplicationBuilder().token(BOT_TOKEN).request(request_settings)
        app = builder.build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("convert", convert_command))

        async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            text = (update.message.text or "").strip()
            if not text:
                return
            parts = text.split()
            if parts and parts[0].lower() == "convert":
                parts = parts[1:]
            if len(parts) >= 4 and parts[-2].lower() == "to":
                context.args = parts
                await convert_command(update, context)
            else:
                await unknown(update, context)

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        app.add_handler(MessageHandler(filters.COMMAND, unknown))
        initialization_error = None
        return app
    except Exception as e:
        initialization_error = e
        return None

async def initialize_bot_async(app: Application) -> bool:
    global initialization_error, is_async_initialized
    try:
        await app.initialize()
        webhook_ok = await setup_webhook(app, WEBHOOK_URL)
        if not webhook_ok:
            return False
        is_async_initialized = True
        initialization_error = None
        return True
    except Exception as e:
        initialization_error = e
        is_async_initialized = False
        return False

# --- Flask app ---
flask_app = Flask(__name__)
application = initialize_telegram_app_sync()
flask_app.config['TELEGRAM_APP'] = application
flask_app.config['INIT_ERROR'] = initialization_error

@flask_app.route("/", methods=["GET", "HEAD"])
@flask_app.route("/healthz", methods=["GET", "HEAD"])
def health_check():
    sync_err = flask_app.config.get('INIT_ERROR')
    app_inst = flask_app.config.get('TELEGRAM_APP')
    status_code = 200
    message = "OK"
    if sync_err:
        status_code = 500
        message = f"Initialization Error: {sync_err}"
    elif not app_inst:
        status_code = 500
        message = "Error: Bot application not available"
    elif not is_async_initialized:
        message = "OK (Initializing)"
    return message, status_code

@flask_app.route("/webhook", methods=["POST"])
async def webhook() -> Response:
    global application, initialization_error, is_async_initialized, init_lock
    app_inst = flask_app.config.get('TELEGRAM_APP')
    if not app_inst:
        return Response(status=500)
    if not is_async_initialized:
        async with init_lock:
            if not is_async_initialized:
                init_success = await initialize_bot_async(app_inst)
                if not init_success:
                    flask_app.config['INIT_ERROR'] = initialization_error
                    return Response(status=500)
                else:
                    flask_app.config['INIT_ERROR'] = None
    raw_data = request.get_data()
    if not raw_data:
        return Response(status=200)
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return Response(status=400)
    update = Update.de_json(data, app_inst.bot)
    await app_inst.process_update(update)
    return Response(status=200)

# --- ASGI wrapper ---
asgi_app = WsgiToAsgi(flask_app)
