import os
import logging
import requests
import re
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes


# ======================================
# LOGGING
# ======================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ======================================
# CONFIG
# ======================================

TOKEN = os.getenv("BOT_TOKEN")

PRODUCT_NAME = "iPhone 17 Pro Max 512GB Silver"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


SHOPS = {
    "aw_store": {
        "name": "🍏 Apple World",
        "url": "https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/",
        "emoji": "🏪"
    },
    "swype": {
        "name": "⚡ Swype",
        "url": "https://swype59.ru/product/iphone-17-pro-max-512-gb-silver",
        "emoji": "⚡"
    },
    "ipoint": {
        "name": "📱 iPoint",
        "url": "https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim",
        "emoji": "📍"
    }
}


# ======================================
# HTTP
# ======================================

def fetch(url):

    try:

        r = requests.get(url, headers=HEADERS, timeout=10)

        if r.status_code == 200:
            return r.text

    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")

    return None


# ======================================
# SMART PRICE PARSER
# ======================================

def smart_price_parser(html):

    soup = BeautifulSoup(html, "html.parser")

    # удаляем зачёркнутые цены
    for tag in soup.find_all(["del", "s"]):
        tag.decompose()

    selectors = [
        ".price",
        ".product-price",
        ".current-price",
        ".price-current",
        ".price_value",
        ".woocommerce-Price-amount"
    ]

    prices = []

    for sel in selectors:

        elements = soup.select(sel)

        for el in elements:

            text = el.get_text(" ", strip=True)

            matches = re.findall(r"\d[\d\s]{3,7}", text)

            for m in matches:
                price = int(m.replace(" ", ""))
                prices.append(price)

    if prices:
        return min(prices)

    # fallback
    matches = re.findall(r"\d[\d\s]{4,7}", html)

    prices = []

    for m in matches:

        p = int(m.replace(" ", ""))

        if 10000 < p < 500000:
            prices.append(p)

    if prices:
        return min(prices)

    return None


# ======================================
# PARSERS
# ======================================

def parse_aw_store(url):

    html = fetch(url)

    if not html:
        return None

    match = re.search(r'(\d[\d\s]*)\s*руб\.\s*/\s*шт', html)

    if match:
        price = int(match.group(1).replace(" ", ""))
        logger.info(f"Apple World price {price}")
        return price

    return None


def parse_swype(url):

    html = fetch(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    price_block = soup.select_one(".price")

    if not price_block:
        return None

    prices = re.findall(r'(\d[\d\s]*)\s*₽', price_block.text)

    if not prices:
        return None

    # берём последнюю цену (она акционная)
    price = int(prices[-1].replace(" ", ""))

    logger.info(f"Swype price {price}")

    return price


def parse_ipoint(url):

    html = fetch(url)

    if not html:
        return None

    price = smart_price_parser(html)

    logger.info(f"iPoint price {price}")

    return price


# ======================================
# CHECK PRICES
# ======================================

async def check_prices():

    parsers = {
        "aw_store": parse_aw_store,
        "swype": parse_swype,
        "ipoint": parse_ipoint
    }

    tasks = []

    for shop_id, shop in SHOPS.items():

        parser = parsers[shop_id]

        tasks.append(
            asyncio.to_thread(parser, shop["url"])
        )

    prices = await asyncio.gather(*tasks)

    results = []

    for i, shop_id in enumerate(SHOPS.keys()):

        price = prices[i]

        if price:

            results.append({
                "shop": SHOPS[shop_id]["name"],
                "price": price,
                "url": SHOPS[shop_id]["url"],
                "emoji": SHOPS[shop_id]["emoji"]
            })

    return results


# ======================================
# FORMAT
# ======================================

def format_price(price):

    return f"{price:,}".replace(",", " ")


# ======================================
# TELEGRAM
# ======================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("💰 Проверить цену", callback_data="price")]
    ]

    await update.message.reply_text(
        f"📱 Отслеживаю цену:\n\n{PRODUCT_NAME}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    await query.edit_message_text("🔎 Проверяю цены...")

    prices = await check_prices()

    if not prices:

        await query.edit_message_text("❌ Не удалось получить цены")

        return

    best = min(prices, key=lambda x: x["price"])

    text = f"📱 {PRODUCT_NAME}\n\n"

    text += "🏆 Лучшая цена\n"

    text += f"{best['emoji']} {best['shop']}\n"

    text += f"💰 {format_price(best['price'])} ₽\n\n"

    text += "📊 Все магазины\n\n"

    for p in sorted(prices, key=lambda x: x["price"]):

        text += f"{p['emoji']} {p['shop']} — {format_price(p['price'])} ₽\n"

    text += f"\n🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="price")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )


# ======================================
# MAIN
# ======================================

def main():

    if not TOKEN:

        logger.error("BOT_TOKEN не найден")

        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(button))

    logger.info("Бот запущен")

    app.run_polling()


if __name__ == "__main__":
    main()
