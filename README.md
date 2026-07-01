# Tasty Bites — Food Ordering Application

A full-featured restaurant ordering system built with Django, PostgreSQL, and Nginx.
Fully containerised with Docker and deployable to Kubernetes via a GitHub Actions CI/CD pipeline.

[![CI/CD Pipeline](https://github.com/efimijacuneva/food-ordering-application/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/efimijacuneva/food-ordering-application/actions/workflows/ci-cd.yml)

---

## Features

**Customer**
- Browse menu with category filters, search, and availability indicator
- Session-based cart for guests; DB-persisted cart for logged-in users (merged on login)
- Checkout with delivery address, phone number, and order notes
- 6-step order status tracking: Pending → Accepted → Preparing → Out for Delivery → Delivered / Cancelled
- Order history with per-order timeline view

**Admin panel** (`/admin-panel/`)
- Dashboard with live stats — total orders, revenue, customers, products
- Product CRUD with image uploads
- Category CRUD with product counts
- Order management: view items, customer info, update status
- Customer management: view order count, enable / disable accounts

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 4.2 + Gunicorn |
| Database | PostgreSQL 15 |
| Reverse proxy | Nginx 1.25 |
| Frontend | Bootstrap 5.3 + Font Awesome 6.5 |
| Containers | Docker (multi-stage build) |
| Orchestration | Kubernetes |
| CI/CD | GitHub Actions → Docker Hub |

---

## Quick Start — Docker Compose

```bash
# 1. Clone
git clone https://github.com/efimijacuneva/food-ordering-application.git
cd food-ordering-application

# 2. (Optional) copy and edit environment variables
cp .env.example .env

# 3. Start all services
docker compose up -d

# 4. Create an admin user
docker compose exec backend python manage.py createsuperuser

# 5. Open in browser  (docker-compose.override.yml maps the frontend to :8080)
#   App:           http://localhost:8080
#   Admin panel:   http://localhost:8080/admin-panel/
#   Django admin:  http://localhost:8080/django-admin/
```

---

## Project Structure

```
food-ordering-application/
├── backend/                        # Django application
│   ├── Dockerfile                  # Multi-stage build (builder + production)
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── entrypoint.sh               # Waits for DB, runs migrations, starts Gunicorn
│   ├── manage.py
│   ├── restaurant/                 # Django project (settings, urls, wsgi)
│   └── orders/                     # Main app
│       ├── models.py               # CustomUser, Category, Product, Cart, Order, OrderItem
│       ├── views.py
│       ├── urls.py
│       ├── forms.py
│       ├── tests.py                # 35 tests across 5 test classes
│       ├── context_processors.py
│       ├── admin.py
│       └── templates/
│           ├── base.html
│           ├── menu.html
│           ├── cart.html
│           ├── checkout.html
│           ├── order_*.html
│           ├── profile.html
│           ├── registration/
│           └── admin_panel/
├── frontend/                       # Nginx reverse proxy
│   ├── Dockerfile
│   ├── .dockerignore
│   └── nginx.conf.template         # envsubst replaces BACKEND_HOST at startup
├── k8s/                            # Kubernetes manifests (12 files)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── persistent-volume.yaml
│   ├── persistent-volume-claim.yaml
│   ├── postgres-statefulset.yaml
│   ├── postgres-service.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   └── ingress.yaml
├── .github/
│   └── workflows/
│       └── ci-cd.yml               # Test → Build & Push → Deploy
├── docs/
│   └── architecture.md             # Diagrams and design decisions
├── docker-compose.yml
├── .env.example
├── .gitignore
└── DEPLOYMENT_GUIDE.md
```

---

## CI/CD Pipeline

Every push to `main` triggers a three-job pipeline:

```
push to main
     │
     ▼
[test]  — Django tests against a live PostgreSQL service container
     │
     ▼  (push to main only, after tests pass)
[build-and-push]  — Docker Buildx → Docker Hub  (:latest + :<sha8>)
     │
     ▼  (only if KUBECONFIG secret is configured)
[deploy]  — kubectl apply k8s/ → rollout status
```

### Required Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub username (`efimijac`) |
| `DOCKERHUB_TOKEN` | Docker Hub access token (read/write) |
| `KUBECONFIG` | *(Optional)* base64-encoded kubeconfig to enable auto-deploy |

---

## Kubernetes Deployment

All image names are pre-configured. Just apply the manifests:

```bash
# 1. Apply all 12 manifests
kubectl apply -f k8s/

# 2. Watch pods become ready
kubectl get pods -n food-ordering -w

# 3. Get the Ingress IP
kubectl get ingress -n food-ordering

# 4. Add to /etc/hosts  (replace <INGRESS-IP> with the address above)
echo "<INGRESS-IP>  food-ordering.local" | sudo tee -a /etc/hosts

# 5. Open http://food-ordering.local
```

Full setup instructions, troubleshooting, and Minikube guide are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

---

## Running Tests

```bash
# Against the running Docker Compose stack
docker compose exec backend python manage.py test orders --verbosity=2

# Locally (requires a running PostgreSQL instance)
cd backend
python manage.py test orders --verbosity=2
```

**35 tests across 5 classes:**

| Class | Tests | Coverage |
|-------|-------|----------|
| `AuthTests` | 7 | Registration, login, duplicate email, invalid credentials, profile |
| `CategoryProductTests` | 7 | Menu load, available/unavailable products, search, category filter |
| `CartTests` | 7 | Add, accumulate, remove, update quantity, guest→user merge, totals |
| `OrderTests` | 7 | Checkout redirect, place order (auth + guest), order history, detail |
| `AdminPanelTests` | 7 | Dashboard auth, product CRUD, order status update, account management |

---

## Environment Variables

Copy [.env.example](.env.example) to `.env` and adjust as needed:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | insecure dev key |
| `DEBUG` | Enable debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins (with scheme) | `http://localhost,http://127.0.0.1` |
| `POSTGRES_DB` | Database name | `food_ordering_db` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | `postgres` |
| `DEFAULT_FROM_EMAIL` | Sender address for emails | `Tasty Bites <noreply@tastybites.mk>` |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | System diagrams, data models, request flow, security decisions |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Local, Docker Compose, Kubernetes, and CI/CD setup with troubleshooting |

---

## License

This project is for educational purposes.
