# Project Report — Tasty Bites Food Ordering Application

**Course:** Software Engineering / CI/CD  
**Project:** Food Ordering Web Application with Full CI/CD Pipeline  
**Technology Stack:** Django · PostgreSQL · Nginx · Docker · Kubernetes · GitHub Actions

---

## 1. Project Overview

Tasty Bites is a full-featured restaurant ordering web application that allows customers to browse a menu, manage a shopping cart, place orders, and track order status. Restaurant staff access a dedicated admin panel to manage the catalog and fulfil orders.

The project demonstrates a complete modern software delivery pipeline: the application is containerised with Docker, orchestrated locally via Docker Compose, and deployed to a production Kubernetes cluster. Every commit to `main` triggers a three-stage GitHub Actions pipeline that tests the code, builds Docker images, publishes them to Docker Hub, and optionally deploys to Kubernetes.

---

## 2. Architecture

```
Internet
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                    │
│                                                          │
│  ┌──────────────┐     ┌──────────────┐                   │
│  │   Ingress    │────▶│   Frontend   │ (Nginx, 2 pods)   │
│  │  Controller  │     │   Service    │                   │
│  └──────────────┘     └──────┬───────┘                   │
│                              │ proxy_pass                 │
│                       ┌──────▼───────┐                   │
│                       │   Backend    │ (Django/Gunicorn,  │
│                       │   Service    │  2 pods)           │
│                       └──────┬───────┘                   │
│                              │                           │
│                       ┌──────▼───────┐                   │
│                       │  PostgreSQL  │ (StatefulSet,     │
│                       │   Service    │  1 pod + 5Gi PVC) │
│                       └──────────────┘                   │
│                                                          │
│  ConfigMap: app config    Secret: credentials            │
│  PV/PVC: media uploads    Namespace: food-ordering       │
└──────────────────────────────────────────────────────────┘
```

**Request flow:**
1. Browser → Kubernetes Ingress (Nginx Ingress Controller, host: `food-ordering.local`)
2. Ingress → Frontend Service (port 80)
3. Frontend container (Nginx) → Backend Service (port 8000) via `proxy_pass`
4. Backend container (Django/Gunicorn) → PostgreSQL Service (port 5432)

---

## 3. Technologies Used

| Component | Technology | Version |
|-----------|-----------|---------|
| Web framework | Django | 4.2 |
| Application server | Gunicorn | 21.2 |
| Reverse proxy | Nginx | 1.25 |
| Database | PostgreSQL | 15 |
| Static files | WhiteNoise | 6.6 |
| Image uploads | Pillow | 10.2 |
| Container runtime | Docker | 24+ |
| Orchestration | Kubernetes | 1.28+ |
| CI/CD | GitHub Actions | — |
| Image registry | Docker Hub | — |
| UI framework | Bootstrap | 5.3 |
| Icons | Font Awesome | 6.5 |

---

## 4. Dockerization

### Backend (`backend/Dockerfile`)

A **multi-stage build** is used to minimise the final image size:

- **Stage 1 (builder):** installs Python dependencies into an isolated `/install` prefix using `gcc` and `libpq-dev`.
- **Stage 2 (production):** copies only the compiled packages, drops `gcc`, runs `collectstatic`, creates a **non-root `appuser`**, and exposes port 8000.

Key features:
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` for clean container output
- Static files collected at build time so the image is self-contained
- Non-root user reduces the attack surface
- Entrypoint script (`entrypoint.sh`) waits for PostgreSQL, runs migrations, then starts Gunicorn

### Frontend (`frontend/Dockerfile`)

- Based on `nginx:1.25-alpine` — minimal image
- `nginx.conf.template` is processed at container start with `envsubst` to inject `$BACKEND_HOST`
- Only `${BACKEND_HOST}` is substituted, leaving Nginx's own `$host`, `$remote_addr` etc. intact

### `.dockerignore` files

Both images have `.dockerignore` files excluding:
- `.git/` and version control metadata
- Python bytecode and cache
- Local virtual environments and `.env` files
- Development artefacts (`staticfiles/`, `media/`, `*.sqlite3`)

---

## 5. Docker Compose

`docker-compose.yml` defines three services on a dedicated bridge network (`food-ordering-net`):

| Service | Image | Role |
|---------|-------|------|
| `postgres` | `postgres:15-alpine` | Relational database |
| `backend` | custom build | Django application server |
| `frontend` | custom build | Nginx reverse proxy |

**Key design decisions:**
- `postgres` uses a health check; `backend` only starts after PostgreSQL is healthy (`condition: service_healthy`)
- Two named volumes: `postgres_data` (database files) and `media_files` (uploaded images) — both survive `docker-compose down`
- All credentials are provided via environment variables with safe defaults for local development; override with a `.env` file in production
- The `frontend` service maps port 80 (configurable via `$HTTP_PORT`)

Start the entire application with:
```bash
docker compose up -d
```

---

## 6. GitHub Actions CI/CD Pipeline

The pipeline is defined in `.github/workflows/ci-cd.yml` and contains three jobs.

### Job 1 — Test (runs on every push and PR)

| Step | Description |
|------|-------------|
| Checkout | Fetches the repository |
| Setup Python 3.11 | Caches `pip` dependencies |
| Install dependencies | `pip install -r requirements.txt` |
| Django system check | `manage.py check` |
| Migrate | `manage.py migrate --noinput` against the CI PostgreSQL service |
| Run tests | `manage.py test orders --verbosity=2` (35+ tests) |
| Validate Compose | `docker compose config --quiet` |

A PostgreSQL 15 service container is spun up automatically as part of the job.

### Job 2 — Build & Push (push to `main` only, after tests pass)

| Step | Description |
|------|-------------|
| Checkout | — |
| Compute image tag | `SHORT_SHA` — first 8 characters of the commit SHA |
| Setup Docker Buildx | Enables advanced build features and layer caching |
| Docker Hub login | Uses `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` secrets |
| Build & push backend | Tags: `latest` and `<short-sha>` |
| Build & push frontend | Tags: `latest` and `<short-sha>` |
| Job summary | Prints published image names and tags |

Layer caching (`cache-from/cache-to: type=gha`) dramatically reduces build times on repeated runs.

### Job 3 — Deploy to Kubernetes (optional bonus, push to `main` only)

Activated only when the `KUBECONFIG` secret is set in the repository.

| Step | Description |
|------|-------------|
| Setup kubectl | Latest stable version |
| Configure kubectl | Decodes `KUBECONFIG` secret into `~/.kube/config` |
| Substitute image names | `sed` replaces `YOUR_DOCKERHUB_USERNAME` and `:latest` with real values |
| Apply manifests | Applies all files in `k8s/` in dependency order |
| Wait for rollout | `kubectl rollout status` for both deployments |

---

## 7. Docker Hub Integration

Images are automatically published to Docker Hub on every successful push to `main`:

| Image | Tag strategy |
|-------|-------------|
| `<username>/food-ordering-backend` | `latest` + `<8-char-sha>` |
| `<username>/food-ordering-frontend` | `latest` + `<8-char-sha>` |

**Required GitHub Secrets:**

| Secret | Purpose |
|--------|---------|
| `DOCKERHUB_USERNAME` | Docker Hub account name |
| `DOCKERHUB_TOKEN` | Docker Hub access token (read/write) |

**To use pre-built images with Docker Compose:**
```bash
DOCKERHUB_USERNAME=efimijac docker compose pull
docker compose up -d
```

---

## 8. Kubernetes Deployment

All manifests live in the `k8s/` directory and target the `food-ordering` namespace.

### Apply order (dependency chain)

```
namespace → configmap/secret → PV → PVC
         → postgres-statefulset → postgres-service
         → backend-deployment  → backend-service
         → frontend-deployment → frontend-service
         → ingress
```

### Manifest summary

| File | Kind | Purpose |
|------|------|---------|
| `namespace.yaml` | Namespace | Isolates all resources under `food-ordering` |
| `configmap.yaml` | ConfigMap | Non-sensitive app configuration |
| `secret.yaml` | Secret | Django secret key + DB credentials (base64) |
| `persistent-volume.yaml` | PersistentVolume | 2 Gi host-path volume for media files |
| `persistent-volume-claim.yaml` | PersistentVolumeClaim | Claim bound to media PV |
| `postgres-statefulset.yaml` | StatefulSet | PostgreSQL with auto-provisioned 5 Gi PVC |
| `postgres-service.yaml` | Service (headless) | Stable DNS name for PostgreSQL |
| `backend-deployment.yaml` | Deployment | Django/Gunicorn, 2 replicas, rolling update |
| `backend-service.yaml` | Service (ClusterIP) | Internal access on port 8000 |
| `frontend-deployment.yaml` | Deployment | Nginx, 2 replicas |
| `frontend-service.yaml` | Service (ClusterIP) | Internal access on port 80 |
| `ingress.yaml` | Ingress | Routes `food-ordering.local` → frontend |

---

## 9. ConfigMaps and Secrets

### ConfigMap (`food-ordering-config`)

Stores all non-sensitive configuration injected into the backend via `envFrom.configMapRef`:

```yaml
DEBUG: "False"
ALLOWED_HOSTS: "localhost,127.0.0.1,food-ordering.local"
DB_HOST: "postgres"
DB_PORT: "5432"
DB_NAME: "food_ordering_db"
DEFAULT_FROM_EMAIL: "Tasty Bites <noreply@tastybites.mk>"
```

### Secret (`food-ordering-secret`)

Stores sensitive values as base64-encoded strings:

```yaml
SECRET_KEY: <base64 Django secret key>
DB_USER:    <base64 postgres username>
DB_PASSWORD: <base64 postgres password>
```

The backend deployment uses `envFrom.secretRef` to mount all secret values as environment variables, keeping credentials out of the application configuration files.

---

## 10. StatefulSet

PostgreSQL is deployed as a **StatefulSet** (not a Deployment) for two reasons:

1. **Stable network identity** — the pod always has the DNS name `postgres-0.postgres.food-ordering.svc.cluster.local`
2. **Persistent storage** — the `volumeClaimTemplates` block automatically provisions a dedicated `5 Gi` PVC for each pod, ensuring data survives pod restarts and reschedules

The StatefulSet uses `PGDATA=/var/lib/postgresql/data/pgdata` to avoid permission issues with the PVC mount point.

Health checks (`pg_isready`) prevent the backend from connecting before PostgreSQL is ready.

---

## 11. Ingress

The Nginx Ingress Controller routes all traffic for `food-ordering.local` to the frontend service on port 80. The frontend Nginx then proxies API and page requests back to the backend service.

Key Ingress annotations:
- `nginx.ingress.kubernetes.io/proxy-body-size: "10m"` — allows image uploads up to 10 MB
- `nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"` and `proxy-read-timeout: "60"` — prevents timeouts on slower requests

---

## 12. Testing

### Automated tests (35+ test cases)

| Suite | Tests |
|-------|-------|
| `AuthTests` | Register, login, duplicate email, profile access control |
| `CategoryProductTests` | Menu display, search, category filter, unavailable items |
| `CartTests` | Add, remove, update quantity, quantity=0 removes item, total |
| `OrderTests` | Authenticated + guest checkout, cart empty redirect, order history |
| `AdminPanelTests` | Staff-only access, CRUD products, status update, customer toggle |

All tests run against a real PostgreSQL database (in CI via the GitHub Actions service container).

### Manual verification checklist

- [ ] `docker compose up -d` — all three containers start and pass health checks
- [ ] `http://localhost` — menu page loads
- [ ] Registration and login work
- [ ] Items can be added to cart and ordered
- [ ] Admin panel accessible at `/admin-panel/` (staff user required)
- [ ] Order status can be updated by staff
- [ ] `docker compose exec backend python manage.py test orders` — all tests pass

---

## 13. Screenshots

> Replace the placeholders below with actual screenshots.

### Menu Page
`[Screenshot: menu page with product cards, search bar, category pills]`

### Shopping Cart
`[Screenshot: cart with items, quantity controls, order summary]`

### Checkout
`[Screenshot: checkout form with delivery details]`

### Order Success
`[Screenshot: order confirmation page with order ID and status]`

### Admin Dashboard
`[Screenshot: admin panel dashboard with stat cards and recent orders]`

### Admin Orders
`[Screenshot: orders list with status badges and filters]`

### GitHub Actions Pipeline
`[Screenshot: GitHub Actions workflow run showing all three jobs passing]`

### Docker Hub
`[Screenshot: Docker Hub repository showing backend and frontend images with tags]`
