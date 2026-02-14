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
        
        # ============ 调试输出：角色提取输入 ============
        print("\n" + "="*60)
        print("🎭 LLM角色提取 - 输入Prompt")
        print("="*60)
        print(f"Prompt长度: {len(prompt)} 字符")
        print(f"剧本长度: {len(script)} 字符")
        print("-"*60)
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print("="*60 + "\n")
        
        response = await self.generate(prompt)
        
        # ============ 调试输出：角色提取输出 ============
        print("\n" + "="*60)
        print("🎭 LLM角色提取 - 输出响应")
        print("="*60)
        print(f"响应长度: {len(response)} 字符")
        print("-"*60)
        print(response[:2000] + "..." if len(response) > 2000 else response)
        print("="*60 + "\n")
        
        # 解析JSON响应
        try:
            data = json.loads(self._extract_json(response))
            characters = data.get("characters", [])
            
            # 输出解析结果
            print(f"✅ 成功解析角色: {len(characters)} 个")
            for i, char in enumerate(characters, 1):
                print(f"   {i}. {char.get('name', 'N/A')} - {char.get('description', 'N/A')[:50]}...")
            
            return characters
        except json.JSONDecodeError as e:
            print(f"❌ 角色JSON解析失败: {e}")
            print(f"   尝试解析内容: {self._extract_json(response)[:500]}")
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
        
        # ============ 调试输出：场景提取输入 ============
        print("\n" + "="*60)
        print("🎬 LLM场景提取 - 输入Prompt")
        print("="*60)
        print(f"Prompt长度: {len(prompt)} 字符")
        print(f"剧本长度: {len(script)} 字符")
        print("-"*60)
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print("="*60 + "\n")
        
        response = await self.generate(prompt)
        
        # ============ 调试输出：场景提取输出 ============
        print("\n" + "="*60)
        print("🎬 LLM场景提取 - 输出响应")
        print("="*60)
        print(f"响应长度: {len(response)} 字符")
        print("-"*60)
        print(response[:2000] + "..." if len(response) > 2000 else response)
        print("="*60 + "\n")
        
        try:
            data = json.loads(self._extract_json(response))
            scenes = data.get("scenes", [])
            
            # 输出解析结果
            print(f"✅ 成功解析场景: {len(scenes)} 个")
            for i, scene in enumerate(scenes, 1):
                name = scene.get('name', 'N/A')
                chars = scene.get('characters', [])
                segment_len = len(scene.get('script_segment', ''))
                print(f"   {i}. {name} - 角色: {len(chars)} 个, 剧本片段: {segment_len} 字符")
                if segment_len > 0:
                    print(f"      片段预览: {scene.get('script_segment', '')[:100]}...")
            
            return scenes
        except json.JSONDecodeError as e:
            print(f"❌ 场景JSON解析失败: {e}")
            print(f"   尝试解析内容: {self._extract_json(response)[:500]}")
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
