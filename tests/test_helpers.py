import unittest

from app.main import format_money, parse_referrer


class HelperTests(unittest.TestCase):
    def test_parse_referrer(self) -> None:
        self.assertEqual(parse_referrer("ref_123"), 123)
        self.assertIsNone(parse_referrer("123"))
        self.assertIsNone(parse_referrer("ref_bad"))
        self.assertIsNone(parse_referrer(None))

    def test_format_money(self) -> None:
        self.assertEqual(format_money(12500), "12 500 so‘m")

