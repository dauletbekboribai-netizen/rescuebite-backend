from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from redis import Redis
from redis.exceptions import RedisError
from sqlmodel import Session, select
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database import get_session
from app.models.domain import BatchIngredient, BatchStatus, CustomerOrder, FoodBatch, OrderItem, OrderStatus, PaymentTransaction, Reservation, ReservationStatus, User, UserAllergy
from app.schemas.common import OrderCreate, OrderList, OrderRead, OrderUpdate, ReservationCreate, ReservationRead
from app.services.price_decay import apply_price_decay

router = APIRouter(prefix='/orders', tags=['orders'])
settings = get_settings()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def has_allergy_conflict(session: Session, user_id: int, batch_id: int) -> bool:
    user_allergens = {a.allergen for a in session.exec(select(UserAllergy).where(UserAllergy.user_id == user_id)).all()}
    batch_allergens = {i.allergen for i in session.exec(select(BatchIngredient).where(BatchIngredient.batch_id == batch_id)).all() if i.allergen}
    return bool(user_allergens.intersection(batch_allergens))


@router.post('/reservations', response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    batch = session.get(FoodBatch, payload.batch_id)
    if not batch or batch.status != BatchStatus.active:
        raise HTTPException(status_code=404, detail='batch not available')
    apply_price_decay(batch)
    if batch.current_price_kzt < 0 or batch.quantity_available < payload.quantity:
        raise HTTPException(status_code=409, detail='not enough stock')
    if has_allergy_conflict(session, user.id, batch.id):
        raise HTTPException(status_code=409, detail='allergy conflict: purchase blocked')
    key = f'reserve:batch:{batch.id}'
    try:
        reserved = int(redis_client.get(key) or 0)
        if reserved + payload.quantity > batch.quantity_available:
            raise HTTPException(status_code=409, detail='stock already reserved')
        pipe = redis_client.pipeline()
        pipe.incrby(key, payload.quantity)
        pipe.expire(key, 600)
        pipe.execute()
    except RedisError:
        pass
    batch.quantity_available -= payload.quantity
    reservation = Reservation(user_id=user.id, batch_id=batch.id, quantity=payload.quantity, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    session.add(batch); session.add(reservation); session.commit(); session.refresh(reservation)
    return reservation


@router.post('/reservations/{reservationId}/cancel', response_model=ReservationRead)
def cancel_reservation(reservationId: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    reservation = session.get(Reservation, reservationId)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail='reservation not found')
    if reservation.status != ReservationStatus.active:
        raise HTTPException(status_code=409, detail='reservation is not active')
    batch = session.get(FoodBatch, reservation.batch_id)
    reservation.status = ReservationStatus.cancelled
    if batch:
        batch.quantity_available += reservation.quantity
        session.add(batch)
    session.add(reservation); session.commit(); session.refresh(reservation)
    return reservation


@router.get('', response_model=OrderList)
def list_orders(cursor: int | None = None, limit: int = Query(default=20, ge=1, le=100), user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    statement = select(CustomerOrder).where(CustomerOrder.user_id == user.id, CustomerOrder.status != OrderStatus.deleted).order_by(CustomerOrder.id.desc()).limit(limit + 1)
    if cursor:
        statement = select(CustomerOrder).where(CustomerOrder.user_id == user.id, CustomerOrder.id < cursor, CustomerOrder.status != OrderStatus.deleted).order_by(CustomerOrder.id.desc()).limit(limit + 1)
    items = session.exec(statement).all()
    next_cursor = None
    if len(items) > limit:
        next_cursor = str(items[limit - 1].id)
        items = items[:limit]
    return OrderList(items=items, next_cursor=next_cursor)


@router.post('', response_model=OrderRead, status_code=201)
def create_order(payload: OrderCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    reservation = session.get(Reservation, payload.reservation_id)

    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail='reservation not found')

    now = datetime.now(timezone.utc)

    expires_at = reservation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if reservation.status != ReservationStatus.active or expires_at < now:
        raise HTTPException(status_code=409, detail='reservation expired or not active')

    batch = session.get(FoodBatch, reservation.batch_id)

    if not batch:
        raise HTTPException(status_code=404, detail='batch not found')

    apply_price_decay(batch)

    total = batch.current_price_kzt * reservation.quantity

    reservation.status = ReservationStatus.converted

    order = CustomerOrder(
        user_id=user.id,
        reservation_id=reservation.id,
        total_kzt=total,
        status=OrderStatus.pending_payment
    )

    session.add(reservation)
    session.add(order)
    session.commit()
    session.refresh(order)

    item = OrderItem(
        order_id=order.id,
        batch_id=batch.id,
        quantity=reservation.quantity,
        unit_price_kzt=batch.current_price_kzt
    )

    session.add(item)
    session.add(PaymentTransaction(order_id=order.id, restaurant_id=batch.restaurant_id, amount_kzt=total, provider=payload.payment_method))
    session.commit()

    return order


@router.get('/{orderId}', response_model=OrderRead)
def get_order(orderId: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = session.get(CustomerOrder, orderId)
    if not order or order.user_id != user.id or order.status == OrderStatus.deleted:
        raise HTTPException(status_code=404, detail='order not found')
    return order


@router.patch('/{orderId}', response_model=OrderRead)
def update_order(orderId: int, payload: OrderUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = session.get(CustomerOrder, orderId)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail='order not found')
    if payload.status and order.status not in {OrderStatus.pending_payment, OrderStatus.paid, OrderStatus.prepared, OrderStatus.ready_for_pickup}:
        raise HTTPException(status_code=409, detail='order no longer editable')
    if payload.status:
        order.status = payload.status
    session.add(order); session.commit(); session.refresh(order)
    return order


@router.delete('/{orderId}', status_code=204)
def delete_order(orderId: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = session.get(CustomerOrder, orderId)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail='order not found')
    order.status = OrderStatus.deleted
    session.add(order); session.commit()
    return None


@router.post('/{orderId}/cancel', response_model=OrderRead)
def cancel_order(orderId: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = session.get(CustomerOrder, orderId)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail='order not found')
    if order.status not in {OrderStatus.pending_payment, OrderStatus.paid, OrderStatus.prepared}:
        raise HTTPException(status_code=409, detail='order cannot be cancelled')
    order.status = OrderStatus.cancelled
    session.add(order); session.commit(); session.refresh(order)
    return order
