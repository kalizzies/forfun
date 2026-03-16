import os
import logging
import requests
import re
import asyncio

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

    return results


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("УЗНАТЬ ЦЕНУ", callback_data='price')],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Ты ебанулась, но ладно...",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == 'price':

        await query.edit_message_text("Проверяю цены...")

        prices = await check_prices()

        if prices:

            min_price = min(prices, key=lambda x: x['price'])

            message = f"Лучшая цена: {min_price['price']} руб.\n"
            message += f"🔗 {min_price['url']}"

            await query.edit_message_text(message)

        else:
            await query.edit_message_text("Не удалось получить цены")


def main():

    logger.info("Запуск бота...")

    if not TOKEN:
        logger.error("Нет токена!")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен!")

    application.run_polling()


if __name__ == '__main__':
    main()
