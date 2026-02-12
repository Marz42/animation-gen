"""
批量生成流水线服务
支持无人值守的批量首帧生成 + 视频生成
自动处理任务依赖、失败重试、状态持久化
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid
import logging

from src.core.project_manager import ProjectManager
from src.core.task_queue import get_queue, TaskPriority
from src.models.schemas import Project, Shot, VideoDuration
from src.services.video.providers.base import VideoResolution
from src.services.image_service import ImageService
from src.services.video import VideoService

logger = logging.getLogger(__name__)


class BatchTaskStatus(str, Enum):
    """批量任务状态"""
    PENDING = "pending"              # 等待开始
    WAITING_KEYFRAME = "waiting_keyframe"  # 等待首帧完成
    KEYFRAME_GENERATING = "keyframe_generating"  # 首帧生成中
    KEYFRAME_FAILED = "keyframe_failed"      # 首帧生成失败
    WAITING_VIDEO = "waiting_video"          # 等待视频生成
    VIDEO_GENERATING = "video_generating"    # 视频生成中
    VIDEO_FAILED = "video_failed"            # 视频生成失败
    COMPLETED = "completed"                  # 全部完成
    CANCELLED = "cancelled"                  # 已取消


@dataclass
class BatchTask:
    """单个批量任务"""
    task_id: str
    project_id: str
    shot_id: str
    sequence: int  # 执行顺序
    
    # 状态
    status: BatchTaskStatus = BatchTaskStatus.PENDING
    
    # 首帧生成
    keyframe_attempts: int = 0
    max_keyframe_attempts: int = 3
    keyframe_error: Optional[str] = None
    
    # 视频生成
    video_attempts: int = 0
    max_video_attempts: int = 3
    video_error: Optional[str] = None
    video_task_id: Optional[str] = None
    
    # 配置
    duration: str = "4s"
    size: str = "720p"
    watermark: bool = False
    provider: Optional[str] = None
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    keyframe_completed_at: Optional[datetime] = None
    video_completed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "shot_id": self.shot_id,
            "sequence": self.sequence,
            "status": self.status.value,
            "keyframe_attempts": self.keyframe_attempts,
            "max_keyframe_attempts": self.max_keyframe_attempts,
            "keyframe_error": self.keyframe_error,
            "video_attempts": self.video_attempts,
            "max_video_attempts": self.max_video_attempts,
            "video_error": self.video_error,
            "video_task_id": self.video_task_id,
            "duration": self.duration,
            "size": self.size,
            "watermark": self.watermark,
            "provider": self.provider,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "keyframe_completed_at": self.keyframe_completed_at.isoformat() if self.keyframe_completed_at else None,
            "video_completed_at": self.video_completed_at.isoformat() if self.video_completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BatchTask":
        """从字典创建"""
        task = cls(
            task_id=data["task_id"],
            project_id=data["project_id"],
            shot_id=data["shot_id"],
            sequence=data["sequence"],
            status=BatchTaskStatus(data["status"]),
            keyframe_attempts=data.get("keyframe_attempts", 0),
            max_keyframe_attempts=data.get("max_keyframe_attempts", 3),
            keyframe_error=data.get("keyframe_error"),
            video_attempts=data.get("video_attempts", 0),
            max_video_attempts=data.get("max_video_attempts", 3),
            video_error=data.get("video_error"),
            video_task_id=data.get("video_task_id"),
            duration=data.get("duration", "4s"),
            size=data.get("size", "720p"),
            watermark=data.get("watermark", False),
            provider=data.get("provider"),
        )
        task.created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("keyframe_completed_at"):
            task.keyframe_completed_at = datetime.fromisoformat(data["keyframe_completed_at"])
        if data.get("video_completed_at"):
            task.video_completed_at = datetime.fromisoformat(data["video_completed_at"])
        return task


@dataclass
class BatchJob:
    """批量作业"""
    job_id: str
    name: str
    project_id: str
    tasks: List[BatchTask] = field(default_factory=list)
    status: str = "pending"  # pending / running / paused / completed / failed
    
    # 统计
    completed_count: int = 0
    failed_count: int = 0
    
    # 配置
    auto_retry: bool = True
    sequential: bool = False  # True=顺序执行, False=并行执行
    max_parallel: int = 2     # 最大并行数
    
    # 回调
    on_task_complete: Optional[Callable] = None
    on_task_failed: Optional[Callable] = None
    on_job_complete: Optional[Callable] = None
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "project_id": self.project_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "status": self.status,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "auto_retry": self.auto_retry,
            "sequential": self.sequential,
            "max_parallel": self.max_parallel,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BatchJob":
        """从字典创建"""
        job = cls(
            job_id=data["job_id"],
            name=data["name"],
            project_id=data["project_id"],
            tasks=[BatchTask.from_dict(t) for t in data.get("tasks", [])],
            status=data.get("status", "pending"),
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            auto_retry=data.get("auto_retry", True),
            sequential=data.get("sequential", False),
            max_parallel=data.get("max_parallel", 2),
        )
        job.created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        if data.get("started_at"):
            job.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            job.completed_at = datetime.fromisoformat(data["completed_at"])
        return job
    
    @property
    def total_tasks(self) -> int:
        return len(self.tasks)
    
    @property
    def progress_percentage(self) -> float:
        if not self.tasks:
            return 0.0
        return ((self.completed_count + self.failed_count) / len(self.tasks)) * 100


class BatchPipelineService:
    """
    批量生成流水线服务
    
    功能：
    1. 自动处理首帧生成 → 视频生成的依赖关系
    2. 支持失败自动重试（指数退避）
    3. 支持任务状态持久化（服务重启后可恢复）
    4. 支持顺序或并行执行模式
    5. 支持批量任务进度监控
    """
    
    PERSISTENCE_DIR = Path.home() / ".animation_gen" / "batch_jobs"
    
    def __init__(self):
        self.project_manager = ProjectManager()
        self.active_jobs: Dict[str, BatchJob] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self.PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """启动服务"""
        if self._running:
            return
        
        self._running = True
        
        # 恢复未完成的作业
        await self._recover_pending_jobs()
        
        # 启动监控循环
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("✅ 批量流水线服务已启动")
    
    async def stop(self):
        """停止服务"""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # 保存所有活跃作业
        for job in self.active_jobs.values():
            self._save_job(job)
        
        logger.info("⏹️ 批量流水线服务已停止")
    
    async def create_batch_job(
        self,
        project_id: str,
        shot_ids: List[str],
        name: Optional[str] = None,
        duration: str = "4s",
        size: str = "720p",
        watermark: bool = False,
        provider: Optional[str] = None,
        auto_retry: bool = True,
        sequential: bool = False,
        max_parallel: int = 2
    ) -> BatchJob:
        """
        创建批量作业
        
        Args:
            shot_ids: 需要处理的分镜ID列表
            name: 作业名称
            duration: 视频时长
            size: 视频尺寸
            watermark: 是否添加水印
            provider: 视频提供商
            auto_retry: 失败时自动重试
            sequential: 是否顺序执行
            max_parallel: 最大并行数
        """
        project = self.project_manager.load_project(project_id)
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        # 创建作业
        job_id = f"batch_{uuid.uuid4().hex[:12]}"
        job_name = name or f"批量生成_{datetime.now().strftime('%m%d_%H%M')}"
        
        job = BatchJob(
            job_id=job_id,
            name=job_name,
            project_id=project_id,
            auto_retry=auto_retry,
            sequential=sequential,
            max_parallel=max_parallel
        )
        
        # 创建任务
        for i, shot_id in enumerate(shot_ids):
            task = BatchTask(
                task_id=f"{job_id}_task_{i+1:03d}",
                project_id=project_id,
                shot_id=shot_id,
                sequence=i,
                duration=duration,
                size=size,
                watermark=watermark,
                provider=provider
            )
            job.tasks.append(task)
        
        # 保存并启动
        self.active_jobs[job_id] = job
        self._save_job(job)
        
        # 立即开始处理
        asyncio.create_task(self._process_job(job))
        
        logger.info(f"✅ 批量作业创建完成: {job_id}, {len(shot_ids)} 个任务")
        return job
    
    async def _process_job(self, job: BatchJob):
        """处理批量作业"""
        job.status = "running"
        job.started_at = datetime.now()
        self._save_job(job)
        
        try:
            if job.sequential:
                # 顺序执行
                for task in job.tasks:
                    if not self._running or job.status == "paused":
                        break
                    await self._process_task(task, job)
            else:
                # 并行执行（限制并发数）
                semaphore = asyncio.Semaphore(job.max_parallel)
                
                async def process_with_limit(task: BatchTask):
                    async with semaphore:
                        await self._process_task(task, job)
                
                await asyncio.gather(*[
                    process_with_limit(task) for task in job.tasks
                    if task.status not in [BatchTaskStatus.COMPLETED, BatchTaskStatus.CANCELLED]
                ])
            
            # 检查是否全部完成
            all_done = all(
                t.status in [BatchTaskStatus.COMPLETED, BatchTaskStatus.CANCELLED, BatchTaskStatus.KEYFRAME_FAILED, BatchTaskStatus.VIDEO_FAILED]
                for t in job.tasks
            )
            
            if all_done:
                job.status = "completed" if job.failed_count == 0 else "failed"
                job.completed_at = datetime.now()
                
                if job.on_job_complete:
                    await job.on_job_complete(job)
                
                logger.info(f"✅ 批量作业完成: {job.job_id}")
            
        except Exception as e:
            logger.error(f"❌ 批量作业处理异常: {e}")
            job.status = "failed"
        
        self._save_job(job)
    
    async def _process_task(self, task: BatchTask, job: BatchJob):
        """处理单个任务（首帧 + 视频）"""
        task.started_at = datetime.now()
        
        try:
            # 阶段1: 生成首帧
            await self._generate_keyframe(task, job)
            
            if task.status == BatchTaskStatus.KEYFRAME_FAILED:
                # 首帧失败，检查是否需要重试
                if job.auto_retry and task.keyframe_attempts < task.max_keyframe_attempts:
                    await asyncio.sleep(2 ** task.keyframe_attempts)  # 指数退避
                    await self._generate_keyframe(task, job)
                
                if task.status == BatchTaskStatus.KEYFRAME_FAILED:
                    job.failed_count += 1
                    if job.on_task_failed:
                        await job.on_task_failed(task, job)
                    return
            
            # 阶段2: 生成视频
            await self._generate_video(task, job)
            
            if task.status == BatchTaskStatus.VIDEO_FAILED:
                # 视频失败，检查是否需要重试
                if job.auto_retry and task.video_attempts < task.max_video_attempts:
                    await asyncio.sleep(2 ** task.video_attempts)  # 指数退避
                    await self._generate_video(task, job)
                
                if task.status == BatchTaskStatus.VIDEO_FAILED:
                    job.failed_count += 1
                    if job.on_task_failed:
                        await job.on_task_failed(task, job)
                    return
            
            # 任务完成
            if task.status == BatchTaskStatus.COMPLETED:
                job.completed_count += 1
                if job.on_task_complete:
                    await job.on_task_complete(task, job)
            
        except Exception as e:
            logger.error(f"❌ 任务 {task.task_id} 处理异常: {e}")
            task.status = BatchTaskStatus.VIDEO_FAILED
            task.video_error = str(e)
            job.failed_count += 1
        
        self._save_job(job)
    
    async def _generate_keyframe(self, task: BatchTask, job: BatchJob):
        """生成首帧"""
        task.status = BatchTaskStatus.KEYFRAME_GENERATING
        task.keyframe_attempts += 1
        self._save_job(job)
        
        try:
            project = self.project_manager.load_project(task.project_id)
            shots = self.project_manager.load_shots(project)
            shot = next((s for s in shots if s.shot_id == task.shot_id), None)
            
            if not shot:
                raise ValueError(f"分镜不存在: {task.shot_id}")
            
            # 检查是否已有审核通过的首帧
            batch = shot.get_current_batch()
            if batch and batch.get("keyframe") and batch["keyframe"].get("status") == "approved":
                logger.info(f"✅ 任务 {task.task_id} 已有审核通过的首帧，跳过")
                task.status = BatchTaskStatus.WAITING_VIDEO
                task.keyframe_completed_at = datetime.now()
                return
            
            # 提交首帧生成任务到队列
            async def do_generate():
                image_service = ImageService()
                try:
                    # 获取参考图
                    characters = self.project_manager.load_characters(project)
                    scenes = self.project_manager.load_scenes(project)
                    
                    char_refs = {c.character_id: c.get_current_version().path for c in characters if c.get_current_version()}
                    scene_refs = {s.scene_id: s.get_current_version().path for s in scenes if s.get_current_version()}
                    
                    shot_char_refs = {cid: char_refs[cid] for cid in shot.characters if cid in char_refs}
                    scene_ref = scene_refs.get(shot.scene_id)
                    
                    # 生成首帧
                    batch_id = shot.create_batch()
                    output_path = Path(project.root_path) / "03_keyframes" / f"{shot.shot_id}_{batch_id}.png"
                    
                    actual_path = await image_service.generate_keyframe(
                        shot, shot_char_refs, scene_ref, output_path
                    )
                    
                    if actual_path:
                        batch = shot.get_current_batch()
                        if batch:
                            batch["keyframe"] = {
                                "status": "completed",
                                "path": str(actual_path),
                                "prompt": shot.image_prompt.positive if shot.image_prompt else "",
                            }
                        shot.status = "frame_pending_review"
                        self.project_manager.update_shot(project, shot)
                        return True
                    else:
                        return False
                        
                finally:
                    await image_service.close()
            
            # 提交到图片队列
            image_queue = get_queue("image")
            queue_task = await image_queue.submit(do_generate, priority=TaskPriority.NORMAL)
            
            # 等待完成（带超时）
            timeout = 300  # 5分钟超时
            start_time = asyncio.get_event_loop().time()
            
            while queue_task.status.value not in ["completed", "failed"]:
                await asyncio.sleep(1)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError("首帧生成超时")
            
            if queue_task.status.value == "completed" and queue_task.result:
                task.status = BatchTaskStatus.WAITING_VIDEO
                task.keyframe_completed_at = datetime.now()
                logger.info(f"✅ 任务 {task.task_id} 首帧生成完成")
            else:
                raise Exception("首帧生成失败")
                
        except Exception as e:
            logger.error(f"❌ 任务 {task.task_id} 首帧生成失败: {e}")
            task.status = BatchTaskStatus.KEYFRAME_FAILED
            task.keyframe_error = str(e)
    
    async def _generate_video(self, task: BatchTask, job: BatchJob):
        """生成视频"""
        task.status = BatchTaskStatus.VIDEO_GENERATING
        task.video_attempts += 1
        self._save_job(job)
        
        try:
            project = self.project_manager.load_project(task.project_id)
            shots = self.project_manager.load_shots(project)
            shot = next((s for s in shots if s.shot_id == task.shot_id), None)
            
            if not shot:
                raise ValueError(f"分镜不存在: {task.shot_id}")
            
            batch = shot.get_current_batch()
            if not batch or not batch.get("keyframe"):
                raise ValueError("没有可用的首帧")
            
            keyframe_path = batch["keyframe"].get("path")
            if not keyframe_path or not Path(keyframe_path).exists():
                raise ValueError(f"首帧文件不存在: {keyframe_path}")
            
            # 获取视频生成提示词
            prompt = shot.image_prompt.positive if shot.image_prompt else ""
            if not prompt:
                prompt = f"{shot.description} {shot.action}" if shot.description else "动画视频"
            
            # 构建视频服务配置
            video_config = self._get_video_config(task.provider)
            
            # 提交视频生成任务
            async def do_generate():
                video_service = VideoService(video_config)
                try:
                    result = await video_service.generate_video(
                        prompt=prompt,
                        first_frame_path=keyframe_path,
                        duration=task.duration,
                        size=task.size,
                        watermark=task.watermark
                    )
                    
                    if result.success:
                        # 保存任务ID
                        if "videos" not in batch:
                            batch["videos"] = []
                        
                        video_info = {
                            "task_id": result.task_id,
                            "status": result.status,
                            "duration": task.duration,
                            "size": task.size,
                            "prompt": prompt,
                            "provider": task.provider or "jiekouai",
                            "created_at": datetime.now().isoformat()
                        }
                        batch["videos"].append(video_info)
                        shot.status = "video_generating"
                        self.project_manager.update_shot(project, shot)
                        
                        return result.task_id
                    else:
                        raise Exception(result.error_message or "视频生成失败")
                        
                finally:
                    await video_service.close()
            
            # 提交到视频队列
            video_queue = get_queue("video")
            queue_task = await video_queue.submit(do_generate, priority=TaskPriority.NORMAL)
            
            # 等待提交完成获取task_id
            timeout = 60
            start_time = asyncio.get_event_loop().time()
            
            while queue_task.status.value not in ["completed", "failed"]:
                await asyncio.sleep(0.5)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError("视频任务提交超时")
            
            if queue_task.status.value == "completed" and queue_task.result:
                task.video_task_id = queue_task.result
                task.status = BatchTaskStatus.WAITING_VIDEO  # 等待视频完成
                logger.info(f"✅ 任务 {task.task_id} 视频任务已提交: {task.video_task_id}")
            else:
                raise Exception("视频任务提交失败")
                
        except Exception as e:
            logger.error(f"❌ 任务 {task.task_id} 视频生成失败: {e}")
            task.status = BatchTaskStatus.VIDEO_FAILED
            task.video_error = str(e)
    
    def _get_video_config(self, provider: Optional[str]) -> dict:
        """获取视频服务配置"""
        if provider == "mock":
            return {"default": "mock", "mock": {"simulate_delay": 2}}
        
        return {
            "default": "jiekouai",
            "jiekouai": {
                "api_key": os.getenv("JIEKOUAI_API_KEY", ""),
                "base_url": "https://api.jiekou.ai",
            }
        }
    
    async def _monitor_loop(self):
        """监控循环 - 检查视频生成状态"""
        while self._running:
            try:
                await self._check_video_status()
            except Exception as e:
                logger.error(f"❌ 监控循环异常: {e}")
            
            await asyncio.sleep(30)  # 每30秒检查一次
    
    async def _check_video_status(self):
        """检查所有等待中的视频状态"""
        from src.services.video import VideoService
        
        for job in list(self.active_jobs.values()):
            if job.status != "running":
                continue
            
            for task in job.tasks:
                if task.status != BatchTaskStatus.WAITING_VIDEO or not task.video_task_id:
                    continue
                
                try:
                    video_config = self._get_video_config(task.provider)
                    video_service = VideoService(video_config)
                    
                    result = await video_service.check_status(task.video_task_id)
                    
                    if result.status == "completed":
                        # 视频完成，下载
                        await self._download_completed_video(task, job, result.video_url, video_service)
                        
                    elif result.status == "failed":
                        task.status = BatchTaskStatus.VIDEO_FAILED
                        task.video_error = result.error_message or "视频生成失败"
                        job.failed_count += 1
                        self._save_job(job)
                        
                        # 自动重试
                        if job.auto_retry and task.video_attempts < task.max_video_attempts:
                            asyncio.create_task(self._retry_video_task(task, job))
                    
                    await video_service.close()
                    
                except Exception as e:
                    logger.error(f"❌ 检查视频状态失败 {task.video_task_id}: {e}")
    
    async def _download_completed_video(
        self, 
        task: BatchTask, 
        job: BatchJob, 
        video_url: str, 
        video_service
    ):
        """下载完成的视频"""
        try:
            project = self.project_manager.load_project(task.project_id)
            output_dir = Path(project.root_path) / "04_videos"
            output_dir.mkdir(exist_ok=True)
            
            output_path = output_dir / f"{task.shot_id}_{task.video_task_id[:8]}.mp4"
            
            success = await video_service.download_video(video_url, str(output_path))
            
            if success:
                # 更新分镜状态
                shots = self.project_manager.load_shots(project)
                shot = next((s for s in shots if s.shot_id == task.shot_id), None)
                
                if shot:
                    batch = shot.get_current_batch()
                    if batch and batch.get("videos"):
                        for v in batch["videos"]:
                            if v.get("task_id") == task.video_task_id:
                                v["local_path"] = str(output_path)
                                v["status"] = "completed"
                                break
                    
                    shot.status = "completed"
                    self.project_manager.update_shot(project, shot)
                
                task.status = BatchTaskStatus.COMPLETED
                task.video_completed_at = datetime.now()
                job.completed_count += 1
                
                logger.info(f"✅ 视频下载完成: {output_path}")
            else:
                raise Exception("视频下载失败")
                
        except Exception as e:
            logger.error(f"❌ 视频下载失败: {e}")
            task.status = BatchTaskStatus.VIDEO_FAILED
            task.video_error = f"下载失败: {str(e)}"
            job.failed_count += 1
        
        self._save_job(job)
    
    async def _retry_video_task(self, task: BatchTask, job: BatchJob):
        """重试视频任务"""
        await asyncio.sleep(5)
        await self._generate_video(task, job)
    
    def _save_job(self, job: BatchJob):
        """持久化作业状态"""
        job_path = self.PERSISTENCE_DIR / f"{job.job_id}.json"
        with open(job_path, 'w', encoding='utf-8') as f:
            json.dump(job.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_job(self, job_id: str) -> Optional[BatchJob]:
        """加载作业"""
        job_path = self.PERSISTENCE_DIR / f"{job_id}.json"
        if job_path.exists():
            with open(job_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return BatchJob.from_dict(data)
        return None
    
    async def _recover_pending_jobs(self):
        """恢复未完成的作业"""
        recovered = 0
        for job_file in self.PERSISTENCE_DIR.glob("*.json"):
            try:
                with open(job_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    job = BatchJob.from_dict(data)
                    
                    # 只恢复运行中的作业
                    if job.status == "running":
                        self.active_jobs[job.job_id] = job
                        asyncio.create_task(self._process_job(job))
                        recovered += 1
                        
            except Exception as e:
                logger.error(f"❌ 恢复作业失败 {job_file}: {e}")
        
        if recovered > 0:
            logger.info(f"♻️ 恢复了 {recovered} 个未完成的批量作业")
    
    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """获取作业状态"""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        return self._load_job(job_id)
    
    def list_jobs(self, project_id: Optional[str] = None) -> List[BatchJob]:
        """列出所有作业"""
        jobs = []
        
        # 活跃作业
        for job in self.active_jobs.values():
            if project_id is None or job.project_id == project_id:
                jobs.append(job)
        
        # 历史作业
        for job_file in self.PERSISTENCE_DIR.glob("*.json"):
            job_id = job_file.stem
            if job_id not in self.active_jobs:
                job = self._load_job(job_id)
                if job and (project_id is None or job.project_id == project_id):
                    jobs.append(job)
        
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)
    
    async def pause_job(self, job_id: str) -> bool:
        """暂停作业"""
        job = self.active_jobs.get(job_id)
        if job and job.status == "running":
            job.status = "paused"
            self._save_job(job)
            return True
        return False
    
    async def resume_job(self, job_id: str) -> bool:
        """恢复作业"""
        job = self.active_jobs.get(job_id)
        if job and job.status == "paused":
            job.status = "running"
            asyncio.create_task(self._process_job(job))
            return True
        return False
    
    async def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        job = self.active_jobs.get(job_id)
        if job and job.status in ["pending", "running", "paused"]:
            job.status = "cancelled"
            for task in job.tasks:
                if task.status not in [BatchTaskStatus.COMPLETED, BatchTaskStatus.CANCELLED]:
                    task.status = BatchTaskStatus.CANCELLED
            self._save_job(job)
            return True
        return False


# 全局服务实例
_batch_pipeline_service: Optional[BatchPipelineService] = None


def get_batch_pipeline_service() -> BatchPipelineService:
    """获取批量流水线服务实例"""
    global _batch_pipeline_service
    if _batch_pipeline_service is None:
        _batch_pipeline_service = BatchPipelineService()
    return _batch_pipeline_service
