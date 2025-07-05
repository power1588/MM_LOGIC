import asyncio
import time
from collections import deque

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests_per_second: int):
        self.max_requests = max_requests_per_second
        self.request_times = deque()
        self._lock = asyncio.Lock()
        
    async def acquire(self) -> None:
        """获取请求许可"""
        async with self._lock:
            if self.max_requests <= 0:
                return
            current_time = time.time()
            
            # 清理超过1秒的请求记录
            while self.request_times and current_time - self.request_times[0] >= 1.0:
                self.request_times.popleft()
                
            # 如果当前1秒内的请求数已达到限制，等待
            if len(self.request_times) >= self.max_requests:
                wait_time = 1.0 - (current_time - self.request_times[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
                    
            # 记录当前请求时间
            self.request_times.append(current_time)
            
    def get_current_rate(self) -> float:
        """获取当前请求速率"""
        current_time = time.time()
        
        # 清理过期的请求记录
        while self.request_times and current_time - self.request_times[0] >= 1.0:
            self.request_times.popleft()
            
        return len(self.request_times) 