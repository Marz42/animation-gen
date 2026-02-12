"""
分镜设计服务
根据场景和角色自动生成分镜
"""

import json
from typing import List, Dict, Optional
from datetime import datetime

from src.core.config import Config
from src.models.schemas import Scene, Character, Shot, ShotType, CameraMovement, VideoDuration, ImagePrompt, VideoPrompt
from src.services.llm_service import LLMService


class ShotDesignService:
    """分镜设计服务"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load_global()
        self.llm_service = LLMService(self.config)
    
    async def design_shots_for_scene(
        self,
        scene: Scene,
        characters: List[Character],
        style_description: str,
        script_segment: str
    ) -> List[Shot]:
        """
        为单个场景设计分镜
        
        Args:
            scene: 场景对象
            characters: 场景中的角色列表
            style_description: 风格描述
            script_segment: 剧本片段
        
        Returns:
            分镜列表
        """
        # 获取角色信息
        char_info = "\n".join([
            f"- {c.name}: {c.description} ({c.personality})"
            for c in characters
        ])
        
        # 构建提示词（使用 replace 避免 format 的 KeyError 问题）
        prompt_template = self.config.prompts.get("shot_design", "")
        
        # 安全替换占位符（统一使用 [[VAR]] 格式）
        replacements = {
            "[[SCENE_NAME]]": scene.name,
            "[[SCENE_DESCRIPTION]]": scene.description,
            "[[CHARACTERS]]": char_info,
            "[[SCRIPT_SEGMENT]]": script_segment
        }
        
        prompt = prompt_template
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        
        # 调用LLM生成分镜
        response = await self.llm_service.generate(prompt)
        
        # 解析JSON响应
        try:
            data = json.loads(self._extract_json(response))
            shots_data = data.get("shots", [])
        except json.JSONDecodeError:
            # 如果解析失败，创建默认分镜
            shots_data = self._create_default_shots(scene, characters)
        
        # 构建Shot对象
        shots = []
        scene_character_ids = {c.character_id for c in characters}  # 场景所有角色ID集合
        
        for i, shot_data in enumerate(shots_data):
            # 获取该分镜涉及的角色ID
            shot_character_ids = shot_data.get("character_ids", [])
            
            # 过滤：只保留实际属于该场景的角色ID
            # （LLM可能返回错误或多余的ID）
            valid_character_ids = [
                cid for cid in shot_character_ids 
                if cid in scene_character_ids
            ]
            
            # 如果没有返回有效角色，默认使用该场景所有角色（兼容旧逻辑）
            if not valid_character_ids:
                valid_character_ids = [c.character_id for c in characters]
                print(f"⚠️ 分镜 {scene.scene_id}_shot_{i+1:03d} 未返回有效character_ids，使用场景所有角色")
            else:
                print(f"✅ 分镜 {scene.scene_id}_shot_{i+1:03d} 涉及角色: {valid_character_ids}")
            
            shot = Shot(
                shot_id=f"{scene.scene_id}_shot_{i+1:03d}",
                scene_id=scene.scene_id,
                sequence=i + 1,
                type=ShotType(shot_data.get("type", "medium")),
                camera_movement=CameraMovement(shot_data.get("camera_movement", "static")),
                duration=VideoDuration(shot_data.get("duration", "5s")),
                description=shot_data.get("description", ""),
                action=shot_data.get("action", ""),
                dialogue=shot_data.get("dialogue"),
                characters=valid_character_ids
            )
            shots.append(shot)
        
        return shots
    
    async def generate_shot_prompts(
        self,
        shot: Shot,
        characters: List[Character],
        scene: Scene,
        style_description: str
    ) -> Shot:
        """
        为分镜生成图片和视频提示词
        
        Args:
            shot: 分镜对象
            characters: 角色列表
            scene: 场景对象
            style_description: 风格描述
        
        Returns:
            更新后的分镜对象
        """
        # 生成图片提示词
        image_prompt = await self._generate_image_prompt(
            shot, characters, scene, style_description
        )
        shot.image_prompt = image_prompt
        
        # 生成视频提示词
        video_prompt = await self._generate_video_prompt(shot)
        shot.video_prompt = video_prompt
        
        # 构建完整显示提示词
        shot.display_prompt = self._build_display_prompt(
            image_prompt, characters, scene, style_description
        )
        
        shot.updated_at = datetime.now()
        return shot
    
    async def _generate_image_prompt(
        self,
        shot: Shot,
        characters: List[Character],
        scene: Scene,
        style_description: str
    ) -> ImagePrompt:
        """生成图片提示词"""
        prompt_template = self.config.prompts.get("image_prompt", "")
        
        # 构建角色描述
        char_descriptions = "\n".join([
            f"{c.name}: {c.description}"
            for c in characters
        ])
        
        # 调用LLM生成
        prompt = f"""
基于以下信息生成AI图片生成提示词：

分镜描述: {shot.description}
涉及角色: {char_descriptions}
场景氛围: {scene.description}
镜头类型: {shot.type.value}
整体风格: {style_description}

请生成：
1. 详细的正面提示词（包含角色、场景、构图、光影、风格）
2. 负面提示词（需要避免的内容）

请以JSON格式输出：
{{
    "positive": "详细的正面提示词",
    "negative": "负面提示词"
}}
"""
        
        response = await self.llm_service.generate(prompt)
        
        try:
            data = json.loads(self._extract_json(response))
            return ImagePrompt(
                positive=data.get("positive", ""),
                negative=data.get("negative", ""),
                parameters={
                    "seed": None,
                    "steps": self.config.defaults.image.default_steps,
                    "cfg_scale": self.config.defaults.image.default_cfg
                }
            )
        except json.JSONDecodeError:
            # 返回默认提示词
            return ImagePrompt(
                positive=f"{shot.description}, {style_description}, high quality, detailed",
                negative="bad anatomy, bad hands, worst quality, low quality"
            )
    
    async def _generate_video_prompt(self, shot: Shot) -> VideoPrompt:
        """生成视频提示词"""
        prompt = f"""
基于以下分镜信息生成视频生成提示词：

分镜描述: {shot.description}
动作描述: {shot.action or '无'}
镜头运动: {shot.camera_movement.value}
持续时间: {shot.duration.value}

请生成一个详细的视频描述，包含：
1. 画面主体的动作描述
2. 相机运动方式
3. 光影变化（如果有）

输出格式：
- 视频描述（50-100字）
- 相机运动说明
"""
        
        response = await self.llm_service.generate(prompt)
        
        return VideoPrompt(
            description=response.strip(),
            camera=shot.camera_movement.value
        )
    
    def _build_display_prompt(
        self,
        image_prompt: ImagePrompt,
        characters: List[Character],
        scene: Scene,
        style_description: str
    ) -> str:
        """构建显示用的完整提示词"""
        parts = [
            f"Style: {style_description}",
            f"Scene: {scene.description}",
            f"Characters: {', '.join([c.name for c in characters])}",
            f"Prompt: {image_prompt.positive}",
            f"Negative: {image_prompt.negative}",
            f"Parameters: steps={image_prompt.parameters.get('steps', 30)}, cfg={image_prompt.parameters.get('cfg_scale', 7.0)}"
        ]
        return "\n\n".join(parts)
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        
        return text
    
    def _create_default_shots(self, scene: Scene, characters: List[Character]) -> List[Dict]:
        """创建默认分镜（当LLM解析失败时使用）"""
        char_names = ", ".join([c.name for c in characters]) if characters else "角色"
        
        return [
            {
                "type": "wide",
                "camera_movement": "static",
                "duration": "5s",
                "description": f"{scene.name}全景，展示{char_names}",
                "action": "场景介绍",
                "dialogue": None
            },
            {
                "type": "medium",
                "camera_movement": "static",
                "duration": "5s",
                "description": f"{char_names}中景对话",
                "action": "对话交流",
                "dialogue": None
            }
        ]
    
    def estimate_shot_count(self, scene_description: str) -> int:
        """估算场景需要的分镜数（基于描述复杂度）"""
        # 简单启发式：根据字数估算
        length = len(scene_description)
        if length < 50:
            return 2
        elif length < 150:
            return 3
        elif length < 300:
            return 4
        else:
            return 5
