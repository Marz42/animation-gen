"""
视频提供商工厂
"""
from typing import Dict, Type

from .base import BaseVideoProvider
from .jiekouai import JiekouaiVideoProvider
from .mock import MockVideoProvider

# 提供商注册表 - 支持字符串键
PROVIDER_REGISTRY: Dict[str, Type[BaseVideoProvider]] = {
    "jiekouai": JiekouaiVideoProvider,
    "mock": MockVideoProvider,
    # 未来可扩展：
    # "keling": KelingVideoProvider,
    # "runway": RunwayVideoProvider,
}


def create_video_provider(
    provider_type: str,
    config: Dict
) -> BaseVideoProvider:
    """
    创建视频提供商实例
    
    Args:
        provider_type: 提供商类型字符串
        config: 配置字典
    
    Returns:
        提供商实例
    """
    if provider_type not in PROVIDER_REGISTRY:
        raise ValueError(f"未知的视频提供商: {provider_type}")
    
    provider_class = PROVIDER_REGISTRY[provider_type]
    return provider_class(config)


def get_available_providers() -> list:
    """获取所有可用的提供商列表"""
    return list(PROVIDER_REGISTRY.keys())


def get_provider_capabilities(provider_type: str) -> Dict:
    """获取提供商能力信息"""
    provider = create_video_provider(provider_type, {})
    return provider.get_capabilities()
