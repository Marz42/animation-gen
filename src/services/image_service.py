"""
图片生成服务
支持多种图片生成API（nanobanana、接口AI等）
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from src.core.config import Config, settings
from src.models.schemas import Character, Scene, Shot, ImagePrompt
from src.services.jiekouai_service import JiekouAIImageService


class ImageService:
    """图片生成服务"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load_global()
        self.image_config = self.config.get_image_config()
        self.api_key = settings.get_api_key(self.image_config.provider)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 初始化接口AI服务（如果配置为jiekouai）
        self.jiekouai_service: Optional[JiekouAIImageService] = None
        if self.image_config.provider == "jiekouai":
            self.jiekouai_service = JiekouAIImageService(
                api_key=self.api_key or "",
                base_url=getattr(settings, 'jiekouai_base_url', "https://api.jiekou.ai"),
                endpoint=getattr(settings, 'jiekouai_endpoint', "/v3/nano-banana-pro-light-t2i")
            )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
        # 同时关闭 jiekouai 服务
        if self.jiekouai_service:
            await self.jiekouai_service.close()
    
    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        seed: Optional[int] = None,
        steps: int = 30,
        cfg_scale: float = 7.0,
        reference_images: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        生成图片
        
        Args:
            prompt: 正面提示词
            negative_prompt: 负面提示词
            width: 图片宽度
            height: 图片高度
            seed: 随机种子
            steps: 生成步数
            cfg_scale: CFG比例
            reference_images: 参考图片URL列表
        
        Returns:
            包含图片URL或路径的字典
        """
        # 这里使用nanobanana API作为示例
        # 实际实现需要根据具体API调整
        
        session = await self._get_session()
        
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
            "cfg_scale": cfg_scale
        }
        
        if reference_images:
            payload["reference_images"] = reference_images
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with session.post(
            f"{self.image_config.base_url}/generate",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.image_config.timeout)
        ) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    "success": True,
                    "url": data.get("image_url"),
                    "seed": data.get("seed", seed),
                    "cost_usd": data.get("cost", 0.02)
                }
            else:
                error_text = await response.text()
                return {
                    "success": False,
                    "error": f"API错误: {response.status} - {error_text}"
                }
    
    async def generate_character_reference(
        self,
        character: Character,
        style_description: str,
        output_path: Path
    ) -> bool:
        """
        生成角色参考图
        
        Args:
            character: 角色对象
            style_description: 风格描述
            output_path: 输出路径
        
        Returns:
            是否成功
        """
        from src.services.llm_service import LLMService
        
        # 生成提示词
        llm_service = LLMService(self.config)
        prompt = await llm_service.generate_character_prompt(character, style_description)
        
        # 解析分辨率
        res = self.config.defaults.generation.character_ref_resolution
        
        # 根据provider选择生成方式
        if self.image_config.provider == "jiekouai" and self.jiekouai_service:
            actual_path = await self.jiekouai_service.generate_character_reference(
                prompt=f"{prompt}, {style_description}, high quality, detailed",
                output_path=output_path,
                size=res
            )
            if actual_path:
                # 更新版本信息
                version = character.add_version(
                    prompt=prompt,
                    seed=None,  # 接口AI不返回seed
                    path=str(actual_path)
                )
                version.cost_usd = 0.02
            return actual_path is not None
        else:
            # 使用默认方式
            width, height = map(int, res.split("x"))
            
            result = await self.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                seed=character.versions[-1].seed if character.versions else None
            )
            
            if result["success"]:
                await self._download_image(result["url"], output_path)
                
                version = character.add_version(
                    prompt=prompt,
                    seed=result.get("seed"),
                    path=str(output_path)
                )
                version.cost_usd = result.get("cost_usd")
                
                return True
            
            return False
    
    async def generate_scene_reference(
        self,
        scene: Scene,
        style_description: str,
        output_path: Path,
        reference_image_url: Optional[str] = None
    ) -> bool:
        """
        生成场景参考图
        
        Args:
            scene: 场景对象
            style_description: 风格描述
            output_path: 输出路径
            reference_image_url: 可选的参考图片URL (用于i2i生成)
        
        Returns:
            是否成功
        """
        from src.services.llm_service import LLMService
        
        llm_service = LLMService(self.config)
        prompt = await llm_service.generate_scene_prompt(scene, style_description)
        
        res = self.config.defaults.generation.scene_ref_resolution
        
        # 根据provider选择生成方式
        if self.image_config.provider == "jiekouai" and self.jiekouai_service:
            actual_path = await self.jiekouai_service.generate_scene_reference(
                prompt=f"{prompt}, {style_description}, high quality, detailed",
                output_path=output_path,
                size=res,
                reference_image_url=reference_image_url  # 传递参考图URL
            )
            if actual_path:
                version = scene.add_version(
                    prompt=prompt,
                    seed=None,
                    path=str(actual_path)
                )
                version.cost_usd = 0.02
            return actual_path is not None
        else:
            # 使用默认方式
            width, height = map(int, res.split("x"))
            
            result = await self.generate_image(
                prompt=prompt,
                width=width,
                height=height
            )
            
            if result["success"]:
                await self._download_image(result["url"], output_path)
                
                version = scene.add_version(
                    prompt=prompt,
                    seed=result.get("seed"),
                    path=str(output_path)
                )
                version.cost_usd = result.get("cost_usd")
                
                return True
            
            return False
    
    def _path_to_static_url(self, local_path: str) -> Optional[str]:
        """将本地文件路径转换为 static URL"""
        if not local_path:
            return None
        # 例如: /home/user/animation_projects/project_xxx/02_references/characters/char_001.png
        # 转换为: http://localhost:8000/static/project_xxx/02_references/characters/char_001.png
        import os
        if 'animation_projects' in local_path:
            parts = local_path.split('animation_projects/')
            if len(parts) > 1:
                relative_path = parts[1]  # project_xxx/02_references/characters/char_001.png
                return f"http://localhost:8000/static/{relative_path}"
        return None
    
    async def generate_keyframe(
        self,
        shot: Shot,
        character_refs: Dict[str, str],
        scene_ref: str,
        output_path: Path
    ) -> Optional[Path]:
        """
        生成视频首帧
        
        Args:
            shot: 分镜对象
            character_refs: 角色参考图路径字典 {character_id: path}
            scene_ref: 场景参考图路径
            output_path: 输出路径
        
        Returns:
            实际保存的路径，失败返回None
        """
        if not shot.image_prompt:
            print(f"❌ shot {shot.shot_id} 没有 image_prompt")
            return None
        
        res = self.config.defaults.generation.keyframe_resolution
        
        # 获取本地路径列表
        char_paths = [path for path in character_refs.values() if path]
        
        print(f"🎬 生成首帧: shot={shot.shot_id}, chars={len(char_paths)}, scene={scene_ref is not None}")
        
        # 根据provider选择生成方式
        if self.image_config.provider == "jiekouai" and self.jiekouai_service:
            # 接口AI方式（支持多图i2i）- 使用压缩后的场景图和人物图
            actual_path = await self.jiekouai_service.generate_keyframe(
                prompt=shot.image_prompt.positive,
                output_path=output_path,
                size=res,
                character_refs=char_paths,  # 人物参考图
                scene_ref=scene_ref  # 场景参考图
            )
            return actual_path
        else:
            # 默认方式
            width, height = map(int, res.split("x"))
            
            # 准备参考图（本地路径列表）
            ref_images = [scene_ref] if scene_ref else []
            ref_images.extend(character_refs.values())
            
            result = await self.generate_image(
                prompt=shot.image_prompt.positive,
                negative_prompt=shot.image_prompt.negative,
                width=width,
                height=height,
                seed=shot.image_prompt.parameters.get("seed"),
                steps=shot.image_prompt.parameters.get("steps", 30),
                cfg_scale=shot.image_prompt.parameters.get("cfg_scale", 7.0),
                reference_images=ref_images
            )
            
            if result["success"]:
                await self._download_image(result["url"], output_path)
                return output_path
            
            return None
    
    async def _download_image(self, url: str, output_path: Path):
        """下载图片到本地"""
        session = await self._get_session()
        
        async with session.get(url) as response:
            if response.status == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(await response.read())
    
    async def regenerate_with_seed(
        self,
        original_prompt: str,
        original_params: Dict[str, Any],
        new_seed: int,
        output_path: Path
    ) -> bool:
        """
        使用新seed重新生成
        
        Args:
            original_prompt: 原始提示词
            original_params: 原始参数
            new_seed: 新种子
            output_path: 输出路径
        
        Returns:
            是否成功
        """
        result = await self.generate_image(
            prompt=original_prompt,
            seed=new_seed,
            width=original_params.get("width", 512),
            height=original_params.get("height", 512),
            steps=original_params.get("steps", 30),
            cfg_scale=original_params.get("cfg_scale", 7.0)
        )
        
        if result["success"]:
            await self._download_image(result["url"], output_path)
            return True
        
        return False
