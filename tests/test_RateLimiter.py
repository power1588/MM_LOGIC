import pytest
import asyncio
import time
from src.utils.limiting.RateLimiter import RateLimiter

class TestRateLimiter:
    """测试速率限制器"""
    
    @pytest.fixture
    def rate_limiter(self):
        """创建速率限制器实例"""
        return RateLimiter(max_requests_per_second=10)
        
    @pytest.mark.asyncio
    async def test_init(self, rate_limiter):
        """测试初始化"""
        assert rate_limiter.max_requests == 10
        assert len(rate_limiter.request_times) == 0
        
    @pytest.mark.asyncio
    async def test_acquire_normal(self, rate_limiter):
        """测试正常获取许可"""
        start_time = time.time()
        
        # 获取许可
        await rate_limiter.acquire()
        
        end_time = time.time()
        
        # 应该立即返回
        assert end_time - start_time < 0.1
        
        # 检查请求时间记录
        assert len(rate_limiter.request_times) == 1
        
    @pytest.mark.asyncio
    async def test_acquire_rate_limit(self, rate_limiter):
        """测试达到速率限制"""
        # 快速获取10个许可（达到限制）
        for i in range(10):
            await rate_limiter.acquire()
            
        # 第11个请求应该被延迟
        start_time = time.time()
        await rate_limiter.acquire()
        end_time = time.time()
        
        # 应该等待约1秒
        assert end_time - start_time >= 0.9
        
    @pytest.mark.asyncio
    async def test_acquire_multiple_requests(self, rate_limiter):
        """测试多个请求"""
        # 获取5个许可
        for i in range(5):
            await rate_limiter.acquire()
            
        # 检查当前速率
        current_rate = rate_limiter.get_current_rate()
        assert current_rate == 5
        
    @pytest.mark.asyncio
    async def test_cleanup_old_requests(self, rate_limiter):
        """测试清理旧请求"""
        # 添加一些请求
        for i in range(5):
            await rate_limiter.acquire()
            
        # 等待超过1秒
        await asyncio.sleep(1.1)
        
        # 检查当前速率
        current_rate = rate_limiter.get_current_rate()
        assert current_rate == 0
        
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, rate_limiter):
        """测试并发请求"""
        async def make_request():
            await rate_limiter.acquire()
            return time.time()
            
        # 并发发送10个请求
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # 所有请求都应该成功
        assert len(results) == 10
        
        # 检查请求时间记录
        assert len(rate_limiter.request_times) == 10
        
    @pytest.mark.asyncio
    async def test_get_current_rate(self, rate_limiter):
        """测试获取当前速率"""
        # 初始速率应该为0
        assert rate_limiter.get_current_rate() == 0
        
        # 添加一些请求
        for i in range(3):
            await rate_limiter.acquire()
            
        # 当前速率应该为3
        assert rate_limiter.get_current_rate() == 3
        
    @pytest.mark.asyncio
    async def test_rate_limit_different_values(self):
        """测试不同的速率限制值"""
        # 测试低速率限制
        low_rate_limiter = RateLimiter(max_requests_per_second=1)
        
        start_time = time.time()
        await low_rate_limiter.acquire()
        await low_rate_limiter.acquire()
        end_time = time.time()
        
        # 第二个请求应该等待约1秒
        assert end_time - start_time >= 0.9
        
        # 测试高速率限制
        high_rate_limiter = RateLimiter(max_requests_per_second=100)
        
        start_time = time.time()
        for i in range(50):
            await high_rate_limiter.acquire()
        end_time = time.time()
        
        # 应该快速完成
        assert end_time - start_time < 0.1
        
    @pytest.mark.asyncio
    async def test_edge_cases(self, rate_limiter):
        """测试边界情况"""
        # 测试零速率限制（应该允许所有请求）
        zero_rate_limiter = RateLimiter(max_requests_per_second=0)
        
        start_time = time.time()
        await zero_rate_limiter.acquire()
        end_time = time.time()
        
        # 应该立即返回
        assert end_time - start_time < 0.1
        
        # 测试负速率限制（应该允许所有请求）
        negative_rate_limiter = RateLimiter(max_requests_per_second=-1)
        
        start_time = time.time()
        await negative_rate_limiter.acquire()
        end_time = time.time()
        
        # 应该立即返回
        assert end_time - start_time < 0.1
        
    @pytest.mark.asyncio
    async def test_cleanup_mechanism(self, rate_limiter):
        """测试清理机制"""
        # 添加一些请求
        for i in range(5):
            await rate_limiter.acquire()
            
        # 手动设置一些旧请求
        old_time = time.time() - 2.0  # 2秒前
        rate_limiter.request_times.appendleft(old_time)
        
        # 获取当前速率（应该触发清理）
        current_rate = rate_limiter.get_current_rate()
        
        # 旧请求应该被清理
        assert current_rate == 5
        assert old_time not in rate_limiter.request_times
        
    @pytest.mark.asyncio
    async def test_thread_safety(self, rate_limiter):
        """测试线程安全性"""
        # 模拟并发访问
        async def concurrent_access():
            await rate_limiter.acquire()
            await asyncio.sleep(0.01)  # 模拟处理时间
            return rate_limiter.get_current_rate()
            
        # 创建多个并发任务
        tasks = [concurrent_access() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        # 所有任务都应该成功完成
        assert len(results) == 20
        assert all(isinstance(r, int) for r in results) 