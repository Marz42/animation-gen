# 更新日志 (Changelog)

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
