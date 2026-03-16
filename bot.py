import os
import logging
from wsgiref import headers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import asyncio

##TOKEN = os.environ.get('BOT_TOKEN')

TOKEN = "8772705807:AAGrh-vS3tI1Pjk1fa-ScBCvifcCfqfh_hU"

#https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/ AppleWorld
#https://swype59.ru/product/iphone-17-pro-max-512-gb-silver Swype
#https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim iPoint

#Логирование, деплоем все же
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)   
logger=logging.getLogger(__name__)

Product_name="iPhone 17 Pro Max 512GB Silver Esim"

Shops={
    "AppleWorld":{
        "name": "AppleWorld", "url": "https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/"
    },
    "Swype": {
        "name": "Swype", "url": "https://swype59.ru/product/iphone-17-pro-max-512-gb-silver"
    },
    "iPoint": {
        "name": "iPoint", "url": "https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim"
    }
}

def parse_from_appleworld():
    url=Shops["AppleWorld"]["url"]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response=requests.get(url, headers=headers)
    soup=BeautifulSoup(response.text,'html.parser')
    price=soup.select_one('.price_value')
    if price:
        price_text=price.text.strip()
        price_numbers=int(''.join(filter(str.isdigit, price_text)))
        print(price_numbers)
        return(price_numbers)

def parse_from_swype(url):
    url=Shops["Swype"][url]
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    price_element = soup.find('.product__price-old')
    price_text = price_element.text
    price = int(''.join(filter(str.isdigit, price_text)))
    return price

def parse_from_ipoint(url):
    url=Shops["iPoint"][url]
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    price_element = soup.find('.price js-product-price')
    price_text = price_element.text
    price = int(''.join(filter(str.isdigit, price_text)))
    return price

async def check_prices():
    results = []
    tasks = [
        asyncio.to_thread(parse_from_appleworld, Shops["AppleWorld"]["url"]),
        asyncio.to_thread(parse_from_swype, Shops["Swype"]["url"]),
        asyncio.to_thread(parse_from_ipoint, Shops["iPoint"]["url"])
    ]
    prices = await asyncio.gather(*tasks)
    
    # Сбор результатов
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
    # Создаем кнопки
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
            # Находим минимальную
            min_price = min(prices, key=lambda x: x['price'])
            
            message = f"Лучшая цена: {min_price['price']} руб.\n"
            message += f"🔗 {min_price['url']}"
            
            await query.edit_message_text(message)
        else:
            await query.edit_message_text("Ну ты и навайбкодила")

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
