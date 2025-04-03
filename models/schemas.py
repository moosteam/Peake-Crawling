from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class CategoryItem(BaseModel):
    id: int
    name: str


class CategoriesResponse(BaseModel):
    categories: List[CategoryItem]
    total: int


class ChannelResult(BaseModel):
    channel_name: str
    channel_handle: str
    channel_url: str
    subscriber_count: Union[float, str]
    raw_text: str
    profile_image_url: Optional[str] = None
    crawled_at: str


class CategoryResponse(BaseModel):
    category: str
    channels: List[ChannelResult]
    total_channels: int
    crawled_at: str
    elapsed_seconds: float


class ErrorResponse(BaseModel):
    detail: str