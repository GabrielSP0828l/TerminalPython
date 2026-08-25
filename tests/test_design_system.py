import unittest

from styles.theme import Theme
from styles.tokens import Colors, FontSize, Radius, Spacing


class DesignSystemTest(unittest.TestCase):
    def test_semantic_color_tokens_are_valid_hex_values(self):
        token_names = (
            "BACKGROUND_PRIMARY",
            "BACKGROUND_SECONDARY",
            "SURFACE",
            "PRIMARY",
            "SECONDARY",
            "TEXT_PRIMARY",
            "TEXT_SECONDARY",
            "BORDER",
            "SUCCESS",
            "WARNING",
            "ERROR",
            "INFO",
        )
        for name in token_names:
            value = getattr(Colors, name)
            self.assertRegex(value, r"^#[0-9A-F]{6}$", name)

    def test_scales_are_ordered(self):
        self.assertLess(Spacing.XS, Spacing.SM)
        self.assertLess(Spacing.SM, Spacing.MD)
        self.assertLess(Spacing.MD, Spacing.LG)
        self.assertLess(Radius.INPUT, Radius.CARD)
        self.assertLess(FontSize.CAPTION, FontSize.BODY)
        self.assertLess(FontSize.BODY, FontSize.H1)

    def test_theme_exposes_reusable_component_variants(self):
        stylesheet = Theme.component_stylesheet()
        for selector in (
            'variant="primary"',
            'variant="secondary"',
            'variant="danger"',
            'variant="ghost"',
            'role="input"',
            'role="card"',
            'state="success"',
            'state="error"',
            'state="loading"',
        ):
            self.assertIn(selector, stylesheet)

    def test_activation_theme_uses_official_tokens(self):
        stylesheet = Theme.activation_stylesheet()
        self.assertIn(Colors.BACKGROUND_PRIMARY, stylesheet)
        self.assertIn(Colors.PRIMARY, stylesheet)
        self.assertIn(Colors.SUCCESS, stylesheet)
        self.assertIn(Colors.ERROR, stylesheet)


if __name__ == "__main__":
    unittest.main()
