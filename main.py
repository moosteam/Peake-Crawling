from fastapi import FastAPI, HTTPException, Query
import uvicorn

from config import API_HOST, API_PORT, DEBUG_MODE
from utils.logging_config import logger
from services.crawler import crawl_channels_by_category, get_all_categories
from models.schemas import CategoriesResponse, CategoryResponse, ErrorResponse


app = FastAPI(
    title="YouTube Subscriber API",
    description="유튜브 채널 구독자 수 조회 API",
    version="1.0.0"
)


@app.get("/", response_model=dict)
def read_root():
    return {"message": "YouTube Subscriber API에 오신 것을 환영합니다!"}


@app.get("/categories", response_model=CategoriesResponse, responses={400: {"model": ErrorResponse}})
def get_categories():
    result = get_all_categories()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/category/{category_id}", response_model=CategoryResponse, responses={400: {"model": ErrorResponse}})
def get_category_channels(
    category_id: int,
    max_workers: int = Query(4, gt=0, le=10, description="병렬 처리에 사용할 최대 워커 수")
):
    result = crawl_channels_by_category(category_id, max_workers)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


def main():
    logger.info(f"YouTube Subscriber API 서버 시작 (host: {API_HOST}, port: {API_PORT})")
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=DEBUG_MODE)


if __name__ == "__main__":
    main()