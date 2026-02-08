"""
数据模型定义
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EntityStatus(str, Enum):
    """实体状态枚举"""
    PENDING = "pending"
    GENERATING_PROMPT = "generating_prompt"
    PROMPT_READY = "prompt_ready"
    GENERATING = "generating"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ShotType(str, Enum):
    """镜头类型枚举"""
    WIDE = "wide"           # 全景
    MEDIUM = "medium"       # 中景
    CLOSE_UP = "close_up"   # 特写
    EXTREME_CLOSE_UP = "extreme_close_up"  # 大特写


class CameraMovement(str, Enum):
    """镜头运动枚举"""
    STATIC = "static"       # 静止
    PAN = "pan"             # 平移
    TILT = "tilt"           # 倾斜
    ZOOM = "zoom"           # 缩放
    TRACKING = "tracking"   # 跟随


class VideoDuration(str, Enum):
    """视频时长枚举（不同提供商支持不同）"""
    SECONDS_2 = "2s"
    SECONDS_3 = "3s"
    SECONDS_4 = "4s"
    SECONDS_5 = "5s"
    SECONDS_6 = "6s"
    SECONDS_8 = "8s"
    SECONDS_10 = "10s"
    SECONDS_12 = "12s"
    SECONDS_15 = "15s"


class ProjectStatistics(BaseModel):
    """项目统计信息"""
    total_characters: int = 0
    total_scenes: int = 0
    total_shots: int = 0
    total_tasks: int = Field(0, description="总任务数 = 角色生成 + 场景生成 + 首帧生成 + 视频生成")
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    
    @property
    def progress_percentage(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100


class GenerationVersion(BaseModel):
    """生成版本记录（支持回滚）"""
    version_id: int
    status: EntityStatus
    prompt: str
    seed: Optional[int] = None
    path: Optional[str] = None  # 文件路径
    url: Optional[str] = None   # URL（如果远程存储）
    rejected_reason: Optional[str] = None
    cost_usd: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImagePrompt(BaseModel):
    """图片生成提示词"""
    positive: str
    negative: str = "bad anatomy, bad hands, worst quality, low quality"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class VideoPrompt(BaseModel):
    """视频生成提示词"""
    description: str
    camera: Optional[str] = None


class Placeholder(BaseModel):
    """导演模式占位符"""
    enabled: bool = False
    type: Optional[str] = None  # sketch / reference_image
    path: Optional[str] = None
    description: Optional[str] = None


class Character(BaseModel):
    """角色模型"""
    character_id: str
    name: str
    description: str
    personality: str
    status: EntityStatus = EntityStatus.PENDING
    
    # 参考图版本管理
    current_version: int = 0
    versions: List[GenerationVersion] = Field(default_factory=list)
    
    # 手动覆盖
    manual_override: Optional[ImagePrompt] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def get_current_version(self) -> Optional[GenerationVersion]:
        if not self.versions:
            return None
        return next((v for v in self.versions if v.version_id == self.current_version), None)
    
    def add_version(self, prompt: str, seed: Optional[int] = None, path: Optional[str] = None) -> GenerationVersion:
        """添加新版本"""
        version_id = len(self.versions) + 1
        version = GenerationVersion(
            version_id=version_id,
            status=EntityStatus.PENDING_REVIEW,
            prompt=prompt,
            seed=seed,
            path=path
        )
        self.versions.append(version)
        self.current_version = version_id
        self.updated_at = datetime.now()
        return version


class Scene(BaseModel):
    """场景模型"""
    scene_id: str
    name: str
    description: str
    location: str
    time: str  # 白天/夜晚/黄昏等
    atmosphere: Optional[str] = None
    status: EntityStatus = EntityStatus.PENDING
    
    # 参考图版本管理
    current_version: int = 0
    versions: List[GenerationVersion] = Field(default_factory=list)
    
    # 关联的分镜
    shots: List[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def get_current_version(self) -> Optional[GenerationVersion]:
        if not self.versions:
            return None
        return next((v for v in self.versions if v.version_id == self.current_version), None)
    
    def add_version(self, prompt: str, seed: Optional[int] = None, path: Optional[str] = None) -> GenerationVersion:
        """添加新版本"""
        version_id = len(self.versions) + 1
        version = GenerationVersion(
            version_id=version_id,
            status=EntityStatus.PENDING_REVIEW,
            prompt=prompt,
            seed=seed,
            path=path
        )
        self.versions.append(version)
        self.current_version = version_id
        self.updated_at = datetime.now()
        return version


class Shot(BaseModel):
    """分镜模型（支持Batch）"""
    shot_id: str
    scene_id: str
    sequence: int
    type: ShotType = ShotType.MEDIUM
    camera_movement: CameraMovement = CameraMovement.STATIC
    duration: VideoDuration = VideoDuration.SECONDS_5
    description: str
    action: Optional[str] = None
    dialogue: Optional[str] = None
    characters: List[str] = Field(default_factory=list)
    
    # 提示词
    image_prompt: Optional[ImagePrompt] = None
    video_prompt: Optional[VideoPrompt] = None
    display_prompt: Optional[str] = None  # 实际发送给AI的完整Prompt
    
    # 导演模式占位符
    placeholder: Placeholder = Field(default_factory=Placeholder)
    
    # Batch版本管理
    current_batch_id: Optional[str] = None
    batches: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # 成本预估
    cost_estimate: Optional[Dict[str, float]] = None
    
    # 手动覆盖
    manual_override: Optional[Dict[str, Any]] = None
    
    # 状态
    status: Optional[str] = None  # draft / frame_pending_review / frame_approved / frame_failed / video_generating / completed
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def create_batch(self, batch_id: Optional[str] = None) -> str:
        """创建新的batch"""
        if batch_id is None:
            batch_id = f"batch_{len(self.batches) + 1:03d}"
        
        self.batches[batch_id] = {
            "created_at": datetime.now().isoformat(),
            "keyframe": None,
            "video": None
        }
        self.current_batch_id = batch_id
        self.updated_at = datetime.now()
        return batch_id
    
    def get_current_batch(self) -> Optional[Dict[str, Any]]:
        if not self.current_batch_id:
            return None
        return self.batches.get(self.current_batch_id)


class Task(BaseModel):
    """异步任务模型"""
    task_id: str
    project_id: str
    entity_type: str  # character / scene / shot
    entity_id: str
    batch_id: Optional[str] = None
    task_type: str  # generate_prompt / generate_image / generate_video
    status: TaskStatus = TaskStatus.PENDING
    
    # 执行信息
    worker_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 结果
    result_path: Optional[str] = None
    result_url: Optional[str] = None
    cost_usd: Optional[float] = None
    
    # API外部任务ID（用于Webhook回调）
    external_task_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProjectConfig(BaseModel):
    """项目配置"""
    resolution: str = "1280x720"
    frame_rate: int = 24
    parallel_workers: int = 4
    llm_provider: str = "openai"
    llm_model: str = "gemini-3-flash-preview"  # 使用接口AI支持的模型
    image_provider: str = "jiekouai"  # 使用接口AI
    video_provider: str = "sora2"
    video_duration: VideoDuration = VideoDuration.SECONDS_5


class Project(BaseModel):
    """项目模型"""
    project_id: str
    name: str
    description: Optional[str] = None
    
    # 文件路径
    script_path: str
    root_path: str
    
    # 配置
    style_description: str
    config: ProjectConfig = Field(default_factory=ProjectConfig)
    
    # 阶段信息
    current_stage: str = "draft"  # draft / extracting / generating_refs / designing_shots / generating_frames / generating_videos / completed
    is_running: bool = False
    
    # 统计
    statistics: ProjectStatistics = Field(default_factory=ProjectStatistics)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def status(self) -> str:
        """计算项目整体状态（非存储字段）"""
        if self.statistics.failed_tasks > 0 and self.statistics.failed_tasks == self.statistics.total_tasks:
            return "error"
        if self.statistics.completed_tasks == 0:
            return "draft"
        if self.statistics.completed_tasks == self.statistics.total_tasks and self.statistics.total_tasks > 0:
            return "completed"
        return "in_progress"
    
    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        return self.statistics.progress_percentage
