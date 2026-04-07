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
from aiohttp import web

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_ID = 6606706488
SUPPORT_CONTACT = "@hdhdjdjggdr"

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
            buttons.append([InlineKeyboardButton(text=f"{p['name']} — {p['price']} USDT", callback_data=f"buy_{key}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]])

# ========== ПЛАТЕЖИ (ИСПРАВЛЕНО) ==========
async def create_crypto_invoice(amount_usdt, product_key, user_id):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    
    # Ссылка на твоего бота, чтобы кнопка в чеке вела обратно
    bot_url = "https://t.me/whoosho_bot" 

    payload = {
        "asset": "USDT", 
        "amount": str(amount_usdt),
        "description": PRODUCTS[product_key]["name"],
        "paid_btn_name": "viewItem",      # ИЗМЕНЕНО: так надежнее для возврата
        "paid_btn_url": bot_url,          # ОБЯЗАТЕЛЬНО: исправляет ошибку 400
        "payload": json.dumps({"product": product_key, "user_id": user_id})
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logging.error(f"CryptoBot Error: {data}")
                    return None, None
                return data["result"]["bot_invoice_url"], data["result"]["invoice_id"]
        except Exception as e:
            logging.error(f"Network Error: {e}")
            return None, None

async def check_invoice_status(invoice_id):
    # Тут оставь старую функцию check_invoice_status без изменений
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params={"invoice_ids": invoice_id}) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]["status"]
    return "unknown"

# ========== ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    if uid not in users_db:
        users_db[uid] = {"username": message.from_user.username, "date": datetime.now()}
    await message.answer("🏪 *Магазин промокодов*\nВыберите сервис:", parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Выберите сервис:", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("service_"))
async def show_products(callback: CallbackQuery):
    s_map = {"whoosh": "Whoosh", "urent": "Юрент", "yandex_scooter": "Яндекс Самокат", "yandex_taxi": "Яндекс Такси"}
    key = callback.data.split("_", 1)[1]
    name = s_map.get(key, "Сервис")
    await callback.message.edit_text(f"🎫 *{name}*\nВыберите товар:", parse_mode=ParseMode.MARKDOWN, reply_markup=products_menu(name))

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    p_key = callback.data.replace("buy_", "")
    product = PRODUCTS.get(p_key)
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    url, inv_id = await create_crypto_invoice(product["price"], p_key, callback.from_user.id)
    if not url:
        await callback.message.answer("❌ Ошибка платежки. Проверьте токены на Render!")
        return
    
    user_data[callback.from_user.id] = {"invoice_id": inv_id, "product": product}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Оплатить", url=url)],
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data=f"check_{p_key}")]
    ])
    await callback.message.edit_text(f"🛒 *{product['name']}*\nЦена: {product['price']} USDT", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: CallbackQuery):
    uid = callback.from_user.id
    data = user_data.get(uid)
    if not data:
        await callback.answer("❌ Сессия истекла", show_alert=True)
        return
    
    status = await check_invoice_status(data["invoice_id"])
    if status == "paid":
        p = data["product"]
        await callback.message.edit_text(f"✅ Оплачено!\nВаш код для {p['service']}:\n`{p['code']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
        await bot.send_message(ADMIN_ID, f"💰 Продажа: {p['name']} (@{callback.from_user.username})")
        del user_data[uid]
    else:
        await callback.answer("⏳ Оплата не найдена", show_alert=True)

@dp.callback_query(F.data == "admin_panel")
async def admin(callback: CallbackQuery):
    if callback.from_user.id == ADMIN_ID:
        await callback.answer(f"Админ-стата: {len(users_db)} юзеров", show_alert=True)

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    asyncio.create_task(site.start())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
