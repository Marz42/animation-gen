"""
异步任务队列模块
使用纯asyncio实现，无需Redis
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务定义"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    func: Callable = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None
    metadata: Dict = field(default_factory=dict)


class AsyncTaskQueue:
    """
    异步任务队列
    
    特性：
    - 优先级队列
    - 并发控制
    - 重试机制
    - 状态追踪
    """
    
    def __init__(self, max_workers: int = 4, name: str = "default"):
        self.name = name
        self.max_workers = max_workers
        self.queue = asyncio.PriorityQueue()
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self._workers: List[asyncio.Task] = []
        self._semaphore = asyncio.Semaphore(max_workers)
    
    async def start(self):
        """启动任务队列"""
        if self.running:
            return
        
        self.running = True
        logger.info(f"[{self.name}] 任务队列启动，并发数: {self.max_workers}")
        
        # 启动worker
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)
    
    async def stop(self):
        """停止任务队列"""
        self.running = False
        
        # 取消所有worker
        for worker in self._workers:
            worker.cancel()
        
        # 等待所有worker完成
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info(f"[{self.name}] 任务队列已停止")
    
    async def submit(
        self,
        func: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict] = None,
        **kwargs
    ) -> Task:
        """
        提交任务到队列
        
        Args:
            func: 异步函数
            args: 位置参数
            priority: 优先级
            max_retries: 最大重试次数
            callback: 完成回调函数
            metadata: 元数据
            kwargs: 关键字参数
        
        Returns:
            Task对象
        """
        task = Task(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            callback=callback,
            metadata=metadata or {}
        )
        
        self.tasks[task.task_id] = task
        
        # 放入优先级队列 (priority, created_at, task_id)
        await self.queue.put((priority.value, task.created_at.timestamp(), task.task_id))
        
        logger.debug(f"[{self.name}] 任务提交: {task.task_id}")
        return task
    
    async def _worker_loop(self, worker_name: str):
        """Worker循环"""
        logger.debug(f"[{self.name}] {worker_name} 启动")
        
        while self.running:
            try:
                # 获取任务
                _, _, task_id = await self.queue.get()
                task = self.tasks.get(task_id)
                
                if not task or task.status == TaskStatus.CANCELLED:
                    self.queue.task_done()
                    continue
                
                # 使用信号量控制并发
                async with self._semaphore:
                    await self._execute_task(task)
                
                self.queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Worker错误: {e}")
        
        logger.debug(f"[{self.name}] {worker_name} 停止")
    
    async def _execute_task(self, task: Task):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        logger.info(f"[{self.name}] 任务开始: {task.task_id}")
        
        try:
            # 执行函数
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            logger.info(f"[{self.name}] 任务完成: {task.task_id}")
            
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                # 重试
                logger.warning(f"[{self.name}] 任务失败，准备重试: {task.task_id} (尝试 {task.retry_count}/{task.max_retries})")
                task.status = TaskStatus.PENDING
                await asyncio.sleep(2 ** task.retry_count)  # 指数退避
                await self.queue.put((task.priority.value, datetime.now().timestamp(), task.task_id))
            else:
                # 最终失败
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                logger.error(f"[{self.name}] 任务最终失败: {task.task_id} - {e}")
        
        finally:
            # 执行回调
            if task.callback:
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(task)
                    else:
                        task.callback(task)
                except Exception as e:
                    logger.error(f"[{self.name}] 回调错误: {e}")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """按状态获取任务列表"""
        return [t for t in self.tasks.values() if t.status == status]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if task and task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            return True
        return False
    
    @property
    def pending_count(self) -> int:
        """待处理任务数"""
        return len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
    
    @property
    def running_count(self) -> int:
        """运行中任务数"""
        return len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING])
    
    @property
    def completed_count(self) -> int:
        """已完成任务数"""
        return len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
    
    @property
    def failed_count(self) -> int:
        """失败任务数"""
        return len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED])
    
    async def wait_for_completion(self):
        """等待所有任务完成"""
        await self.queue.join()


# 全局队列实例
_queues: Dict[str, AsyncTaskQueue] = {}


def get_queue(name: str = "default", max_workers: int = 4) -> AsyncTaskQueue:
    """获取或创建任务队列"""
    if name not in _queues:
        _queues[name] = AsyncTaskQueue(max_workers=max_workers, name=name)
    return _queues[name]


async def shutdown_all_queues():
    """关闭所有队列"""
    for queue in _queues.values():
        await queue.stop()
    _queues.clear()
