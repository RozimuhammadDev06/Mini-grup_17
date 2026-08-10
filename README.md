<div align="center">

# 🧱 Stroyopttorg — Backend

**Production-ready REST API for a building-materials store & marketplace**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.18-A30000?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

[![Tests](https://img.shields.io/badge/tests-152%20passing-brightgreen)](#-testing)
[![Endpoints](https://img.shields.io/badge/endpoints-163%20operations-blue)](#-api-reference)
[![Docs](https://img.shields.io/badge/OpenAPI-Swagger%20%2B%20ReDoc-85EA2D?logo=swagger&logoColor=black)](#-api-documentation)

</div>

---

## 📖 Overview

A modular Django + DRF backend covering the full storefront lifecycle: catalogue
with dynamic attribute filtering, guest & user carts, transactional checkout with
stock locking, orders, reviews, wishlists, delivery addresses, promotions and CMS
content — plus a staff management API.

| | |
|---|---|
| 🔐 **Auth** | JWT with refresh-token blacklisting, email verification, password reset |
| 🛒 **Commerce** | Guest carts, promo codes, discount tiers, atomic checkout |
| 🔎 **Catalogue** | Composable filters, search, ordering, EAV-style attributes |
| ⚡ **Performance** | Subquery aggregates, Redis caching, zero N+1 on the home page |
| 🛡️ **Security** | Deny-by-default permissions, owner-scoped querysets, rate limiting |
| 📦 **Ops** | Docker dev + prod, health checks, Celery worker & beat |

---

## 🏗️ Architecture

Two layers with a hard boundary: **`apps/` owns the domain**, **`api/` owns HTTP**.

```
src/
├── config/                 ⚙️  settings (base · development · production · test)
│   ├── celery.py               Celery app
│   └── urls.py                 root URLconf + OpenAPI routes
│
├── apps/                   🧠  DOMAIN — models, services, selectors, admin
│   ├── users/                  User, Address, OTP · auth services · email tasks
│   ├── catalog/                Category, Brand, Product, Attribute, Stock
│   ├── carts/                  Cart, CartItem, Wishlist, Compare
│   ├── orders/                 Order, OrderItem · checkout service
│   ├── discounts/              PromoCode, DiscountTier · pricing service
│   ├── reviews/                Review · rating aggregation
│   ├── content/                Article, Promotion, Banner, FAQ, StaticPage
│   ├── payments/  geo/  leads/  utils/
│   └── …
│
└── api/                    🌐  HTTP — serializers, views, filters, permissions
    ├── auth/                   register · verify · login · logout · reset
    ├── user/                   profile · addresses · orders · wishlist · reviews
    ├── catalog/                categories · brands · products · comparison
    ├── cart/                   guest + authenticated cart
    ├── content/                home · news · promotions · banners · FAQ · leads
    └── admin/                  staff-only management API
```

**Rules that keep it maintainable**

- Business logic lives in `apps/<domain>/services.py`; queries in `selectors.py`.
- Views orchestrate, they don't compute — no domain logic inside a view.
- Each audience module splits into `serializers/` and `views/` packages,
  **one responsibility per file**.
- Money is `Decimal` end to end, and every total flows through a single
  [`PricingService`](src/apps/discounts/services.py) so the cart and the order
  can never disagree.

---

## 🚀 Quick start

### Option A — Docker (recommended)

```bash
cp src/.env.example src/.env      # then edit SECRET_KEY + POSTGRES_PASSWORD
docker compose -f docker-compose.dev.yml up --build
```

Brings up Django (autoreload), PostgreSQL 16, Redis 7, a Celery worker and beat.
Migrations run automatically. → <http://localhost:8000/api/docs/>

<details>
<summary><b>Production stack</b></summary>

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Gunicorn behind nginx, multi-stage image, non-root user, `DEBUG=False`,
health checks and `restart: always`. PostgreSQL publishes **no ports** — it is
reachable only on the internal compose network.

</details>

### Option B — local virtualenv

```bash
python -m venv venv && source venv/bin/activate
pip install -r src/requirements/dev.txt

cd src
cp .env.example .env              # DB_TYPE=sqlite works with no services
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

> **Emails in development** print to the console when no SMTP credentials are
> set — the verification code appears right in your terminal.

---

## 📚 API documentation

Three OpenAPI documents, all generated from the same views so they cannot drift:

| Audience | Swagger | ReDoc | Raw schema | Ops |
|---|---|---|---|:-:|
| 🌍 **Frontend** | [`/api/docs/frontend/`](http://localhost:8000/api/docs/frontend/) | `/api/redoc/frontend/` | `/api/schema/frontend/` | 70 |
| 🛠️ Staff | `/api/docs/admin/` | `/api/redoc/admin/` | `/api/schema/admin/` | 94 |
| 📋 Everything | `/api/docs/` | `/api/redoc/` | `/api/schema/` | 163 |

**Frontend developers want `/api/docs/frontend/`** — it hides the staff API and
documents the auth flow, guest-cart behaviour, error shapes and pagination.

### Postman

Import both files from `src/`, then select the `local` environment:

```
postman-workflows.json    148 requests, organised by audience
postman-variables.json    24 variables
```

`auth → login` **stores the tokens automatically**; every other request inherits
Bearer auth from the collection.

---

## 🔌 API reference

<details open>
<summary><b>🔐 Auth</b> — <code>/api/v1/auth/</code></summary>

| Method | Endpoint | Description |
|:--|:--|:--|
| `POST` | `register/` | Create an **unverified** account, email a 6-digit code |
| `POST` | `verify/` | Consume the code, activate the account |
| `POST` | `resend-verification/` | New code; invalidates the old one |
| `POST` | `login/` | Returns `access` + `refresh`; merges the guest cart |
| `POST` | `logout/` | Blacklists the refresh token |
| `POST` | `token/refresh/` · `token/verify/` | SimpleJWT standard views |
| `POST` | `forgot-password/` → `verify-reset-code/` → `reset-password/` | Reset flow |

</details>

<details>
<summary><b>🔎 Catalog</b> — <code>/api/v1/catalog/</code> · public</summary>

| Method | Endpoint |
|:--|:--|
| `GET` | `categories/` · `categories/tree/` · `categories/{slug}/` |
| `GET` | `brands/` · `brands/{slug}/` · `attributes/?category=` |
| `GET` | `products/` · `products/{id}/` · `products/{slug}/` · `products/{slug}/related/` |
| `GET` | `products/{id}/reviews/` · `products/{id}/rating/` |
| `POST` | `products/compare/` — stateless, 2–4 products |
| `GET`/`POST`/`DELETE` | `compare/` — saved comparison (guest or user) |

**Filters compose freely:**

```http
GET /api/v1/catalog/products/?category=1&min_price=100&max_price=1000
    &brand=2&stock=true&discount=true&featured=true&rating=4
    &search=drill&attribute=power:1500&ordering=-price
```

`ordering` accepts `price`, `created_at`, `name`, `rating`, `sold_count`,
`review_count` — prefix with `-` to reverse.

</details>

<details>
<summary><b>🛒 Cart</b> — <code>/api/v1/cart/</code> · guest or authenticated</summary>

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` / `DELETE` | `/` | Fetch or empty the cart |
| `POST` | `items/` | Add — validated against stock |
| `PATCH` / `DELETE` | `items/{product_id}/` | Set quantity (`0` removes) / remove |
| `POST` / `DELETE` | `promo/` | Apply or clear a promo code |

Guests are tracked by session cookie. **Prices always come from the database** —
a price in the request body is ignored.

</details>

<details>
<summary><b>👤 User</b> — <code>/api/v1/user/</code> · 🔒 authenticated</summary>

| Method | Endpoint |
|:--|:--|
| `GET` `PATCH` | `profile/` |
| `POST` | `password/change/` |
| `GET` `POST` `PATCH` `DELETE` | `addresses/` · `addresses/{id}/` · `addresses/{id}/set-default/` |
| `GET` `POST` | `orders/` · `orders/{id}/` · `orders/{id}/cancel/` |
| `GET` `POST` `DELETE` | `wishlist/` · `wishlist/add/` · `wishlist/{id}/status/` |
| `GET` `POST` `PATCH` `DELETE` | `reviews/` · `reviews/{id}/` |

Every queryset is scoped to `request.user` — another account's id returns **404**,
never data.

</details>

<details>
<summary><b>📰 Content</b> — <code>/api/v1/</code> · public</summary>

| Method | Endpoint |
|:--|:--|
| `GET` | `home/` — aggregated landing page, Redis-cached |
| `GET` | `news/` · `news/{slug}/` · `promotions/` · `promotions/{slug}/` |
| `GET` | `banners/` · `faq/` · `pages/{slug}/` |
| `POST` | `leads/` — callback / price request / one-click buy |

</details>

<details>
<summary><b>🛠️ Admin</b> — <code>/api/v1/admin/</code> · 🔒 staff only</summary>

Full CRUD over 14 resources — `categories`, `brands`, `products`,
`product-images`, `stock`, `reviews`, `leads`, `articles`, `promotions`,
`banners`, `faq`, `pages`, `promo-codes`, `discount-tiers` — plus read/update on
`orders/` (with `orders/{id}/set-status/`) and `users/`.

Orders and users cannot be created or deleted through the API by design.

</details>

---

## 🛡️ Security

| Control | Implementation |
|---|---|
| **Deny by default** | `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; public views opt in with `AllowAny` |
| **IDOR** | Owner-scoped querysets — foreign ids 404, they never 403-and-confirm |
| **Mass assignment** | `is_staff`, `is_superuser`, `is_active`, `email` are absent from writable serializers |
| **Brute force** | Scoped throttles on login, register, OTP and password reset |
| **OTP abuse** | Single-use codes, TTL, attempt limit with lockout, resend cooldown |
| **Account enumeration** | Reset and resend return identical responses for unknown emails |
| **Password reset** | Consumes the code **and revokes every refresh token** |
| **Secrets** | Everything from env vars; `.env` has never been in git history |
| **Production** | HSTS, SSL redirect, secure cookies, `SECURE_PROXY_SSL_HEADER` — `check --deploy` is clean |

---

## 🧪 Testing

```bash
cd src
python manage.py test --settings=config.settings.test
```

```
Ran 152 tests in 2.5s — OK
```

| Suite | Covers |
|---|---|
| `test_auth` | Registration, verification, expiry, attempt limits, login, logout, reset |
| `test_catalog` | Listing, search, every filter, ordering, detail, comparison |
| `test_cart` | Add/update/remove, stock limits, promo codes, tier stacking, guest merge |
| `test_orders` | Checkout, snapshots, stock deduction, **transaction rollback**, cancellation |
| `test_user` | Profile, privilege-escalation attempts, password, wishlist, addresses |
| `test_reviews` | Verified-purchase gate, duplicates, rating bounds, aggregates |
| `test_security` | **IDOR across orders, addresses, wishlist, reviews, carts** |
| `test_admin_crud` | Full create→read→update→delete on all 14 admin resources |
| `test_content` | Published filtering, home sections, **constant-query-count assertion** |

---

## ⚙️ Configuration

All settings come from environment variables — see
[`src/.env.example`](src/.env.example) for the annotated full list.

| Variable | Purpose |
|---|---|
| `DEBUG` | Also selects the settings module: `1` → development, `0` → production |
| `SECRET_KEY` | **Required.** Use ≥ 50 random characters |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Comma-separated |
| `POSTGRES_DB` · `_USER` · `_PASSWORD` · `_HOST` · `_PORT` | Legacy `DB_*` names still honoured |
| `REDIS_URL` | Cache + Celery broker; falls back to in-memory when unset |
| `EMAIL_HOST` · `_PORT` · `_HOST_USER` · `_HOST_PASSWORD` · `_USE_TLS` | SMTP |
| `JWT_ACCESS_TOKEN_LIFETIME` / `JWT_REFRESH_TOKEN_LIFETIME` | Minutes / days |
| `OTP_CODE_TTL_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS` | Code policy |
| `THROTTLE_*`, `CACHE_TTL_*`, `PAGE_SIZE` | Tuning |
| `SECURE_SSL_ENABLED` | Set `False` behind a proxy that has not yet terminated TLS |

---

## 🩺 Health & operations

```bash
curl http://localhost:8000/healthz/
# {"status": "ok", "checks": {"database": "ok", "cache": "ok"}}
```

Returns **503** when a dependency is down, so orchestrators stop routing traffic.
Wired into every Docker health check.

```bash
celery -A config worker --loglevel=info   # background email delivery
celery -A config beat   --loglevel=info   # scheduler
```

---

## 🗺️ Roadmap

Known gaps, honestly stated:

- [ ] **Payments** — models exist, but there are no endpoints and no gateway
      integration; `Order.paid_at` is never set
- [ ] **Celery Beat has no scheduled jobs** — the container idles
- [ ] **1C integration** — product/price/stock import is unbuilt
- [ ] **Change-email endpoints** — model retained, HTTP layer not yet rebuilt
- [ ] **Order status state machine** — any transition is currently allowed, and
      transitions are not audit-logged
- [ ] **Postgres full-text search** — search is `icontains`; GIN + `pg_trgm` is
      needed at 50k SKUs
- [ ] Docker images have not been built in CI yet

---

## 📄 Further reading

- [`src/qollanma.md`](src/qollanma.md) — quick-start guide (Uzbek)
- [`stroyopttorg-backend.drawio`](stroyopttorg-backend.drawio) — ERD, architecture
  and order-status diagrams
- [`deployment/`](deployment/) — bare-metal systemd + nginx templates

<div align="center">

**Mini-grup 17**

</div>
