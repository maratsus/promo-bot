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

# ========== 1. КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_ID = 6606706488
SUPPORT_CONTACT = "@hdhdjdjggdr"

# Базы данных в памяти
users_db = {}
payments_db = []
user_data = {}

# Список товаров
PRODUCTS = {
    "urent_6":      {"name": "Юрент | 6 поездок",      "price": 3.90,  "service": "Юрент", "code": "URENT6-CODE-1"},
    "urent_10":     {"name": "Юрент | 10 поездок",     "price": 4.70,  "service": "Юрент", "code": "URENT10-CODE-2"},
    "whoosh_6":     {"name": "Whoosh | 6 поездок",     "price": 3.90,  "service": "Whoosh", "code": "WHOOSH6-CODE-3"},
    "yandex_sc6":   {"name": "Яндекс | 6 поездок",      "price": 1.95,  "service": "Яндекс Самокат", "code": "YNDX6-CODE-4"},
    "yandex_taxi3": {"name": "Яндекс Такси | 3 поезда", "price": 5.00,  "service": "Яндекс Такси", "code": "TAXI3-CODE-5"},
}

# ========== 2. ИНИЦИАЛИЗАЦИЯ БОТА (ВАЖНО: Порядок!) ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== 3. КЛАВИАТУРЫ ==========
def main_menu():
    buttons = [
        [InlineKeyboardButton(text="🛴 Whoosh", callback_data="service_whoosh")],
        [InlineKeyboardButton(text="🛴 Юрент", callback_data="service_urent")],
        [InlineKeyboardButton(text="🛴 Яндекс Самокат", callback_data="service_yandex_scooter")],
        [InlineKeyboardButton(text="🚖 Яндекс Такси", callback_data="service_yandex_taxi")],
        [InlineKeyboardButton(text="🎁 ПОЛУЧИТЬ БЕСПЛАТНО", callback_data="free_promo")],
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

# ========== 4. ПЛАТЕЖИ ==========
async def create_crypto_invoice(amount_usdt, product_key, user_id):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    bot_url = "https://t.me/whoosho_bot" 

    payload = {
        "asset": "USDT", "amount": str(amount_usdt),
        "description": PRODUCTS[product_key]["name"],
        "paid_btn_name": "viewItem",
        "paid_btn_url": bot_url,
        "payload": json.dumps({"product": product_key, "user_id": user_id})
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"): return None, None
                return data["result"]["bot_invoice_url"], data["result"]["invoice_id"]
        except: return None, None

async def check_invoice_status(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params={"invoice_ids": invoice_id}) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]["status"]
    return "unknown"

# ========== 5. ОБРАБОТЧИКИ ==========

@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    if uid not in users_db:
        users_db[uid] = {"username": message.from_user.username, "date": datetime.now()}
    await message.answer("🏪 *WhooshShop | ЮрентShop | ЯндексShop*\n\nВыберите компанию 👇", parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Выберите компанию 👇", reply_markup=main_menu())

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    await callback.message.edit_text(f"🆘 *Служба поддержки*\n\nПишите администратору: {SUPPORT_CONTACT}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

@dp.callback_query(F.data == "free_promo")
async def free_promo_handler(callback: CallbackQuery):
    text = (
        "🔥 *АКЦИЯ: КАТАЙСЯ ЗА ОТЗЫВЫ В TIKTOK!*\n\n"
        "1️⃣ Оставь коммент: «Лучший бот с промокодами 👉 @whoosho_bot» под видео в ТТ.\n"
        "2️⃣ Сделай скриншоты (нужно 35 штук).\n"
        f"3️⃣ Скидывай сюда — {SUPPORT_CONTACT}\n\n"
        "🎁 *Награда:* 1 любой промокод бесплатно!"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

@dp.callback_query(F.data == "admin_panel")
async def admin_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(f"🔐 *ADMIN*\nЮзеров: {len(users_db)}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

@dp.callback_query(F.data.startswith("service_"))
async def show_products(callback: CallbackQuery):
    s_map = {"whoosh": "Whoosh", "urent": "Юрент", "yandex_scooter": "Яндекс Самокат", "yandex_taxi": "Яндекс Такси"}
    key = callback.data.split("_", 1)[1]
    name = s_map.get(key, "Сервис")
    await callback.message.edit_text(f"🎫 *Вы выбрали {name}*\nВыберите промокод:", parse_mode=ParseMode.MARKDOWN, reply_markup=products_menu(name))

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    p_key = callback.data.replace("buy_", "")
    product = PRODUCTS.get(p_key)
    url, inv_id = await create_crypto_invoice(product["price"], p_key, callback.from_user.id)
    if not url:
        await callback.answer("❌ Ошибка оплаты", show_alert=True)
        return
    user_data[callback.from_user.id] = {"invoice_id": inv_id, "product": product}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Оплатить", url=url)],
        [InlineKeyboardButton(text="✅ ПРОВЕРИТЬ ОПЛАТУ", callback_data=f"check_{p_key}")]
    ])
    await callback.message.edit_text(f"🛒 {product['name']}\nЦена: {product['price']} USDT", reply_markup=kb)

@dp.callback_query(F.data.startswith("check_"))
async def check_pay(callback: CallbackQuery):
    data = user_data.get(callback.from_user.id)
    if not data: return
    status = await check_invoice_status(data["invoice_id"])
    if status == "paid":
        p = data["product"]
        await callback.message.edit_text(f"✅ Оплачено!\nВаш код: `{p['code']}`", parse_mode=ParseMode.MARKDOWN)
        del user_data[callback.from_user.id]
    else:
        await callback.answer("⏳ Оплата не найдена", show_alert=True)

# ========== 6. ЗАПУСК ==========
async def handle(request): return web.Response(text="Alive")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    asyncio.create_task(site.start())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
