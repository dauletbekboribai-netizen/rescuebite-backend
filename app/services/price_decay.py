from datetime import datetime, timezone

from app.models.domain import BatchState, FoodBatch


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def apply_price_decay(batch: FoodBatch, now: datetime | None = None) -> FoodBatch:
    current_time = _as_utc(now or datetime.now(timezone.utc))
    created_at = _as_utc(batch.created_at)
    expires_at = _as_utc(batch.expires_at)

    total_seconds = max((expires_at - created_at).total_seconds(), 1)
    remaining_seconds = (expires_at - current_time).total_seconds()
    ratio_remaining = remaining_seconds / total_seconds

    if remaining_seconds <= 0:
        batch.state = BatchState.compost
        batch.current_price_kzt = 0
        batch.discount_percentage = 100
    elif ratio_remaining <= 0.20:
        batch.state = BatchState.free
        batch.current_price_kzt = 0
        batch.discount_percentage = 100
    elif ratio_remaining <= 0.50:
        batch.state = BatchState.discounted
        batch.discount_percentage = 50
        batch.current_price_kzt = int(batch.original_price_kzt * 0.5)
    else:
        batch.state = BatchState.fresh
        batch.discount_percentage = 0
        batch.current_price_kzt = batch.original_price_kzt

    batch.updated_at = current_time
    return batch
