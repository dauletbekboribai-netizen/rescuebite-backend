# Changelog

## 1.0.0

- Implemented FastAPI project bootstrap.
- Added SQLModel database schema and Alembic baseline migration.
- Added JWT authentication with refresh token storage and logout revocation.
- Added RBAC-protected endpoints for users, batches, orders, donations, routes, and admin verification.
- Added RescueBite core logic for price decay, allergy validation, and Redis-assisted reservations.
- Added Docker Compose, tests, and CI workflow.

## 1.1.0

- Added dedicated restaurant operations API under `/restaurants`.
- Added editable restaurant profile fields: description, phone, email, cuisine type, opening hours, open/closed state.
- Added `RestaurantProduct` catalog CRUD with soft delete.
- Added restaurant dashboard combining profile, current products, active/expiring batches, and recent orders.
- Added inventory expiry timer fields on batch responses: `expires_in_seconds` and `sale_label` (`fresh`, `discounted`, `free`, `expired`).
- Added manual seller-confirmed payment flow through `PaymentTransaction` and `/restaurants/{restaurant_id}/orders/{order_id}/confirm-payment`.
- Changed newly created customer orders to start as `pending_payment`; seller confirmation advances them to `paid`.
- Added restaurant operation audit log endpoint.
- Regenerated `openapi.yaml` with 33 documented paths.
