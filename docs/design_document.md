# 动画/动态漫画生成系统 - 设计文档 (v1.1)

**版本**: 1.1  
**日期**: 2026-02-07  
**状态**: 设计阶段（MVP修订版）

---

## 版本修订记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| 1.0 | 2026-02-07 | 初始版本（Celery + SQLite + React） |
| 1.1 | 2026-02-07 | **MVP简化版**：JSON存储 + 纯asyncio + Streamlit；增加Batch ID、GenerationHistory、成本预估、Webhook等 |

---

## 1. 系统概述

### 1.1 目标
构建一个从剧本到动画/动态漫画的自动化生成系统，支持人工审核干预，确保生成质量。

### 1.2 核心特性
- **Markdown剧本输入**：支持标准Markdown格式
- **风格描述**：自然语言风格描述（如"高精度日系作画风格，参考新海诚动画电影"）
- **七阶段Pipeline**：提取 → 参考图 → 分镜 → 首帧 → 视频 → 输出
- **人工审核点**：4个关键审核节点（提取结果、参考图、首帧、视频）
- **并行生成**：可配置并发数，加速生成过程
- **错误恢复**：断点续传，状态持久化
- **成本预估**：生成前显示预估成本

### 1.3 非目标（Out of Scope）
- 音频生成（预留接口，暂不实现）
- 后期剪辑合成（输出独立片段）
- 实时协作编辑

---

## 2. 架构设计（MVP版）

### 2.1 系统架构图（MVP简化）

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Web 界面                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ 项目管理  │ │ 画廊视图  │ │ 对比视图  │ │ 成本预估  │           │
│  │ (侧边栏)  │ │ (主区域)  │ │ (模态框)  │ │ (弹窗)   │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
└───────┼────────────┼────────────┼────────────┼─────────────────┘
        │            │            │            │
        └────────────┴────────────┴────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Backend (纯Python，无Celery)                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ 项目控制器  │ │ 异步任务池  │ │ 状态管理器  │ │ 文件管理器  │   │
│  └──────┬─────┘ └──────┬─────┘ └──────┬─────┘ └──────┬─────┘   │
└─────────┼──────────────┼──────────────┼──────────────┼─────────┘
          │              │              │              │
          └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     存储层（JSON文件）                            │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ project.json    │ │ history/        │ │ logs/           │   │
│  │ (状态+配置)      │ │ (生成历史)       │ │ (运行日志)       │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   LLM Provider  │  │  nanobanana API │  │ Sora2/Veo3 API  │
│ (OpenAI/Claude) │  │   (图片生成)     │  │   (视频生成)     │
│  + Webhook回调  │  │                 │  │  + Webhook回调  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 2.2 技术栈选型（MVP版）

| 组件 | 技术 | 理由 |
|------|------|------|
| **Web框架** | FastAPI + Streamlit | 前后端分离，后期可替换前端 |
| **存储** | JSON文件 + 本地文件系统 | 零依赖，易于备份和迁移 |
| **任务调度** | 纯asyncio + asyncio.Queue | 无需Redis，MVP足够 |
| **LLM调用** | LiteLLM | 统一接口，支持多提供商切换 |
| **配置管理** | Pydantic Settings + YAML | 两层配置结构 |

**后期可迁移至**：
- Streamlit → React/Vue
- JSON文件 → SQLite/PostgreSQL
- 纯asyncio → Celery + Redis

---

## 3. 数据模型（MVP修订版）

### 3.1 核心变更

**变更1**: Project.status 改为**计算属性**，基于任务完成度计算
**变更2**: 增加 **GenerationHistory** 表，支持回滚到历史版本
**变更3**: 增加 **Batch** 概念，支持同一组分镜多次尝试

### 3.2 JSON Schema 定义

#### Project (项目) - 修订版
```json
{
  "project_id": "uuid",
  "name": "项目名称",
  "created_at": "2026-02-07T19:00:00Z",
  "updated_at": "2026-02-07T19:30:00Z",
  "script_path": "00_script/script.md",
  "style_description": "高精度日系作画风格，参考新海诚动画电影",
  
  "config": {
    "resolution": "1280x720",
    "frame_rate": 24,
    "parallel_workers": 4,
    "llm_provider": "openai",
    "llm_model": "gpt-4",
    "image_provider": "nanobanana",
    "video_provider": "sora2",
    "video_duration": "5s"
  },
  
  "statistics": {
    "total_characters": 5,
    "total_scenes": 10,
    "total_shots": 50,
    "completed_tasks": 25,
    "failed_tasks": 0,
    "pending_tasks": 25
  },
  
  "current_stage": "generating_frames",
  "is_running": false
}
```

**注意**: `status` 不再是存储字段，而是计算属性：
```python
@property
def status(self):
    """计算项目整体状态"""
    if self.statistics['failed_tasks'] > 0:
        return "error"
    if self.statistics['completed_tasks'] == 0:
        return "draft"
    if self.statistics['completed_tasks'] == self.statistics['total_tasks']:
        return "completed"
    return "in_progress"

@property
def progress_percentage(self):
    """计算进度百分比"""
    total = self.statistics['total_tasks']
    completed = self.statistics['completed_tasks']
    return (completed / total * 100) if total > 0 else 0
```

#### Character (人物) - 修订版
```json
{
  "character_id": "char_001",
  "name": "角色名称",
  "description": "外貌描述",
  "personality": "性格特征",
  "status": "approved",
  
  "reference_image": {
    "current_version": 2,
    "versions": [
      {
        "version_id": 1,
        "status": "rejected",
        "prompt": "提示词...",
        "seed": 12345,
        "path": "02_references/characters/char_001_v1.png",
        "rejected_reason": "发色不对",
        "created_at": "timestamp"
      },
      {
        "version_id": 2,
        "status": "approved",
        "prompt": "修正后的提示词...",
        "seed": 67890,
        "path": "02_references/characters/char_001_v2.png",
        "created_at": "timestamp"
      }
    ]
  },
  
  "manual_override": {
    "prompt": null,
    "enabled": false
  }
}
```

#### Shot (分镜) - 修订版（增加Batch支持）
```json
{
  "shot_id": "shot_001",
  "scene_id": "scene_001",
  "sequence": 1,
  "type": "wide|medium|close_up",
  "camera_movement": "static|pan|tilt|zoom",
  "duration": "5s",
  "description": "分镜描述",
  "action": "动作描述",
  "dialogue": "对话内容",
  "characters": ["char_001"],
  
  "image_prompt": {
    "positive": "详细图片描述...",
    "negative": "负面提示词...",
    "parameters": {"seed": 12345, "steps": 30}
  },
  
  "video_prompt": {
    "description": "视频动作描述...",
    "camera": "相机运动描述"
  },
  
  "display_prompt": "实际发送给AI的完整Prompt（拼接后）",
  
  "placeholder": {
    "enabled": false,
    "type": "sketch|reference_image",
    "path": null,
    "description": "占位符说明"
  },
  
  "current_batch": {
    "batch_id": "batch_002",
    "keyframe_version": 3,
    "video_version": 2
  },
  
  "batches": {
    "batch_001": {
      "created_at": "timestamp",
      "keyframe": {
        "status": "rejected",
        "path": "03_keyframes/shot_001_batch_001.png",
        "prompt": "...",
        "seed": 11111,
        "rejected_reason": "构图不佳"
      },
      "video": null
    },
    "batch_002": {
      "created_at": "timestamp",
      "keyframe": {
        "status": "approved",
        "path": "03_keyframes/shot_001_batch_002.png",
        "prompt": "...",
        "seed": 22222
      },
      "video": {
        "status": "approved",
        "path": "04_videos/shot_001_batch_002.mp4",
        "cost_usd": 0.50
      }
    }
  },
  
  "cost_estimate": {
    "image_generation": 0.02,
    "video_generation": 0.50,
    "total": 0.52
  }
}
```

#### Task (任务) - 新增（用于追踪异步任务）
```json
{
  "task_id": "task_uuid",
  "project_id": "project_uuid",
  "entity_type": "character|scene|shot",
  "entity_id": "shot_001",
  "batch_id": "batch_002",
  "task_type": "generate_keyframe|generate_video",
  "status": "pending|running|completed|failed",
  "worker_id": "worker_001",
  "started_at": "timestamp",
  "completed_at": "timestamp",
  "retry_count": 0,
  "max_retries": 3,
  "error_message": null,
  "cost_usd": 0.50,
  "api_response": {...}
}
```

---

## 4. 七阶段工作流程（修订版）

### 4.1 阶段详细说明（增加新功能）

#### Stage 2-3: 参考图生成（增加显示完整Prompt）

**新增要求**: 必须显示"实际发送给AI的完整Prompt"

```python
# Prompt 拼接逻辑
def build_character_prompt(character, style):
    base_prompt = character['reference_image']['versions'][-1]['prompt']
    full_prompt = f"{base_prompt}, {style}, high quality, detailed"
    negative_prompt = "bad anatomy, bad hands, worst quality, low quality"
    
    return {
        "positive": full_prompt,
        "negative": negative_prompt,
        "display": full_prompt  # 用户界面显示
    }
```

**UI要求**: 
- 画廊视图下方显示完整Prompt
- 支持"编辑并重新生成"（覆盖原Prompt）
- 显示Seed值，支持"换Seed重试"

#### Stage 5: 首帧生成（增加导演模式）

**新增功能**: 占位符（Placeholder）

```python
# 导演模式逻辑
async def generate_keyframe(shot, references):
    if shot['placeholder']['enabled']:
        # 使用用户上传的草图/参考图作为控制
        control_image = shot['placeholder']['path']
        return await generate_with_controlnet(
            prompt=shot['image_prompt'],
            control_image=control_image,
            references=references
        )
    else:
        # 正常生成
        return await generate_image(
            prompt=shot['image_prompt'],
            references=references
        )
```

**UI支持**:
- 分镜列表中上传占位符按钮
- 占位符预览（小缩略图）
- 生成时使用ControlNet输入

#### Stage 6: 视频生成（增加成本预估）

**新增要求**: 批量生成前显示成本预估弹窗

```python
# 成本预估逻辑
class CostEstimator:
    PRICING = {
        'nanobanana': {'per_image': 0.02},
        'sora2': {'per_second': 0.10},  # 假设10秒=$1
        'veo3': {'per_second': 0.08}
    }
    
    def estimate_video_cost(self, shots, provider):
        total_seconds = sum(self.parse_duration(s['duration']) for s in shots)
        cost = total_seconds * self.PRICING[provider]['per_second']
        return {
            'shots_count': len(shots),
            'total_seconds': total_seconds,
            'estimated_cost_usd': round(cost, 2),
            'provider': provider
        }
```

**UI弹窗**:
```
┌────────────────────────────────────────────┐
│ ⚠️  成本确认                                │
├────────────────────────────────────────────┤
│ 即将生成 50 个视频片段                        │
│ 总时长: 250 秒                              │
│ 提供商: Sora2                               │
│                                            │
│ 预估费用: $25.00 USD                        │
│ 账户余额: $100.00 USD                       │
│                                            │
│ [取消]              [确认生成]              │
└────────────────────────────────────────────┘
```

---

## 5. 视频时长控制（修订）

### 5.1 时长枚举定义

```python
from enum import Enum

class VideoDuration(str, Enum):
    """视频生成模型通常只支持固定时长档位"""
    SECONDS_4 = "4s"
    SECONDS_5 = "5s"
    SECONDS_6 = "6s"
    SECONDS_8 = "8s"
    SECONDS_10 = "10s"

class VideoProvider(Enum):
    SORA2 = "sora2"
    VEO3 = "veo3"
    
    @property
    def supported_durations(self):
        durations = {
            'sora2': [VideoDuration.SECONDS_5, VideoDuration.SECONDS_10],
            'veo3': [VideoDuration.SECONDS_4, VideoDuration.SECONDS_8]
        }
        return durations[self.value]
    
    def validate_duration(self, duration: VideoDuration):
        if duration not in self.supported_durations:
            raise ValueError(f"{self.value} 不支持 {duration}，支持的时长: {self.supported_durations}")
```

### 5.2 配置示例

```yaml
# config.yaml
generation:
  video_duration: "5s"  # 根据所选模型自动验证
  
  # 或者按模型配置
  duration_by_provider:
    sora2: "5s"
    veo3: "4s"
```

---

## 6. 错误恢复与容错（修订）

### 6.1 僵尸任务处理（新增）

```python
# FastAPI startup event
@app.on_event("startup")
async def recover_zombie_tasks():
    """启动时恢复僵尸任务"""
    zombie_timeout = 300  # 5分钟无更新视为僵尸
    
    # 查找所有运行中超时的任务
    zombie_tasks = await Task.filter(
        status="running",
        started_at__lt=datetime.now() - timedelta(seconds=zombie_timeout)
    )
    
    for task in zombie_tasks:
        logger.warning(f"发现僵尸任务: {task.task_id}, 重置为 failed")
        task.status = "failed"
        task.error_message = "Worker进程异常终止（僵尸任务恢复）"
        await task.save()
        
        # 更新实体状态
        await update_entity_status(task.entity_id, "failed")
```

### 6.2 Webhook回调机制（新增）

```python
# FastAPI Webhook端点
@app.post("/webhook/video/{provider}")
async def video_webhook_callback(
    provider: str,
    request: Request,
    background_tasks: BackgroundTasks
):
    """接收视频生成服务的Webhook回调"""
    payload = await request.json()
    
    # 验证签名（防伪造）
    signature = request.headers.get("X-Signature")
    if not verify_webhook_signature(payload, signature, provider):
        raise HTTPException(401, "Invalid signature")
    
    task_id = payload.get("task_id")
    status = payload.get("status")  # completed/failed
    result_url = payload.get("result_url")
    
    # 更新任务状态
    task = await Task.get_or_none(task_id=task_id)
    if task:
        if status == "completed":
            task.status = "completed"
            task.result_url = result_url
            await update_entity_status(task.entity_id, "completed", result_url)
        else:
            task.status = "failed"
            task.error_message = payload.get("error")
        
        await task.save()
    
    return {"status": "ok"}

# 任务提交时注册Webhook
async def submit_video_generation(task):
    """提交视频生成任务，注册Webhook回调"""
    callback_url = f"{settings.PUBLIC_URL}/webhook/video/{task.provider}"
    
    response = await video_api.submit(
        prompt=task.prompt,
        first_frame=task.first_frame,
        webhook_url=callback_url,
        webhook_headers={"X-Task-ID": task.task_id}
    )
    
    task.external_task_id = response["task_id"]
    await task.save()
```

### 6.3 降级策略（当Webhook不可用时）

```python
async def poll_task_status(task, max_attempts=60):
    """轮询作为Webhook的降级方案"""
    for i in range(max_attempts):
        status = await video_api.check_status(task.external_task_id)
        
        if status == "completed":
            await handle_completion(task)
            return
        elif status == "failed":
            await handle_failure(task)
            return
        
        await asyncio.sleep(10)  # 每10秒检查一次
    
    # 超时处理
    task.status = "failed"
    task.error_message = "轮询超时"
    await task.save()
```

---

## 7. 配置管理（修订 - 两层配置）

### 7.1 全局默认配置

```yaml
# ~/.animation_gen/config.yaml (全局配置)
defaults:
  # API设置
  llm:
    provider: "openai"
    base_url: "https://api.openai.com/v1"
    model: "gpt-4"
    temperature: 0.7
    max_tokens: 4096
  
  image:
    provider: "nanobanana"
    base_url: "https://api.nanobanana.com"
    default_steps: 30
    default_cfg: 7.0
  
  video:
    provider: "sora2"
    base_url: "https://api.sora2.com"
    duration: "5s"
  
  # 生成参数
  generation:
    resolution: "1280x720"
    frame_rate: 24
    character_ref_resolution: "512x512"
    scene_ref_resolution: "768x432"
    keyframe_resolution: "1280x720"
  
  # 并行配置
  concurrency:
    llm_workers: 8
    image_workers: 4
    video_workers: 2
  
  # 成本限制
  cost_limits:
    max_cost_per_project_usd: 100.0
    warn_threshold_usd: 50.0

# 多LLM提供商配置
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    models: ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
  
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
    models: ["claude-3-opus", "claude-3-sonnet"]
  
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
    models: ["google/gemini-pro", "meta/llama-3"]
```

### 7.2 项目覆盖配置

```yaml
# {project_root}/config.yaml (项目级配置，覆盖全局)
# 只需定义需要覆盖的字段

# 示例：使用不同的LLM提供商
llm:
  provider: "anthropic"  # 覆盖全局的openai
  model: "claude-3-opus"

# 示例：调整视频参数
video:
  provider: "veo3"  # 使用veo3而不是sora2
  duration: "4s"    # veo3支持4秒

# 示例：调整并行度
concurrency:
  image_workers: 2  # 降低并发，避免API限流
```

### 7.3 配置加载逻辑

```python
from pydantic import BaseSettings, Field
from typing import Optional
import yaml

class Config(BaseSettings):
    """配置类，支持两层配置"""
    
    # 加载全局配置
    @classmethod
    def load_global(cls):
        global_path = Path.home() / ".animation_gen" / "config.yaml"
        if global_path.exists():
            with open(global_path) as f:
                return yaml.safe_load(f)
        return {}
    
    # 加载项目配置（覆盖全局）
    @classmethod
    def load_project(cls, project_path: Path):
        global_config = cls.load_global()
        project_config_path = project_path / "config.yaml"
        
        if project_config_path.exists():
            with open(project_config_path) as f:
                project_config = yaml.safe_load(f)
                # 深度合并
                return deep_merge(global_config, project_config)
        
        return global_config
    
    # 运行时切换LLM提供商
    def switch_llm_provider(self, provider: str):
        """切换到不同的LLM提供商"""
        if provider not in self.providers:
            raise ValueError(f"未知的提供商: {provider}")
        
        self.llm.provider = provider
        self.llm.api_key = self.providers[provider].api_key
        self.llm.base_url = self.providers[provider].base_url
```

---

## 8. Web界面设计（Streamlit修订版）

### 8.1 关键视图修订

#### 对比视图（增加完整Prompt显示）

```python
# Streamlit伪代码
def comparison_view(shot):
    col1, col2 = st.columns(2)
    
    with col1:
        st.image(shot['reference_image'], caption="参考图")
        st.text_area("参考图Prompt", shot['ref_prompt'], disabled=True)
    
    with col2:
        st.image(shot['keyframe'], caption="生成首帧")
        
        # 关键：显示完整Prompt
        with st.expander("📋 查看实际发送给AI的完整Prompt", expanded=True):
            st.code(shot['display_prompt'], language="text")
            st.text(f"Seed: {shot['seed']}")
            st.text(f"Steps: {shot['steps']}")
            st.text(f"CFG: {shot['cfg']}")
    
    # 操作按钮
    col3, col4, col5 = st.columns(3)
    with col3:
        if st.button("✅ 通过"):
            approve_shot(shot)
    with col4:
        if st.button("❌ 拒绝"):
            reject_shot(shot)
    with col5:
        # 重新生成选项
        option = st.selectbox("重新生成方式", ["改Seed", "改Prompt", "两者都改"])
        if st.button("🔄 重新生成"):
            regenerate_shot(shot, option)
```

#### 导演模式界面（占位符上传）

```python
def director_mode_view(shot):
    st.subheader(f"分镜 {shot['shot_id']}: {shot['description']}")
    
    # 占位符上传
    uploaded_file = st.file_uploader(
        "上传草图或参考图作为占位符（可选）",
        type=["png", "jpg", "jpeg"],
        key=f"placeholder_{shot['shot_id']}"
    )
    
    if uploaded_file:
        st.image(uploaded_file, caption="占位符预览")
        
        # 保存占位符
        save_placeholder(shot, uploaded_file)
        
        # 显示占位符状态
        st.info("已启用占位符模式：生成时将以此图为参考构图")
        
        # 选项：是否使用ControlNet
        use_controlnet = st.checkbox("使用ControlNet精确控制构图", value=True)
    
    # 正常生成按钮
    if st.button("生成首帧", disabled=shot['status'] == 'generating'):
        generate_keyframe(shot, use_placeholder=uploaded_file is not None)
```

#### 成本预估弹窗

```python
def cost_confirmation_dialog(shots, provider):
    """生成前显示成本确认弹窗"""
    
    estimator = CostEstimator()
    estimate = estimator.estimate_video_cost(shots, provider)
    
    # Streamlit原生不支持模态弹窗，使用session_state模拟
    if 'show_cost_dialog' not in st.session_state:
        st.session_state.show_cost_dialog = True
    
    if st.session_state.show_cost_dialog:
        with st.container():
            st.warning("⚠️ 成本确认")
            st.write(f"即将生成 **{estimate['shots_count']}** 个视频片段")
            st.write(f"总时长: **{estimate['total_seconds']}** 秒")
            st.write(f"提供商: **{estimate['provider']}**")
            st.write(f"预估费用: **${estimate['estimated_cost_usd']}** USD")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("取消"):
                    st.session_state.show_cost_dialog = False
                    return False
            with col2:
                if st.button("✅ 确认生成", type="primary"):
                    st.session_state.show_cost_dialog = False
                    return True
    
    return False
```

---

## 9. 项目文件结构（修订版）

```
{project_root}/
├── project.json                    # 项目元数据+状态
├── config.yaml                     # 项目级配置（覆盖全局）
│
├── 00_script/
│   └── script.md                   # 原始剧本
│
├── 01_extraction/
│   ├── characters.json             # 人物列表
│   ├── scenes.json                 # 场景列表
│   └── shots.json                  # 分镜列表
│
├── 02_references/
│   ├── characters/
│   │   ├── char_001_v1.png         # 历史版本
│   │   ├── char_001_v2.png         # 当前版本
│   │   └── ...
│   └── scenes/
│       ├── scene_001_v1.png
│       └── ...
│
├── 03_keyframes/                   # 按Batch组织
│   ├── shot_001_batch_001.png      # 历史版本
│   ├── shot_001_batch_002.png      # 当前版本
│   └── ...
│
├── 04_videos/
│   ├── shot_001_batch_001.mp4
│   ├── shot_001_batch_002.mp4
│   └── ...
│
├── 05_audio/                       # 预留
│   └── .gitkeep
│
├── 06_placeholders/                # 导演模式占位符
│   ├── shot_001_placeholder.png
│   └── ...
│
├── logs/
│   ├── generation.log
│   ├── api_calls.log
│   └── webhook.log                 # Webhook接收日志
│
└── history/                        # 生成历史记录
    └── generation_history.jsonl    # 每行一个历史记录，便于追加
```

---

## 10. 实施路线图（MVP修订版）

### Milestone 1: 核心框架 + Stage 1-3 (2周)
- [x] 设计文档定稿
- [ ] 项目创建与文件结构管理
- [ ] JSON状态持久化
- [ ] FastAPI基础API
- [ ] Stage 1: 剧本解析
- [ ] Stage 2-3: 参考图生成 + 画廊审核
- [ ] Streamlit基础界面（项目列表、画廊）
- [ ] 全局/项目两层配置

**交付**: 可以上传剧本 → 生成 → 审核参考图

### Milestone 2: Stage 4-5 + 导演模式 (1.5周)
- [ ] Stage 4: 分镜设计 + 时间线视图
- [ ] Stage 5: 首帧生成
- [ ] **对比视图**（显示完整Prompt）
- [ ] **导演模式**（占位符上传）
- [ ] Batch ID + GenerationHistory

**交付**: 可以生成并审核首帧，支持历史版本回滚

### Milestone 3: Stage 6 + 成本预估 + Webhook (1.5周)
- [ ] Stage 6: 视频生成
- [ ] **成本预估弹窗**
- [ ] **Webhook回调机制**
- [ ] 僵尸任务恢复
- [ ] 视频播放器审核

**交付**: 完整端到端流程可用

### Milestone 4: 优化与迁移准备 (1周)
- [ ] 多LLM提供商切换UI
- [ ] 性能优化
- [ ] 文档完善
- [ ] 为迁移到React + SQLite做准备（抽象接口）

---

## 附录 A: API接口详细规范（新增Webhook）

```
# Webhook回调（供应商 → 我们的服务）
POST   /webhook/video/{provider}        # 视频生成完成回调
POST   /webhook/image/{provider}        # 图片生成完成回调（备用）

# 验证Webhook签名
Headers:
  X-Signature: sha256=...
  X-Task-ID: {task_id}
  X-Event-Type: completed|failed

# 响应
200 OK: {"status": "received"}
400 Bad Request: 签名无效
```

---

**文档结束 (v1.1)**

*主要修订内容*:
1. MVP简化：JSON存储 → 纯asyncio → Streamlit
2. 增加Batch ID + GenerationHistory支持版本回滚
3. 视频时长改为枚举值
4. 增加显示完整Prompt、导演模式、成本预估
5. 增加Webhook回调 + 僵尸任务恢复
6. 两层配置结构（全局 + 项目）

*请确认后开始实施Milestone 1。*
