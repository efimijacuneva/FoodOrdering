# Architecture — Tasty Bites Food Ordering Application

## System Overview

Tasty Bites follows a **three-tier architecture**: a stateless frontend reverse proxy, a stateless application backend, and a stateful database. All three tiers run as separate containers and communicate over an internal network.

---

## Component Diagram

```
                          ┌─────────────────────────────┐
                          │        User Browser         │
                          └──────────────┬──────────────┘
                                         │ HTTP :80
                          ┌──────────────▼──────────────┐
                          │    Nginx (frontend)          │
                          │    Reverse Proxy             │
                          │    - Serves no static files  │
                          │    - proxy_pass → backend    │
                          └──────────────┬──────────────┘
                                         │ HTTP :8000 (internal)
                          ┌──────────────▼──────────────┐
                          │   Django + Gunicorn          │
                          │   (backend)                  │
                          │                              │
                          │   ┌──────────────────────┐  │
                          │   │  Application Layer   │  │
                          │   │  - Views (requests)  │  │
                          │   │  - Forms (validation)│  │
                          │   │  - Models (ORM)      │  │
                          │   └──────────────────────┘  │
                          │                              │
                          │   Static files served by     │
                          │   WhiteNoise middleware       │
                          │   Media files on shared PVC  │
                          └──────────────┬──────────────┘
                                         │ TCP :5432 (internal)
                          ┌──────────────▼──────────────┐
                          │   PostgreSQL 15              │
                          │   (database)                 │
                          │                              │
                          │   - Persistent volume        │
                          │   - StatefulSet in K8s       │
                          └─────────────────────────────┘
```

---

## Data Models

```
CustomUser ──────┐
  id              │      Order ───────── OrderItem
  username        │        id                id
  email           ├──FK──▶ user_id            order_id ──FK──▶ Order
  phone           │        delivery_address   product_id ──FK──▶ Product
  address         │        phone              product_name
  is_staff        │        notes              product_price (snapshot)
  is_active       │        total_price        quantity
                  │        status             notes
                  │        created_at
Cart ────────────┘        updated_at
  id
  user_id ──OneToOne──▶ CustomUser    Category
  session_key (guests)     id
                           name
CartItem                   description
  id                       image
  cart_id ──FK──▶ Cart     is_active
  product_id ──FK──▶ Product  display_order
  quantity
  notes            Product
                     id
                     category_id ──FK──▶ Category
                     name
                     description
                     price
                     image
                     is_available
                     created_at / updated_at
```

---

## Request / Response Flow

### Customer order flow

```
1. GET  /              → menu_view        → render menu.html
2. POST /cart/add/<id> → add_to_cart_view → save CartItem to DB
3. GET  /cart/         → cart_view        → render cart.html
4. GET  /checkout/     → checkout_view    → render checkout.html
5. POST /checkout/     → checkout_view    → create Order + OrderItems → redirect order_success
6. GET  /orders/       → order_history_view → render order_history.html
```

### Admin order management flow

```
1. GET  /admin-panel/orders/         → list all orders (filterable)
2. GET  /admin-panel/orders/<id>/    → view order detail + status form
3. POST /admin-panel/orders/<id>/    → update Order.status → (send email if ACCEPTED)
```

### Cart — guest vs authenticated

```
Guest user:
  session created automatically → Cart(session_key=<key>) in DB

Authenticated user:
  Cart(user=request.user) in DB

On login:
  merge_guest_cart() moves CartItems from guest Cart → user Cart → delete guest Cart
```

---

## Containerisation Architecture

### Docker images

| Image | Base | Size target | Contents |
|-------|------|------------|---------|
| Backend | `python:3.11-slim` (multi-stage) | ~200 MB | App code, Python deps, static files |
| Frontend | `nginx:1.25-alpine` | ~45 MB | Nginx binary + config template |

### Multi-stage build (backend)

```dockerfile
Stage 1 (builder):   python:3.11-slim + gcc + libpq-dev
                     → pip install to /install prefix

Stage 2 (production): python:3.11-slim + libpq5 (runtime only)
                      COPY /install from builder
                      COPY app code
                      RUN collectstatic
                      RUN adduser appuser (non-root)
```

The final image does not contain a compiler, reducing the attack surface.

---

## Kubernetes Architecture

```
Namespace: food-ordering
│
├── ConfigMap: food-ordering-config
│   └── (non-sensitive env vars: DEBUG, ALLOWED_HOSTS, DB_HOST, DB_NAME…)
│
├── Secret: food-ordering-secret
│   └── (base64: SECRET_KEY, DB_USER, DB_PASSWORD)
│
├── StatefulSet: postgres (1 replica)
│   └── PVC (auto-provisioned, 5 Gi) ← volumeClaimTemplates
│
├── Service: postgres (headless, ClusterIP: None)
│   └── DNS: postgres.food-ordering.svc.cluster.local
│
├── PersistentVolume: media-pv (2 Gi, hostPath)
├── PersistentVolumeClaim: media-pvc (2 Gi, ReadWriteOnce)
│
├── Deployment: backend (2 replicas, RollingUpdate)
│   ├── envFrom: configmap + secret
│   └── volumeMount: media-pvc → /app/media
│
├── Service: backend (ClusterIP, port 8000)
│
├── Deployment: frontend (2 replicas, RollingUpdate)
│   └── env: BACKEND_HOST=backend
│
├── Service: frontend (ClusterIP, port 80)
│
└── Ingress: food-ordering-ingress
    └── host: food-ordering.local → frontend:80
```

---

## CI/CD Architecture

```
Developer push
      │
      ▼
GitHub Actions
      │
      ├── Job 1: Test ────────────────────────────┐
      │   ├── Service: postgres:15-alpine         │
      │   ├── pip install                         │
      │   ├── manage.py check                     │
      │   ├── manage.py migrate                   │
      │   ├── manage.py test orders               │
      │   └── docker compose config               │
      │                                           │
      └── (only on push to main, after test pass) │
            │                                     │
            ▼                                     │
      Job 2: Build & Push                         │
            ├── Docker Buildx (layer cache)       │
            ├── Push backend:latest + :<sha8>     │
            └── Push frontend:latest + :<sha8>    │
                          │                       │
                          ▼                       │
            Job 3: Deploy [OPTIONAL BONUS]        │
            ├── kubectl apply k8s/ manifests      │
            └── kubectl rollout status            │
                                                  ▼
                                        Docker Hub Registry
                                        ├── <user>/food-ordering-backend
                                        └── <user>/food-ordering-frontend
```

---

## Security Considerations

| Area | Measure |
|------|---------|
| Secrets | Never committed; stored in `.env` (local) or K8s Secrets / GitHub Secrets |
| Container user | Backend runs as non-root `appuser` |
| CSRF | Django CSRF middleware enabled on all POST forms |
| Password storage | Django's PBKDF2 hashing (default) |
| SQL injection | Django ORM with parameterised queries |
| Admin access | `staff_required` decorator gates all `/admin-panel/` views |
| Image uploads | Restricted to `MEDIA_ROOT`; Nginx serves the media volume |
| XSS | Django template auto-escaping enabled |
| Static files | Served by WhiteNoise with `CompressedManifestStaticFilesStorage` (cache-busting) |
