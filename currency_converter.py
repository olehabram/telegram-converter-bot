# currency_converter.py (Async version)
import requests
import json
import asyncio
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

API_URL_BASE = "https://open.er-api.com/v6/latest"

exchange_rates_cache: Dict[str, Dict[str, float]] = {}
cache_timestamps: Dict[str, float] = {}
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 годин кеш

def _fetch_rates_sync(url: str, timeout: int) -> Optional[Dict[str, Any]]:
    logger.info(f"[_fetch_rates_sync] Fetching rates from {url}...")
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success" and "rates" in data:
            logger.info(f"[_fetch_rates_sync] Successfully fetched rates.")
            return data
        else:
            error_type = data.get("error-type", "Unknown API error")
            logger.error(f"[_fetch_rates_sync] API error: {error_type}")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"[_fetch_rates_sync] Timeout fetching {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[_fetch_rates_sync] Request failed: {e}")
    except json.JSONDecodeError:
        logger.error(f"[_fetch_rates_sync] JSON decode error")
    except Exception:
        logger.exception(f"[_fetch_rates_sync] Unexpected error")
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

    url = f"{API_URL_BASE}/{base_currency}"
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _fetch_rates_sync, url, 10)

    if data is None:
        logger.error(f"Failed to fetch exchange rates for {base_currency}")
        return None

    rates = data.get("rates")
    if not rates:
        logger.error(f"No rates found in API response for {base_currency}")
        return None

    exchange_rates_cache[base_currency] = rates
    cache_timestamps[base_currency] = current_time
    logger.info(f"Rates cached for {base_currency}")
    return rates

async def convert_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    rates_usd = await get_exchange_rates("USD")
    if rates_usd is None:
        logger.error("Cannot get base USD rates for conversion")
        return None

    if from_currency not in rates_usd or to_currency not in rates_usd:
        missing = [cur for cur in (from_currency, to_currency) if cur not in rates_usd]
        logger.error(f"Currency(ies) not found in rates: {', '.join(missing)}")
        return None

    try:
        rate_from_usd = rates_usd[from_currency]
        rate_to_usd = rates_usd[to_currency]

        if rate_from_usd == 0:
            logger.error(f"Rate for {from_currency} is zero")
            return None

        converted = (amount / rate_from_usd) * rate_to_usd
        logger.info(f"Converted {amount} {from_currency} to {converted:.4f} {to_currency}")
        return converted
    except Exception:
        logger.exception("Unexpected error during conversion")
        return None

# Тестування модуля
async def _test():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test: Get USD rates")
    rates = await get_exchange_rates("USD")
    print("USD rates:", "Success" if rates else "Failed")

    print("Test: Convert 100 USD to UAH")
    res = await convert_currency(100, "USD", "UAH")
    print(f"100 USD = {res:.2f} UAH" if res else "Conversion failed")

    print("Test: Convert 100 EUR to GBP")
    res = await convert_currency(100, "EUR", "GBP")
    print(f"100 EUR = {res:.2f} GBP" if res else "Conversion failed")

if __name__ == "__main__":
    asyncio.run(_test())
