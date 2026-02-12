# 更新日志 (Changelog)

## [Unreleased] - 2026-02-12

### 🚨 紧急修复

#### 代码级 Bug 修复
- ✅ 修复 `src/main.py` 缺失 `import random` - 导致视频页重新生成首帧失败
- ✅ **修复硬编码API密钥** - 使用 `settings.jiekouai_api_key` 从环境变量读取
- ✅ **修复错误类名** - `InterfaceAIService` → `ImageService`（通用接口）
- ✅ **修复分镜角色关联** - 每个分镜只关联实际出场的角色（而非场景所有角色）
- ✅ **修复首帧生成超时** - 图片压缩改为异步执行，添加超时保护
- ✅ **修复配置保存失效** - 统一使用JSON格式保存，与加载优先级一致

#### 占位符变量统一
- ✅ 统一使用 `[[VARIABLE_NAME]]` 双括号格式
- ✅ 更新所有提示词模板
- ✅ 前端编辑界面添加详细占位符说明

### 🔥 新增功能：无人值守批量生成流水线

#### BatchPipelineService - 批量生成流水线服务
- ✅ 自动处理首帧生成 → 视频生成的依赖关系
- ✅ 支持失败自动重试（指数退避策略）
- ✅ 支持顺序或并行执行模式（可配置最大并行数）
- ✅ 任务状态持久化（服务重启后可恢复未完成作业）
- ✅ 批量任务进度实时监控

#### 新增 API 端点
```
POST /api/projects/{id}/batch-jobs       # 创建批量作业
GET  /api/projects/{id}/batch-jobs       # 列出名业作业
GET  /api/projects/{id}/batch-jobs/{jid} # 获取作业详情
POST /api/projects/{id}/batch-jobs/{jid}/pause   # 暂停作业
POST /api/projects/{id}/batch-jobs/{jid}/resume  # 恢复作业
POST /api/projects/{id}/batch-jobs/{jid}/cancel  # 取消作业
```

#### 批量作业功能特性
- **自动依赖管理**: 自动等待首帧完成后再提交视频任务
- **智能重试**: 首帧和视频分别配置最大重试次数（默认3次）
- **指数退避**: 失败重试间隔随次数增加（2^n 秒）
- **持久化存储**: 作业状态保存到 `~/.animation_gen/batch_jobs/`
- **服务恢复**: 启动时自动恢复未完成的批量作业

### 修复 (基础功能)

#### 视频生成参数修复
- ✅ 修复 duration 参数: 从 [5s, 10s] 改为 API 要求的 [4s, 8s, 12s]
- ✅ 修复 size 参数: 从 [720x1280, 1280x720] 改为 API 要求的 [720p, 1080p]
- ✅ 更新 VideoDuration 枚举: SECONDS_4, SECONDS_8, SECONDS_12
- ✅ 更新 VideoResolution 枚举: P720, P1080
- ✅ 更新前端选择器和默认值
- ✅ 更新 mock provider 能力声明

#### 视频状态自动轮询机制
- ✅ 新增 VideoMonitorService 后台服务
- ✅ 自动轮询 submitted/processing 状态的视频
- ✅ 完成时自动下载视频到项目目录
- ✅ 在应用启动时自动启动，关闭时自动停止

#### 多提供商参数适配系统
- ✅ 新增 ProviderConfig 配置管理系统
- ✅ 支持不同提供商的参数映射 (duration/resolution)
- ✅ 预定义配置: 接口AI Sora-2 (4s/8s/12s), 可灵 (5s/10s), Runway (4s/10s)
- ✅ 前端动态显示提供商支持的参数选项
- ✅ API 端点 `/api/video-provider` 返回详细配置信息

### ✨ 功能增强

#### 视频Prompt批量重新生成
- ✅ **全选操作**: 一键选择所有分镜/有Prompt的/无Prompt的
- ✅ **重新生成按钮**: 为已选分镜重新生成Prompt（覆盖已有）
- ✅ **智能过滤**: "生成"按钮只处理没有Prompt的分镜
- ✅ **批量统计**: 显示成功/失败数量

#### 首帧生成性能优化
- ✅ **异步图片压缩**: 使用线程池避免阻塞事件循环
- ✅ **超时保护**: 图片下载60秒超时，HTTP请求180秒超时
- ✅ **性能监控**: 详细耗时日志，便于排查问题

### 📝 新增文档
- ✅ `docs/BUGFIX_CHARACTER_IDS.md` - 分镜角色关联Bug修复说明
- ✅ `docs/BUGFIX_PROMPT_TEMPLATE_SAVE.md` - 提示词模板保存Bug修复说明
- ✅ `docs/CHARACTER_FILTER_EXPLANATION.md` - 角色过滤问题详细解释
- ✅ `docs/KEYFRAME_GENERATION_ANALYSIS.md` - 首帧生成逻辑深度分析
- ✅ `docs/KEYFRAME_TIMEOUT_TROUBLESHOOTING.md` - 首帧生成超时排查指南
- ✅ `docs/PROMPT_PLACEHOLDERS.md` - 占位符变量参考文档
- ✅ `docs/VIDEO_PROMPT_BATCH_REGENERATE.md` - 视频Prompt批量重生成说明

### 🔧 新增工具
- ✅ `fix_shot_characters.py` - 修复已有分镜的角色关联问题

### 新增功能

#### API提供商管理
- ✅ 内置API提供商支持（builtin_llm, builtin_image, builtin_video）
- ✅ API提供商配置导入/导出（CURL命令解析）
- ✅ 提供商验证功能（连通性测试）
- ✅ 默认提供商设置
- ✅ 提供商状态显示（内置/用户定义）

#### 视频生成页面增强
- ✅ 显示首帧图片缩略图
- ✅ 分镜选择功能（单选/多选）
- ✅ 批量生成视频Prompt
- ✅ 批量生成视频
- ✅ 首帧Prompt编辑和重新生成（从视频页面）
- ✅ 视频Prompt自动生成（基于剧本+首帧Prompt）
- ✅ 视频Prompt手动编辑
- ✅ 视频Prompt模板自定义

#### 系统优化
- ✅ 成本预估API修复（添加total_seconds字段）
- ✅ 场景参考图生成使用LLM翻译（中文→英文）
- ✅ CURL导入支持更多格式（--url, --request, --header, --data）
- ✅ 内置提供商验证支持（不保存到配置文件）

### API变更

#### 新增端点
```
GET    /api/providers                     # 获取所有提供商（包含内置）
POST   /api/providers                     # 创建提供商
PUT    /api/providers/{id}                # 更新提供商
DELETE /api/providers/{id}                # 删除提供商
POST   /api/providers/{id}/verify         # 验证提供商
POST   /api/providers/{id}/set-default    # 设为默认
POST   /api/providers/parse-curl          # 解析CURL命令
GET    /api/providers/default/{type}      # 获取默认提供商
POST   /api/config/export                 # 导出配置
POST   /api/config/import                 # 导入配置
POST   /api/projects/{id}/shots/{id}/generate-video-prompt    # 生成视频Prompt
GET    /api/projects/{id}/shots/{id}/video-prompt              # 获取视频Prompt
POST   /api/projects/{id}/shots/{id}/video-prompt              # 保存视频Prompt
POST   /api/projects/{id}/shots/{id}/regenerate-keyframe-from-video  # 从视频页重新生成首帧
```

### 修复问题
1. **成本预估404** - 修复内置提供商的验证端点
2. **成本预估字段缺失** - 添加total_seconds字段到视频服务estimate_cost
3. **场景参考图中文问题** - 使用LLM将中文描述翻译为英文Prompt
4. **CURL解析** - 支持更多CURL命令格式

---

## [v1.0.0] - 2026-02-09

### 首次发布 🎉

完整的动画生成系统，支持从剧本到视频的全流程自动化。

### 新增功能

#### 项目管理
- ✅ 项目创建、列表、删除
- ✅ 剧本上传和存储
- ✅ 风格描述配置

#### 剧本解析
- ✅ 自动角色提取（名称、外貌、性格）
- ✅ 自动场景提取（地点、时间、描述）
- ✅ 人工审核机制
- ✅ 可编辑的解析提示词

#### 参考图生成
- ✅ 角色参考图生成
- ✅ 场景参考图生成
- ✅ 版本管理（支持重新生成）
- ✅ Prompt编辑功能
- ✅ 高级选项（Seed、Prompt修改）

#### 分镜设计
- ✅ 基于LLM的自动分镜生成
- ✅ 分镜属性：镜头类型、运动、时长、描述、动作、对话
- ✅ 单个分镜编辑和重新设计
- ✅ 全局分镜设计提示词编辑
- ✅ 展开行查看详情

#### 首帧生成
- ✅ 多图i2i支持（场景+角色参考）
- ✅ 自动图片压缩（<300KB）
- ✅ 成本预估功能
- ✅ 单个首帧编辑和重新生成
- ✅ 审核机制
- ✅ 全局图片/视频提示词编辑

#### 视频生成
- ✅ 多提供商架构（接口AI、Mock）
- ✅ 异步任务队列
- ✅ 自动视频下载
- ✅ 状态查询
- ✅ 提供商切换API

#### 系统功能
- ✅ 任务队列状态监控
- ✅ 全局提示词配置管理
- ✅ 环境变量配置
- ✅ 自动错误恢复
- ✅ 僵尸任务检测

### 技术实现

#### 后端
- FastAPI框架
- Pydantic数据验证
- 异步任务队列（llm/image/video）
- 多提供商视频服务架构
- 图片压缩优化

#### 前端
- Vue 3 + Element Plus
- Pinia状态管理
- 实时状态刷新
- 响应式布局

#### AI服务集成
- 接口AI LLM（OpenAI兼容）
- 接口AI图片生成（t2i/i2i）
- 接口AI视频生成（Sora 2 Img2Video）

### 修复问题

1. **yaml模块导入** - 添加`import yaml`到main.py
2. **VideoDuration枚举** - 扩展支持2s-15s所有时长
3. **Session泄漏** - ImageService.close()同时关闭jiekouai_service
4. **配置加载** - 处理空yaml文件的情况
5. **API Key配置** - 更新.env使用正确的密钥

### 已知问题

1. 视频状态查询端点不稳定
2. 不同视频提供商时长限制不统一
3. 缺少项目导出功能（视频合并）

### 提交记录

```
e5e8052 Add prompt editing for shot_design in Shots.vue and image/video prompts in Keyframes.vue
7391d71 Fix VideoDuration to support all durations (2s-15s), update shot_design prompt, add prompt editing API for all stages
5115cad Fix: Add VideoDuration.SECONDS_3 support and fix session leak in ImageService.close()
2759bc8 Fix config loading for empty yaml files
e35b18e Fix yaml import and update scene/character extraction prompts
5f39000 Fix Jiekouai video status check endpoint - GET /v3/async/task-result?task_id={id}
c48e2c0 Update Jiekouai video provider - status check endpoint temporarily unavailable, returns submitted status
5b62aad Fix Jiekouai video provider with correct async endpoint /v3/async/sora-2-img2video
46cfd8e Add MockVideoProvider for testing, fix provider type handling
8458fea Implement multi-provider video service architecture with Jiekouai Sora 2 support
1bae863 Update Videos.vue with video player and status display
dfe789f Complete prompt editing and regeneration features for References, Shots, and Keyframes
5a9317d Add backend APIs and frontend API methods for prompt editing and regeneration
a788748 Fix: Add missing manual_override field to Shot model
```

---

## 开发里程碑

- **Day 1** (2026-02-08): 项目启动，基础架构搭建
- **Day 2** (2026-02-08): 核心功能实现（剧本解析、参考图、分镜）
- **Day 3** (2026-02-08): 首帧生成、视频生成、Bug修复
- **Day 4** (2026-02-09): 提示词编辑、文档完善、首次发布

---

## 版本规划

### v1.1.0 (计划中)
- 视频状态查询端点修复
- 批量操作优化
- UI/UX改进

### v1.2.0 (计划中)
- 支持更多视频提供商
- 提示词模板库
- 角色一致性优化

### v2.0.0 (长期)
- 多用户支持
- 云存储集成
- 协作功能
