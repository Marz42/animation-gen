"""
项目管理模块
处理项目的创建、加载、保存和文件结构管理
"""

import json
import shutil
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from src.models.schemas import Project, Character, Scene, Shot, Task, ProjectConfig
from src.core.config import Config


class ProjectManager:
    """项目管理器"""
    
    PROJECTS_ROOT = Path.home() / "animation_projects"
    
    def __init__(self):
        self.PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    
    def create_project(
        self,
        name: str,
        script_content: str,
        style_description: str,
        config_override: Optional[dict] = None
    ) -> Project:
        """
        创建新项目
        
        Args:
            name: 项目名称
            script_content: 剧本内容（Markdown）
            style_description: 风格描述
            config_override: 项目级配置覆盖
        
        Returns:
            Project对象
        """
        project_id = str(uuid4())[:8]
        project_path = self.PROJECTS_ROOT / f"{name}_{project_id}"
        
        # 创建目录结构
        self._create_project_structure(project_path)
        
        # 保存剧本
        script_path = project_path / "00_script" / "script.md"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # 创建项目配置
        config = ProjectConfig()
        if config_override:
            for key, value in config_override.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # 创建项目对象
        project = Project(
            project_id=project_id,
            name=name,
            script_path=str(script_path),
            root_path=str(project_path),
            style_description=style_description,
            config=config
        )
        
        # 保存项目元数据
        self._save_project_meta(project)
        
        # 保存项目配置
        if config_override:
            config_obj = Config.load_global()
            config_obj = Config._deep_merge_config(config_obj, {"defaults": config_override})
            config_obj.save_project_config(project_path)
        
        return project
    
    def _create_project_structure(self, project_path: Path):
        """创建项目目录结构"""
        directories = [
            "00_script",
            "01_extraction",
            "02_references/characters",
            "02_references/scenes",
            "03_keyframes",
            "04_videos",
            "05_audio",
            "06_placeholders",
            "logs",
            "history"
        ]
        
        for dir_path in directories:
            (project_path / dir_path).mkdir(parents=True, exist_ok=True)
        
        # 创建.gitkeep文件
        (project_path / "05_audio" / ".gitkeep").touch()
    
    def _save_project_meta(self, project: Project):
        """保存项目元数据"""
        meta_path = Path(project.root_path) / "project.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(project.model_dump(), f, indent=2, ensure_ascii=False, default=str)
    
    def load_project(self, project_id: str) -> Optional[Project]:
        """加载项目"""
        # 查找项目目录
        for project_dir in self.PROJECTS_ROOT.iterdir():
            if project_dir.is_dir() and project_id in project_dir.name:
                meta_path = project_dir / "project.json"
                if meta_path.exists():
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return Project(**data)
        return None
    
    def load_project_by_path(self, project_path: Path) -> Optional[Project]:
        """通过路径加载项目"""
        meta_path = project_path / "project.json"
        if meta_path.exists():
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Project(**data)
        return None
    
    def list_projects(self) -> List[Project]:
        """列出所有项目"""
        projects = []
        for project_dir in self.PROJECTS_ROOT.iterdir():
            if project_dir.is_dir():
                project = self.load_project_by_path(project_dir)
                if project:
                    projects.append(project)
        return sorted(projects, key=lambda p: p.created_at, reverse=True)
    
    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        project = self.load_project(project_id)
        if project:
            project_path = Path(project.root_path)
            if project_path.exists():
                shutil.rmtree(project_path)
                return True
        return False
    
    def update_project(self, project: Project):
        """更新项目元数据"""
        project.updated_at = datetime.now()
        self._save_project_meta(project)
    
    # === 角色管理 ===
    
    def save_characters(self, project: Project, characters: List[Character]):
        """保存角色列表"""
        characters_path = Path(project.root_path) / "01_extraction" / "characters.json"
        characters_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(characters_path, 'w', encoding='utf-8') as f:
                json.dump([c.model_dump() for c in characters], f, indent=2, ensure_ascii=False, default=str)
            print(f"💾 角色已保存到 {characters_path}")
        except Exception as e:
            print(f"❌ 保存角色失败: {e}")
            raise
        
        # 更新统计
        project.statistics.total_characters = len(characters)
        self.update_project(project)
    
    def load_characters(self, project: Project) -> List[Character]:
        """加载角色列表"""
        characters_path = Path(project.root_path) / "01_extraction" / "characters.json"
        if characters_path.exists():
            with open(characters_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Character(**item) for item in data]
        return []
    
    def update_character(self, project: Project, character: Character):
        """更新单个角色"""
        characters = self.load_characters(project)
        for i, c in enumerate(characters):
            if c.character_id == character.character_id:
                characters[i] = character
                break
        else:
            characters.append(character)
        
        self.save_characters(project, characters)
    
    # === 场景管理 ===
    
    def save_scenes(self, project: Project, scenes: List[Scene]):
        """保存场景列表"""
        scenes_path = Path(project.root_path) / "01_extraction" / "scenes.json"
        scenes_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(scenes_path, 'w', encoding='utf-8') as f:
                json.dump([s.model_dump() for s in scenes], f, indent=2, ensure_ascii=False, default=str)
            print(f"💾 场景已保存到 {scenes_path}")
        except Exception as e:
            print(f"❌ 保存场景失败: {e}")
            raise
        
        project.statistics.total_scenes = len(scenes)
        self.update_project(project)
    
    def load_scenes(self, project: Project) -> List[Scene]:
        """加载场景列表"""
        scenes_path = Path(project.root_path) / "01_extraction" / "scenes.json"
        if scenes_path.exists():
            with open(scenes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Scene(**item) for item in data]
        return []
    
    # === 分镜管理 ===
    
    def save_shots(self, project: Project, shots: List[Shot]):
        """保存分镜列表"""
        shots_path = Path(project.root_path) / "01_extraction" / "shots.json"
        with open(shots_path, 'w', encoding='utf-8') as f:
            json.dump([s.model_dump() for s in shots], f, indent=2, ensure_ascii=False, default=str)
        
        project.statistics.total_shots = len(shots)
        self.update_project(project)
    
    def load_shots(self, project: Project) -> List[Shot]:
        """加载分镜列表"""
        shots_path = Path(project.root_path) / "01_extraction" / "shots.json"
        if shots_path.exists():
            with open(shots_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Shot(**item) for item in data]
        return []
    
    def update_shot(self, project: Project, shot: Shot):
        """更新单个分镜"""
        shots = self.load_shots(project)
        for i, s in enumerate(shots):
            if s.shot_id == shot.shot_id:
                shots[i] = shot
                break
        self.save_shots(project, shots)
    
    # === 任务管理 ===
    
    def save_task(self, project: Project, task: Task):
        """保存任务（追加到历史记录）"""
        history_path = Path(project.root_path) / "history" / "tasks.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(task.model_dump(), ensure_ascii=False, default=str) + '\n')
    
    def load_tasks(self, project: Project, status: Optional[str] = None) -> List[Task]:
        """加载任务列表"""
        history_path = Path(project.root_path) / "history" / "tasks.jsonl"
        tasks = []
        
        if history_path.exists():
            with open(history_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        if status is None or data.get('status') == status:
                            tasks.append(Task(**data))
        
        return tasks
    
    def get_running_tasks(self, project: Project) -> List[Task]:
        """获取正在运行的任务"""
        return self.load_tasks(project, status="running")
    
    def recover_zombie_tasks(self, project: Project, timeout_seconds: int = 300):
        """
        恢复僵尸任务
        
        Args:
            project: 项目对象
            timeout_seconds: 超时时间（默认5分钟）
        
        Returns:
            恢复的僵尸任务数量
        """
        running_tasks = self.get_running_tasks(project)
        zombie_tasks = []
        
        now = datetime.now()
        for task in running_tasks:
            if task.started_at:
                elapsed = (now - task.started_at).total_seconds()
                if elapsed > timeout_seconds:
                    zombie_tasks.append(task)
        
        # 标记僵尸任务为失败
        for task in zombie_tasks:
            task.status = "failed"
            task.error_message = "Worker进程异常终止（僵尸任务恢复）"
            task.completed_at = now
            self.save_task(project, task)
        
        return len(zombie_tasks)
