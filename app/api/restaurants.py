from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_roles
from app.database import get_session
from app.models.domain import (
    BatchStatus,
    CustomerOrder,
    FoodBatch,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    PaymentTransaction,
    Reservation,
    Restaurant,
    RestaurantOperationLog,
    RestaurantProduct,
    User,
    UserRole,
    VerificationStatus,
)
from app.schemas.common import (
    BatchList,
    BatchRead,
    OrderList,
    OrderRead,
    PaymentRead,
    ProductCreate,
    ProductList,
    ProductRead,
    ProductUpdate,
    RestaurantDashboard,
    RestaurantOperationRead,
    RestaurantRead,
    RestaurantUpdate,
)
from app.services.price_decay import apply_price_decay

router = APIRouter(prefix='/restaurants', tags=['restaurants'])


def _owned_restaurant(session: Session, user: User, restaurant_id: int | None = None) -> Restaurant:
    if restaurant_id is not None:
        restaurant = session.get(Restaurant, restaurant_id)
    else:
        restaurant = session.exec(select(Restaurant).where(Restaurant.owner_id == user.id)).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail='restaurant not found')
    if user.role != UserRole.admin and restaurant.owner_id != user.id:
        raise HTTPException(status_code=403, detail='not owner of this restaurant')
    return restaurant


def _log(session: Session, user_id: int, restaurant_id: int, action: str, entity_type: str, entity_id: int | None = None, details: str = '') -> None:
    session.add(RestaurantOperationLog(actor_user_id=user_id, restaurant_id=restaurant_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details[:2000]))


@router.get('/me', response_model=RestaurantDashboard)
def my_restaurant_dashboard(user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user)
    batches = session.exec(select(FoodBatch).where(FoodBatch.restaurant_id == restaurant.id, FoodBatch.status != BatchStatus.deleted).order_by(FoodBatch.expires_at.asc()).limit(50)).all()
    for batch in batches:
        apply_price_decay(batch)
        session.add(batch)
    products = session.exec(select(RestaurantProduct).where(RestaurantProduct.restaurant_id == restaurant.id, RestaurantProduct.active == True).order_by(RestaurantProduct.name.asc()).limit(50)).all()  # noqa: E712
    order_ids = session.exec(select(OrderItem.order_id).join(FoodBatch, FoodBatch.id == OrderItem.batch_id).where(FoodBatch.restaurant_id == restaurant.id).limit(100)).all()
    orders = session.exec(select(CustomerOrder).where(CustomerOrder.id.in_(order_ids), CustomerOrder.status != OrderStatus.deleted).order_by(CustomerOrder.created_at.desc()).limit(50)).all() if order_ids else []
    session.commit()
    return RestaurantDashboard(restaurant=restaurant, products=products, current_batches=batches, recent_orders=orders)


@router.patch('/me', response_model=RestaurantRead)
def update_my_restaurant(payload: RestaurantUpdate, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, key, value)
    _log(session, user.id, restaurant.id, 'restaurant.updated', 'restaurant', restaurant.id)
    session.add(restaurant); session.commit(); session.refresh(restaurant)
    return restaurant


@router.get('/{restaurant_id}', response_model=RestaurantRead)
def get_restaurant(restaurant_id: int, session: Session = Depends(get_session)):
    restaurant = session.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail='restaurant not found')
    return restaurant


@router.get('/{restaurant_id}/products', response_model=ProductList)
def list_products(restaurant_id: int, limit: int = Query(default=50, ge=1, le=100), session: Session = Depends(get_session)):
    items = session.exec(select(RestaurantProduct).where(RestaurantProduct.restaurant_id == restaurant_id, RestaurantProduct.active == True).order_by(RestaurantProduct.name.asc()).limit(limit)).all()  # noqa: E712
    return ProductList(items=items, next_cursor=None)


@router.post('/{restaurant_id}/products', response_model=ProductRead, status_code=201)
def create_product(restaurant_id: int, payload: ProductCreate, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user, restaurant_id)
    product = RestaurantProduct(restaurant_id=restaurant.id, **payload.model_dump())
    session.add(product); session.commit(); session.refresh(product)
    _log(session, user.id, restaurant.id, 'product.created', 'product', product.id, product.name)
    session.commit()
    return product


@router.patch('/{restaurant_id}/products/{product_id}', response_model=ProductRead)
def update_product(restaurant_id: int, product_id: int, payload: ProductUpdate, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user, restaurant_id)
    product = session.get(RestaurantProduct, product_id)
    if not product or product.restaurant_id != restaurant.id:
        raise HTTPException(status_code=404, detail='product not found')
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    product.updated_at = datetime.now(timezone.utc)
    _log(session, user.id, restaurant.id, 'product.updated', 'product', product.id)
    session.add(product); session.commit(); session.refresh(product)
    return product


@router.delete('/{restaurant_id}/products/{product_id}', status_code=204)
def delete_product(restaurant_id: int, product_id: int, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user, restaurant_id)
    product = session.get(RestaurantProduct, product_id)
    if not product or product.restaurant_id != restaurant.id:
        raise HTTPException(status_code=404, detail='product not found')
    product.active = False
    product.updated_at = datetime.now(timezone.utc)
    _log(session, user.id, restaurant.id, 'product.deleted', 'product', product.id)
    session.add(product); session.commit()
    return None


@router.get('/{restaurant_id}/batches', response_model=BatchList)
def restaurant_batches(restaurant_id: int, limit: int = Query(default=50, ge=1, le=100), session: Session = Depends(get_session)):
    batches = session.exec(select(FoodBatch).where(FoodBatch.restaurant_id == restaurant_id, FoodBatch.status != BatchStatus.deleted).order_by(FoodBatch.expires_at.asc()).limit(limit)).all()
    for batch in batches:
        apply_price_decay(batch)
        session.add(batch)
    session.commit()
    return BatchList(items=batches, next_cursor=None)


@router.get('/{restaurant_id}/orders', response_model=OrderList)
def restaurant_orders(restaurant_id: int, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user, restaurant_id)
    order_ids = session.exec(select(OrderItem.order_id).join(FoodBatch, FoodBatch.id == OrderItem.batch_id).where(FoodBatch.restaurant_id == restaurant.id).limit(200)).all()
    orders = session.exec(select(CustomerOrder).where(CustomerOrder.id.in_(order_ids), CustomerOrder.status != OrderStatus.deleted).order_by(CustomerOrder.created_at.desc()).limit(100)).all() if order_ids else []
    return OrderList(items=orders, next_cursor=None)


@router.post('/{restaurant_id}/orders/{order_id}/confirm-payment', response_model=PaymentRead)
def confirm_payment(restaurant_id: int, order_id: int, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user, restaurant_id)
    item = session.exec(select(OrderItem).join(FoodBatch, FoodBatch.id == OrderItem.batch_id).where(OrderItem.order_id == order_id, FoodBatch.restaurant_id == restaurant.id)).first()
    if not item:
        raise HTTPException(status_code=404, detail='order not found for this restaurant')
    order = session.get(CustomerOrder, order_id)
    if not order or order.status == OrderStatus.deleted:
        raise HTTPException(status_code=404, detail='order not found')
    payment = session.exec(select(PaymentTransaction).where(PaymentTransaction.order_id == order.id)).first()
    if not payment:
        payment = PaymentTransaction(order_id=order.id, restaurant_id=restaurant.id, amount_kzt=order.total_kzt)
    if payment.status == PaymentStatus.confirmed:
        return payment
    payment.status = PaymentStatus.confirmed
    payment.confirmed_by_user_id = user.id
    payment.confirmed_at = datetime.now(timezone.utc)
    order.status = OrderStatus.paid
    order.updated_at = datetime.now(timezone.utc)
    _log(session, user.id, restaurant.id, 'payment.confirmed', 'order', order.id, f'{order.total_kzt} KZT')
    session.add(payment); session.add(order); session.commit(); session.refresh(payment)
    return payment


@router.get('/{restaurant_id}/operations', response_model=list[RestaurantOperationRead])
def restaurant_operations(restaurant_id: int, user: User = Depends(require_roles(UserRole.restaurant_manager, UserRole.admin)), session: Session = Depends(get_session)):
    restaurant = _owned_restaurant(session, user, restaurant_id)
    return session.exec(select(RestaurantOperationLog).where(RestaurantOperationLog.restaurant_id == restaurant.id).order_by(RestaurantOperationLog.created_at.desc()).limit(100)).all()
