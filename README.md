# RescueBite Backend

RescueBite is a FastAPI backend for reducing food waste through discounted food batches, allergy-safe checkout, donation claims, and driver route assignments.

## Stack

- FastAPI
- SQLModel
- PostgreSQL 15
- Redis
- Alembic
- Pytest
- Docker Compose

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

Open API docs:

```text
http://localhost:8000/docs
```

## Main implemented flows

- Registration with password validation and unique email/username.
- Login with bcrypt password verification.
- JWT access tokens and refresh tokens.
- Logout by refresh token revocation.
- Role-based access control for restaurant, shelter, driver, and admin endpoints.
- Redis-backed rate limiting for login and registration.
- Food batch lifecycle: fresh, discounted, free, compost.
- Allergy profile storage and ingredient validation.
- Redis-assisted stock reservation before checkout.
- Cursor pagination for list endpoints.

## Useful demo order

1. Register a consumer.
2. Login and copy the access token.
3. Use Authorize in Swagger UI with `Bearer <access_token>`.
4. Set allergies with `PUT /users/me/allergies`.
5. Register an admin as the first admin account if verification operations are needed.
6. Register restaurant, shelter, and driver accounts for RBAC testing.
7. Create batches with a verified restaurant or an admin token.
8. Create a reservation with `POST /orders/reservations`.
9. Convert the reservation into an order with `POST /orders`.

## Tests

```bash
pytest
```

## Lint

```bash
ruff check app tests
```

roles:

consumer
restaurant_manager
shelter_coordinator
driver
admin

---

allergens:

peanuts
tree_nuts
dairy
eggs
gluten
soy
fish
shellfish
sesame

---

Batch state:

fresh
discounted
free
compost

---

claim status:

pending
approved
received
cancelled
deleted

---

Order status:

paid
prepared
ready_for_pickup
in_transit
completed
cancelled
deleted

---

Route status:

proposed
accepted
in_progress
completed
cancelled
deleted

docker compose exec api pytest -v
## Restaurant operations added in v1.1

Restaurant managers now have a dedicated operational section:

- `GET /restaurants/me` — dashboard with restaurant info, products, current batches, and recent orders.
- `PATCH /restaurants/me` — update restaurant profile, contact info, cuisine type, working hours, location, and open/closed state.
- `GET /restaurants/{restaurant_id}` — public restaurant profile.
- `GET /restaurants/{restaurant_id}/products` — public active menu/product catalog.
- `POST /restaurants/{restaurant_id}/products` — add a product/menu item.
- `PATCH /restaurants/{restaurant_id}/products/{product_id}` — edit a product/menu item.
- `DELETE /restaurants/{restaurant_id}/products/{product_id}` — soft-delete a product/menu item.
- `GET /restaurants/{restaurant_id}/batches` — restaurant rescue inventory with expiry timer fields.
- `GET /restaurants/{restaurant_id}/orders` — restaurant order list.
- `POST /restaurants/{restaurant_id}/orders/{order_id}/confirm-payment` — seller confirms manual payment; order continues from `pending_payment` to `paid`.
- `GET /restaurants/{restaurant_id}/operations` — audit log of restaurant-side operations.

Batch responses now include:

- `expires_in_seconds` — live countdown value for API clients.
- `sale_label` — one of `fresh`, `discounted`, `free`, `expired`.

Payment is modeled without real card processing. When a customer creates an order, the order starts as `pending_payment` and a `PaymentTransaction` starts as `pending_seller_confirmation`. Once the seller confirms receipt, payment becomes `confirmed` and the order becomes `paid`.

## Contract

The OpenAPI contract is exported to `openapi.yaml` and covers all implemented endpoints.
