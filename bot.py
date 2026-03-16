import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import asyncio

# Берем токен из переменных окружения (настройка в Railway)
TOKEN = os.environ.get('BOT_TOKEN')

TOKEN = "8772705807:AAGrh-vS3tI1Pjk1fa-ScBCvifcCfqfh_hU"

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SHOPS = {
    "aw_store": {
        "name": "Apple World",
        "url": "https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/",
        "price": None
    },
    "ipoint": {
        "name": "iPoint Perm",
        "url": "https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim",
        "price": None
    },
    "swype": {
        "name": "Swype",
        "url": "https://swype59.ru/product/iphone-17-pro-max-512-gb-silver",
        "price": None
    }
}

PRODUCT_NAME = "iPhone 17 Pro Max 512GB Silver"

def parse_price_aw_store(url):
    """Парсинг цены с Apple World"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price_element = soup.find('span', {'class': 'price'})
        if not price_element:
            price_element = soup.find('div', {'class': 'product-price'})
        if not price_element:
            price_element = soup.find('span', {'itemprop': 'price'})
        
        if price_element:
            price_text = price_element.text.strip()
            # Убираем все кроме цифр (оставляем только числа)
            price = int(''.join(filter(str.isdigit, price_text)))
            logger.info(f"Apple World цена: {price}")
            return price
        else:
            # Пробуем найти цену в тексте страницы
            price_pattern = re.compile(r'(\d+[\s]*\d*)[\s]*руб')
            match = price_pattern.search(response.text)
            if match:
                price_text = match.group(1).replace(' ', '')
                return int(price_text)
    except Exception as e:
        logger.error(f"Ошибка парсинга Apple World: {e}")
    return None

def parse_price_ipoint(url):
    """Парсинг цены с iPoint Perm"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем цену - на сайте она выделена жирным
        price_element = soup.find('span', {'class': 'price'})
        if not price_element:
            price_element = soup.find('div', {'class': 'product-price'})
        if not price_element:
            # Ищем по атрибуту content
            price_element = soup.find('meta', {'itemprop': 'price'})
            if price_element:
                return int(float(price_element.get('content', 0)))
        
        if price_element:
            price_text = price_element.text.strip()
            price = int(''.join(filter(str.isdigit, price_text)))
            logger.info(f"iPoint цена: {price}")
            return price
    except Exception as e:
        logger.error(f"Ошибка парсинга iPoint: {e}")
    return None

def parse_price_swype(url):
    """Парсинг цены с Swype"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # На Swype цена может быть в формате "132 990 ₽ 135 990 ₽" (со скидкой)
        # Ищем все возможные места с ценой
        
        # Сначала ищем элемент с акционной ценой
        price_element = soup.find('span', {'class': 'price'})
        if price_element:
            price_text = price_element.text.strip()
            # Берем первую цену (обычно это акционная)
            prices = re.findall(r'(\d+[\s]*\d*)', price_text)
            if prices:
                price = int(prices[0].replace(' ', ''))
                logger.info(f"Swype цена (акционная): {price}")
                return price
        
        # Если не нашли, ищем в тексте
        price_pattern = re.compile(r'(\d+[\s]*\d*)[\s]*[₽руб]')
        match = price_pattern.search(response.text)
        if match:
            price_text = match.group(1).replace(' ', '')
            return int(price_text)
            
    except Exception as e:
        logger.error(f"Ошибка парсинга Swype: {e}")
    return None

async def check_prices():
    """Проверяет цены во всех магазинах параллельно"""
    results = []
    
    # Создаем задачи для параллельного парсинга
    tasks = [
        asyncio.to_thread(parse_price_aw_store, SHOPS["aw_store"]["url"]),
        asyncio.to_thread(parse_price_ipoint, SHOPS["ipoint"]["url"]),
        asyncio.to_thread(parse_price_swype, SHOPS["swype"]["url"])
    ]
    
    # Запускаем все задачи параллельно
    prices = await asyncio.gather(*tasks)
    
    # Собираем результаты
    shop_keys = list(SHOPS.keys())
    for i, price in enumerate(prices):
        if price:
            shop_key = shop_keys[i]
            results.append({
                'shop': SHOPS[shop_key]["name"],
                'price': price,
                'url': SHOPS[shop_key]["url"],
                'emoji': SHOPS[shop_key]["emoji"]
            })
    
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("💰 УЗНАТЬ МИНИМАЛЬНУЮ ЦЕНУ", callback_data='price')],
        [InlineKeyboardButton("🔄 ОБНОВИТЬ ЦЕНЫ", callback_data='refresh')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет! Я отслеживаю цены на **{PRODUCT_NAME}**\n\n"
        "📊 Проверяю цены в магазинах:\n"
        f"{SHOPS['aw_store']['emoji']} {SHOPS['aw_store']['name']}\n"
        f"{SHOPS['ipoint']['emoji']} {SHOPS['ipoint']['name']}\n"
        f"{SHOPS['swype']['emoji']} {SHOPS['swype']['name']}\n\n"
        "🔍 Нажми кнопку ниже, чтобы найти лучшую цену!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'price':
        await query.edit_message_text("🔍 Проверяю цены во всех магазинах...\nЭто займет несколько секунд.")
        
        # Получаем актуальные цены
        prices = await check_prices()
        
        if prices:
            # Находим минимальную цену
            min_price = min(prices, key=lambda x: x['price'])
            
            # Формируем сообщение
            message = f"📱 **{PRODUCT_NAME}**\n\n"
            message += f"🏆 **МИНИМАЛЬНАЯ ЦЕНА:**\n"
            message += f"{min_price['emoji']} **{min_price['shop']}**\n"
            message += f"💰 **{min_price['price']:,} руб.**\n".replace(',', ' ')
            message += f"🔗 [Перейти в магазин]({min_price['url']})\n\n"
            
            message += "📊 **Все цены:**\n"
            
            # Сортируем все цены по возрастанию
            sorted_prices = sorted(prices, key=lambda x: x['price'])
            for p in sorted_prices:
                if p['price'] == min_price['price']:
                    message += f"✅ {p['shop']}: {p['price']:,} руб. (лучшая цена)\n".replace(',', ' ')
                else:
                    diff = p['price'] - min_price['price']
                    message += f"• {p['shop']}: {p['price']:,} руб. (дороже на {diff:,} руб.)\n".replace(',', ' ')
            
            message += f"\n🕐 Обновлено: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            
            # Кнопки после результата
            keyboard = [
                [InlineKeyboardButton("🔄 ПРОВЕРИТЬ СНОВА", callback_data='price')],
                [InlineKeyboardButton("🏠 ГЛАВНОЕ МЕНЮ", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            # Если не удалось получить цены
            keyboard = [
                [InlineKeyboardButton("🔄 ПОПРОБОВАТЬ СНОВА", callback_data='price')],
                [InlineKeyboardButton("🏠 ГЛАВНОЕ МЕНЮ", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ Не удалось получить цены. Возможно:\n"
                "• Сайты временно недоступны\n"
                "• Изменилась структура страниц\n"
                "• Нет соединения с интернетом\n\n"
                "Попробуйте позже.",
                reply_markup=reply_markup
            )
    
    elif query.data == 'refresh':
        await query.edit_message_text("🔄 Обновляю цены...")
        
        # Просто показываем цены заново
        prices = await check_prices()
        
        if prices:
            min_price = min(prices, key=lambda x: x['price'])
            
            message = f"📱 **{PRODUCT_NAME}**\n\n"
            message += f"🏆 **МИНИМАЛЬНАЯ ЦЕНА:**\n"
            message += f"{min_price['emoji']} **{min_price['shop']}**\n"
            message += f"💰 **{min_price['price']:,} руб.**\n".replace(',', ' ')
            message += f"🔗 [Перейти в магазин]({min_price['url']})\n\n"
            
            message += "📊 **Все цены:**\n"
            
            sorted_prices = sorted(prices, key=lambda x: x['price'])
            for p in sorted_prices:
                if p['price'] == min_price['price']:
                    message += f"✅ {p['shop']}: {p['price']:,} руб. (лучшая цена)\n".replace(',', ' ')
                else:
                    diff = p['price'] - min_price['price']
                    message += f"• {p['shop']}: {p['price']:,} руб. (дороже на {diff:,} руб.)\n".replace(',', ' ')
            
            message += f"\n🕐 Обновлено: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            
            keyboard = [
                [InlineKeyboardButton("🔄 ПРОВЕРИТЬ СНОВА", callback_data='price')],
                [InlineKeyboardButton("🏠 ГЛАВНОЕ МЕНЮ", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    
    elif query.data == 'back':
        # Возвращаемся в главное меню
        keyboard = [
            [InlineKeyboardButton("💰 УЗНАТЬ МИНИМАЛЬНУЮ ЦЕНУ", callback_data='price')],
            [InlineKeyboardButton("🔄 ОБНОВИТЬ ЦЕНЫ", callback_data='refresh')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👋 **Главное меню**\n\n"
            f"Отслеживаю цены на **{PRODUCT_NAME}**\n\n"
            "📊 Проверяю цены в магазинах:\n"
            f"{SHOPS['aw_store']['emoji']} {SHOPS['aw_store']['name']}\n"
            f"{SHOPS['ipoint']['emoji']} {SHOPS['ipoint']['name']}\n"
            f"{SHOPS['swype']['emoji']} {SHOPS['swype']['name']}\n\n"
            "🔍 Нажми кнопку для поиска лучшей цены!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = f"""
📖 **Как пользоваться ботом:**

1️⃣ Нажми кнопку **"УЗНАТЬ МИНИМАЛЬНУЮ ЦЕНУ"**
2️⃣ Бот проверит цены во всех магазинах
3️⃣ Получишь ссылку на магазин с лучшей ценой

**Магазины для проверки:**
{SHOPS['aw_store']['emoji']} {SHOPS['aw_store']['name']}
{SHOPS['ipoint']['emoji']} {SHOPS['ipoint']['name']}
{SHOPS['swype']['emoji']} {SHOPS['swype']['name']}

**Товар:** {PRODUCT_NAME}

**Команды:**
/start - главное меню
/help - эта справка
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    print("🤖 Бот для iPhone 17 Pro Max запущен!")
    print("Проверяемые магазины:")
    print(f"  - {SHOPS['aw_store']['name']}")
    print(f"  - {SHOPS['ipoint']['name']}")
    print(f"  - {SHOPS['swype']['name']}")
    application.run_polling()

if __name__ == '__main__':
    main()
