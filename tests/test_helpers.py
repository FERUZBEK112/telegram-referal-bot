import unittest
from unittest.mock import patch

from app.config import Settings
from app.main import format_money, parse_referrer


class HelperTests(unittest.TestCase):
    def test_parse_referrer(self) -> None:
        self.assertEqual(parse_referrer("ref_123"), 123)
        self.assertIsNone(parse_referrer("123"))
        self.assertIsNone(parse_referrer("ref_bad"))
        self.assertIsNone(parse_referrer(None))

    def test_format_money(self) -> None:
        self.assertEqual(format_money(12500), "12 500 so‘m")

    def test_admin_ids_from_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {"BOT_TOKEN": "test-token", "ADMIN_IDS": "7021389442,123"},
            clear=True,
        ):
            settings = Settings()
        self.assertEqual(settings.admin_ids, [7021389442, 123])

