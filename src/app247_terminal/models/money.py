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
    """Real brasileiro para exibição: ``R$ 1.299,90`` (ponto no milhar)."""
    amount = charged(value)
    sign = "-" if amount < 0 else ""
    text = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {text}"
