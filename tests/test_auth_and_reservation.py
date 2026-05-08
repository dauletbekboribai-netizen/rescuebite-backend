from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models.domain import FoodBatch, Restaurant, User, VerificationStatus

client = TestClient(app)


def setup_module():
    create_db_and_tables()


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def register(email, username, role='consumer'):
    return client.post('/auth/register', json={'email': email, 'username': username, 'password': 'Strong123', 'role': role})


def login(email):
    res = client.post('/auth/login', json={'email': email, 'password': 'Strong123'})
    return res.json()['access_token']


def test_auth_protected_endpoint_and_rbac():
    assert client.get('/users/me').status_code == 401
    suffix = unique_name('rbac')
    email = f'{suffix}@example.com'
    username = suffix
    register(email, username)
    token = login(email)
    assert client.get('/users/me', headers={'Authorization': f'Bearer {token}'}).status_code == 200
    denied = client.post('/batches', headers={'Authorization': f'Bearer {token}'}, json={})
    assert denied.status_code in (403, 422)


def test_reservation_prevents_overselling():
    suffix = unique_name('buyer')
    email = f'{suffix}@example.com'
    username = suffix
    register(email, username)
    token = login(email)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        restaurant = Restaurant(
            owner_id=user.id,
            name='Test Cafe',
            address='Abay 1',
            lat=43.2,
            lng=76.8,
            verification_status=VerificationStatus.verified,
        )
        session.add(restaurant)
        session.commit()
        session.refresh(restaurant)
        batch = FoodBatch(
            restaurant_id=restaurant.id,
            title='Salad',
            category='meal',
            quantity_total=1,
            quantity_available=1,
            original_price_kzt=1000,
            current_price_kzt=1000,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=3),
            pickup_start_at=datetime.now(timezone.utc),
            pickup_end_at=datetime.now(timezone.utc) + timedelta(hours=3),
            lat=43.2,
            lng=76.8,
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        batch_id = batch.id
    headers = {'Authorization': f'Bearer {token}'}
    first = client.post('/orders/reservations', headers=headers, json={'batch_id': batch_id, 'quantity': 1})
    assert first.status_code == 201
    second = client.post('/orders/reservations', headers=headers, json={'batch_id': batch_id, 'quantity': 1})
    assert second.status_code == 409
