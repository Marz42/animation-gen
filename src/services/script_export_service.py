"""
分镜剧本导出服务
将分镜数据与原始剧本结合，生成带有分镜设计和对话强调的新版剧本
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from src.models.schemas import Project, Character, Scene, Shot, ShotType, CameraMovement
from src.core.project_manager import ProjectManager


class ScriptExportService:
    """分镜剧本导出服务"""
    
    # 镜头类型中文映射
    SHOT_TYPE_NAMES = {
        "wide": "全景",
        "medium": "中景",
        "close_up": "特写",
        "extreme_close_up": "大特写"
    }
    
    # 镜头运动中文映射
    CAMERA_MOVEMENT_NAMES = {
        "static": "静止",
        "pan": "平移",
        "tilt": "倾斜",
        "zoom": "缩放",
        "tracking": "跟随"
    }
    
    def __init__(self):
        self.project_manager = ProjectManager()
    
    async def export_shot_script(
        self,
        project: Project,
        include_dialogue: bool = True,
        include_camera_info: bool = True,
        include_action: bool = True,
        format_type: str = "markdown"
    ) -> Dict[str, any]:
        """
        导出分镜剧本
        
        Args:
            project: 项目对象
            include_dialogue: 是否包含对话（并强调）
            include_camera_info: 是否包含镜头信息
            include_action: 是否包含动作描述
            format_type: 输出格式 (markdown/html/docx)
        
        Returns:
            包含导出内容和文件路径的字典
        """
        # 加载数据
        characters = self.project_manager.load_characters(project)
        scenes = self.project_manager.load_scenes(project)
        shots = self.project_manager.load_shots(project)
        
        # 构建角色ID到名称的映射
        char_map = {c.character_id: c for c in characters}
        
        # 按场景分组分镜
        shots_by_scene: Dict[str, List[Shot]] = {}
        for shot in shots:
            if shot.scene_id not in shots_by_scene:
                shots_by_scene[shot.scene_id] = []
            shots_by_scene[shot.scene_id].append(shot)
        
        # 按sequence排序
        for scene_id in shots_by_scene:
            shots_by_scene[scene_id].sort(key=lambda s: s.sequence)
        
        # 生成剧本内容
        if format_type == "markdown":
            content = self._generate_markdown(
                project, scenes, shots_by_scene, char_map,
                include_dialogue, include_camera_info, include_action
            )
        elif format_type == "html":
            content = self._generate_html(
                project, scenes, shots_by_scene, char_map,
                include_dialogue, include_camera_info, include_action
            )
        else:
            content = self._generate_markdown(
                project, scenes, shots_by_scene, char_map,
                include_dialogue, include_camera_info, include_action
            )
        
        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.name}_分镜剧本_{timestamp}.{format_type if format_type != 'markdown' else 'md'}"
        output_path = Path(project.root_path) / "00_script" / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "content": content,
            "file_path": str(output_path),
            "filename": filename,
            "format": format_type,
            "stats": {
                "total_scenes": len(scenes),
                "total_shots": len(shots),
                "total_characters": len(characters)
            }
        }
    
    def _generate_markdown(
        self,
        project: Project,
        scenes: List[Scene],
        shots_by_scene: Dict[str, List[Shot]],
        char_map: Dict[str, Character],
        include_dialogue: bool,
        include_camera_info: bool,
        include_action: bool
    ) -> str:
        """生成Markdown格式的分镜剧本"""
        
        lines = []
        
        # 标题
        lines.append(f"# {project.name}")
        lines.append(f"## 分镜剧本")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**风格**: {project.style_description}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 角色表
        lines.append("## 角色表")
        lines.append("")
        for char in char_map.values():
            lines.append(f"- **{char.name}**: {char.description}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 按场景遍历
        for scene in scenes:
            lines.append(f"## 场景 {scene.scene_id}: {scene.name}")
            lines.append("")
            lines.append(f"**地点**: {scene.location}")
            lines.append(f"**时间**: {scene.time}")
            if scene.atmosphere:
                lines.append(f"**氛围**: {scene.atmosphere}")
            lines.append(f"**描述**: {scene.description}")
            lines.append("")
            
            # 该场景的分镜
            scene_shots = shots_by_scene.get(scene.scene_id, [])
            if scene_shots:
                lines.append(f"### 分镜列表 ({len(scene_shots)}个)")
                lines.append("")
                
                for shot in scene_shots:
                    lines.extend(self._format_shot_markdown(
                        shot, char_map, include_dialogue, include_camera_info, include_action
                    ))
                    lines.append("")
            else:
                lines.append("*暂无分镜*")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_shot_markdown(
        self,
        shot: Shot,
        char_map: Dict[str, Character],
        include_dialogue: bool,
        include_camera_info: bool,
        include_action: bool
    ) -> List[str]:
        """格式化单个分镜为Markdown"""
        lines = []
        
        # 分镜标题
        shot_type_name = self.SHOT_TYPE_NAMES.get(shot.type.value, shot.type.value)
        lines.append(f"#### 分镜 {shot.sequence}: {shot_type_name}")
        lines.append("")
        
        # 镜头信息
        if include_camera_info:
            movement_name = self.CAMERA_MOVEMENT_NAMES.get(shot.camera_movement.value, shot.camera_movement.value)
            lines.append(f"**镜头**: {shot_type_name} | **运动**: {movement_name} | **时长**: {shot.duration.value}")
            lines.append("")
        
        # 涉及角色
        if shot.characters:
            char_names = [char_map.get(cid, Character(character_id=cid, name=cid, description="", personality="")).name 
                         for cid in shot.characters]
            lines.append(f"**角色**: {', '.join(char_names)}")
            lines.append("")
        
        # 分镜描述
        lines.append(f"**画面**: {shot.description}")
        lines.append("")
        
        # 动作描述
        if include_action and shot.action:
            lines.append(f"**动作**: {shot.action}")
            lines.append("")
        
        # 对话（强调显示）
        if include_dialogue and shot.dialogue:
            lines.append("> 💬 **对话**")
            lines.append(">")
            # 处理多行对话
            dialogue_lines = shot.dialogue.strip().split('\n')
            for dline in dialogue_lines:
                lines.append(f"> {dline}")
            lines.append("")
        
        # 提示词（可选，简要显示）
        if shot.image_prompt:
            lines.append(f"*提示词: {shot.image_prompt.positive[:80]}...*")
            lines.append("")
        
        return lines
    
    def _generate_html(
        self,
        project: Project,
        scenes: List[Scene],
        shots_by_scene: Dict[str, List[Shot]],
        char_map: Dict[str, Character],
        include_dialogue: bool,
        include_camera_info: bool,
        include_action: bool
    ) -> str:
        """生成HTML格式的分镜剧本"""
        
        html_parts = []
        
        # HTML头部
        html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{} - 分镜剧本</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; background: #ecf0f1; padding: 10px; border-radius: 5px; }}
        h4 {{ color: #2980b9; margin-top: 20px; }}
        .meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }}
        .character-list {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .character-list li {{ margin: 5px 0; }}
        .shot {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; margin: 15px 0; }}
        .shot-header {{ font-weight: bold; color: #2980b9; margin-bottom: 10px; }}
        .shot-meta {{ font-size: 0.85em; color: #666; margin-bottom: 10px; }}
        .shot-description {{ margin: 10px 0; }}
        .dialogue {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 15px; 
            border-radius: 8px; 
            margin: 10px 0;
            font-weight: 500;
        }}
        .dialogue-label {{ font-size: 0.8em; opacity: 0.9; margin-bottom: 5px; }}
        .divider {{ border: none; border-top: 2px solid #ecf0f1; margin: 30px 0; }}
        .scene-info {{ background: #f1f3f4; padding: 10px 15px; border-radius: 5px; margin: 10px 0; }}
        .prompt {{ font-size: 0.8em; color: #95a5a6; font-style: italic; margin-top: 10px; }}
    </style>
</head>
<body>
""".format(project.name))
        
        # 标题部分
        html_parts.append(f"""
    <h1>{project.name}</h1>
    <h2>分镜剧本</h2>
    <div class="meta">
        <p><strong>生成时间</strong>: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>风格</strong>: {project.style_description}</p>
    </div>
    <hr class="divider">
""")
        
        # 角色表
        html_parts.append("    <h2>角色表</h2>")
        html_parts.append('    <ul class="character-list">')
        for char in char_map.values():
            html_parts.append(f"        <li><strong>{char.name}</strong>: {char.description}</li>")
        html_parts.append("    </ul>")
        html_parts.append('    <hr class="divider">')
        
        # 场景和分镜
        for scene in scenes:
            html_parts.append(f"""
    <h2>场景 {scene.scene_id}: {scene.name}</h2>
    <div class="scene-info">
        <p><strong>地点</strong>: {scene.location} | <strong>时间</strong>: {scene.time}</p>
        <p><strong>描述</strong>: {scene.description}</p>
    </div>
""")
            
            scene_shots = shots_by_scene.get(scene.scene_id, [])
            if scene_shots:
                html_parts.append(f"    <h3>分镜列表 ({len(scene_shots)}个)</h3>")
                
                for shot in scene_shots:
                    html_parts.extend(self._format_shot_html(
                        shot, char_map, include_dialogue, include_camera_info, include_action
                    ))
            else:
                html_parts.append("    <p><em>暂无分镜</em></p>")
            
            html_parts.append('    <hr class="divider">')
        
        # HTML尾部
        html_parts.append("""
</body>
</html>
""")
        
        return "\n".join(html_parts)
    
    def _format_shot_html(
        self,
        shot: Shot,
        char_map: Dict[str, Character],
        include_dialogue: bool,
        include_camera_info: bool,
        include_action: bool
    ) -> List[str]:
        """格式化单个分镜为HTML"""
        lines = []
        
        shot_type_name = self.SHOT_TYPE_NAMES.get(shot.type.value, shot.type.value)
        
        lines.append('    <div class="shot">')
        lines.append(f'        <div class="shot-header">分镜 {shot.sequence}: {shot_type_name}</div>')
        
        # 镜头信息
        if include_camera_info:
            movement_name = self.CAMERA_MOVEMENT_NAMES.get(shot.camera_movement.value, shot.camera_movement.value)
            lines.append(f'        <div class="shot-meta">镜头: {shot_type_name} | 运动: {movement_name} | 时长: {shot.duration.value}</div>')
        
        # 角色
        if shot.characters:
            char_names = [char_map.get(cid, Character(character_id=cid, name=cid, description="", personality="")).name 
                         for cid in shot.characters]
            lines.append(f'        <div class="shot-meta">角色: {", ".join(char_names)}</div>')
        
        # 描述
        lines.append(f'        <div class="shot-description"><strong>画面</strong>: {shot.description}</div>')
        
        # 动作
        if include_action and shot.action:
            lines.append(f'        <div class="shot-description"><strong>动作</strong>: {shot.action}</div>')
        
        # 对话（强调显示）
        if include_dialogue and shot.dialogue:
            dialogue_html = shot.dialogue.strip().replace('\n', '<br>')
            lines.append('        <div class="dialogue">')
            lines.append('            <div class="dialogue-label">💬 对话</div>')
            lines.append(f'            <div>{dialogue_html}</div>')
            lines.append('        </div>')
        
        # 提示词
        if shot.image_prompt:
            lines.append(f'        <div class="prompt">提示词: {shot.image_prompt.positive[:80]}...</div>')
        
        lines.append('    </div>')
        
        return lines
