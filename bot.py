import httpx
from selectolax.parser import HTMLParser
import re

Shops = {
    "AppleWorld": {
        "name": "AppleWorld",
        "url": "https://aw-store.ru/catalog/iphone/iphone_17_pro_max/87898/",
        "selector": ".price_value"
    },
    "Swype": {
        "name": "Swype",
        "url": "https://swype59.ru/product/iphone-17-pro-max-512-gb-silver",
        "selector": ".product__price"
    },
    "iPoint": {
        "name": "iPoint",
        "url": "https://ipointperm.ru/product/apple-iphone-17-pro-max-512gb-belyy-silver-dual-sim",
        "selector": ".price"
    }
}

headers = {
    "User-Agent": "Mozilla/5.0"
}


def extract_price(text: str):
    numbers = re.findall(r'\d+', text)
    if numbers:
        return int("".join(numbers))
    return None


async def parse_shop(client, shop):
    try:
        r = await client.get(shop["url"])
        tree = HTMLParser(r.text)

        node = tree.css_first(shop["selector"])

        if not node:
            return None

        price = extract_price(node.text())
        return {
            "shop": shop["name"],
            "price": price,
            "url": shop["url"]
        }

    except Exception as e:
        print("Ошибка:", shop["name"], e)
        return None


async def check_prices():
    async with httpx.AsyncClient(headers=headers, timeout=20) as client:

        tasks = [
            parse_shop(client, shop)
            for shop in Shops.values()
        ]

        results = await asyncio.gather(*tasks)

    results = [r for r in results if r]

    return results
