import base64
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from typing import Union, Any

import requests
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

app = FastAPI()

RESULTS = []
CONVERSION_RATES = {}


# Serve static files from the "static" directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Connect to the SQLite database and create a table for search history
conn = sqlite3.connect("search_history.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        time TEXT,
        item_name TEXT,
        amazon_us_price REAL,
        amazon_uk_price REAL,
        amazon_de_price REAL,
        amazon_ca_price REAL
    )
''')

conn.commit()


# Function to insert search history records into the database
def add_search_history(query: str, time: str):
    cursor.execute("INSERT INTO search_history (query, time) VALUES (?, ?)", (query, time))
    conn.commit()


def add_item_details(item_name: str, amazon_us_price: str, amazon_uk_price: str, amazon_de_price: str, amazon_ca_price: str):
    cursor.execute(
        "UPDATE search_history SET item_name=?, amazon_us_price=?, amazon_uk_price=?, amazon_de_price=?, amazon_ca_price=? WHERE id=(SELECT MAX(id) FROM search_history)",
        (item_name, amazon_us_price, amazon_uk_price, amazon_de_price, amazon_ca_price))
    conn.commit()


def has_reached_daily_limit():
    # Get the current date and time
    now = datetime.now()

    # Get the date at the beginning of the day
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get the number of searches performed today
    cursor.execute("SELECT COUNT(*) FROM search_history WHERE time >= ?", (today_start,))
    searches_today = cursor.fetchone()[0]

    # Check if 10 or more searches have been performed today
    if searches_today >= 10:
        return True

    return False


def resize_image(image_url: str, size: tuple = (64, 64)) -> str:
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    img.thumbnail(size)
    byte_data = BytesIO()
    img.save(byte_data, format="JPEG")
    data_url = "data:image/jpeg;base64," + base64.b64encode(byte_data.getvalue()).decode("utf-8")
    return data_url


def get_chrome_driver():
    chrome_options = Options()
    chrome_options.browser_version = 114
    chrome_options.add_argument("--headless=new")

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except:
        driver = webdriver.Chrome(options=chrome_options, service=Service())

    return driver


def scrape_amazon(query: str) -> tuple[str, list[dict[str, str | Any]]] | list[dict[str, str]]:
    MAX_RETRIES = 3

    driver = get_chrome_driver()

    for attempt in range(MAX_RETRIES):
        try:
            driver.get(f"https://www.amazon.com/s?k={query}")

            global RESULTS
            RESULTS = []

            try:
                result_elements = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.s-result-item")))
            except:
                try:
                    result_elements = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.sg-col-20-of-24")))
                except:
                    result_elements = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.sg-col-4-of-24")))

            for result_element in result_elements[1:]:
                if len(RESULTS) == 10:
                    break

                result = {}
                try:
                    result["name"] = result_element.find_element(By.CSS_SELECTOR, ".a-text-normal").get_attribute("textContent")
                    result["image"] = resize_image(result_element.find_element(By.CSS_SELECTOR, ".s-image").get_attribute("src"))
                    result["asin"] = result_element.get_attribute("data-asin")
                except:
                    continue
                try:
                    result["rating"] = result_element.find_element(By.CSS_SELECTOR, ".a-icon-alt").get_attribute("textContent")
                except:
                    result["rating"] = "Not Rated"

                RESULTS.append(result)

            driver.quit()
            if len(RESULTS) == 0: raise Exception

            return "success", RESULTS
        except:
            if attempt == MAX_RETRIES - 1:
                driver.quit()
                return "failure", []
            else:
                continue


def fetch_price_by_asin(domain, asin):
    url = f'https://{domain}/dp/{asin}'

    driver = get_chrome_driver()

    driver.get(url)

    try:
        try:
            price_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.reinventPricePriceToPayMargin>span:nth-child(1)')))
            price = price_element.get_attribute("textContent")
        except:
            price_element = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#price_inside_buybox')))
            price = price_element.get_attribute("textContent")
    except:
        price = "N/A"

    driver.quit()
    return domain, price, url


def get_first_product_url(domain, product_name):
    url = f'https://{domain}/s?k={product_name}'

    driver = get_chrome_driver()

    driver.get(url)

    first_product_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.s-result-item .a-link-normal.s-no-outline')))
    product_url = first_product_element.get_attribute("href")

    return product_url


def fetch_price_by_name(domain, product_name):
    url = get_first_product_url(domain, product_name)

    driver = get_chrome_driver()

    driver.get(url)

    try:
        try:
            price_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.reinventPricePriceToPayMargin>span:nth-child(1)')))
            price = price_element.get_attribute("textContent")
        except:
            price_element = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#price_inside_buybox')))
            price = price_element.get_attribute("textContent")

    except:
        price = "N/A"

    driver.quit()

    return domain, price, url


def fetch_price(domain, asin, product_name):
    domain, price, url = fetch_price_by_asin(domain, asin)

    if price == "N/A":
        domain, price, url = fetch_price_by_name(domain, product_name)

    return domain, price, url


def update_conversion_rates():
    global CONVERSION_RATES

    url = "https://api.apilayer.com/exchangerates_data/latest?symbols=USD%2CGBP%2CEUR%2CCAD&base=USD"

    payload = {}
    headers = {
        "apikey": "your_api_key"    # place API key
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    if response.ok:
        result = json.loads(response.text)
        CONVERSION_RATES = result["rates"]
    else:
        CONVERSION_RATES = {
            "USD": 1.0,
            "GBP": 0.8,   # 1 USD to GBP
            "EUR": 0.9,   # 1 USD to EUR
            "CAD": 1.36,  # 1 USD to CAD
        }


def convert_to_usd(amount, currency):
    if currency not in CONVERSION_RATES:
        raise ValueError(f"Unsupported currency: {currency}")

    conversion_rate = CONVERSION_RATES[currency]
    return amount / conversion_rate


def parse_price(price_str: str, domain: str) -> Union[float, str]:
    if price_str == "N/A":
        return price_str

    if domain == 'amazon.de':
        price_str = price_str.replace(',', '.')
    # Remove any non-numeric characters (except decimal points) and convert to float
    return float(re.sub(r"[^\d.]", "", price_str))


def scrape_amazon_prices(asin: str, product_name: str) -> tuple[dict[Any, float | str], dict[Any, Any]]:
    amazon_domains = ['amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.ca']
    domain_currencies = {
        'amazon.com': 'USD',
        'amazon.co.uk': 'GBP',
        'amazon.de': 'EUR',
        'amazon.ca': 'CAD',
    }
    prices = {}
    urls = {}

    update_conversion_rates()

    with ThreadPoolExecutor() as executor:
        tasks = [executor.submit(fetch_price, domain, asin, product_name) for domain in amazon_domains]
        results = [task.result() for task in tasks]

    for domain, price_str, url in results:
        currency = domain_currencies[domain]
        price = parse_price(price_str, domain)
        if price == "N/A":
            prices[domain] = price
        else:
            price_usd = convert_to_usd(price, currency)
            prices[domain] = f"${price_usd:.2f}"
        urls[domain] = url

    return prices, urls


@app.get("/", response_class=FileResponse)
async def get_index():
    return FileResponse("templates/index.html")


@app.get("/search")
async def search_amazon(query: str):
    if has_reached_daily_limit():
        return JSONResponse(content={"results": []}, status_code=429)

    status, RESULTS = scrape_amazon(query)

    if status == "failure":
        return JSONResponse(content={"results": []}, status_code=500)

    # Record search history
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_search_history(query, current_time)

    return {"results": RESULTS}


@app.get("/search_history")
async def get_search_history():
    cursor.execute("SELECT * FROM search_history")
    search_history = cursor.fetchall()
    history_data = [
        {
            "id": record[0],
            "query": record[1],
            "time": record[2],
            "item_name": record[3],
            "amazon_us_price": record[4],
            "amazon_uk_price": record[5],
            "amazon_de_price": record[6],
            "amazon_ca_price": record[7],
        }
        for record in search_history
    ]
    return {"search_history": history_data}


@app.get("/search_history_page")
async def get_search_history_page():
    return FileResponse("static/search_history.html")


@app.get("/compare", response_class=HTMLResponse)
async def compare_amazon_prices(request: Request, asin: str):
    for result in RESULTS:
        if asin == result['asin']:
            product_name = result['name']
            prices, urls = scrape_amazon_prices(asin, product_name)

            # Store item details
            add_item_details(result['name'], prices['amazon.com'], prices['amazon.co.uk'], prices['amazon.de'], prices['amazon.ca'])

            return JSONResponse(content={
                "item_name": result['name'],
                "item_rating": result['rating'],
                "prices": prices,
                "urls": urls
             })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
