from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
import json
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional
import uvicorn
from datetime import datetime
import concurrent.futures
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Subscriber API", description="유튜브 채널 구독자 수 조회 API")

def setup_chrome_driver(headless=True):
    """크롬 셀레니움 드라이버 설정 - 성능 최적화"""
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

def extract_subscriber_count(text):
    """구독자 수 텍스트에서 숫자 추출"""
    if not text:
        return "정보 없음", None
    
    match = re.search(r'구독자\s+([\d,.]+)([만천])?', text)
    if match:
        number = match.group(1).replace(',', '')
        unit = match.group(2) if match.group(2) else ""
        
        if unit == "만":
            return float(number) * 10000, None
        elif unit == "천":
            return float(number) * 1000, None
        else:
            return float(number), None
    else:
        match = re.search(r'([\d,.]+)([KMB])?\s+subscribers', text)
        if match:
            number = match.group(1).replace(',', '')
            unit = match.group(2) if match.group(2) else ""
            
            if unit == "K":
                return float(number) * 1000, None
            elif unit == "M":
                return float(number) * 1000000, None
            elif unit == "B":
                return float(number) * 1000000000, None
            else:
                return float(number), None
        else:
            return text, None

def find_profile_image(driver):
    """이미지 URL을 찾기 위한 전용 함수 - 프로필 이미지만 정확히 가져오도록 개선"""
    try:
        profile_selectors = [
            "#avatar img", 
            "#channel-header-container #avatar img",
            "#inner-header-container #avatar img",
            "yt-img-shadow#avatar img",
            "#profile-image img",
            "#channel-thumbnail img"
        ]
        
        for selector in profile_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for img in elements:
                src = img.get_attribute('src')
                if src and ('yt3' in src) and not ('banner' in src.lower()):
                    logger.info(f"정확한 프로필 선택자로 찾은 이미지: {src}")
                    return src

        all_imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in all_imgs:
            src = img.get_attribute('src')
            alt = img.get_attribute('alt') or ""

            if src and ('yt3.googleusercontent.com' in src) and not ('banner' in src.lower()):
                width = img.get_attribute('width')
                height = img.get_attribute('height')

                if width and height and int(width) == int(height) and int(width) <= 200:
                    logger.info(f"크기 확인으로 찾은 프로필 이미지: {src}")
                    return src

                if any(keyword in alt.lower() for keyword in ['profile', '프로필', 'avatar', 'channel']):
                    logger.info(f"alt 텍스트로 찾은 프로필 이미지: {src}")
                    return src
            
        logger.warning("프로필 이미지를 찾을 수 없음")
        return None
        
    except Exception as e:
        logger.error(f"이미지 찾기 오류: {e}")
        return None

def get_subscriber_count(driver, channel_url, timeout=10):
    """특정 채널 URL로 이동해서 구독자 수와 프로필 이미지 URL 가져오기 - 속도 최적화"""
    try:
        driver.get(channel_url)
        logger.info(f"페이지 로딩 중: {channel_url}")
        start_time = time.time()

        subscriber_text = None
        profile_image_url = None

        while time.time() - start_time < timeout:
            driver.execute_script("window.scrollBy(0, 300);")
            if not profile_image_url:
                profile_image_url = find_profile_image(driver)

            if not subscriber_text:
                try:
                    xpath = '//*[@id="page-header"]/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-content-metadata-view-model/div[2]/span[1]'
                    subscriber_element = driver.find_element(By.XPATH, xpath)
                    text = subscriber_element.text
                    if '구독자' in text or 'subscriber' in text.lower():
                        subscriber_text = text
                        logger.info(f"XPath로 찾은 구독자 텍스트: {subscriber_text}")
                except:
                    pass

                if not subscriber_text:
                    try:
                        all_spans = driver.find_elements(By.TAG_NAME, "span")
                        for span in all_spans:
                            text = span.text
                            if '구독자' in text or 'subscriber' in text.lower():
                                subscriber_text = text
                                logger.info(f"span 태그에서 찾은 구독자 텍스트: {subscriber_text}")
                                break
                    except:
                        pass

            if subscriber_text and profile_image_url:
                break

            time.sleep(0.5)
        if subscriber_text:
            subscriber_count, _ = extract_subscriber_count(subscriber_text)
        else:
            subscriber_count = "정보를 찾을 수 없음"
            subscriber_text = "텍스트 없음"
            
        if not profile_image_url:
            logger.warning("프로필 이미지를 찾을 수 없음")
            
        elapsed = time.time() - start_time
        logger.info(f"채널 크롤링 완료: {elapsed:.2f}초 소요")
        
        return subscriber_count, subscriber_text, profile_image_url
    
    except Exception as e:
        logger.error(f"에러 발생: {e}")
        return "에러 발생", "에러", None

def crawl_single_channel(channel_info, current_time):
    """단일 채널 크롤링 함수 - 병렬 처리용"""
    channel_name = channel_info["name"]
    channel_handle = channel_info["handle"]
    channel_url = f"https://www.youtube.com/@{channel_handle}"
    
    driver = setup_chrome_driver(headless=True)
    try:
        logger.info(f"크롤링 시작: {channel_name} ({channel_url})")
        subscriber_count, raw_text, profile_image_url = get_subscriber_count(driver, channel_url)
        
        result = {
            "channel_name": channel_name,
            "channel_handle": channel_handle,
            "channel_url": channel_url,
            "subscriber_count": subscriber_count,
            "raw_text": raw_text,
            "profile_image_url": profile_image_url,
            "crawled_at": current_time
        }
        
        logger.info(f"채널 크롤링 결과: {channel_name}, 구독자 수: {subscriber_count}")
        return result
    except Exception as e:
        logger.error(f"{channel_name} 크롤링 중 오류: {e}")
        return {
            "channel_name": channel_name,
            "channel_handle": channel_handle,
            "channel_url": channel_url,
            "subscriber_count": "에러 발생",
            "raw_text": f"에러: {str(e)}",
            "profile_image_url": None,
            "crawled_at": current_time
        }
    finally:
        driver.quit()

def crawl_channels_by_category(category_index: int, max_workers=4):
    """특정 카테고리의 채널들을 병렬 크롤링하여 구독자 수 정보 반환"""
    try:
        with open('channels.json', 'r', encoding='utf-8') as file:
            channels_data = json.load(file)
    except Exception as e:
        logger.error(f"채널 리스트 로드 실패: {e}")
        return {"error": "채널 데이터를 로드할 수 없습니다."}

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    categories = list(channels_data.keys())
    logger.info(f"카테고리 수: {len(categories)}")
    
    if category_index < 1 or category_index > len(categories):
        return {"error": f"유효한 카테고리 인덱스가 아닙니다. 1부터 {len(categories)}까지의 값을 입력하세요."}

    selected_category = categories[category_index - 1]
    channels_in_category = channels_data[selected_category]

    logger.info(f"'{selected_category}' 카테고리 크롤링 시작 ({len(channels_in_category)} 채널)")
    start_time = time.time()
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_channel = {
            executor.submit(crawl_single_channel, channel, current_time): channel 
            for channel in channels_in_category
        }
        
        for future in concurrent.futures.as_completed(future_to_channel):
            result = future.result()
            if result:
                results.append(result)
    
    def sort_key(item):
        sub_count = item['subscriber_count']
        if isinstance(sub_count, (int, float)):
            return sub_count
        try:
            return float(sub_count)
        except:
            return 0
            
    results.sort(key=sort_key, reverse=True)
    
    elapsed = time.time() - start_time
    logger.info(f"'{selected_category}' 카테고리 크롤링 완료: {elapsed:.2f}초 소요")
    
    return {
        "category": selected_category,
        "channels": results,
        "total_channels": len(results),
        "crawled_at": current_time,
        "elapsed_seconds": round(elapsed, 2)
    }

def get_all_categories():
    """모든 카테고리 목록 반환"""
    try:
        with open('channels.json', 'r', encoding='utf-8') as file:
            channels_data = json.load(file)
        categories = list(channels_data.keys())
        return {
            "categories": [
                {"id": i+1, "name": category} 
                for i, category in enumerate(categories)
            ],
            "total": len(categories)
        }
    except Exception as e:
        logger.error(f"카테고리 목록 로드 실패: {e}")
        return {"error": "카테고리 목록을 로드할 수 없습니다."}

@app.get("/")
def read_root():
    """API 루트 엔드포인트"""
    return {"message": "YouTube Subscriber API에 오신 것을 환영합니다!"}

@app.get("/categories")
def get_categories():
    """모든 카테고리 목록 조회"""
    return get_all_categories()

@app.get("/category/{category_id}")
def get_category_channels(category_id: int, max_workers: int = 4):
    """특정 카테고리의 채널 구독자 수 조회 - max_workers로 병렬 처리 수준 조절 가능"""
    result = crawl_channels_by_category(category_id, max_workers)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

def main():
    """메인 함수 - 직접 실행 시 FastAPI 서버 시작"""
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()