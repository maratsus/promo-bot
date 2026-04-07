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

# ========== КОНФИГУРАЦИЯ (ОБНОВЛЕНО) ==========
ADMIN_ID = 6606706488
SUPPORT_CONTACT = "@hdhdjdjggdr"

# ========== КЛАВИАТУРА МЕНЮ ==========
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

# ========== НОВЫЕ ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    text = (
        "🆘 *Служба поддержки*\n\n"
        f"Возникли вопросы? Пишите нашему менеджеру: {SUPPORT_CONTACT}\n"
        "Поможем с оплатой или заменой товара в течение 15-30 минут."
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

@dp.callback_query(F.data == "free_promo")
async def free_promo_handler(callback: CallbackQuery):
    text = (
        "🔥 *АКЦИЯ: КАТАЙСЯ ЗА ОТЗЫВЫ В TIKTOK!*\n\n"
        "Мы раздаем бесплатные промокоды за актив в ТТ! Всё просто:\n\n"
        "1️⃣ Найди видео про самокаты или такси в TikTok.\n"
        "2️⃣ Оставь комментарий: «Лучший бот с промокодами 👉 @whoosho_bot» (или похожий по смыслу).\n"
        "3️⃣ Сделай скриншот каждого своего комментария.\n\n"
        "💰 *Условие:* Собери **35 скриншотов** с разных видео.\n"
        f"📩 *Куда скидывать:* Скрины отправляй сюда — {SUPPORT_CONTACT}\n\n"
        "🎁 *Награда:* После проверки ты получишь **1 любой промокод** на выбор бесплатно!"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

@dp.callback_query(F.data == "admin_panel")
async def admin_handler(callback: CallbackQuery):
    # Проверка на твой ID
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ только для владельца!", show_alert=True)
        return
    
    text = (
        "🔐 *ADMIN PANEL*\n\n"
        f"Юзеров в базе: {len(users_db)}\n"
        "Статус системы: Работает штатно ✅"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())


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

# ========== ОБРАБОТЧИКИ (ФИНАЛ) ==========

@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    # Сохраняем пользователя в базу (в памяти)
    if uid not in users_db:
        users_db[uid] = {
            "username": message.from_user.username or "Unknown",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    await message.answer(
        "🏪 *WhooshShop | ЮрентShop | ЯндексShop*\n\nВыберите компанию 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Выберите компанию 👇", reply_markup=main_menu())

# ОБРАБОТЧИК ПОДДЕРЖКИ
@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    text = (
        "🆘 *Служба поддержки*\n\n"
        f"Если у вас возникли проблемы с оплатой или промокодом, пишите администратору: {SUPPORT_CONTACT}\n\n"
        "График работы: 10:00 - 22:00 МСК"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

# ОБРАБОТЧИК АДМИН-ПАНЕЛИ
@dp.callback_query(F.data == "admin_panel")
async def admin_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав администратора!", show_alert=True)
        return
    
    total_users = len(users_db)
    total_sales = len(payments_db)
    total_money = sum(p["amount"] for p in payments_db)
    
    text = (
        "🔐 *Панель администратора*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Успешных продаж: {total_sales}\n"
        f"💵 Общая выручка: {total_money} USDT"
    )
    
    # Кнопки внутри админки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список заказов", callback_data="admin_orders")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if not payments_db:
        await callback.answer("Заказов пока нет", show_alert=True)
        return
    
    report = "*Последние 10 заказов:*\n\n"
    for p in payments_db[-10:]:
        report += f"▫️ {p['date']} | @{p['username']} | {p['product']} | {p['amount']} USDT\n"
    
    await callback.message.edit_text(report, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())

# Обработчик выбора сервиса (уже был, но проверь наличие)
@dp.callback_query(F.data.startswith("service_"))
async def show_products(callback: CallbackQuery):
    s_map = {
        "whoosh": "Whoosh", 
        "urent": "Юрент", 
        "yandex_scooter": "Яндекс Самокат", 
        "yandex_taxi": "Яндекс Такси"
    }
    key = callback.data.split("_", 1)[1]
    name = s_map.get(key, "Сервис")
    await callback.message.edit_text(
        f"🎫 *Вы выбрали {name}*\nВыберите нужный промокод:", 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=products_menu(name)
    )

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
