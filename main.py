import asyncio
import json
import aiohttp
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.enums import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8687270310:AAG6jmf9yjf0iy5L56xuIgXPokQ7-AiufzI"
CRYPTOBOT_TOKEN = "563565:AAYHI6yh4ZskQJHMGEVLVuDUk4H6FhvuYrb"
ADMIN_ID = 6606706488
SUPPORT_CONTACT = "@hdhdjdjggdr"

# Товары (все цены в USDT)
PRODUCTS = {
    # Юрент
    "urent_6":      {"name": "Юрент | 6 поездок",      "price": 3.90,  "service": "Юрент", "code": "URENT6-ABCD"},
    "urent_10":     {"name": "Юрент | 10 поездок",     "price": 4.70,  "service": "Юрент", "code": "URENT10-1234"},
    "urent_week":   {"name": "Юрент | Недельная",      "price": 5.00,  "service": "Юрент", "code": "URENTWEEK-A1B2"},
    "urent_2weeks": {"name": "Юрент | 2 недели",       "price": 6.80,  "service": "Юрент", "code": "URENT2W-XYZZ"},
    
    # Whoosh
    "whoosh_6":     {"name": "Whoosh | 6 поездок",     "price": 3.90,  "service": "Whoosh", "code": "WHOOSH6-QWER"},
    "whoosh_10":    {"name": "Whoosh | 10 поездок",    "price": 4.70,  "service": "Whoosh", "code": "WHOOSH10-ASDF"},
    
    # Яндекс Самокаты (цены на 50% меньше, чем у других)
    "yandex_scooter_6":   {"name": "Яндекс Самокат | 6 поездок",  "price": 1.95,  "service": "Яндекс Самокат", "code": "YNDXSC6-ABCD"},
    "yandex_scooter_10":  {"name": "Яндекс Самокат | 10 поездок", "price": 2.35,  "service": "Яндекс Самокат", "code": "YNDXSC10-EFGH"},
    "yandex_scooter_week": {"name": "Яндекс Самокат | Недельная", "price": 2.50,  "service": "Яндекс Самокат", "code": "YNDXSCWK-1234"},
    
    # Яндекс Такси (3 бесплатные поездки)
    "yandex_taxi_3":  {"name": "Яндекс Такси | 3 бесплатные поездки", "price": 5.00, "service": "Яндекс Такси", "code": "YNDXTAXI-3FREE"},
}

# Хранилища данных
user_data = {}          # Временные данные покупок
users_db = {}           # Все пользователи {user_id: {"username": "...", "first_seen": "..."}}
payments_db = []        # Все оплаты [{"user_id": ..., "product": "...", "amount": ..., "date": "...", "status": "paid"}]

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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def admin_menu():
    buttons = [
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Все оплаты", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== ФУНКЦИИ CRYPTO BOT ==========
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
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]["bot_invoice_url"], data["result"]["invoice_id"]
            return None, None

async def check_invoice_status(invoice_id: int):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {"invoice_ids": invoice_id}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]["status"]
    return "unknown"

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ==========
def register_user(user_id, username):
    """Регистрирует пользователя при первом запуске"""
    if user_id not in users_db:
        users_db[user_id] = {
            "username": username,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return True
    return False

def add_payment(user_id, product_name, amount, status="paid"):
    """Добавляет запись об оплате"""
    payments_db.append({
        "user_id": user_id,
        "username": users_db.get(user_id, {}).get("username", str(user_id)),
        "product": product_name,
        "amount": amount,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    })

# ========== ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    register_user(user_id, username)
    
    text = (
        "🏪 *WhooshShop | ЮрентShop | ЯндексShop*\n\n"
        "Перемещайся по городу так, как хочешь!\n"
        "Быстро, комфортно и с удовольствием.\n\n"
        "Добро пожаловать в наш онлайн магазин промокодов! 🎁\n\n"
        "Доступные сервисы:\n"
        "• Whoosh — скидка до 50%\n"
        "• Юрент — безлимитные поездки\n"
        "• Яндекс Самокат — цены на 50% ниже\n"
        "• Яндекс Такси — 3 бесплатные поездки\n\n"
        "Выберите компанию, чтобы начать 👇"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Выберите компанию:", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    text = (
        "📞 *Поддержка*\n\n"
        f"По вопросам оплаты и получения промокодов пишите: {SUPPORT_CONTACT}\n\n"
        "• Вопросы по активации\n"
        "• Проблемы с оплатой\n"
        "• Не пришёл промокод\n\n"
        "Отвечаем в течение 15 минут."
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def show_products(callback: CallbackQuery):
    service_map = {
        "whoosh": "Whoosh",
        "urent": "Юрент",
        "yandex_scooter": "Яндекс Самокат",
        "yandex_taxi": "Яндекс Такси"
    }
    service_key = callback.data.split("_")[1]
    service_name = service_map.get(service_key, "Сервис")
    
    # Дополнительное описание для Яндекс Такси
    if service_key == "yandex_taxi":
        await callback.message.edit_text(
            f"🚖 *{service_name}*\n\n"
            "🎫 *3 бесплатные поездки*\n"
            "• Действует на любые поездки в пределах города\n"
            "• Максимальная скидка — 500₽ за поездку\n"
            "• Промокод активируется в приложении Яндекс Go\n"
            "• Срок действия — 30 дней после активации\n\n"
            "Выберите нужный промокод:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=products_menu(service_name)
        )
    elif service_key == "yandex_scooter":
        await callback.message.edit_text(
            f"🛴 *{service_name}*\n\n"
            "💰 *Специальная цена! На 50% ниже рыночной*\n"
            "• Безлимитные поездки на электросамокатах\n"
            "• Активация в приложении Яндекс Go\n"
            "• Подходит для любого тарифа\n\n"
            "Выберите нужный промокод:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=products_menu(service_name)
        )
    else:
        await callback.message.edit_text(
            f"💡 *{service_name} промокоды* 💡\n\n"
            "Выберите нужный промокод:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=products_menu(service_name)
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_key = callback.data.split("_")[1]
    product = PRODUCTS.get(product_key)
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    invoice_url, invoice_id = await create_crypto_invoice(product["price"], product_key, callback.from_user.id)
    if not invoice_url:
        await callback.message.answer("❌ Ошибка создания счёта. Попробуйте позже.")
        return
    
    user_data[callback.from_user.id] = {
        "invoice_id": invoice_id,
        "product_key": product_key,
        "product": product
    }
    
    # Разные инструкции для разных сервисов
    if product["service"] == "Яндекс Такси":
        instruction = (
            "📌 *Инструкция для Яндекс Такси:*\n"
            "1. Откройте приложение Яндекс Go\n"
            "2. Нажмите на профиль → «Промокоды»\n"
            "3. Введите промокод\n"
            "4. При заказе такси скидка применится автоматически"
        )
    elif product["service"] == "Яндекс Самокат":
        instruction = (
            "📌 *Инструкция для Яндекс Самокат:*\n"
            "1. Откройте приложение Яндекс Go\n"
            "2. Раздел «Самокаты» → «Промокоды»\n"
            "3. Введите промокод\n"
            "4. Начинайте поездку со скидкой 50%"
        )
    else:
        instruction = (
            f"📌 *Инструкция для {product['service']}:*\n"
            "1. Зайдите в приложение\n"
            "2. Раздел «Промокоды» → «Ввести промокод»\n"
            "3. Активируйте и пользуйтесь!"
        )
    
    text = (
        f"🛒 *{product['name']}*\n"
        f"💰 Цена: {product['price']} USDT (TRC20)\n\n"
        f"🔗 [Оплатить через Crypto Bot]({invoice_url})\n\n"
        f"{instruction}\n\n"
        f"✅ После оплаты нажмите кнопку ниже 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data=f"check_{product_key}")]
    ])
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await callback.answer("❌ Не найден активный счёт. Начните покупку заново.", show_alert=True)
        return
    
    status = await check_invoice_status(data["invoice_id"])
    
    if status == "paid":
        product = data["product"]
        promo_code = product["code"]
        
        # Сохраняем оплату в базу
        add_payment(user_id, product["name"], product["price"])
        
        # Разные инструкции после получения кода
        if product["service"] == "Яндекс Такси":
            after_text = (
                f"🎫 Ваш промокод для *{product['service']}*:\n`{promo_code}`\n\n"
                f"🔥 Промокод даёт 3 бесплатные поездки!\n"
                f"• Максимальная скидка: 500₽ за поездку\n"
                f"• Активируйте в приложении Яндекс Go\n\n"
                f"Спасибо за покупку! ❤️"
            )
        elif product["service"] == "Яндекс Самокат":
            after_text = (
                f"🎫 Ваш промокод для *{product['service']}*:\n`{promo_code}`\n\n"
                f"🛴 Экономьте 50% на каждой поездке!\n"
                f"• Активируйте в приложении Яндекс Go\n"
                f"• Действует на все самокаты\n\n"
                f"Спасибо за покупку! ❤️"
            )
        else:
            after_text = (
                f"🎫 Ваш промокод для *{product['service']}*:\n`{promo_code}`\n\n"
                f"📌 Инструкция:\n"
                f"1. Зайдите в приложение {product['service']}\n"
                f"2. Раздел «Промокоды» → «Ввести промокод»\n"
                f"3. Активируйте и пользуйтесь!\n\n"
                f"💬 Вопросы: {SUPPORT_CONTACT}"
            )
        
        text = (
            f"✅ *Оплата подтверждена!*\n\n"
            f"{after_text}"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
        del user_data[user_id]
        
        # Уведомление админу
        await bot.send_message(
            ADMIN_ID,
            f"✅ *НОВАЯ ОПЛАТА!*\n\n"
            f"👤 Пользователь: @{callback.from_user.username or user_id}\n"
            f"🛒 Товар: {product['name']}\n"
            f"💰 Сумма: {product['price']} USDT\n"
            f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    elif status == "active":
        await callback.answer("⏳ Платёж ещё не получен. Подождите 2-3 минуты и попробуйте снова.", show_alert=True)
    else:
        await callback.answer("❌ Платёж не найден или истёк. Создайте новый заказ через /start", show_alert=True)
    
    await callback.answer()

# ========== АДМИН-ПАНЕЛЬ ==========
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа к админ-панели", show_alert=True)
        return
    await callback.message.edit_text("🔐 *Админ панель*\n\nВыберите действие:", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    if not users_db:
        await callback.message.answer("📭 Пока нет пользователей")
        return
    
    text = "👥 *Список пользователей:*\n\n"
    for user_id, info in users_db.items():
        text += f"• @{info['username']} | ID: {user_id} | Первое посещение: {info['first_seen']}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "...\n\nСлишком много пользователей"
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data == "admin_payments")
async def admin_payments(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    if not payments_db:
        await callback.message.answer("📭 Пока нет оплат")
        return
    
    text = "💰 *Список оплат:*\n\n"
    total = 0
    for p in payments_db[-50:]:
        text += f"• @{p['username']} | {p['product']} | {p['amount']} USDT | {p['date']}\n"
        total += p["amount"]
    
    text += f"\n📊 *Общая выручка:* {total} USDT"
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    total_users = len(users_db)
    total_payments = len(payments_db)
    total_revenue = sum(p["amount"] for p in payments_db)
    
    # Статистика по товарам
    product_stats = {}
    for p in payments_db:
        product_stats[p["product"]] = product_stats.get(p["product"], 0) + 1
    
    text = "📊 *Статистика:*\n\n"
    text += f"👥 Всего пользователей: {total_users}\n"
    text += f"💰 Всего оплат: {total_payments}\n"
    text += f"💵 Общая выручка: {total_revenue} USDT\n\n"
    text += "📈 *Популярность товаров:*\n"
    for product, count in product_stats.items():
        text += f"• {product}: {count} шт.\n"
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
