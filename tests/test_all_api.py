#!/usr/bin/env python3
"""
全面后端API测试脚本
实际调用接口AI进行测试
"""

import sys
sys.path.insert(0, '.')

import asyncio
import json
from pathlib import Path

print("=" * 70)
print("🧪 后端API全面测试")
print("=" * 70)

# 测试配置
API_BASE = "http://localhost:8000"
TEST_SCRIPT = """# 第一幕：相遇

## 场景1：图书馆

男主角小明坐在图书馆靠窗的位置，正在看一本关于天文学的厚书。
女主角小红抱着一摞书走过来，不小心被椅子腿绊了一下。
书散落一地，小明连忙起身帮忙捡起。
两人四目相对，小红脸颊微红，说了声谢谢。

## 场景2：咖啡厅

几天后，小明和小红在学校附近的咖啡厅偶遇。
他们坐在同一张桌子旁，聊起了各自喜欢的书籍。
窗外的阳光洒进来，氛围温馨而美好。
"""

TEST_STYLE = "高精度日系作画风格，参考新海诚动画电影，色彩柔和，光影细腻"

# 测试数据存储
project_id = None
characters = []
scenes = []
shots = []

async def test_project_api():
    """测试项目管理API"""
    print("\n📋 测试1: 项目管理API")
    
    import requests
    
    # 1. 创建项目
    print("   1.1 创建项目...")
    response = requests.post(
        f"{API_BASE}/api/projects",
        json={
            "name": "全面测试项目",
            "script_content": TEST_SCRIPT,
            "style_description": TEST_STYLE
        },
        timeout=10
    )
    assert response.status_code == 200, f"创建项目失败: {response.text}"
    data = response.json()
    global project_id
    project_id = data["project_id"]
    print(f"   ✅ 项目创建成功: {project_id}")
    print(f"   📊 LLM模型: {data['config']['llm_model']}")
    print(f"   📊 图片提供商: {data['config']['image_provider']}")
    
    # 2. 列出项目
    print("   1.2 列出项目...")
    response = requests.get(f"{API_BASE}/api/projects", timeout=5)
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) > 0
    print(f"   ✅ 项目列表获取成功: {len(projects)} 个项目")
    
    # 3. 获取单个项目
    print("   1.3 获取项目详情...")
    response = requests.get(f"{API_BASE}/api/projects/{project_id}", timeout=5)
    assert response.status_code == 200
    project = response.json()
    assert project["project_id"] == project_id
    print(f"   ✅ 项目详情获取成功")
    
    return True

async def test_script_parsing():
    """测试剧本解析API"""
    print("\n📋 测试2: 剧本解析API")
    
    import requests
    
    # 开始解析
    print("   2.1 开始剧本解析...")
    response = requests.post(
        f"{API_BASE}/api/projects/{project_id}/parse",
        timeout=5
    )
    assert response.status_code == 200, f"解析请求失败: {response.text}"
    print(f"   ✅ 解析任务已提交")
    
    # 等待解析完成（最多30秒）
    print("   2.2 等待解析完成...")
    max_wait = 30
    waited = 0
    while waited < max_wait:
        await asyncio.sleep(2)
        waited += 2
        
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}",
            timeout=5
        )
        project = response.json()
        
        if project["current_stage"] == "pending_review_extraction":
            print(f"   ✅ 解析完成 (耗时 {waited}s)")
            break
        elif project["current_stage"] == "error":
            print(f"   ❌ 解析失败 (stage=error)")
            return False
        else:
            print(f"   ⏳ 解析中... ({waited}s)")
    else:
        print(f"   ⚠️ 解析超时")
        return False
    
    # 检查角色
    print("   2.3 检查角色数据...")
    response = requests.get(
        f"{API_BASE}/api/projects/{project_id}/characters",
        timeout=5
    )
    assert response.status_code == 200
    global characters
    characters = response.json()
    print(f"   ✅ 角色数量: {len(characters)}")
    for char in characters:
        print(f"      - {char['name']}: {char.get('description', 'N/A')[:30]}...")
    
    # 检查场景
    print("   2.4 检查场景数据...")
    response = requests.get(
        f"{API_BASE}/api/projects/{project_id}/scenes",
        timeout=5
    )
    assert response.status_code == 200
    global scenes
    scenes = response.json()
    print(f"   ✅ 场景数量: {len(scenes)}")
    for scene in scenes:
        print(f"      - {scene['name']}: {scene.get('description', 'N/A')[:30]}...")
    
    return len(characters) > 0 and len(scenes) > 0

async def test_shot_design():
    """测试分镜设计API"""
    print("\n📋 测试3: 分镜设计API")
    
    import requests
    
    # 开始设计分镜
    print("   3.1 开始分镜设计...")
    response = requests.post(
        f"{API_BASE}/api/projects/{project_id}/design-shots",
        json={},
        timeout=5
    )
    assert response.status_code == 200, f"分镜设计请求失败: {response.text}"
    print(f"   ✅ 分镜设计任务已提交")
    
    # 等待设计完成
    print("   3.2 等待分镜设计完成...")
    max_wait = 30
    waited = 0
    while waited < max_wait:
        await asyncio.sleep(2)
        waited += 2
        
        response = requests.get(
            f"{API_BASE}/api/projects/{project_id}",
            timeout=5
        )
        project = response.json()
        
        if project["current_stage"] == "pending_review_shots":
            print(f"   ✅ 分镜设计完成 (耗时 {waited}s)")
            break
        elif project["current_stage"] == "error":
            print(f"   ❌ 分镜设计失败")
            return False
        else:
            print(f"   ⏳ 设计中... ({waited}s)")
    else:
        print(f"   ⚠️ 分镜设计超时")
        return False
    
    # 检查分镜
    print("   3.3 检查分镜数据...")
    response = requests.get(
        f"{API_BASE}/api/projects/{project_id}/shots",
        timeout=5
    )
    assert response.status_code == 200
    global shots
    shots = response.json()
    print(f"   ✅ 分镜数量: {len(shots)}")
    for shot in shots[:3]:  # 只显示前3个
        print(f"      - {shot['shot_id']}: {shot.get('description', 'N/A')[:40]}...")
    
    return len(shots) > 0

async def test_image_generation():
    """测试图片生成API（只测试1个角色）"""
    print("\n📋 测试4: 图片生成API")
    
    import requests
    
    if not characters:
        print("   ⚠️ 没有角色数据，跳过图片生成测试")
        return True
    
    # 只测试第一个角色
    char = characters[0]
    print(f"   4.1 生成角色 '{char['name']}' 的参考图...")
    print(f"   📝 角色描述: {char.get('description', 'N/A')[:50]}...")
    
    # 实际调用图片生成API
    from src.services.jiekouai_service import JiekouAIImageService
    from src.core.config import settings
    
    image_service = JiekouAIImageService(
        api_key=settings.jiekouai_api_key,
        base_url=settings.jiekouai_base_url,
        endpoint=settings.jiekouai_endpoint
    )
    
    # 构建提示词
    prompt = f"{char['description']}, {TEST_STYLE}, high quality, detailed, portrait"
    print(f"   🎨 生成提示词: {prompt[:60]}...")
    
    output_path = Path(f"~/animation_projects/test_{project_id}_{char['character_id']}.png").expanduser()
    
    try:
        result = await image_service.generate_image(
            prompt=prompt,
            width=512,
            height=512
        )
        
        if result["success"]:
            print(f"   ✅ 图片生成成功")
            print(f"   🌐 图片URL: {result.get('url', 'N/A')[:50]}...")
            
            # 下载图片
            await image_service._download_image(result["url"], output_path)
            if output_path.exists():
                print(f"   💾 图片已保存: {output_path}")
                print(f"   📁 文件大小: {output_path.stat().st_size} bytes")
            else:
                print(f"   ⚠️ 图片下载可能失败")
        else:
            print(f"   ❌ 图片生成失败: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"   ❌ 图片生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await image_service.close()
    
    return True

async def test_queue_status():
    """测试队列状态API"""
    print("\n📋 测试5: 队列状态API")
    
    import requests
    
    response = requests.get(f"{API_BASE}/api/queues/status", timeout=5)
    assert response.status_code == 200
    queues = response.json()
    
    print("   ✅ 队列状态:")
    for queue_name, stats in queues.items():
        print(f"      {queue_name}: 待处理={stats['pending']}, 运行中={stats['running']}, 已完成={stats['completed']}, 失败={stats['failed']}")
    
    return True

async def run_all_tests():
    """运行所有测试"""
    results = []
    
    # 测试1: 项目管理
    try:
        results.append(("项目管理API", await test_project_api()))
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("项目管理API", False))
    
    if not results[-1][1]:
        print("\n❌ 项目创建失败，终止测试")
        return results
    
    # 测试2: 剧本解析
    try:
        results.append(("剧本解析API", await test_script_parsing()))
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("剧本解析API", False))
    
    # 测试3: 分镜设计
    if results[-1][1]:  # 只有解析成功才测试分镜
        try:
            results.append(("分镜设计API", await test_shot_design()))
        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append(("分镜设计API", False))
    else:
        print("\n⚠️ 跳过测试3（剧本解析失败）")
        results.append(("分镜设计API", None))
    
    # 测试4: 图片生成
    try:
        results.append(("图片生成API", await test_image_generation()))
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("图片生成API", False))
    
    # 测试5: 队列状态
    try:
        results.append(("队列状态API", await test_queue_status()))
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        results.append(("队列状态API", False))
    
    return results

# 运行测试
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("⚠️  确保后端服务已启动: ./start_backend.sh")
    print("=" * 70)
    
    # 检查后端是否运行
    import requests
    try:
        response = requests.get(f"{API_BASE}/api/projects", timeout=3)
        print("\n✅ 后端服务连接正常")
    except:
        print("\n❌ 后端服务未启动，请先运行:")
        print("   cd ~/.openclaw/workspace/animation-gen")
        print("   ./start_backend.sh")
        sys.exit(1)
    
    # 运行测试
    results = asyncio.run(run_all_tests())
    
    # 打印测试报告
    print("\n" + "=" * 70)
    print("📊 测试报告")
    print("=" * 70)
    
    for test_name, result in results:
        status = "✅ 通过" if result == True else ("❌ 失败" if result == False else "⏭️ 跳过")
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, r in results if r == True)
    failed = sum(1 for _, r in results if r == False)
    skipped = sum(1 for _, r in results if r is None)
    total = len(results)
    
    print("\n" + "=" * 70)
    print(f"总计: {total} | ✅ 通过: {passed} | ❌ 失败: {failed} | ⏭️ 跳过: {skipped}")
    print("=" * 70)
    
    # 清理测试项目
    if project_id:
        print(f"\n🧹 清理测试项目 {project_id}...")
        try:
            requests.delete(f"{API_BASE}/api/projects/{project_id}", timeout=5)
            print("✅ 测试项目已删除")
        except:
            print("⚠️ 测试项目删除失败（可手动清理）")
    
    sys.exit(0 if failed == 0 else 1)
