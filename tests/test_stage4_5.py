#!/usr/bin/env python3
"""
测试分镜设计和首帧生成功能
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import asyncio
from pathlib import Path

print("=" * 60)
print("🧪 测试分镜设计 & 首帧生成功能")
print("=" * 60)

# 测试1: ShotDesignService
print("\n📋 测试1: ShotDesignService")
from src.services.shot_design_service import ShotDesignService
from src.models.schemas import Scene, Character, Shot

service = ShotDesignService()
print("✅ ShotDesignService 创建成功")

# 测试2: 创建测试场景和角色
print("\n📋 测试2: 创建测试数据")
scene = Scene(
    scene_id="scene_001",
    name="教室",
    description="阳光明媚的教室，学生们在早读",
    location="学校",
    time="早晨"
)

char1 = Character(
    character_id="char_001",
    name="小明",
    description="黑短发，戴眼镜",
    personality="内向"
)

char2 = Character(
    character_id="char_002",
    name="小红",
    description="长马尾，笑容甜美",
    personality="活泼"
)

print(f"✅ 场景: {scene.name}")
print(f"✅ 角色1: {char1.name}")
print(f"✅ 角色2: {char2.name}")

# 测试3: 测试分镜设计（需要API，跳过实际调用）
print("\n📋 测试3: 分镜设计提示词构建")
script_segment = """
小明走进教室，看到小红正在看书。
小明走过去打招呼，两人开始聊天。
"""

# 只测试内部方法
default_shots = service._create_default_shots(scene, [char1, char2])
print(f"✅ 默认分镜生成: {len(default_shots)} 个")
for i, shot in enumerate(default_shots):
    print(f"   分镜{i+1}: {shot['description'][:30]}...")

# 测试4: 测试首帧路径生成
print("\n📋 测试4: 首帧路径生成")
test_project_path = Path("/tmp/test_project_12345")
test_project_path.mkdir(exist_ok=True)

shot = Shot(
    shot_id="scene_001_shot_001",
    scene_id="scene_001",
    sequence=1,
    duration="5s",
    description="小明走进教室",
    characters=["char_001"]
)

batch_id = shot.create_batch()
output_path = test_project_path / "03_keyframes" / f"{shot.shot_id}_{batch_id}.png"
print(f"✅ 首帧路径: {output_path}")

# 测试5: 版本管理
print("\n📋 测试5: Batch版本管理")
shot.create_batch()  # batch_002
shot.create_batch()  # batch_003
print(f"✅ Batch数量: {len(shot.batches)}")
print(f"✅ 当前Batch: {shot.current_batch_id}")

# 测试6: 统计信息
print("\n📋 测试6: 成本预估")
from src.services.video_service import VideoService

video_service = VideoService()
estimate = video_service.estimate_cost(10, VideoDuration.SECONDS_5)
print(f"✅ 成本预估:")
print(f"   分镜数: {estimate['shot_count']}")
print(f"   总秒数: {estimate['total_seconds']}")
print(f"   预估费用: ${estimate['estimated_cost_usd']}")

# 清理
import shutil
shutil.rmtree(test_project_path, ignore_errors=True)

print("\n" + "=" * 60)
print("✅ 分镜设计 & 首帧生成功能测试通过！")
print("=" * 60)
