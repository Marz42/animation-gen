"""
接口AI Sora 2 Img2Video 提供商（异步版）
"""
import aiohttp
import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .base import (
    BaseVideoProvider, VideoGenerationRequest,
    VideoGenerationResult, VideoDuration, VideoResolution
)


class JiekouaiVideoProvider(BaseVideoProvider):
    """接口AI Sora 2 Img2Video 实现 - 使用正确的异步端点"""
    
    provider_type = "jiekouai"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    
    def get_capabilities(self) -> Dict[str, Any]:
        from .config import JIEKOUAI_SORA2_CONFIG
        return {
            "supports_image_input": True,
            "image_format": "base64",
            "durations": JIEKOUAI_SORA2_CONFIG.duration_param.options,
            "resolutions": JIEKOUAI_SORA2_CONFIG.resolution_param.options,
            "max_prompt_length": 2000,
            "supports_watermark": False,
            "requires_upload": False,
            "async_only": True,
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _image_to_base64(self, image_path: str) -> str:
        """将图片转为 base64"""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def _normalize_duration(self, duration: VideoDuration) -> int:
        """转换时长到 API 要求的整数值"""
        # 接口AI Sora-2 支持: 4, 8, 12 秒
        duration_map = {
            VideoDuration.SECONDS_4: 4,
            VideoDuration.SECONDS_8: 8,
            VideoDuration.SECONDS_12: 12,
        }
        return duration_map.get(duration, 4)  # 默认4秒
    
    def _normalize_resolution(self, resolution: VideoResolution) -> str:
        """转换分辨率到 API 要求的格式"""
        # 接口AI Sora-2 支持: 720p, 1080p
        resolution_map = {
            VideoResolution.P720: "720p",
            VideoResolution.P1080: "1080p",
        }
        return resolution_map.get(resolution, "720p")  # 默认720p
    
    async def generate_video(
        self, 
        request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """提交视频生成任务"""
        try:
            session = await self._get_session()
            
            # 转换参数
            actual_duration = self._normalize_duration(request.duration)
            actual_resolution = self._normalize_resolution(request.resolution)
            
            # 准备图片 - 转为 base64
            image_base64 = None
            if request.image_path and os.path.exists(request.image_path):
                image_base64 = self._image_to_base64(request.image_path)
                print(f"📤 图片已转换: {request.image_path} -> {len(image_base64)} chars base64")
            else:
                return VideoGenerationResult(
                    success=False,
                    status="failed",
                    error_message=f"图片不存在: {request.image_path}"
                )
            
            # 构造请求
            payload = {
                "prompt": request.prompt,
                "image": image_base64,
                "duration": actual_duration,
                "resolution": actual_resolution,
                "professional": False,  # 使用普通版
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 正确的端点
            url = f"{self.base_url}/v3/async/sora-2-img2video"
            
            print(f"🎬 提交视频生成任务: {url}")
            print(f"   Prompt: {request.prompt[:80]}...")
            print(f"   Duration: {actual_duration}s, Resolution: {actual_resolution}")
            
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                response_data = await resp.json()
                
                if resp.status != 200:
                    error_msg = response_data.get("error", "未知错误")
                    print(f"❌ API调用失败: {error_msg}")
                    return VideoGenerationResult(
                        success=False,
                        status="failed",
                        error_message=f"API错误: {error_msg}"
                    )
                
                task_id = response_data.get("task_id")
                
                print(f"✅ 视频任务已提交: task_id={task_id}")
                
                return VideoGenerationResult(
                    success=True,
                    task_id=task_id,
                    status="submitted",
                    provider_info={
                        "raw_response": response_data,
                        "provider": "jiekouai",
                        "duration": actual_duration,
                        "resolution": actual_resolution,
                    }
                )
                
        except Exception as e:
            print(f"❌ 视频生成异常: {e}")
            import traceback
            traceback.print_exc()
            return VideoGenerationResult(
                success=False,
                status="failed",
                error_message=str(e)
            )
    
    async def check_status(self, task_id: str) -> VideoGenerationResult:
        """查询任务状态"""
        try:
            session = await self._get_session()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 正确的状态查询端点 (从 N8N 配置获取)
            url = f"{self.base_url}/v3/async/task-result?task_id={task_id}"
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return VideoGenerationResult(
                        success=False,
                        task_id=task_id,
                        status="failed",
                        error_message=f"API错误: {text[:200]}"
                    )
                
                response_data = await resp.json()
                
                # 解析任务状态
                task_info = response_data.get("task", {})
                status = task_info.get("status", "unknown")
                
                # 状态映射
                status_map = {
                    "TASK_STATUS_PENDING": "submitted",
                    "TASK_STATUS_PROCESSING": "processing",
                    "TASK_STATUS_SUCCEED": "completed",
                    "TASK_STATUS_FAILED": "failed",
                }
                normalized_status = status_map.get(status, status.lower())
                
                result = VideoGenerationResult(
                    success=normalized_status != "failed",
                    task_id=task_id,
                    status=normalized_status,
                    progress=task_info.get("progress_percent", 0),
                    provider_info={"raw_response": response_data}
                )
                
                # 如果完成，提取视频URL
                if normalized_status == "completed":
                    videos = response_data.get("videos", [])
                    if videos:
                        result.video_url = videos[0].get("video_url")
                
                # 如果失败，提取错误信息
                if normalized_status == "failed":
                    result.error_message = task_info.get("reason", "未知错误")
                
                return result
                
        except Exception as e:
            print(f"❌ 检查状态异常: {e}")
            import traceback
            traceback.print_exc()
            return VideoGenerationResult(
                success=False,
                task_id=task_id,
                status="unknown",
                error_message=str(e)
            )
