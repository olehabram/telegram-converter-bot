# currency_converter.py (Async version)
import requests  # Все ще потрібен для запитів
import json
import asyncio
import concurrent.futures # Потрібен для ThreadPoolExecutor (хоча можна і None)
from typing import Dict, Optional, Any # Для кращої типізації

# URL для API
API_URL_BASE = "https://open.er-api.com/v6/latest/"

# Кеш залишається синхронним, доступ до нього швидкий
exchange_rates_cache: Dict[str, Dict[str, float]] = {}

def _fetch_rates_sync(url: str, timeout: int) -> Optional[Dict[str, Any]]:
    """Синхронна функція для виконання запиту requests.get.
       Ця функція буде виконуватися в окремому потоці.
    """
    print(f"[_fetch_rates_sync] Attempting to fetch from {url}...")
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()  # Перевірка на HTTP помилки
        data = response.json()
        print(f"[_fetch_rates_sync] Successfully fetched and parsed JSON.")
        return data
    except requests.exceptions.Timeout:
        print(f"[_fetch_rates_sync] Error: Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[_fetch_rates_sync] Error: Network request failed: {e}")
        return None
    except json.JSONDecodeError:
        print(f"[_fetch_rates_sync] Error: Failed to decode JSON response from {url}")
        return None
    except Exception as e:
        # Логуємо інші неочікувані помилки
        print(f"[_fetch_rates_sync] Unexpected error: {e}")
        return None


async def get_exchange_rates(base_currency: str = "USD") -> Optional[Dict[str, float]]:
    """
    Асинхронно отримує курси валют відносно базової валюти з API або кешу.

    Args:
        base_currency (str): Код базової валюти (за замовчуванням "USD").

    Returns:
        dict or None: Словник з курсами валют або None у разі помилки.
    """
    base_currency = base_currency.upper()
    # Перевірка кешу (синхронна, бо швидка)
    if base_currency in exchange_rates_cache:
        print(f"Using cached rates for {base_currency}")
        return exchange_rates_cache[base_currency]

    # Якщо в кеші немає, виконуємо синхронний запит в екзекуторі
    print(f"Fetching fresh rates for {base_currency} from API via executor...")
    url = f"{API_URL_BASE}{base_currency}"
    loop = asyncio.get_running_loop()

    try:
        # Використовуємо run_in_executor для запуску _fetch_rates_sync
        # None означає використання стандартного ThreadPoolExecutor
        data = await loop.run_in_executor(None, _fetch_rates_sync, url, 10) # 10 секунд таймаут
    except Exception as e:
        # Ловимо помилки, що могли виникнути при запуску/роботі екзекутора
        print(f"[get_exchange_rates] Error running executor task: {e}")
        data = None

    if data is None:
        print(f"Failed to fetch data for {base_currency} from API.")
        return None

    # Обробка отриманих даних
    if data.get("result") == "success" and "rates" in data:
        print(f"Rates for {base_currency} successfully obtained and validated.")
        rates = data["rates"]
        # Зберігаємо в кеш (синхронно)
        exchange_rates_cache[base_currency] = rates
        return rates
    else:
        error_type = data.get('error-type', 'Unknown API error')
        print(f"API Error for {base_currency}: {error_type}")
        return None


async def convert_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """
    Асинхронно конвертує суму з однієї валюти в іншу.

    Args:
        amount (float): Сума для конвертації.
        from_currency (str): Код вихідної валюти (наприклад, "USD").
        to_currency (str): Код цільової валюти (наприклад, "UAH").

    Returns:
        float or None: Конвертована сума або None у разі помилки.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    # Отримуємо курси асинхронно
    print(f"Attempting to get rates relative to USD for {from_currency} -> {to_currency} conversion...")
    rates_usd = await get_exchange_rates("USD")

    if rates_usd is None:
        print("Failed to get base (USD) exchange rates.")
        # Можна додати спробу отримати відносно from_currency, якщо потрібно
        # print(f"Attempting to get rates relative to {from_currency}...")
        # rates_alternative = await get_exchange_rates(from_currency)
        # if rates_alternative and to_currency in rates_alternative:
        #     rate = rates_alternative[to_currency]
        #     print(f"Using alternative rate {from_currency} -> {to_currency}: {rate}")
        #     return amount * rate
        # else:
        #     print(f"Failed to get alternative rates for {from_currency} -> {to_currency}.")
        #     return None
        return None # Поки що спрощуємо: якщо USD не вдалося, то помилка

    # Перевіряємо наявність валют у курсах відносно USD
    if from_currency not in rates_usd or to_currency not in rates_usd:
        missing = [cur for cur in [from_currency, to_currency] if cur not in rates_usd]
        print(f"Error: Currency codes {', '.join(missing)} not found in rates relative to USD.")
        return None

    try:
        # Розрахунок (цей код швидкий, залишаємо синхронним)
        rate_from_usd = rates_usd[from_currency]
        rate_to_usd = rates_usd[to_currency]

        if rate_from_usd == 0:
            print(f"Error: Exchange rate for {from_currency} is zero.")
            return None

        # Конвертація через USD: Amount / (From/USD) * (To/USD)
        converted_amount = (amount / rate_from_usd) * rate_to_usd
        print(f"Conversion successful: {amount} {from_currency} = {converted_amount} {to_currency}")
        return converted_amount

    except ZeroDivisionError:
        # Мало б бути оброблено перевіркою вище, але про всяк випадок
        print(f"Error: Division by zero during conversion (rate for {from_currency} might be zero).")
        return None
    except KeyError as e:
         # Також мало б бути оброблено перевіркою наявності вище
         print(f"Error: Currency {e} not found during calculation step.")
         return None
    except Exception as e:
        print(f"Unexpected error during currency conversion calculation: {e}")
        return None


# --- Приклад використання (для тестування) ---
async def _test():
    print("--- Async Currency Converter Tests ---")
    # Тест 1: Отримання курсів USD
    print("\n[Test 1] Getting USD rates...")
    rates = await get_exchange_rates("USD")
    if rates:
        print("USD rates obtained (first 5):")
        count = 0
        for cur, rate in rates.items():
            print(f"  {cur}: {rate}")
            count += 1
            if count >= 5: break
    else:
        print("Failed to get USD rates.")

    # Тест 2: Конвертація USD -> UAH
    print("\n[Test 2] Converting USD to UAH...")
    result = await convert_currency(100, "USD", "UAH")
    if result is not None:
        print(f"Result: 100 USD = {result:.2f} UAH")
    else:
        print("Failed to convert USD to UAH.")

    # Тест 3: Конвертація EUR -> GBP (використає кеш USD)
    print("\n[Test 3] Converting EUR to GBP...")
    result = await convert_currency(100, "EUR", "GBP")
    if result is not None:
        print(f"Result: 100 EUR = {result:.2f} GBP")
    else:
        print("Failed to convert EUR to GBP.")

    # Тест 4: Використання кешу
    print("\n[Test 4] Getting USD rates again (should use cache)...")
    rates_cached = await get_exchange_rates("USD")
    if rates_cached:
        print("USD rates obtained again (likely from cache).")

    # Тест 5: Неіснуюча валюта
    print("\n[Test 5] Converting USD to XYZ...")
    result = await convert_currency(100, "USD", "XYZ")
    if result is None:
        print("Failed to convert USD to XYZ (expected).")

if __name__ == "__main__":
    # Запускаємо асинхронні тести
    asyncio.run(_test())
