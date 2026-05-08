import enum
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship, Column
from sqlalchemy import Enum as SAEnum, CheckConstraint, UniqueConstraint, Index


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    consumer = 'consumer'
    restaurant_manager = 'restaurant_manager'
    shelter_coordinator = 'shelter_coordinator'
    driver = 'driver'
    admin = 'admin'


class AccountStatus(str, enum.Enum):
    active = 'active'
    suspended = 'suspended'


class Allergen(str, enum.Enum):
    peanuts = 'peanuts'
    tree_nuts = 'tree_nuts'
    dairy = 'dairy'
    eggs = 'eggs'
    gluten = 'gluten'
    soy = 'soy'
    fish = 'fish'
    shellfish = 'shellfish'
    sesame = 'sesame'


class BatchState(str, enum.Enum):
    fresh = "fresh"
    discounted = "discounted"
    free = "free"
    compost = "compost"


class BatchStatus(str, enum.Enum):
    active = 'active'
    paused = 'paused'
    withdrawn = 'withdrawn'
    deleted = 'deleted'


class ReservationStatus(str, enum.Enum):
    active = 'active'
    cancelled = 'cancelled'
    converted = 'converted'
    expired = 'expired'


class OrderStatus(str, enum.Enum):
    pending_payment = 'pending_payment'
    paid = 'paid'
    prepared = 'prepared'
    ready_for_pickup = 'ready_for_pickup'
    in_transit = 'in_transit'
    completed = 'completed'
    cancelled = 'cancelled'
    deleted = 'deleted'


class ClaimStatus(str, enum.Enum):
    pending = 'pending'
    approved = 'approved'
    received = 'received'
    cancelled = 'cancelled'
    deleted = 'deleted'


class RouteStatus(str, enum.Enum):
    proposed = 'proposed'
    accepted = 'accepted'
    in_progress = 'in_progress'
    completed = 'completed'
    cancelled = 'cancelled'
    deleted = 'deleted'


class StopStatus(str, enum.Enum):
    pending = 'pending'
    completed = 'completed'
    failed = 'failed'


class VerificationStatus(str, enum.Enum):
    pending = 'pending'
    verified = 'verified'
    rejected = 'rejected'


class ProductStatus(str, enum.Enum):
    draft = 'draft'
    active = 'active'
    archived = 'archived'


class PaymentStatus(str, enum.Enum):
    pending_seller_confirmation = 'pending_seller_confirmation'
    confirmed = 'confirmed'
    rejected = 'rejected'
    refunded = 'refunded'


class User(SQLModel, table=True):
    __tablename__ = 'users'
    __table_args__ = (Index('ix_users_role_status', 'role', 'status'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    username: str = Field(index=True, unique=True, max_length=80)
    password_hash: str = Field(max_length=255)
    role: UserRole = Field(sa_column=Column(SAEnum(UserRole, name='user_role'), nullable=False, index=True))
    status: AccountStatus = Field(default=AccountStatus.active, sa_column=Column(SAEnum(AccountStatus, name='account_status'), nullable=False))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class RefreshToken(SQLModel, table=True):
    __tablename__ = 'refresh_tokens'
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)
    token_hash: str = Field(index=True, unique=True, max_length=128)
    revoked: bool = Field(default=False, index=True)
    expires_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Address(SQLModel, table=True):
    __tablename__ = 'addresses'
    __table_args__ = (Index('ix_addresses_user_created', 'user_id', 'created_at'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)
    label: str = Field(max_length=80)
    city: str = Field(max_length=80)
    street: str = Field(max_length=160)
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class UserAllergy(SQLModel, table=True):
    __tablename__ = 'user_allergies'
    __table_args__ = (UniqueConstraint('user_id', 'allergen', name='uq_user_allergen'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)
    allergen: Allergen = Field(sa_column=Column(SAEnum(Allergen, name='allergen'), nullable=False, index=True))


class Restaurant(SQLModel, table=True):
    __tablename__ = 'restaurants'
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key='users.id', index=True)
    name: str = Field(max_length=120)
    description: str = Field(default='', max_length=1000)
    phone: str = Field(default='', max_length=40)
    email: str = Field(default='', max_length=255)
    cuisine_type: str = Field(default='mixed', max_length=80, index=True)
    opening_hours: str = Field(default='09:00-21:00', max_length=200)
    is_open: bool = Field(default=True, index=True)
    city: str = Field(default='Almaty', max_length=80)
    address: str = Field(max_length=200)
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    verification_status: VerificationStatus = Field(default=VerificationStatus.pending, sa_column=Column(SAEnum(VerificationStatus, name='verification_status'), nullable=False, index=True))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class RestaurantProduct(SQLModel, table=True):
    __tablename__ = 'restaurant_products'
    __table_args__ = (
        CheckConstraint('base_price_kzt >= 0', name='ck_product_base_price_nonnegative'),
        Index('ix_products_restaurant_active', 'restaurant_id', 'active'),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key='restaurants.id', index=True)
    name: str = Field(max_length=160, index=True)
    description: str = Field(default='', max_length=1000)
    category: str = Field(max_length=80, index=True)
    base_price_kzt: int = Field(ge=0)
    active: bool = Field(default=True, index=True)
    status: ProductStatus = Field(default=ProductStatus.active, sa_column=Column(SAEnum(ProductStatus, name='product_status'), nullable=False, index=True))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class RestaurantOperationLog(SQLModel, table=True):
    __tablename__ = 'restaurant_operation_logs'
    __table_args__ = (Index('ix_restaurant_ops_restaurant_created', 'restaurant_id', 'created_at'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key='restaurants.id', index=True)
    actor_user_id: Optional[int] = Field(default=None, foreign_key='users.id', index=True)
    action: str = Field(max_length=120, index=True)
    entity_type: str = Field(max_length=80, index=True)
    entity_id: Optional[int] = Field(default=None, index=True)
    details: str = Field(default='', max_length=2000)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Shelter(SQLModel, table=True):
    __tablename__ = 'shelters'
    id: Optional[int] = Field(default=None, primary_key=True)
    coordinator_id: int = Field(foreign_key='users.id', index=True, unique=True)
    name: str = Field(max_length=120)
    capacity_units: int = Field(default=100, ge=0)
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    verification_status: VerificationStatus = Field(default=VerificationStatus.pending, sa_column=Column(SAEnum(VerificationStatus, name='verification_status'), nullable=False, index=True))


class DriverProfile(SQLModel, table=True):
    __tablename__ = 'driver_profiles'
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True, unique=True)
    available: bool = Field(default=True, index=True)
    lat: float = Field(default=43.238949, index=True)
    lng: float = Field(default=76.889709, index=True)
    verification_status: VerificationStatus = Field(default=VerificationStatus.pending, sa_column=Column(SAEnum(VerificationStatus, name='verification_status'), nullable=False, index=True))


class FoodBatch(SQLModel, table=True):
    __tablename__ = 'food_batches'
    __table_args__ = (
        CheckConstraint('quantity_total >= 0', name='ck_batch_quantity_total_nonnegative'),
        CheckConstraint('quantity_available >= 0', name='ck_batch_quantity_available_nonnegative'),
        CheckConstraint('original_price_kzt >= 0', name='ck_batch_original_price_nonnegative'),
        CheckConstraint('current_price_kzt >= 0', name='ck_batch_current_price_nonnegative'),
        CheckConstraint('discount_percentage >= 0 AND discount_percentage <= 100', name='ck_batch_discount_range'),
        Index('ix_batches_status_state_expiry', 'status', 'state', 'expires_at'),
        Index('ix_batches_geo', 'lat', 'lng'),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key='restaurants.id', index=True)
    title: str = Field(max_length=160, index=True)
    description: str = Field(default='', max_length=1000)
    category: str = Field(max_length=80, index=True)
    quantity_total: int
    quantity_available: int
    original_price_kzt: int
    current_price_kzt: int
    discount_percentage: int = Field(default=0)
    state: BatchState = Field(default=BatchState.fresh, sa_column=Column(SAEnum(BatchState, name='batch_state'), nullable=False, index=True))
    status: BatchStatus = Field(default=BatchStatus.active, sa_column=Column(SAEnum(BatchStatus, name='batch_status'), nullable=False, index=True))
    expires_at: datetime = Field(index=True)
    pickup_start_at: datetime
    pickup_end_at: datetime
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def expires_in_seconds(self) -> int:
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return max(int((expires - datetime.now(timezone.utc)).total_seconds()), 0)

    @property
    def sale_label(self) -> str:
        labels = {
            BatchState.fresh: 'fresh',
            BatchState.discounted: 'discounted',
            BatchState.free: 'free',
            BatchState.compost: 'expired',
        }
        return labels.get(self.state, 'fresh')


class BatchIngredient(SQLModel, table=True):
    __tablename__ = 'batch_ingredients'
    __table_args__ = (Index('ix_batch_ingredients_batch_allergen', 'batch_id', 'allergen'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key='food_batches.id', index=True)
    name: str = Field(max_length=120, index=True)
    allergen: Optional[Allergen] = Field(default=None, sa_column=Column(SAEnum(Allergen, name='allergen'), nullable=True, index=True))


class Reservation(SQLModel, table=True):
    __tablename__ = 'reservations'
    __table_args__ = (Index('ix_reservation_user_status', 'user_id', 'status'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)
    batch_id: int = Field(foreign_key='food_batches.id', index=True)
    quantity: int = Field(gt=0)
    status: ReservationStatus = Field(default=ReservationStatus.active, sa_column=Column(SAEnum(ReservationStatus, name='reservation_status'), nullable=False, index=True))
    expires_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class CustomerOrder(SQLModel, table=True):
    __tablename__ = 'customer_orders'
    __table_args__ = (Index('ix_orders_user_status_created', 'user_id', 'status', 'created_at'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='users.id', index=True)
    reservation_id: Optional[int] = Field(default=None, foreign_key='reservations.id', index=True)
    total_kzt: int = Field(default=0)
    status: OrderStatus = Field(default=OrderStatus.paid, sa_column=Column(SAEnum(OrderStatus, name='order_status'), nullable=False, index=True))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class OrderItem(SQLModel, table=True):
    __tablename__ = 'order_items'
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key='customer_orders.id', index=True)
    batch_id: int = Field(foreign_key='food_batches.id', index=True)
    quantity: int = Field(gt=0)
    unit_price_kzt: int = Field(ge=0)


class PaymentTransaction(SQLModel, table=True):
    __tablename__ = 'payment_transactions'
    __table_args__ = (
        CheckConstraint('amount_kzt >= 0', name='ck_payment_amount_nonnegative'),
        Index('ix_payment_order_status', 'order_id', 'status'),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key='customer_orders.id', index=True, unique=True)
    restaurant_id: int = Field(foreign_key='restaurants.id', index=True)
    amount_kzt: int = Field(default=0)
    provider: str = Field(default='manual_seller_confirmation', max_length=80)
    status: PaymentStatus = Field(default=PaymentStatus.pending_seller_confirmation, sa_column=Column(SAEnum(PaymentStatus, name='payment_status'), nullable=False, index=True))
    confirmed_by_user_id: Optional[int] = Field(default=None, foreign_key='users.id', index=True)
    confirmed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class DonationClaim(SQLModel, table=True):
    __tablename__ = 'donation_claims'
    __table_args__ = (Index('ix_claim_shelter_status', 'shelter_id', 'status'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    shelter_id: int = Field(foreign_key='shelters.id', index=True)
    batch_id: int = Field(foreign_key='food_batches.id', index=True)
    quantity: int = Field(gt=0)
    status: ClaimStatus = Field(default=ClaimStatus.pending, sa_column=Column(SAEnum(ClaimStatus, name='claim_status'), nullable=False, index=True))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    received_at: Optional[datetime] = None


class RouteAssignment(SQLModel, table=True):
    __tablename__ = 'route_assignments'
    id: Optional[int] = Field(default=None, primary_key=True)
    driver_id: int = Field(foreign_key='users.id', index=True)
    status: RouteStatus = Field(default=RouteStatus.proposed, sa_column=Column(SAEnum(RouteStatus, name='route_status'), nullable=False, index=True))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class RouteStop(SQLModel, table=True):
    __tablename__ = 'route_stops'
    __table_args__ = (Index('ix_stops_assignment_sequence', 'assignment_id', 'sequence'),)
    id: Optional[int] = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key='route_assignments.id', index=True)
    batch_id: Optional[int] = Field(default=None, foreign_key='food_batches.id')
    kind: str = Field(max_length=20)
    sequence: int = Field(index=True)
    address: str = Field(max_length=200)
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    status: StopStatus = Field(default=StopStatus.pending, sa_column=Column(SAEnum(StopStatus, name='stop_status'), nullable=False, index=True))
    completed_at: Optional[datetime] = None


class AuditLog(SQLModel, table=True):
    __tablename__ = 'audit_logs'
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, foreign_key='users.id', index=True)
    action: str = Field(max_length=120, index=True)
    entity_type: str = Field(max_length=80, index=True)
    entity_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    details: str = Field(default='', max_length=2000)
