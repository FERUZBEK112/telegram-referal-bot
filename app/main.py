import asyncio
import logging
import re
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.client.default import DefaultBotProperties

from app.config import Settings, get_settings
from app.database import Database
from app.keyboards import admin_withdrawal_keyboard, main_menu


class WithdrawForm(StatesGroup):
    amount = State()
    card = State()


def parse_referrer(args: str | None) -> int | None:
    if not args:
        return None
    match = re.fullmatch(r"ref_(\d+)", args.strip())
    return int(match.group(1)) if match else None


def format_money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " so‘m"


def build_router(db: Database, settings: Settings) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start(message: Message, command: CommandObject, bot: Bot) -> None:
        if not message.from_user:
            return
        result = await db.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            referrer_id=parse_referrer(command.args),
        )
        if result.rewarded_inviter_id:
            try:
                await bot.send_message(
                    result.rewarded_inviter_id,
                    f"🎉 Yangi referal qo‘shildi! Balansingizga "
                    f"{format_money(settings.referral_reward)} qo‘shildi.",
                )
            except Exception:
                logging.exception("Inviter notification failed")
        await message.answer(
            f"Assalomu alaykum, <b>{escape(message.from_user.full_name)}</b>!\n\n"
            "Do‘stlaringizni taklif qiling va har bir yangi foydalanuvchi uchun "
            f"<b>{format_money(settings.referral_reward)}</b> oling.",
            reply_markup=main_menu(),
        )

    @router.message(F.text == "👤 Kabinet")
    async def cabinet(message: Message) -> None:
        if not message.from_user:
            return
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Avval /start buyrug‘ini bosing.")
            return
        await message.answer(
            "👤 <b>Shaxsiy kabinet</b>\n\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
            f"💰 Balans: <b>{format_money(user.balance)}</b>\n"
            f"👥 Referallar: <b>{user.referral_count} ta</b>"
        )

    @router.message(F.text == "🔗 Referal")
    async def referral(message: Message, bot: Bot) -> None:
        if not message.from_user:
            return
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
        await message.answer(
            "🔗 <b>Sizning referal havolangiz:</b>\n"
            f"<code>{link}</code>\n\n"
            "Har bir yangi do‘stingiz uchun "
            f"<b>{format_money(settings.referral_reward)}</b> olasiz."
        )

    @router.message(F.text == "💳 Pul yechish")
    async def withdraw_start(message: Message, state: FSMContext) -> None:
        if not message.from_user:
            return
        if not settings.admin_ids:
            await message.answer("Pul yechish vaqtincha sozlanmagan. Administratorga murojaat qiling.")
            return
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Avval /start buyrug‘ini bosing.")
            return
        if user.balance < settings.min_withdrawal:
            await message.answer(
                "Pul yechish uchun minimal balans: "
                f"<b>{format_money(settings.min_withdrawal)}</b>.\n"
                f"Sizning balansingiz: <b>{format_money(user.balance)}</b>."
            )
            return
        await state.set_state(WithdrawForm.amount)
        await message.answer(
            f"Yechmoqchi bo‘lgan summani kiriting (kamida {format_money(settings.min_withdrawal)}):\n"
            "Bekor qilish uchun /cancel yuboring."
        )

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Amal bekor qilindi.", reply_markup=main_menu())

    @router.message(WithdrawForm.amount)
    async def withdraw_amount(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").replace(" ", "")
        if not raw.isdigit():
            await message.answer("Summani faqat raqam bilan kiriting.")
            return
        amount = int(raw)
        if amount < settings.min_withdrawal:
            await message.answer(f"Minimal summa: {format_money(settings.min_withdrawal)}.")
            return
        await state.update_data(amount=amount)
        await state.set_state(WithdrawForm.card)
        await message.answer("Uzcard yoki Humo karta raqamini kiriting (16 ta raqam):")

    @router.message(WithdrawForm.card)
    async def withdraw_card(message: Message, state: FSMContext, bot: Bot) -> None:
        if not message.from_user:
            return
        card = re.sub(r"\D", "", message.text or "")
        if len(card) != 16:
            await message.answer("Karta raqami 16 ta raqamdan iborat bo‘lishi kerak.")
            return
        data = await state.get_data()
        amount = int(data["amount"])
        withdrawal = await db.create_withdrawal(message.from_user.id, amount, card)
        if not withdrawal:
            await state.clear()
            await message.answer("Balans yetarli emas yoki so‘rov yaratilmadi.", reply_markup=main_menu())
            return
        await state.clear()
        masked = f"{card[:4]} **** **** {card[-4:]}"
        admin_text = (
            "💸 <b>Yangi pul yechish so‘rovi</b>\n\n"
            f"So‘rov: <code>#{withdrawal.id}</code>\n"
            f"Foydalanuvchi: {escape(message.from_user.full_name)}\n"
            f"ID: <code>{message.from_user.id}</code>\n"
            f"Summa: <b>{format_money(amount)}</b>\n"
            f"Karta: <code>{card}</code>"
        )
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    admin_text,
                    reply_markup=admin_withdrawal_keyboard(withdrawal.id),
                )
            except Exception:
                logging.exception("Admin notification failed for %s", admin_id)
        await message.answer(
            f"✅ So‘rov qabul qilindi.\nSumma: <b>{format_money(amount)}</b>\nKarta: <code>{masked}</code>",
            reply_markup=main_menu(),
        )

    @router.callback_query(F.data.startswith("payout:"))
    async def payout_action(callback: CallbackQuery, bot: Bot) -> None:
        if not callback.from_user or callback.from_user.id not in settings.admin_ids:
            await callback.answer("Sizda ruxsat yo‘q.", show_alert=True)
            return
        _, action, raw_id = (callback.data or "").split(":", 2)
        withdrawal = await db.resolve_withdrawal(int(raw_id), approve=action == "approve")
        if not withdrawal:
            await callback.answer("Bu so‘rov avval ko‘rib chiqilgan.", show_alert=True)
            return
        status = "✅ To‘landi" if action == "approve" else "❌ Rad etildi"
        await callback.answer(status)
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"{status}: so‘rov #{withdrawal.id}")
        user_notice = (
            f"✅ {format_money(withdrawal.amount)} pul yechish so‘rovingiz tasdiqlandi."
            if action == "approve"
            else f"❌ Pul yechish so‘rovingiz rad etildi. {format_money(withdrawal.amount)} balansga qaytarildi."
        )
        try:
            await bot.send_message(withdrawal.user_id, user_notice)
        except Exception:
            logging.exception("Withdrawal result notification failed")

    @router.message(F.text == "🆘 Yordam")
    async def help_menu(message: Message) -> None:
        if settings.support_username:
            await message.answer(
                f"Savollar bo‘yicha: @{escape(settings.support_username)}\n\n"
                "Bekor qilish: /cancel"
            )
        else:
            await message.answer("Yordam xizmati tez orada ishga tushadi.\nBekor qilish: /cancel")

    @router.message()
    async def fallback(message: Message) -> None:
        await message.answer("Quyidagi menyudan foydalaning.", reply_markup=main_menu())

    return router


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    db = Database(settings.database_url, settings.referral_reward)
    await db.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(db, settings))
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(run())

