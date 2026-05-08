import base64
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select
from app.api.deps import get_current_user, require_roles
from app.database import get_session
from app.models.domain import BatchIngredient, BatchStatus, FoodBatch, Restaurant, User, UserRole, VerificationStatus
from app.schemas.common import BatchCreate, BatchList, BatchRead, BatchUpdate
from app.services.price_decay import apply_price_decay

router = APIRouter(prefix='/batches', tags=['batches'])


def encode_cursor(created_at: datetime, item_id: int) -> str:
    return base64.urlsafe_b64encode(f'{created_at.isoformat()}|{item_id}'.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_raw, id_raw = raw.split('|')
    return datetime.fromisoformat(created_raw), int(id_raw)


@router.get('', response_model=BatchList)
def list_batches(cursor: str | None = None, limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)):
    statement = select(FoodBatch).where(FoodBatch.status == BatchStatus.active).order_by(FoodBatch.created_at.desc(), FoodBatch.id.desc()).limit(limit + 1)
    if cursor:
        created, item_id = decode_cursor(cursor)
        statement = select(FoodBatch).where(
            FoodBatch.status == BatchStatus.active,
            (FoodBatch.created_at < created) | ((FoodBatch.created_at == created) & (FoodBatch.id < item_id)),
        ).order_by(FoodBatch.created_at.desc(), FoodBatch.id.desc()).limit(limit + 1)
    items = session.exec(statement).all()
    for batch in items:
        apply_price_decay(batch)
    next_cursor = None
    if len(items) > limit:
        last = items[limit - 1]
        next_cursor = encode_cursor(last.created_at, last.id)
        items = items[:limit]
    return BatchList(items=items, next_cursor=next_cursor)


@router.post('', response_model=BatchRead, status_code=201)
def create_batch(payload: BatchCreate, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = session.exec(select(Restaurant).where(Restaurant.owner_id == user.id)).first()
    if user.role != UserRole.admin and (not restaurant or restaurant.verification_status != VerificationStatus.verified):
        raise HTTPException(status_code=403, detail='restaurant must be verified before publishing batches')
    if not restaurant:
        restaurant = Restaurant(owner_id=user.id, name='Admin Test Restaurant', address='Almaty', lat=payload.lat, lng=payload.lng, verification_status=VerificationStatus.verified)
        session.add(restaurant)
        session.commit(); session.refresh(restaurant)
    batch = FoodBatch(
        restaurant_id=restaurant.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        quantity_total=payload.quantity_total,
        quantity_available=payload.quantity_total,
        original_price_kzt=payload.original_price_kzt,
        current_price_kzt=payload.original_price_kzt,
        expires_at=payload.expires_at,
        pickup_start_at=payload.pickup_start_at,
        pickup_end_at=payload.pickup_end_at,
        lat=payload.lat,
        lng=payload.lng,
    )
    apply_price_decay(batch)
    session.add(batch)
    session.commit(); session.refresh(batch)
    for item in payload.ingredients:
        session.add(BatchIngredient(batch_id=batch.id, name=item.name, allergen=item.allergen))
    session.commit()
    return batch


@router.get('/{batchId}', response_model=BatchRead)
def get_batch(batchId: int, session: Session = Depends(get_session)):
    batch = session.get(FoodBatch, batchId)
    if not batch or batch.status == BatchStatus.deleted:
        raise HTTPException(status_code=404, detail='batch not found')
    apply_price_decay(batch)
    session.add(batch); session.commit(); session.refresh(batch)
    return batch


@router.patch('/{batchId}', response_model=BatchRead)
def update_batch(batchId: int, payload: BatchUpdate, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    batch = session.get(FoodBatch, batchId)
    if not batch or batch.status == BatchStatus.deleted:
        raise HTTPException(status_code=404, detail='batch not found')
    if user.role != UserRole.admin:
        restaurant = session.get(Restaurant, batch.restaurant_id)
        if not restaurant or restaurant.owner_id != user.id:
            raise HTTPException(status_code=403, detail='not owner of this batch')
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(batch, key, value)
    apply_price_decay(batch)
    session.add(batch); session.commit(); session.refresh(batch)
    return batch


@router.delete('/{batchId}', status_code=204)
def delete_batch(batchId: int, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    batch = session.get(FoodBatch, batchId)
    if not batch:
        raise HTTPException(status_code=404, detail='batch not found')
    if user.role != UserRole.admin:
        restaurant = session.get(Restaurant, batch.restaurant_id)
        if not restaurant or restaurant.owner_id != user.id:
            raise HTTPException(status_code=403, detail='not owner of this batch')
    batch.status = BatchStatus.deleted
    session.add(batch); session.commit()
    return None
