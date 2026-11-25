from dataclasses import dataclass
from enum import Enum
import re
import time


CUSTOMER_LINK_PREFIX = "app247://customer-link/"
APP_QR_SCHEME = "app247"
# Leitores HID configurados com outro layout de teclado (US x ABNT2) trocam
# ":" e "/" por outros símbolos (ex.: "app247Ç;;customer-link;..."). Letras,
# dígitos, "-" e "_" saem iguais, então o QR é reconhecido pela estrutura e os
# separadores podem ser qualquer não alfanumérico.
_CUSTOMER_LINK_PATTERN = re.compile(
    r"app247[^A-Za-z0-9]{0,4}customer-link[^A-Za-z0-9]{0,2}([A-Za-z0-9_-]{43})",
    re.IGNORECASE,
)


class ScanType(Enum):
    PRODUCT_BARCODE = "PRODUCT_BARCODE"
    CUSTOMER_LINK_TOKEN = "CUSTOMER_LINK_TOKEN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ScanResult:
    type: ScanType
    value: str


class ScannerRouter:
    """Classifica o framing explícito e suprime o Enter duplicado do HID."""

    def __init__(self, duplicate_window_seconds=0.35, clock=None):
        self.duplicate_window_seconds = float(duplicate_window_seconds)
        self.clock = clock or time.monotonic
        self._last_value = None
        self._last_at = 0.0

    def parse(self, raw):
        value = str(raw or "").strip()
        if not value:
            return ScanResult(ScanType.UNKNOWN, "")
        customer_link = _CUSTOMER_LINK_PATTERN.fullmatch(value)
        if customer_link:
            result = ScanResult(ScanType.CUSTOMER_LINK_TOKEN, customer_link.group(1))
        elif value.lower().startswith(APP_QR_SCHEME) or "://" in value:
            result = ScanResult(ScanType.UNKNOWN, value)
        else:
            result = ScanResult(ScanType.PRODUCT_BARCODE, value)

        now = self.clock()
        if result.type == ScanType.CUSTOMER_LINK_TOKEN \
                and result.value and result.value == self._last_value \
                and now - self._last_at <= self.duplicate_window_seconds:
            return ScanResult(ScanType.UNKNOWN, "")
        self._last_value = result.value
        self._last_at = now
        return result
