from dataclasses import dataclass
from enum import Enum
import time


CUSTOMER_LINK_PREFIX = "app247://customer-link/"


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
        if value.startswith(CUSTOMER_LINK_PREFIX):
            opaque = value[len(CUSTOMER_LINK_PREFIX):]
            if len(opaque) == 43 and all(
                character.isalnum() or character in "-_" for character in opaque
            ):
                result = ScanResult(ScanType.CUSTOMER_LINK_TOKEN, opaque)
            else:
                result = ScanResult(ScanType.UNKNOWN, value)
        elif "://" in value:
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
