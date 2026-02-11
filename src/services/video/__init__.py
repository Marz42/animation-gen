"""
统一视频服务
支持多提供商，自动选择/切换
"""
import os
from typing import Optional, Dict, Any
from pathlib import Path

from .providers import create_video_provider, get_available_providers
from .providers.base import (
    VideoGenerationRequest, VideoGenerationResult,
    VideoDuration, VideoResolution, VideoProviderType
)


class VideoService:
    """统一视频服务"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化视频服务
        
        Args:
            config: 配置字典，如果不提供则从环境变量读取
        """
        if config is None:
            config = self._load_config_from_env()
        
        self.config = config
        self.default_provider_type = config.get("default", "jiekouai")
        self.default_provider = self._create_provider(self.default_provider_type)
        
        # 活跃任务映射: task_id -> provider
        self.active_tasks: Dict[str, Any] = {}
    
    def _load_config_from_env(self) -> Dict:
        """从环境变量加载配置"""
        return {
            "default": os.getenv("VIDEO_PROVIDER", "jiekouai"),
            "jiekouai": {
                "api_key": os.getenv("JIEKOUAI_API_KEY", ""),
                "base_url": "https://api.jiekou.ai",
                "upload_base_url": "http://localhost:8000/static/temp",
                "temp_dir": "/tmp/animation_gen/video",
            }
        }
    
    def _create_provider(self, provider_type: str):
        """创建提供商实例"""
        provider_config = self.config.get(provider_type, {})
        return create_video_provider(provider_type, provider_config)
    
    def _normalize_duration(self, duration: str) -> VideoDuration:
        """标准化时长"""
        duration_map = {
            "4s": VideoDuration.SECONDS_4,
            "8s": VideoDuration.SECONDS_8,
            "12s": VideoDuration.SECONDS_12,
        }
        return duration_map.get(duration, VideoDuration.SECONDS_4)
    
    def _normalize_resolution(self, size: str) -> VideoResolution:
        """标准化分辨率"""
        # 直接映射到 API 支持的格式
        resolution_map = {
            "720p": VideoResolution.P720,
            "1080p": VideoResolution.P1080,
            # 兼容旧格式
            "1280x720": VideoResolution.P720,
            "1920x1080": VideoResolution.P1080,
        }
        return resolution_map.get(size, VideoResolution.P720)
    
    def get_capabilities(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """获取提供商能力"""
        if provider:
            p = self._create_provider(provider)
        else:
            p = self.default_provider
        return p.get_capabilities()
    
    async def generate_video(
        self,
        prompt: str,
        first_frame_path: Optional[str] = None,
        duration: str = "5s",
        size: str = "512x512",
        watermark: bool = False,
        provider: Optional[str] = None,
        provider_params: Optional[Dict] = None
    ) -> VideoGenerationResult:
        """
        生成视频
        
        Args:
            prompt: 视频描述提示词
            first_frame_path: 首帧图片路径
            duration: 时长 (4s/5s/6s/8s/10s)
            size: 尺寸 (如 512x512, 1280x720)
            watermark: 是否添加水印
            provider: 指定提供商，默认使用配置中的默认提供商
            provider_params: 提供商特定参数
        
        Returns:
            生成结果
        """
        # 选择提供商
        if provider:
            video_provider = self._create_provider(provider)
        else:
            video_provider = self.default_provider
        
        # 转换参数
        request = VideoGenerationRequest(
            prompt=prompt,
            image_path=first_frame_path,
            duration=self._normalize_duration(duration),
            resolution=self._normalize_resolution(size),
            watermark=watermark,
            provider_params=provider_params or {}
        )
        
        # 提交任务
        result = await video_provider.generate_video(request)
        
        # 记录任务对应的提供商
        if result.task_id:
            self.active_tasks[result.task_id] = video_provider
        
        return result
    
    async def check_status(self, task_id: str) -> VideoGenerationResult:
        """
        检查任务状态
        
        自动路由到正确的提供商
        """
        provider = self.active_tasks.get(task_id, self.default_provider)
        return await provider.check_status(task_id)
    
    async def download_video(self, video_url: str, output_path: str) -> bool:
        """
        下载视频到本地
        
        Args:
            video_url: 视频URL
            output_path: 本地保存路径
        
        Returns:
            是否成功
        """
        import aiohttp
        import aiofiles
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        # 确保目录存在
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        
                        async with aiofiles.open(output_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        print(f"✅ 视频已下载: {output_path}")
                        return True
                    else:
                        print(f"❌ 下载失败: HTTP {resp.status}")
                        return False
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            return False
    
    def estimate_cost(self, shot_count: int, duration: str = "5s") -> Dict[str, Any]:
        """
        估算成本
        
        基于接口AI定价：
        - 10秒视频：$0.20
        """
        # 接口AI Sora 2 定价（约）
        cost_per_video = 0.20  # $0.20 per 10s video
        
        # 计算总秒数
        seconds = int(duration.replace("s", ""))
        total_seconds = shot_count * seconds
        
        total_cost = shot_count * cost_per_video
        
        return {
            "shot_count": shot_count,
            "total_seconds": total_seconds,
            "estimated_cost_usd": round(total_cost, 2),
            "provider": self.default_provider_type
        }
    
    async def close(self):
        """清理资源"""
        await self.default_provider.close()
        for provider in self.active_tasks.values():
            await provider.close()
