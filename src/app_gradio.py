"""
Gradio前端界面 - 动画生成系统 (简化版)
兼容 Gradio 5.x
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import gradio as gr
from dataclasses import dataclass

# API基础URL
API_BASE = "http://localhost:8000"

# ============ 数据模型 ============

@dataclass
class AppState:
    """应用状态"""
    current_project_id: Optional[str] = None
    current_project_name: Optional[str] = None

app_state = AppState()

# ============ API 辅助函数 ============

def api_get(endpoint: str, timeout: int = 10) -> Dict:
    """GET请求"""
    try:
        response = requests.get(f"{API_BASE}{endpoint}", timeout=timeout)
        return {"success": response.status_code == 200, "data": response.json() if response.status_code == 200 else None, "error": response.text if response.status_code != 200 else None}
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_post(endpoint: str, json_data: Dict = None, timeout: int = 10) -> Dict:
    """POST请求"""
    try:
        response = requests.post(f"{API_BASE}{endpoint}", json=json_data, timeout=timeout)
        return {"success": response.status_code == 200, "data": response.json() if response.status_code == 200 else None, "error": response.text if response.status_code != 200 else None}
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_delete(endpoint: str, timeout: int = 10) -> Dict:
    """DELETE请求"""
    try:
        response = requests.delete(f"{API_BASE}{endpoint}", timeout=timeout)
        return {"success": response.status_code == 200, "data": response.json() if response.status_code == 200 else None, "error": response.text if response.status_code != 200 else None}
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_put(endpoint: str, json_data: Dict = None, timeout: int = 10) -> Dict:
    """PUT请求"""
    try:
        response = requests.put(f"{API_BASE}{endpoint}", json=json_data, timeout=timeout)
        return {"success": response.status_code == 200, "data": response.json() if response.status_code == 200 else None, "error": response.text if response.status_code != 200 else None}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============ 页面功能 ============

def format_project_list() -> str:
    """格式化项目列表为Markdown"""
    result = api_get("/api/projects")
    if not result["success"]:
        return f"**加载失败**: {result.get('error', '未知错误')}"
    
    projects = result["data"]
    if not projects:
        return "暂无项目"
    
    lines = ["| ID | 名称 | 状态 | 进度 |", "|---|---|---|---|"]
    for p in projects:
        pid = p.get("project_id", "")[:8]
        name = p.get("name", "")
        status = p.get("status", "")
        progress = p.get("progress_percentage", 0)
        lines.append(f"| {pid}... | {name} | {status} | {progress:.1f}% |")
    
    return "\n".join(lines)

def create_project(name: str, style: str, script: str) -> str:
    """创建新项目"""
    if not name or not script:
        return "❌ 项目名称和剧本内容不能为空"
    
    result = api_post("/api/projects", {
        "name": name,
        "script_content": script,
        "style_description": style
    })
    
    if result["success"]:
        return f"✅ 项目 '{name}' 创建成功！"
    else:
        return f"❌ 创建失败: {result.get('error', '未知错误')}"

def select_project(project_id: str) -> str:
    """选择项目"""
    global app_state
    if not project_id:
        return "请选择项目ID"
    
    result = api_get(f"/api/projects/{project_id}")
    if result["success"]:
        app_state.current_project_id = project_id
        app_state.current_project_name = result["data"].get("name")
        return f"✅ 已选择: {result['data'].get('name')}"
    else:
        return f"❌ 无法加载: {result.get('error', '未知错误')}"

def delete_project(project_id: str) -> str:
    """删除项目"""
    if not project_id:
        return "❌ 请输入项目ID"
    
    result = api_delete(f"/api/projects/{project_id}")
    if result["success"]:
        global app_state
        if app_state.current_project_id == project_id:
            app_state.current_project_id = None
            app_state.current_project_name = None
        return "✅ 项目已删除"
    else:
        return f"❌ 删除失败: {result.get('error', '未知错误')}"

def get_current_project_info() -> str:
    """获取当前项目信息"""
    if not app_state.current_project_id:
        return "⚠️ 请先选择项目"
    
    result = api_get(f"/api/projects/{app_state.current_project_id}")
    if not result["success"]:
        return f"❌ 无法加载: {result.get('error', '未知错误')}"
    
    p = result["data"]
    return f"""**项目**: {p.get('name', 'Unknown')}
**ID**: {p.get('project_id', '')[:12]}...
**状态**: {p.get('current_stage', 'unknown')}
**进度**: {p.get('progress_percentage', 0):.1f}%"""

def start_parsing() -> str:
    """开始解析剧本"""
    if not app_state.current_project_id:
        return "❌ 请先选择项目"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/parse")
    if result["success"]:
        return "✅ 解析任务已提交"
    else:
        return f"❌ 提交失败: {result.get('error', '未知错误')}"

def format_characters() -> str:
    """格式化角色列表"""
    if not app_state.current_project_id:
        return "请先选择项目"
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/characters")
    if not result["success"]:
        return f"加载失败: {result.get('error', '未知错误')}"
    
    chars = result["data"]
    if not chars:
        return "暂无角色数据"
    
    lines = []
    for c in chars:
        name = c.get("name", "未命名")
        desc = c.get("description", "")[:50]
        status = c.get("status", "unknown")
        lines.append(f"**{name}** ({status})\n{desc}...")
    return "\n\n".join(lines)

def format_scenes() -> str:
    """格式化场景列表"""
    if not app_state.current_project_id:
        return "请先选择项目"
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/scenes")
    if not result["success"]:
        return f"加载失败: {result.get('error', '未知错误')}"
    
    scenes = result["data"]
    if not scenes:
        return "暂无场景数据"
    
    lines = []
    for s in scenes:
        name = s.get("name", "未命名")
        location = s.get("location", "")
        desc = s.get("description", "")[:50]
        lines.append(f"**{name}** ({location})\n{desc}...")
    return "\n\n".join(lines)

def generate_references() -> str:
    """生成参考图"""
    if not app_state.current_project_id:
        return "❌ 请先选择项目"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/generate-references")
    if result["success"]:
        return "✅ 参考图生成任务已提交"
    else:
        return f"❌ 提交失败: {result.get('error', '未知错误')}"

def load_character_images():
    """加载角色图片"""
    if not app_state.current_project_id:
        return []
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/characters")
    if not result["success"]:
        return []
    
    chars = result["data"]
    images = []
    for c in chars:
        versions = c.get("versions", [])
        if versions:
            current = versions[c.get("current_version", 1) - 1]
            path = current.get("path")
            if path and Path(path).exists():
                caption = f"{c.get('name', 'Unknown')} - {current.get('status', 'unknown')}"
                images.append((path, caption))
    return images

def load_scene_images():
    """加载场景图片"""
    if not app_state.current_project_id:
        return []
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/scenes")
    if not result["success"]:
        return []
    
    scenes = result["data"]
    images = []
    for s in scenes:
        versions = s.get("versions", [])
        if versions:
            current = versions[s.get("current_version", 1) - 1]
            path = current.get("path")
            if path and Path(path).exists():
                caption = f"{s.get('name', 'Unknown')} - {current.get('status', 'unknown')}"
                images.append((path, caption))
    return images

def approve_character(char_id: str) -> str:
    """通过角色"""
    if not app_state.current_project_id or not char_id:
        return "❌ 参数错误"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/characters/{char_id}/approve", {"approved": True})
    if result["success"]:
        return f"✅ 角色 {char_id} 已通过"
    else:
        return f"❌ 操作失败: {result.get('error', '未知错误')}"

def reject_character(char_id: str) -> str:
    """拒绝角色"""
    if not app_state.current_project_id or not char_id:
        return "❌ 参数错误"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/characters/{char_id}/approve", {"approved": False, "reason": "需要重新生成"})
    if result["success"]:
        return f"✅ 角色 {char_id} 已拒绝"
    else:
        return f"❌ 操作失败: {result.get('error', '未知错误')}"

def design_shots() -> str:
    """生成分镜"""
    if not app_state.current_project_id:
        return "❌ 请先选择项目"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/design-shots", {})
    if result["success"]:
        return "✅ 分镜设计任务已提交"
    else:
        return f"❌ 提交失败: {result.get('error', '未知错误')}"

def format_shots() -> str:
    """格式化分镜列表"""
    if not app_state.current_project_id:
        return "请先选择项目"
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/shots")
    if not result["success"]:
        return f"加载失败: {result.get('error', '未知错误')}"
    
    shots = result["data"]
    if not shots:
        return "暂无分镜数据"
    
    lines = []
    for s in shots:
        sid = s.get("shot_id", "")
        seq = s.get("sequence", "")
        shot_type = s.get("type", "")
        duration = s.get("duration", "")
        desc = s.get("description", "")[:40]
        status = s.get("status", "")
        lines.append(f"**#{seq}** {sid} ({shot_type}, {duration}) - {status}\n{desc}...")
    return "\n\n".join(lines)

def generate_keyframes() -> str:
    """生成首帧"""
    if not app_state.current_project_id:
        return "❌ 请先选择项目"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/generate-keyframes")
    if result["success"]:
        return "✅ 首帧生成任务已提交"
    else:
        return f"❌ 提交失败: {result.get('error', '未知错误')}"

def load_keyframe_images():
    """加载首帧图片"""
    if not app_state.current_project_id:
        return []
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/shots")
    if not result["success"]:
        return []
    
    shots = result["data"]
    images = []
    for s in shots:
        batches = s.get("batches", {})
        current_batch_id = s.get("current_batch_id")
        if current_batch_id and current_batch_id in batches:
            keyframe = batches[current_batch_id].get("keyframe")
            if keyframe and keyframe.get("path") and Path(keyframe["path"]).exists():
                caption = f"{s.get('shot_id', 'Unknown')} - {keyframe.get('status', 'unknown')}"
                images.append((keyframe["path"], caption))
    return images

def get_cost_estimate() -> str:
    """成本预估"""
    if not app_state.current_project_id:
        return "请先选择项目"
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/cost-estimate")
    if result["success"]:
        data = result["data"]
        return f"分镜: {data.get('shot_count', 0)} | 时长: {data.get('total_seconds', 0)}s | 预估: ${data.get('estimated_cost_usd', 0):.2f}"
    else:
        return f"获取失败: {result.get('error', '未知错误')}"

def generate_videos(duration: str, size: str, watermark: bool, shot_range: str) -> str:
    """批量生成视频"""
    if not app_state.current_project_id:
        return "❌ 请先选择项目"
    
    shot_ids = None
    if shot_range.strip():
        shot_ids = [s.strip() for s in shot_range.split(",") if s.strip()]
    
    result = api_post(
        f"/api/projects/{app_state.current_project_id}/generate-videos",
        {"duration": duration, "size": size, "watermark": watermark, "shot_ids": shot_ids}
    )
    
    if result["success"]:
        data = result["data"]
        return f"✅ 已提交 {data.get('submitted_count', 0)} 个视频任务"
    else:
        return f"❌ 提交失败: {result.get('error', '未知错误')}"

def format_videos() -> str:
    """格式化视频列表"""
    if not app_state.current_project_id:
        return "请先选择项目"
    
    result = api_get(f"/api/projects/{app_state.current_project_id}/videos")
    if not result["success"]:
        return f"加载失败: {result.get('error', '未知错误')}"
    
    videos = result["data"]
    if not videos:
        return "暂无视频数据"
    
    lines = []
    for v in videos:
        sid = v.get("shot_id", "")
        status = v.get("status", "")
        duration = v.get("duration", "")
        size = v.get("size", "")
        lines.append(f"**{sid}**: {status} ({duration}, {size})")
    return "\n".join(lines)

def check_video_status(shot_id: str) -> str:
    """检查视频状态"""
    if not app_state.current_project_id or not shot_id:
        return "❌ 参数错误"
    
    result = api_post(f"/api/projects/{app_state.current_project_id}/videos/{shot_id}/check-status", {})
    if result["success"]:
        videos = result["data"].get("videos", [])
        if videos:
            v = videos[0]
            return f"状态: {v.get('status')} | 进度: {v.get('progress', 0)}% | 本地: {v.get('local_path', '未下载')}"
        return "暂无视频数据"
    else:
        return f"❌ 查询失败: {result.get('error', '未知错误')}"

def get_queue_status() -> str:
    """获取队列状态"""
    result = api_get("/api/queues/status")
    if not result["success"]:
        return f"无法获取: {result.get('error', '未知错误')}"
    
    queues = result["data"]
    lines = []
    for name, stats in queues.items():
        lines.append(f"**{name.upper()}**: ⏳{stats.get('pending', 0)} ▶️{stats.get('running', 0)} ✅{stats.get('completed', 0)} ❌{stats.get('failed', 0)}")
    return "\n".join(lines)

# ============ Gradio UI ============

def create_ui():
    with gr.Blocks(title="动画生成系统") as demo:
        gr.Markdown("# 🎬 动画生成系统")
        gr.Markdown("从剧本到动画的自动化生成工具")
        
        # ===== 项目管理 =====
        with gr.Tab("📁 项目管理"):
            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("### 项目列表")
                    project_list = gr.Markdown(value=format_project_list)
                    refresh_projects = gr.Button("刷新列表")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 操作")
                    project_id = gr.Textbox(label="项目ID", placeholder="输入项目ID")
                    select_btn = gr.Button("选择", variant="primary")
                    delete_btn = gr.Button("删除", variant="stop")
                    status = gr.Textbox(label="状态", interactive=False)
                    
                    gr.Markdown("### 创建项目")
                    new_name = gr.Textbox(label="名称", placeholder="我的动画")
                    new_style = gr.Textbox(label="风格", placeholder="日系动漫风格")
                    new_script = gr.TextArea(label="剧本", placeholder="# 第一幕...", lines=6)
                    create_btn = gr.Button("➕ 创建", variant="primary")
            
            refresh_projects.click(fn=format_project_list, outputs=project_list)
            select_btn.click(fn=select_project, inputs=project_id, outputs=status)
            delete_btn.click(fn=delete_project, inputs=project_id, outputs=status)
            create_btn.click(fn=create_project, inputs=[new_name, new_style, new_script], outputs=status)
        
        # ===== 剧本解析 =====
        with gr.Tab("📝 剧本解析"):
            with gr.Row():
                with gr.Column():
                    project_info = gr.Markdown(value=get_current_project_info)
                    parse_btn = gr.Button("🚀 开始解析", variant="primary")
                    parse_result = gr.Textbox(label="结果", interactive=False)
                
                with gr.Column():
                    with gr.Tabs():
                        with gr.Tab("角色"):
                            char_list = gr.Markdown(value=format_characters)
                        with gr.Tab("场景"):
                            scene_list = gr.Markdown(value=format_scenes)
            
            parse_btn.click(fn=start_parsing, outputs=parse_result)
        
        # ===== 参考图 =====
        with gr.Tab("🎨 参考图"):
            with gr.Row():
                gen_ref_btn = gr.Button("🎨 生成参考图", variant="primary")
                gen_ref_result = gr.Textbox(label="结果", interactive=False)
            
            with gr.Row():
                char_id_input = gr.Textbox(label="角色ID", placeholder="输入ID进行审核")
                approve_btn = gr.Button("✅ 通过", variant="primary")
                reject_btn = gr.Button("❌ 拒绝", variant="stop")
            approve_result = gr.Textbox(label="审核结果", interactive=False)
            
            with gr.Tabs():
                with gr.Tab("角色参考图"):
                    char_gallery = gr.Gallery(label="角色", value=load_character_images, columns=3)
                with gr.Tab("场景参考图"):
                    scene_gallery = gr.Gallery(label="场景", value=load_scene_images, columns=3)
            
            gen_ref_btn.click(fn=generate_references, outputs=gen_ref_result)
            approve_btn.click(fn=approve_character, inputs=char_id_input, outputs=approve_result)
            reject_btn.click(fn=reject_character, inputs=char_id_input, outputs=approve_result)
        
        # ===== 分镜设计 =====
        with gr.Tab("🎬 分镜设计"):
            with gr.Row():
                design_btn = gr.Button("🎬 自动生成分镜", variant="primary")
                design_result = gr.Textbox(label="结果", interactive=False)
            shot_list = gr.Markdown(label="分镜列表", value=format_shots)
            design_btn.click(fn=design_shots, outputs=design_result)
        
        # ===== 首帧生成 =====
        with gr.Tab("🖼️ 首帧生成"):
            with gr.Row():
                gen_kf_btn = gr.Button("🖼️ 生成首帧", variant="primary")
                cost_btn = gr.Button("💰 成本预估")
                gen_kf_result = gr.Textbox(label="结果", interactive=False)
                cost_result = gr.Textbox(label="预估", interactive=False)
            keyframe_gallery = gr.Gallery(label="首帧", value=load_keyframe_images, columns=2)
            gen_kf_btn.click(fn=generate_keyframes, outputs=gen_kf_result)
            cost_btn.click(fn=get_cost_estimate, outputs=cost_result)
        
        # ===== 视频生成 =====
        with gr.Tab("🎥 视频生成"):
            with gr.Tabs():
                with gr.Tab("生成"):
                    with gr.Row():
                        with gr.Column():
                            duration = gr.Dropdown(["4s", "5s", "6s", "8s", "10s"], value="5s", label="时长")
                            size = gr.Dropdown(["480x480", "512x512", "720x480", "1280x720"], value="512x512", label="尺寸")
                            watermark = gr.Checkbox(label="水印", value=False)
                        with gr.Column():
                            shot_range = gr.Textbox(label="分镜范围", placeholder="留空=全部")
                            gen_video_btn = gr.Button("🎥 生成视频", variant="primary")
                            gen_video_result = gr.Textbox(label="结果", interactive=False)
                    video_list = gr.Markdown(label="视频列表", value=format_videos)
                    gen_video_btn.click(fn=generate_videos, inputs=[duration, size, watermark, shot_range], outputs=gen_video_result)
                
                with gr.Tab("检查状态"):
                    check_shot_id = gr.Textbox(label="分镜ID")
                    check_btn = gr.Button("🔍 检查", variant="primary")
                    check_result = gr.Textbox(label="状态", interactive=False, lines=3)
                    check_btn.click(fn=check_video_status, inputs=check_shot_id, outputs=check_result)
        
        # ===== 队列状态 =====
        with gr.Tab("📊 队列"):
            queue_md = gr.Markdown(value=get_queue_status)
            refresh_queue = gr.Button("刷新")
            refresh_queue.click(fn=get_queue_status, outputs=queue_md)
        
        gr.Markdown("---")
        gr.Markdown("v2.0 Gradio | 动画生成系统")
    
    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_api=False,
        show_error=True
    )
