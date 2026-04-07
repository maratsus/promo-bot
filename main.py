import os
import asyncio
import json
import aiohttp
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ (БЕЗОПАСНО) ==========
# На Render добавь эти переменные в Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_ID = 6606706488
SUPPORT_CONTACT = "@hdhdjdjggdr"

# Проверка наличия токенов
if not BOT_TOKEN or not CRYPTOBOT_TOKEN:
    logging.error("Токены BOT_TOKEN или CRYPTOBOT_TOKEN не найдены в переменных окружения!")

# Товары
PRODUCTS = {
    "urent_6":      {"name": "Юрент | 6 поездок",      "price": 3.90,  "service": "Юрент", "code": "URENT6-ABCD"},
    "urent_10":     {"name": "Юрент | 10 поездок",     "price": 4.70,  "service": "Юрент", "code": "URENT10-1234"},
    "urent_week":   {"name": "Юрент | Недельная",      "price": 5.00,  "service": "Юрент", "code": "URENTWEEK-A1B2"},
    "urent_2weeks": {"name": "Юрент | 2 недели",       "price": 6.80,  "service": "Юрент", "code": "URENT2W-XYZZ"},
    
    "whoosh_6":     {"name": "Whoosh | 6 поездок",     "price": 3.90,  "service": "Whoosh", "code": "WHOOSH6-QWER"},
    "whoosh_10":    {"name": "Whoosh | 10 поездок",    "price": 4.70,  "service": "Whoosh", "code": "WHOOSH10-ASDF"},
    
    "yandex_scooter_6":   {"name": "Яндекс Самокат | 6 поездок",  "price": 1.95,  "service": "Яндекс Самокат", "code": "YNDXSC6-ABCD"},
    "yandex_scooter_10":  {"name": "Яндекс Самокат | 10 поездок", "price": 2.35,  "service": "Яндекс Самокат", "code": "YNDXSC10-EFGH"},
    "yandex_scooter_week": {"name": "Яндекс Самокат | Недельная", "price": 2.50,  "service": "Яндекс Самокат", "code": "YNDXSCWK-1234"},
    
    "yandex_taxi_3":  {"name": "Яндекс Такси | 3 бесплатные поездки", "price": 5.00, "service": "Яндекс Такси", "code": "YNDXTAXI-3FREE"},
}

user_data = {}
users_db = {}
payments_db = []

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    buttons = [
        [InlineKeyboardButton(text="🛴 Whoosh", callback_data="service_whoosh")],
        [InlineKeyboardButton(text="🛴 Юрент", callback_data="service_urent")],
        [InlineKeyboardButton(text="🛴 Яндекс Самокат", callback_data="service_yandex_scooter")],
        [InlineKeyboardButton(text="🚖 Яндекс Такси", callback_data="service_yandex_taxi")],
        [InlineKeyboardButton(text="📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="🔐 Админ панель", callback_data="admin_panel")]
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

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Все оплаты", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

# ========== CRYPTO BOT API ==========
async def create_crypto_invoice(amount_usdt: float, product_key: str, user_id: int):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount_usdt),
        "description": PRODUCTS[product_key]["name"],
        "paid_btn_name": "callback",
        "payload": json.dumps({"product": product_key, "user_id": user_id})
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data["result"]["bot_invoice_url"], data["result"]["invoice_id"]
        return None, None
    except Exception:
        return None, None

async def check_invoice_status(invoice_id: int):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {"invoice_ids": invoice_id}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                data = await resp.json()
                if data.get("ok") and data["result"]["items"]:
                    return data["result"]["items"][0]["status"]
        return "unknown"
    except Exception:
        return "unknown"

# ========== ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    uname = message.from_user.username or message.from_user.full_name
    if uid not in users_db:
        users_db[uid] = {"username": uname, "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    
    text = (
        "🏪 *WhooshShop | ЮрентShop | ЯндексShop*\n\n"
        "Выберите компанию, чтобы начать покупку 👇"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Выберите компанию:", reply_markup=main_menu())

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.edit_text(f"📞 *Поддержка*\n\nПишите: {SUPPORT_CONTACT}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

@dp.callback_query(F.data.startswith("service_"))
async def show_products(callback: CallbackQuery):
    service_map = {"whoosh": "Whoosh", "urent": "Юрент", "yandex_scooter": "Яндекс Самокат", "yandex_taxi": "Яндекс Такси"}
    key = callback.data.split("_", 1)[1]
    name = service_map.get(key, "Сервис")
    await callback.message.edit_text(f"🎫 *Вы выбрали {name}*\n\nВыберите нужный промокод:", parse_mode=ParseMode.MARKDOWN, reply_markup=products_menu(name))

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    # ИСПРАВЛЕННАЯ ЛОГИКА: корректно извлекаем ключ товара
    product_key = callback.data.replace("buy_", "")
    product = PRODUCTS.get(product_key)
    
    if not product:
        await callback.answer(f"❌ Товар не найден: {product_key}", show_alert=True)
        return
    
    invoice_url, invoice_id = await create_crypto_invoice(product["price"], product_key, callback.from_user.id)
    if not invoice_url:
        await callback.message.answer("❌ Ошибка платежной системы. Проверьте токены в админке.")
        return
    
    user_data[callback.from_user.id] = {"invoice_id": invoice_id, "product_key": product_key, "product": product}
    
    text = (
        f"🛒 *{product['name']}*\n"
        f"💰 Цена: {product['price']} USDT\n\n"
        f"🔗 [Оплатить через Crypto Bot]({invoice_url})\n\n"
        "После оплаты нажмите кнопку ниже 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data=f"check_{product_key}")]])
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: CallbackQuery):
    uid = callback.from_user.id
    data = user_data.get(uid)
    if not data:
        await callback.answer("❌ Счёт не найден. Начните заново.", show_alert=True)
        return
    
    status = await check_invoice_status(data["invoice_id"])
    if status == "paid":
        product = data["product"]
        payments_db.append({"username": callback.from_user.username, "product": product["name"], "amount": product["price"], "date": datetime.now().strftime("%Y-%m-%d")})
        
        await callback.message.edit_text(
            f"✅ *Оплата принята!*\n\nВаш промокод для {product['service']}:\n`{product['code']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_button()
        )
        del user_data[uid]
        await bot.send_message(ADMIN_ID, f"💰 Новая покупка: {product['name']} от @{callback.from_user.username}")
    else:
        await callback.answer("⏳ Оплата пока не подтверждена.", show_alert=True)

# ========== АДМИНКА ==========
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("🔐 *Админ панель*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    total_rev = sum(p["amount"] for p in payments_db)
    await callback.message.edit_text(f"📊 *Статистика*\n\nПользователей: {len(users_db)}\nПродаж: {len(payments_db)}\nВыручка: {total_rev} USDT", parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

# Остальные обработчики админки (аналогично твоим)
# ...

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
