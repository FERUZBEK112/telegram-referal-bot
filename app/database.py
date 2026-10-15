from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, User, Withdrawal


@dataclass(slots=True)
class RegistrationResult:
    user: User
    is_new: bool
    rewarded_inviter_id: int | None = None


class Database:
    def __init__(self, url: str, referral_reward: int) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.referral_reward = referral_reward

    async def init(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def register_user(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str,
        referrer_id: int | None,
    ) -> RegistrationResult:
        async with self.sessions() as session:
            existing = await session.get(User, telegram_id)
            if existing:
                existing.username = username
                existing.full_name = full_name
                await session.commit()
                return RegistrationResult(existing, False)

            valid_referrer: int | None = None
            if referrer_id and referrer_id != telegram_id:
                inviter = await session.get(User, referrer_id)
                if inviter:
                    valid_referrer = referrer_id

            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                referred_by=valid_referrer,
            )
            session.add(user)
            try:
                await session.flush()
                if valid_referrer:
                    await session.execute(
                        update(User)
                        .where(User.telegram_id == valid_referrer)
                        .values(
                            balance=User.balance + self.referral_reward,
                            referral_count=User.referral_count + 1,
                        )
                    )
                await session.commit()
                return RegistrationResult(user, True, valid_referrer)
            except IntegrityError:
                await session.rollback()
                existing = await session.get(User, telegram_id)
                if existing is None:
                    raise
                return RegistrationResult(existing, False)

    async def get_user(self, telegram_id: int) -> User | None:
        async with self.sessions() as session:
            return await session.get(User, telegram_id)

    async def create_withdrawal(
        self, user_id: int, amount: int, card_number: str
    ) -> Withdrawal | None:
        async with self.sessions() as session:
            user = await session.get(User, user_id, with_for_update=True)
            if not user or amount <= 0 or user.balance < amount:
                return None
            user.balance -= amount
            withdrawal = Withdrawal(user_id=user_id, amount=amount, card_number=card_number)
            session.add(withdrawal)
            await session.commit()
            await session.refresh(withdrawal)
            return withdrawal

    async def resolve_withdrawal(self, withdrawal_id: int, approve: bool) -> Withdrawal | None:
        async with self.sessions() as session:
            withdrawal = await session.get(Withdrawal, withdrawal_id, with_for_update=True)
            if not withdrawal or withdrawal.status != "pending":
                return None
            withdrawal.status = "approved" if approve else "rejected"
            if not approve:
                user = await session.get(User, withdrawal.user_id, with_for_update=True)
                if user:
                    user.balance += withdrawal.amount
            await session.commit()
            return withdrawal

