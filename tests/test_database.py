import tempfile
import unittest
from pathlib import Path

from app.database import Database


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tempdir.name) / "test.db"
        self.db = Database(f"sqlite+aiosqlite:///{db_path}", referral_reward=250)
        await self.db.init()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tempdir.cleanup()

    async def test_referral_reward_is_given_only_once(self) -> None:
        await self.db.register_user(1, "inviter", "Inviter", None)

        first = await self.db.register_user(2, "friend", "Friend", 1)
        second = await self.db.register_user(2, "friend_new", "Friend New", 1)

        inviter = await self.db.get_user(1)
        self.assertTrue(first.is_new)
        self.assertEqual(first.rewarded_inviter_id, 1)
        self.assertFalse(second.is_new)
        self.assertIsNotNone(inviter)
        self.assertEqual(inviter.balance, 250)
        self.assertEqual(inviter.referral_count, 1)

    async def test_self_referral_is_ignored(self) -> None:
        result = await self.db.register_user(3, None, "Self", 3)
        user = await self.db.get_user(3)

        self.assertTrue(result.is_new)
        self.assertIsNone(result.rewarded_inviter_id)
        self.assertIsNone(user.referred_by)

    async def test_rejected_withdrawal_refunds_balance(self) -> None:
        await self.db.register_user(10, None, "Inviter", None)
        await self.db.register_user(11, None, "A", 10)
        await self.db.register_user(12, None, "B", 10)
        withdrawal = await self.db.create_withdrawal(10, 500, "8600123412341234")

        self.assertIsNotNone(withdrawal)
        user = await self.db.get_user(10)
        self.assertEqual(user.balance, 0)

        await self.db.resolve_withdrawal(withdrawal.id, approve=False)
        user = await self.db.get_user(10)
        self.assertEqual(user.balance, 500)

