# Bug 修复：视频Prompt模板保存失效

## 问题描述

在视频生成页面编辑视频Prompt模板后，点击保存按钮显示"模板已保存"，但刷新页面或重新打开对话框后，修改的内容丢失。

## 根因分析

**问题定位**：后端配置保存和加载的格式不一致

**详细原因**：
1. `Config.load_global()` 方法**优先加载 JSON 格式**的配置文件（如果存在）
2. `update_prompts` API 端点却将配置保存到 **YAML 格式**的文件
3. 当 `~/.animation_gen/config.json` 文件存在时，保存到 YAML 的修改不会被加载

**代码对比**：

```python
# load_global() - 优先加载 JSON
if json_path.exists():  # ← 优先检查 JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return cls(**data)

# update_prompts() - 保存到 YAML  
config_path = Path.home() / ".animation_gen" / "config.yaml"
with open(config_path, 'w', encoding='utf-8') as f:  # ← 保存到 YAML
    yaml.dump(config.model_dump(), f, ...)
```

## 修复方案

修改 `update_prompts` 函数，使用 `config.save_global_config(use_json=True)` 方法，确保保存到 JSON 格式，与加载优先级一致。

**修复前**：
```python
@app.put("/api/config/prompts")
async def update_prompts(request: UpdatePromptsRequest):
    """更新提示词配置"""
    config = Config.load_global()
    
    if request.video_prompt is not None:
        config.prompts["video_prompt"] = request.video_prompt
    
    # 保存到YAML文件 ❌
    config_path = Path.home() / ".animation_gen" / "config.yaml"
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config.model_dump(), f, ...)
    
    return {"status": "updated"}
```

**修复后**：
```python
@app.put("/api/config/prompts")
async def update_prompts(request: UpdatePromptsRequest):
    """更新提示词配置"""
    config = Config.load_global()
    
    if request.video_prompt is not None:
        config.prompts["video_prompt"] = request.video_prompt
    
    # 保存到JSON文件 ✅（与load_global优先级一致）
    config.save_global_config(use_json=True)
    
    return {"status": "updated"}
```

## 影响范围

此修复影响所有通过 `/api/config/prompts` PUT 接口保存的提示词配置：
- `character_extraction`
- `scene_extraction`
- `character_ref_prompt`
- `scene_ref_prompt`
- `shot_design`
- `image_prompt`
- `video_prompt`

## 验证修复

1. 编辑视频Prompt模板
2. 点击保存
3. 刷新页面
4. 重新打开编辑对话框
5. **预期结果**：显示刚才保存的内容

## 后续建议

为避免类似问题，建议统一使用一种配置格式：

### 方案1：统一使用 JSON（推荐）
- 加载和保存都优先使用 JSON
- JSON 解析更快，且与 Python 字典兼容性好

### 方案2：删除 JSON 文件
- 如果项目中已存在 `config.json`，手动删除
- 之后只使用 YAML 格式

### 方案3：同步保存两种格式
```python
def save_global_config(self):
    """保存到两种格式，确保兼容"""
    yaml_path, json_path = self.get_global_config_paths()
    data = self.model_dump()
    
    # 保存JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 保存YAML
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## 修复日期

2026-02-12
