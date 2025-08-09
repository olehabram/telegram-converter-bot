# currency_converter.py (Async version with MonoBank rates)
import requests
import json
import asyncio
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

API_URL_BASE = "https://open.er-api.com/v6/latest/"

exchange_rates_cache: Dict[str, Dict[str, float]] = {}
CACHE_TTL_SECONDS = 6 * 60 * 60
cache_timestamps: Dict[str, float] = {}

def _fetch_rates_sync(url: str, timeout: int) -> Optional[Dict[str, Any]]:
    logger.info(f"[_fetch_rates_sync] Fetching from {url}...")
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success" and "rates" in data:
            logger.info(f"[_fetch_rates_sync] Success from {url}")
            return data
        else:
            error_type = data.get('error-type', 'Unknown API error')
            logger.error(f"[_fetch_rates_sync] API Error: {error_type}")
            return None
    except Exception as e:
        logger.exception(f"[_fetch_rates_sync] Error fetching {url}: {e}")
        return None

async def get_exchange_rates(base_currency: str = "USD") -> Optional[Dict[str, float]]:
    base_currency = base_currency.upper()
    current_time = asyncio.get_running_loop().time()

    if base_currency in exchange_rates_cache and base_currency in cache_timestamps:
        if current_time - cache_timestamps[base_currency] < CACHE_TTL_SECONDS:
            logger.info(f"Using cached rates for {base_currency}")
            return exchange_rates_cache[base_currency]
        else:
            logger.info(f"Cache expired for {base_currency}")

    url = f"{API_URL_BASE}{base_currency}"
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _fetch_rates_sync, url, 10)

    if data is None:
        logger.error(f"Failed to fetch data for {base_currency}")
        return None

    if data.get("result") == "success" and "rates" in data:
        rates = data["rates"]
        exchange_rates_cache[base_currency] = rates
        cache_timestamps[base_currency] = current_time
        logger.info(f"Rates for {base_currency} updated")
        return rates

    error_type = data.get('error-type', 'Invalid data structure')
    logger.error(f"API data validation failed for {base_currency}: {error_type}")
    return None

def get_mono_exchange_rates():
    url = "https://api.monobank.ua/bank/currency"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        rates = {}
        code_map = {840: 'USD', 978: 'EUR'}  
        for entry in data:
            if entry.get('currencyCodeB') == 980:  # UAH
                if 'rateBuy' in entry and 'rateSell' in entry and entry['rateBuy'] and entry['rateSell']:
                    ccy = code_map.get(entry['currencyCodeA'])
                    if ccy:
                        rates[ccy] = {
                            'buy': float(entry['rateBuy']),
                            'sell': float(entry['rateSell'])
                        }
        return rates
    except Exception as e:
        logger.error(f"Error getting MonoBank rates: {e}")
        return None

async def convert_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    logger.info(f"Converting {amount} {from_currency} to {to_currency} using open.er-api.com")
    rates_usd = await get_exchange_rates("USD")
    if rates_usd is None:
        logger.error("Failed to get base (USD) exchange rates")
        return None

    if from_currency not in rates_usd or to_currency not in rates_usd:
        logger.error(f"Currencies {from_currency} or {to_currency} not found in rates")
        return None

    try:
        rate_from_usd = rates_usd[from_currency]
        rate_to_usd = rates_usd[to_currency]

        if rate_from_usd == 0:
            logger.error(f"Rate for {from_currency} relative to USD is zero")
            return None

        converted_amount = (amount / rate_from_usd) * rate_to_usd
        logger.info(f"Converted: {amount} {from_currency} = {converted_amount:.4f} {to_currency}")
        return converted_amount

    except Exception as e:
        logger.exception("Unexpected error during conversion")
        return None

async def convert_currency_with_mono(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    if 'UAH' in (from_currency, to_currency):
        mono_rates = get_mono_exchange_rates()
        if mono_rates:
            if from_currency == 'UAH' and to_currency in mono_rates:
                rate = mono_rates[to_currency]['buy']
                if rate:
                    return amount / rate
            elif to_currency == 'UAH' and from_currency in mono_rates:
                rate = mono_rates[from_currency]['sell']
                if rate:
                    return amount * rate

    return await convert_currency(amount, from_currency, to_currency)

# --- Тести для перевірки ---
async def _test():
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("\n[Test 1] Конвертація USD -> UAH (з MonoBank)")
    res = await convert_currency_with_mono(100, "USD", "UAH")
    print(f"100 USD = {res:.2f} UAH" if res else "Не вдалося конвертувати USD -> UAH")

    print("\n[Test 2] Конвертація EUR -> USD (з MonoBank fallback)")
    res = await convert_currency_with_mono(100, "EUR", "USD")
    print(f"100 EUR = {res:.2f} USD" if res else "Не вдалося конвертувати EUR -> USD")

    print("\n[Test 3] Конвертація USD -> EUR (без UAH)")
    res = await convert_currency_with_mono(100, "USD", "EUR")
    print(f"100 USD = {res:.2f} EUR" if res else "Не вдалося конвертувати USD -> EUR")

if __name__ == "__main__":
    asyncio.run(_test())
