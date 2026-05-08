from datetime import datetime, timedelta, timezone
from app.models.domain import FoodBatch, BatchState
from app.services.price_decay import apply_price_decay


def make_batch(created, expires):
    return FoodBatch(
        restaurant_id=1,
        title='Soup',
        category='meal',
        quantity_total=5,
        quantity_available=5,
        original_price_kzt=1000,
        current_price_kzt=1000,
        expires_at=expires,
        pickup_start_at=created,
        pickup_end_at=expires,
        lat=43.2,
        lng=76.8,
        created_at=created,
    )


def test_price_decay_reaches_free_window():
    now = datetime.now(timezone.utc)
    batch = make_batch(now - timedelta(hours=8), now + timedelta(hours=1))
    apply_price_decay(batch, now=now)
    assert batch.state == BatchState.free
    assert batch.current_price_kzt == 0
    assert batch.discount_percentage == 100
