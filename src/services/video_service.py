"""
视频生成服务
支持接口AI的Sora-2-Video-Reverse API
"""

import asyncio
import aiohttp
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
from enum import Enum

from src.core.config import Config, settings


class VideoDuration(str, Enum):
    """视频时长选项"""
    SECONDS_4 = "4s"
    SECONDS_5 = "5s"
    SECONDS_6 = "6s"
    SECONDS_8 = "8s"
    SECONDS_10 = "10s"


class JiekouAIVideoService:
    """
    接口AI视频生成服务
    
    API端点: POST https://api.jiekou.ai/v3/async/sora-2-video-reverse
    
    请求体:
    {
        "prompt": "视频描述",
        "image": "base64编码的图片或图片URL",
        "duration": 5,
        "size": "512x512",
        "watermark": false,
        "character_url": "可选的角色参考图URL",
        "character_timestamps": "可选的时间戳"
    }
    """
    
    # 支持的尺寸
    SUPPORTED_SIZES = ["480x480", "512x512", "720x480", "1280x720"]
    
    # 时长映射 (秒)
    DURATION_MAP = {
        VideoDuration.SECONDS_4: 4,
        VideoDuration.SECONDS_5: 5,
        VideoDuration.SECONDS_6: 6,
        VideoDuration.SECONDS_8: 8,
        VideoDuration.SECONDS_10: 10
    }
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.jiekou.ai"):
        self.api_key = api_key or settings.jiekouai_api_key
        self.base_url = base_url.rstrip('/')
        self.endpoint = "/v3/async/sora-2-video-reverse"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _image_to_base64(self, image_path: Path) -> str:
        """将图片转为base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    async def generate_video(
        self,
        prompt: str,
        image_path: Path,
        duration: VideoDuration = VideoDuration.SECONDS_5,
        size: str = "512x512",
        watermark: bool = False,
        character_url: Optional[str] = None,
        character_timestamps: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        提交视频生成任务
        
        Args:
            prompt: 视频描述提示词
            image_path: 首帧图片路径（本地文件）
            duration: 视频时长
            size: 视频尺寸
            watermark: 是否添加水印
            character_url: 可选的角色参考图URL
            character_timestamps: 可选的时间戳标记
        
        Returns:
            包含任务ID和状态的字典
        """
        session = await self._get_session()
        
        # 读取图片并转为base64
        try:
            image_base64 = self._image_to_base64(image_path)
            # 添加data URI前缀
            image_data = f"data:image/png;base64,{image_base64}"
        except Exception as e:
            return {
                "success": False,
                "error": f"读取图片失败: {str(e)}"
            }
        
        # 构建请求体
        payload = {
            "prompt": prompt,
            "image": image_data,
            "duration": self.DURATION_MAP.get(duration, 5),
            "size": size if size in self.SUPPORTED_SIZES else "512x512",
            "watermark": watermark
        }
        
        # 可选参数
        if character_url:
            payload["character_url"] = character_url
        if character_timestamps:
            payload["character_timestamps"] = character_timestamps
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        url = f"{self.base_url}{self.endpoint}"
        
        try:
            print(f"🎥 提交视频生成任务: {prompt[:50]}...")
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)  # 60秒超时
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        return {
                            "success": True,
                            "task_id": data.get("task_id") or data.get("id"),
                            "status": "submitted",
                            "raw_response": data
                        }
                    except:
                        return {
                            "success": True,
                            "status": "submitted",
                            "raw_response": response_text
                        }
                else:
                    return {
                        "success": False,
                        "error": f"API错误: {response.status} - {response_text}",
                        "status": "failed"
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "提交任务超时",
                "status": "failed"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"请求异常: {str(e)}",
                "status": "failed"
            }
    
    async def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态
        
        接口AI的异步任务查询接口
        """
        session = await self._get_session()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 假设查询接口为 /v3/async/status/{task_id}
        # 实际接口可能需要根据接口AI文档调整
        url = f"{self.base_url}/v3/async/status/{task_id}"
        
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "status": data.get("status"),  # pending/processing/completed/failed
                        "video_url": data.get("video_url"),
                        "progress": data.get("progress", 0)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"查询失败: {response.status}"
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "查询超时"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"查询异常: {str(e)}"
            }
    
    async def download_video(self, video_url: str, output_path: Path) -> bool:
        """下载视频到本地"""
        session = await self._get_session()
        
        try:
            async with session.get(video_url) as response:
                if response.status == 200:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(await response.read())
                    print(f"✅ 视频下载完成: {output_path}")
                    return True
                else:
                    print(f"❌ 下载失败: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            return False


class VideoService:
    """视频生成服务统一接口"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load_global()
        # 默认使用接口AI
        self.provider = JiekouAIVideoService(
            api_key=settings.jiekouai_api_key,
            base_url=settings.jiekouai_base_url or "https://api.jiekou.ai"
        )
    
    async def generate_video(
        self,
        prompt: str,
        first_frame_path: Path,
        duration: str = "5s",
        size: str = "512x512",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成视频
        
        Args:
            prompt: 视频描述
            first_frame_path: 首帧图片路径
            duration: 视频时长 (4s/5s/6s/8s/10s)
            size: 视频尺寸
        
        Returns:
            任务结果
        """
        duration_enum = VideoDuration(duration)
        return await self.provider.generate_video(
            prompt=prompt,
            image_path=first_frame_path,
            duration=duration_enum,
            size=size,
            **kwargs
        )
    
    async def batch_generate_videos(
        self,
        shots: List[Dict[str, Any]],
        output_dir: Path,
        duration: str = "5s",
        size: str = "512x512"
    ) -> List[Dict[str, Any]]:
        """
        批量生成视频
        
        Args:
            shots: 分镜列表，每个分镜包含 shot_id, prompt, keyframe_path
            output_dir: 输出目录
            duration: 视频时长
            size: 视频尺寸
        
        Returns:
            生成结果列表
        """
        results = []
        
        for shot in shots:
            shot_id = shot.get("shot_id")
            prompt = shot.get("prompt", "")
            keyframe_path = Path(shot.get("keyframe_path", ""))
            
            if not keyframe_path.exists():
                results.append({
                    "shot_id": shot_id,
                    "success": False,
                    "error": "首帧图片不存在"
                })
                continue
            
            result = await self.generate_video(
                prompt=prompt,
                first_frame_path=keyframe_path,
                duration=duration,
                size=size
            )
            
            results.append({
                "shot_id": shot_id,
                **result
            })
        
        return results
    
    def estimate_cost(self, shot_count: int, duration: str = "5s") -> Dict[str, Any]:
        """
        估算视频生成成本
        
        Args:
            shot_count: 分镜数量
            duration: 每个分镜的时长
        
        Returns:
            成本估算
        """
        # 接口AI Sora-2 定价参考（示例）
        seconds = int(duration.replace("s", ""))
        cost_per_second = 0.05  # $0.05 per second (示例价格)
        
        total_seconds = shot_count * seconds
        estimated_cost = total_seconds * cost_per_second
        
        return {
            "shot_count": shot_count,
            "total_seconds": total_seconds,
            "estimated_cost_usd": round(estimated_cost, 2),
            "provider": "jiekouai-sora2"
        }
    
    async def close(self):
        """关闭服务"""
        await self.provider.close()
