from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models.domain import Restaurant, VerificationStatus

client = TestClient(app)


def setup_module():
    create_db_and_tables()


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def register(email, username, role):
    return client.post('/auth/register', json={'email': email, 'username': username, 'password': 'Strong123', 'role': role})


def login(email):
    res = client.post('/auth/login', json={'email': email, 'password': 'Strong123'})
    return res.json()['access_token']


def test_restaurant_product_crud_and_payment_confirmation():
    suffix = unique_name('rest')
    email = f'{suffix}@example.com'
    register(email, suffix, 'restaurant_manager')
    token = login(email)
    headers = {'Authorization': f'Bearer {token}'}

    with Session(engine) as session:
        restaurant = session.exec(select(Restaurant).where(Restaurant.email == '')).all()[-1]
        restaurant.verification_status = VerificationStatus.verified
        restaurant.name = 'Verified Rescue Cafe'
        restaurant.email = email
        session.add(restaurant)
        session.commit()
        restaurant_id = restaurant.id

    created = client.post(f'/restaurants/{restaurant_id}/products', headers=headers, json={
        'name': 'Chicken wrap', 'description': 'Daily menu item', 'category': 'meal', 'base_price_kzt': 1800
    })
    assert created.status_code == 201
    product_id = created.json()['id']

    patched = client.patch(f'/restaurants/{restaurant_id}/products/{product_id}', headers=headers, json={'base_price_kzt': 1500})
    assert patched.status_code == 200
    assert patched.json()['base_price_kzt'] == 1500

    batch = client.post('/batches', headers=headers, json={
        'title': 'Wrap rescue box',
        'description': 'Safe same-day food',
        'category': 'meal',
        'quantity_total': 2,
        'original_price_kzt': 1800,
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        'pickup_start_at': datetime.now(timezone.utc).isoformat(),
        'pickup_end_at': (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        'lat': 43.2,
        'lng': 76.8,
        'ingredients': [{'name': 'tortilla', 'allergen': 'gluten'}]
    })
    assert batch.status_code == 201

    buyer = unique_name('buyer')
    buyer_email = f'{buyer}@example.com'
    register(buyer_email, buyer, 'consumer')
    buyer_token = login(buyer_email)
    buyer_headers = {'Authorization': f'Bearer {buyer_token}'}
    reservation = client.post('/orders/reservations', headers=buyer_headers, json={'batch_id': batch.json()['id'], 'quantity': 1})
    assert reservation.status_code == 201
    order = client.post('/orders', headers=buyer_headers, json={'reservation_id': reservation.json()['id'], 'payment_method': 'cash_on_pickup'})
    assert order.status_code == 201
    assert order.json()['status'] == 'pending_payment'

    payment = client.post(f'/restaurants/{restaurant_id}/orders/{order.json()["id"]}/confirm-payment', headers=headers)
    assert payment.status_code == 200
    assert payment.json()['status'] == 'confirmed'

    deleted = client.delete(f'/restaurants/{restaurant_id}/products/{product_id}', headers=headers)
    assert deleted.status_code == 204
