"""
FastAPI后端入口
提供REST API接口
"""

import os
import sys
import asyncio
import shutil
import logging
import yaml
import random
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加项目根目录到路径（兼容不同启动方式）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn

from src.core.config import Config, settings
from src.core.project_manager import ProjectManager
from src.core.task_queue import get_queue, shutdown_all_queues, TaskPriority
from src.models.schemas import Project, Character, Scene, Shot, TaskStatus, ImagePrompt
from src.services.llm_service import LLMService
from src.services.image_service import ImageService
from src.services.video import VideoService
from src.services.shot_design_service import ShotDesignService
from src.services.video_monitor import get_video_monitor
from src.services.batch_pipeline import get_batch_pipeline_service, BatchJob, BatchTaskStatus


# 全局实例
project_manager = ProjectManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("🚀 启动动画生成系统...")
    
    # 启动任务队列
    llm_queue = get_queue("llm", max_workers=8)
    image_queue = get_queue("image", max_workers=4)
    video_queue = get_queue("video", max_workers=2)
    
    await llm_queue.start()
    await image_queue.start()
    await video_queue.start()
    
    # 启动视频状态监控服务
    video_monitor = get_video_monitor()
    await video_monitor.start()
    
    # 启动批量流水线服务
    batch_pipeline = get_batch_pipeline_service()
    await batch_pipeline.start()
    
    # 恢复僵尸任务
    for project in project_manager.list_projects():
        recovered = project_manager.recover_zombie_tasks(project, timeout_seconds=300)
        if recovered > 0:
            print(f"♻️ 项目 {project.name} 恢复了 {recovered} 个僵尸任务")
    
    yield
    
    # 关闭时
    print("🛑 关闭动画生成系统...")
    
    # 停止批量流水线服务
    batch_pipeline = get_batch_pipeline_service()
    await batch_pipeline.stop()
    
    # 停止视频状态监控服务
    video_monitor = get_video_monitor()
    await video_monitor.stop()
    
    await shutdown_all_queues()


app = FastAPI(
    title="动画生成系统 API",
    description="剧本到动画/动态漫画的自动化生成系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务 - 提供项目图片访问
projects_dir = Path.home() / "animation_projects"
if projects_dir.exists():
    app.mount("/static", StaticFiles(directory=str(projects_dir)), name="static")

# 临时文件服务 - 用于视频生成时的图片上传
temp_dir = Path.home() / "animation_projects" / "_temp"
temp_dir.mkdir(parents=True, exist_ok=True)
app.mount("/temp", StaticFiles(directory=str(temp_dir)), name="temp")


# ============ 请求/响应模型 ============

class CreateProjectRequest(BaseModel):
    name: str
    script_content: str
    style_description: str
    config_override: Optional[Dict] = None


class UpdateCharacterRequest(BaseModel):
    character_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    manual_override: Optional[Dict] = None


class ApproveRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None


class RegenerateRequest(BaseModel):
    method: str  # "seed" | "prompt" | "both"
    new_seed: Optional[int] = None
    new_prompt: Optional[str] = None


class DesignShotsRequest(BaseModel):
    scene_ids: Optional[List[str]] = None  # 如果为空，设计所有场景


class UpdateShotRequest(BaseModel):
    description: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[str] = None
    type: Optional[str] = None
    camera_movement: Optional[str] = None
    duration: Optional[str] = None
    manual_prompt: Optional[str] = None  # 手动覆盖提示词


class EditPromptRequest(BaseModel):
    """编辑提示词请求"""
    positive_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None  # 如 seed, steps, cfg_scale


class UploadPlaceholderRequest(BaseModel):
    shot_id: str
    description: Optional[str] = None


class CostEstimateResponse(BaseModel):
    shot_count: int
    total_seconds: int
    estimated_cost_usd: float
    provider: str


# ============ 项目API ============

@app.post("/api/projects", response_model=Project)
async def create_project(request: CreateProjectRequest):
    """创建新项目"""
    try:
        project = project_manager.create_project(
            name=request.name,
            script_content=request.script_content,
            style_description=request.style_description,
            config_override=request.config_override
        )
        return project
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects", response_model=List[Project])
async def list_projects():
    """列出所有项目"""
    return project_manager.list_projects()


@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """获取项目详情"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目"""
    success = project_manager.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"status": "deleted"}


# ============ 剧本解析API ============

@app.post("/api/projects/{project_id}/parse")
async def parse_script(project_id: str, background_tasks: BackgroundTasks):
    """解析剧本，提取角色和场景"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 更新状态
    project.current_stage = "extracting"
    project_manager.update_project(project)
    
    # 异步执行解析
    async def do_parse():
        try:
            print(f"🚀 开始解析项目 {project.name}...")
            
            # 读取剧本
            with open(project.script_path, 'r', encoding='utf-8') as f:
                script = f.read()
            print(f"📖 剧本长度: {len(script)} 字符")
            
            # 使用LLM解析
            llm_service = LLMService()
            print(f"🤖 LLM服务初始化完成，使用模型: {llm_service.llm_config.model}")
            
            # 提取角色
            print("🔍 提取角色...")
            characters_data = await llm_service.extract_characters(script)
            print(f"✅ 提取到 {len(characters_data)} 个角色")
            
            characters = [
                Character(
                    character_id=f"char_{i+1:03d}",
                    name=c.get("name", ""),
                    description=c.get("description", ""),
                    personality=c.get("personality", "")
                )
                for i, c in enumerate(characters_data)
            ]
            project_manager.save_characters(project, characters)
            print(f"💾 角色保存完成: {len(characters)} 个")
            
            # 提取场景
            print("🔍 提取场景...")
            scenes_data = await llm_service.extract_scenes(script)
            print(f"✅ 提取到 {len(scenes_data)} 个场景")
            
            scenes = [
                Scene(
                    scene_id=f"scene_{i+1:03d}",
                    name=s.get("name", ""),
                    description=s.get("description", ""),
                    location=s.get("location", ""),
                    time=s.get("time", "")
                )
                for i, s in enumerate(scenes_data)
            ]
            project_manager.save_scenes(project, scenes)
            print(f"💾 场景保存完成: {len(scenes_data)} 个")
            
            # 更新状态
            project.current_stage = "pending_review_extraction"
            project.statistics.total_characters = len(characters)
            project.statistics.total_scenes = len(scenes)
            project_manager.update_project(project)
            
            print(f"✅ 项目 {project.name} 剧本解析完成")
            
        except Exception as e:
            import traceback
            project.current_stage = "error"
            project_manager.update_project(project)
            print(f"❌ 项目 {project.name} 解析失败: {e}")
            print(traceback.format_exc())
    
    # 提交到LLM队列
    llm_queue = get_queue("llm")
    await llm_queue.submit(do_parse, priority=TaskPriority.NORMAL)
    
    return {"status": "parsing_started"}


@app.get("/api/projects/{project_id}/characters")
async def get_characters(project_id: str):
    """获取角色列表"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return project_manager.load_characters(project)


@app.get("/api/projects/{project_id}/scenes")
async def get_scenes(project_id: str):
    """获取场景列表"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return project_manager.load_scenes(project)


@app.put("/api/projects/{project_id}/characters/{character_id}")
async def update_character(project_id: str, character_id: str, request: UpdateCharacterRequest):
    """更新角色信息"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    characters = project_manager.load_characters(project)
    for char in characters:
        if char.character_id == character_id:
            if request.name:
                char.name = request.name
            if request.description:
                char.description = request.description
            if request.personality:
                char.personality = request.personality
            project_manager.save_characters(project, characters)
            return char
    
    raise HTTPException(status_code=404, detail="角色不存在")


# ============ 参考图生成API ============

@app.post("/api/projects/{project_id}/generate-references")
async def generate_references(project_id: str):
    """生成所有参考图（角色+场景）"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.current_stage = "generating_refs"
    project_manager.update_project(project)
    
    characters = project_manager.load_characters(project)
    scenes = project_manager.load_scenes(project)
    
    image_queue = get_queue("image")
    
    # 提交角色参考图生成任务
    for char in characters:
        async def gen_char_ref(c=char):
            image_service = ImageService()
            # 不带扩展名，让服务自动检测
            output_path = Path(project.root_path) / "02_references" / "characters" / c.character_id
            success = await image_service.generate_character_reference(
                c, project.style_description, output_path
            )
            if success:
                project_manager.update_character(project, c)
        
        await image_queue.submit(gen_char_ref, priority=TaskPriority.NORMAL)
    
    # 提交场景参考图生成任务
    for scene in scenes:
        async def gen_scene_ref(s=scene):
            image_service = ImageService()
            # 不带扩展名，让服务自动检测
            output_path = Path(project.root_path) / "02_references" / "scenes" / s.scene_id
            success = await image_service.generate_scene_reference(
                s, project.style_description, output_path
            )
            if success:
                # 保存场景
                scenes_list = project_manager.load_scenes(project)
                for i, sc in enumerate(scenes_list):
                    if sc.scene_id == s.scene_id:
                        scenes_list[i] = s
                        break
                project_manager.save_scenes(project, scenes_list)
        
        await image_queue.submit(gen_scene_ref, priority=TaskPriority.NORMAL)
    
    return {
        "status": "generating",
        "character_count": len(characters),
        "scene_count": len(scenes)
    }


@app.post("/api/projects/{project_id}/characters/{character_id}/approve")
async def approve_character(project_id: str, character_id: str, request: ApproveRequest):
    """审核角色参考图"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    characters = project_manager.load_characters(project)
    for char in characters:
        if char.character_id == character_id:
            version = char.get_current_version()
            if version:
                if request.approved:
                    version.status = "approved"
                    char.status = "approved"
                else:
                    version.status = "rejected"
                    version.rejected_reason = request.reason
                project_manager.save_characters(project, characters)
                return {"status": "updated"}
    
    raise HTTPException(status_code=404, detail="角色不存在")


@app.post("/api/projects/{project_id}/characters/{character_id}/regenerate")
async def regenerate_character(project_id: str, character_id: str, request: RegenerateRequest):
    """重新生成角色参考图"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    characters = project_manager.load_characters(project)
    for char in characters:
        if char.character_id == character_id:
            # 提交重新生成任务
            async def do_regenerate():
                image_service = ImageService()
                version = char.add_version(
                    prompt=request.new_prompt or "",
                    seed=request.new_seed
                )
                output_path = Path(project.root_path) / "02_references" / "characters" / f"{char.character_id}_v{version.version_id}.png"
                
                success = await image_service.generate_character_reference(
                    char, project.style_description, output_path
                )
                if success:
                    project_manager.update_character(project, char)
            
            image_queue = get_queue("image")
            await image_queue.submit(do_regenerate, priority=TaskPriority.HIGH)
            
            return {"status": "regenerating"}
    
    raise HTTPException(status_code=404, detail="角色不存在")


# ============ 分镜设计API ============

@app.post("/api/projects/{project_id}/design-shots")
async def design_shots(project_id: str, request: DesignShotsRequest):
    """自动生成分镜设计"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.current_stage = "designing_shots"
    project_manager.update_project(project)
    
    scenes = project_manager.load_scenes(project)
    characters = project_manager.load_characters(project)
    char_dict = {c.character_id: c for c in characters}
    
    # 读取剧本
    with open(project.script_path, 'r', encoding='utf-8') as f:
        script = f.read()
    
    llm_queue = get_queue("llm")
    
    async def do_design():
        shot_design_service = ShotDesignService()
        all_shots = []
        
        for scene in scenes:
            # 获取场景中的角色
            scene_chars = [char_dict[cid] for cid in scene.shots if cid in char_dict]
            if not scene_chars:
                # 如果场景没有关联角色，使用所有角色
                scene_chars = characters
            
            # 提取剧本片段（简化处理，实际应该更智能地分割）
            script_segment = _extract_scene_script(script, scene.name)
            
            # 生成分镜
            shots = await shot_design_service.design_shots_for_scene(
                scene, scene_chars, project.style_description, script_segment
            )
            
            # 为每个分镜生成提示词
            for shot in shots:
                shot = await shot_design_service.generate_shot_prompts(
                    shot, scene_chars, scene, project.style_description
                )
                all_shots.append(shot)
            
            # 更新场景的shots列表
            scene.shots = [s.shot_id for s in shots]
        
        # 保存所有分镜
        project_manager.save_shots(project, all_shots)
        project_manager.save_scenes(project, scenes)
        
        # 更新项目状态
        project.current_stage = "pending_review_shots"
        project.statistics.total_shots = len(all_shots)
        project_manager.update_project(project)
        
        print(f"✅ 项目 {project.name} 分镜设计完成，共 {len(all_shots)} 个分镜")
    
    await llm_queue.submit(do_design, priority=TaskPriority.NORMAL)
    
    return {"status": "designing", "scene_count": len(scenes)}


def _extract_scene_script(script: str, scene_name: str) -> str:
    """从剧本中提取场景相关的片段"""
    # 简化实现：按场景名称查找
    lines = script.split('\n')
    result = []
    in_scene = False
    
    for line in lines:
        if scene_name in line or f"## {scene_name}" in line:
            in_scene = True
        elif line.startswith('## ') and in_scene:
            break
        
        if in_scene:
            result.append(line)
    
    return '\n'.join(result) if result else script[:500]  # 默认返回前500字符


@app.get("/api/projects/{project_id}/shots")
async def get_shots(project_id: str, scene_id: Optional[str] = None):
    """获取分镜列表"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    
    if scene_id:
        shots = [s for s in shots if s.scene_id == scene_id]
    
    return shots


@app.get("/api/projects/{project_id}/shots/{shot_id}")
async def get_shot(project_id: str, shot_id: str):
    """获取单个分镜详情"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            return shot
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.put("/api/projects/{project_id}/shots/{shot_id}")
async def update_shot(project_id: str, shot_id: str, request: UpdateShotRequest):
    """更新分镜信息"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            if request.description:
                shot.description = request.description
            if request.action:
                shot.action = request.action
            if request.dialogue:
                shot.dialogue = request.dialogue
            if request.type:
                shot.type = request.type
            if request.camera_movement:
                shot.camera_movement = request.camera_movement
            if request.duration:
                shot.duration = request.duration
            if request.manual_prompt:
                # 手动覆盖提示词
                if not shot.image_prompt:
                    shot.image_prompt = ImagePrompt(positive="", negative="")
                shot.image_prompt.positive = request.manual_prompt
                shot.manual_override = {"prompt": request.manual_prompt, "enabled": True}
            
            project_manager.save_shots(project, shots)
            return shot
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.post("/api/projects/{project_id}/shots/{shot_id}/edit-prompt")
async def edit_shot_prompt(project_id: str, shot_id: str, request: EditPromptRequest):
    """编辑分镜的 Prompt"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            if not shot.image_prompt:
                shot.image_prompt = ImagePrompt(positive="", negative="")
            
            # 更新提示词
            if request.positive_prompt is not None:
                shot.image_prompt.positive = request.positive_prompt
            if request.negative_prompt is not None:
                shot.image_prompt.negative = request.negative_prompt
            if request.parameters:
                shot.image_prompt.parameters.update(request.parameters)
            
            # 标记为手动编辑
            shot.manual_override = {
                "prompt": shot.image_prompt.positive,
                "enabled": True,
                "edited_at": datetime.now().isoformat()
            }
            
            project_manager.save_shots(project, shots)
            return {"status": "updated", "shot_id": shot_id}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.post("/api/projects/{project_id}/shots/{shot_id}/redesign")
async def redesign_shot(project_id: str, shot_id: str, request: RegenerateRequest):
    """重新设计分镜（根据新描述重新生成提示词）"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    characters = project_manager.load_characters(project)
    scenes = project_manager.load_scenes(project)
    
    for shot in shots:
        if shot.shot_id == shot_id:
            async def do_redesign():
                from src.services.shot_design_service import ShotDesignService
                
                # 获取场景和角色信息
                scene = next((s for s in scenes if s.scene_id == shot.scene_id), None)
                shot_characters = [c for c in characters if c.character_id in shot.characters]
                
                # 更新描述（如果提供了新描述）
                if request.new_prompt:
                    shot.description = request.new_prompt
                
                # 重新生成提示词
                shot_design_service = ShotDesignService()
                shot = await shot_design_service.generate_shot_prompts(
                    shot, shot_characters, scene, project.style_description
                )
                
                # 保存
                project_manager.save_shots(project, shots)
                print(f"✅ 分镜 {shot.shot_id} 重新设计完成")
            
            llm_queue = get_queue("llm")
            await llm_queue.submit(do_redesign, priority=TaskPriority.HIGH)
            
            return {"status": "redesigning", "shot_id": shot_id}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.post("/api/projects/{project_id}/shots/{shot_id}/upload-placeholder")
async def upload_placeholder(
    project_id: str,
    shot_id: str,
    description: Optional[str] = None,
    file: UploadFile = File(...)
):
    """上传占位符图片（导演模式）"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            # 保存文件
            placeholder_dir = Path(project.root_path) / "06_placeholders"
            placeholder_dir.mkdir(exist_ok=True)
            
            file_path = placeholder_dir / f"{shot_id}_placeholder{Path(file.filename).suffix}"
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # 更新shot
            shot.placeholder.enabled = True
            shot.placeholder.type = "reference_image"
            shot.placeholder.path = str(file_path)
            shot.placeholder.description = description
            
            project_manager.save_shots(project, shots)
            
            return {"status": "uploaded", "path": str(file_path)}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


# ============ 首帧生成API ============

@app.post("/api/projects/{project_id}/generate-keyframes")
async def generate_keyframes(project_id: str, shot_ids: Optional[List[str]] = None):
    """生成视频首帧"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.current_stage = "generating_frames"
    project_manager.update_project(project)
    
    shots = project_manager.load_shots(project)
    characters = project_manager.load_characters(project)
    scenes = project_manager.load_scenes(project)
    
    # 过滤需要生成的分镜
    if shot_ids:
        shots = [s for s in shots if s.shot_id in shot_ids]
    
    # 构建参考图字典
    char_refs = {}
    for char in characters:
        version = char.get_current_version()
        if version and version.path:
            char_refs[char.character_id] = version.path
    
    scene_refs = {}
    for scene in scenes:
        version = scene.get_current_version()
        if version and version.path:
            scene_refs[scene.scene_id] = version.path
    
    image_queue = get_queue("image")
    
    for shot in shots:
        async def gen_keyframe(s=shot):
            try:
                # 创建batch
                batch_id = s.create_batch()
                
                image_service = ImageService()
                
                # 获取角色参考字典 {character_id: path}
                shot_char_refs = {cid: char_refs[cid] for cid in s.characters if cid in char_refs}
                scene_ref = scene_refs.get(s.scene_id)
                
                output_path = Path(project.root_path) / "03_keyframes" / f"{s.shot_id}_{batch_id}.png"
                
                print(f"🎬 开始生成首帧: shot={s.shot_id}, chars={list(shot_char_refs.keys())}, scene={scene_ref}")
                
                # 生成首帧
                actual_path = await image_service.generate_keyframe(
                    s, shot_char_refs, scene_ref, output_path
                )
                
                # 关闭服务释放资源
                await image_service.close()
                
                if actual_path:
                    batch = s.get_current_batch()
                    if batch:
                        batch["keyframe"] = {
                            "status": "completed",
                            "path": str(actual_path),
                            "prompt": s.image_prompt.positive if s.image_prompt else "",
                            "seed": s.image_prompt.parameters.get("seed") if s.image_prompt else None
                        }
                    s.status = "frame_pending_review"
                    project_manager.update_shot(project, s)
                    print(f"✅ 首帧生成完成: {s.shot_id} -> {actual_path}")
                else:
                    print(f"❌ 首帧生成失败: {s.shot_id}")
                    # 更新状态为失败
                    s.status = "frame_failed"
                    project_manager.update_shot(project, s)
            except Exception as e:
                print(f"❌ 首帧生成异常: {s.shot_id}, error={e}")
                import traceback
                traceback.print_exc()
                # 关闭服务释放资源
                await image_service.close()
                # 更新状态为失败
                s.status = "frame_failed"
                project_manager.update_shot(project, s)
        
        await image_queue.submit(gen_keyframe, priority=TaskPriority.NORMAL)
    
    return {
        "status": "generating",
        "shot_count": len(shots)
    }


@app.post("/api/projects/{project_id}/shots/{shot_id}/approve-keyframe")
async def approve_keyframe(project_id: str, shot_id: str, request: ApproveRequest):
    """审核首帧"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            batch = shot.get_current_batch()
            if batch and batch.get("keyframe"):
                if request.approved:
                    batch["keyframe"]["status"] = "approved"
                    shot.status = "frame_approved"
                else:
                    batch["keyframe"]["status"] = "rejected"
                    batch["keyframe"]["rejected_reason"] = request.reason
                
                project_manager.save_shots(project, shots)
                return {"status": "updated"}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.post("/api/projects/{project_id}/shots/{shot_id}/regenerate-keyframe")
async def regenerate_keyframe(project_id: str, shot_id: str, request: RegenerateRequest):
    """重新生成首帧"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            # 创建新batch
            batch_id = shot.create_batch()
            
            async def do_regenerate():
                image_service = ImageService()
                
                # 更新提示词或seed
                if request.new_prompt:
                    if not shot.image_prompt:
                        shot.image_prompt = ImagePrompt(positive="", negative="")
                    shot.image_prompt.positive = request.new_prompt
                
                if request.new_seed and shot.image_prompt:
                    shot.image_prompt.parameters["seed"] = request.new_seed
                
                # 重新生成
                characters = project_manager.load_characters(project)
                scenes = project_manager.load_scenes(project)
                
                char_refs = {c.character_id: c.get_current_version().path for c in characters if c.get_current_version()}
                scene_refs = {s.scene_id: s.get_current_version().path for s in scenes if s.get_current_version()}
                
                output_path = Path(project.root_path) / "03_keyframes" / f"{shot.shot_id}_{batch_id}.png"
                
                shot_char_refs = {cid: char_refs[cid] for cid in shot.characters if cid in char_refs}
                scene_ref = scene_refs.get(shot.scene_id)
                
                actual_path = await image_service.generate_keyframe(
                    shot, shot_char_refs, scene_ref, output_path
                )
                
                # 关闭服务释放资源
                await image_service.close()
                
                if actual_path:
                    batch = shot.get_current_batch()
                    if batch:
                        batch["keyframe"] = {
                            "status": "pending_review",
                            "path": str(actual_path),
                            "prompt": shot.image_prompt.positive if shot.image_prompt else "",
                            "seed": shot.image_prompt.parameters.get("seed") if shot.image_prompt else None
                        }
                    project_manager.update_shot(project, shot)
            
            image_queue = get_queue("image")
            await image_queue.submit(do_regenerate, priority=TaskPriority.HIGH)
            
            return {"status": "regenerating", "batch_id": batch_id}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


# ============ 成本预估API ============

@app.get("/api/projects/{project_id}/cost-estimate", response_model=CostEstimateResponse)
async def estimate_cost(project_id: str):
    """估算视频生成成本"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    
    video_service = VideoService()
    estimate = video_service.estimate_cost(len(shots), project.config.video_duration)
    
    return CostEstimateResponse(**estimate)


# ============ 视频生成API ============

class GenerateVideosRequest(BaseModel):
    """视频生成请求 (接口AI Sora-2 支持: duration=[4s,8s,12s], size=[720p,1080p])"""
    shot_ids: Optional[List[str]] = None  # 如果为空，生成所有已审核首帧的分镜
    duration: str = "4s"  # 4s/8s/12s
    size: str = "720p"  # 720p/1080p
    watermark: bool = False
    provider: Optional[str] = None  # 指定提供商ID，不指定则使用默认


@app.post("/api/projects/{project_id}/generate-videos")
async def generate_videos(project_id: str, request: GenerateVideosRequest):
    """批量生成视频"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.current_stage = "generating_videos"
    project_manager.update_project(project)
    
    shots = project_manager.load_shots(project)
    
    # 筛选需要生成分镜
    if request.shot_ids:
        shots = [s for s in shots if s.shot_id in request.shot_ids]
    else:
        # 默认生成所有已有审核通过首帧的分镜
        shots = [s for s in shots if s.status == "frame_approved"]
    
    if not shots:
        return {"status": "no_shots", "message": "没有可生成的分镜，请确保首帧已审核通过"}
    
    video_queue = get_queue("video")
    
    # 获取视频服务配置
    video_config = _get_video_service_config(request.provider)
    
    # 获取提供商显示名称
    provider_name = request.provider or os.getenv("VIDEO_PROVIDER", "jiekouai")
    
    submitted_count = 0
    
    for shot in shots:
        batch = shot.get_current_batch()
        if not batch or not batch.get("keyframe"):
            continue
        
        keyframe = batch["keyframe"]
        keyframe_path = Path(keyframe.get("path", ""))
        
        if not keyframe_path.exists():
            continue
        
        # 获取视频生成提示词
        prompt = shot.image_prompt.positive if shot.image_prompt else ""
        if not prompt:
            prompt = f"{shot.description} {shot.action}" if shot.description else "动画视频"
        
        async def gen_video(s=shot, kp=keyframe_path, p=prompt, b=batch):
            video_service = None
            try:
                video_service = VideoService(video_config)
                
                result = await video_service.generate_video(
                    prompt=p,
                    first_frame_path=str(kp),
                    duration=request.duration,
                    size=request.size,
                    watermark=request.watermark
                )
                
                if result.success:
                    # 保存任务ID
                    if "videos" not in b:
                        b["videos"] = []
                    
                    video_info = {
                        "task_id": result.task_id,
                        "status": result.status,
                        "duration": request.duration,
                        "size": request.size,
                        "prompt": p,
                        "provider": provider_name,  # 保存用户选择的提供商ID
                        "provider_impl": result.provider_info.get("provider", "jiekouai"),  # 实际使用的实现
                        "created_at": datetime.now().isoformat()
                    }
                    b["videos"].append(video_info)
                    s.status = "video_generating"
                    project_manager.update_shot(project, s)
                    print(f"✅ 分镜 {s.shot_id} 视频任务已提交: {result.task_id}")
                else:
                    print(f"❌ 分镜 {s.shot_id} 视频生成失败: {result.error_message}")
            except Exception as e:
                print(f"❌ 分镜 {s.shot_id} 视频生成异常: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if video_service:
                    await video_service.close()
        
        await video_queue.submit(gen_video, priority=TaskPriority.NORMAL)
        submitted_count += 1
    
    return {
        "status": "generating",
        "submitted_count": submitted_count,
        "duration": request.duration,
        "size": request.size
    }


@app.get("/api/projects/{project_id}/videos")
async def get_videos(project_id: str):
    """获取项目所有视频生成状态（包含首帧图片路径）"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    videos = []
    
    for shot in shots:
        batch = shot.get_current_batch()
        if batch:
            # 获取首帧图片路径
            keyframe_path = None
            if batch.get("keyframe"):
                keyframe_path = batch["keyframe"].get("path")
            
            # 获取视频列表
            shot_videos = batch.get("videos", [])
            
            # 构建基础信息
            base_info = {
                "shot_id": shot.shot_id,
                "sequence": shot.sequence,
                "scene_id": shot.scene_id,
                "keyframe_path": keyframe_path,
                "status": shot.status,
                "image_prompt": shot.image_prompt.dict() if shot.image_prompt else None,
                "video_prompt": shot.video_prompt.dict() if shot.video_prompt else None,
            }
            
            if shot_videos:
                for video in shot_videos:
                    videos.append({
                        **base_info,
                        **video
                    })
            else:
                # 即使没有视频，也返回分镜信息（用于待生成状态）
                videos.append({
                    **base_info,
                    "task_id": None,
                    "status": "pending",
                    "duration": None,
                    "size": None,
                    "prompt": None,
                    "provider": None,
                    "created_at": None
                })
    
    return videos


@app.get("/api/projects/{project_id}/videos/{shot_id}")
async def get_video_detail(project_id: str, shot_id: str):
    """获取单个分镜的视频详情"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            batch = shot.get_current_batch()
            if batch and batch.get("videos"):
                return {
                    "shot_id": shot_id,
                    "videos": batch["videos"]
                }
            return {"shot_id": shot_id, "videos": []}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.post("/api/projects/{project_id}/videos/{shot_id}/check-status")
async def check_video_status(project_id: str, shot_id: str):
    """检查视频生成状态"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    for shot in shots:
        if shot.shot_id == shot_id:
            batch = shot.get_current_batch()
            if batch and batch.get("videos"):
                # 从项目配置获取提供商设置
                provider = os.getenv("VIDEO_PROVIDER", "jiekouai")
                
                if provider == "mock":
                    video_config = {
                        "default": "mock",
                        "mock": {
                            "simulate_delay": 2,
                        }
                    }
                else:
                    video_config = {
                        "default": "jiekouai",
                        "jiekouai": {
                            "api_key": "sk_affBAM8S-pxy_fOTCLKwqGZMTR3uJY7C35HZKDhufHo",
                            "base_url": "https://api.jiekou.ai",
                        }
                    }
                
                video_service = VideoService(video_config)
                
                try:
                    for video in batch["videos"]:
                        if video.get("status") in ["submitted", "processing"] and video.get("task_id"):
                            try:
                                result = await video_service.check_status(video["task_id"])
                                
                                video["status"] = result.status
                                video["progress"] = result.progress
                                
                                if result.video_url:
                                    video["video_url"] = result.video_url
                                
                                if result.error_message:
                                    video["error"] = result.error_message
                                
                                # 如果已完成，下载视频
                                if result.status == "completed" and result.video_url:
                                    output_dir = Path(project.root_path) / "04_videos"
                                    output_dir.mkdir(exist_ok=True)
                                    output_path = output_dir / f"{shot_id}_{video.get('task_id', 'unknown')[:8]}.mp4"
                                    
                                    success = await video_service.download_video(
                                        result.video_url, str(output_path)
                                    )
                                    if success:
                                        video["local_path"] = str(output_path)
                                        shot.status = "completed"
                            except Exception as e:
                                video["error"] = str(e)
                    
                    project_manager.update_shot(project, shot)
                    return {"shot_id": shot_id, "videos": batch["videos"]}
                finally:
                    await video_service.close()
            
            return {"shot_id": shot_id, "videos": []}
    
    raise HTTPException(status_code=404, detail="分镜不存在")


class BatchDownloadRequest(BaseModel):
    """批量下载视频请求"""
    shot_ids: List[str]


@app.post("/api/projects/{project_id}/videos/batch-download")
async def batch_download_videos(project_id: str, request: BatchDownloadRequest):
    """
    批量获取视频下载链接
    
    返回每个shot_id对应的视频下载URL列表
    """
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    download_list = []
    
    for shot in shots:
        if shot.shot_id not in request.shot_ids:
            continue
        
        batch = shot.get_current_batch()
        if not batch or not batch.get("videos"):
            continue
        
        for video in batch["videos"]:
            # 只返回已完成的视频
            if video.get("status") != "completed":
                continue
            
            video_url = None
            
            # 优先使用本地路径
            if video.get("local_path"):
                parts = video["local_path"].split("animation_projects/")
                if len(parts) > 1:
                    video_url = f"/static/{parts[1]}"
            # 其次使用远程URL
            elif video.get("video_url"):
                video_url = video["video_url"]
            
            if video_url:
                download_list.append({
                    "shot_id": shot.shot_id,
                    "task_id": video.get("task_id"),
                    "url": video_url,
                    "filename": f"{shot.shot_id}.mp4"
                })
    
    return {
        "total": len(request.shot_ids),
        "available": len(download_list),
        "downloads": download_list
    }


# ============ 视频Prompt管理API ============

class GenerateVideoPromptRequest(BaseModel):
    """生成视频Prompt请求"""
    use_template: bool = True  # 是否使用模板生成


class VideoPromptResponse(BaseModel):
    """视频Prompt响应"""
    description: str
    camera: Optional[str] = None


@app.post("/api/projects/{project_id}/shots/{shot_id}/generate-video-prompt")
async def generate_video_prompt_endpoint(project_id: str, shot_id: str, request: GenerateVideoPromptRequest):
    """
    基于剧本场景片段和首帧提示词生成视频Prompt
    """
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    characters = project_manager.load_characters(project)
    scenes = project_manager.load_scenes(project)
    
    for shot in shots:
        if shot.shot_id == shot_id:
            # 获取场景信息
            scene = next((s for s in scenes if s.scene_id == shot.scene_id), None)
            if not scene:
                raise HTTPException(status_code=404, detail="场景不存在")
            
            # 获取角色信息
            shot_characters = [c for c in characters if c.character_id in shot.characters]
            
            # 获取首帧提示词
            image_prompt_text = ""
            if shot.image_prompt:
                image_prompt_text = shot.image_prompt.positive
            
            # 获取剧本片段（场景描述）
            scene_description = scene.description or ""
            
            # 加载配置和Prompt模板
            config = Config.load_global()
            prompt_template = config.prompts.get("video_prompt", "")
            
            if not prompt_template or not request.use_template:
                # 使用默认模板
                prompt_template = """基于以下信息生成视频生成提示词：

剧本场景描述：
[[SCENE_DESCRIPTION]]

首帧图片提示词：
[[IMAGE_PROMPT]]

角色信息：
[[CHARACTERS]]

分镜动作描述：[[ACTION]]
镜头运动：[[CAMERA_MOVEMENT]]
持续时间：[[DURATION]]

请生成一个详细的视频描述，包含：
1. 画面主体的动作描述
2. 相机运动方式
3. 光影变化（如果有）

只输出视频描述文本，不要解释。"""
            
            # 构建上下文
            characters_desc = "\n".join([f"- {c.name}: {c.description}" for c in shot_characters]) if shot_characters else "无"
            
            # 替换模板变量
            filled_prompt = prompt_template
            filled_prompt = filled_prompt.replace("[[SCENE_DESCRIPTION]]", scene_description)
            filled_prompt = filled_prompt.replace("[[IMAGE_PROMPT]]", image_prompt_text)
            filled_prompt = filled_prompt.replace("[[CHARACTERS]]", characters_desc)
            filled_prompt = filled_prompt.replace("[[ACTION]]", shot.action or "无")
            filled_prompt = filled_prompt.replace("[[CAMERA_MOVEMENT]]", shot.camera_movement.value if shot.camera_movement else "static")
            filled_prompt = filled_prompt.replace("[[DURATION]]", shot.duration.value if shot.duration else "5s")
            
            # 调用LLM生成视频Prompt
            try:
                llm_service = LLMService()
                response = await llm_service.generate(filled_prompt)
                
                # 解析响应
                description = response.strip()
                camera = shot.camera_movement.value if shot.camera_movement else "static"
                
                # 保存到shot
                from src.models.schemas import VideoPrompt
                shot.video_prompt = VideoPrompt(
                    description=description,
                    camera=camera
                )
                project_manager.save_shots(project, shots)
                
                return {
                    "status": "generated",
                    "video_prompt": {
                        "description": description,
                        "camera": camera
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"生成视频Prompt失败: {str(e)}")
    
    raise HTTPException(status_code=404, detail="分镜不存在")


class UpdateVideoPromptRequest(BaseModel):
    """更新视频Prompt请求"""
    description: str
    camera: Optional[str] = None


@app.post("/api/projects/{project_id}/shots/{shot_id}/video-prompt")
async def update_video_prompt(project_id: str, shot_id: str, request: UpdateVideoPromptRequest):
    """保存视频Prompt到分镜"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    
    for shot in shots:
        if shot.shot_id == shot_id:
            from src.models.schemas import VideoPrompt
            shot.video_prompt = VideoPrompt(
                description=request.description,
                camera=request.camera or (shot.camera_movement.value if shot.camera_movement else "static")
            )
            project_manager.save_shots(project, shots)
            
            return {
                "status": "updated",
                "video_prompt": shot.video_prompt.dict()
            }
    
    raise HTTPException(status_code=404, detail="分镜不存在")


@app.get("/api/projects/{project_id}/shots/{shot_id}/video-prompt")
async def get_video_prompt(project_id: str, shot_id: str):
    """获取分镜的视频Prompt"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    
    for shot in shots:
        if shot.shot_id == shot_id:
            if shot.video_prompt:
                return {
                    "status": "exists",
                    "video_prompt": shot.video_prompt.dict()
                }
            else:
                return {
                    "status": "not_found",
                    "video_prompt": None
                }
    
    raise HTTPException(status_code=404, detail="分镜不存在")


# ============ 首帧重新生成API（视频页面用） ============

class RegenerateKeyframeRequest(BaseModel):
    """重新生成首帧请求"""
    positive_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None


@app.post("/api/projects/{project_id}/shots/{shot_id}/regenerate-keyframe-from-video")
async def regenerate_keyframe_from_video(project_id: str, shot_id: str, request: RegenerateKeyframeRequest):
    """
    从视频生成页面重新生成首帧
    这会重置该分镜的视频状态，并触发首帧重新生成
    """
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shots = project_manager.load_shots(project)
    
    for shot in shots:
        if shot.shot_id == shot_id:
            batch = shot.get_current_batch()
            if not batch:
                raise HTTPException(status_code=400, detail="当前分镜没有batch，无法重新生成")
            
            # 更新提示词（如果提供了）
            if request.positive_prompt is not None or request.negative_prompt is not None:
                if not shot.image_prompt:
                    from src.models.schemas import ImagePrompt
                    shot.image_prompt = ImagePrompt(positive="", negative="")
                
                if request.positive_prompt is not None:
                    shot.image_prompt.positive = request.positive_prompt
                if request.negative_prompt is not None:
                    shot.image_prompt.negative = request.negative_prompt
            
            # 重置视频状态和视频数据
            shot.status = "frame_pending_review"  # 重置为首帧待审核状态
            if "videos" in batch:
                batch["videos"] = []  # 清空视频列表
            
            # 提交首帧生成任务
            async def do_regenerate():
                try:
                    from src.services.jiekouai_service import InterfaceAIService
                    
                    image_service = InterfaceAIService()
                    
                    # 生成新seed（如果没有提供）
                    new_seed = request.seed if request.seed is not None else random.randint(1, 999999999)
                    
                    # 使用已有的参考图（如果有）
                    ref_images = []
                    
                    # 调用图片生成
                    result = await image_service.generate_image(
                        prompt=shot.image_prompt.positive if shot.image_prompt else shot.description,
                        negative_prompt=shot.image_prompt.negative if shot.image_prompt else None,
                        seed=new_seed,
                        reference_images=ref_images
                    )
                    
                    if result.get("success"):
                        # 保存首帧
                        keyframe_dir = Path(project.root_path) / "03_keyframes" / shot.shot_id
                        keyframe_dir.mkdir(parents=True, exist_ok=True)
                        
                        import urllib.request
                        keyframe_path = keyframe_dir / f"keyframe_{new_seed}.png"
                        urllib.request.urlretrieve(result["url"], keyframe_path)
                        
                        # 更新batch
                        batch["keyframe"] = {
                            "path": str(keyframe_path),
                            "url": result["url"],
                            "status": "completed",
                            "seed": new_seed,
                            "created_at": datetime.now().isoformat()
                        }
                        
                        project_manager.save_shots(project, shots)
                        print(f"✅ 分镜 {shot.shot_id} 首帧重新生成完成: {keyframe_path}")
                    else:
                        batch["keyframe"] = {
                            "status": "failed",
                            "error": result.get("error", "未知错误"),
                            "created_at": datetime.now().isoformat()
                        }
                        project_manager.save_shots(project, shots)
                        print(f"❌ 分镜 {shot.shot_id} 首帧重新生成失败: {result.get('error')}")
                        
                except Exception as e:
                    print(f"❌ 分镜 {shot.shot_id} 首帧重新生成异常: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # 更新状态为失败
                    batch["keyframe"] = {
                        "status": "failed",
                        "error": str(e),
                        "created_at": datetime.now().isoformat()
                    }
                    project_manager.save_shots(project, shots)
                finally:
                    if 'image_service' in locals():
                        await image_service.close()
            
            # 先保存状态更新
            project_manager.save_shots(project, shots)
            
            # 提交到图片生成队列
            image_queue = get_queue("image")
            await image_queue.submit(do_regenerate, priority=TaskPriority.HIGH)
            
            return {
                "status": "regenerating",
                "shot_id": shot_id,
                "message": "首帧重新生成任务已提交，视频状态已重置"
            }
    
    raise HTTPException(status_code=404, detail="分镜不存在")


# ============ Webhook回调API ============

@app.post("/webhook/video/{provider}")
async def video_webhook(provider: str, request: Dict[Any, Any]):
    """接收视频生成完成的Webhook回调"""
    # 处理接口AI的回调
    if provider == "jiekouai":
        task_id = request.get("task_id")
        status = request.get("status")
        video_url = request.get("video_url")
        
        # TODO: 根据task_id找到对应的分镜并更新状态
        # 这里需要建立task_id到shot的映射
        
        return {"status": "received", "task_id": task_id}
    
    return {"status": "received"}


# ============ 任务状态API ============

@app.get("/api/queues/status")
async def get_queue_status():
    """获取所有队列状态"""
    return {
        "llm": {
            "pending": get_queue("llm").pending_count,
            "running": get_queue("llm").running_count,
            "completed": get_queue("llm").completed_count,
            "failed": get_queue("llm").failed_count
        },
        "image": {
            "pending": get_queue("image").pending_count,
            "running": get_queue("image").running_count,
            "completed": get_queue("image").completed_count,
            "failed": get_queue("image").failed_count
        },
        "video": {
            "pending": get_queue("video").pending_count,
            "running": get_queue("video").running_count,
            "completed": get_queue("video").completed_count,
            "failed": get_queue("video").failed_count
        }
    }


# ============ 视频提供商配置API ============

@app.get("/api/video-provider")
async def get_video_provider():
    """获取当前视频提供商配置"""
    from src.services.video.providers.config import get_provider_config, list_provider_configs
    
    provider_id = os.getenv("VIDEO_PROVIDER", "jiekouai")
    api_key_set = bool(os.getenv("JIEKOUAI_API_KEY"))
    
    # 获取提供商配置
    config = get_provider_config(provider_id)
    
    # 获取用户自定义的视频提供商
    custom_config = Config.load_global()
    custom_providers = []
    for provider in custom_config.providers.get("video", []):
        custom_providers.append({
            "id": _get_provider_id(provider),
            "name": _get_provider_attr(provider, "name"),
            "type": "custom",
            "base_url": _get_provider_attr(provider, "base_url"),
        })
    
    return {
        "current_provider": provider_id,
        "current_config": {
            "display_name": config.display_name,
            "durations": config.duration_param.options,
            "resolutions": config.resolution_param.options,
            "default_duration": config.duration_param.default,
            "default_resolution": config.resolution_param.default,
            "capabilities": config.capabilities,
        },
        "available_providers": [
            {
                "id": p.provider_id,
                "name": p.display_name,
                "durations": p.duration_param.options,
                "resolutions": p.resolution_param.options,
                "type": "builtin",
            }
            for p in list_provider_configs()
        ],
        "custom_providers": custom_providers,
        "api_key_configured": {
            "jiekouai": api_key_set
        }
    }


class SetVideoProviderRequest(BaseModel):
    provider: str  # "jiekouai" or "mock"


@app.post("/api/video-provider")
async def set_video_provider(request: SetVideoProviderRequest):
    """切换视频提供商（仅修改当前进程环境变量）"""
    if request.provider not in ["jiekouai", "mock"]:
        raise HTTPException(status_code=400, detail="不支持的提供商")
    
    os.environ["VIDEO_PROVIDER"] = request.provider
    
    return {
        "status": "updated",
        "provider": request.provider,
        "note": "此更改仅在当前服务器进程有效，重启后会恢复默认值"
    }


# ============ 提示词管理API ============

class UpdatePromptsRequest(BaseModel):
    character_extraction: Optional[str] = None
    scene_extraction: Optional[str] = None
    character_ref_prompt: Optional[str] = None
    scene_ref_prompt: Optional[str] = None
    shot_design: Optional[str] = None
    image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None


@app.get("/api/config/prompts")
async def get_prompts():
    """获取当前提示词配置"""
    config = Config.load_global()
    return {
        "character_extraction": config.prompts.get("character_extraction", ""),
        "scene_extraction": config.prompts.get("scene_extraction", ""),
        "character_ref_prompt": config.prompts.get("character_ref_prompt", ""),
        "scene_ref_prompt": config.prompts.get("scene_ref_prompt", ""),
        "shot_design": config.prompts.get("shot_design", ""),
        "image_prompt": config.prompts.get("image_prompt", ""),
        "video_prompt": config.prompts.get("video_prompt", "")
    }


@app.put("/api/config/prompts")
async def update_prompts(request: UpdatePromptsRequest):
    """更新提示词配置"""
    config = Config.load_global()
    
    if request.character_extraction is not None:
        config.prompts["character_extraction"] = request.character_extraction
    if request.scene_extraction is not None:
        config.prompts["scene_extraction"] = request.scene_extraction
    if request.character_ref_prompt is not None:
        config.prompts["character_ref_prompt"] = request.character_ref_prompt
    if request.scene_ref_prompt is not None:
        config.prompts["scene_ref_prompt"] = request.scene_ref_prompt
    if request.shot_design is not None:
        config.prompts["shot_design"] = request.shot_design
    if request.image_prompt is not None:
        config.prompts["image_prompt"] = request.image_prompt
    if request.video_prompt is not None:
        config.prompts["video_prompt"] = request.video_prompt
    
    # 保存到全局配置
    config_path = Path.home() / ".animation_gen" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config.model_dump(), f, allow_unicode=True, default_flow_style=False)
    
    return {"status": "updated"}


# ============ 重新生成API ============

class RegenerateRequest(BaseModel):
    method: str = "seed"  # seed, prompt, both
    new_seed: Optional[int] = None
    new_prompt: Optional[str] = None


@app.post("/api/projects/{project_id}/characters/{character_id}/regenerate")
async def regenerate_character(project_id: str, character_id: str, request: RegenerateRequest):
    """重新生成角色参考图"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    characters = project_manager.load_characters(project)
    for char in characters:
        if char.character_id == character_id:
            # 提交重新生成任务
            async def do_regenerate():
                from src.services.jiekouai_service import JiekouAIImageService
                
                config = Config.load_global()
                image_config = config.get_image_config()
                
                service = JiekouAIImageService(
                    api_key=settings.jiekouai_api_key,
                    base_url=image_config.base_url,
                    endpoint=image_config.endpoint
                )
                
                # 创建新版本
                version = char.add_version(
                    prompt=request.new_prompt or "",
                    seed=request.new_seed
                )
                
                # 生成文件名（不带扩展名，让API决定）
                output_path = Path(project.root_path) / "02_references" / "characters" / f"{char.character_id}_v{version.version_id}"
                
                # 构建给LLM的指令提示词
                if request.new_prompt:
                    # 用户直接提供的是图片提示词
                    image_prompt = request.new_prompt
                else:
                    # 使用模板构建给LLM的指令
                    prompt_template = config.prompts.get("character_ref_prompt", "")
                    llm_prompt = prompt_template.replace("[[NAME]]", char.name or "")
                    llm_prompt = llm_prompt.replace("[[DESCRIPTION]]", char.description or "")
                    llm_prompt = llm_prompt.replace("[[PERSONALITY]]", char.personality or "")
                    llm_prompt = llm_prompt.replace("[[STYLE]]", project.style_description or "")
                    
                    # 调用LLM生成英文图片提示词
                    print(f"  🤖 调用LLM生成角色图片提示词...")
                    from src.services.llm_service import LLMService
                    llm_service = LLMService(config)
                    image_prompt = await llm_service.generate(llm_prompt)
                    print(f"  🤖 LLM返回: {image_prompt[:80]}...")
                
                # 使用英文提示词生成图片
                result = await service.generate_image(
                    prompt=image_prompt,
                    width=512,
                    height=512
                )
                
                try:
                    if result.get("success") and result.get("url"):
                        # 下载图片，自动检测扩展名
                        actual_path = await service._download_image_with_ext(result["url"], output_path)
                        version.path = str(actual_path)
                        version.status = "pending_review"
                        project_manager.save_characters(project, characters)
                        print(f"✅ 角色 {char.name} 重新生成完成")
                    else:
                        version.status = "failed"
                        version.rejected_reason = result.get("error", "未知错误")
                        project_manager.save_characters(project, characters)
                        print(f"❌ 角色 {char.name} 重新生成失败: {result.get('error')}")
                finally:
                    await service.close()
            
            image_queue = get_queue("image")
            await image_queue.submit(do_regenerate, priority=TaskPriority.HIGH)
            
            return {"status": "regenerating"}
    
    raise HTTPException(status_code=404, detail="角色不存在")


@app.post("/api/projects/{project_id}/scenes/{scene_id}/regenerate")
async def regenerate_scene(project_id: str, scene_id: str, request: RegenerateRequest):
    """重新生成场景参考图"""
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    scenes = project_manager.load_scenes(project)
    for scene in scenes:
        if scene.scene_id == scene_id:
            # 提交重新生成任务
            async def do_regenerate():
                from src.services.jiekouai_service import JiekouAIImageService
                
                config = Config.load_global()
                image_config = config.get_image_config()
                
                service = JiekouAIImageService(
                    api_key=settings.jiekouai_api_key,
                    base_url=image_config.base_url,
                    endpoint=image_config.endpoint
                )
                
                # 创建新版本
                version = scene.add_version(
                    prompt=request.new_prompt or "",
                    seed=request.new_seed
                )
                
                # 生成文件名（不带扩展名，让API决定）
                output_path = Path(project.root_path) / "02_references" / "scenes" / f"{scene.scene_id}_v{version.version_id}"
                
                # 构建给LLM的指令提示词
                if request.new_prompt:
                    # 用户直接提供的是图片提示词，不需要再让LLM生成
                    image_prompt = request.new_prompt
                else:
                    # 使用模板构建给LLM的指令
                    prompt_template = config.prompts.get("scene_ref_prompt", "")
                    llm_prompt = prompt_template.replace("[[NAME]]", scene.name or "")
                    llm_prompt = llm_prompt.replace("[[DESCRIPTION]]", scene.description or "")
                    llm_prompt = llm_prompt.replace("[[LOCATION]]", scene.location or "")
                    llm_prompt = llm_prompt.replace("[[TIME]]", scene.time or "")
                    llm_prompt = llm_prompt.replace("[[STYLE]]", project.style_description or "")
                    
                    print(f"  📝 给LLM的指令: {llm_prompt[:100]}...")
                    
                    # 调用LLM生成英文图片提示词
                    print(f"  🤖 调用LLM生成图片提示词...")
                    from src.services.llm_service import LLMService
                    llm_service = LLMService(config)
                    image_prompt = await llm_service.generate(llm_prompt)
                    print(f"  🤖 LLM返回的图片提示词: {image_prompt[:100]}...")
                
                # 使用英文提示词生成图片
                print(f"  🎨 开始生成图片，提示词: {image_prompt[:80]}...")
                result = await service.generate_image(
                    prompt=image_prompt,
                    width=512,
                    height=512
                )
                
                try:
                    if result.get("success") and result.get("url"):
                        # 下载图片，自动检测扩展名
                        actual_path = await service._download_image_with_ext(result["url"], output_path)
                        version.path = str(actual_path)
                        version.status = "pending_review"
                        project_manager.save_scenes(project, scenes)
                        print(f"✅ 场景 {scene.name} 重新生成完成")
                    else:
                        version.status = "failed"
                        version.rejected_reason = result.get("error", "未知错误")
                        project_manager.save_scenes(project, scenes)
                        print(f"❌ 场景 {scene.name} 重新生成失败: {result.get('error')}")
                finally:
                    await service.close()
            
            image_queue = get_queue("image")
            await image_queue.submit(do_regenerate, priority=TaskPriority.HIGH)
            
            return {"status": "regenerating"}
    
    raise HTTPException(status_code=404, detail="场景不存在")


# ============ 配置导入/导出API ============

@app.get("/api/config/export")
async def export_config():
    """导出完整配置（包括 prompts 和 API提供商配置）"""
    try:
        config = Config.load_global()
        return config.export_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出配置失败: {str(e)}")


class ImportConfigRequest(BaseModel):
    config: Dict[str, Any]


@app.post("/api/config/import")
async def import_config(request: ImportConfigRequest):
    """导入配置，验证JSON格式后保存"""
    try:
        # 验证配置格式
        config = Config.import_config(request.config)
        # 保存到全局配置
        config.save_global_config(use_json=True)
        return {"status": "success", "message": "配置导入成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置导入失败: {str(e)}")


# ============ API提供商管理API ============

class APIProviderRequest(BaseModel):
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


def _has_user_default_provider(config: Config, provider_type: str) -> bool:
    """检查是否有用户自定义的默认提供商"""
    providers = config.providers.get(provider_type, [])
    for p in providers:
        if _get_provider_attr(p, "is_default"):
            return True
    return False


def _convert_defaults_to_providers(config: Config) -> Dict[str, List[Dict]]:
    """将defaults配置转换为APIProvider格式
    
    这样可以在前端统一显示配置文件中的默认API设置
    如果用户设置了自定义默认提供商，内置提供商的is_default将为False
    """
    builtin_providers = {"llm": [], "image": [], "video": []}
    
    # 检查各类型是否有用户自定义默认提供商
    llm_has_default = _has_user_default_provider(config, "llm")
    image_has_default = _has_user_default_provider(config, "image")
    video_has_default = _has_user_default_provider(config, "video")
    
    # LLM 默认配置
    llm_config = config.defaults.llm
    if llm_config.base_url:
        builtin_providers["llm"].append({
            "id": "builtin_llm",
            "name": f"内置LLM ({llm_config.provider})",
            "type": "llm",
            "enabled": True,
            "is_default": not llm_has_default,  # 只有没有用户默认时才为True
            "is_builtin": True,  # 标记为内置配置
            "base_url": llm_config.base_url,
            "model": llm_config.model,
            "timeout": llm_config.timeout,
            "api_key": None,  # 不显示API Key
            "endpoint": None,
            "headers": {},
            "custom_fields": {
                "temperature": llm_config.temperature,
                "max_tokens": llm_config.max_tokens
            },
            "verified": None,
            "latency": None
        })
    
    # Image 默认配置
    image_config = config.defaults.image
    if image_config.base_url:
        builtin_providers["image"].append({
            "id": "builtin_image",
            "name": f"内置Image ({image_config.provider})",
            "type": "image",
            "enabled": True,
            "is_default": not image_has_default,  # 只有没有用户默认时才为True
            "is_builtin": True,
            "base_url": image_config.base_url,
            "model": None,
            "endpoint": image_config.endpoint,
            "timeout": image_config.timeout,
            "api_key": None,
            "headers": {},
            "custom_fields": {
                "default_steps": image_config.default_steps,
                "default_cfg": image_config.default_cfg
            },
            "verified": None,
            "latency": None
        })
    
    # Video 默认配置
    video_config = config.defaults.video
    if video_config.base_url:
        builtin_providers["video"].append({
            "id": "builtin_video",
            "name": f"内置Video ({video_config.provider})",
            "type": "video",
            "enabled": True,
            "is_default": not video_has_default,  # 只有没有用户默认时才为True
            "is_builtin": True,
            "base_url": video_config.base_url,
            "model": None,
            "timeout": video_config.timeout,
            "api_key": None,
            "endpoint": None,
            "headers": {},
            "custom_fields": {
                "duration": video_config.duration
            },
            "verified": None,
            "latency": None
        })
    
    return builtin_providers


@app.get("/api/providers")
async def get_providers():
    """获取所有API提供商配置
    
    返回内容包括：
    1. 配置文件中的默认API设置（内置提供商）
    2. 用户手动添加的API提供商
    """
    try:
        config = Config.load_global()
        
        # 获取内置提供商（来自defaults配置）
        builtin_providers = _convert_defaults_to_providers(config)
        
        # 合并内置提供商和用户添加的提供商
        result = {
            "llm": builtin_providers["llm"] + [p.model_dump() if hasattr(p, 'model_dump') else p for p in config.providers.get("llm", [])],
            "image": builtin_providers["image"] + [p.model_dump() if hasattr(p, 'model_dump') else p for p in config.providers.get("image", [])],
            "video": builtin_providers["video"] + [p.model_dump() if hasattr(p, 'model_dump') else p for p in config.providers.get("video", [])],
        }
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取提供商失败: {str(e)}")


@app.post("/api/providers")
async def add_provider(request: APIProviderRequest):
    """添加新提供商"""
    try:
        config = Config.load_global()
        
        # 生成唯一ID
        import uuid
        provider_id = str(uuid.uuid4())[:8]
        
        from datetime import datetime
        provider_data = {
            "id": provider_id,
            "name": request.name,
            "type": request.type,
            "enabled": request.enabled,
            "base_url": request.base_url,
            "api_key": request.api_key,
            "model": request.model,
            "endpoint": request.endpoint,
            "headers": request.headers or {},
            "timeout": request.timeout,
            "custom_fields": request.custom_fields or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        # 确保providers结构存在
        if request.type not in config.providers:
            config.providers[request.type] = []
        
        config.providers[request.type].append(provider_data)
        config.save_global_config(use_json=True)
        
        return {"status": "success", "provider": provider_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加提供商失败: {str(e)}")


def _get_provider_id(provider) -> str:
    """获取提供商ID（支持字典和APIProvider对象）"""
    if isinstance(provider, dict):
        return provider.get("id")
    return getattr(provider, "id", None)


def _get_provider_attr(provider, attr: str, default=None):
    """获取提供商属性（支持字典和APIProvider对象）"""
    if isinstance(provider, dict):
        return provider.get(attr, default)
    return getattr(provider, attr, default)


def _set_provider_attr(provider, attr: str, value):
    """设置提供商属性（支持字典和APIProvider对象）"""
    if isinstance(provider, dict):
        provider[attr] = value
    else:
        setattr(provider, attr, value)


def _get_video_service_config(provider_id: Optional[str] = None) -> dict:
    """
    获取视频服务配置
    
    支持三种模式：
    1. mock: 模拟提供商
    2. jiekouai: 接口AI内置提供商
    3. generic: 通用提供商（通过 request_template 配置）
    
    Args:
        provider_id: 提供商ID，如果为None则使用环境变量或默认配置
    
    Returns:
        视频服务配置字典
    """
    # 如果未指定提供商，使用环境变量或默认
    if not provider_id:
        provider_id = os.getenv("VIDEO_PROVIDER", "jiekouai")
    
    # 检查是否为mock
    if provider_id == "mock":
        return {
            "default": "mock",
            "mock": {"simulate_delay": 2}
        }
    
    # 尝试从配置中加载自定义提供商
    config = Config.load_global()
    
    # 查找视频类型的提供商
    for provider in config.providers.get("video", []):
        if _get_provider_id(provider) == provider_id:
            # 检查是否有 request_template，有则使用通用提供商
            custom_fields = _get_provider_attr(provider, "custom_fields", {})
            request_template = custom_fields.get("request_template")
            
            if request_template:
                # 使用通用提供商
                return {
                    "default": "generic",
                    "generic": {
                        "api_key": _get_provider_attr(provider, "api_key", ""),
                        "base_url": _get_provider_attr(provider, "base_url", ""),
                        "request_template": request_template,
                        "parameter_mapping": custom_fields.get("parameter_mapping", {}),
                        "response_parser": custom_fields.get("response_parser", {}),
                        "status_query": custom_fields.get("status_query", {}),
                    }
                }
            
            # 否则使用 jiekouai 作为实现（接口AI兼容）
            return {
                "default": "jiekouai",
                "jiekouai": {
                    "api_key": _get_provider_attr(provider, "api_key", "") or os.getenv("JIEKOUAI_API_KEY", ""),
                    "base_url": _get_provider_attr(provider, "base_url", "https://api.jiekou.ai"),
                    "endpoint": _get_provider_attr(provider, "endpoint"),
                    "headers": _get_provider_attr(provider, "headers", {}),
                }
            }
    
    # 默认使用内置的jiekouai配置
    return {
        "default": "jiekouai",
        "jiekouai": {
            "api_key": os.getenv("JIEKOUAI_API_KEY", ""),
            "base_url": "https://api.jiekou.ai",
        }
    }


@app.put("/api/providers/{provider_id}")
async def update_provider(provider_id: str, request: APIProviderRequest):
    """更新提供商"""
    try:
        config = Config.load_global()
        
        # 查找并更新提供商
        found = False
        for provider_type, providers in config.providers.items():
            for i, provider in enumerate(providers):
                if _get_provider_id(provider) == provider_id:
                    # 更新字段
                    from datetime import datetime
                    _set_provider_attr(provider, "name", request.name)
                    _set_provider_attr(provider, "type", request.type)
                    _set_provider_attr(provider, "enabled", request.enabled)
                    _set_provider_attr(provider, "base_url", request.base_url)
                    _set_provider_attr(provider, "api_key", request.api_key)
                    _set_provider_attr(provider, "model", request.model)
                    _set_provider_attr(provider, "endpoint", request.endpoint)
                    _set_provider_attr(provider, "headers", request.headers or {})
                    _set_provider_attr(provider, "timeout", request.timeout)
                    _set_provider_attr(provider, "custom_fields", request.custom_fields or {})
                    _set_provider_attr(provider, "updated_at", datetime.now().isoformat())
                    found = True
                    break
            if found:
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        config.save_global_config(use_json=True)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新提供商失败: {str(e)}")


@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除提供商"""
    try:
        config = Config.load_global()
        
        # 查找并删除提供商
        found = False
        for provider_type, providers in config.providers.items():
            for i, provider in enumerate(providers):
                if _get_provider_id(provider) == provider_id:
                    providers.pop(i)
                    found = True
                    break
            if found:
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        config.save_global_config(use_json=True)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除提供商失败: {str(e)}")


class ParseCurlRequest(BaseModel):
    curl_command: str


def _generate_generic_provider_config(parsed_result: dict, data_json: dict) -> dict:
    """
    根据解析的CURL命令生成通用提供商配置
    
    自动生成 request_template, parameter_mapping, response_parser, status_query
    """
    import json
    
    base_url = parsed_result.get("base_url", "")
    endpoint = parsed_result.get("endpoint", "")
    headers = parsed_result.get("headers", {})
    method = parsed_result.get("method", "POST")
    
    # 构建请求模板
    request_template = {
        "url": f"{base_url}{endpoint}" if base_url and endpoint else f"{base_url}/v3/async/sora-2-video-reverse",
        "method": method,
        "headers": {}
    }
    
    # 处理 headers，替换敏感信息为模板变量
    for key, value in headers.items():
        if key.lower() in ["authorization", "x-api-key"]:
            # API key 替换为模板变量
            request_template["headers"][key] = "Bearer {{api_key}}" if "Bearer" in value else "{{api_key}}"
        else:
            request_template["headers"][key] = value
    
    # 构建 body 模板
    body_template_dict = {}
    parameter_mapping = {
        "duration": {},
        "resolution": {}
    }
    
    for key, value in data_json.items():
        if key == "prompt":
            body_template_dict[key] = "{{prompt}}"
        elif key == "image":
            body_template_dict[key] = "{{image_base64}}"
        elif key == "duration":
            body_template_dict[key] = "{{duration}}"
            # 推断 duration 映射
            if isinstance(value, int):
                if value <= 5:
                    parameter_mapping["duration"] = {"4s": value}
                elif value <= 10:
                    parameter_mapping["duration"] = {"10s": value}
                else:
                    parameter_mapping["duration"] = {"15s": value}
        elif key == "size":
            body_template_dict[key] = "{{resolution}}"
            # 推断 resolution 映射
            if isinstance(value, str):
                if "720" in value or "1080" in value:
                    parameter_mapping["resolution"] = {
                        "720p": value,
                        "1080p": value.replace("720", "1080") if "720" in value else value
                    }
        elif key == "watermark":
            body_template_dict[key] = "{{watermark}}"
        elif key in ["character_url", "character_timestamps"]:
            # 可选字段，保留原值或设为空
            body_template_dict[key] = ""
        else:
            body_template_dict[key] = value
    
    request_template["body_template"] = json.dumps(body_template_dict, indent=2, ensure_ascii=False)
    
    # 构建响应解析器（基于常见API格式推断）
    response_parser = {
        "task_id_path": "task_id",
        "status_path": "status",
        "video_url_path": "videos.0.video_url",
        "error_path": "reason"
    }
    
    # 构建状态查询配置
    status_query = {
        "url": f"{base_url}/v3/async/task-result?task_id={{{{task_id}}}}",
        "method": "GET",
        "status_mapping": {
            "TASK_STATUS_PENDING": "submitted",
            "TASK_STATUS_PROCESSING": "processing",
            "TASK_STATUS_SUCCEED": "completed",
            "TASK_STATUS_FAILED": "failed"
        }
    }
    
    return {
        "request_template": request_template,
        "parameter_mapping": parameter_mapping,
        "response_parser": response_parser,
        "status_query": status_query
    }


@app.post("/api/providers/parse-curl")
async def parse_curl(request: ParseCurlRequest):
    """解析CURL命令，返回解析后的字段"""
    try:
        import re
        import json
        
        curl_text = request.curl_command.strip()
        result = {
            "base_url": "",
            "endpoint": "",
            "headers": {},
            "model": None,
            "api_key": None,
            "method": "GET",
            "custom_fields": None
        }
        
        # 解析URL (支持 --url 和直接跟在curl后面的URL)
        # 先尝试匹配 --url 格式
        url_match = re.search(r'--url\s+["\']?([^"\'\s]+)', curl_text, re.IGNORECASE)
        if not url_match:
            # 再尝试匹配 curl 后面直接跟URL的格式
            url_match = re.search(r'curl\s+["\']?([^"\'\s]+)', curl_text, re.IGNORECASE)
        
        if url_match:
            full_url = url_match.group(1)
            # 分离base_url和endpoint
            parsed = full_url.split('/', 3)
            if len(parsed) >= 3:
                result["base_url"] = f"{parsed[0]}//{parsed[2]}"
                if len(parsed) >= 4:
                    result["endpoint"] = "/" + parsed[3]
        
        # 解析方法 (支持 --request 和 -X)
        method_match = re.search(r'(?:-X|--request)\s+["\']?(\w+)["\']?', curl_text, re.IGNORECASE)
        if method_match:
            result["method"] = method_match.group(1).upper()
        
        # 解析 headers (支持 --header 和 -H)
        # 匹配 -H 'key: value' 或 --header 'key: value' 格式
        header_matches = re.findall(r'(?:-H|--header)\s+["\']([^"\']+)["\']', curl_text, re.IGNORECASE)
        for header in header_matches:
            if ':' in header:
                key, value = header.split(':', 1)
                key = key.strip()
                value = value.strip()
                result["headers"][key] = value
                
                # 提取API key
                if key.lower() in ["authorization", "x-api-key"]:
                    if value.lower().startswith("bearer "):
                        result["api_key"] = value[7:]
                    else:
                        result["api_key"] = value
        
        # 解析 data (支持 --data 和 -d，以及多行JSON)
        # 尝试匹配单行格式: -d '{...}' 或 --data '{...}'
        data_match = re.search(r'(?:-d|--data)\s+["\']([\s\S]*?)["\'](?:\s+-|$)', curl_text, re.IGNORECASE)
        
        # 如果没匹配到，尝试匹配多行格式（data后面跟着换行和JSON）
        if not data_match:
            data_match = re.search(r'(?:-d|--data)\s+["\']?\s*\n?\s*([\{\[][\s\S]*?[\}\]])', curl_text, re.IGNORECASE)
        
        if data_match:
            try:
                data_str = data_match.group(1).strip()
                # 尝试解析JSON
                data_json = json.loads(data_str)
                
                # 提取model（LLM提供商用）
                if "model" in data_json:
                    result["model"] = data_json["model"]
                
                # 生成通用提供商配置（视频提供商用）
                if result["method"] == "POST" and ("prompt" in data_json or "image" in data_json):
                    result["custom_fields"] = _generate_generic_provider_config(
                        result, data_json
                    )
            except Exception as e:
                # JSON解析失败，忽略
                pass
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"解析CURL命令失败: {str(e)}")


# ============ API提供商验证API ============

@app.post("/api/providers/{provider_id}/verify")
async def verify_provider(provider_id: str):
    """验证指定提供商的API有效性"""
    import time
    start_time = time.time()
    
    try:
        config = Config.load_global()
        
        # 查找提供商
        provider = None
        is_builtin = False
        
        # 检查是否为内置提供商
        if provider_id == "builtin_llm":
            provider = {
                "id": "builtin_llm",
                "name": f"内置LLM ({config.defaults.llm.provider})",
                "type": "llm",
                "base_url": config.defaults.llm.base_url,
                "api_key": settings.openai_api_key,  # 从lLM配置获取API Key
                "model": config.defaults.llm.model,
                "timeout": config.defaults.llm.timeout,
                "headers": {},
            }
            is_builtin = True
        elif provider_id == "builtin_image":
            provider = {
                "id": "builtin_image",
                "name": f"内置Image ({config.defaults.image.provider})",
                "type": "image",
                "base_url": config.defaults.image.base_url,
                "api_key": settings.jiekouai_api_key,  # 从settings获取
                "endpoint": config.defaults.image.endpoint,
                "timeout": config.defaults.image.timeout,
                "headers": {},
            }
            is_builtin = True
        elif provider_id == "builtin_video":
            provider = {
                "id": "builtin_video",
                "name": f"内置Video ({config.defaults.video.provider})",
                "type": "video",
                "base_url": config.defaults.video.base_url,
                "api_key": settings.jiekouai_api_key,  # 从settings获取
                "timeout": config.defaults.video.timeout,
                "headers": {},
            }
            is_builtin = True
        else:
            # 查找用户添加的提供商
            for provider_type, providers in config.providers.items():
                for p in providers:
                    if _get_provider_id(p) == provider_id:
                        provider = p
                        _set_provider_attr(provider, "_type", provider_type)
                        break
                if provider:
                    break
        
        if not provider:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        provider_type = _get_provider_attr(provider, "type") or _get_provider_attr(provider, "_type", "llm")
        base_url = _get_provider_attr(provider, "base_url", "")
        api_key = _get_provider_attr(provider, "api_key", "")
        model = _get_provider_attr(provider, "model")
        
        latency = int((time.time() - start_time) * 1000)
        
        # 根据类型进行验证
        if provider_type == "llm":
            # LLM验证：发送极短prompt，max_tokens=1
            try:
                import aiohttp
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                headers.update(_get_provider_attr(provider, "headers", {}))
                
                payload = {
                    "model": model or "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=10
                    ) as resp:
                        if resp.status in [200, 201]:
                            latency = int((time.time() - start_time) * 1000)
                            # 更新验证状态（仅对非内置提供商保存）
                            if not is_builtin:
                                _set_provider_attr(provider, "verified", True)
                                _set_provider_attr(provider, "verified_at", datetime.now().isoformat())
                                _set_provider_attr(provider, "latency", latency)
                                config.save_global_config(use_json=True)
                            return {"valid": True, "latency": latency}
                        else:
                            text = await resp.text()
                            return {"valid": False, "error": f"API返回错误: HTTP {resp.status}, {text}"}
            except Exception as e:
                return {"valid": False, "error": f"连接失败: {str(e)}"}
                
        elif provider_type == "image":
            # Image验证：尝试连接base_url，检查API key格式
            try:
                import aiohttp
                headers = {
                    "Authorization": f"Bearer {api_key}"
                }
                headers.update(provider.get("headers", {}))
                
                # 简单HEAD请求验证连通性
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.head(base_url, timeout=5) as resp:
                            pass
                    except:
                        pass  # HEAD可能不被支持，忽略错误
                    
                    # 检查API key是否配置
                    if not api_key:
                        return {"valid": False, "error": "API Key未配置"}
                    
                    latency = int((time.time() - start_time) * 1000)
                    # 仅对非内置提供商保存验证状态
                    if not is_builtin:
                        _set_provider_attr(provider, "verified", True)
                        _set_provider_attr(provider, "verified_at", datetime.now().isoformat())
                        _set_provider_attr(provider, "latency", latency)
                        config.save_global_config(use_json=True)
                    return {"valid": True, "latency": latency, "note": "基础连接验证通过"}
            except Exception as e:
                return {"valid": False, "error": f"验证失败: {str(e)}"}
                
        elif provider_type == "video":
            # Video验证：类似Image
            try:
                if not api_key:
                    return {"valid": False, "error": "API Key未配置"}
                
                latency = int((time.time() - start_time) * 1000)
                # 仅对非内置提供商保存验证状态
                if not is_builtin:
                    _set_provider_attr(provider, "verified", True)
                    _set_provider_attr(provider, "verified_at", datetime.now().isoformat())
                    _set_provider_attr(provider, "latency", latency)
                    config.save_global_config(use_json=True)
                return {"valid": True, "latency": latency, "note": "基础配置验证通过"}
            except Exception as e:
                return {"valid": False, "error": f"验证失败: {str(e)}"}
        else:
            return {"valid": False, "error": f"不支持的提供商类型: {provider_type}"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证提供商失败: {str(e)}")


# ============ 默认提供商API ============

@app.get("/api/providers/default/{provider_type}")
async def get_default_provider(provider_type: str):
    """获取指定类型的默认提供商"""
    try:
        config = Config.load_global()
        
        if provider_type not in ["llm", "image", "video"]:
            raise HTTPException(status_code=400, detail="无效的提供商类型")
        
        providers = config.providers.get(provider_type, [])
        
        # 查找默认提供商
        for provider in providers:
            if _get_provider_attr(provider, "is_default"):
                return provider
        
        # 如果没有默认提供商，返回第一个启用的提供商
        for provider in providers:
            if _get_provider_attr(provider, "enabled", True):
                return provider
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取默认提供商失败: {str(e)}")


@app.post("/api/providers/{provider_id}/set-default")
async def set_default_provider(provider_id: str):
    """设置默认提供商（支持内置提供商和用户自定义提供商）"""
    try:
        config = Config.load_global()
        
        # 处理内置提供商
        builtin_type_map = {
            "builtin_llm": "llm",
            "builtin_image": "image",
            "builtin_video": "video"
        }
        
        if provider_id in builtin_type_map:
            # 内置提供商：只需将该类型的所有用户自定义提供商设为非默认
            provider_type = builtin_type_map[provider_id]
            providers = config.providers.get(provider_type, [])
            for p in providers:
                _set_provider_attr(p, "is_default", False)
            
            config.save_global_config(use_json=True)
            return {"status": "success", "message": f"已恢复为系统默认{provider_type.upper()}提供商"}
        
        # 查找用户自定义提供商
        found = False
        provider_type = None
        
        for ptype, providers in config.providers.items():
            for provider in providers:
                if _get_provider_id(provider) == provider_id:
                    # 将同类型的其他提供商设置为非默认
                    for p in providers:
                        _set_provider_attr(p, "is_default", False)
                    # 设置当前提供商为默认
                    _set_provider_attr(provider, "is_default", True)
                    found = True
                    provider_type = ptype
                    break
            if found:
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        config.save_global_config(use_json=True)
        return {"status": "success", "message": f"已设置为默认{provider_type}提供商"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置默认提供商失败: {str(e)}")


# ============ 批量流水线API ============

class CreateBatchJobRequest(BaseModel):
    """创建批量作业请求"""
    shot_ids: List[str]
    name: Optional[str] = None
    duration: str = "4s"
    size: str = "720p"
    watermark: bool = False
    provider: Optional[str] = None
    auto_retry: bool = True
    sequential: bool = False  # False=并行, True=顺序
    max_parallel: int = 2


class BatchJobResponse(BaseModel):
    """批量作业响应"""
    job_id: str
    name: str
    project_id: str
    status: str
    total_tasks: int
    completed_count: int
    failed_count: int
    progress_percentage: float
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@app.post("/api/projects/{project_id}/batch-jobs", response_model=BatchJobResponse)
async def create_batch_job(project_id: str, request: CreateBatchJobRequest):
    """
    创建批量生成作业（无人值守）
    
    自动处理：首帧生成 → 等待完成 → 视频生成 → 下载
    """
    project = project_manager.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if not request.shot_ids:
        raise HTTPException(status_code=400, detail="shot_ids 不能为空")
    
    try:
        batch_service = get_batch_pipeline_service()
        job = await batch_service.create_batch_job(
            project_id=project_id,
            shot_ids=request.shot_ids,
            name=request.name,
            duration=request.duration,
            size=request.size,
            watermark=request.watermark,
            provider=request.provider,
            auto_retry=request.auto_retry,
            sequential=request.sequential,
            max_parallel=request.max_parallel
        )
        
        return BatchJobResponse(
            job_id=job.job_id,
            name=job.name,
            project_id=job.project_id,
            status=job.status,
            total_tasks=job.total_tasks,
            completed_count=job.completed_count,
            failed_count=job.failed_count,
            progress_percentage=job.progress_percentage,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建批量作业失败: {str(e)}")


@app.get("/api/projects/{project_id}/batch-jobs")
async def list_batch_jobs(project_id: str):
    """列出项目的所有批量作业"""
    batch_service = get_batch_pipeline_service()
    jobs = batch_service.list_jobs(project_id=project_id)
    
    return [
        {
            "job_id": job.job_id,
            "name": job.name,
            "status": job.status,
            "total_tasks": job.total_tasks,
            "completed_count": job.completed_count,
            "failed_count": job.failed_count,
            "progress_percentage": job.progress_percentage,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        }
        for job in jobs
    ]


@app.get("/api/projects/{project_id}/batch-jobs/{job_id}")
async def get_batch_job(project_id: str, job_id: str):
    """获取批量作业详情"""
    batch_service = get_batch_pipeline_service()
    job = batch_service.get_job(job_id)
    
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    return {
        "job_id": job.job_id,
        "name": job.name,
        "project_id": job.project_id,
        "status": job.status,
        "total_tasks": job.total_tasks,
        "completed_count": job.completed_count,
        "failed_count": job.failed_count,
        "progress_percentage": job.progress_percentage,
        "auto_retry": job.auto_retry,
        "sequential": job.sequential,
        "max_parallel": job.max_parallel,
        "tasks": [
            {
                "task_id": task.task_id,
                "shot_id": task.shot_id,
                "sequence": task.sequence,
                "status": task.status.value,
                "keyframe_attempts": task.keyframe_attempts,
                "video_attempts": task.video_attempts,
                "keyframe_error": task.keyframe_error,
                "video_error": task.video_error,
                "video_task_id": task.video_task_id,
                "duration": task.duration,
                "size": task.size,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "keyframe_completed_at": task.keyframe_completed_at.isoformat() if task.keyframe_completed_at else None,
                "video_completed_at": task.video_completed_at.isoformat() if task.video_completed_at else None
            }
            for task in job.tasks
        ],
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


@app.post("/api/projects/{project_id}/batch-jobs/{job_id}/pause")
async def pause_batch_job(project_id: str, job_id: str):
    """暂停批量作业"""
    batch_service = get_batch_pipeline_service()
    job = batch_service.get_job(job_id)
    
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    success = await batch_service.pause_job(job_id)
    if success:
        return {"status": "paused"}
    raise HTTPException(status_code=400, detail="无法暂停作业")


@app.post("/api/projects/{project_id}/batch-jobs/{job_id}/resume")
async def resume_batch_job(project_id: str, job_id: str):
    """恢复批量作业"""
    batch_service = get_batch_pipeline_service()
    job = batch_service.get_job(job_id)
    
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    success = await batch_service.resume_job(job_id)
    if success:
        return {"status": "resumed"}
    raise HTTPException(status_code=400, detail="无法恢复作业")


@app.post("/api/projects/{project_id}/batch-jobs/{job_id}/cancel")
async def cancel_batch_job(project_id: str, job_id: str):
    """取消批量作业"""
    batch_service = get_batch_pipeline_service()
    job = batch_service.get_job(job_id)
    
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    success = await batch_service.cancel_job(job_id)
    if success:
        return {"status": "cancelled"}
    raise HTTPException(status_code=400, detail="无法取消作业")


# ============ 主入口 ============

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=True,
        log_level="info"
    )
