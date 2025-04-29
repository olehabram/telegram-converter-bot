# currency_converter.py (Async version)
import requests
import json
import asyncio
import concurrent.futures
import logging # Додано logging
from typing import Dict, Optional, Any

# Налаштування логера для цього модуля
# Рівень логування буде взято з налаштувань у main_bot.py
logger = logging.getLogger(__name__)

# URL для API (використовуємо open.er-api.com, як у початковій версії)
API_URL_BASE = "https://open.er-api.com/v6/latest/"

# Кеш залишається синхронним, доступ до нього швидкий
exchange_rates_cache: Dict[str, Dict[str, float]] = {}
# Час життя кешу в секундах (наприклад, 6 годин)
CACHE_TTL_SECONDS = 6 * 60 * 60
# Додаємо словник для зберігання часу завантаження кешу
cache_timestamps: Dict[str, float] = {}

def _fetch_rates_sync(url: str, timeout: int) -> Optional[Dict[str, Any]]:
    """Синхронна функція для виконання запиту requests.get."""
    logger.info(f"[_fetch_rates_sync] Attempting to fetch from {url}...")
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        # Перевірка успішності відповіді API
        if data.get("result") == "success" and "rates" in data:
             logger.info(f"[_fetch_rates_sync] Successfully fetched and parsed JSON from {url}.")
             return data # Повертаємо весь об'єкт відповіді
        else:
             error_type = data.get('error-type', 'Unknown API error')
             logger.error(f"[_fetch_rates_sync] API Error from {url}: {error_type}")
             return None
    except requests.exceptions.Timeout:
        logger.error(f"[_fetch_rates_sync] Error: Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"[_fetch_rates_sync] Error: Network request failed for {url}: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"[_fetch_rates_sync] Error: Failed to decode JSON response from {url}")
        return None
    except Exception as e:
        # Логуємо інші неочікувані помилки з повним трейсбеком
        logger.exception(f"[_fetch_rates_sync] Unexpected error fetching {url}")
        return None


async def get_exchange_rates(base_currency: str = "USD") -> Optional[Dict[str, float]]:
    """Асинхронно отримує курси валют з API або кешу."""
    base_currency = base_currency.upper()
    current_time = asyncio.get_running_loop().time()

    # Перевірка кешу
    if base_currency in exchange_rates_cache and base_currency in cache_timestamps:
        timestamp = cache_timestamps[base_currency]
        if current_time - timestamp < CACHE_TTL_SECONDS:
            logger.info(f"Using cached rates for {base_currency}")
            return exchange_rates_cache[base_currency]
        else:
            logger.info(f"Cache expired for {base_currency}")

    # Виконуємо запит в екзекуторі
    logger.info(f"Fetching fresh rates for {base_currency} from API via executor...")
    url = f"{API_URL_BASE}{base_currency}"
    loop = asyncio.get_running_loop()
    data = None # Ініціалізуємо data
    try:
        # Запускаємо синхронну функцію в окремому потоці
        data = await loop.run_in_executor(None, _fetch_rates_sync, url, 10) # 10 секунд таймаут
    except Exception as e:
        logger.exception(f"[get_exchange_rates] Error running executor task for {url}")
        # data залишається None

    if data is None:
        logger.error(f"Failed to fetch data for {base_currency} from API.")
        return None # Помилка отримання даних

    # Перевіряємо результат ще раз (хоча _fetch_rates_sync вже мав це зробити)
    if data.get("result") == "success" and "rates" in data:
        rates = data["rates"]
        logger.info(f"Rates for {base_currency} successfully obtained and validated.")
        # Оновлюємо кеш і час
        exchange_rates_cache[base_currency] = rates
        cache_timestamps[base_currency] = current_time
        return rates
    else:
        # Якщо _fetch_rates_sync повернув дані, але вони некоректні
        error_type = data.get('error-type', 'Invalid data structure')
        logger.error(f"API data validation failed for {base_currency}: {error_type}")
        return None


async def convert_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """Асинхронно конвертує суму з однієї валюти в іншу."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    # Отримуємо курси відносно USD (або іншої бази, якщо потрібно)
    logger.info(f"Attempting to get rates relative to USD for {from_currency} -> {to_currency} conversion...")
    rates_usd = await get_exchange_rates("USD") # Використовуємо USD як базу

    if rates_usd is None:
        logger.error("Failed to get base (USD) exchange rates for conversion.")
        return None

    # Перевіряємо наявність валют
    if from_currency not in rates_usd or to_currency not in rates_usd:
        missing = [cur for cur in [from_currency, to_currency] if cur not in rates_usd]
        logger.error(f"Error: Currency codes {', '.join(missing)} not found in rates relative to USD.")
        # Можна додати спробу отримати курси відносно from_currency, якщо USD не містить потрібної
        # logger.info(f"Trying to get rates relative to {from_currency} as fallback...")
        # rates_alt = await get_exchange_rates(from_currency)
        # if rates_alt and to_currency in rates_alt:
        #     rate = rates_alt[to_currency]
        #     logger.info(f"Using alternative rate {from_currency} -> {to_currency}: {rate}")
        #     return amount * rate
        # else:
        #     logger.error(f"Fallback failed: Could not get rates for {to_currency} relative to {from_currency}.")
        #     return None
        return None # Поки що не використовуємо fallback

    try:
        # Розрахунок
        rate_from_usd = rates_usd[from_currency]
        rate_to_usd = rates_usd[to_currency]

        if rate_from_usd == 0:
            logger.error(f"Error: Exchange rate for {from_currency} relative to USD is zero.")
            return None

        # Конвертація через USD: Amount / (From/USD) * (To/USD)
        converted_amount = (amount / rate_from_usd) * rate_to_usd
        logger.info(f"Conversion successful: {amount} {from_currency} = {converted_amount:.4f} {to_currency}")
        return converted_amount

    except ZeroDivisionError: # Має бути оброблено перевіркою вище
        logger.error(f"Error: Division by zero during conversion (rate for {from_currency} might be zero).")
        return None
    except KeyError as e: # Має бути оброблено перевіркою наявності вище
         logger.error(f"Error: Currency {e} not found during calculation step (should have been caught earlier).")
         return None
    except Exception as e:
        logger.exception(f"Unexpected error during currency conversion calculation")
        return None

# --- Приклад використання (для тестування) ---
async def _test():
    # Налаштовуємо логування для тестів
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("--- Async Currency Converter Tests ---")
    # Тест 1: Отримання курсів USD
    print("\n[Test 1] Getting USD rates...")
    rates = await get_exchange_rates("USD")
    if rates: print("USD rates obtained.")
    else: print("Failed to get USD rates.")

    # Тест 2: Конвертація USD -> UAH
    print("\n[Test 2] Converting USD to UAH...")
    result = await convert_currency(100, "USD", "UAH")
    if result is not None: print(f"Result: 100 USD = {result:.2f} UAH")
    else: print("Failed to convert USD to UAH.")

    # Тест 3: Конвертація EUR -> GBP (використає кеш USD)
    print("\n[Test 3] Converting EUR to GBP...")
    result = await convert_currency(100, "EUR", "GBP")
    if result is not None: print(f"Result: 100 EUR = {result:.2f} GBP")
    else: print("Failed to convert EUR to GBP.")

    # Тест 4: Використання кешу
    print("\n[Test 4] Getting USD rates again (should use cache)...")
    rates_cached = await get_exchange_rates("USD")
    if rates_cached: print("USD rates obtained again (likely from cache).")

    # Тест 5: Неіснуюча валюта
    print("\n[Test 5] Converting USD to XYZ...")
    result = await convert_currency(100, "USD", "XYZ")
    if result is None: print("Failed to convert USD to XYZ (expected).")

if __name__ == "__main__":
    asyncio.run(_test())
