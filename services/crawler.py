import time
import concurrent.futures
from typing import Dict, List, Tuple, Any, Union

from selenium.webdriver.common.by import By

from config import DEFAULT_TIMEOUT, DEFAULT_MAX_WORKERS
from utils.logging_config import logger
from utils.helpers import extract_subscriber_count, load_channel_data, get_current_time, sort_results_by_subscriber_count
from services.selenium_setup import setup_chrome_driver


def find_profile_image(driver):
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


def get_subscriber_count(driver, channel_url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[Union[float, str], str, Union[str, None]]:
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


def crawl_single_channel(channel_info: Dict[str, str], current_time: str) -> Dict[str, Any]:
    channel_name = channel_info["name"]
    channel_handle = channel_info["handle"]
    channel_url = f"https://www.youtube.com/@{channel_handle}"
    
    driver = setup_chrome_driver()
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


def crawl_channels_by_category(category_index: int, max_workers: int = DEFAULT_MAX_WORKERS) -> Dict[str, Any]:
    channels_data = load_channel_data()
    if not channels_data:
        return {"error": "채널 데이터를 로드할 수 없습니다."}

    current_time = get_current_time()
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
    
    sorted_results = sort_results_by_subscriber_count(results)
    
    elapsed = time.time() - start_time
    logger.info(f"'{selected_category}' 카테고리 크롤링 완료: {elapsed:.2f}초 소요")
    
    return {
        "category": selected_category,
        "channels": sorted_results,
        "total_channels": len(sorted_results),
        "crawled_at": current_time,
        "elapsed_seconds": round(elapsed, 2)
    }


def get_all_categories() -> Dict[str, Any]:
    channels_data = load_channel_data()
    if not channels_data:
        return {"error": "카테고리 목록을 로드할 수 없습니다."}
        
    categories = list(channels_data.keys())
    return {
        "categories": [
            {"id": i+1, "name": category} 
            for i, category in enumerate(categories)
        ],
        "total": len(categories)
    }