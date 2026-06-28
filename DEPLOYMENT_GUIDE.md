# Deployment Guide — Tasty Bites

This guide covers every way to run the application: locally without Docker, with Docker Compose, and on Kubernetes.

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.11 | python.org |
| Docker | 24.0 | docker.com |
| Docker Compose | v2 (plugin) | included with Docker Desktop |
| kubectl | 1.28 | kubernetes.io/docs/tasks/tools |
| PostgreSQL (local only) | 15 | postgresql.org |

---

## Option 1 — Local Development (without Docker)

### 1.1 Clone the repository
```bash
git clone <repo-url>
cd food-ordering-application
```

### 1.2 Create a virtual environment
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 1.3 Install dependencies
```bash
pip install -r requirements.txt
```

### 1.4 Start a local PostgreSQL database
```bash
# macOS (Homebrew)
brew services start postgresql@15

# Windows — start from Services or pgAdmin

# Create the database
createdb food_ordering_db
```

### 1.5 Set environment variables
```bash
# Windows (PowerShell)
$env:SECRET_KEY="your-dev-secret-key"
$env:DEBUG="True"
$env:DB_HOST="localhost"
$env:DB_NAME="food_ordering_db"
$env:DB_USER="postgres"
$env:DB_PASSWORD="postgres"

# macOS / Linux
export SECRET_KEY="your-dev-secret-key"
export DEBUG="True"
export DB_HOST="localhost"
export DB_NAME="food_ordering_db"
export DB_USER="postgres"
export DB_PASSWORD="postgres"
```

### 1.6 Apply migrations and create a superuser
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 1.7 Run the development server
```bash
python manage.py runserver
```

Open **http://localhost:8000** in your browser.

---

## Option 2 — Docker (single container build test)

Use this to verify that the Docker image builds and starts correctly.

### 2.1 Build the backend image
```bash
docker build -t food-ordering-backend ./backend
```

### 2.2 Build the frontend image
```bash
docker build -t food-ordering-frontend ./frontend
```

### 2.3 Verify the images
```bash
docker images | grep food-ordering
```

---

## Option 3 — Docker Compose (recommended for local full-stack)

This is the primary way to run the complete application locally.

### 3.1 Configure environment (optional)
```bash
cp .env.example .env
# Edit .env with your values (the defaults work for local development)
```

### 3.2 Start all services
```bash
docker compose up -d
```

Docker Compose will:
1. Pull `postgres:15-alpine`
2. Build the backend image from `./backend/Dockerfile`
3. Build the frontend image from `./frontend/Dockerfile`
4. Start PostgreSQL, wait for its health check
5. Start the backend, which runs migrations on first start
6. Start the frontend Nginx proxy

### 3.3 Verify the stack is running
```bash
docker compose ps
```

All three containers should show `running (healthy)` or `running`.

### 3.4 Open the application
```
http://localhost
```

### 3.5 Create an admin user
```bash
docker compose exec backend python manage.py createsuperuser
```

Then log in and visit **http://localhost/admin-panel/** for the admin dashboard.

### 3.6 Seed sample data (optional)
```bash
docker compose exec backend python manage.py shell -c "
from orders.models import Category, Product
from decimal import Decimal
b = Category.objects.create(name='Burgers', display_order=1)
p = Category.objects.create(name='Pizza', display_order=2)
d = Category.objects.create(name='Drinks', display_order=3)
Product.objects.create(category=b, name='Classic Burger', description='Beef patty, lettuce, cheese.', price=Decimal('8.99'))
Product.objects.create(category=p, name='Margherita', description='Tomato, mozzarella, basil.', price=Decimal('9.00'))
Product.objects.create(category=d, name='Cola', description='330ml chilled.', price=Decimal('2.00'))
print('Done.')
"
```

### 3.7 Run the test suite
```bash
docker compose exec backend python manage.py test orders --verbosity=2
```

### 3.8 View logs
```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

### 3.9 Stop the stack
```bash
docker compose down          # stop, keep volumes
docker compose down -v       # stop AND delete all data
```

---

## Option 4 — Kubernetes

### 4.1 Prerequisites

- A running Kubernetes cluster (minikube, k3s, GKE, EKS, AKS, etc.)
- `kubectl` configured and pointing to your cluster
- Nginx Ingress Controller installed
- Docker images pushed to Docker Hub (see CI/CD section)

### 4.2 Install Nginx Ingress Controller (if not present)

```bash
# minikube
minikube addons enable ingress

# Generic cluster
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
```

### 4.3 Replace the Docker Hub username placeholder

```bash
# Linux / macOS
export DOCKERHUB_USERNAME="efimijac"
sed -i "s/YOUR_DOCKERHUB_USERNAME/${DOCKERHUB_USERNAME}/g" \
  k8s/backend-deployment.yaml \
  k8s/frontend-deployment.yaml

# Windows (PowerShell)
$user = "efimijac"
(Get-Content k8s/backend-deployment.yaml)  -replace 'YOUR_DOCKERHUB_USERNAME', $user | Set-Content k8s/backend-deployment.yaml
(Get-Content k8s/frontend-deployment.yaml) -replace 'YOUR_DOCKERHUB_USERNAME', $user | Set-Content k8s/frontend-deployment.yaml
```

### 4.4 Update secrets with real values

Edit `k8s/secret.yaml` and replace the base64 values:

```bash
# Encode your values
echo -n "your-strong-django-secret-key" | base64
echo -n "your-db-password"              | base64

# Paste the output into k8s/secret.yaml
```

### 4.5 Apply all manifests

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/persistent-volume.yaml
kubectl apply -f k8s/persistent-volume-claim.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/ingress.yaml
```

Or apply all at once:
```bash
kubectl apply -f k8s/
```

> **Note:** Applying everything at once works, but Kubernetes will reconcile dependencies automatically. Allow 60–120 seconds for all pods to become ready.

### 4.6 Watch pods come up

```bash
kubectl get pods -n food-ordering -w
```

Expected output after a successful deployment:
```
NAME                        READY   STATUS    RESTARTS   AGE
backend-xxxxxxxxxx-xxxxx    1/1     Running   0          2m
backend-xxxxxxxxxx-xxxxx    1/1     Running   0          2m
frontend-xxxxxxxxxx-xxxxx   1/1     Running   0          1m
frontend-xxxxxxxxxx-xxxxx   1/1     Running   0          1m
postgres-0                  1/1     Running   0          3m
```

### 4.7 Configure local DNS

```bash
# Get the Ingress IP
kubectl get ingress -n food-ordering

# Add to /etc/hosts (Linux/macOS) or C:\Windows\System32\drivers\etc\hosts (Windows)
<INGRESS-IP>   food-ordering.local
```

For minikube:
```bash
minikube tunnel   # keep this running
# In /etc/hosts: 127.0.0.1  food-ordering.local
```

### 4.8 Open the application

```
http://food-ordering.local
```

### 4.9 Create the admin user in Kubernetes

```bash
kubectl exec -it -n food-ordering \
  $(kubectl get pods -n food-ordering -l app=backend -o jsonpath='{.items[0].metadata.name}') \
  -- python manage.py createsuperuser
```

---

## CI/CD Setup (GitHub Actions)

### Required secrets

Go to your GitHub repository → **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token with read/write scope |
| `KUBECONFIG` | *(Optional)* `base64`-encoded kubeconfig for automatic K8s deployment |

### Generate KUBECONFIG secret

```bash
cat ~/.kube/config | base64 -w 0
# Paste the output as the KUBECONFIG secret value
```

### Pipeline behaviour

| Trigger | Jobs that run |
|---------|--------------|
| Pull request → `main` | Test only |
| Push → `main` | Test → Build & Push |
| Push → `main` + `KUBECONFIG` set | Test → Build & Push → Deploy |

---

## Troubleshooting

### `docker compose up` — backend exits immediately

Check logs:
```bash
docker compose logs backend
```

Common causes:
- PostgreSQL not ready yet — the entrypoint script retries 30 times (2 s each); if it still fails, check `docker compose logs postgres`
- Missing `SECRET_KEY` — ensure your `.env` file is present or the default is used

### `docker compose up` — port 80 already in use

Change the port in your `.env`:
```env
HTTP_PORT=8080
```
Then restart: `docker compose up -d`

### Kubernetes — pods in `CrashLoopBackOff`

```bash
kubectl describe pod <pod-name> -n food-ordering
kubectl logs <pod-name> -n food-ordering
```

Most common fix: the `DB_HOST` env var in `configmap.yaml` must be `postgres` (the headless service name), not `localhost`.

### Kubernetes — `ImagePullBackOff`

The image name in the deployment still contains a placeholder username. Re-run step 4.3 and re-apply the deployment.

### Kubernetes — Ingress not routing traffic

Confirm the Ingress controller is running:
```bash
kubectl get pods -n ingress-nginx
```

Check that the Ingress resource was created:
```bash
kubectl describe ingress food-ordering-ingress -n food-ordering
```

### Django migrations fail in container

Run migrations manually:
```bash
# Docker Compose
docker compose exec backend python manage.py migrate

# Kubernetes
kubectl exec -it -n food-ordering \
  $(kubectl get pods -n food-ordering -l app=backend -o jsonpath='{.items[0].metadata.name}') \
  -- python manage.py migrate
```

### Reset the database (Docker Compose)

```bash
docker compose down -v       # deletes postgres_data volume
docker compose up -d         # fresh database, migrations run automatically
```
