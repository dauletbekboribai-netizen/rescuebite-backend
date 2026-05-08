# Architecture

## Overview

The backend uses a layered FastAPI structure. Routers expose HTTP endpoints, schemas validate request and response bodies, services contain domain rules, and SQLModel models define the database schema. PostgreSQL is the source of truth for durable data. Redis is used for rate limiting and temporary reservation counters.

## Environment validation

Configuration is loaded through Pydantic Settings. The app refuses to start without a database URL, Redis URL, JWT signing secrets, and explicit CORS origins. Wildcard CORS is rejected.

## Authentication and authorization

Passwords are stored using bcrypt hashes. Login issues a short-lived access token and a longer-lived refresh token. Refresh tokens are stored as SHA-256 hashes in the database and can be revoked on logout. Protected endpoints use Bearer JWT authentication. Role checks return `403 Forbidden` when a valid user lacks permission.

## RescueBite domain logic

Food batches move through the following lifecycle:

```text
fresh -> discounted -> free -> compost
```

Price decay is implemented in application logic because pricing thresholds are business policy and may change. The database stores the resulting state, current price, and discount percentage. This keeps state transitions auditable without embedding changing business policy inside database triggers.

Allergen integrity is handled by enums in both Pydantic schemas and SQLModel database columns. A user allergy profile is compared against batch ingredient allergens before reservation or checkout. Conflicting purchases are blocked by the backend.

## Geospatial strategy

The schema stores latitude and longitude for restaurants, shelters, drivers, route stops, and food batches. The current implementation uses indexed `lat` and `lng` columns and can apply Haversine calculations at service level. For larger production datasets, this design can be migrated to PostGIS with a geography column and a GiST index.

## Redis usage

Redis is used for:

- login and registration rate limiting;
- temporary reservation counters with TTL;
- future background worker coordination.

PostgreSQL remains the durable source of truth. Redis data is temporary and never treated as the only permanent record.

## Migrations

Alembic provides the baseline migration. The migration imports SQLModel metadata and creates the tables defined by the models. Future schema changes should be added as forward-only migrations and tested against PostgreSQL before deployment.

## Restaurant operations module

The restaurant module is intentionally separate from the public batch marketplace. It gives a restaurant manager one operational surface for:

- restaurant profile and operating details;
- product/menu catalog management;
- current expiring food batches;
- incoming orders;
- manual seller-confirmed payments;
- append-only restaurant operation logs.

Product catalog data lives in `restaurant_products`, while rescue inventory remains in `food_batches`. This keeps the regular menu separate from time-sensitive rescue offers.

## Expiry timer and sale status

Every `FoodBatch` exposes computed response fields:

- `expires_in_seconds` is calculated from `expires_at` at response time;
- `sale_label` normalizes the price decay state for client UI: `fresh`, `discounted`, `free`, or `expired`.

The authoritative state machine is still `fresh -> discounted -> free -> compost`. API handlers call `apply_price_decay()` before returning or mutating batch inventory.

## Manual payment confirmation

Real payment acquisition is intentionally not integrated. Instead, order creation produces a `PaymentTransaction` with status `pending_seller_confirmation`. The restaurant manager confirms receipt using the restaurant order endpoint. Confirmation sets the payment to `confirmed` and moves the order from `pending_payment` to `paid`. This models cash, Kaspi transfer, or POS-terminal confirmation without storing card data.

## Route optimization pseudocode

For production pickup batching, RescueBite should use a TSP-lite nearest-neighbor heuristic first, then improve with a local 2-opt pass:

```text
input: driver location, candidate pickup/dropoff stops, capacity, pickup windows
filter stops by verified restaurant, active stock, non-expired pickup window
score each stop by distance + expiry urgency + promised pickup window penalty
route = [driver_start]
while unvisited stops exist:
    choose feasible stop with minimum score from current location
    append stop to route
    update capacity and current time
run 2-opt swaps while total distance decreases and time windows remain valid
return route
```

The current schema uses indexed latitude/longitude columns and can run Haversine distance calculations at service level. At larger volume, the same data model can migrate to PostGIS geography columns with GiST indexes for radius queries and distance ordering.
