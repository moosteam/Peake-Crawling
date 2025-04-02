from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
import time
import csv
import re
import json  # Add JSON import
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional
import uvicorn
from datetime import datetime

# FastAPI 앱 생성
app = FastAPI(title="YouTube Subscriber API", description="유튜브 채널 구독자 수 조회 API")

def setup_firefox_driver(headless):
    """파이어폭스 셀레니움 드라이버 설정"""
    options = Options()
    
    if headless:
        options.add_argument("--headless")  # 화면 표시 없이 실행
    
    options.set_preference("dom.webnotifications.enabled", False)  # 알림 비활성화
    options.set_preference("media.volume_scale", "0.0")  # 음소거
    
    # 사용자 에이전트 설정
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0")
    
    # geckodriver 설치 및 서비스 설정
    service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    
    # 창 최대화
    driver.maximize_window()
    
    return driver

def extract_subscriber_count(text):
    """구독자 수 텍스트에서 숫자 추출"""
    if not text:
        return "정보 없음"
    
    # "구독자 1.82만명" 같은 형식에서 숫자와 단위 추출
    match = re.search(r'구독자\s+([\d,.]+)([만천])?', text)
    if match:
        number = match.group(1).replace(',', '')
        unit = match.group(2) if match.group(2) else ""
        
        if unit == "만":
            return float(number) * 10000
        elif unit == "천":
            return float(number) * 1000
        else:
            return float(number)
    
    # 영어 형식 ("1.2M subscribers")
    match = re.search(r'([\d,.]+)([KMB])?\s+subscribers', text)
    if match:
        number = match.group(1).replace(',', '')
        unit = match.group(2) if match.group(2) else ""
        
        if unit == "K":
            return float(number) * 1000
        elif unit == "M":
            return float(number) * 1000000
        elif unit == "B":
            return float(number) * 1000000000
        else:
            return float(number)
    
    return text  # 매칭되지 않으면 원본 텍스트 반환

def get_subscriber_count(driver, channel_url):
    """특정 채널 URL로 이동해서 구독자 수 가져오기"""
    try:
        driver.get(channel_url)
        print(f"페이지 로딩 중: {channel_url}")
        
        # 무작정 5초 기다리는 대신 1초씩 최대 5번 시도하는 방식으로 변경
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            print(f"시도 {attempt}/{max_attempts}...")
            time.sleep(1)  # 1초 대기
            
            # XPath를 사용하여 구독자 수 요소 찾기
            try:
                xpath = '//*[@id="page-header"]/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-content-metadata-view-model/div[2]/span[1]'
                wait = WebDriverWait(driver, 1)  # 짧은 대기 시간 설정
                subscriber_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                subscriber_text = subscriber_element.text
                
                # 요소가 구독자 정보를 포함하는지 확인
                if '구독자' in subscriber_text or 'subscriber' in subscriber_text.lower():
                    print(f"XPath로 찾은 구독자 텍스트: {subscriber_text} (시도 {attempt}에 성공)")
                    subscriber_count = extract_subscriber_count(subscriber_text)
                    return subscriber_count, subscriber_text
            except Exception as e:
                print(f"시도 {attempt}: XPath 선택자 실패: {e}")
                
                # 마지막 시도에서만 백업 방법 시도
                if attempt == max_attempts:
                    print("모든 XPath 시도 실패, 백업 방법으로 전환")
                    # 추가 시도: 모든 span 요소에서 '구독자' 텍스트 검색 (기존 백업 방법)
                    try:
                        all_spans = driver.find_elements(By.TAG_NAME, "span")
                        for span in all_spans:
                            text = span.text
                            if '구독자' in text or 'subscriber' in text.lower():
                                print(f"span 태그에서 찾은 구독자 텍스트: {text}")
                                driver.execute_script("arguments[0].style.border='3px solid red'", span)
                                time.sleep(0.5)
                                return extract_subscriber_count(text), text
                    except Exception as span_e:
                        print(f"span 태그 검색 실패: {span_e}")
        
        return "정보를 찾을 수 없음", "텍스트 없음"
    
    except Exception as e:
        print(f"에러 발생: {e}")
        return "에러 발생", "에러"

def crawl_channels_by_category(category_index: int):
    """특정 카테고리의 채널들을 크롤링하여 구독자 수 정보 반환"""
    # 채널 데이터 로드
    try:
        with open('channels.json', 'r', encoding='utf-8') as file:
            channels_data = json.load(file)
    except Exception as e:
        print(f"채널 리스트 로드 실패: {e}")
        return {"error": "채널 데이터를 로드할 수 없습니다."}
    
    # 현재 시간 가져오기 (시, 분까지만)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 카테고리 목록 가져오기
    categories = list(channels_data.keys())
    print(len(categories))
    # 유효한 카테고리 인덱스인지 확인
    if category_index < 1 or category_index > len(categories):
        return {"error": f"유효한 카테고리 인덱스가 아닙니다. 1부터 {len(categories)}까지의 값을 입력하세요."}
    
    # 선택된 카테고리
    selected_category = categories[category_index - 1]
    channels_in_category = channels_data[selected_category]
    
    # 결과를 저장할 리스트
    results = []
    
    # 파이어폭스 드라이버 설정
    driver = setup_firefox_driver(headless=True)
    
    try:
        for channel in channels_in_category:
            channel_name = channel["name"]
            channel_handle = channel["handle"]
            channel_url = f"https://www.youtube.com/@{channel_handle}"
            
            print(f"\n크롤링 시작: {channel_name} ({channel_url})")
            
            # 구독자 수 가져오기
            subscriber_count, raw_text = get_subscriber_count(driver, channel_url)
            
            # 결과 저장
            results.append({
                "category": selected_category,
                "channel_name": channel_name,
                "channel_handle": channel_handle,
                "channel_url": channel_url,
                "subscriber_count": subscriber_count,
                "raw_text": raw_text,
                "crawled_at": current_time
            })
            
            # 결과 출력
            print(f"채널: {channel_name}")
            print(f"핸들: @{channel_handle}")
            print(f"구독자 수: {subscriber_count}")
            print(f"원본 텍스트: {raw_text}")
            print(f"크롤링 시간: {current_time}")
        
        return {
            "category": selected_category,
            "channels": results,
            "total_channels": len(results),
            "crawled_at": current_time
        }
            
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {e}")
        return {"error": f"크롤링 중 오류 발생: {str(e)}"}
    
    finally:
        # 드라이버 종료
        driver.quit()

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
        print(f"카테고리 목록 로드 실패: {e}")
        return {"error": "카테고리 목록을 로드할 수 없습니다."}

# FastAPI 라우트 정의
@app.get("/")
def read_root():
    """API 루트 엔드포인트"""
    return {"message": "YouTube Subscriber API에 오신 것을 환영합니다!"}

@app.get("/categories")
def get_categories():
    """모든 카테고리 목록 조회"""
    return get_all_categories()

@app.get("/category/{category_id}")
def get_category_channels(category_id: int):
    """특정 카테고리의 채널 구독자 수 조회"""
    result = crawl_channels_by_category(category_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

def main():
    """메인 함수 - 직접 실행 시 FastAPI 서버 시작"""
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()