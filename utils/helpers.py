import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Union, Any
from datetime import datetime

from utils.logging_config import logger
from config import CHANNELS_FILE


def extract_subscriber_count(text: str) -> Tuple[Union[float, str], Union[str, None]]:
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
            
    return text, None


def load_channel_data() -> Dict[str, List[Dict[str, str]]]:
    try:
        channels_path = Path(CHANNELS_FILE)
        if not channels_path.exists():
            logger.error(f"채널 파일이 존재하지 않습니다: {CHANNELS_FILE}")
            return {}
            
        with open(channels_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"채널 데이터 로드 중 오류 발생: {e}")
        return {}


def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def sort_results_by_subscriber_count(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(item):
        sub_count = item['subscriber_count']
        if isinstance(sub_count, (int, float)):
            return sub_count
        try:
            return float(sub_count)
        except:
            return 0
            
    return sorted(results, key=sort_key, reverse=True)