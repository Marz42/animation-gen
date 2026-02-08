#!/usr/bin/env python3
"""
项目测试脚本
验证核心功能是否正常工作
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncio
from src.core.config import Config, settings
from src.core.project_manager import ProjectManager
from src.core.task_queue import AsyncTaskQueue, TaskPriority
from src.models.schemas import Project, Character, Scene


def test_config():
    """测试配置加载"""
    print("\n🧪 测试配置管理...")
    
    # 加载全局配置
    config = Config.load_global()
    assert config.defaults.llm.provider == "openai"
    assert config.defaults.image.provider == "nanobanana"
    print("✅ 全局配置加载成功")
    
    # 测试环境变量
    print(f"   API端口: {settings.api_port}")
    print(f"   公开URL: {settings.public_url}")


def test_models():
    """测试数据模型"""
    print("\n🧪 测试数据模型...")
    
    # 创建角色
    char = Character(
        character_id="char_001",
        name="测试角色",
        description="这是一个测试角色",
        personality="开朗活泼"
    )
    assert char.name == "测试角色"
    print("✅ 角色模型创建成功")
    
    # 测试版本管理
    char.add_version(prompt="测试提示词", seed=12345)
    assert len(char.versions) == 1
    assert char.current_version == 1
    print("✅ 版本管理功能正常")
    
    # 创建场景
    scene = Scene(
        scene_id="scene_001",
        name="测试场景",
        description="这是一个测试场景",
        location="教室",
        time="白天"
    )
    assert scene.name == "测试场景"
    print("✅ 场景模型创建成功")


def test_project_manager():
    """测试项目管理"""
    print("\n🧪 测试项目管理...")
    
    pm = ProjectManager()
    
    # 创建测试项目
    project = pm.create_project(
        name="测试项目",
        script_content="# 测试剧本\n\n这是一个测试剧本。",
        style_description="测试风格"
    )
    
    assert project.name == "测试项目"
    print(f"✅ 项目创建成功: {project.project_id}")
    
    # 测试加载
    loaded = pm.load_project(project.project_id)
    assert loaded is not None
    assert loaded.name == "测试项目"
    print("✅ 项目加载成功")
    
    # 测试角色保存
    from src.models.schemas import Character
    char = Character(
        character_id="char_001",
        name="主角",
        description="主角描述",
        personality="勇敢"
    )
    pm.save_characters(project, [char])
    
    loaded_chars = pm.load_characters(project)
    assert len(loaded_chars) == 1
    assert loaded_chars[0].name == "主角"
    print("✅ 角色保存/加载成功")
    
    # 清理测试项目
    pm.delete_project(project.project_id)
    print("✅ 测试项目已清理")


async def test_task_queue():
    """测试任务队列"""
    print("\n🧪 测试任务队列...")
    
    queue = AsyncTaskQueue(max_workers=2, name="test")
    await queue.start()
    
    # 测试任务
    async def test_task(x):
        await asyncio.sleep(0.1)
        return x * 2
    
    # 提交任务
    task1 = await queue.submit(test_task, 5, priority=TaskPriority.NORMAL)
    task2 = await queue.submit(test_task, 10, priority=TaskPriority.HIGH)
    
    # 等待完成
    await queue.wait_for_completion()
    await queue.stop()
    
    # 验证结果
    assert task1.status.value == "completed"
    assert task1.result == 10
    assert task2.status.value == "completed"
    assert task2.result == 20
    
    print("✅ 任务队列功能正常")
    print(f"   完成任务数: {queue.completed_count}")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 动画生成系统 - 功能测试")
    print("=" * 60)
    
    try:
        test_config()
        test_models()
        test_project_manager()
        asyncio.run(test_task_queue())
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
