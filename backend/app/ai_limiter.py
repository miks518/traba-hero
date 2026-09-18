"""AI concurrency limiter — caps simultaneous AI provider calls.

Uses asyncio.BoundedSemaphore for concurrency control + manual queue
depth tracking to reject burst overflow immediately (503).
"""

import asyncio
import logging

from fastapi import HTTPException

from app.config import settings

log = logging.getLogger("trabahero")


class AILimiter:
    """Limits concurrent AI requests with a bounded queue depth.

    Args:
        max_concurrent: Max simultaneous AI calls (semaphore slots).
        max_queue_depth: Max requests waiting in the acquire queue.
        acquire_timeout: Max seconds a request waits for a semaphore slot.
        call_timeout: Max seconds for a single AI call.
    """

    def __init__(
        self,
        max_concurrent: int = 2,
        max_queue_depth: int = 10,
        acquire_timeout: float = 10.0,
        call_timeout: float = 120.0,
    ):
        self.max_concurrent = max_concurrent
        self.max_queue_depth = max_queue_depth
        self.acquire_timeout = acquire_timeout
        self.call_timeout = call_timeout
        self._semaphore = asyncio.BoundedSemaphore(max_concurrent)
        self._waiter_count = 0
        self._active_count = 0

    @property
    def stats(self) -> dict:
        return {
            "max_concurrent": self.max_concurrent,
            "max_queue_depth": self.max_queue_depth,
            "active": self._active_count,
            "queued": self._waiter_count,
            "available_slots": max(0, self.max_concurrent - self._active_count),
        }

    async def acquire(self) -> None:
        """Acquire a semaphore slot. Raises 503 if queue full or acquire times out."""
        if self._waiter_count >= self.max_queue_depth:
            log.warning(
                "AI limiter queue full: %d queued (max %d), %d active",
                self._waiter_count,
                self.max_queue_depth,
                self._active_count,
            )
            raise HTTPException(
                status_code=503,
                detail="Server is at capacity. Too many requests queued. Please try again.",
            )

        self._waiter_count += 1
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.acquire_timeout,
            )
        except asyncio.TimeoutError:
            log.warning(
                "AI limiter acquire timeout after %.1fs: %d active, %d queued",
                self.acquire_timeout,
                self._active_count,
                self._waiter_count,
            )
            raise HTTPException(
                status_code=503,
                detail="Server is busy. All AI slots occupied. Please try again.",
            )
        finally:
            self._waiter_count -= 1

        self._active_count += 1

    def release(self) -> None:
        """Release a semaphore slot."""
        self._active_count = max(0, self._active_count - 1)
        self._semaphore.release()

    async def run(self, coro):
        """Execute an async call within the limiter.

        Handles acquire, call timeout, and release automatically.
        """
        await self.acquire()
        try:
            async with asyncio.timeout(self.call_timeout):
                return await coro
        except TimeoutError:
            log.error("AI call timed out after %.1fs", self.call_timeout)
            raise HTTPException(
                status_code=504,
                detail="The AI service took too long to respond. Please try again.",
            )
        finally:
            self.release()


ai_limiter = AILimiter(
    max_concurrent=settings.ai_max_concurrent,
    max_queue_depth=settings.ai_max_queue_depth,
    acquire_timeout=settings.ai_acquire_timeout,
    call_timeout=settings.ai_call_timeout,
)
