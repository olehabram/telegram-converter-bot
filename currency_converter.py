# currency_converter.py
# Переконайся, що бібліотека 'requests' встановлена: pip install requests
import requests  # Імпортуємо бібліотеку для HTTP-запитів
import json  # Імпортуємо бібліотеку для роботи з JSON

# URL для безкоштовного API ExchangeRate-API (з базовою валютою USD)
# Ви можете змінити USD на EUR або іншу підтримувану базову валюту, якщо потрібно
# Перевірте документацію API для доступних базових валют на безкоштовному плані
API_URL = "https://open.er-api.com/v6/latest/USD"

# Словник для кешування курсів, щоб не робити запит до API щоразу
# Ключ - код базової валюти (наприклад, 'USD'), значення - словник курсів
exchange_rates_cache = {}


def get_exchange_rates(base_currency="USD"):
    """
    Отримує курси валют відносно базової валюти з API або кешу.

    Args:
        base_currency (str): Код базової валюти (за замовчуванням "USD").

    Returns:
        dict or None: Словник з курсами валют або None у разі помилки.
                     Формат: {'USD': 1.0, 'EUR': 0.92, 'UAH': 39.5, ...}
    """
    # Перевіряємо, чи є курси для цієї базової валюти в кеші
    if base_currency in exchange_rates_cache:
        print(f"Використання кешованих курсів для {base_currency}")
        return exchange_rates_cache[base_currency]

    # Якщо в кеші немає, робимо запит до API
    print(f"Отримання свіжих курсів для {base_currency} з API...")
    url = f"https://open.er-api.com/v6/latest/{base_currency}"
    try:
        # Встановлюємо таймаут для запиту (наприклад, 10 секунд)
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Перевіряємо на HTTP-помилки (4xx або 5xx)

        data = response.json()

        # Перевіряємо, чи запит був успішним і чи є ключ 'rates'
        if data.get("result") == "success" and "rates" in data:
            print("Курси успішно отримано.")
            # Зберігаємо курси в кеш
            exchange_rates_cache[base_currency] = data["rates"]
            return data["rates"]
        else:
            print(f"Помилка у відповіді API: {data.get('error-type', 'Невідома помилка')}")
            return None

    except requests.exceptions.Timeout:
        print(f"Помилка: Запит до API {url} перевищив час очікування.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Помилка мережевого запиту до API: {e}")
        return None
    except json.JSONDecodeError:
        print("Помилка декодування відповіді API (не JSON).")
        return None
    except Exception as e:
        print(f"Неочікувана помилка при отриманні курсів: {e}")
        return None


def convert_currency(amount, from_currency, to_currency):
    """
    Конвертує суму з однієї валюти в іншу.

    Args:
        amount (float): Сума для конвертації.
        from_currency (str): Код вихідної валюти (наприклад, "USD").
        to_currency (str): Код цільової валюти (наприклад, "UAH").

    Returns:
        float or None: Конвертована сума або None у разі помилки.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    # Якщо валюти однакові, конвертація не потрібна
    if from_currency == to_currency:
        return amount

    # Спочатку отримуємо курси відносно базової валюти (USD за замовчуванням)
    rates = get_exchange_rates()  # Використовуємо USD як базу

    if rates is None:
        print("Не вдалося отримати курси валют.")
        return None

    # Перевіряємо, чи існують потрібні валюти в отриманих курсах
    if from_currency not in rates or to_currency not in rates:
        missing = []
        if from_currency not in rates:
            missing.append(from_currency)
        if to_currency not in rates:
            missing.append(to_currency)
        print(f"Помилка: Валюти {', '.join(missing)} не знайдено в курсах відносно USD.")

        # Спробуємо отримати курси з базою from_currency, якщо вона не USD
        # Це може допомогти, якщо API надає курси відносно інших баз
        if from_currency != "USD":
            print(f"Спроба отримати курси з базою {from_currency}...")
            rates_alternative = get_exchange_rates(from_currency)
            if rates_alternative and to_currency in rates_alternative:
                rate = rates_alternative[to_currency]
                print(f"Використано альтернативний курс {from_currency} -> {to_currency}: {rate}")
                return amount * rate
            else:
                print(f"Не вдалося знайти курс для {to_currency} з базою {from_currency}.")
                return None
        else:
            # Якщо from_currency була USD і її немає в списку (дуже дивно), або to_currency немає
            return None

    try:
        # Конвертація через базову валюту (USD)
        # Спочатку конвертуємо from_currency в USD
        # rates[from_currency] - це скільки одиниць from_currency коштує 1 USD
        # Щоб отримати суму в USD, треба поділити на цей курс
        # Приклад: якщо курс USD/EUR = 0.9, то 1 USD = 0.9 EUR. Щоб 100 EUR перевести в USD: 100 / 0.9
        if rates[from_currency] == 0:
             print(f"Помилка: Курс для {from_currency} дорівнює нулю.")
             return None
        amount_in_usd = amount / rates[from_currency]

        # Потім конвертуємо USD в to_currency
        # rates[to_currency] - це скільки одиниць to_currency коштує 1 USD
        # Щоб отримати суму в to_currency, треба помножити суму в USD на цей курс
        converted_amount = amount_in_usd * rates[to_currency]
        return converted_amount

    except ZeroDivisionError:
        # Ця помилка оброблена вище, але залишимо про всяк випадок
        print(f"Помилка ділення на нуль при конвертації (курс для {from_currency} може бути 0).")
        return None
    except KeyError as e:
         print(f"Помилка: Валюта {e} не знайдена у внутрішніх розрахунках.")
         return None
    except Exception as e:
        print(f"Неочікувана помилка під час конвертації: {e}")
        return None


# --- Приклад використання (для тестування) ---
if __name__ == "__main__":
    # Тест 1: Отримання курсів
    print("--- Тест отримання курсів ---")
    rates_usd = get_exchange_rates("USD")
    if rates_usd:
        print("Курси відносно USD (перші 5):")
        count = 0
        for currency, rate in rates_usd.items():
            print(f"  {currency}: {rate}")
            count += 1
            if count >= 5:
                break
    else:
        print("Не вдалося отримати курси USD.")

    print("\n--- Тест конвертації ---")
    # Тест 2: Конвертація
    amount_to_convert = 100
    from_curr = "USD"
    to_curr = "UAH"
    result = convert_currency(amount_to_convert, from_curr, to_curr)
    if result is not None:
        print(f"{amount_to_convert} {from_curr} = {result:.2f} {to_curr}")
    else:
        print(f"Не вдалося конвертувати {from_curr} в {to_curr}")

    # Тест 3: Інша пара
    from_curr = "EUR"
    to_curr = "GBP"
    result = convert_currency(amount_to_convert, from_curr, to_curr)
    if result is not None:
        print(f"{amount_to_convert} {from_curr} = {result:.2f} {to_curr}")
    else:
        print(f"Не вдалося конвертувати {from_curr} в {to_curr}")

    # Тест 4: Неіснуюча валюта
    from_curr = "USD"
    to_curr = "XYZ"
    result = convert_currency(amount_to_convert, from_curr, to_curr)
    if result is not None:
        print(f"{amount_to_convert} {from_curr} = {result:.2f} {to_curr}")
    else:
        print(f"Не вдалося конвертувати {from_curr} в {to_curr} (очікувана помилка)")

    # Тест 5: Використання кешу
    print("\n--- Тест використання кешу ---")
    rates_usd_cached = get_exchange_rates("USD")  # Має використати кеш
    if rates_usd_cached:
        print("Курси USD отримано (ймовірно, з кешу).")

    # Тест 6: Отримання курсів для іншої бази
    rates_eur = get_exchange_rates("EUR")
    if rates_eur:
        print("Курси відносно EUR (перші 5):")
        count = 0
        for currency, rate in rates_eur.items():
            print(f"  {currency}: {rate}")
            count += 1
            if count >= 5:
                break
    else:
        print("Не вдалося отримати курси EUR.")
