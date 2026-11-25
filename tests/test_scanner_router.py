import unittest

from app247_terminal.services.scanner_router import ScannerRouter, ScanType


class ScannerRouterTest(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.router = ScannerRouter(clock=lambda: self.now)

    def test_product_barcode_and_newline(self):
        result = self.router.parse("7891234567890\r\n")
        self.assertEqual(ScanType.PRODUCT_BARCODE, result.type)
        self.assertEqual("7891234567890", result.value)

    def test_customer_qr_uses_explicit_prefix(self):
        opaque = "A" * 43
        result = self.router.parse(f"app247://customer-link/{opaque}\n")
        self.assertEqual(ScanType.CUSTOMER_LINK_TOKEN, result.type)
        self.assertEqual(opaque, result.value)

    def test_customer_qr_survives_keyboard_layout_mismatch(self):
        opaque = "bWQ-2Ll5MD1WubCPSyr7PSvUFavCcbkKQ4OqcveM4ao"
        for raw in (
            f"app247\u00c7;;customer-link;{opaque}",  # leitor US, sistema ABNT2
            f"app247??customer-link?{opaque}",
            f"app247customer-link{opaque}",  # separadores descartados
            f"APP247://CUSTOMER-LINK/{opaque}",
        ):
            self.now += 1
            result = self.router.parse(raw + "\n")
            self.assertEqual(ScanType.CUSTOMER_LINK_TOKEN, result.type, raw)
            self.assertEqual(opaque, result.value, raw)

    def test_customer_token_starting_with_dash_keeps_full_value(self):
        opaque = "-" + "C" * 42
        result = self.router.parse(f"app247\u00c7;;customer-link;{opaque}")
        self.assertEqual(ScanType.CUSTOMER_LINK_TOKEN, result.type)
        self.assertEqual(opaque, result.value)

    def test_garbled_app_qr_is_never_treated_as_product(self):
        result = self.router.parse("app247\u00c7;;customer-link;partial")
        self.assertEqual(ScanType.UNKNOWN, result.type)

    def test_unknown_partial_and_empty(self):
        self.assertEqual(ScanType.UNKNOWN, self.router.parse("").type)
        self.assertEqual(
            ScanType.UNKNOWN,
            self.router.parse("app247://customer-link/partial").type,
        )
        self.assertEqual(ScanType.UNKNOWN, self.router.parse("app247://coupon/x").type)

    def test_duplicate_customer_hid_event_is_suppressed(self):
        qr = "app247://customer-link/" + ("B" * 43)
        self.assertEqual(ScanType.CUSTOMER_LINK_TOKEN, self.router.parse(qr).type)
        self.now += 0.1
        duplicate = self.router.parse(qr + "\n")
        self.assertEqual(ScanType.UNKNOWN, duplicate.type)
        self.assertEqual("", duplicate.value)

    def test_repeated_product_scan_remains_two_events(self):
        self.assertEqual(ScanType.PRODUCT_BARCODE, self.router.parse("789").type)
        self.now += 0.1
        self.assertEqual(ScanType.PRODUCT_BARCODE, self.router.parse("789").type)


if __name__ == "__main__":
    unittest.main()
