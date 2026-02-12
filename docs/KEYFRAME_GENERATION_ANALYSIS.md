# 首帧生成逻辑深度分析

## 一、架构概览

首帧生成是动画生成系统的**第四阶段**（Stage 4），承上启下：
- **输入**: 分镜设计(Stage 3)生成的 shot + 参考图(Stage 2)生成的角色/场景图片
- **输出**: 每个分镜的首帧图片（用于视频生成 Stage 5）

```
剧本解析(Stage 1) → 参考图生成(Stage 2) → 分镜设计(Stage 3) → 【首帧生成(Stage 4)】 → 视频生成(Stage 5)
                                                                     ↑
                                                              多图i2i技术融合
                                                                     ↓
                                                        角色参考图 + 场景参考图
```

---

## 二、核心数据模型

### 2.1 Shot 模型（分镜）
```python
class Shot(BaseModel):
    shot_id: str
    scene_id: str
    sequence: int
    
    # 提示词
    image_prompt: Optional[ImagePrompt] = None    # 图片生成提示词
    video_prompt: Optional[VideoPrompt] = None    # 视频生成提示词
    
    # Batch版本管理（关键设计）
    current_batch_id: Optional[str] = None
    batches: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # 状态流转
    status: Optional[str] = None  # draft → frame_pending_review → frame_approved → video_generating → completed
```

### 2.2 Batch 版本管理设计
每个分镜支持**多版本首帧**，通过 `batches` 字段管理：

```python
{
  "batch_001": {
    "created_at": "2026-02-12T10:00:00",
    "keyframe": {
      "status": "approved",           # pending_review / approved / rejected
      "path": "/path/to/image.png",
      "prompt": "positive prompt...",
      "seed": 12345
    },
    "videos": []  # 关联的视频生成记录
  },
  "batch_002": { ... }  # 重新生成的版本
}
```

**设计优势**：
- ✅ 支持版本回滚（不满意可切换回旧版本）
- ✅ 保留历史记录（每次重新生成都有记录）
- ✅ 首帧和视频关联（batch 内包含 keyframe 和 videos）

---

## 三、生成流程详解

### 3.1 API 端点
```
POST /api/projects/{project_id}/generate-keyframes
POST /api/projects/{project_id}/shots/{shot_id}/approve-keyframe
POST /api/projects/{project_id}/shots/{shot_id}/regenerate-keyframe
GET  /api/projects/{project_id}/cost-estimate
```

### 3.2 核心生成流程（generate_keyframes）

```python
async def generate_keyframes(project_id: str, shot_ids: Optional[List[str]] = None):
    # 1. 加载项目数据
    shots = project_manager.load_shots(project)
    characters = project_manager.load_characters(project)
    scenes = project_manager.load_scenes(project)
    
    # 2. 构建参考图字典
    char_refs = {char.character_id: version.path for char in characters}
    scene_refs = {scene.scene_id: version.path for scene in scenes}
    
    # 3. 提交到图片生成队列
    for shot in shots:
        async def gen_keyframe(s=shot):
            # 3.1 创建新 batch
            batch_id = s.create_batch()
            
            # 3.2 准备参考图
            shot_char_refs = {cid: char_refs[cid] for cid in s.characters}
            scene_ref = scene_refs.get(s.scene_id)
            
            # 3.3 调用图片生成服务
            actual_path = await image_service.generate_keyframe(
                s, shot_char_refs, scene_ref, output_path
            )
            
            # 3.4 更新状态
            if actual_path:
                s.status = "frame_pending_review"
            else:
                s.status = "frame_failed"
        
        await image_queue.submit(gen_keyframe)
```

### 3.3 多图 i2i 生成核心（ImageService.generate_keyframe）

**技术方案**：使用多张参考图进行 image-to-image 生成

```python
async def generate_keyframe(self, shot, character_refs, scene_ref, output_path):
    # 1. 准备提示词
    prompt = shot.image_prompt.positive
    
    # 2. 多提供商适配
    if self.image_config.provider == "jiekouai":
        # 接口AI方式：支持多图i2i
        actual_path = await self.jiekouai_service.generate_keyframe(
            prompt=prompt,
            character_refs=char_paths,  # 角色参考图列表
            scene_ref=scene_ref,         # 场景参考图
            size="1280x720"
        )
    else:
        # 通用方式：直接调用generate_image
        result = await self.generate_image(
            prompt=prompt,
            reference_images=[scene_ref] + char_paths
        )
```

### 3.4 图片压缩策略（JiekouAIImageService）

**关键问题**：API 对图片大小有限制（通常<300KB）

**压缩策略**：
```python
def _compress_image_to_base64(self, local_path: str, max_size_kb: int = 300):
    # 策略1: 降低JPEG质量 (quality: 85 → 20)
    while quality > 20:
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
        if size_kb <= max_size_kb:
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        quality -= 10
    
    # 策略2: 缩小尺寸 (ratio: 0.9 → 0.3)
    while ratio > 0.3:
        new_size = (int(img.width * ratio), int(img.height * ratio))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        if size_kb <= max_size_kb:
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        ratio -= 0.1
    
    # 策略3: 强制保底 (512x512, quality=60)
    img.resize((512, 512), Image.Resampling.LANCZOS).save(buffer, format='JPEG', quality=60)
```

---

## 四、状态流转

### 4.1 分镜状态机
```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                                                             ▼
draft → frame_generating → frame_pending_review → frame_approved → video_generating → completed
                │              │                      │
                │              ▼                      ▼
                └──────► frame_failed           frame_failed (重新生成)
```

### 4.2 状态说明
| 状态 | 说明 | 可操作 |
|------|------|--------|
| `draft` | 分镜刚创建，未生成首帧 | 生成首帧 |
| `frame_generating` | 首帧生成中 | 等待 |
| `frame_pending_review` | 首帧待审核 | 审核/重新生成 |
| `frame_approved` | 首帧已通过 | 进入视频生成 |
| `frame_failed` | 生成失败 | 重新生成 |
| `video_generating` | 视频生成中 | 等待 |
| `completed` | 全部完成 | 下载 |

---

## 五、前端交互设计

### 5.1 页面布局（Keyframes.vue）
```
┌─────────────────────────────────────────────────────────────┐
│ 首帧生成                                        [成本预估]   │
│                                         [生成所有] [刷新]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │         │
│  │  │       │  │  │  │       │  │  │  │       │  │         │
│  │  │ 图片  │  │  │  │ 图片  │  │  │  │ 图片  │  │         │
│  │  │       │  │  │  │       │  │  │  │       │  │         │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │         │
│  │  shot_001   │  │  shot_002   │  │  shot_003   │         │
│  │  [待审核]   │  │  [已通过]   │  │  [待审核]   │         │
│  │  [重新生成] │  │             │  │  [重新生成] │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 核心功能
| 功能 | 实现 |
|------|------|
| **批量生成** | 一键提交所有分镜的首帧生成任务 |
| **成本预估** | 根据分镜数量估算视频生成成本 |
| **重新生成** | 支持更换Seed或修改Prompt后重新生成 |
| **查看详情** | 点击查看大图、完整提示词、参数 |
| **编辑提示词** | 修改全局图片/视频提示词模板 |

---

## 六、关键设计亮点

### 6.1 多图 i2i 技术
**创新点**：同时融合**场景参考图** + **多角色参考图**生成首帧

```python
# 参考图融合顺序：
reference_images = [
    scene_base64,      # 第1张：场景（背景氛围）
    char1_base64,      # 第2张：角色1
    char2_base64,      # 第3张：角色2
    ...
]

# API调用
payload = {
    "images": reference_images,  # 多图参考
    "prompt": "详细的画面描述",
    "size": "16x9"  # 1280x720
}
```

**优势**：
- ✅ 角色一致性：参考图引导生成的角色外观保持一致
- ✅ 场景融合：背景与角色自然融合
- ✅ 批量处理：一次请求融合多张参考图

### 6.2 异步队列处理
```python
# 提交到图片生成队列
image_queue = get_queue("image", max_workers=4)
await image_queue.submit(gen_keyframe, priority=TaskPriority.NORMAL)
```

**队列特性**：
- 最大并发数：4（避免API限流）
- 优先级控制：重新生成任务为高优先级
- 失败重试：自动重试3次

### 6.3 成本预估
```python
# 基于分镜数量估算视频生成成本
def estimate_cost(shot_count: int, duration: str = "5s"):
    seconds = int(duration.replace("s", ""))
    total_seconds = shot_count * seconds
    estimated_cost = total_seconds * 0.05  # $0.05/秒
    
    return {
        "shot_count": shot_count,
        "total_seconds": total_seconds,
        "estimated_cost_usd": round(estimated_cost, 2)
    }
```

---

## 七、潜在问题与建议

### 7.1 当前问题

| 问题 | 影响 | 建议方案 |
|------|------|----------|
| **i2i 参考图顺序** | 场景图和角色图融合效果不确定 | 测试不同顺序的生成效果 |
| **压缩导致质量损失** | 压缩到<300KB可能丢失细节 | 支持配置压缩阈值 |
| **缺少进度反馈** | 用户不知道生成进度 | 添加WebSocket实时进度 |
| **单点失败** | 一个分镜失败不影响其他 | ✅ 已支持，但需优化错误提示 |

### 7.2 改进建议

1. **首帧选择功能**
   ```python
   # 生成多个候选首帧供用户选择
   async def generate_keyframe_candidates(shot, n=4):
       candidates = []
       for i in range(n):
           seed = random.randint(1, 999999999)
           path = await generate_with_seed(shot, seed)
           candidates.append({"seed": seed, "path": path})
       return candidates
   ```

2. **批量审核**
   ```python
   # 一键审核通过所有首帧
   POST /api/projects/{id}/keyframes/batch-approve
   ```

3. **首帧对比**
   - 支持新旧版本首帧左右对比
   - 显示生成参数差异

4. **智能提示词优化**
   - 基于首帧效果自动优化提示词
   - 提示词效果评分

---

## 八、代码文件清单

| 文件 | 职责 |
|------|------|
| `src/services/image_service.py` | 首帧生成服务接口，多提供商适配 |
| `src/services/jiekouai_service.py` | 接口AI实现，多图i2i，图片压缩 |
| `src/models/schemas.py` | Shot/GenerationVersion/ImagePrompt 数据模型 |
| `src/main.py` | generate_keyframes / approve_keyframe / regenerate_keyframe API |
| `frontend/src/views/Keyframes.vue` | 首帧生成页面UI |
| `config/default_config.yaml` | image_prompt / video_prompt 模板配置 |

---

## 九、总结

首帧生成模块采用**多图i2i + Batch版本管理 + 异步队列**的架构设计：

1. **技术亮点**：多图融合保持角色/场景一致性
2. **产品亮点**：版本管理支持回滚和对比
3. **工程亮点**：异步队列保证稳定性和并发控制

整体实现较为完善，但在**生成进度反馈**、**批量操作**、**首帧候选**等方面还有优化空间。
