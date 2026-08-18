import uuid

import pytest
from tests.conftest import FakeRedis

from app.services.errors import QuizGenerationRateLimitExceededError
from app.services.rate_limit import QuizGenerationRateLimiter


async def test_check_and_increment_allows_requests_within_limits(fake_redis: FakeRedis) -> None:
    limiter = QuizGenerationRateLimiter(fake_redis)
    user_id = uuid.uuid4()

    for _ in range(5):
        await limiter.check_and_increment(user_id)


async def test_check_and_increment_raises_after_hourly_limit(fake_redis: FakeRedis) -> None:
    limiter = QuizGenerationRateLimiter(fake_redis)
    user_id = uuid.uuid4()

    for _ in range(5):
        await limiter.check_and_increment(user_id)

    with pytest.raises(QuizGenerationRateLimitExceededError):
        await limiter.check_and_increment(user_id)


async def test_check_and_increment_raises_after_daily_limit(fake_redis: FakeRedis) -> None:
    limiter = QuizGenerationRateLimiter(fake_redis)
    user_id = uuid.uuid4()

    # 1時間あたりの上限(5)を跨いでも1日あたりの上限(10)は独立してカウントされることを確認するため、
    # hourlyキーだけ都度リセットしつつ10回インクリメントする。
    for _ in range(10):
        await fake_redis.delete(f"quiz_gen_count:{user_id}:hourly")
        await limiter.check_and_increment(user_id)

    await fake_redis.delete(f"quiz_gen_count:{user_id}:hourly")
    with pytest.raises(QuizGenerationRateLimitExceededError):
        await limiter.check_and_increment(user_id)


async def test_check_and_increment_is_scoped_per_user(fake_redis: FakeRedis) -> None:
    limiter = QuizGenerationRateLimiter(fake_redis)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    for _ in range(5):
        await limiter.check_and_increment(user_a)

    await limiter.check_and_increment(user_b)
