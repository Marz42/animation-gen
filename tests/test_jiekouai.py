#!/usr/bin/env python3
"""
测试接口AI配置
验证API连接是否正常
"""

import sys
sys.path.insert(0, '../src')

import asyncio

print("=" * 60)
print("🧪 接口AI配置测试")
print("=" * 60)

# 测试1: 配置读取
print("\n📋 测试1: 配置读取")
from src.core.config import Config, settings

config = Config.load_global()
print(f"✅ 图片提供商: {config.defaults.image.provider}")
print(f"✅ Base URL: {config.defaults.image.base_url}")
print(f"✅ Endpoint: {config.defaults.image.endpoint}")

# 测试2: 环境变量读取
print("\n📋 测试2: 环境变量")
print(f"✅ JIEKOUAI_API_KEY: {'已设置' if settings.jiekouai_api_key else '未设置'}")
print(f"✅ JIEKOUAI_BASE_URL: {settings.jiekouai_base_url}")
print(f"✅ JIEKOUAI_ENDPOINT: {settings.jiekouai_endpoint}")

if not settings.jiekouai_api_key:
    print("\n⚠️ 警告: API Key 未设置！")
    print("请在 .env 文件中设置 JIEKOUAI_API_KEY")
    print("\n测试终止")
    sys.exit(1)

# 测试3: 服务初始化
print("\n📋 测试3: 服务初始化")
from src.services.jiekouai_service import JiekouAIImageService

service = JiekouAIImageService(
    api_key=settings.jiekouai_api_key,
    base_url=settings.jiekouai_base_url,
    endpoint=settings.jiekouai_endpoint
)
print("✅ JiekouAIImageService 初始化成功")

# 测试4: API连接测试
print("\n📋 测试4: API连接测试")
print("正在发送测试请求...")

async def test_api():
    result = await service.test_connection()
    return result

result = asyncio.run(test_api())

if result["connected"]:
    print("✅ API连接成功！")
    print(f"响应数据: {result.get('response', 'N/A')}")
else:
    print("❌ API连接失败")
    print(f"错误信息: {result.get('error')}")
    print(f"原始响应: {result.get('response')}")

# 测试5: 简单图片生成测试
print("\n📋 测试5: 简单图片生成")
print("正在生成测试图片（可能需要几十秒）...")

async def test_generation():
    result = await service.generate_image(
        prompt="一只可爱的小猫，卡通风格",
        width=512,
        height=512,
        n=1
    )
    return result

result = asyncio.run(test_generation())

if result["success"]:
    print("✅ 图片生成成功！")
    print(f"图片URL: {result.get('url', 'N/A')[:50]}...")
else:
    print("❌ 图片生成失败")
    print(f"错误: {result.get('error')}")
    print(f"原始响应: {result.get('raw_response')}")

print("\n" + "=" * 60)
print("✅ 接口AI配置测试完成")
print("=" * 60)

print("\n💡 如果测试失败，请检查:")
print("   1. API Key 是否正确")
print("   2. 网络连接是否正常")
print("   3. 账户余额是否充足")
