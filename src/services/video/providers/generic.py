"""
通用视频提供商
支持通过配置自定义API调用，适配不同的视频生成服务
"""
import json
import base64
import aiohttp
from typing import Dict, Any, Optional
from pathlib import Path

from .base import (
    BaseVideoProvider, VideoGenerationRequest, VideoGenerationResult,
    VideoDuration, VideoResolution
)


class GenericVideoProvider(BaseVideoProvider):
    """
    通用视频提供商
    
    通过配置支持任意符合HTTP API的视频生成服务
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 解析配置
        self.request_template = config.get("request_template", {})
        self.parameter_mapping = config.get("parameter_mapping", {})
        self.response_parser = config.get("response_parser", {})
        self.status_query = config.get("status_query", {})
    
    def get_capabilities(self) -> Dict[str, Any]:
        """获取能力配置"""
        # 从参数映射中推断支持的能力
        duration_options = list(self.parameter_mapping.get("duration", {}).keys())
        resolution_options = list(self.parameter_mapping.get("resolution", {}).keys())
        
        return {
            "supports_image_input": True,
            "image_format": "base64",
            "durations": duration_options if duration_options else ["4s", "8s", "12s"],
            "resolutions": resolution_options if resolution_options else ["720p", "1080p"],
            "max_prompt_length": 2000,
            "supports_watermark": False,
            "requires_upload": False,
            "async_only": True,
            "generic": True,
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _image_to_base64(self, image_path: str) -> str:
        """将图片转为 base64"""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def _map_parameter(self, param_name: str, value: Any) -> Any:
        """映射参数值"""
        mapping = self.parameter_mapping.get(param_name, {})
        return mapping.get(value, value)
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """渲染模板字符串"""
        result = template
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, (dict, list)):
                # JSON对象直接替换
                result = result.replace(f'"{placeholder}"', json.dumps(value))
            else:
                result = result.replace(placeholder, str(value))
        return result
    
    def _build_request(self, request: VideoGenerationRequest) -> Dict[str, Any]:
        """构建HTTP请求"""
        # 准备上下文
        image_base64 = ""
        if request.image_path and Path(request.image_path).exists():
            image_base64 = self._image_to_base64(request.image_path)
        
        context = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "prompt": request.prompt,
            "image_base64": image_base64,
            "duration": self._map_parameter("duration", request.duration.value),
            "resolution": self._map_parameter("resolution", request.resolution.value),
            "watermark": request.watermark,
        }
        
        # 构建请求
        url_template = self.request_template.get("url", "")
        method = self.request_template.get("method", "POST")
        headers_template = self.request_template.get("headers", {})
        body_template = self.request_template.get("body_template", "")
        
        # 渲染模板
        url = self._render_template(url_template, context)
        headers = {
            key: self._render_template(value, context)
            for key, value in headers_template.items()
        }
        body = self._render_template(body_template, context) if body_template else ""
        
        return {
            "url": url,
            "method": method,
            "headers": headers,
            "body": body,
        }
    
    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析响应数据"""
        result = {}
        
        # 解析 task_id
        task_id_path = self.response_parser.get("task_id_path", "")
        if task_id_path:
            result["task_id"] = self._get_nested_value(response_data, task_id_path)
        
        # 解析状态
        status_path = self.response_parser.get("status_path", "")
        if status_path:
            result["status"] = self._get_nested_value(response_data, status_path)
        
        # 解析视频URL
        video_url_path = self.response_parser.get("video_url_path", "")
        if video_url_path:
            result["video_url"] = self._get_nested_value(response_data, video_url_path)
        
        # 解析错误信息
        error_path = self.response_parser.get("error_path", "")
        if error_path:
            result["error"] = self._get_nested_value(response_data, error_path)
        
        return result
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """获取嵌套字典值，如 'data.task.id' """
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    async def generate_video(
        self, 
        request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """提交视频生成任务"""
        try:
            session = await self._get_session()
            
            # 构建请求
            req = self._build_request(request)
            
            print(f"🎬 提交视频生成任务: {req['url']}")
            print(f"   Method: {req['method']}")
            print(f"   Prompt: {request.prompt[:80]}...")
            
            # 发送请求
            body = json.loads(req["body"]) if req["body"] else None
            async with session.request(
                method=req["method"],
                url=req["url"],
                headers=req["headers"],
                json=body,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                response_data = await resp.json()
                
                if resp.status not in [200, 201]:
                    error_msg = self._parse_response(response_data).get("error", f"HTTP {resp.status}")
                    print(f"❌ API调用失败: {error_msg}")
                    return VideoGenerationResult(
                        success=False,
                        status="failed",
                        error_message=f"API错误: {error_msg}"
                    )
                
                # 解析响应
                parsed = self._parse_response(response_data)
                task_id = parsed.get("task_id")
                
                print(f"✅ 视频任务已提交: task_id={task_id}")
                
                return VideoGenerationResult(
                    success=True,
                    task_id=task_id,
                    status="submitted",
                    provider_info={
                        "raw_response": response_data,
                        "provider": "generic",
                    }
                )
                
        except Exception as e:
            print(f"❌ 视频生成异常: {e}")
            import traceback
            traceback.print_exc()
            return VideoGenerationResult(
                success=False,
                status="failed",
                error_message=str(e)
            )
    
    async def check_status(self, task_id: str) -> VideoGenerationResult:
        """查询任务状态"""
        try:
            session = await self._get_session()
            
            # 构建状态查询请求
            query_config = self.status_query
            url_template = query_config.get("url", "")
            method = query_config.get("method", "GET")
            headers_template = query_config.get("headers", {})
            
            context = {
                "api_key": self.api_key,
                "task_id": task_id,
            }
            
            url = self._render_template(url_template, context)
            headers = {
                key: self._render_template(value, context)
                for key, value in headers_template.items()
            }
            
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return VideoGenerationResult(
                        success=False,
                        task_id=task_id,
                        status="failed",
                        error_message=f"API错误: {text[:200]}"
                    )
                
                response_data = await resp.json()
                
                # 解析响应
                parsed = self._parse_response(response_data)
                raw_status = parsed.get("status", "unknown")
                
                # 映射状态
                status_mapping = query_config.get("status_mapping", {})
                normalized_status = status_mapping.get(raw_status, raw_status.lower())
                
                result = VideoGenerationResult(
                    success=normalized_status != "failed",
                    task_id=task_id,
                    status=normalized_status,
                    provider_info={"raw_response": response_data}
                )
                
                # 如果完成，提取视频URL
                if normalized_status == "completed":
                    result.video_url = parsed.get("video_url")
                
                # 如果失败，提取错误信息
                if normalized_status == "failed":
                    result.error_message = parsed.get("error", "未知错误")
                
                return result
                
        except Exception as e:
            print(f"❌ 检查状态异常: {e}")
            return VideoGenerationResult(
                success=False,
                task_id=task_id,
                status="unknown",
                error_message=str(e)
            )
    
    async def download_video(self, video_url: str, output_path: str) -> bool:
        """下载视频"""
        try:
            session = await self._get_session()
            
            async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status == 200:
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    chunks = []
                    async for chunk in resp.content.iter_chunked(8192):
                        chunks.append(chunk)
                    
                    data = b''.join(chunks)
                    with open(output_path, 'wb') as f:
                        f.write(data)
                    
                    print(f"✅ 视频已下载: {output_path}")
                    return True
                else:
                    print(f"❌ 下载失败: HTTP {resp.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            return False
    
    async def close(self):
        """关闭资源"""
        if self.session and not self.session.closed:
            await self.session.close()
