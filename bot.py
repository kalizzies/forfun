import os
import logging
import requests
import re
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes


TOKEN = os.environ.get('BOT_TOKEN')


# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


Product_name = "iPhone 17 Pro Max 512GB Silver Esim"


Shops = {
    "AppleWorld": {
        "name": "AppleWorld",
        "url": "https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/"
    },
    "Swype": {
        "name": "Swype",
        "url": "https://swype59.ru/product/iphone-17-pro-max-512-gb-silver"
    },
    "iPoint": {
        "name": "iPoint",
        "url": "https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim"
    }
}


headers = {
    "User-Agent": "Mozilla/5.0"
}


def extract_price(text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        return int("".join(numbers))
    return None


def parse_from_appleworld():
    url = Shops["AppleWorld"]["url"]
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    price = soup.select_one('.price_value')
    if price:
        return extract_price(price.text)
    return None


def parse_from_swype():
    url = Shops["Swype"]["url"]
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    price = soup.select_one('.product__price')
    if price:
        return extract_price(price.text)
    return None


def parse_from_ipoint():
    url = Shops["iPoint"]["url"]
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    price = soup.select_one('.price')
    if price:
        return extract_price(price.text)
    return None


async def check_prices():
    results = []
    tasks = [
        asyncio.to_thread(parse_from_appleworld),
        asyncio.to_thread(parse_from_swype),
        asyncio.to_thread(parse_from_ipoint)
    ]
    prices = await asyncio.gather(*tasks)
    
    shop_keys = list(Shops.keys())
    for i, price in enumerate(prices):
        if price:
            results.append({
                'shop': Shops[shop_keys[i]]["name"],
                'price': price,
                'url': Shops[shop_keys[i]]["url"],
            })
            logger.info(f"{Shops[shop_keys[i]]['name']}: {price} руб.")
    
    return results


def format_price(price):
    """Форматирует цену с пробелами (1000000 -> 1 000 000)"""
    return f"{price:,}".replace(',', ' ')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(" УЗНАТЬ ЦЕНУ", callback_data='price')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Привет! Я отслеживаю цены на **{Product_name}**\n\n"
        "Нажми кнопку ниже, чтобы узнать лучшую цену:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'price':
        await query.edit_message_text("🔍 Проверяю цены в магазинах...")
        
        prices = await check_prices()

        if prices:
            # Сохраняем результаты в контекст, чтобы потом показать детали
            context.user_data['last_prices'] = prices
            context.user_data['last_search_time'] = datetime.now()
            
            # Находим лучшую цену
            min_price = min(prices, key=lambda x: x['price'])
            
            # Форматируем сообщение
            message = f"**{Product_name}**\n\n"
            message += f"**ЛУЧШАЯ ЦЕНА:**\n"
            message += f"**{format_price(min_price['price'])} руб.**\n"
            message += f" Магазин: {min_price['shop']}\n"
            message += f"🔗 [Ссылка на товар]({min_price['url']})\n\n"
            
            message += "**Все найденные цены:**\n"
            
            # Сортируем цены от меньшей к большей
            sorted_prices = sorted(prices, key=lambda x: x['price'])
            for p in sorted_prices:
                if p['price'] == min_price['price']:
                    message += f"✅ {p['shop']}: {format_price(p['price'])} руб. (лучшая)\n"
                else:
                    diff = p['price'] - min_price['price']
                    message += f"• {p['shop']}: {format_price(p['price'])} руб. (+{format_price(diff)})\n"
            
            # Добавляем время проверки
            now = datetime.now().strftime("%H:%M %d.%m.%Y")
            message += f"\n🕐 Проверено: {now}"
            
            # Создаем клавиатуру с кнопками
            keyboard = [
                [InlineKeyboardButton("🔄 ПРОВЕРИТЬ СНОВА", callback_data='price')],
                [InlineKeyboardButton("🔍 КАК НАШЛИ ЦЕНУ", callback_data='how_found')],
                [InlineKeyboardButton("◀️ НАЗАД", callback_data='back_to_start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔄 ПОПРОБОВАТЬ СНОВА", callback_data='price')],
                [InlineKeyboardButton("◀️ НАЗАД", callback_data='back_to_start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ Не удалось получить цены. Попробуйте позже.",
                reply_markup=reply_markup
            )
    
    elif query.data == 'how_found':
        # Показываем, как были найдены цены
        if 'last_prices' in context.user_data:
            prices = context.user_data['last_prices']
            search_time = context.user_data.get('last_search_time', datetime.now())
            
            message = "🔍 **Как мы искали цены:**\n\n"
            
            for p in prices:
                message += f"**{p['shop']}**\n"
                message += f"• Найденная цена: {format_price(p['price'])} руб.\n"
                message += f"• Ссылка: [перейти]({p['url']})\n\n"
            
            message += f"🕐 Время поиска: {search_time.strftime('%H:%M %d.%m.%Y')}\n\n"
            message += "_Цены получены прямым парсингом сайтов магазинов_"
            
            keyboard = [[InlineKeyboardButton("◀️ НАЗАД К ЦЕНАМ", callback_data='back_to_prices')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text(
                "Нет данных о последнем поиске. Нажмите 'УЗНАТЬ ЦЕНУ' сначала.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ НАЗАД", callback_data='back_to_start')
                ]])
            )
    
    elif query.data == 'back_to_prices':
        # Возвращаемся к результатам цен
        if 'last_prices' in context.user_data:
            prices = context.user_data['last_prices']
            min_price = min(prices, key=lambda x: x['price'])
            
            message = f" **{Product_name}**\n\n"
            message += f" **ЛУЧШАЯ ЦЕНА:**\n"
            message += f" **{format_price(min_price['price'])} руб.**\n"
            message += f" Магазин: {min_price['shop']}\n"
            message += f" [Ссылка на товар]({min_price['url']})\n\n"
            
            message += "📊 **Все найденные цены:**\n"
            
            sorted_prices = sorted(prices, key=lambda x: x['price'])
            for p in sorted_prices:
                if p['price'] == min_price['price']:
                    message += f"{p['shop']}: {format_price(p['price'])} руб. (лучшая)\n"
                else:
                    diff = p['price'] - min_price['price']
                    message += f"• {p['shop']}: {format_price(p['price'])} руб. (+{format_price(diff)})\n"
            
            keyboard = [
                [InlineKeyboardButton("АХУЕТЬ! НАЗАД...", callback_data='back_to_start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    
    elif query.data == 'back_to_start':
        # Возвращаемся в начальное меню
        keyboard = [
            [InlineKeyboardButton("УЗНАТЬ ЦЕНУ", callback_data='price')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        )

def main():
    logger.info("Запуск бота...")

    if not TOKEN:
        logger.error("Нет токена!")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот успешно запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
