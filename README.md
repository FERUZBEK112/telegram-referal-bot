# Telegram Referal Bot

O‘zbek tilidagi Telegram referral bot. Har bir yangi taklif qilingan foydalanuvchi uchun taklif qiluvchiga 250 so‘m (yoki `REFERRAL_REWARD`) yoziladi.

## Imkoniyatlar

- `/start` va shaxsiy referral havola
- Bir foydalanuvchi uchun faqat bir marta bonus
- O‘zini o‘zi taklif qilishdan himoya
- Kabinet: balans va referallar soni
- Karta orqali pul yechish so‘rovi
- Admin uchun tasdiqlash/rad etish tugmalari
- SQLite va PostgreSQL qo‘llab-quvvatlanadi

## Ishga tushirish

1. `.env.example` faylidan `.env` yarating.
2. `BOT_TOKEN` va `ADMIN_IDS` qiymatlarini kiriting.
3. `pip install -r requirements.txt` buyrug‘ini bajaring.
4. `python -m app.main` bilan ishga tushiring.

## Railway o‘zgaruvchilari

- `BOT_TOKEN` — BotFather bergan token (majburiy)
- `ADMIN_IDS` — vergul bilan ajratilgan Telegram raqamli ID lar
- `DATABASE_URL` — PostgreSQL ulanish manzili yoki SQLite URL
- `REFERRAL_REWARD` — standart `250`
- `MIN_WITHDRAWAL` — standart `5000`
- `SUPPORT_USERNAME` — `@` belgisiz username

Maxfiy tokenni GitHub’ga joylamang.
