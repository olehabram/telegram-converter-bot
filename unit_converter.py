import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

CONVERSION_FACTORS = {
    'length': {
        'mm': 0.001,
        'cm': 0.01,
        'm': 1.0,
        'km': 1000.0,
        'in': 0.0254,
        'ft': 0.3048,
        'yd': 0.9144,
        'mi': 1609.34,
    },
    'mass': {
        'mg': 1e-6,
        'g': 0.001,
        'kg': 1.0,
        't': 1000.0,
        'oz': 0.0283495,
        'lb': 0.453592,
    },
    'volume': {
        'ml': 0.001,
        'l': 1.0,
        'm3': 1000.0,
        'gal': 3.78541,
    }
}


def get_unit_category(unit: str) -> str | None:
    unit = unit.lower()
    for category, units in CONVERSION_FACTORS.items():
        if unit in units:
            return category
    return None


def convert_units(value: float, from_unit: str, to_unit: str) -> float | None:
    from_unit_l = from_unit.lower()
    to_unit_l = to_unit.lower()

    from_cat = get_unit_category(from_unit_l)
    to_cat = get_unit_category(to_unit_l)

    if not from_cat or not to_cat:
        logger.error(f"Unknown unit(s): {from_unit} or {to_unit}")
        return None

    if from_cat != to_cat:
        if not (len(from_unit) == 3 and from_unit.isalpha() and len(to_unit) == 3 and to_unit.isalpha()):
            logger.error(f"Cannot convert between different categories: {from_cat} -> {to_cat}")
            return None

    factors = CONVERSION_FACTORS[from_cat]

    try:
        factor_from = factors[from_unit_l]
        factor_to = factors[to_unit_l]

        if factor_to == 0:
            logger.error(f"Conversion factor for target unit {to_unit} is zero.")
            return None

        base_value = value * factor_from
        converted = base_value / factor_to
        logger.info(f"Converted {value} {from_unit} to {converted:.4f} {to_unit}")
        return converted
    except KeyError:
        logger.error(f"Conversion factors missing for {from_unit} or {to_unit} in category {from_cat}")
    except ZeroDivisionError:
        logger.error(f"Division by zero error for target unit {to_unit}")
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {e}")

    return None


if __name__ == "__main__":
    # Прості тести
    tests = [
        (7.32, "m", "yd"),
        (100, "kg", "lb"),
        (500, "ml", "gal"),
        (1, "km", "mi"),
        (10, "ft", "cm"),
        (100, "USD", "EUR"),  # Має повертати None (різні категорії)
    ]

    for val, f_unit, t_unit in tests:
        res = convert_units(val, f_unit, t_unit)
        if res is not None:
            print(f"{val} {f_unit} = {res:.4f} {t_unit}")
        else:
            print(f"Conversion failed: {f_unit} -> {t_unit}")
