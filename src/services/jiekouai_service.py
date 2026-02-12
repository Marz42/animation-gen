"""
接口AI (jiekou.ai) 图片生成服务适配器
API文档: https://api.jiekou.ai/v3/nano-banana-pro-light-t2i
"""

import aiohttp
import asyncio
import base64
import io
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
from PIL import Image


class JiekouAIImageService:
    """
    接口AI图片生成服务
    
    API格式:
    POST https://api.jiekou.ai/v3/nano-banana-pro-light-t2i
    Headers:
        Content-Type: application/json
        Authorization: Bearer ${API_KEY}
    Body:
        {
            "n": 1,
            "size": "1x1",
            "prompt": "一只可爱的小猫坐在花园里",
            "quality": "1k",
            "response_format": "url"
        }
    """
    
    # 支持的尺寸映射
    SIZE_MAPPING = {
        "512x512": "1x1",
        "768x432": "16x9",
        "1024x1024": "1x1",
        "1280x720": "16x9",
    }
    
    # 质量映射 - 接口AI只支持 "1k", "2k", "4k"
    QUALITY_MAPPING = {
        "512x512": "1k",
        "768x432": "1k",
        "1024x1024": "1k",
        "1280x720": "1k",
    }
    
    def __init__(self, api_key: str, base_url: str = "https://api.jiekou.ai", endpoint: str = "/v3/nano-banana-pro-light-t2i"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.endpoint = endpoint
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _map_size(self, width: int, height: int) -> str:
        """将分辨率映射到API支持的尺寸格式"""
        key = f"{width}x{height}"
        return self.SIZE_MAPPING.get(key, "1x1")
    
    def _map_quality(self, width: int, height: int) -> str:
        """根据分辨率选择质量"""
        key = f"{width}x{height}"
        return self.QUALITY_MAPPING.get(key, "1k")
    
    async def generate_image(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
        n: int = 1,
        response_format: str = "url",
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        生成图片（支持重试）
        
        Args:
            prompt: 提示词
            width: 图片宽度
            height: 图片高度
            n: 生成数量
            response_format: 响应格式 (url 或 base64)
            max_retries: 最大重试次数
        
        Returns:
            包含图片URL或base64的字典
        """
        session = await self._get_session()
        
        # 构建请求体
        payload = {
            "n": n,
            "size": self._map_size(width, height),
            "prompt": prompt,
            "quality": self._map_quality(width, height),
            "response_format": response_format
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        url = f"{self.base_url}{self.endpoint}"
        
        for attempt in range(max_retries):
            try:
                print(f"    🚀 提交图片生成任务 (尝试 {attempt + 1}/{max_retries})")
                print(f"    📌 URL: {url}")
                print(f"    📌 Prompt: {prompt[:100]}...")
                print(f"    📌 Size: {width}x{height} -> {self._map_size(width, height)}")
                print(f"    📌 Quality: {self._map_quality(width, height)}")
                print(f"    📌 Request Body: {payload}")
                
                import time
                start_time = time.time()
                
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as response:
                    elapsed = time.time() - start_time
                    print(f"    ⏱️ 请求耗时: {elapsed:.2f}秒")
                    if response.status == 200:
                        data = await response.json()
                        print(f"    📥 HTTP 200 响应")
                        print(f"    📥 响应内容: {data}")
                        print(f"    📥 响应键: {list(data.keys())}")
                        
                        # 检查是否返回了图片URL
                        if data.get("data"):
                            print(f"    📥 data字段存在: {type(data['data'])}, 长度: {len(data['data']) if isinstance(data['data'], list) else 'N/A'}")
                            if isinstance(data["data"], list) and len(data["data"]) > 0:
                                image_data = data["data"][0]
                                print(f"    📥 image_data: {image_data}")
                                if image_data.get("url"):
                                    print(f"    ✅ 成功获取URL: {image_data['url'][:60]}...")
                                    return {
                                        "success": True,
                                        "url": image_data.get("url"),
                                        "base64": image_data.get("b64_json"),
                                        "prompt": prompt,
                                        "cost_usd": 0.02
                                    }
                                else:
                                    print(f"    ⚠️ image_data 没有 url 字段")
                            else:
                                print(f"    ⚠️ data 为空或不是列表")
                        else:
                            print(f"    ⚠️ 响应没有 data 字段")
                        
                        # 检查是否有错误信息
                        if "error" in data:
                            error_msg = f"API错误: {data['error']}"
                            print(f"    ❌ {error_msg}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return {"success": False, "error": error_msg, "raw_response": data}
                        
                        if data.get("message"):
                            print(f"    ℹ️ API返回message: {data['message']}")
                        
                        # 重试
                        error_msg = f"API未返回图片URL: {data}"
                        print(f"    ⚠️ {error_msg}")
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"    ⏳ 等待{wait_time}秒后重试...")
                            await asyncio.sleep(wait_time)
                            continue
                        return {"success": False, "error": error_msg, "raw_response": data}
                    else:
                        error_text = await response.text()
                        error_msg = f"API错误: HTTP {response.status}"
                        print(f"    ❌ {error_msg}")
                        print(f"    ❌ 响应内容: {error_text[:500]}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {"success": False, "error": error_msg, "raw_response": error_text}
                        
            except asyncio.TimeoutError:
                print(f"    ⏱️ 请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "success": False,
                    "error": "请求超时"
                }
            except Exception as e:
                error_msg = f"请求异常: {str(e)}"
                print(f"    ❌ {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "success": False,
                    "error": error_msg
                }
        
        return {
            "success": False,
            "error": "达到最大重试次数"
        }
    
    async def generate_character_reference(
        self,
        prompt: str,
        output_path: Path,
        size: str = "512x512"
    ) -> Path:
        """
        生成角色参考图
        
        Args:
            prompt: 提示词
            output_path: 输出路径 (不带扩展名)
            size: 尺寸 (512x512 或 768x432)
        
        Returns:
            实际保存的图片路径
        """
        width, height = map(int, size.split('x'))
        
        result = await self.generate_image(prompt, width, height)
        
        if result["success"] and result.get("url"):
            # 下载图片，自动检测扩展名
            actual_path = await self._download_image_with_ext(result["url"], output_path)
            return actual_path
        
        return None
    
    async def generate_image_i2i(
        self,
        prompt: str,
        image_url: str,
        width: int = 512,
        height: int = 512,
        n: int = 1,
        response_format: str = "url",
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        使用 i2i (image-to-image) API 生成图片（支持重试）
        
        API端点: POST https://api.jiekou.ai/v3/nano-banana-pro-light-i2i
        
        Args:
            prompt: 提示词
            image_url: 参考图片URL
            width: 图片宽度
            height: 图片高度
            n: 生成数量
            response_format: 响应格式
            max_retries: 最大重试次数
        
        Returns:
            包含图片URL或base64的字典
        """
        session = await self._get_session()
        
        # 构建请求体 - i2i API (images 是字符串数组)
        payload = {
            "n": n,
            "size": self._map_size(width, height),
            "images": [image_url],
            "prompt": prompt,
            "quality": self._map_quality(width, height),
            "response_format": response_format
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        url = f"{self.base_url}/v3/nano-banana-pro-light-i2i"
        
        for attempt in range(max_retries):
            try:
                print(f"    🚀 提交i2i图片生成任务 (尝试 {attempt + 1}/{max_retries})")
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"    📥 响应: {data}")
                        
                        if data.get("data") and len(data["data"]) > 0:
                            image_data = data["data"][0]
                            if image_data.get("url"):
                                return {
                                    "success": True,
                                    "url": image_data.get("url"),
                                    "base64": image_data.get("b64_json"),
                                    "prompt": prompt,
                                    "cost_usd": 0.02
                                }
                        
                        if "error" in data:
                            error_msg = f"API错误: {data['error']}"
                            print(f"    ❌ {error_msg}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return {"success": False, "error": error_msg, "raw_response": data}
                        
                        error_msg = f"API未返回图片URL: {data}"
                        print(f"    ⚠️ {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {"success": False, "error": error_msg, "raw_response": data}
                    else:
                        error_text = await response.text()
                        error_msg = f"API错误: {response.status} - {error_text}"
                        print(f"    ❌ {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {"success": False, "error": error_msg}
                        
            except asyncio.TimeoutError:
                print(f"    ⏱️ 请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"success": False, "error": "请求超时"}
            except Exception as e:
                error_msg = f"请求异常: {str(e)}"
                print(f"    ❌ {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"success": False, "error": error_msg}
        
        return {"success": False, "error": "达到最大重试次数"}

    async def generate_scene_reference(
        self,
        prompt: str,
        output_path: Path,
        size: str = "1024x1024",
        reference_image_url: Optional[str] = None
    ) -> Path:
        """
        生成场景参考图
        
        Args:
            prompt: 提示词
            output_path: 输出路径 (不带扩展名)
            size: 尺寸 (默认1024x1024)
            reference_image_url: 可选的参考图片URL (用于i2i生成)
        
        Returns:
            实际保存的图片路径
        """
        width, height = map(int, size.split('x'))
        
        # 如果有参考图URL，使用i2i；否则使用t2i
        if reference_image_url:
            result = await self.generate_image_i2i(prompt, reference_image_url, width, height)
        else:
            result = await self.generate_image(prompt, width, height)
        
        if result["success"] and result.get("url"):
            actual_path = await self._download_image_with_ext(result["url"], output_path)
            return actual_path
        
        return None

    async def _compress_image_to_base64(self, local_path: str, max_size_kb: int = 300) -> Optional[str]:
        """压缩图片并转为base64编码（异步版本，避免阻塞事件循环）"""
        import concurrent.futures
        
        def _do_compress(path_str: str, max_kb: int) -> Optional[str]:
            """实际压缩操作（在线程池中执行）"""
            try:
                path = Path(path_str)
                if not path.exists():
                    return None
                
                # 打开图片
                img = Image.open(path)
                
                # 转换为 RGB（去除透明通道）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 初始质量
                quality = 85
                
                while quality > 20:
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=quality, optimize=True)
                    size_kb = buffer.tell() / 1024
                    
                    if size_kb <= max_kb:
                        return base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    quality -= 10
                
                # 如果质量降到 20 还是太大，缩小尺寸
                ratio = 0.9
                while ratio > 0.3:
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    resized = img.resize(new_size, Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    resized.save(buffer, format='JPEG', quality=70, optimize=True)
                    size_kb = buffer.tell() / 1024
                    
                    if size_kb <= max_kb:
                        return base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    ratio -= 0.1
                
                # 最后尝试
                buffer = io.BytesIO()
                img.resize((512, 512), Image.Resampling.LANCZOS).save(buffer, format='JPEG', quality=60)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
                
            except Exception as e:
                print(f"    ⚠️ 压缩图片失败: {e}")
                return None
        
        # 在线程池中执行压缩操作
        try:
            import time
            start_time = time.time()
            
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(
                    pool, 
                    _do_compress, 
                    local_path, 
                    max_size_kb
                )
            
            elapsed = time.time() - start_time
            if result:
                print(f"    📦 图片压缩完成，耗时: {elapsed:.2f}秒")
            
            return result
            
        except Exception as e:
            print(f"    ⚠️ 异步压缩图片失败: {e}")
            return None
    
    # 保留同步版本供兼容（已废弃）
    def _compress_image_to_base64_sync(self, local_path: str, max_size_kb: int = 300) -> Optional[str]:
        """压缩图片并转为base64编码（同步版本，已废弃，请使用异步版本）"""
        try:
            path = Path(local_path)
            if not path.exists():
                print(f"    ⚠️ 图片不存在: {local_path}")
                return None
            
            # 打开图片
            img = Image.open(path)
            
            # 转换为 RGB（去除透明通道）
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # 初始质量
            quality = 85
            
            while quality > 20:
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                size_kb = buffer.tell() / 1024
                
                if size_kb <= max_size_kb:
                    print(f"    📦 压缩后: {size_kb:.1f}KB (quality={quality})")
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                quality -= 10
            
            # 如果质量降到 20 还是太大，缩小尺寸
            ratio = 0.9
            while ratio > 0.3:
                new_size = (int(img.width * ratio), int(img.height * ratio))
                resized = img.resize(new_size, Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                resized.save(buffer, format='JPEG', quality=70, optimize=True)
                size_kb = buffer.tell() / 1024
                
                if size_kb <= max_size_kb:
                    print(f"    📦 压缩后: {size_kb:.1f}KB (尺寸={new_size[0]}x{new_size[1]})")
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                ratio -= 0.1
            
            # 最后尝试
            buffer = io.BytesIO()
            img.resize((512, 512), Image.Resampling.LANCZOS).save(buffer, format='JPEG', quality=60)
            print(f"    📦 强制压缩到 512x512")
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
        except Exception as e:
            print(f"    ⚠️ 压缩图片失败: {e}")
            return None

    async def generate_keyframe(
        self,
        prompt: str,
        output_path: Path,
        size: str = "1280x720",
        character_refs: Optional[List[str]] = None,
        scene_ref: Optional[str] = None
    ) -> Optional[Path]:
        """
        生成视频首帧（支持多图i2i，带性能监控）
        
        Args:
            prompt: 提示词
            output_path: 输出路径
            size: 尺寸 (默认1280x720)
            character_refs: 角色参考图路径列表
            scene_ref: 场景参考图路径
        
        Returns:
            实际保存的路径，失败返回None
        """
        import time
        total_start_time = time.time()
        
        width, height = map(int, size.split('x'))
        
        print(f"🎬 [性能] 开始首帧生成流程")
        
        # 压缩并编码参考图（异步执行）
        reference_images = []
        if scene_ref:
            scene_b64 = await self._compress_image_to_base64(scene_ref, max_size_kb=300)
            if scene_b64:
                reference_images.append(scene_b64)
                print(f"  📷 场景参考图已压缩")
        
        if character_refs:
            for path in character_refs:
                char_b64 = await self._compress_image_to_base64(path, max_size_kb=300)
                if char_b64:
                    reference_images.append(char_b64)
                    print(f"  📷 角色参考图已压缩")
        
        print(f"  📊 参考图数量: {len(reference_images)} (场景: {scene_ref is not None}, 人物: {len(character_refs) if character_refs else 0})")
        
        # 如果有参考图，使用i2i；否则使用t2i
        if reference_images:
            print(f"  🎨 使用多图i2i生成，尺寸: {width}x{height}")
            result = await self.generate_image_multi_i2i(
                prompt=prompt,
                image_urls=reference_images,
                width=width,
                height=height
            )
        else:
            print(f"  🎨 使用t2i生成，尺寸: {width}x{height}")
            result = await self.generate_image(prompt, width, height)
        
        if result["success"] and result.get("url"):
            print(f"  ✅ 图片生成成功，URL: {result['url'][:60]}...")
            actual_path = await self._download_image_with_ext(result["url"], output_path)
            
            total_elapsed = time.time() - total_start_time
            print(f"  ✅ [性能] 首帧生成总耗时: {total_elapsed:.2f}秒")
            return actual_path
        else:
            print(f"  ❌ 图片生成失败: {result.get('error', '未知错误')}")
            
            total_elapsed = time.time() - total_start_time
            print(f"  ❌ [性能] 首帧生成失败，耗时: {total_elapsed:.2f}秒")
        
        return None
    
    async def generate_image_multi_i2i(
        self,
        prompt: str,
        image_urls: List[str],
        width: int = 512,
        height: int = 512,
        n: int = 1,
        response_format: str = "url",
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        使用多图i2i (image-to-image) API 生成图片（支持重试）
        
        Args:
            prompt: 提示词
            image_urls: 参考图片URL列表
            width: 图片宽度
            height: 图片高度
            n: 生成数量
            response_format: 响应格式
            max_retries: 最大重试次数
        
        Returns:
            包含图片URL或base64的字典
        """
        session = await self._get_session()
        images = [url for url in image_urls if url]

        payload = {
            "n": n,
            "size": self._map_size(width, height),
            "images": images,
            "prompt": prompt,
            "quality": self._map_quality(width, height),
            "response_format": response_format
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        url = f"{self.base_url}/v3/nano-banana-pro-light-i2i"
        print(f"    📤 发送i2i请求: {url}, images={len(images)}")

        for attempt in range(max_retries):
            try:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as response:
                    print(f"    📥 收到响应: status={response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"    ✅ 解析响应成功: {data}")

                        if data.get("data") and len(data["data"]) > 0:
                            image_data = data["data"][0]
                            if image_data.get("url"):
                                return {
                                    "success": True,
                                    "url": image_data.get("url"),
                                    "base64": image_data.get("b64_json"),
                                    "prompt": prompt,
                                    "cost_usd": 0.02
                                }
                        
                        if "error" in data:
                            error_msg = f"API错误: {data['error']}"
                            print(f"    ❌ {error_msg}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return {"success": False, "error": error_msg, "raw_response": data}
                        
                        error_msg = f"API未返回图片URL: {data}"
                        print(f"    ⚠️ {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {"success": False, "error": error_msg, "raw_response": data}
                    else:
                        error_text = await response.text()
                        error_msg = f"API错误: {response.status} - {error_text}"
                        print(f"    ❌ {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {"success": False, "error": error_msg}
                        
            except asyncio.TimeoutError:
                print(f"    ⏱️ 请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"success": False, "error": "请求超时"}
            except Exception as e:
                print(f"    ❌ 请求异常: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"success": False, "error": f"请求异常: {str(e)}"}
        
        return {"success": False, "error": "达到最大重试次数"}
    
    async def _download_image(self, url: str, output_path: Path, timeout: int = 60):
        """下载图片到本地
        
        Args:
            url: 图片URL
            output_path: 输出路径
            timeout: 下载超时时间（秒）
        """
        session = await self._get_session()
        
        import time
        start_time = time.time()
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 从 Content-Type 检测实际图片格式
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        actual_path = output_path.with_suffix('.jpg')
                    elif 'png' in content_type:
                        actual_path = output_path.with_suffix('.png')
                    elif 'webp' in content_type:
                        actual_path = output_path.with_suffix('.webp')
                    else:
                        # 默认使用请求的路径扩展名，如果没有则使用 .png
                        actual_path = output_path if output_path.suffix else output_path.with_suffix('.png')
                    
                    with open(actual_path, 'wb') as f:
                        f.write(await response.read())
                    
                    elapsed = time.time() - start_time
                    print(f"    ✅ 图片下载完成: {actual_path}, 耗时: {elapsed:.2f}秒")
                    return True
                else:
                    print(f"    ❌ 图片下载失败: HTTP {response.status}")
                    return False
                    
        except asyncio.TimeoutError:
            print(f"    ⏱️ 图片下载超时: {url}")
            return False
        except Exception as e:
            print(f"    ❌ 图片下载失败: {e}")
            return False
    
    async def _download_image_with_ext(self, url: str, output_path: Path, timeout: int = 60) -> Path:
        """下载图片并返回实际保存的路径（自动检测扩展名）
        
        Args:
            url: 图片URL
            output_path: 输出路径
            timeout: 下载超时时间（秒）
        """
        session = await self._get_session()
        
        import time
        start_time = time.time()
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 从 Content-Type 检测实际图片格式
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        actual_path = output_path.with_suffix('.jpg')
                    elif 'png' in content_type:
                        actual_path = output_path.with_suffix('.png')
                    elif 'webp' in content_type:
                        actual_path = output_path.with_suffix('.webp')
                    else:
                        # 尝试从 URL 检测
                        url_lower = url.lower()
                        if '.jpg' in url_lower or '.jpeg' in url_lower:
                            actual_path = output_path.with_suffix('.jpg')
                        elif '.png' in url_lower:
                            actual_path = output_path.with_suffix('.png')
                        elif '.webp' in url_lower:
                            actual_path = output_path.with_suffix('.webp')
                        else:
                            actual_path = output_path.with_suffix('.png')
                    
                    with open(actual_path, 'wb') as f:
                        f.write(await response.read())
                    
                    elapsed = time.time() - start_time
                    print(f"    ✅ 图片下载完成: {actual_path}, 耗时: {elapsed:.2f}秒")
                    return actual_path
                else:
                    print(f"    ❌ 图片下载失败: HTTP {response.status}")
                    return output_path
                    
        except asyncio.TimeoutError:
            print(f"    ⏱️ 图片下载超时: {url}")
            return output_path
        except Exception as e:
            print(f"    ❌ 图片下载失败: {e}")
            return output_path
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试API连接
        
        Returns:
            测试结果
        """
        # 使用简单提示词测试
        result = await self.generate_image(
            prompt="test",
            width=512,
            height=512,
            n=1
        )
        
        return {
            "connected": result["success"],
            "error": result.get("error"),
            "response": result.get("raw_response")
        }
