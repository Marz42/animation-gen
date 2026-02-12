# 首帧生成超时问题排查与修复

## 问题现象

首帧生成过程中，部分图片出现生成超时的情况，导致任务失败。

## 根因分析

### 1. 图片压缩阻塞事件循环（主要原因）

**问题代码**：
```python
def _compress_image_to_base64(self, local_path: str, max_size_kb: int = 300) -> Optional[str]:
    # ... 同步图片压缩操作
```

**问题**：
- 图片压缩是**同步操作**，在异步环境中会**阻塞事件循环**
- 多图i2i需要压缩多张图片（场景+多个角色），耗时累积
- 阻塞期间，其他任务无法执行，导致整体超时

**影响**：
- 压缩1张图片可能需要 1-3 秒
- 6张图片累积可能需要 6-18 秒
- 阻塞事件循环导致队列任务堆积

### 2. 图片下载无超时设置

**问题代码**：
```python
async with session.get(url) as response:  # ❌ 无超时设置
```

**问题**：
- 图片下载没有设置超时，可能无限等待
- 网络波动时容易卡住

### 3. HTTP请求超时时间不足

**问题代码**：
```python
timeout=aiohttp.ClientTimeout(total=120)  # 120秒可能不够
```

**问题**：
- 多图i2i生成耗时较长（特别是1280x720分辨率）
- 120秒超时对于复杂图片可能不足

---

## 修复方案

### 修复1: 图片压缩改为异步执行

**解决**：使用线程池执行压缩操作，避免阻塞事件循环

```python
async def _compress_image_to_base64(self, local_path: str, max_size_kb: int = 300) -> Optional[str]:
    import concurrent.futures
    
    def _do_compress(path_str: str, max_kb: int) -> Optional[str]:
        # 实际的同步压缩操作
        ...
    
    # 在线程池中执行
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, _do_compress, local_path, max_size_kb)
    
    return result
```

**效果**：
- 压缩操作在独立线程中执行
- 不阻塞主事件循环
- 其他任务可以并发执行

### 修复2: 图片下载添加超时

**解决**：为图片下载添加60秒超时

```python
async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
```

### 修复3: 增加HTTP请求超时时间

**解决**：将API请求超时从120秒增加到180秒

```python
timeout=aiohttp.ClientTimeout(total=180)  # 3分钟
```

### 修复4: 添加性能监控日志

**解决**：添加详细的耗时统计，便于排查问题

```python
import time
start_time = time.time()
# ... 操作
elapsed = time.time() - start_time
print(f"[性能] 操作耗时: {elapsed:.2f}秒")
```

---

## 优化效果对比

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 图片压缩 | 阻塞事件循环 | 异步执行，不阻塞 |
| 图片下载超时 | 无限制 | 60秒超时 |
| API请求超时 | 120秒 | 180秒 |
| 性能监控 | 无 | 详细日志 |
| 并发能力 | 低（阻塞） | 高（非阻塞） |

---

## 使用建议

### 1. 监控日志输出

修复后的日志会显示各环节耗时：
```
🎬 [性能] 开始首帧生成流程
  📦 图片压缩完成，耗时: 2.35秒
  📦 图片压缩完成，耗时: 1.89秒
  📊 参考图数量: 7 (场景: True, 人物: 6)
  🎨 使用多图i2i生成，尺寸: 1280x720
    📤 发送i2i请求: ..., images=7
    📥 收到响应: status=200
    ✅ 解析响应成功
  ✅ 图片生成成功，URL: ...
  ✅ 图片下载完成: ..., 耗时: 3.21秒
  ✅ [性能] 首帧生成总耗时: 45.67秒
```

### 2. 如果仍然超时

#### 检查图片大小
- 参考图过大（>2MB）会导致压缩耗时增加
- 建议使用 512x512 或更小的参考图

#### 减少角色数量
- 每个分镜只关联实际出场的角色
- 已通过 `character_ids` 修复实现

#### 调整超时参数
在 `config/default_config.yaml` 中：
```yaml
defaults:
  image:
    timeout: 180  # 根据需要调整
```

#### 检查API提供商状态
- 接口AI服务器负载高时响应会变慢
- 可以切换到 mock 模式测试本地流程

### 3. 批量生成建议

- 首帧生成是计算密集型操作，建议**不要同时生成太多**
- 队列并发数已设置为4，可根据服务器性能调整
- 可以在配置中调整 `image_workers`：
```yaml
defaults:
  concurrency:
    image_workers: 4  # 根据CPU核心数调整
```

---

## 相关文件

| 文件 | 变更 |
|------|------|
| `src/services/jiekouai_service.py` | 图片压缩改为异步、下载添加超时、增加监控日志 |
| `config/default_config.yaml` | 可调整超时参数 |

---

## 验证修复

1. 重新启动后端服务
2. 提交首帧生成任务
3. 观察日志输出，检查是否有超时错误
4. 对比修复前后的生成速度

---

## 后续优化建议

1. **图片压缩缓存**：相同图片多次压缩时，可以缓存结果
2. **渐进式生成**：先生成低分辨率预览，确认后再生成高清图
3. **智能超时**：根据历史数据动态调整超时时间
4. **断点续传**：支持生成中断后从中断点继续

---

## 修复日期

2026-02-12
