import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import asyncio

TOKEN = os.environ.get('BOT_TOKEN')

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


def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def parse_from_appleworld():
    driver = create_driver()
    driver.get(Shops["AppleWorld"]["url"])

    try:
        price = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".price_value"))
        )
        price_text = price.text
        price_numbers = int(''.join(filter(str.isdigit, price_text)))
        return price_numbers
    except:
        return None
    finally:
        driver.quit()


def parse_from_swype():
    driver = create_driver()
    driver.get(Shops["Swype"]["url"])

    try:
        price = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product__price-old"))
        )
        price_text = price.text
        price_numbers = int(''.join(filter(str.isdigit, price_text)))
        return price_numbers
    except:
        return None
    finally:
        driver.quit()


def parse_from_ipoint():
    driver = create_driver()
    driver.get(Shops["iPoint"]["url"])

    try:
        price = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".price"))
        )
        price_text = price.text
        price_numbers = int(''.join(filter(str.isdigit, price_text)))
        return price_numbers
    except:
        return None
    finally:
        driver.quit()


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
