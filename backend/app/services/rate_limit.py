import uuid

from redis.asyncio import Redis

from app.core.errors import TooManyRequestsError

RATE_LIMIT_MESSAGE = "規定のリクエスト回数に達しました。制限解除までしばらくお待ちください。"

_KEY_PREFIX = "quiz_gen_count"
_HOURLY_LIMIT = 5
_HOURLY_TTL_SECONDS = 60 * 60
_DAILY_LIMIT = 10
_DAILY_TTL_SECONDS = 60 * 60 * 24


class QuizGenerationRateLimitExceededError(TooManyRequestsError):
    pass


class QuizGenerationRateLimiter:
    """USERロールのクイズ生成回数を1時間5回・1日10回に制限する(ADMINは呼び出し元でスキップする)。"""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check_and_increment(self, user_id: uuid.UUID) -> None:
        """回数をインクリメントし、上限を超えていればQuizGenerationRateLimitExceededErrorを送出する。"""
        hourly_key = f"{_KEY_PREFIX}:{user_id}:hourly"
        daily_key = f"{_KEY_PREFIX}:{user_id}:daily"

        hourly_count = await self._redis.incr(hourly_key)
        if hourly_count == 1:
            await self._redis.expire(hourly_key, _HOURLY_TTL_SECONDS)
        daily_count = await self._redis.incr(daily_key)
        if daily_count == 1:
            await self._redis.expire(daily_key, _DAILY_TTL_SECONDS)

        if hourly_count > _HOURLY_LIMIT or daily_count > _DAILY_LIMIT:
            raise QuizGenerationRateLimitExceededError(RATE_LIMIT_MESSAGE)
