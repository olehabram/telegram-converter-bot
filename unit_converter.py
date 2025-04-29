# unit_converter.py

# Словник з коефіцієнтами конвертації відносно базової одиниці СІ
# Базові одиниці: метр (m) для довжини, кілограм (kg) для маси, літр (l) для об'єму
CONVERSION_FACTORS = {
    # Довжина (базова: метр 'm')
    'length': {
        'mm': 0.001,      # Міліметр
        'cm': 0.01,       # Сантиметр
        'm': 1.0,         # Метр
        'km': 1000.0,     # Кілометр
        'in': 0.0254,     # Дюйм (inch)
        'ft': 0.3048,     # Фут (foot)
        'yd': 0.9144,     # Ярд (yard)  <--- ДОДАНО
        'mi': 1609.34,    # Миля (mile)
    },
    # Маса (базова: кілограм 'kg')
    'mass': {
        'mg': 0.000001,   # Міліграм
        'g': 0.001,       # Грам
        'kg': 1.0,        # Кілограм
        't': 1000.0,      # Тонна (метрична)
        'oz': 0.0283495,  # Унція (ounce)
        'lb': 0.453592,   # Фунт (pound)
    },
    # Об'єм (базова: літр 'l')
    'volume': {
        'ml': 0.001,      # Мілілітр
        'l': 1.0,         # Літр
        'm3': 1000.0,     # Кубічний метр (m³)
        'gal': 3.78541,   # Галон (US liquid gallon)
    }
}


def get_unit_category(unit):
    """Визначає категорію (довжина, маса, об'єм) для заданої одиниці."""
    unit_lower = unit.lower()
    for category, units in CONVERSION_FACTORS.items():
        if unit_lower in units:
            return category
    return None


def convert_units(value, from_unit, to_unit):
    """
    Конвертує значення з однієї одиниці в іншу в межах однієї категорії.
    """
    from_unit_lower = from_unit.lower()
    to_unit_lower = to_unit.lower()

    from_category = get_unit_category(from_unit_lower)
    to_category = get_unit_category(to_unit_lower)

    if not from_category or not to_category:
        return None # Можливо, це валюта

    if from_category != to_category:
        is_potential_currency = (
            len(from_unit) == 3 and from_unit.isalpha() and
            len(to_unit) == 3 and to_unit.isalpha()
        )
        if not is_potential_currency:
             # Логуємо тільки якщо це точно не валюта
             print(f"Помилка: Неможливо конвертувати між різними категоріями ({from_category} -> {to_category})")
        return None

    factors = CONVERSION_FACTORS[from_category]

    try:
        factor_from = factors.get(from_unit_lower)
        factor_to = factors.get(to_unit_lower)

        if factor_from is None or factor_to is None:
             print(f"Внутрішня помилка: Не знайдено коефіцієнт для {from_unit} або {to_unit} у категорії {from_category}")
             return None

        if factor_to == 0:
            print(f"Помилка: Коефіцієнт для цільової одиниці {to_unit} дорівнює нулю.")
            return None

        value_in_base_unit = value * factor_from
        converted_value = value_in_base_unit / factor_to
        return converted_value

    except ZeroDivisionError:
        print(f"Помилка ділення на нуль при конвертації одиниць (коефіцієнт для {to_unit} може бути 0).")
        return None
    except Exception as e:
        print(f"Неочікувана помилка під час конвертації одиниць: {e}")
        return None

# --- Приклад використання (для тестування) ---
if __name__ == "__main__":
    print("--- Unit Converter Tests (with yd) ---")
    # ... (тести з попередньої версії залишаються актуальними) ...
    val = 7.32
    f_unit = "m"
    t_unit = "yd"
    res = convert_units(val, f_unit, t_unit)
    if res is not None: print(f"{val} {f_unit} = {res:.2f} {t_unit}")
    else: print(f"Помилка конвертації {f_unit} -> {t_unit}")

