from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Kabinet"), KeyboardButton(text="🔗 Referal")],
            [KeyboardButton(text="💳 Pul yechish"), KeyboardButton(text="🆘 Yordam")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Kerakli bo‘limni tanlang",
    )


def admin_withdrawal_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To‘landi", callback_data=f"payout:approve:{withdrawal_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish", callback_data=f"payout:reject:{withdrawal_id}"
                ),
            ]
        ]
    )

