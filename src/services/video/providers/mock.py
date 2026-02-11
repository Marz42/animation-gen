"""
模拟视频生成提供商（用于测试）
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, Any

from .base import (
    BaseVideoProvider, VideoProviderType, VideoGenerationRequest,
    VideoGenerationResult
)


class MockVideoProvider(BaseVideoProvider):
    """模拟视频提供商 - 用于测试流程"""
    
    provider_type = "mock"  # 直接使用字符串
    
    # 模拟任务存储
    _tasks: Dict[str, Dict] = {}
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.simulate_delay = config.get("simulate_delay", 2)  # 模拟延迟秒数
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "supports_image_input": True,
            "image_format": "url_or_path",
            "durations": ["4s", "8s", "12s"],
            "resolutions": ["720p", "1080p"],
            "max_prompt_length": 2000,
            "supports_watermark": True,
            "requires_upload": False,
            "async_only": True,
            "mock": True,
        }
    
    async def generate_video(
        self, 
        request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """模拟提交视频生成任务"""
        # 生成模拟 task_id
        task_id = f"mock_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
        
        # 存储任务信息
        MockVideoProvider._tasks[task_id] = {
            "prompt": request.prompt,
            "image_path": request.image_path,
            "duration": request.duration.value,
            "resolution": request.resolution.value,
            "created_at": datetime.now(),
            "status": "submitted",
            "progress": 0,
        }
        
        print(f"🎬 [MOCK] 视频任务已创建: {task_id}")
        print(f"   Prompt: {request.prompt[:60]}...")
        print(f"   Duration: {request.duration.value}, Size: {request.resolution.value}")
        
        # 启动后台任务模拟进度
        asyncio.create_task(self._simulate_progress(task_id))
        
        return VideoGenerationResult(
            success=True,
            task_id=task_id,
            status="submitted",
            provider_info={
                "provider": "mock",
                "duration": request.duration.value,
                "size": request.resolution.value,
            }
        )
    
    async def _simulate_progress(self, task_id: str):
        """模拟任务进度"""
        await asyncio.sleep(1)  # 初始等待
        
        task = MockVideoProvider._tasks.get(task_id)
        if not task:
            return
        
        # 模拟处理中状态
        task["status"] = "processing"
        
        # 模拟进度增长
        for progress in [10, 25, 50, 75, 90]:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            task["progress"] = progress
        
        # 模拟完成
        await asyncio.sleep(1)
        task["status"] = "completed"
        task["progress"] = 100
        task["video_url"] = f"http://localhost:8000/static/mock_videos/{task_id}.mp4"
        task["completed_at"] = datetime.now()
        
        print(f"✅ [MOCK] 视频任务完成: {task_id}")
    
    async def check_status(self, task_id: str) -> VideoGenerationResult:
        """查询模拟任务状态"""
        task = MockVideoProvider._tasks.get(task_id)
        
        if not task:
            return VideoGenerationResult(
                success=False,
                task_id=task_id,
                status="failed",
                error_message="Task not found"
            )
        
        return VideoGenerationResult(
            success=task["status"] != "failed",
            task_id=task_id,
            status=task["status"],
            progress=task.get("progress", 0),
            video_url=task.get("video_url"),
            provider_info={
                "provider": "mock",
                "mock_data": task,
            }
        )
