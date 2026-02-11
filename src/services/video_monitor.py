"""
视频生成状态监控服务
自动轮询已提交的视频生成任务，更新状态并下载完成的视频
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import aiohttp

from src.services.video import VideoService
from src.core.project_manager import ProjectManager
from src.core.config import Config

project_manager = ProjectManager()


class VideoMonitorService:
    """视频状态监控服务"""
    
    def __init__(self):
        self.running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._poll_interval = 30  # 轮询间隔（秒）
        self._video_service_cache: Dict[str, VideoService] = {}
    
    async def start(self):
        """启动监控服务"""
        if self.running:
            return
        
        self.running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        print("✅ 视频状态监控服务已启动")
    
    async def stop(self):
        """停止监控服务"""
        self.running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有缓存的视频服务
        for service in self._video_service_cache.values():
            await service.close()
        self._video_service_cache.clear()
        
        print("⏹️ 视频状态监控服务已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                await self._check_all_pending_videos()
            except Exception as e:
                print(f"❌ 视频监控循环异常: {e}")
            
            await asyncio.sleep(self._poll_interval)
    
    async def _check_all_pending_videos(self):
        """检查所有待处理的视频"""
        # 获取所有项目
        projects = project_manager.list_projects()
        
        for project in projects:
            try:
                # project 已经是 Project 对象，不需要再加载
                shots = project_manager.load_shots(project)
                
                for shot in shots:
                    await self._check_shot_videos(project, shot)
                    
            except Exception as e:
                print(f"❌ 检查项目 {project.project_id if hasattr(project, 'project_id') else 'unknown'} 失败: {e}")
    
    async def _check_shot_videos(self, project, shot):
        """检查单个分镜的视频状态"""
        batch = shot.get_current_batch()
        if not batch or not batch.get("videos"):
            return
        
        need_update = False
        
        for video in batch["videos"]:
            # 只检查 submitted 或 processing 状态的视频
            if video.get("status") not in ["submitted", "processing"]:
                continue
            
            task_id = video.get("task_id")
            if not task_id:
                continue
            
            try:
                # 获取视频服务
                provider = video.get("provider", "jiekouai")
                video_service = await self._get_video_service(provider)
                
                # 查询状态
                result = await video_service.check_status(task_id)
                
                # 更新状态
                if result.status != video.get("status"):
                    video["status"] = result.status
                    video["progress"] = result.progress
                    need_update = True
                    
                    print(f"📊 分镜 {shot.shot_id} 视频状态更新: {result.status}")
                
                # 如果完成，下载视频
                if result.status == "completed" and result.video_url and not video.get("local_path"):
                    await self._download_video(project, shot, video, result.video_url, video_service)
                    need_update = True
                
                # 如果失败，记录错误
                if result.status == "failed" and result.error_message:
                    video["error"] = result.error_message
                    need_update = True
                    
            except Exception as e:
                print(f"❌ 检查视频 {task_id} 失败: {e}")
        
        # 如果需要更新，保存到数据库
        if need_update:
            project_manager.update_shot(project, shot)
    
    async def _get_video_service(self, provider: str) -> VideoService:
        """获取或创建视频服务"""
        if provider not in self._video_service_cache:
            video_config = self._get_video_config(provider)
            self._video_service_cache[provider] = VideoService(video_config)
        
        return self._video_service_cache[provider]
    
    def _get_video_config(self, provider: str) -> dict:
        """获取视频服务配置"""
        if provider == "mock":
            return {
                "default": "mock",
                "mock": {"simulate_delay": 2}
            }
        else:
            # 真实提供商配置
            return {
                "default": "jiekouai",
                "jiekouai": {
                    "api_key": os.getenv("JIEKOUAI_API_KEY", ""),
                    "base_url": "https://api.jiekou.ai",
                }
            }
    
    async def _download_video(self, project, shot, video, video_url, video_service):
        """下载完成的视频"""
        try:
            output_dir = Path(project.root_path) / "04_videos"
            output_dir.mkdir(exist_ok=True)
            
            task_id = video.get("task_id", "unknown")
            output_path = output_dir / f"{shot.shot_id}_{task_id[:8]}.mp4"
            
            print(f"⬇️ 下载视频: {shot.shot_id} -> {output_path}")
            
            success = await video_service.download_video(video_url, str(output_path))
            
            if success:
                video["local_path"] = str(output_path)
                shot.status = "completed"
                print(f"✅ 视频下载完成: {output_path}")
            else:
                video["error"] = "视频下载失败"
                print(f"❌ 视频下载失败: {shot.shot_id}")
                
        except Exception as e:
            video["error"] = f"下载异常: {str(e)}"
            print(f"❌ 下载视频异常: {e}")


# 全局监控服务实例
_video_monitor: Optional[VideoMonitorService] = None


def get_video_monitor() -> VideoMonitorService:
    """获取视频监控服务实例"""
    global _video_monitor
    if _video_monitor is None:
        _video_monitor = VideoMonitorService()
    return _video_monitor
