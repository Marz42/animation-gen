# Bug 修复记录：分镜角色关联问题

## 问题描述

**现象**：首帧生成时传入了过多的角色参考图

**日志证据**：
```
🎬 生成首帧: shot=scene_001_shot_001, chars=6, scene=True
📊 参考图数量: 7 (场景: True, 人物: 6)
```

**影响**：
- 首帧生成质量下降（无关角色干扰）
- API 成本增加（更多参考图 = 更高成本）
- 生成速度变慢

---

## 根因分析

**问题代码**（`src/services/shot_design_service.py:86`）：
```python
characters=[c.character_id for c in characters]  # ❌ 使用了场景所有角色
```

**原因**：
1. 分镜设计时，将场景的**所有角色**都赋给了每个分镜
2. 无论分镜实际涉及几个角色，都关联全部角色
3. 首帧生成时，根据 `shot.characters` 传入所有角色参考图

**正确行为**：
- 分镜1（只有角色A出场）→ 只传入角色A的参考图
- 分镜2（角色A+B出场）→ 传入角色A和B的参考图
- 分镜3（只有角色B出场）→ 只传入角色B的参考图

---

## 修复方案

### 1. 更新分镜设计提示词

**文件**: `config/default_config.yaml`

**变更**：
- 添加 `character_ids` 字段要求
- 明确说明只包含实际出场的角色

```yaml
shot_design: |
  请设计3-5个分镜，每个分镜包含：
  - character_ids: 该分镜实际出场的角色ID列表（从场景角色列表中选择）
  
  重要规则：
  - character_ids 只包含实际在该分镜出场的角色ID
  
  请以JSON格式输出：
  {
    "shots": [{
      "type": "wide",
      "camera_movement": "static",
      "duration": "5s",
      "description": "...",
      "action": "...",
      "dialogue": null,
      "character_ids": ["char_001", "char_002"]  // 新增字段
    }]
  }
```

### 2. 更新分镜设计服务

**文件**: `src/services/shot_design_service.py`

**变更**：
- 解析 LLM 返回的 `character_ids` 字段
- 过滤验证角色ID（确保属于该场景）
- 添加日志输出

```python
for i, shot_data in enumerate(shots_data):
    # 获取该分镜涉及的角色ID
    shot_character_ids = shot_data.get("character_ids", [])
    
    # 过滤：只保留实际属于该场景的角色ID
    valid_character_ids = [
        cid for cid in shot_character_ids 
        if cid in scene_character_ids
    ]
    
    # 如果没有返回有效角色，默认使用该场景所有角色（兼容旧逻辑）
    if not valid_character_ids:
        valid_character_ids = [c.character_id for c in characters]
    
    shot = Shot(
        ...
        characters=valid_character_ids  # 使用过滤后的角色列表
    )
```

### 3. 更新前端提示词编辑界面

**文件**: `frontend/src/views/Shots.vue`

**变更**：
- Tooltip 添加 `character_ids` 字段说明
- Placeholder 显示完整的 JSON 格式示例

---

## 预期效果

### 修复前
```
场景：图书馆（6个角色）
├─ 分镜1：只有主角看书 → 传入6个角色参考图 ❌
├─ 分镜2：主角和配角对话 → 传入6个角色参考图 ❌
└─ 分镜3：全景空镜 → 传入6个角色参考图 ❌
```

### 修复后
```
场景：图书馆（6个角色）
├─ 分镜1：只有主角看书 → 传入1个角色参考图 ✅
├─ 分镜2：主角和配角对话 → 传入2个角色参考图 ✅
└─ 分镜3：全景空镜 → 传入0个角色参考图（只有场景）✅
```

---

## 兼容性考虑

### 向后兼容
- 如果 LLM 未返回 `character_ids`，使用场景所有角色作为默认值
- 如果返回的角色ID不属于该场景，自动过滤

### 日志输出
```
✅ 分镜 scene_001_shot_001 涉及角色: ['char_001']
✅ 分镜 scene_001_shot_002 涉及角色: ['char_001', 'char_002']
⚠️ 分镜 scene_001_shot_003 未返回有效character_ids，使用场景所有角色
```

---

## 测试建议

1. **重新生成分镜**
   - 删除现有分镜
   - 点击"自动生成分镜"
   - 检查分镜的 `characters` 字段

2. **验证首帧生成**
   - 查看日志中的 `chars=X` 数量
   - 确认与分镜实际角色数一致

3. **边界情况**
   - 空场景（无角色）
   - 单角色场景
   - 多角色但分镜只涉及部分角色

---

## 相关文件

| 文件 | 变更 |
|------|------|
| `config/default_config.yaml` | 更新 shot_design 提示词模板 |
| `src/services/shot_design_service.py` | 解析 character_ids 字段 |
| `frontend/src/views/Shots.vue` | 更新占位符说明 |

---

## 修复日期

2026-02-12
