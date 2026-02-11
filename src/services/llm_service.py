"""
LLM服务模块
使用LiteLLM统一接口，支持多提供商切换
"""

import json
from typing import Optional, Dict, Any
import litellm
from litellm import completion

from src.core.config import Config, settings
from src.models.schemas import Character, Scene


class LLMService:
    """LLM服务"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load_global()
        self.llm_config = self.config.get_llm_config()
        
        # 设置API密钥
        self._setup_api_keys()
    
    def _setup_api_keys(self):
        """设置API密钥"""
        api_key = settings.get_api_key(self.llm_config.provider)
        if api_key:
            if self.llm_config.provider == "openai":
                litellm.openai_key = api_key
                # 设置自定义base_url（如接口AI）
                custom_base_url = settings.get_llm_base_url()
                if custom_base_url:
                    litellm.api_base = custom_base_url
                    self.llm_config.base_url = custom_base_url
            elif self.llm_config.provider == "anthropic":
                litellm.anthropic_key = api_key
    
    def switch_provider(self, provider: str, model: Optional[str] = None):
        """切换LLM提供商"""
        if provider not in self.config.providers:
            raise ValueError(f"未知的提供商: {provider}")
        
        self.llm_config.provider = provider
        
        if model:
            self.llm_config.model = model
        elif provider == "anthropic":
            self.llm_config.model = "claude-3-opus-20240229"
        
        # 更新base_url
        provider_config = self.config.providers.get(provider, {})
        if "base_url" in provider_config:
            self.llm_config.base_url = provider_config["base_url"]
        
        # 重新设置API密钥
        self._setup_api_keys()
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        生成文本
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
        
        Returns:
            生成的文本
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await litellm.acompletion(
            model=f"{self.llm_config.provider}/{self.llm_config.model}",
            messages=messages,
            temperature=temperature or self.llm_config.temperature,
            max_tokens=max_tokens or self.llm_config.max_tokens,
            api_base=self.llm_config.base_url if self.llm_config.base_url else None,
            **kwargs
        )
        
        return response.choices[0].message.content
    
    async def extract_characters(self, script: str) -> list:
        """
        从剧本中提取角色
        
        Args:
            script: 剧本内容
        
        Returns:
            角色列表
        """
        prompt_template = self.config.prompts.get("character_extraction", "")
        # 使用 [[SCRIPT]] 占位符，避免与 JSON 大括号冲突
        if "[[SCRIPT]]" in prompt_template:
            prompt = prompt_template.replace("[[SCRIPT]]", script)
        else:
            # 如果没有占位符，直接追加剧本
            prompt = f"{prompt_template}\n\n剧本内容：\n{script}"
        
        response = await self.generate(prompt)
        
        # 解析JSON响应
        try:
            data = json.loads(self._extract_json(response))
            return data.get("characters", [])
        except json.JSONDecodeError:
            # 如果解析失败，返回空列表
            return []
    
    async def extract_scenes(self, script: str) -> list:
        """
        从剧本中提取场景
        
        Args:
            script: 剧本内容
        
        Returns:
            场景列表
        """
        prompt_template = self.config.prompts.get("scene_extraction", "")
        # 使用 [[SCRIPT]] 占位符，避免与 JSON 大括号冲突
        if "[[SCRIPT]]" in prompt_template:
            prompt = prompt_template.replace("[[SCRIPT]]", script)
        else:
            # 如果没有占位符，直接追加剧本
            prompt = f"{prompt_template}\n\n剧本内容：\n{script}"
        
        response = await self.generate(prompt)
        
        try:
            data = json.loads(self._extract_json(response))
            return data.get("scenes", [])
        except json.JSONDecodeError:
            return []
    
    async def generate_character_prompt(
        self,
        character: Character,
        style_description: str
    ) -> str:
        """
        生成角色参考图提示词
        
        Args:
            character: 角色对象
            style_description: 风格描述
        
        Returns:
            图片生成提示词
        """
        prompt_template = self.config.prompts.get("character_ref_prompt", "")
        # 使用 replace 替换 [[占位符]] 格式
        prompt = prompt_template.replace("[[NAME]]", character.name or "")
        prompt = prompt.replace("[[DESCRIPTION]]", character.description or "")
        prompt = prompt.replace("[[PERSONALITY]]", character.personality or "")
        prompt = prompt.replace("[[STYLE]]", style_description or "")
        
        return await self.generate(prompt)
    
    async def generate_scene_prompt(
        self,
        scene: Scene,
        style_description: str
    ) -> str:
        """
        生成场景参考图提示词
        
        Args:
            scene: 场景对象
            style_description: 风格描述
        
        Returns:
            图片生成提示词
        """
        prompt_template = self.config.prompts.get("scene_ref_prompt", "")
        # 使用 replace 替换 [[占位符]] 格式
        prompt = prompt_template.replace("[[NAME]]", scene.name or "")
        prompt = prompt.replace("[[DESCRIPTION]]", scene.description or "")
        prompt = prompt.replace("[[LOCATION]]", scene.location or "")
        prompt = prompt.replace("[[TIME]]", scene.time or "")
        prompt = prompt.replace("[[STYLE]]", style_description or "")
        
        return await self.generate(prompt)
    
    async def summarize_script(self, script: str, max_words: int = 300) -> str:
        """
        总结剧本概要
        
        Args:
            script: 剧本内容
            max_words: 最大字数
        
        Returns:
            剧本概要
        """
        prompt = f"""请将以下故事总结为{max_words}字的概要：

{script}

请提供：
1. 主要情节
2. 关键转折点
3. 故事主题
"""
        return await self.generate(prompt)
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分"""
        # 尝试找到JSON代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        
        # 尝试找到花括号包围的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        
        return text
