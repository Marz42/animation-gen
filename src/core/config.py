"""
配置管理模块
支持两层配置：全局默认 + 项目覆盖
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


class ImageConfig(BaseModel):
    provider: str = "jiekouai"  # 默认使用接口AI
    base_url: str = "https://api.jiekou.ai"
    endpoint: str = "/v3/nano-banana-pro-light-t2i"
    default_steps: int = 30
    default_cfg: float = 7.0
    timeout: int = 120


class VideoConfig(BaseModel):
    provider: str = "sora2"
    base_url: str = "https://api.sora2.com"
    duration: str = "5s"
    timeout: int = 300


class GenerationConfig(BaseModel):
    resolution: str = "1280x720"
    frame_rate: int = 24
    character_ref_resolution: str = "512x512"
    scene_ref_resolution: str = "768x432"
    keyframe_resolution: str = "1280x720"


class ConcurrencyConfig(BaseModel):
    llm_workers: int = 8
    image_workers: int = 4
    video_workers: int = 2
    max_retries: int = 3
    retry_delay: int = 5


class DefaultsConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    image: ImageConfig = ImageConfig()
    video: VideoConfig = VideoConfig()
    generation: GenerationConfig = GenerationConfig()
    concurrency: ConcurrencyConfig = ConcurrencyConfig()


class Config(BaseModel):
    defaults: DefaultsConfig = DefaultsConfig()
    providers: Dict[str, Any] = {}
    prompts: Dict[str, str] = {}
    
    @classmethod
    def load_global(cls) -> "Config":
        """加载全局配置"""
        config_path = Path.home() / ".animation_gen" / "config.yaml"
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:  # 确保数据不为None
                    return cls(**data)
        
        # 从项目config加载默认配置
        default_config_path = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
        if default_config_path.exists():
            with open(default_config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:  # 确保数据不为None
                    return cls(**data)
        
        # 使用默认配置
        return cls()
    
    @classmethod
    def load_project(cls, project_path: Path) -> "Config":
        """加载项目配置（覆盖全局）"""
        # 先加载全局配置
        config = cls.load_global()
        
        # 加载项目配置（如果存在）
        project_config_path = project_path / "config.yaml"
        if project_config_path.exists():
            with open(project_config_path, 'r', encoding='utf-8') as f:
                project_data = yaml.safe_load(f)
                # 深度合并
                config = cls._deep_merge_config(config, project_data)
        
        return config
    
    @staticmethod
    def _deep_merge_config(base: "Config", override: Dict) -> "Config":
        """深度合并配置"""
        base_dict = base.model_dump()
        
        def merge_dict(base_d: Dict, override_d: Dict) -> Dict:
            result = base_d.copy()
            for key, value in override_d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result
        
        merged = merge_dict(base_dict, override)
        return Config(**merged)
    
    def save_project_config(self, project_path: Path):
        """保存项目配置"""
        config_path = project_path / "config.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, allow_unicode=True, default_flow_style=False)
    
    def get_llm_config(self) -> LLMConfig:
        return self.defaults.llm
    
    def get_image_config(self) -> ImageConfig:
        return self.defaults.image
    
    def get_video_config(self) -> VideoConfig:
        return self.defaults.video


# 环境变量配置
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    
    # API Keys
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")
    nanobanana_api_key: Optional[str] = Field(None, alias="NANOBANANA_API_KEY")
    jiekouai_api_key: Optional[str] = Field(None, alias="JIEKOUAI_API_KEY")
    sora2_api_key: Optional[str] = Field(None, alias="SORA2_API_KEY")
    veo3_api_key: Optional[str] = Field(None, alias="VEO3_API_KEY")
    
    # Base URLs
    public_url: str = Field("http://localhost:8000", alias="PUBLIC_URL")
    api_port: int = Field(8000, alias="API_PORT")
    
    # LLM自定义Base URL（用于接口AI等代理服务）
    openai_base_url: Optional[str] = Field(None, alias="OPENAI_BASE_URL")
    
    # 接口AI特殊配置
    jiekouai_base_url: str = Field("https://api.jiekou.ai", alias="JIEKOUAI_BASE_URL")
    jiekouai_endpoint: str = Field("/v3/nano-banana-pro-light-t2i", alias="JIEKOUAI_ENDPOINT")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """获取指定提供商的API密钥"""
        mapping = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "nanobanana": self.nanobanana_api_key,
            "jiekouai": self.jiekouai_api_key,
            "sora2": self.sora2_api_key,
            "veo3": self.veo3_api_key,
        }
        return mapping.get(provider)
    
    def get_llm_base_url(self) -> Optional[str]:
        """获取LLM的自定义Base URL（用于接口AI等）"""
        return self.openai_base_url


# 全局设置实例
settings = Settings()
