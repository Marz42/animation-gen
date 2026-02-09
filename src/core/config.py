"""
配置管理模块
支持两层配置：全局默认 + 项目覆盖
支持 YAML 和 JSON 格式
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
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


class APIProvider(BaseModel):
    """API提供商配置模型"""
    id: str
    name: str
    type: str  # "llm" | "image" | "video"
    enabled: bool = True
    base_url: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    endpoint: Optional[str] = None
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    timeout: int = 60
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    verified: Optional[bool] = None
    verified_at: Optional[str] = None
    latency: Optional[int] = None


class Config(BaseModel):
    defaults: DefaultsConfig = DefaultsConfig()
    providers: Dict[str, List[APIProvider]] = Field(default_factory=lambda: {"llm": [], "image": [], "video": []})
    prompts: Dict[str, str] = Field(default_factory=dict)
    
    @classmethod
    def get_global_config_paths(cls) -> tuple[Path, Path]:
        """获取全局配置文件的yaml和json路径"""
        base_dir = Path.home() / ".animation_gen"
        return base_dir / "config.yaml", base_dir / "config.json"
    
    @classmethod
    def get_project_config_paths(cls, project_path: Path) -> tuple[Path, Path]:
        """获取项目配置文件的yaml和json路径"""
        return project_path / "config.yaml", project_path / "config.json"
    
    @classmethod
    def load_global(cls) -> "Config":
        """加载全局配置（优先使用JSON格式）"""
        yaml_path, json_path = cls.get_global_config_paths()
        
        # 优先尝试加载JSON格式
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data:
                    return cls._migrate_providers_format(cls(**data))
            except Exception as e:
                print(f"⚠️ 加载JSON配置失败: {e}，尝试YAML格式")
        
        # 回退到YAML格式
        if yaml_path.exists():
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data:
                    return cls._migrate_providers_format(cls(**data))
            except Exception as e:
                print(f"⚠️ 加载YAML配置失败: {e}")
        
        # 从项目config加载默认配置
        default_config_path = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
        if default_config_path.exists():
            try:
                with open(default_config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data:
                    return cls._migrate_providers_format(cls(**data))
            except Exception as e:
                print(f"⚠️ 加载默认配置失败: {e}")
        
        # 使用默认配置
        return cls()
    
    @classmethod
    def _migrate_providers_format(cls, config: "Config") -> "Config":
        """迁移旧版providers格式到新版"""
        # 如果providers是dict但不是按type分类的，需要迁移
        if isinstance(config.providers, dict):
            # 检查是否是新格式（包含llm/image/video键且值为列表）
            if all(k in config.providers for k in ["llm", "image", "video"]):
                # 检查是否已经是新格式（值为列表）
                if all(isinstance(config.providers[k], list) for k in ["llm", "image", "video"]):
                    return config
            
            # 旧格式：按provider_id索引的字典，或default_config.yaml中的models配置
            new_providers = {"llm": [], "image": [], "video": []}
            for provider_id, provider_data in config.providers.items():
                if isinstance(provider_data, dict):
                    # 跳过旧格式的models配置（如openai: {models: [...] }）
                    if "models" in provider_data and len(provider_data) == 1:
                        continue
                    # 检查是否有type字段
                    if "type" not in provider_data:
                        # 根据provider_id推断类型
                        if provider_id in ["openai", "anthropic", "openrouter"]:
                            provider_data["type"] = "llm"
                        elif provider_id in ["nanobanana", "jiekouai"]:
                            provider_data["type"] = "image"
                        elif provider_id in ["sora2", "veo3"]:
                            provider_data["type"] = "video"
                        else:
                            continue
                    
                    provider_type = provider_data.get("type", "llm")
                    if provider_type in new_providers:
                        if "id" not in provider_data:
                            provider_data["id"] = provider_id
                        try:
                            new_providers[provider_type].append(APIProvider(**provider_data))
                        except Exception:
                            pass
            config.providers = new_providers
        return config
    
    @classmethod
    def load_project(cls, project_path: Path) -> "Config":
        """加载项目配置（覆盖全局），优先使用JSON格式"""
        # 先加载全局配置
        config = cls.load_global()
        
        # 加载项目配置（如果存在）
        yaml_path, json_path = cls.get_project_config_paths(project_path)
        
        project_data = None
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
            except Exception as e:
                print(f"⚠️ 加载项目JSON配置失败: {e}")
        elif yaml_path.exists():
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    project_data = yaml.safe_load(f)
            except Exception as e:
                print(f"⚠️ 加载项目YAML配置失败: {e}")
        
        if project_data:
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
    
    def save_global_config(self, use_json: bool = True):
        """保存全局配置"""
        yaml_path, json_path = self.get_global_config_paths()
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.model_dump()
        
        if use_json:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    def save_project_config(self, project_path: Path, use_json: bool = True):
        """保存项目配置"""
        yaml_path, json_path = self.get_project_config_paths(project_path)
        data = self.model_dump()
        
        if use_json:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    def get_llm_config(self) -> LLMConfig:
        return self.defaults.llm
    
    def get_image_config(self) -> ImageConfig:
        return self.defaults.image
    
    def get_video_config(self) -> VideoConfig:
        return self.defaults.video
    
    def export_config(self) -> Dict[str, Any]:
        """导出完整配置"""
        return self.model_dump()
    
    @classmethod
    def import_config(cls, data: Dict[str, Any]) -> "Config":
        """导入配置并验证"""
        return cls(**data)


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
