#!/usr/bin/env python3
"""
修复已有分镜的角色关联问题
将每个分镜的 characters 重置为该场景的所有角色（保守方案）
或根据分镜描述智能分析（需要LLM，较复杂）

使用方法:
1. 列出项目: python fix_shot_characters.py --list
2. 修复项目: python fix_shot_characters.py --project <project_id>
3. 预览修复: python fix_shot_characters.py --project <project_id> --dry-run
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.project_manager import ProjectManager


def list_projects():
    """列出所有项目"""
    pm = ProjectManager()
    projects = pm.list_projects()
    
    print("\n📋 项目列表：")
    print("-" * 80)
    for p in projects:
        print(f"ID: {p.project_id}")
        print(f"名称: {p.name}")
        print(f"阶段: {p.current_stage}")
        print(f"路径: {p.root_path}")
        print("-" * 80)


def fix_project_characters(project_id: str, dry_run: bool = True):
    """
    修复项目的分镜角色关联
    
    策略：
    由于无法准确知道每个分镜实际涉及哪些角色（需要重新分析剧本），
    我们采用保守策略：保留第一个角色作为主角，移除其他角色。
    这样可以至少减少部分不必要的参考图。
    
    更精确的修复需要：
    1. 重新解析剧本
    2. 根据分镜描述匹配角色
    3. 或调用LLM分析
    """
    pm = ProjectManager()
    project = pm.load_project(project_id)
    
    if not project:
        print(f"❌ 项目不存在: {project_id}")
        return
    
    print(f"\n🔧 修复项目: {project.name} ({project_id})")
    print("-" * 80)
    
    # 加载数据
    shots = pm.load_shots(project)
    characters = pm.load_characters(project)
    scenes = pm.load_scenes(project)
    
    if not shots:
        print("⚠️ 项目没有分镜")
        return
    
    # 构建场景角色映射
    scene_characters = {}
    for scene in scenes:
        scene_characters[scene.scene_id] = scene.characters  # 场景关联的角色名称列表
    
    # 构建角色ID到名称的映射
    char_id_to_name = {c.character_id: c.name for c in characters}
    char_name_to_id = {c.name: c.character_id for c in characters}
    
    print(f"\n📊 项目统计：")
    print(f"  分镜数: {len(shots)}")
    print(f"  角色数: {len(characters)}")
    print(f"  场景数: {len(scenes)}")
    
    print(f"\n🔍 分镜角色分析：")
    print("-" * 80)
    
    fixes = []
    
    for shot in shots:
        current_chars = shot.characters
        current_count = len(current_chars)
        
        # 获取该场景的所有角色ID
        scene = next((s for s in scenes if s.scene_id == shot.scene_id), None)
        if not scene:
            print(f"  ⚠️ {shot.shot_id}: 找不到对应场景")
            continue
        
        # 场景关联的角色名称列表
        scene_char_names = scene.characters or []
        
        # 转换为角色ID列表（只保留存在的角色）
        valid_char_ids = []
        for name in scene_char_names:
            char_id = char_name_to_id.get(name)
            if char_id:
                valid_char_ids.append(char_id)
        
        # 如果分镜的角色比场景还多，说明有问题
        if current_count > len(valid_char_ids):
            print(f"  ❌ {shot.shot_id}: {current_count}个角色 → 应最多{len(valid_char_ids)}个")
            print(f"     当前: {[char_id_to_name.get(c, c) for c in current_chars]}")
            print(f"     场景角色: {scene_char_names}")
            
            # 保守修复：只保留第一个角色
            if valid_char_ids:
                new_chars = [valid_char_ids[0]]  # 只保留第一个角色
            else:
                new_chars = []
            
            fixes.append({
                'shot': shot,
                'old_chars': current_chars,
                'new_chars': new_chars
            })
        else:
            print(f"  ✅ {shot.shot_id}: {current_count}个角色 - 正常")
    
    print("-" * 80)
    
    if not fixes:
        print("\n✅ 所有分镜角色关联正常，无需修复")
        return
    
    print(f"\n🔧 需要修复的分镜: {len(fixes)}个")
    
    if dry_run:
        print("\n⚠️ 预览模式（未实际修改），使用 --apply 参数执行修复")
        return
    
    # 执行修复
    print("\n📝 执行修复...")
    for fix in fixes:
        shot = fix['shot']
        shot.characters = fix['new_chars']
        print(f"  ✅ {shot.shot_id}: 角色已更新为 {[char_id_to_name.get(c, c) for c in fix['new_chars']]}")
    
    # 保存修改
    pm.save_shots(project, shots)
    print("\n💾 修改已保存")
    print("\n⚠️ 注意：这只是保守修复（只保留第一个角色）")
    print("   如需精确修复，请手动编辑数据文件或重新生成分镜")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='修复分镜角色关联问题')
    parser.add_argument('--list', action='store_true', help='列出所有项目')
    parser.add_argument('--project', type=str, help='项目ID')
    parser.add_argument('--apply', action='store_true', help='实际执行修复（默认仅预览）')
    
    args = parser.parse_args()
    
    if args.list:
        list_projects()
    elif args.project:
        fix_project_characters(args.project, dry_run=not args.apply)
    else:
        parser.print_help()
        print("\n示例：")
        print("  python fix_shot_characters.py --list")
        print("  python fix_shot_characters.py --project xxxxxx --dry-run")
        print("  python fix_shot_characters.py --project xxxxxx --apply")


if __name__ == "__main__":
    main()
