"""
令牌桶限速器 — 按用户维度控制上传/下载速率。
算法: 每个用户维护独立的令牌桶, 按配置的速率补充令牌, 每次传输消耗令牌。
"""
import asyncio
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("multimount.ratelimit")


@dataclass
class TokenBucket:
    """令牌桶: 控制单个用户的传输速率"""
    capacity: float            # 桶容量 (bytes)
    rate: float                # 令牌补充速率 (bytes/sec)
    tokens: float = 0.0        # 当前令牌数
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        self.tokens = self.capacity

    def consume(self, amount: float) -> float:
        """
        尝试消费指定量的令牌。
        返回实际可消费的量 (可能小于请求量, 需要等待)。
        """
        self._refill()
        granted = min(amount, self.tokens)
        self.tokens -= granted
        return granted

    def wait_time(self, amount: float) -> float:
        """计算等待多少秒后才能消费指定量的令牌"""
        self._refill()
        if self.tokens >= amount:
            return 0.0
        deficit = amount - self.tokens
        return deficit / self.rate if self.rate > 0 else float("inf")

    def _refill(self):
        """根据流逝时间补充令牌"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now


class RateLimiter:
    """
    全局限速管理器 — 按用户 ID 维护独立的上传/下载令牌桶。
    用法:
        limiter = RateLimiter()
        limiter.set_user_limit(user_id, download_kbps=1024, upload_kbps=512)
        allowed = await limiter.acquire(user_id, "download", chunk_size)
    """

    def __init__(self):
        # key: (user_id, direction) → TokenBucket
        self._buckets: dict[tuple[int, str], TokenBucket] = {}
        self._lock = asyncio.Lock()

    def set_user_limit(self, user_id: int,
                       download_kbps: int = 0, upload_kbps: int = 0):
        """设置用户的上下行速率限制 (KB/s, 0 表示不限制)"""
        if download_kbps > 0:
            rate = download_kbps * 1024  # 转 bytes/s
            # 桶容量 = 1 秒的量, 允许短时突发
            self._buckets[(user_id, "download")] = TokenBucket(
                capacity=rate, rate=rate
            )
        if upload_kbps > 0:
            rate = upload_kbps * 1024
            self._buckets[(user_id, "upload")] = TokenBucket(
                capacity=rate, rate=rate
            )

    async def acquire(self, user_id: int, direction: str, size: int) -> int:
        """
        获取传输许可 — 返回允许传输的字节数。
        如果速率受限, 会异步等待直到有足够令牌。
        direction: "upload" 或 "download"
        """
        bucket = self._buckets.get((user_id, direction))
        if bucket is None:
            return size  # 未配置限制, 全部允许

        async with self._lock:
            granted = bucket.consume(size)
            if granted < size:
                # 需要等待剩余令牌
                wait = bucket.wait_time(size - granted)
                if wait > 0:
                    await asyncio.sleep(min(wait, 1.0))  # 最多等 1 秒再重试
                    granted += bucket.consume(size - granted)
            return int(granted)

    def remove_user(self, user_id: int):
        """移除用户的限速配置"""
        keys_to_remove = [k for k in self._buckets if k[0] == user_id]
        for key in keys_to_remove:
            del self._buckets[key]


# 全局限速器实例
rate_limiter = RateLimiter()
