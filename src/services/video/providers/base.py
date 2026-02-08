"""
视频服务多提供商支持
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class VideoProviderType(str, Enum):
    """视频提供商类型"""
    JIEKOUAI = "jiekouai"
    KELING = "keling"
    RUNWAY = "runway"
    PIKA = "pika"


class VideoDuration(str, Enum):
    """标准化时长"""
    SECONDS_5 = "5s"
    SECONDS_10 = "10s"


class VideoResolution(str, Enum):
    """标准化分辨率"""
    PORTRAIT_720P = "720x1280"   # 竖屏
    LANDSCAPE_720P = "1280x720"  # 横屏


class VideoGenerationRequest(BaseModel):
    """统一请求格式"""
    prompt: str
    image_path: Optional[str] = None
    duration: VideoDuration = VideoDuration.SECONDS_5
    resolution: VideoResolution = VideoResolution.LANDSCAPE_720P
    watermark: bool = False
    # 提供商特定参数
    provider_params: Dict[str, Any] = Field(default_factory=dict)


class VideoGenerationResult(BaseModel):
    """统一响应格式"""
    success: bool
    task_id: Optional[str] = None
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    status: str = "submitted"  # submitted/processing/completed/failed
    progress: int = 0
    error_message: Optional[str] = None
    provider_info: Dict[str, Any] = Field(default_factory=dict)


class BaseVideoProvider(ABC):
    """视频提供商抽象基类"""
    
    provider_type: str
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "")
        self.session = None
    
    @abstractmethod
    async def generate_video(
        self, 
        request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """提交视频生成任务"""
        pass
    
    @abstractmethod
    async def check_status(
        self, 
        task_id: str
    ) -> VideoGenerationResult:
        """查询任务状态"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """获取提供商能力"""
        pass
    
    async def close(self):
        """清理资源"""
        if self.session:
            await self.session.close()
