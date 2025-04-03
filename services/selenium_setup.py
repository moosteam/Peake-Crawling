from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from config import HEADLESS_MODE
from utils.logging_config import logger


def setup_chrome_driver(headless=HEADLESS_MODE):
    logger.info(f"Chrome 드라이버 설정 (headless: {headless})")
    options = Options()
    
    if headless:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--disable-features=NetworkService")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--block-new-web-contents")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--aggressive-cache-discard")
    options.page_load_strategy = 'eager'
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1280, 720)
    
    return driver