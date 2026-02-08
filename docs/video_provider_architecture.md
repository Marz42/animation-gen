# 视频服务多提供商架构设计

## 目标
支持快速切换视频生成服务提供商，如：接口AI、可灵、Runway、Pika 等。

## 架构设计

### 1. 核心抽象层

```python
# src/services/video/providers/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator
from enum import Enum

class VideoProviderType(str, Enum):
    JIEKOUAI = "jiekouai"      # 接口AI - Sora 2
    KELING = "keling"          # 可灵 AI
    RUNWAY = "runway"          # Runway ML
    PIKA = "pika"              # Pika Labs
    # 可扩展更多...

class VideoDuration(str, Enum):
    """标准化时长"""
    SECONDS_5 = "5s"
    SECONDS_10 = "10s"
    
class VideoResolution(str, Enum):
    """标准化分辨率"""
    PORTRAIT_720P = "720x1280"   # 竖屏
    LANDSCAPE_720P = "1280x720"  # 横屏

class VideoGenerationRequest:
    """统一请求格式"""
    prompt: str
    image_path: Optional[str] = None  # 本地文件路径
    duration: VideoDuration
    resolution: VideoResolution
    watermark: bool = False
    # 提供商特定参数
    provider_params: Dict[str, Any] = {}

class VideoGenerationResult:
    """统一响应格式"""
    success: bool
    task_id: Optional[str] = None
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    status: str  # submitted/processing/completed/failed
    progress: int = 0
    error_message: Optional[str] = None
    provider_info: Dict[str, Any] = {}  # 提供商原始响应

class BaseVideoProvider(ABC):
    """视频提供商抽象基类"""
    
    provider_type: VideoProviderType
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
    
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
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务（如果支持）"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """获取提供商能力"""
        pass
    
    async def close(self):
        """清理资源"""
        pass
```

### 2. 提供商实现示例

```python
# src/services/video/providers/jiekouai_provider.py
class JiekouaiVideoProvider(BaseVideoProvider):
    """接口AI Sora 2 实现"""
    
    provider_type = VideoProviderType.JIEKOUAI
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "supports_image_input": True,
            "image_format": "url_only",  # 仅支持URL
            "durations": ["10s", "15s"],
            "resolutions": ["720x1280", "1280x720"],
            "max_prompt_length": 2000,
            "supports_watermark": True,
            "requires_upload": True,  # 需要上传图片到临时存储
        }
    
    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        # 1. 检查并转换时长
        duration_map = {
            VideoDuration.SECONDS_5: 10,   # 5s -> 10s
            VideoDuration.SECONDS_10: 10,
        }
        actual_duration = duration_map.get(request.duration, 10)
        
        # 2. 检查并转换分辨率
        resolution_map = {
            VideoResolution.PORTRAIT_720P: "720x1280",
            VideoResolution.LANDSCAPE_720P: "1280x720",
        }
        actual_size = resolution_map.get(request.resolution, "1280x720")
        
        # 3. 上传图片获取URL（如果需要）
        image_url = None
        if request.image_path:
            image_url = await self._upload_image(request.image_path)
        
        # 4. 调用API
        payload = {
            "prompt": request.prompt,
            "image": image_url,
            "duration": actual_duration,
            "size": actual_size,
            "watermark": request.watermark,
        }
        
        response = await self._call_api("/v3/sora-2-video-reverse", payload)
        
        return VideoGenerationResult(
            success=True,
            task_id=response["task_id"],
            status="submitted",
            provider_info={"raw_response": response}
        )
    
    async def _upload_image(self, local_path: str) -> str:
        """上传图片到临时存储并返回URL"""
        # 实现：上传到图床或临时OSS
        pass
```

### 3. 工厂模式创建提供商

```python
# src/services/video/provider_factory.py
from typing import Type

PROVIDER_REGISTRY: Dict[VideoProviderType, Type[BaseVideoProvider]] = {}

def register_provider(provider_class: Type[BaseVideoProvider]):
    """注册提供商"""
    PROVIDER_REGISTRY[provider_class.provider_type] = provider_class
    return provider_class

def create_video_provider(
    provider_type: VideoProviderType,
    config: Dict[str, Any]
) -> BaseVideoProvider:
    """创建提供商实例"""
    if provider_type not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_type}")
    
    provider_class = PROVIDER_REGISTRY[provider_type]
    return provider_class(config)

# 自动注册
@register_provider
class JiekouaiVideoProvider(BaseVideoProvider):
    ...
```

### 4. 配置驱动

```yaml
# config.yaml
video_providers:
  default: jiekouai  # 默认提供商
  
  jiekouai:
    type: jiekouai
    api_key: ${JIEKOUAI_API_KEY}
    base_url: https://api.jiekou.ai
    upload_storage:  # 图片上传配置
      type: local_static  # 或 oss, s3
      base_url: http://localhost:8000/static/temp
    
  keling:
    type: keling
    api_key: ${KELING_API_KEY}
    base_url: https://api.keling.ai
    
  runway:
    type: runway
    api_key: ${RUNWAY_API_KEY}
```

### 5. 统一视频服务

```python
# src/services/video/video_service.py
class VideoService:
    """统一视频服务，自动选择/切换提供商"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.default_provider = self._create_default_provider()
        self.active_tasks: Dict[str, BaseVideoProvider] = {}  # task_id -> provider
    
    def _create_default_provider(self) -> BaseVideoProvider:
        provider_type = VideoProviderType(self.config.get("default", "jiekouai"))
        provider_config = self.config.get(provider_type.value, {})
        return create_video_provider(provider_type, provider_config)
    
    async def generate_video(
        self,
        prompt: str,
        first_frame_path: Optional[str] = None,
        duration: str = "5s",
        size: str = "512x512",
        watermark: bool = False,
        provider: Optional[str] = None  # 可指定提供商
    ) -> VideoGenerationResult:
        
        # 选择提供商
        video_provider = self.default_provider
        if provider:
            video_provider = create_video_provider(
                VideoProviderType(provider),
                self.config.get(provider, {})
            )
        
        # 转换参数
        request = self._normalize_request(
            prompt, first_frame_path, duration, size, watermark
        )
        
        # 检查能力
        caps = video_provider.get_capabilities()
        if not self._validate_request(request, caps):
            raise ValueError("Request not supported by provider")
        
        # 提交任务
        result = await video_provider.generate_video(request)
        
        # 记录任务对应的提供商
        if result.task_id:
            self.active_tasks[result.task_id] = video_provider
        
        return result
    
    async def check_status(self, task_id: str) -> VideoGenerationResult:
        """检查状态（自动路由到正确的提供商）"""
        provider = self.active_tasks.get(task_id, self.default_provider)
        return await provider.check_status(task_id)
```

## 数据结构扩展

### ProjectConfig 扩展

```python
class ProjectConfig(BaseModel):
    resolution: str = "1280x720"
    frame_rate: int = 24
    video_provider: str = "jiekouai"  # 新增：视频提供商
    video_duration: str = "5s"  # 改为标准化时长
```

### Shot 模型扩展

```python
class Shot(BaseModel):
    # ... 现有字段 ...
    
    # 视频生成记录
    video_generations: List[VideoGenerationRecord] = Field(default_factory=list)

class VideoGenerationRecord(BaseModel):
    """视频生成记录"""
    batch_id: str
    provider: str  # 使用的提供商
    task_id: str
    status: str
    prompt: str
    duration: str
    resolution: str
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

## 快速切换流程

1. **修改配置**: 改 `config.yaml` 中的 `default` 字段
2. **实现新提供商**: 继承 `BaseVideoProvider`，实现3个方法
3. **注册**: 添加 `@register_provider` 装饰器
4. **重启服务**: 自动生效

## 当前任务优先级

1. **立即**: 实现接口AI视频提供商
2. **下一步**: 添加图片上传功能（因为接口AI只支持URL）
3. **随后**: 测试完整流程
4. **未来**: 添加可灵等其他提供商

