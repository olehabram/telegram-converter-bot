# unit_converter.py

# Словник з коефіцієнтами конвертації відносно базової одиниці СІ
# Базові одиниці: метр (m) для довжини, кілограм (kg) для маси, літр (l) для об'єму
CONVERSION_FACTORS = {
    # Довжина (базова: метр 'm')
    'length': {
        'mm': 0.001,  # Міліметр
        'cm': 0.01,  # Сантиметр
        'm': 1.0,  # Метр
        'km': 1000.0,  # Кілометр
        'in': 0.0254,  # Дюйм (inch)
        'ft': 0.3048,  # Фут (foot)
        'mi': 1609.34,  # Миля (mile)
    },
    # Маса (базова: кілограм 'kg')
    'mass': {
        'mg': 0.000001,  # Міліграм
        'g': 0.001,  # Грам
        'kg': 1.0,  # Кілограм
        't': 1000.0,  # Тонна (метрична)
        'oz': 0.0283495,  # Унція (ounce)
        'lb': 0.453592,  # Фунт (pound)
    },
    # Об'єм (базова: літр 'l') - Технічно, м³ є базовою одиницею СІ, але літр зручніший
    'volume': {
        'ml': 0.001,  # Мілілітр
        'l': 1.0,  # Літр
        'm3': 1000.0,  # Кубічний метр (m³)
        'gal': 3.78541,  # Галон (US liquid gallon)
    }
    # Можна додати інші категорії: температура, площа тощо.
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

    Args:
        value (float): Значення для конвертації.
        from_unit (str): Код вихідної одиниці (наприклад, "km").
        to_unit (str): Код цільової одиниці (наприклад, "m").

    Returns:
        float or None: Конвертоване значення або None у разі помилки
                       (різні категорії, невідомі одиниці).
    """
    from_unit_lower = from_unit.lower()
    to_unit_lower = to_unit.lower()

    # Визначаємо категорію для обох одиниць
    from_category = get_unit_category(from_unit_lower)
    to_category = get_unit_category(to_unit_lower)

    # Перевірка 1: Чи знайдені категорії для обох одиниць?
    if not from_category or not to_category:
        missing = []
        if not from_category: missing.append(from_unit)
        if not to_category: missing.append(to_unit)
        # Не друкуємо помилку тут, бо це може бути валюта
        # print(f"Помилка: Невідомі одиниці: {', '.join(missing)}")
        return None # Просто повертаємо None, щоб main_bot спробував валюту

    # Перевірка 2: Чи належать одиниці до однієї категорії?
    if from_category != to_category:
        print(f"Помилка: Неможливо конвертувати між різними категоріями ({from_category} -> {to_category})")
        return None

    # Отримуємо коефіцієнти для відповідної категорії
    factors = CONVERSION_FACTORS[from_category]

    try:
        # Отримуємо коефіцієнти, перевіряючи наявність ключів
        factor_from = factors.get(from_unit_lower)
        factor_to = factors.get(to_unit_lower)

        if factor_from is None or factor_to is None:
             # Ця помилка не мала б виникати через get_unit_category, але про всяк випадок
             print(f"Помилка: Не знайдено коефіцієнт для {from_unit} або {to_unit} у категорії {from_category}")
             return None

        if factor_to == 0:
            print(f"Помилка: Коефіцієнт для цільової одиниці {to_unit} дорівнює нулю.")
            return None

        # Конвертація через базову одиницю категорії
        value_in_base_unit = value * factor_from
        converted_value = value_in_base_unit / factor_to
        return converted_value

    except ZeroDivisionError:
        # Ця помилка оброблена вище, але залишимо про всяк випадок
        print(f"Помилка ділення на нуль при конвертації одиниць (коефіцієнт для {to_unit} може бути 0).")
        return None
    except Exception as e:
        print(f"Неочікувана помилка під час конвертації одиниць: {e}")
        return None


# --- Приклад використання (для тестування) ---
if __name__ == "__main__":
    print("--- Тести конвертації одиниць ---")

    # Тест 1: Довжина
    val = 10.0
    f_unit = "km"
    t_unit = "m"
    res = convert_units(val, f_unit, t_unit)
    if res is not None:
        print(f"{val} {f_unit} = {res:.3f} {t_unit}")
    else:
        print(f"Помилка конвертації {f_unit} -> {t_unit}")

    # Тест 2: Маса
    val = 5.0
    f_unit = "kg"
    t_unit = "g"
    res = convert_units(val, f_unit, t_unit)
    if res is not None:
        print(f"{val} {f_unit} = {res:.1f} {t_unit}")
    else:
        print(f"Помилка конвертації {f_unit} -> {t_unit}")

    # Тест 3: Об'єм
    val = 2.5
    f_unit = "l"
    t_unit = "ml"
    res = convert_units(val, f_unit, t_unit)
    if res is not None:
        print(f"{val} {f_unit} = {res:.1f} {t_unit}")
    else:
        print(f"Помилка конвертації {f_unit} -> {t_unit}")

    # Тест 4: Не СІ одиниці
    val = 100.0
    f_unit = "ft"
    t_unit = "cm"
    res = convert_units(val, f_unit, t_unit)
    if res is not None:
        print(f"{val} {f_unit} = {res:.2f} {t_unit}")
    else:
        print(f"Помилка конвертації {f_unit} -> {t_unit}")

    # Тест 5: Різні категорії (помилка)
    val = 1.0
    f_unit = "kg"
    t_unit = "m"
    res = convert_units(val, f_unit, t_unit)
    if res is None:
        print(f"Помилка конвертації {f_unit} -> {t_unit} (очікувана помилка)")

    # Тест 6: Невідома одиниця (помилка)
    val = 1.0
    f_unit = "km"
    t_unit = "xyz"
    res = convert_units(val, f_unit, t_unit)
    if res is None:
        print(f"Помилка конвертації {f_unit} -> {t_unit} (очікувана помилка)")
