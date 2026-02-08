"""
Streamlit前端界面
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径（兼容不同启动方式）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import json
import time
from datetime import datetime

from src.core.config import Config
from src.core.project_manager import ProjectManager

# API基础URL
API_BASE = "http://localhost:8000"

# 初始化session state
if 'current_project' not in st.session_state:
    st.session_state.current_project = None

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "list"

# 页面配置
st.set_page_config(
    page_title="动画生成系统",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .main {
        padding: 0rem 1rem;
    }
    .stButton>button {
        width: 100%;
    }
    .project-card {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
        margin-bottom: 1rem;
    }
    .status-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: bold;
    }
    .status-draft { background-color: #f0f0f0; }
    .status-in_progress { background-color: #fff3cd; }
    .status-completed { background-color: #d4edda; }
    .status-error { background-color: #f8d7da; }
</style>
""", unsafe_allow_html=True)


def get_status_color(status):
    """获取状态颜色"""
    colors = {
        "draft": "⚪",
        "in_progress": "🟡",
        "completed": "🟢",
        "error": "🔴"
    }
    return colors.get(status, "⚪")


# ============ 侧边栏 ============

with st.sidebar:
    st.title("🎬 动画生成系统")
    st.markdown("---")
    
    # 导航
    page = st.radio(
        "导航",
        ["📁 项目管理", "📝 剧本解析", "🎨 参考图", "🎬 分镜设计", "🖼️ 首帧生成", "🎥 视频生成"],
        index=0
    )
    
    st.markdown("---")
    
    # 队列状态
    st.subheader("📊 队列状态")
    try:
        response = requests.get(f"{API_BASE}/api/queues/status", timeout=2)
        if response.status_code == 200:
            queues = response.json()
            for queue_name, stats in queues.items():
                with st.expander(f"{queue_name.upper()} 队列", expanded=False):
                    st.write(f"⏳ 待处理: {stats['pending']}")
                    st.write(f"▶️ 运行中: {stats['running']}")
                    st.write(f"✅ 已完成: {stats['completed']}")
                    st.write(f"❌ 失败: {stats['failed']}")
    except:
        st.warning("API未连接")
    
    st.markdown("---")
    st.caption("v1.0.0 MVP")


# ============ 项目管理页面 ============

def project_list_page():
    """项目列表页面"""
    st.header("📁 项目管理")
    
    # 创建新项目按钮
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ 创建新项目", type="primary"):
            st.session_state.show_create_dialog = True
    
    # 创建项目对话框
    if st.session_state.get('show_create_dialog'):
        with st.form("create_project_form"):
            st.subheader("创建新项目")
            name = st.text_input("项目名称", placeholder="我的动画项目")
            style = st.text_area(
                "风格描述",
                placeholder="高精度日系作画风格，参考新海诚动画电影",
                help="描述你想要的视觉风格"
            )
            script = st.text_area(
                "剧本内容 (Markdown)",
                height=200,
                placeholder="# 第一幕\\n\\n## 场景1：教室..."
            )
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("创建", type="primary")
            with col2:
                cancel = st.form_submit_button("取消")
            
            if submit and name and script and style:
                try:
                    response = requests.post(
                        f"{API_BASE}/api/projects",
                        json={
                            "name": name,
                            "script_content": script,
                            "style_description": style
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        st.success("项目创建成功！")
                        st.session_state.show_create_dialog = False
                        st.rerun()
                    else:
                        st.error(f"创建失败: {response.text}")
                except Exception as e:
                    st.error(f"错误: {e}")
            
            if cancel:
                st.session_state.show_create_dialog = False
                st.rerun()
    
    st.markdown("---")
    
    # 项目列表
    st.subheader("📋 项目列表")
    
    try:
        response = requests.get(f"{API_BASE}/api/projects", timeout=5)
        if response.status_code == 200:
            projects = response.json()
            
            if not projects:
                st.info("暂无项目，请创建新项目")
            else:
                for project in projects:
                    with st.container():
                        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                        
                        with col1:
                            st.markdown(f"**{project['name']}**")
                            st.caption(f"ID: {project['project_id']}")
                            st.caption(f"创建: {project['created_at'][:10]}")
                        
                        with col2:
                            status = project.get('status', 'draft')
                            st.markdown(f"{get_status_color(status)} {status}")
                            progress = project.get('progress_percentage', 0)
                            st.progress(progress / 100, text=f"{progress:.1f}%")
                        
                        with col3:
                            st.caption(f"角色: {project['statistics']['total_characters']}")
                            st.caption(f"场景: {project['statistics']['total_scenes']}")
                            st.caption(f"分镜: {project['statistics']['total_shots']}")
                        
                        with col4:
                            if st.button("打开", key=f"open_{project['project_id']}"):
                                st.session_state.current_project = project
                                st.rerun()
                            
                            # 删除确认对话框
                            delete_key = f"confirm_delete_{project['project_id']}"
                            if delete_key not in st.session_state:
                                st.session_state[delete_key] = False
                            
                            if st.button("删除", key=f"delete_{project['project_id']}", type="secondary"):
                                st.session_state[delete_key] = True
                                st.rerun()
                            
                            if st.session_state.get(delete_key):
                                st.warning(f"确定要删除项目 **{project['name']}** 吗？")
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("✅ 确认删除", key=f"confirm_del_{project['project_id']}"):
                                        requests.delete(f"{API_BASE}/api/projects/{project['project_id']}")
                                        st.session_state[delete_key] = False
                                        st.rerun()
                                with col2:
                                    if st.button("❌ 取消", key=f"cancel_del_{project['project_id']}"):
                                        st.session_state[delete_key] = False
                                        st.rerun()
                        
                        st.markdown("---")
        else:
            st.error("获取项目列表失败")
    except Exception as e:
        st.error(f"无法连接到API: {e}")
        st.info("请确保后端服务已启动: `python src/main.py`")


# ============ 剧本解析页面 ============

def script_parse_page():
    """剧本解析页面"""
    st.header("📝 剧本解析")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return
    
    project = st.session_state.current_project
    st.markdown(f"**当前项目**: {project['name']}")
    st.markdown(f"**风格**: {project['style_description']}")
    
    st.markdown("---")
    
    # 提示词编辑（新增）
    with st.expander("⚙️ 编辑解析提示词", expanded=False):
        st.info("修改提示词可以影响角色和场景的提取质量")
        
        # 加载当前提示词
        config = Config.load_global()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**角色提取提示词**")
            char_prompt = st.text_area(
                "character_extraction",
                value=config.prompts.get("character_extraction", ""),
                height=200,
                label_visibility="collapsed"
            )
        
        with col2:
            st.write("**场景提取提示词**")
            scene_prompt = st.text_area(
                "scene_extraction",
                value=config.prompts.get("scene_extraction", ""),
                height=200,
                label_visibility="collapsed"
            )
        
        if st.button("💾 保存提示词"):
            config.prompts["character_extraction"] = char_prompt
            config.prompts["scene_extraction"] = scene_prompt
            config.save_global()
            st.success("提示词已保存！")
    
    # 显示剧本内容
    with st.expander("📄 查看剧本", expanded=False):
        try:
            with open(project['script_path'], 'r', encoding='utf-8') as f:
                script_content = f.read()
            st.markdown(script_content)
        except:
            st.error("无法读取剧本文件")
    
    # 解析状态 - 自动刷新
    st.subheader("🔍 解析状态")
    
    # 如果正在处理中，启用自动刷新并重新获取数据
    auto_refresh_stages = ['extracting', 'generating_refs', 'designing_shots', 'generating_keyframes']
    if project['current_stage'] in auto_refresh_stages:
        st.info(f"⏳ 正在处理中... ({project['current_stage']}) 页面将自动刷新")
        # 使用JavaScript自动刷新（更可靠）
        st.markdown("""
        <script>
        setTimeout(function() {
            window.location.reload();
        }, 3000);
        </script>
        """, unsafe_allow_html=True)
        # 同时尝试重新获取项目数据
        try:
            refresh_response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}",
                timeout=5
            )
            if refresh_response.status_code == 200:
                st.session_state.current_project = refresh_response.json()
                project = st.session_state.current_project
        except:
            pass
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("角色数", project['statistics']['total_characters'])
    with col2:
        st.metric("场景数", project['statistics']['total_scenes'])
    with col3:
        st.metric("分镜数", project['statistics']['total_shots'])
    
    # 显示解析结果（如果有）
    if project['statistics']['total_characters'] > 0 or project['statistics']['total_scenes'] > 0:
        st.markdown("---")
        st.subheader("📊 解析结果")
        
        # 获取并显示角色
        try:
            response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}/characters",
                timeout=5
            )
            if response.status_code == 200:
                characters = response.json()
                if characters:
                    st.write("**👥 角色列表:**")
                    for char in characters:
                        with st.expander(f"🎭 {char.get('name', '未命名')}", expanded=False):
                            st.write(f"**外貌描述:** {char.get('description', '无') or '未提取'}")
                            st.write(f"**性格特征:** {char.get('personality', '无') or '未提取'}")
                            st.write(f"**状态:** {char.get('status', 'unknown')}")
        except Exception as e:
            st.error(f"获取角色失败: {e}")
        
        # 获取并显示场景
        try:
            response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}/scenes",
                timeout=5
            )
            if response.status_code == 200:
                scenes = response.json()
                if scenes:
                    st.write("**🎬 场景列表:**")
                    for scene in scenes:
                        with st.expander(f"🌍 {scene.get('name', '未命名')}", expanded=False):
                            st.write(f"**描述:** {scene.get('description', '无') or '未提取'}")
                            st.write(f"**地点:** {scene.get('location', '未指定')}")
                            st.write(f"**时间:** {scene.get('time', '未指定')}")
        except Exception as e:
            st.error(f"获取场景失败: {e}")
    
    # 操作按钮
    st.markdown("---")
    
    if project['current_stage'] == 'draft':
        if st.button("🚀 开始解析剧本", type="primary"):
            try:
                response = requests.post(
                    f"{API_BASE}/api/projects/{project['project_id']}/parse",
                    timeout=5
                )
                if response.status_code == 200:
                    st.success("解析任务已提交，请在队列中查看进度")
                    st.rerun()
                else:
                    st.error(f"提交失败: {response.text}")
            except Exception as e:
                st.error(f"错误: {e}")
    elif project['current_stage'] == 'extracting':
        st.info("⏳ 正在解析中...")
        if st.button("🔄 刷新状态"):
            st.rerun()
    elif project['current_stage'] == 'pending_review_extraction':
        st.success("✅ 解析完成，请审核结果")
        
        # 显示角色和场景
        st.subheader("👥 角色列表")
        try:
            response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}/characters",
                timeout=5
            )
            if response.status_code == 200:
                characters = response.json()
                
                if not characters:
                    st.warning("暂无角色数据，可能是解析失败或数据未保存")
                else:
                    for char in characters:
                        with st.expander(f"{char['name']}", expanded=False):
                            st.write(f"**描述**: {char['description']}")
                            st.write(f"**性格**: {char['personality']}")
            else:
                st.error(f"获取角色失败: {response.status_code}")
        except Exception as e:
            st.error(f"获取角色出错: {e}")
        
        # 显示场景
        st.subheader("🎬 场景列表")
        try:
            response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}/scenes",
                timeout=5
            )
            if response.status_code == 200:
                scenes = response.json()
                
                if not scenes:
                    st.warning("暂无场景数据")
                else:
                    for scene in scenes:
                        with st.expander(f"{scene['name']}", expanded=False):
                            st.write(f"**描述**: {scene['description']}")
                            st.write(f"**地点**: {scene['location']}")
                            st.write(f"**时间**: {scene['time']}")
        except Exception as e:
            st.error(f"获取场景出错: {e}")


# ============ 参考图页面 ============

def reference_images_page():
    """参考图页面（画廊视图）"""
    st.header("🎨 参考图生成")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return
    
    project = st.session_state.current_project
    st.markdown(f"**当前项目**: {project['name']}")
    
    # 如果正在生成参考图，启用自动刷新
    if project['current_stage'] == 'generating_refs':
        st.info("⏳ 正在生成参考图... 页面将自动刷新")
        st.markdown("""
        <script>
        setTimeout(function() {
            window.location.reload();
        }, 3000);
        </script>
        """, unsafe_allow_html=True)
        # 尝试重新获取项目数据
        try:
            refresh_response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}",
                timeout=5
            )
            if refresh_response.status_code == 200:
                st.session_state.current_project = refresh_response.json()
                project = st.session_state.current_project
        except:
            pass
    
    st.markdown("---")
    
    # 提示词编辑（新增）
    with st.expander("⚙️ 编辑参考图提示词", expanded=False):
        st.info("修改提示词可以影响角色和场景参考图的生成质量")
        
        # 加载当前提示词
        config = Config.load_global()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**角色提示词模板**")
            char_ref_prompt = st.text_area(
                "character_ref_prompt",
                value=config.prompts.get("character_ref_prompt", ""),
                height=200,
                label_visibility="collapsed"
            )
        
        with col2:
            st.write("**场景提示词模板**")
            scene_ref_prompt = st.text_area(
                "scene_ref_prompt",
                value=config.prompts.get("scene_ref_prompt", ""),
                height=200,
                label_visibility="collapsed"
            )
        
        if st.button("💾 保存参考图提示词"):
            config.prompts["character_ref_prompt"] = char_ref_prompt
            config.prompts["scene_ref_prompt"] = scene_ref_prompt
            config.save_global()
            st.success("参考图提示词已保存！")
    
    st.markdown("---")
    
    # 生成按钮
    if project['current_stage'] in ['pending_review_extraction', 'generating_refs']:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🎨 生成所有参考图", type="primary"):
                try:
                    response = requests.post(
                        f"{API_BASE}/api/projects/{project['project_id']}/generate-references",
                        timeout=5
                    )
                    if response.status_code == 200:
                        st.success("参考图生成任务已提交")
                        st.rerun()
                except Exception as e:
                    st.error(f"错误: {e}")
    
    # 画廊视图
    st.subheader("📷 角色参考图")
    
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project['project_id']}/characters",
            timeout=5
        )
        if response.status_code == 200:
            characters = response.json()
            
            # 网格布局
            cols = st.columns(3)
            for i, char in enumerate(characters):
                with cols[i % 3]:
                    st.markdown(f"**{char['name']}**")
                    
                    # 显示最新版本
                    if char.get('versions'):
                        current = char['versions'][char.get('current_version', 1) - 1]
                        
                        if current.get('path'):
                            try:
                                st.image(current['path'], width='stretch')
                            except:
                                st.info("图片加载中...")
                        
                        st.caption(f"状态: {current['status']}")
                        
                        # 操作按钮
                        if current['status'] == 'pending_review':
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ 通过", key=f"approve_char_{char['character_id']}"):
                                    requests.post(
                                        f"{API_BASE}/api/projects/{project['project_id']}/characters/{char['character_id']}/approve",
                                        json={"approved": True}
                                    )
                                    st.rerun()
                            with col2:
                                if st.button("❌ 拒绝", key=f"reject_char_{char['character_id']}"):
                                    requests.post(
                                        f"{API_BASE}/api/projects/{project['project_id']}/characters/{char['character_id']}/approve",
                                        json={"approved": False, "reason": "需要重新生成"}
                                    )
                                    st.rerun()
                        
                        # 重新生成
                        with st.expander("🔄 重新生成"):
                            method = st.radio("方式", ["改Seed", "改提示词", "两者都改"], key=f"regen_method_{char['character_id']}")
                            new_seed = st.number_input("新Seed", value=0, key=f"seed_{char['character_id']}")
                            
                            if st.button("重新生成", key=f"regen_{char['character_id']}"):
                                requests.post(
                                    f"{API_BASE}/api/projects/{project['project_id']}/characters/{char['character_id']}/regenerate",
                                    json={
                                        "method": method,
                                        "new_seed": new_seed if method in ["改Seed", "两者都改"] else None
                                    }
                                )
                                st.success("重新生成任务已提交")
                    else:
                        st.info("待生成")
    except Exception as e:
        st.error(f"加载角色失败: {e}")
    
    # 场景参考图
    st.markdown("---")
    st.subheader("📷 场景参考图")
    
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project['project_id']}/scenes",
            timeout=5
        )
        if response.status_code == 200:
            scenes = response.json()
            
            # 网格布局
            cols = st.columns(3)
            for i, scene in enumerate(scenes):
                with cols[i % 3]:
                    st.markdown(f"**{scene['name']}**")
                    st.caption(f"地点: {scene.get('location', '未指定')}")
                    
                    # 显示最新版本
                    if scene.get('versions'):
                        current = scene['versions'][scene.get('current_version', 1) - 1]
                        
                        if current.get('path'):
                            try:
                                st.image(current['path'], width='stretch')
                            except:
                                st.info("图片加载中...")
                        
                        st.caption(f"状态: {current['status']}")
                        
                        # 操作按钮
                        if current['status'] == 'pending_review':
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ 通过", key=f"approve_scene_{scene['scene_id']}"):
                                    requests.post(
                                        f"{API_BASE}/api/projects/{project['project_id']}/scenes/{scene['scene_id']}/approve",
                                        json={"approved": True}
                                    )
                                    st.rerun()
                            with col2:
                                if st.button("❌ 拒绝", key=f"reject_scene_{scene['scene_id']}"):
                                    requests.post(
                                        f"{API_BASE}/api/projects/{project['project_id']}/scenes/{scene['scene_id']}/approve",
                                        json={"approved": False, "reason": "需要重新生成"}
                                    )
                                    st.rerun()
                    else:
                        st.info("待生成")
    except Exception as e:
        st.error(f"加载场景失败: {e}")


# ============ 其他页面占位符 ============

def shots_page():
    """分镜设计页面"""
    st.header("🎬 分镜设计")
    st.info("此功能正在开发中...")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return


def keyframes_page():
    """首帧生成页面"""
    st.header("🖼️ 首帧生成")
    st.info("此功能正在开发中...")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return


def videos_page():
    """视频生成页面"""
    st.header("🎥 视频生成")
    st.info("此功能正在开发中...")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return


# ============ 主路由 ============

if page == "📁 项目管理":
    project_list_page()
elif page == "📝 剧本解析":
    script_parse_page()
elif page == "🎨 参考图":
    reference_images_page()
elif page == "🎬 分镜设计":
    shots_page()
elif page == "🖼️ 首帧生成":
    keyframes_page()
elif page == "🎥 视频生成":
    videos_page()


# ============ 分镜设计页面 ============

def shots_page():
    """分镜设计页面（时间线视图）"""
    st.header("🎬 分镜设计")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return
    
    project = st.session_state.current_project
    st.markdown(f"**当前项目**: {project['name']}")
    
    st.markdown("---")
    
    # 生成分镜按钮
    if project['current_stage'] in ['pending_review_refs', 'designing_shots']:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🎬 自动生成分镜", type="primary"):
                try:
                    response = requests.post(
                        f"{API_BASE}/api/projects/{project['project_id']}/design-shots",
                        json={},
                        timeout=5
                    )
                    if response.status_code == 200:
                        st.success("分镜设计任务已提交")
                        st.rerun()
                except Exception as e:
                    st.error(f"错误: {e}")
    
    # 加载分镜数据
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project['project_id']}/shots",
            timeout=5
        )
        if response.status_code == 200:
            shots = response.json()
            
            if not shots:
                st.info("暂无分镜，请点击'自动生成分镜'")
            else:
                st.subheader(f"📋 分镜列表 (共 {len(shots)} 个)")
                
                # 按场景分组
                shots_by_scene = {}
                for shot in shots:
                    scene_id = shot['scene_id']
                    if scene_id not in shots_by_scene:
                        shots_by_scene[scene_id] = []
                    shots_by_scene[scene_id].append(shot)
                
                # 显示每个场景的分镜
                for scene_id, scene_shots in shots_by_scene.items():
                    with st.expander(f"🎬 {scene_id} ({len(scene_shots)} 个分镜)", expanded=True):
                        
                        # 时间线样式显示
                        for i, shot in enumerate(scene_shots):
                            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
                            
                            with col1:
                                st.markdown(f"**#{shot['sequence']}**")
                                st.caption(f"{shot['duration']}")
                            
                            with col2:
                                st.markdown(f"_{shot['description']}_")
                                if shot.get('action'):
                                    st.caption(f"动作: {shot['action']}")
                            
                            with col3:
                                st.caption(f"镜头: {shot['type']}")
                                st.caption(f"运动: {shot['camera_movement']}")
                            
                            with col4:
                                # 编辑按钮
                                if st.button("✏️ 编辑", key=f"edit_{shot['shot_id']}"):
                                    st.session_state.editing_shot = shot
                                    st.session_state.show_shot_editor = True
                                
                                # 占位符上传
                                if st.button("🎨 占位符", key=f"placeholder_{shot['shot_id']}"):
                                    st.session_state.placeholder_shot = shot
                                    st.session_state.show_placeholder_uploader = True
                            
                            st.markdown("---")
    except Exception as e:
        st.error(f"加载分镜失败: {e}")
    
    # 分镜编辑器弹窗
    if st.session_state.get('show_shot_editor') and st.session_state.get('editing_shot'):
        shot = st.session_state.editing_shot
        with st.form("shot_editor"):
            st.subheader(f"编辑分镜: {shot['shot_id']}")
            
            description = st.text_area("描述", shot.get('description', ''))
            action = st.text_area("动作", shot.get('action', ''))
            dialogue = st.text_area("对话", shot.get('dialogue', ''))
            
            col1, col2 = st.columns(2)
            with col1:
                shot_type = st.selectbox(
                    "镜头类型",
                    ["wide", "medium", "close_up", "extreme_close_up"],
                    index=["wide", "medium", "close_up", "extreme_close_up"].index(shot.get('type', 'medium'))
                )
            with col2:
                camera = st.selectbox(
                    "镜头运动",
                    ["static", "pan", "tilt", "zoom", "tracking"],
                    index=["static", "pan", "tilt", "zoom", "tracking"].index(shot.get('camera_movement', 'static'))
                )
            
            duration = st.selectbox(
                "时长",
                ["4s", "5s", "6s", "8s", "10s"],
                index=["4s", "5s", "6s", "8s", "10s"].index(shot.get('duration', '5s'))
            )
            
            # 提示词编辑
            with st.expander("编辑提示词"):
                manual_prompt = st.text_area(
                    "手动覆盖提示词（可选）",
                    value=shot.get('image_prompt', {}).get('positive', '') if shot.get('image_prompt') else ''
                )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("保存"):
                    try:
                        response = requests.put(
                            f"{API_BASE}/api/projects/{project['project_id']}/shots/{shot['shot_id']}",
                            json={
                                "description": description,
                                "action": action,
                                "dialogue": dialogue,
                                "type": shot_type,
                                "camera_movement": camera,
                                "duration": duration,
                                "manual_prompt": manual_prompt if manual_prompt else None
                            },
                            timeout=5
                        )
                        if response.status_code == 200:
                            st.success("保存成功")
                            st.session_state.show_shot_editor = False
                            st.rerun()
                    except Exception as e:
                        st.error(f"保存失败: {e}")
            
            with col2:
                if st.form_submit_button("取消"):
                    st.session_state.show_shot_editor = False
                    st.rerun()


# ============ 首帧生成页面 ============

def keyframes_page():
    """首帧生成页面（对比视图）"""
    st.header("🖼️ 首帧生成")
    
    if not st.session_state.current_project:
        st.warning("请先选择一个项目")
        return
    
    project = st.session_state.current_project
    st.markdown(f"**当前项目**: {project['name']}")
    
    st.markdown("---")
    
    # 生成首帧按钮
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🖼️ 生成所有首帧", type="primary"):
            try:
                response = requests.post(
                    f"{API_BASE}/api/projects/{project['project_id']}/generate-keyframes",
                    json={},
                    timeout=5
                )
                if response.status_code == 200:
                    st.success("首帧生成任务已提交")
                    st.rerun()
            except Exception as e:
                st.error(f"错误: {e}")
    
    with col2:
        # 成本预估
        try:
            response = requests.get(
                f"{API_BASE}/api/projects/{project['project_id']}/cost-estimate",
                timeout=5
            )
            if response.status_code == 200:
                cost = response.json()
                st.info(f"💰 预估成本: ${cost['estimated_cost_usd']}")
        except:
            pass
    
    # 加载分镜和首帧
    try:
        response = requests.get(
            f"{API_BASE}/api/projects/{project['project_id']}/shots",
            timeout=5
        )
        if response.status_code == 200:
            shots = response.json()
            
            if not shots:
                st.info("暂无分镜，请先完成分镜设计")
            else:
                # 筛选有待生成或已生成首帧的分镜
                shots_with_keyframes = [s for s in shots if s.get('batches')]
                
                if not shots_with_keyframes:
                    st.info("暂无首帧，请点击'生成所有首帧'")
                else:
                    st.subheader(f"📷 首帧审核 (共 {len(shots_with_keyframes)} 个)")
                    
                    # 网格布局显示
                    cols = st.columns(2)
                    for i, shot in enumerate(shots_with_keyframes):
                        with cols[i % 2]:
                            st.markdown(f"**{shot['shot_id']}**")
                            st.caption(f"描述: {shot.get('description', '')[:50]}...")
                            
                            # 获取当前batch的首帧
                            current_batch_id = shot.get('current_batch_id')
                            batches = shot.get('batches', {})
                            
                            if current_batch_id and current_batch_id in batches:
                                batch = batches[current_batch_id]
                                keyframe = batch.get('keyframe')
                                
                                if keyframe and keyframe.get('path'):
                                    try:
                                        st.image(keyframe['path'], width='stretch')
                                    except:
                                        st.info("图片加载中...")
                                    
                                    st.caption(f"状态: {keyframe.get('status', 'unknown')}")
                                    
                                    # 对比视图按钮
                                    if st.button("🔍 对比视图", key=f"compare_{shot['shot_id']}"):
                                        st.session_state.comparing_shot = shot
                                        st.session_state.show_comparison = True
                                    
                                    # 审核按钮
                                    if keyframe.get('status') == 'pending_review':
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button("✅ 通过", key=f"approve_kf_{shot['shot_id']}"):
                                                requests.post(
                                                    f"{API_BASE}/api/projects/{project['project_id']}/shots/{shot['shot_id']}/approve-keyframe",
                                                    json={"approved": True}
                                                )
                                                st.rerun()
                                        with col2:
                                            if st.button("❌ 拒绝", key=f"reject_kf_{shot['shot_id']}"):
                                                requests.post(
                                                    f"{API_BASE}/api/projects/{project['project_id']}/shots/{shot['shot_id']}/approve-keyframe",
                                                    json={"approved": False, "reason": "需要重新生成"}
                                                )
                                                st.rerun()
                                    
                                    # 重新生成
                                    with st.expander("🔄 重新生成"):
                                        method = st.radio(
                                            "方式",
                                            ["改Seed", "改提示词", "两者都改"],
                                            key=f"regen_kf_method_{shot['shot_id']}"
                                        )
                                        new_seed = st.number_input(
                                            "新Seed",
                                            value=0,
                                            key=f"regen_kf_seed_{shot['shot_id']}"
                                        )
                                        new_prompt = st.text_area(
                                            "新提示词",
                                            value=keyframe.get('prompt', ''),
                                            key=f"regen_kf_prompt_{shot['shot_id']}"
                                        )
                                        
                                        if st.button("重新生成", key=f"regen_kf_{shot['shot_id']}"):
                                            requests.post(
                                                f"{API_BASE}/api/projects/{project['project_id']}/shots/{shot['shot_id']}/regenerate-keyframe",
                                                json={
                                                    "method": method,
                                                    "new_seed": new_seed if method in ["改Seed", "两者都改"] else None,
                                                    "new_prompt": new_prompt if method in ["改提示词", "两者都改"] else None
                                                }
                                            )
                                            st.success("重新生成任务已提交")
    except Exception as e:
        st.error(f"加载首帧失败: {e}")
    
    # 对比视图弹窗
    if st.session_state.get('show_comparison') and st.session_state.get('comparing_shot'):
        shot = st.session_state.comparing_shot
        
        st.subheader(f"🔍 对比视图: {shot['shot_id']}")
        
        # 获取参考图和首帧
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🎨 参考图**")
            # 显示角色和场景参考（简化版，实际应该显示关联的参考图）
            st.info("角色/场景参考图")
            
            # 显示提示词
            if shot.get('image_prompt'):
                with st.expander("查看提示词"):
                    st.code(shot['image_prompt'].get('positive', ''), language="text")
        
        with col2:
            st.markdown("**🖼️ 生成首帧**")
            
            current_batch_id = shot.get('current_batch_id')
            batches = shot.get('batches', {})
            
            if current_batch_id and current_batch_id in batches:
                keyframe = batches[current_batch_id].get('keyframe')
                if keyframe and keyframe.get('path'):
                    try:
                        st.image(keyframe['path'], width='stretch')
                    except:
                        st.error("图片加载失败")
                    
                    # 显示完整提示词
                    with st.expander("📋 实际发送给AI的完整Prompt", expanded=True):
                        st.code(shot.get('display_prompt', keyframe.get('prompt', '')), language="text")
                        st.text(f"Seed: {keyframe.get('seed', 'N/A')}")
        
        if st.button("关闭对比视图"):
            st.session_state.show_comparison = False
            st.rerun()
