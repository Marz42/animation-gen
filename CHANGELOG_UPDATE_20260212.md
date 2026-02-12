# 更新日志 - 2026-02-12 缺陷修复与功能增强

## 概述
本次更新集中修复了多个关键缺陷，并增强了系统稳定性和用户体验。

---

## 🔴 严重缺陷修复

### 1. 首帧生成超时问题

**问题**: 首帧生成过程中部分图片出现超时

**根因**: 
- 图片压缩是同步操作，阻塞 asyncio 事件循环
- 多图i2i生成时多张图片的压缩耗时累积

**修复**:
```python
# src/services/jiekouai_service.py
# 将图片压缩改为异步执行（使用线程池）
async def _compress_image_to_base64(self, local_path, max_size_kb):
    def _do_compress(path_str, max_kb):
        # 实际的压缩逻辑
        ...
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, _do_compress, ...)
```

**其他改进**:
- 图片下载添加60秒超时保护
- HTTP请求超时从120秒增加到180秒
- 添加详细的性能监控日志

---

### 2. 分镜角色关联错误（严重逻辑缺陷）

**问题**: 首帧生成时传入过多角色参考图（chars=6，而实际只需要1-2个）

**根因**: `shot_design_service.py` 第86行将场景的**所有角色**赋给了每个分镜

**修复**:
```python
# 修复前：所有分镜都关联场景全部角色
characters=[c.character_id for c in characters]

# 修复后：根据 character_ids 只关联实际出场的角色
valid_character_ids = [cid for cid in shot_character_ids if cid in scene_character_ids]
```

**配置更新**:
- 更新 `shot_design` 提示词模板，要求 LLM 返回 `character_ids` 字段
- 前端添加占位符说明

**注意**: 已有项目需要重新生成分镜才能生效

---

### 3. 视频Prompt模板保存失效

**问题**: 编辑视频Prompt模板后保存，刷新页面后修改丢失

**根因**: 后端保存和加载的配置格式不一致
- `Config.load_global()` **优先加载 JSON** 格式的配置文件
- `update_prompts` API 却将配置保存到 **YAML** 格式

**修复**:
```python
# src/main.py - update_prompts 函数
# 修复前：保存到 YAML
config_path = Path.home() / ".animation_gen" / "config.yaml"
with open(config_path, 'w', encoding='utf-8') as f:
    yaml.dump(config.model_dump(), f, ...)

# 修复后：保存到 JSON（与加载优先级一致）
config.save_global_config(use_json=True)
```

---

### 4. 硬编码API密钥安全风险

**问题**: `src/main.py` 中硬编码了API密钥

**修复**: 使用 `settings.jiekouai_api_key` 从环境变量读取

---

### 5. 错误类名引用

**问题**: `InterfaceAIService` 类不存在，正确类名是 `JiekouAIImageService`

**修复**: 统一使用通用的 `ImageService` 接口

---

## ✨ 功能增强

### 1. 视频Prompt批量重新生成

**新增功能**:
- **全选操作**: 一键选择所有分镜/有Prompt的/无Prompt的
- **重新生成按钮**: 为已选分镜重新生成视频Prompt（覆盖已有）
- **智能过滤**: "生成"按钮只处理没有Prompt的分镜

**界面更新**:
```
全选操作栏（未选择时）:
[全选 (10个)] [选择有Prompt的 (5个)] [选择无Prompt的 (5个)]

批量操作栏（选择后）:
[生成视频Prompt] [重新生成] [生成视频] [批量下载] [取消]
```

### 2. 占位符变量统一

**统一格式**: 所有占位符使用 `[[VARIABLE_NAME]]` 双括号格式

**受影响文件**:
- `config/default_config.yaml`: 更新所有提示词模板
- `src/services/shot_design_service.py`: 更新占位符替换逻辑
- `frontend/src/views/Shots.vue`: 添加详细占位符说明
- `frontend/src/views/Keyframes.vue`: 添加占位符说明

**新增文档**: `docs/PROMPT_PLACEHOLDERS.md`

---

## 📁 新增文档

| 文档 | 说明 |
|------|------|
| `docs/BUGFIX_CHARACTER_IDS.md` | 分镜角色关联Bug修复说明 |
| `docs/BUGFIX_PROMPT_TEMPLATE_SAVE.md` | 提示词模板保存Bug修复说明 |
| `docs/CHARACTER_FILTER_EXPLANATION.md` | 角色过滤问题详细解释 |
| `docs/KEYFRAME_GENERATION_ANALYSIS.md` | 首帧生成逻辑深度分析 |
| `docs/KEYFRAME_TIMEOUT_TROUBLESHOOTING.md` | 首帧生成超时排查指南 |
| `docs/PROMPT_PLACEHOLDERS.md` | 占位符变量参考文档 |
| `docs/VIDEO_PROMPT_BATCH_REGENERATE.md` | 视频Prompt批量重生成说明 |

---

## 🔧 新增工具脚本

| 脚本 | 用途 |
|------|------|
| `fix_shot_characters.py` | 修复已有分镜的角色关联问题 |

---

## 📊 改动统计

### 修改文件
- `config/default_config.yaml` - 提示词模板格式统一
- `frontend/src/views/Keyframes.vue` - 添加占位符说明、性能监控
- `frontend/src/views/Shots.vue` - 添加占位符说明、character_ids说明
- `frontend/src/views/Videos.vue` - 视频Prompt批量重生成功能
- `src/main.py` - API密钥修复、配置保存修复
- `src/services/jiekouai_service.py` - 异步压缩、超时优化
- `src/services/shot_design_service.py` - 角色过滤修复

### 新增文件
- 7个文档文件
- 1个修复脚本

---

## ⚠️ 升级注意事项

1. **重新生成分镜**: 已有项目需要重新生成分镜才能应用角色过滤修复
2. **重启服务**: 所有后端代码修改需要重启服务才能生效
3. **配置备份**: 建议备份 `~/.animation_gen/config.yaml` 和 `config.json`

---

## 🙏 致谢

感谢用户的详细反馈和日志提供，帮助我们定位了多个关键问题。

---

**提交日期**: 2026-02-12  
**提交者**: Kimi Code  
**版本**: v1.0.1 (Hotfix Release)
