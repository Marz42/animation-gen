# 动画生成系统 (Animation Gen)

## 项目概述

**动画生成系统**是一个全流程的自动化动画制作工作流系统，支持从剧本到视频的完整流程：

```
剧本 → 角色/场景解析 → 参考图生成 → 分镜设计 → 首帧生成 → 视频生成
```

## 技术栈

- **前端**: Vue 3 + Element Plus + Pinia
- **后端**: Python + FastAPI + Pydantic
- **AI服务**: 
  - LLM: 接口AI (兼容OpenAI格式)
  - 图片生成: 接口AI nano-banana-pro-light-t2i/i2i
  - 视频生成: 接口AI Sora 2 Img2Video
- **任务队列**: 基于asyncio的异步队列
- **存储**: 本地文件系统

## 核心功能

### 1. 项目管理
- 创建/删除/查看项目
- 项目配置管理（分辨率、帧率、时长等）

### 2. 剧本解析
- 自动提取角色信息（名称、外貌、性格）
- 自动提取场景信息（地点、时间、描述）
- 支持人工审核和编辑

### 3. 参考图生成
- 角色参考图（版本管理、支持重新生成）
- 场景参考图（版本管理、支持重新生成）
- 支持Prompt编辑和高级选项

### 4. 分镜设计
- 基于LLM自动生成
- 支持手动编辑Prompt（shot_design）
- 支持单个分镜重新设计
- 分镜属性：镜头类型、运动、时长、描述、动作、对话

### 5. 首帧生成
- 多图i2i支持（场景+角色参考）
- 自动图片压缩（<300KB）
- 支持Prompt编辑和重新生成
- 支持手动审核

### 6. 视频生成
- 异步任务队列
- 多提供商支持（接口AI、Mock模式）
- 自动视频下载
- 状态轮询/回调支持
- **首帧图片预览**
- **视频Prompt自动生成（基于剧本+首帧）**
- **分镜多选批量生成**
- **首帧Prompt编辑和重新生成**

### 7. API提供商管理
- 内置API提供商（LLM/图片/视频）
- 自定义提供商配置（CURL导入）
- 提供商验证和状态监控
- 默认提供商设置

## 项目结构

```
animation-gen/
├── frontend/                    # Vue 3前端
│   ├── src/
│   │   ├── api/                # API客户端
│   │   ├── stores/             # Pinia状态管理
│   │   ├── views/              # 页面组件
│   │   │   ├── Projects.vue    # 项目管理
│   │   │   ├── Script.vue      # 剧本解析
│   │   │   ├── References.vue  # 参考图生成
│   │   │   ├── Shots.vue       # 分镜设计
│   │   │   ├── Keyframes.vue   # 首帧生成
│   │   │   └── Videos.vue      # 视频生成
│   │   └── App.vue
│   └── package.json
├── src/                         # Python后端
│   ├── main.py                 # FastAPI入口
│   ├── core/                   # 核心模块
│   │   ├── config.py          # 配置管理
│   │   ├── project_manager.py # 项目管理
│   │   └── task_queue.py      # 任务队列
│   ├── models/                 # 数据模型
│   │   └── schemas.py         # Pydantic模型
│   └── services/              # 服务层
│       ├── llm_service.py     # LLM服务
│       ├── image_service.py   # 图片生成服务
│       ├── video/             # 视频服务
│       │   ├── __init__.py
│       │   └── providers/     # 提供商实现
│       │       ├── base.py
│       │       ├── jiekouai.py
│       │       └── mock.py
│       ├── jiekouai_service.py
│       └── shot_design_service.py
├── config/
│   └── default_config.yaml    # 默认配置
├── docs/                      # 文档
├── start_backend.sh          # 启动后端脚本
└── start_frontend.sh         # 启动前端脚本
```

## API端点

### 项目API
```
POST   /api/projects                 # 创建项目
GET    /api/projects                 # 列表
GET    /api/projects/{id}            # 详情
DELETE /api/projects/{id}            # 删除
```

### 剧本解析API
```
POST   /api/projects/{id}/parse                      # 解析剧本
GET    /api/projects/{id}/characters                 # 角色列表
GET    /api/projects/{id}/scenes                     # 场景列表
POST   /api/projects/{id}/characters/{id}/approve    # 审核角色
POST   /api/projects/{id}/scenes/{id}/approve        # 审核场景
```

### 参考图API
```
POST   /api/projects/{id}/generate-references        # 生成所有参考图
POST   /api/projects/{id}/characters/{id}/regenerate # 重新生成角色
POST   /api/projects/{id}/scenes/{id}/regenerate     # 重新生成场景
```

### 分镜API
```
POST   /api/projects/{id}/design-shots               # 自动生成分镜
GET    /api/projects/{id}/shots                      # 分镜列表
GET    /api/projects/{id}/shots/{id}                 # 分镜详情
PUT    /api/projects/{id}/shots/{id}                 # 更新分镜
POST   /api/projects/{id}/shots/{id}/edit-prompt     # 编辑Prompt
POST   /api/projects/{id}/shots/{id}/redesign        # 重新设计分镜
```

### 首帧API
```
GET    /api/projects/{id}/cost-estimate              # 成本预估
POST   /api/projects/{id}/generate-keyframes         # 生成所有首帧
POST   /api/projects/{id}/shots/{id}/approve-keyframe    # 审核首帧
POST   /api/projects/{id}/shots/{id}/regenerate-keyframe # 重新生成首帧
```

### 视频API
```
POST   /api/projects/{id}/generate-videos            # 生成视频
GET    /api/projects/{id}/videos                     # 视频列表（包含首帧路径）
POST   /api/projects/{id}/videos/{id}/check-status   # 检查状态
POST   /api/projects/{id}/shots/{id}/generate-video-prompt    # 生成视频Prompt
GET    /api/projects/{id}/shots/{id}/video-prompt              # 获取视频Prompt
POST   /api/projects/{id}/shots/{id}/video-prompt              # 保存视频Prompt
POST   /api/projects/{id}/shots/{id}/regenerate-keyframe-from-video  # 从视频页重新生成首帧
```

### API提供商API
```
GET    /api/providers                     # 获取所有提供商（包含内置）
POST   /api/providers                     # 创建提供商
PUT    /api/providers/{id}                # 更新提供商
DELETE /api/providers/{id}                # 删除提供商
POST   /api/providers/{id}/verify         # 验证提供商连通性
POST   /api/providers/{id}/set-default    # 设为默认提供商
POST   /api/providers/parse-curl          # 解析CURL命令导入配置
GET    /api/providers/default/{type}      # 获取默认提供商
```

### 配置API
```
GET    /api/config/prompts           # 获取提示词配置
PUT    /api/config/prompts           # 更新提示词配置
POST   /api/config/export            # 导出配置
POST   /api/config/import            # 导入配置
```


```
GET    /api/video-provider           # 获取当前视频提供商
POST   /api/video-provider           # 切换视频提供商
```

### 队列状态API
```
GET    /api/queues/status            # 获取队列状态
```

## 配置说明

### 环境变量 (.env)
```bash
# LLM API
OPENAI_API_KEY=sk_xxx
OPENAI_BASE_URL=https://api.jiekou.ai/openai

# 图片生成API
JIEKOUAI_API_KEY=sk_xxx
JIEKOUAI_BASE_URL=https://api.jiekou.ai

# 视频生成提供商 (jiekouai/mock)
VIDEO_PROVIDER=jiekouai

# 服务器配置
PUBLIC_URL=http://localhost:8000
API_PORT=8000
```

### 全局配置 (~/.animation_gen/config.yaml)
包含LLM、图片、视频的默认参数和提示词模板。

## 启动指南

### 1. 安装依赖
```bash
# 后端
cd animation-gen
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入API密钥
```

### 3. 启动服务
```bash
# 启动后端
./start_backend.sh

# 启动前端 (新终端)
./start_frontend.sh
```

### 4. 访问系统
- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 使用流程

### 完整工作流程

1. **创建项目**
   - 输入项目名称
   - 粘贴剧本内容
   - 设置风格描述

2. **剧本解析**
   - 点击"解析剧本"
   - 查看提取的角色和场景
   - 审核并编辑

3. **参考图生成**
   - 点击"生成所有参考图"
   - 查看生成的角色和场景图片
   - 如需调整，可编辑Prompt重新生成

4. **分镜设计**
   - 点击"自动生成分镜"
   - 查看生成的分镜列表
   - 可编辑单个分镜的Prompt或重新设计
   - 可编辑分镜设计提示词（全局）

5. **首帧生成**
   - 审核分镜后点击"生成所有首帧"
   - 系统使用多图i2i（场景+角色参考）
   - 查看生成结果，可重新生成
   - 可编辑图片/视频提示词（全局）

6. **视频生成**
   - 首帧审核通过后进入视频生成页面
   - **显示首帧图片预览**，方便确认内容
   - **自动生成视频Prompt**：系统调用LLM基于剧本场景+首帧Prompt生成
   - 可编辑视频Prompt模板，自定义生成规则
   - **多选分镜**：勾选需要生成的分镜（单条或批量）
   - 支持编辑首帧Prompt并重新生成（会重置视频状态）
   - 设置视频参数（时长、尺寸、水印）
   - 查看视频生成进度，自动下载到项目目录

## 技术要点

### 1. 多图i2i实现
```python
# 图片压缩策略
quality = 85 → 20 (逐步降低)
ratio = 0.9 → 0.3 (逐步缩小)
最终保底: 512x512, quality=60
```

### 2. 视频提供商架构
- 抽象基类 `BaseVideoProvider`
- 支持多提供商切换
- 配置驱动，易于扩展

### 3. 任务队列
- 独立队列：llm、image、video
- 并发控制
- 自动重试和失败恢复
- 僵尸任务检测

### 4. 提示词管理
- 全局配置存储
- 支持热更新
- 各阶段独立配置
- 视频Prompt自动生成（基于模板）

### 5. 内置API提供商
- 从环境变量读取API密钥
- 动态生成配置（不写入配置文件）
- 支持验证但不保存状态
- 用户自定义提供商可覆盖

### 6. 视频Prompt生成
基于模板调用LLM生成：
```
输入：剧本场景描述 + 首帧图片Prompt + 角色信息
输出：视频描述（动作、相机运动、光影）
```
支持占位符：[[SCENE_DESCRIPTION]], [[IMAGE_PROMPT]], [[CHARACTERS]], [[ACTION]], [[CAMERA_MOVEMENT]], [[DURATION]]

## 已知问题

1. **视频状态查询**
   - 接口AI视频状态查询端点不稳定
   - 临时解决方案：返回submitted状态，需手动刷新

2. **时长限制**
   - 不同视频提供商支持不同时长
   - 当前统一使用4s/5s/6s/8s/10s

## 未来计划

### 短期 (v1.1)
- [x] 批量操作优化 ✅
- [x] API提供商管理 ✅
- [ ] 视频状态查询端点修复
- [ ] UI/UX改进（加载状态、错误提示）
- [ ] 项目导出功能（视频合并）

### 中期 (v1.2)
- [ ] 支持更多视频提供商（可灵、Runway）
- [ ] 提示词模板库
- [ ] 角色一致性优化
- [ ] 预览功能增强

### 长期 (v2.0)
- [ ] Webhook回调完善
- [ ] 多用户支持
- [ ] 云存储集成
- [ ] 协作功能

## 开发团队

- 项目启动：2026-02-08
- 首次开发完成：2026-02-09

## 许可证

MIT License

---

**注意**: 本项目为首次开发版本，API和配置可能会有变动。请参考最新文档。
