import os
import logging
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sys
import traceback

# Настройка логирования в файл и консоль
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Проверка токена при запуске
TOKEN = os.environ.get('8772705807:AAGrh-vS3tI1Pjk1fa-ScBCvifcCfqfh_hU')
if not TOKEN:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    logger.error("Добавьте BOT_TOKEN в Variables на Railway")
    # Не выходим, а ждем, но логируем ошибку

PRODUCT_NAME = "iPhone 17 Pro Max 512GB Silver"

# Данные о магазинах
SHOPS = {
    "aw_store": {
        "name": "🍏 Apple World",
        "url": "https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/",
        "emoji": "🏪",
        "parser": "aw_store"
    },
    "ipoint": {
        "name": "📱 iPoint Perm",
        "url": "https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim",
        "emoji": "📍",
        "parser": "ipoint"
    },
    "swype": {
        "name": "⚡️ Swype",
        "url": "https://swype59.ru/product/iphone-17-pro-max-512-gb-silver",
        "emoji": "🔄",
        "parser": "swype"
    }
}

def fetch_url_with_retry(url, timeout=10, retries=2):
    """Загрузка URL с повторными попытками"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут при загрузке {url}, попытка {attempt + 1}/{retries}")
            if attempt == retries - 1:
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка при загрузке {url}: {e}")
            if attempt == retries - 1:
                return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при загрузке {url}: {e}")
            return None
        
        # Пауза перед повторной попыткой
        asyncio.sleep(1)
    
    return None

def extract_price_from_text(text):
    """Извлекает цену из текста"""
    if not text:
        return None
    
    # Ищем число с пробелами или без
    patterns = [
        r'(\d+[ ]?\d*)[\s]*[₽руб]',  # 135 990 руб
        r'(\d+[ ]?\d*)[\s]*₽',        # 135 990 ₽
        r'(\d+[ ]?\d*)',               # 135990
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            price_text = match.group(1).replace(' ', '')
            try:
                return int(price_text)
            except ValueError:
                continue
    
    return None

def parse_price_aw_store(url):
    """Парсинг цены с Apple World"""
    try:
        html = fetch_url_with_retry(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Поиск по разным селекторам
        selectors = [
            {'name': 'span', 'attrs': {'class': 'price'}},
            {'name': 'div', 'attrs': {'class': 'product-price'}},
            {'name': 'span', 'attrs': {'itemprop': 'price'}},
            {'name': 'meta', 'attrs': {'property': 'product:price:amount'}},
        ]
        
        for selector in selectors:
            try:
                element = soup.find(selector['name'], selector['attrs'])
                if element:
                    if selector['name'] == 'meta':
                        content = element.get('content', '')
                        if content:
                            return int(float(content))
                    else:
                        price = extract_price_from_text(element.text)
                        if price:
                            logger.info(f"Apple World цена: {price}")
                            return price
            except Exception as e:
                logger.debug(f"Ошибка с селектором {selector}: {e}")
                continue
        
        # Если не нашли через селекторы, ищем в тексте
        price = extract_price_from_text(html)
        if price:
            logger.info(f"Apple World цена (из текста): {price}")
            return price
            
    except Exception as e:
        logger.error(f"Ошибка парсинга Apple World: {e}")
    
    return None

def parse_price_ipoint(url):
    """Парсинг цены с iPoint Perm"""
    try:
        html = fetch_url_with_retry(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Пробуем разные селекторы
        price_element = soup.find('span', {'class': 'price'})
        if not price_element:
            price_element = soup.find('div', {'class': 'product-price'})
        if not price_element:
            price_element = soup.find('meta', {'itemprop': 'price'})
        
        if price_element:
            if price_element.name == 'meta':
                content = price_element.get('content', '')
                if content:
                    return int(float(content))
            else:
                price = extract_price_from_text(price_element.text)
                if price:
                    logger.info(f"iPoint цена: {price}")
                    return price
        
        # Ищем в JSON-LD
        script = soup.find('script', {'type': 'application/ld+json'})
        if script:
            import json
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'offers' in data:
                        if 'price' in data['offers']:
                            return int(float(data['offers']['price']))
            except:
                pass
        
    except Exception as e:
        logger.error(f"Ошибка парсинга iPoint: {e}")
    
    return None

def parse_price_swype(url):
    """Парсинг цены с Swype"""
    try:
        html = fetch_url_with_retry(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем акционную цену
        price_element = soup.find('span', {'class': 'price'})
        if price_element:
            price = extract_price_from_text(price_element.text)
            if price:
                logger.info(f"Swype цена: {price}")
                return price
        
        # Ищем в тексте
        price = extract_price_from_text(html)
        if price:
            logger.info(f"Swype цена (из текста): {price}")
            return price
        
    except Exception as e:
        logger.error(f"Ошибка парсинга Swype: {e}")
    
    return None

async def check_prices():
    """Проверка цен во всех магазинах"""
    results = []
    parsers = {
        "aw_store": parse_price_aw_store,
        "ipoint": parse_price_ipoint,
        "swype": parse_price_swype
    }
    
    for shop_id, shop_data in SHOPS.items():
        try:
            parser = parsers.get(shop_data["parser"])
            if parser:
                # Запускаем парсер с таймаутом
                price = await asyncio.wait_for(
                    asyncio.to_thread(parser, shop_data["url"]),
                    timeout=20.0
                )
                
                if price and price > 0:
                    results.append({
                        'shop': shop_data["name"],
                        'price': price,
                        'url': shop_data["url"],
                        'emoji': shop_data["emoji"]
                    })
                else:
                    logger.warning(f"Не удалось получить цену для {shop_data['name']}")
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при парсинге {shop_data['name']}")
        except Exception as e:
            logger.error(f"Ошибка при парсинге {shop_data['name']}: {e}")
    
    return results

def format_price(price):
    """Форматирование цены"""
    return f"{price:,}".replace(',', ' ')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    if not TOKEN:
        await update.message.reply_text("❌ Бот не настроен: отсутствует токен")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 УЗНАТЬ ЦЕНУ", callback_data='price')],
        [InlineKeyboardButton("🔄 ОБНОВИТЬ", callback_data='refresh')]
    ]
    
    await update.message.reply_text(
        f"👋 Отслеживаю цены на **{PRODUCT_NAME}**\n\n"
        "Проверяю магазины:\n" +
        "\n".join([f"{s['emoji']} {s['name']}" for s in SHOPS.values()]) +
        "\n\nНажми кнопку для поиска лучшей цены!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data in ['price', 'refresh']:
        await query.edit_message_text("🔍 Проверяю цены...")
        
        try:
            prices = await check_prices()
            
            if prices:
                min_price = min(prices, key=lambda x: x['price'])
                
                message = f"📱 **{PRODUCT_NAME}**\n\n"
                message += f"🏆 **Лучшая цена:**\n"
                message += f"{min_price['emoji']} **{min_price['shop']}**\n"
                message += f"💰 **{format_price(min_price['price'])} руб.**\n"
                message += f"🔗 [Ссылка]({min_price['url']})\n\n"
                
                message += "📊 **Все цены:**\n"
                
                sorted_prices = sorted(prices, key=lambda x: x['price'])
                for p in sorted_prices:
                    if p['price'] == min_price['price']:
                        message += f"✅ {p['shop']}: {format_price(p['price'])} руб.\n"
                    else:
                        message += f"• {p['shop']}: {format_price(p['price'])} руб.\n"
                
                message += f"\n🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
                
                keyboard = [
                    [InlineKeyboardButton("🔄 ПРОВЕРИТЬ СНОВА", callback_data='price')],
                    [InlineKeyboardButton("🏠 МЕНЮ", callback_data='back')]
                ]
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(
                    "❌ Не удалось получить цены. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 МЕНЮ", callback_data='back')
                    ]])
                )
        except Exception as e:
            logger.error(f"Ошибка: {e}\n{traceback.format_exc()}")
            await query.edit_message_text(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 МЕНЮ", callback_data='back')
                ]])
            )
    
    elif query.data == 'back':
        keyboard = [
            [InlineKeyboardButton("💰 УЗНАТЬ ЦЕНУ", callback_data='price')],
            [InlineKeyboardButton("🔄 ОБНОВИТЬ", callback_data='refresh')]
        ]
        
        await query.edit_message_text(
            f"👋 **Главное меню**\n\nОтслеживаю цены на **{PRODUCT_NAME}**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

def main():
    """Запуск бота"""
    if not TOKEN:
        logger.error("Бот не может запуститься: нет токена!")
        logger.error("Добавьте BOT_TOKEN в Variables на Railway")
        # Ждем 30 секунд и перезапускаемся (Railway перезапустит контейнер)
        import time
        time.sleep(30)
        return
    
    try:
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        logger.info("✅ Бот успешно запущен!")
        application.run_polling()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
        # Ждем и перезапускаемся
        import time
        time.sleep(30)

if __name__ == '__main__':
    main()
