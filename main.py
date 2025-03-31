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
        time.sleep(5)  # 페이지 로딩 기다리기
        
        # 구독자 수 요소 찾기 시도 (여러 선택자)
        selectors = [
            ".yt-core-attributed-string.yt-content-metadata-view-model-wiz__metadata-text",  # 제공된 클래스
            "span.yt-core-attributed-string",  # 일반적인 유튜브 채널 구독자 클래스
            "#subscriber-count",
            "yt-formatted-string#subscriber-count",
            "#meta-contents #subscriber-count",
            ".ytd-c4-tabbed-header-renderer #subscriber-count"
        ]
        
        for selector in selectors:
            try:
                print(f"선택자 시도 중: {selector}")
                wait = WebDriverWait(driver, 5)
                subscriber_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                subscriber_text = subscriber_element.text
                
                # 요소가 구독자 정보를 포함하는지 확인
                if '구독자' in subscriber_text or 'subscriber' in subscriber_text.lower():
                    print(f"찾은 구독자 텍스트: {subscriber_text}")
                    # 요소 강조 표시 (시각적 피드백)
                    # driver.execute_script("""
                    # arguments[0].style.border='3px solid red';
                    # arguments[0].style.backgroundColor='yellow';
                    # arguments[0].style.color='black';
                    # """, subscriber_element)
                    time.sleep(1)  # 강조 표시를 잠시 보여줌
                    subscriber_count = extract_subscriber_count(subscriber_text)
                    return subscriber_count, subscriber_text

            except Exception as e:
                print(f"선택자 {selector} 실패: {e}")
                continue
        
        # 추가 시도: 모든 span 요소에서 '구독자' 텍스트 검색
        try:
            all_spans = driver.find_elements(By.TAG_NAME, "span")
            for span in all_spans:
                text = span.text
                if '구독자' in text or 'subscriber' in text.lower():
                    print(f"span 태그에서 찾은 구독자 텍스트: {text}")
                    driver.execute_script("arguments[0].style.border='3px solid red'", span)
                    time.sleep(1)
                    return extract_subscriber_count(text), text
        except Exception as e:
            print(f"span 태그 검색 실패: {e}")
        
        return "정보를 찾을 수 없음", "텍스트 없음"
    
    except Exception as e:
        print(f"에러 발생: {e}")
        return "에러 발생", "에러"

def main():
    # 크롤링할 유튜브 채널 리스트를 JSON 파일에서 로드
    try:
        with open('channels.json', 'r', encoding='utf-8') as file:
            channels_data = json.load(file)
        print(f"채널 리스트 로드 완료: {len(channels_data)}개의 채널을 찾았습니다.")
    except Exception as e:
        print(f"채널 리스트 로드 실패: {e}")
        channels_data = []  # 빈 리스트로 초기화
    
    # 결과를 저장할 리스트
    results = []
    
    # 파이어폭스 드라이버 설정 (화면 표시 모드)
    driver = setup_firefox_driver(headless=True)
    
    try:
        for channel in channels_data:
            channel_name = channel["name"]
            channel_handle = channel["handle"]
            channel_url = f"https://www.youtube.com/@{channel_handle}"
            
            print(f"\n크롤링 시작: {channel_name} ({channel_url})")
            
            # 구독자 수 가져오기
            subscriber_count, raw_text = get_subscriber_count(driver, channel_url)
            
            # 결과 저장
            results.append({
                "channel_name": channel_name,
                "channel_handle": channel_handle,
                "channel_url": channel_url,
                "subscriber_count": subscriber_count,
                "raw_text": raw_text
            })
            
            # 결과 출력
            print(f"채널: {channel_name}")
            print(f"핸들: @{channel_handle}")
            print(f"구독자 수: {subscriber_count}")
            print(f"원본 텍스트: {raw_text}")
            
        # CSV 파일로 저장
        with open('youtube_subscribers.csv', 'w', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=["channel_name", "channel_handle", "channel_url", "subscriber_count", "raw_text"])
            writer.writeheader()
            writer.writerows(results)
            
        print(f"\n크롤링 완료! 총 {len(results)}개의 채널 정보를 수집했습니다.")
        print("결과는 'youtube_subscribers.csv' 파일에 저장되었습니다.")
            
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {e}")
    
    finally:
        # 드라이버 종료
        driver.quit()

if __name__ == "__main__":
    main()