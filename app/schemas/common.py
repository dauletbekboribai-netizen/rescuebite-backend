from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.domain import UserRole, Allergen, BatchState, BatchStatus, OrderStatus, ClaimStatus, RouteStatus, VerificationStatus, ProductStatus, PaymentStatus


class ErrorResponse(BaseModel):
    code: str
    message: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.consumer

    @field_validator('password')
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError('password must contain at least one uppercase letter and one digit')
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    username: str
    role: UserRole
    status: str
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=80)


class AddressCreate(BaseModel):
    label: str = Field(max_length=80)
    city: str
    street: str
    lat: float
    lng: float


class AddressRead(AddressCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AllergyUpdate(BaseModel):
    allergens: list[Allergen]


class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    allergen: Optional[Allergen] = None


class AllergyCheckRequest(BaseModel):
    ingredients: list[IngredientIn]


class AllergyCheckResponse(BaseModel):
    safe: bool
    conflicts: list[Allergen]


class BatchCreate(BaseModel):
    title: str
    description: str = ''
    category: str
    quantity_total: int = Field(gt=0)
    original_price_kzt: int = Field(ge=0)
    expires_at: datetime
    pickup_start_at: datetime
    pickup_end_at: datetime
    lat: float
    lng: float
    ingredients: list[IngredientIn]


class BatchUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    quantity_total: Optional[int] = Field(default=None, gt=0)
    original_price_kzt: Optional[int] = Field(default=None, ge=0)
    expires_at: Optional[datetime] = None
    pickup_start_at: Optional[datetime] = None
    pickup_end_at: Optional[datetime] = None
    status: Optional[BatchStatus] = None


class BatchRead(BaseModel):
    id: int
    restaurant_id: int
    title: str
    category: str
    quantity_total: int
    quantity_available: int
    original_price_kzt: int
    current_price_kzt: int
    discount_percentage: int
    state: BatchState
    status: BatchStatus
    expires_at: datetime
    expires_in_seconds: int
    sale_label: str
    lat: float
    lng: float
    model_config = ConfigDict(from_attributes=True)


class BatchList(BaseModel):
    items: list[BatchRead]
    next_cursor: Optional[str] = None


class ReservationCreate(BaseModel):
    batch_id: int
    quantity: int = Field(gt=0)


class ReservationRead(BaseModel):
    id: int
    batch_id: int
    quantity: int
    status: str
    expires_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    reservation_id: int
    payment_method: str = Field(default='manual_on_pickup', max_length=80)


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None


class OrderRead(BaseModel):
    id: int
    user_id: int
    reservation_id: Optional[int]
    total_kzt: int
    status: OrderStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderList(BaseModel):
    items: list[OrderRead]
    next_cursor: Optional[str] = None


class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=255)
    cuisine_type: Optional[str] = Field(default=None, max_length=80)
    opening_hours: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = Field(default=None, max_length=200)
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_open: Optional[bool] = None


class RestaurantRead(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str
    phone: str
    email: str
    cuisine_type: str
    opening_hours: str
    city: str
    address: str
    lat: float
    lng: float
    is_open: bool
    verification_status: VerificationStatus
    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=1000)
    category: str = Field(min_length=1, max_length=80)
    base_price_kzt: int = Field(ge=0)
    status: ProductStatus = ProductStatus.active


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    base_price_kzt: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    status: Optional[ProductStatus] = None


class ProductRead(BaseModel):
    id: int
    restaurant_id: int
    name: str
    description: str
    category: str
    base_price_kzt: int
    active: bool
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProductList(BaseModel):
    items: list[ProductRead]
    next_cursor: Optional[str] = None


class PaymentRead(BaseModel):
    id: int
    order_id: int
    restaurant_id: int
    amount_kzt: int
    provider: str
    status: PaymentStatus
    confirmed_by_user_id: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RestaurantOperationRead(BaseModel):
    id: int
    restaurant_id: int
    actor_user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[int]
    details: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RestaurantDashboard(BaseModel):
    restaurant: RestaurantRead
    products: list[ProductRead]
    current_batches: list[BatchRead]
    recent_orders: list[OrderRead]


class DonationClaimCreate(BaseModel):
    batch_id: int
    quantity: int = Field(gt=0)


class DonationClaimUpdate(BaseModel):
    status: Optional[ClaimStatus] = None


class DonationClaimRead(BaseModel):
    id: int
    shelter_id: int
    batch_id: int
    quantity: int
    status: ClaimStatus
    model_config = ConfigDict(from_attributes=True)


class RouteAssignmentUpdate(BaseModel):
    status: Optional[RouteStatus] = None

class RouteStopRead(BaseModel):
    id: int
    assignment_id: int
    batch_id: Optional[int] = None
    kind: str
    sequence: int
    address: str
    lat: float
    lng: float
    status: str
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RouteAssignmentRead(BaseModel):
    id: int
    driver_id: int
    status: RouteStatus
    stops: list[RouteStopRead] = []

    model_config = ConfigDict(from_attributes=True)


class RouteStopComplete(BaseModel):
    lat: float
    lng: float
    note: Optional[str] = None


class VerificationRequest(BaseModel):
    entity_type: str = Field(pattern='^(restaurant|shelter|driver)$')
    entity_id: int
    approved: bool
    reason: Optional[str] = None

class RouteStopCreate(BaseModel):
    batch_id: Optional[int] = None
    kind: str
    sequence: int
    address: str
    lat: float
    lng: float


class RouteAssignmentCreate(BaseModel):
    driver_id: int
    stops: list[RouteStopCreate]
