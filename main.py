import asyncio
import json
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8687270310:AAE3zpVz2QWDvFCEYHmXhPE2XOUCkkFVyIw"
CRYPTOBOT_TOKEN = "563565:AAYHI6yh4ZskQJHMGEVLVuDUk4H6FhvuYrb"  # Получить у @CryptoBot → /token
ADMIN_ID = 6606706488  # Ваш Telegram ID

# Товары: название → цена в USDT (можно дробные, например 3.9)
PRODUCTS = {
    "urent_6":      {"name": "Юрент | 6 поездок",      "price": 3.90,  "service": "Юрент"},
    "urent_10":     {"name": "Юрент | 10 поездок",     "price": 4.70,  "service": "Юрент"},
    "urent_week":   {"name": "Юрент | Недельная",      "price": 5.00,  "service": "Юрент"},
    "urent_2weeks": {"name": "Юрент | 2 недели",       "price": 6.80,  "service": "Юрент"},
    "whoosh_6":     {"name": "Whoosh | 6 поездок",     "price": 3.90,  "service": "Whoosh"},
    "whoosh_10":    {"name": "Whoosh | 10 поездок",    "price": 4.70,  "service": "Whoosh"},
}

# База промокодов (для простоты в памяти, лучше заменить на SQLite)
# Ключ: (сервис, тип_товара) → список кодов
PROMO_STORAGE = {
    ("Юрент", "urent_6"):      ["URENT6-ABCD", "URENT6-EFGH"],
    ("Юрент", "urent_10"):     ["URENT10-1234", "URENT10-5678"],
    ("Юрент", "urent_week"):   ["URENTWEEK-A1B2"],
    ("Юрент", "urent_2weeks"): ["URENT2W-XYZZ"],
    ("Whoosh", "whoosh_6"):    ["WHOOSH6-QWER"],
    ("Whoosh", "whoosh_10"):   ["WHOOSH10-ASDF"],
}

# Храним временные данные пользователей
user_temp = {}

# ========== ИНИЦИАЛИЗАЦИЯ ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    buttons = [
        [InlineKeyboardButton(text="🛴 Whoosh", callback_data="service_whoosh")],
        [InlineKeyboardButton(text="🛴 Юрент", callback_data="service_urent")],
        [InlineKeyboardButton(text="📞 Поддержка", callback_data="support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def products_menu(service):
    buttons = []
    for key, p in PRODUCTS.items():
        if p["service"].lower() == service.lower():
            buttons.append([InlineKeyboardButton(
                text=f"{p['name']} — {p['price']} USDT",
                callback_data=f"buy_{key}"
            )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== ФУНКЦИИ РАБОТЫ С CRYPTO BOT ==========
async def create_crypto_invoice(amount_usdt: float, product_key: str, user_id: int):
    """Создаёт счёт в Crypto Bot и возвращает ссылку на оплату и invoice_id"""
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount_usdt),
        "description": PRODUCTS[product_key]["name"],
        "paid_btn_name": "callback",
        "paid_btn_url": f"https://t.me/{bot.bot.username}",
        "payload": json.dumps({"product": product_key, "user_id": user_id})
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]["bot_invoice_url"], data["result"]["invoice_id"]
            else:
                logging.error(f"CryptoBot error: {data}")
                return None, None

async def check_invoice_status(invoice_id: int):
    """Проверяет статус счёта"""
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {"invoice_ids": invoice_id}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]["status"]  # active, paid, expired
    return "unknown"

# ========== ОБРАБОТЧИКИ БОТА ==========
@dp.message(Command("start"))
async def start(message: Message):
    text = (
        "🏪 *WhooshShop | ЮрентShop*\n\n"
        "Перемещайся по городу так, как хочешь!\n"
        "Быстро, комфортно и с удовольствием.\n\n"
        "Добро пожаловать в наш онлайн магазин промокодов! 🎁\n\n"
        "Выберите компанию, чтобы начать 👇"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Выберите компанию:", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.answer("📞 По вопросам писать: @ваш_ник_поддержки")
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def show_products(callback: CallbackQuery):
    service = callback.data.split("_")[1]  # whoosh или urent
    name = "Whoosh" if service == "whoosh" else "Юрент"
    await callback.message.edit_text(
        f"💡 {name} промокоды 💡\n\nВыберите нужный промокод:",
        reply_markup=products_menu(name)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_key = callback.data.split("_")[1]
    product = PRODUCTS.get(product_key)
    if not product:
        await callback.answer("Товар не найден")
        return
    
    # Проверяем, есть ли промокоды в наличии
    promo_list = PROMO_STORAGE.get((product["service"], product_key), [])
    if not promo_list:
        await callback.answer("❌ Промокоды временно закончились. Напишите в поддержку.")
        return
    
    # Сохраняем, какой товар купили
    user_temp[callback.from_user.id] = {"product_key": product_key}
    
    # Создаём счёт в Crypto Bot
    invoice_url, invoice_id = await create_crypto_invoice(
        product["price"], product_key, callback.from_user.id
    )
    
    if not invoice_url:
        await callback.message.answer("Ошибка оплаты, попробуйте позже.")
        return
    
    # Сохраняем invoice_id для проверки
    user_temp[callback.from_user.id]["invoice_id"] = invoice_id
    
    text = (
        f"🛒 *{product['name']}*\n"
        f"💰 Цена: {product['price']} USDT (TRC20)\n\n"
        f"🔗 *Ссылка для оплаты:*\n"
        f"{invoice_url}\n\n"
        "⚠️ *Инструкция:*\n"
        "1. Перейдите по ссылке\n"
        "2. Оплатите через любой кошелёк USDT (TRC20)\n"
        "3. *После оплаты нажмите кнопку «Я ОПЛАТИЛ»* 👇\n\n"
        "Бот проверит платёж и выдаст промокод автоматически."
    )
    
    # Кнопка проверки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data=f"check_{product_key}")]
    ])
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: CallbackQuery):
    product_key = callback.data.split("_")[1]
    user_data = user_temp.get(callback.from_user.id, {})
    invoice_id = user_data.get("invoice_id")
    
    if not invoice_id:
        await callback.answer("❌ Не найден активный счёт. Начните покупку заново.")
        return
    
    # Проверяем статус
    status = await check_invoice_status(invoice_id)
    
    if status == "paid":
        # Оплачено → выдаём промокод
        service = PRODUCTS[product_key]["service"]
        promo_list = PROMO_STORAGE.get((service, product_key), [])
        
        if promo_list:
            promo_code = promo_list.pop(0)  # Забираем первый доступный
            # Обновляем хранилище
            PROMO_STORAGE[(service, product_key)] = promo_list
            
            await callback.message.edit_text(
                f"✅ *Оплата подтверждена!*\n\n"
                f"🎫 Ваш промокод:\n`{promo_code}`\n\n"
                f"📌 Инструкция:\n"
                f"1. Зайдите в приложение {service}\n"
                f"2. Раздел «Промокоды» → «Ввести промокод»\n"
                f"3. Активируйте и пользуйтесь!\n\n"
                f"💬 Сохраните это сообщение.",
                parse_mode=ParseMode.MARKDOWN
            )
            # Удаляем временные данные
            del user_temp[callback.from_user.id]
        else:
            await callback.message.answer("❌ Коды закончились, обратитесь в поддержку.")
    elif status == "active":
        await callback.answer("⏳ Платёж ещё не получен. Подождите 2-3 минуты и попробуйте снова.", show_alert=True)
    else:
        await callback.answer("❌ Платёж не найден или истёк. Создайте новый заказ через /start", show_alert=True)

# ========== ЗАПУСК ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
