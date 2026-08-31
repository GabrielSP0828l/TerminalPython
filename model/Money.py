from decimal import Decimal, ROUND_HALF_UP


PERSISTENCE_QUANTUM = Decimal("0.000001")
QUANTITY_QUANTUM = Decimal("0.001")
CHARGED_QUANTUM = Decimal("0.01")


def decimal_value(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def persisted(value):
    return decimal_value(value).quantize(PERSISTENCE_QUANTUM, rounding=ROUND_HALF_UP)


def quantity(value):
    if value is None:
        return None
    return decimal_value(value).quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def charged(value):
    return decimal_value(value).quantize(CHARGED_QUANTUM, rounding=ROUND_HALF_UP)


def format_brl(value):
    return f"R$ {charged(value):.2f}".replace(".", ",")
