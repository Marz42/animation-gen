# 动画生成系统 - 项目交接文档
**交接日期**: 2026-02-08  
**交接人**: Alice → Kimi Code  
**项目状态**: Stage 1-5 已完成，Stage 6 待开发

---

## 📁 项目位置

```
/home/ventus/.openclaw/workspace/animation-gen/
├── src/
│   ├── main.py                 # FastAPI 后端主入口
│   ├── app.py                  # Streamlit 前端主入口
│   ├── models/
│   │   └── schemas.py          # Pydantic 数据模型
│   ├── core/
│   │   ├── config.py           # 配置管理
│   │   ├── project_manager.py  # 项目管理
│   │   └── task_queue.py       # 异步任务队列
│   └── services/
│       ├── llm_service.py      # LLM 服务（角色/场景/分镜提取）
│       ├── image_service.py    # 图片生成服务（统一接口）
│       ├── jiekouai_service.py # 接口AI 图片服务实现
│       ├── shot_design_service.py  # 分镜设计服务
│       └── video_service.py    # 视频生成服务（占位）
├── config/
│   └── default_config.yaml     # 默认配置模板
├── tests/                      # 测试脚本
├── requirements.txt
├── start.sh                    # 一键启动脚本
├── start_backend.sh            # 单独启动后端
└── start_frontend.sh           # 单独启动前端
```

---

## ✅ 已完成阶段

### Stage 1: 项目初始化 ✅
- [x] 项目创建 API
- [x] 剧本文件保存
- [x] 项目配置管理
- [x] 项目列表/详情/删除

### Stage 2: 剧本解析 ✅
- [x] LLM 角色提取（支持提示词编辑）
- [x] LLM 场景提取（支持提示词编辑）
- [x] 自动刷新机制（JavaScript 3秒轮询）
- [x] 解析结果展示（角色/场景卡片）

**配置位置**: 
- 提示词: `config/default_config.yaml` → `prompts.character_extraction` / `prompts.scene_extraction`
- 编辑入口: Streamlit 前端 → "⚙️ 编辑解析提示词"

### Stage 3: 参考图生成 ✅
- [x] 角色参考图生成（接口AI）
- [x] 场景参考图生成（接口AI）
- [x] 批量生成任务队列
- [x] 通过/拒绝/重新生成审核流程
- [x] 参考图提示词编辑

**技术要点**:
- 图片服务: `JiekouAIImageService`
- API 端点: `POST /api/projects/{id}/generate-references`
- 质量映射: `QUALITY_MAPPING = {"512x512": "1k", "1024x1024": "1k"}` (接口AI只支持 1k/2k/4k)

### Stage 4: 分镜设计 ✅
- [x] 自动分镜生成
- [x] 镜头类型识别（特写/近景/中景/全景）
- [x] 分镜描述生成
- [x] 图片提示词生成（正/负面）

**关键文件**: `src/services/shot_design_service.py`

### Stage 5: 首帧生成 ✅
- [x] 首帧图片生成 API
- [x] 参考图融合（角色+场景）
- [x] 批量生成队列
- [x] 对比视图（提示词 vs 实际图片）

---

## 🚧 待开发阶段

### Stage 6: 视频生成 ⚠️ 待实现

**需求**:
- 使用首帧图片生成短视频（5秒）
- 支持分镜串联生成完整动画
- 视频预览和下载

**技术方案**:
- 当前占位: `src/services/video_service.py` (空实现)
- 建议接入: 接口AI 的视频生成 API (如果有) 或其他视频生成服务
- 参考实现:
```python
class VideoService:
    async def generate_video(
        self,
        first_frame_path: Path,
        prompt: str,
        output_path: Path,
        duration: str = "5s"
    ) -> bool:
        # TODO: 实现视频生成逻辑
        pass
```

**API 待实现**:
- `POST /api/projects/{id}/generate-videos` - 批量生成视频
- `GET /api/projects/{id}/videos` - 获取视频列表
- `GET /api/projects/{id}/videos/{video_id}` - 获取视频详情

---

## 🔧 技术架构

### 后端 (FastAPI)
```
入口: src/main.py
端口: 8000
依赖: FastAPI, uvicorn, aiohttp, pydantic
```

**核心 API 列表**:
| 路径 | 方法 | 功能 |
|------|------|------|
| `/api/projects` | GET/POST | 项目列表/创建 |
| `/api/projects/{id}` | GET/DELETE | 项目详情/删除 |
| `/api/projects/{id}/parse` | POST | 开始剧本解析 |
| `/api/projects/{id}/generate-references` | POST | 生成参考图 |
| `/api/projects/{id}/design-shots` | POST | 生成分镜 |
| `/api/projects/{id}/characters` | GET | 获取角色列表 |
| `/api/projects/{id}/scenes` | GET | 获取场景列表 |
| `/api/projects/{id}/shots` | GET | 获取分镜列表 |
| `/api/queues/status` | GET | 队列状态 |

### 前端 (Streamlit)
```
入口: src/app.py
端口: 8501
页面: 项目管理、剧本解析、参考图、分镜设计、首帧生成
```

### 数据存储
```
~/animation_projects/{project_name}_{id}/
├── 00_script/script.md
├── 01_extraction/
│   ├── characters.json
│   └── scenes.json
├── 02_references/
│   ├── characters/{char_id}.png
│   └── scenes/{scene_id}.png
├── 03_keyframes/
└── project.json
```

---

## ⚙️ 配置说明

### 环境变量 (.env)
```bash
JIEKOUAI_API_KEY=sk_IfJc_v5r-SKXMrEaO...
JIEKOUAI_BASE_URL=https://api.jiekou.ai
JIEKOUAI_ENDPOINT=/v3/nano-banana-pro-light-t2i
OPENAI_API_KEY=sk-...
```

### 全局配置 (~/.animation_gen/config.yaml)
```yaml
llm:
  provider: "openai"
  model: "gemini-3-flash-preview"
  base_url: "https://api.jiekou.ai/openai"

image:
  provider: "jiekouai"
  resolution: "512x512"
  timeout: 120

video:
  provider: "sora2"  # 待实现
```

---

## 🐛 已知问题与解决方案

### 1. 图片生成质量参数
**问题**: 接口AI的 `quality` 参数只能是 `["1k", "2k", "4k"]`  
**解决**: 已修复 `QUALITY_MAPPING` 映射表  
**位置**: `src/services/jiekouai_service.py`

### 2. 字符串格式化冲突
**问题**: 剧本中的 `{` 导致 Python `format()` 报错  
**解决**: 使用 `[[SCRIPT]]` 双括号占位符  
**位置**: `config/default_config.yaml`, `src/services/llm_service.py`

### 3. 自动刷新机制
**实现**: JavaScript `setTimeout` 每3秒刷新  
**触发阶段**: extracting, generating_refs, designing_shots, generating_keyframes

---

## 🚀 启动方式

```bash
cd ~/.openclaw/workspace/animation-gen

# 方式1: 一键启动
./start.sh

# 方式2: 单独启动
./start_backend.sh   # FastAPI @ :8000
./start_frontend.sh  # Streamlit @ :8501
```

---

## 📝 开发建议

### 优先级1: Stage 6 视频生成
1. 调研接口AI是否支持视频生成
2. 如不支持，接入其他视频生成服务
3. 实现 `VideoService.generate_video()`
4. 添加视频生成API和前端页面

### 优先级2: 体验优化
1. 项目列表分页/搜索
2. 剧本导入（Word/PDF）
3. 批量操作优化
4. 错误重试机制完善

### 优先级3: 功能扩展
1. 多风格预设
2. 角色一致性保持
3. 分镜时间轴编辑
4. 视频合成与导出

---

## 🔗 关键代码片段

### 图片生成调用示例
```python
from src.services.jiekouai_service import JiekouAIImageService

service = JiekouAIImageService(api_key="...", base_url="...")
result = await service.generate_image(
    prompt="日系动漫风格，蓝发少女",
    width=512,
    height=512
)
if result["success"]:
    url = result["url"]  # 图片URL
```

### 添加新API端点
```python
@app.post("/api/projects/{project_id}/generate-videos")
async def generate_videos(project_id: str):
    project = project_manager.load_project(project_id)
    # 实现逻辑...
    return {"status": "generating"}
```

---

## 📞 联系信息

- **用户**: Mar
- **API提供商**: 接口AI (jiekou.ai)
- **LLM模型**: gemini-3-flash-preview
- **项目仓库**: /home/ventus/.openclaw/workspace/animation-gen/

---

**祝开发顺利！** 🎬
