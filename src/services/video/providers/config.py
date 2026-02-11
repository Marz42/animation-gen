"""
视频提供商配置管理
支持不同提供商的参数映射和适配
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum


class ProviderCapability(Enum):
    """提供商能力"""
    IMAGE_INPUT = "supports_image_input"
    WATERMARK = "supports_watermark"
    SYNC_GENERATION = "supports_sync"
    ASYNC_GENERATION = "supports_async"


@dataclass
class ProviderParameter:
    """提供商参数定义"""
    name: str  # 参数名
    type: str  # 类型: int, str, bool, enum
    required: bool = True
    default: Any = None
    options: List[Any] = field(default_factory=list)  # 可选值列表
    min_value: Any = None
    max_value: Any = None
    description: str = ""


@dataclass
class ProviderConfig:
    """提供商配置"""
    provider_id: str
    display_name: str
    
    # 参数定义
    duration_param: ProviderParameter = field(default_factory=lambda: ProviderParameter(
        name="duration",
        type="enum",
        options=["4s", "8s", "12s"],
        default="4s",
        description="视频时长"
    ))
    
    resolution_param: ProviderParameter = field(default_factory=lambda: ProviderParameter(
        name="resolution",
        type="enum",
        options=["720p", "1080p"],
        default="720p",
        description="视频分辨率"
    ))
    
    # 参数映射函数
    duration_mapper: Dict[str, Any] = field(default_factory=dict)
    resolution_mapper: Dict[str, str] = field(default_factory=dict)
    
    # 能力
    capabilities: Dict[str, bool] = field(default_factory=dict)
    
    # API 配置
    base_url: str = ""
    endpoints: Dict[str, str] = field(default_factory=dict)
    
    def map_duration(self, duration: str) -> Any:
        """映射时长参数"""
        return self.duration_mapper.get(duration, self.duration_param.default)
    
    def map_resolution(self, resolution: str) -> str:
        """映射分辨率参数"""
        return self.resolution_mapper.get(resolution, self.resolution_param.default)
    
    def validate_params(self, params: Dict[str, Any]) -> (bool, str):
        """验证参数"""
        # 验证 duration
        if "duration" in params:
            duration = params["duration"]
            if duration not in self.duration_param.options:
                return False, f"Duration {duration} not supported. Options: {self.duration_param.options}"
        
        # 验证 resolution
        if "resolution" in params:
            resolution = params["resolution"]
            if resolution not in self.resolution_param.options:
                return False, f"Resolution {resolution} not supported. Options: {self.resolution_param.options}"
        
        return True, ""


# 预定义的提供商配置

JIEKOUAI_SORA2_CONFIG = ProviderConfig(
    provider_id="jiekouai_sora2",
    display_name="接口AI Sora-2",
    duration_param=ProviderParameter(
        name="duration",
        type="int",
        options=["4s", "8s", "12s"],
        default="4s",
        description="视频时长（秒）"
    ),
    resolution_param=ProviderParameter(
        name="resolution",
        type="str",
        options=["720p", "1080p"],
        default="720p",
        description="视频分辨率"
    ),
    duration_mapper={
        "4s": 4,
        "8s": 8,
        "12s": 12,
    },
    resolution_mapper={
        "720p": "720p",
        "1080p": "1080p",
    },
    capabilities={
        "supports_image_input": True,
        "supports_watermark": False,
        "supports_sync": False,
        "supports_async": True,
        "requires_base64": True,
    },
    base_url="https://api.jiekou.ai",
    endpoints={
        "generate": "/v3/async/sora-2-img2video",
        "status": "/v3/async/task-result",
    }
)

KLING_CONFIG = ProviderConfig(
    provider_id="kling",
    display_name="可灵 (Kling)",
    duration_param=ProviderParameter(
        name="duration",
        type="int",
        options=["5s", "10s"],
        default="5s",
        description="视频时长（秒）"
    ),
    resolution_param=ProviderParameter(
        name="resolution",
        type="str",
        options=["720p", "1080p"],
        default="720p",
        description="视频分辨率"
    ),
    duration_mapper={
        "5s": 5,
        "10s": 10,
    },
    resolution_mapper={
        "720p": "720p",
        "1080p": "1080p",
    },
    capabilities={
        "supports_image_input": True,
        "supports_watermark": False,
        "supports_sync": False,
        "supports_async": True,
        "requires_base64": False,
    },
    base_url="https://api.klingai.com",
    endpoints={
        "generate": "/v1/videos/image2video",
        "status": "/v1/videos/{task_id}",
    }
)

RUNWAY_CONFIG = ProviderConfig(
    provider_id="runway",
    display_name="Runway ML",
    duration_param=ProviderParameter(
        name="duration",
        type="int",
        options=["4s", "10s"],
        default="4s",
        description="视频时长（秒）"
    ),
    resolution_param=ProviderParameter(
        name="resolution",
        type="str",
        options=["720p", "1080p"],
        default="1080p",
        description="视频分辨率"
    ),
    duration_mapper={
        "4s": 4,
        "10s": 10,
    },
    resolution_mapper={
        "720p": "720p",
        "1080p": "1080p",
    },
    capabilities={
        "supports_image_input": True,
        "supports_watermark": False,
        "supports_sync": False,
        "supports_async": True,
        "requires_base64": False,
    },
    base_url="https://api.runwayml.com",
    endpoints={
        "generate": "/v1/generations",
        "status": "/v1/generations/{task_id}",
    }
)

# 提供商配置注册表
PROVIDER_CONFIGS: Dict[str, ProviderConfig] = {
    "jiekouai": JIEKOUAI_SORA2_CONFIG,
    "jiekouai_sora2": JIEKOUAI_SORA2_CONFIG,
    "kling": KLING_CONFIG,
    "runway": RUNWAY_CONFIG,
}


def get_provider_config(provider_id: str) -> ProviderConfig:
    """获取提供商配置"""
    return PROVIDER_CONFIGS.get(provider_id, JIEKOUAI_SORA2_CONFIG)


def list_provider_configs() -> List[ProviderConfig]:
    """列出所有支持的提供商配置"""
    return list(PROVIDER_CONFIGS.values())


def register_provider_config(config: ProviderConfig):
    """注册新的提供商配置"""
    PROVIDER_CONFIGS[config.provider_id] = config
