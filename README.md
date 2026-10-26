![Version](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2FEPFL-CePro%2FeXamc%2Frefs%2Fheads%2Fmain%2Fdjango%2Fapp%2Fpyproject.toml&query=%24.project.version&label=version&color=blue)
![License](https://img.shields.io/badge/license-NCL%20v1.0-red)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/EPFL-CePro/eXamc/refs/heads/main/django/app/pyproject.toml)
![CI](https://img.shields.io/github/actions/workflow/status/EPFL-CePro/eXamc/docker-build-test-and-push.yml?branch=main&label=CI)
![GitHub Issues](https://img.shields.io/github/issues/EPFL-CePro/eXamc)



<div style="text-align: center;">
    <img width="400" src="https://raw.githubusercontent.com/EPFL-CePro/eXamc/refs/heads/main/django/app/examc_app/static/img/eXamc.svg" alt="eXamc logo">
</div>

---

Dockerized environment for **eXamc** featuring:
- **Django**, **Gunicorn** (prod) / **runserver** (dev)
- **Vite** frontend (TypeScript/Sass, pnpm)
- **MySQL 8.4**
- **Redis 7** (Celery broker/results)
- **Celery** (worker) + **Celery Beat**
- **Nginx** (reverse proxy + static dir)
- **Private media** via **Nginx X-Accel-Redirect**
- **Ansible** for deployment, see repository [EPFL-CePro/eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops) for configuration

> [!IMPORTANT]
> This app relies on **Entra ID** (Azure AD) configuration.  
> Do **not** commit any real `.env.*` files or DB dumps.

---

## Table of Contents

<!-- TOC -->
  * [Prerequisites](#prerequisites)
  * [Layout](#layout)
  * [Environment files](#environment-files)
  * [Entra ID (OIDC) parameters](#entra-id-oidc-parameters)
  * [Run in DEV](#run-in-dev)
  * [Updating dependencies](#updating-dependencies)
  * [Makefile commands](#makefile-commands)
  * [DB seed / import / export (optional)](#db-seed--import--export-optional)
  * [MySQL Workbench access](#mysql-workbench-access)
  * [Private media](#private-media)
  * [Migrations & updates](#migrations--updates)
  * [TEST / PROD overview](#test--prod-overview)
  * [Troubleshooting](#troubleshooting)
  * [📄 License](#-license)
  * [🙋 Support](#-support)
<!-- TOC -->

---

## Prerequisites

- Docker & Docker Compose (v2)
- `make` (Linux/macOS; on Windows use WSL)
- Free ports: **8000** (Nginx), **3307** (MySQL exposed in dev)
- Access to your **Entra ID app registration** (to configure OIDC)

---

## Layout

```
.
├─ app/                             # Django application and Python project
│  ├─ docs/                         # Sphinx documentation
│  ├─ examc/                        # Django project: settings/urls/wsgi/asgi/celery
│  ├─ examc_app/                    # Main Django application
│  ├─ templates/                    # Django templates
│  ├─ entrypoint.sh
│  ├─ gunicorn.conf.py
│  ├─ pyproject.toml                # Main project configuration
│  └─ uv.lock
├─ compose/                         # Docker Compose configurations
│  ├─ base.yml                      # Shared service definitions (not used directly)
│  ├─ dev.yml                       # Development environment
│  ├─ test.yml                      # Test/CI environment
│  └─ prod.yml                      # Production environment (also used for staging server)
├─ data/                            # Local persistent data
│  └─ private_media/                # AMC-related files
├─ deploy/                          # Deployment-related configuration
│  ├─ db/
│  │  └─ init-test-user.sql
│  └─ nginx/                        # Nginx configurations
│     ├─ nginx.dev.conf
│     ├─ nginx.prod.conf
│     └─ nginx.test.conf
├─ docker/                          # Docker-specific scripts and patches
├─ scripts/                         # Development and security scripts
│  ├─ check_forbidden_calls.py
│  ├─ check_require_post.py
│  └─ security_check.sh
├─ Security/                        # Security-related documentation
│  └─ local_security_checks.md
├─ Dockerfile
├─ Makefile
├─ CHANGELOG.md
├─ CODE_OF_CONDUCT.md
├─ LICENSE
├─ README.md
├─ README-deploy.md
└─ SECURITY.md
```

---

## Environment files

Create one per environment **locally** (not versioned), from `.env.example`:

```bash
cp .env.example .env.dev
cp .env.example .env.test
cp .env.example .env.prod
```

`.gitignore` excludes: `.env.*` (keep `.env.example`), SQL dumps, `export_tmp/`, `__pycache__`, etc.  
`.dockerignore` excludes: `.git`, `.env.*`, dumps, caches, etc.

Expected variables (example **.env.dev**):

```env
ENV=dev
SECRET_KEY=change-me
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1

MYSQL_DATABASE=examc
MYSQL_USER=examc
MYSQL_PASSWORD=change-me
MYSQL_ROOT_PASSWORD=change-me-root
DB_HOST=mysql
DB_PORT=3306

REDIS_URL=redis://redis:6379/0

STATIC_ROOT=/static
PRIVATE_MEDIA_ROOT=/private_media

# --- Entra ID / OIDC ---
OIDC_ISSUER=https://login.microsoftonline.com/<TENANT_ID>/v2.0
OIDC_CLIENT_ID=<app-client-id>
OIDC_CLIENT_SECRET=<secret>
OIDC_REDIRECT_URI=http://localhost:8000/oidc/callback
OIDC_LOGOUT_REDIRECT_URI=http://localhost:8000/
OIDC_SCOPES=openid,profile,email
```

> OIDC values must match your **app registration** + **redirect URIs**.

---

## Entra ID (OIDC) parameters

1. **Create/Configure** an application in Azure Entra ID (your tenant).
2. **Allow** the following dev redirect URIs:
   - `http://localhost:8000/oidc/callback`
   - (optional) `http://127.0.0.1:8000/oidc/callback`
3. **Collect** `Client ID` and **client secret** → put into `.env.dev`.
4. Django **hosts & CSRF** must align with your dev URL:
   - `ALLOWED_HOSTS=localhost,127.0.0.1`
   - `CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1`

For **test/prod**, adapt to your public hosts and **force HTTPS**.

---

## Run in DEV

```bash
# 1) Create .env.dev and fill values (incl. OIDC)
cp .env.example .env.dev
# ...edit .env.dev

# 2) Start
make up

# 3) Verify
make health             # HEAD /healthz → 200
make ps                 # all services "healthy"

# 4) Open
xdg-open http://127.0.0.1:8000  # (use open/start on macOS/Windows)
```

## Updating dependencies

This project uses [`uv`](https://docs.astral.sh/uv/) to manage dependencies. `uv` is installed in the `tooling` target of the Dockerfile (used by test and dev environments), and can be called like this :

```bash
docker compose -f compose/test.yml run django uv add dependency_name
docker compose -f compose/dev.yml run django uv update
```

This updates both `app/pyproject.toml` and `app/uv.lock`.

Dependencies are split into groups to keep the production image lean:

```toml
[dependency-groups]
test = [
    # dependencies for tests
]

dev = [
    # dependencies for development
]

docs = [
    # dependencies for building the documentation
]
```

The Dockerfile uses these groups to build separate environments:

* **Production**: installs only production dependencies.
* **Docs**: installs the `docs` group to build the Sphinx documentation. The generated documentation is then included in the production image.
* **Tooling**: installs both the `dev` and `test` groups for development and testing.

The tooling image can be built like this if needed:

```bash
docker compose -f compose/test.yml build --target tooling django
```

---

## Makefile commands

```bash
make up             # build & starts everything
make build          # (re)builds & starts services
make tests          # starts tests (using compose/dev.yaml) config
make down           # stop everything
make reset          # stop + remove volumes (DB data!)
make ps             # status
make logs           # tail logs for all services

make django-shell   # shell inside django container
make makemigrations # django makemigrations
make migrate        # django migrate
make collectstatic  # django collectstatic
make createsuperuser

make health         # HEAD /healthz via Nginx
make nginx-reload   # test & reload Nginx

make dbshell        # mysql client (root) inside container
make dbdump         # export DB -> deploy/db/dump-YYYYmmdd_HHMMSS.sql.gz
make dbimport FILE=deploy/db/foo.sql.gz  # import .sql(.gz)

make rebuild-django # rebuild django service only
make prune          # prune dangling images
```

> For **test/prod**: `make up ENV=test` (uses `.env.test` + `compose/test.yml`), etc.

---

## DB seed / import / export (optional)

- **Export**:
  ```bash
  make dbdump
  # → deploy/db/dump-YYYYmmdd_HHMMSS.sql.gz
  ```
- **Import**:
  ```bash
  make dbimport FILE=deploy/db/my_dump.sql.gz
  ```
- **Conditional seed**: provide `deploy/db/dev-seed.sql.gz` (not versioned) and run the `db_seed` service (dedicated profile). Seed runs **only if DB is empty**.

---

## MySQL Workbench access

Dev connection:
- Host: `127.0.0.1`
- Port: `3307`
- User/Pass: `MYSQL_USER` / `MYSQL_PASSWORD`
- DB: `MYSQL_DATABASE`

---

## Private media

- Mounted under **`/private_media`** (django/nginx).  
- Django returns `X-Accel-Redirect` to `/_protected/...`.  
- Nginx (dev):
  ```nginx
  location /_protected/ {
      internal;
      alias /private_media/;
  }
  ```
- Settings:
  ```python
  PRIVATE_MEDIA_ROOT = os.environ.get("PRIVATE_MEDIA_ROOT", "/private_media")
  PRIVATE_MEDIA_URL = "/_protected/"
  ```

---

## Migrations & updates

- **DEV**: entrypoint auto-runs `migrate` (and `collectstatic` if `COLLECTSTATIC=1`).
- **TEST/PROD**: **no auto-migrate** at boot. Apply migrations via CI job or manual step:
  ```bash
  docker compose ... exec django python manage.py migrate --noinput
  docker compose ... exec django python manage.py collectstatic --noinput
  # reload Gunicorn/Nginx
  ```

---

## TEST / PROD overview

- Overrides: `compose/test.yml`, `compose/prod.yml`
- **HTTPS** is managed on the host machine
- Security: `SECURE_SSL_REDIRECT=1`, cookie `*_SECURE=1`, **HSTS** enabled
- **Gunicorn** in front (never `runserver`)
- Controlled migrations, centralized logging, backups, monitoring

Tests can be run with :

```bash
docker compose -f compose/test.yml run --rm --remove-orphans django
```

---

## Troubleshooting

- **MIME `text/plain` for JS/CSS**: ensure `mime.types` is included; `alias /static/` / path correct.
- **`the input device is not a TTY`**: use `docker compose exec -T` for non-interactive commands (done in Makefile).
- **`DB not reachable`**: check `.env.*` (`DB_HOST=mysql`, `DB_PORT=3306`), startup order, healthchecks.
- **OIDC issues**:
  - Redirect URI must exactly match (including **port**),
  - `ALLOWED_HOSTS` & `CSRF_TRUSTED_ORIGINS` align with the URL,
  - Box clock is correct (JWTs are time-sensitive).

## 📄 License

eXamc is distributed under the **eXamc Non-Commercial License (NCL) v1.0**.

### ✔ Allowed
- Use in production for **non-commercial purposes**
- Use by **universities, public institutions, research groups, non-profits**, and individuals
- Modification and redistribution for **non-commercial use**, with attribution

### ❌ Not Allowed Without Permission
- Any **commercial use**
- Selling or licensing the software
- Offering a **SaaS** or hosted service based on eXamc
- Integrating eXamc into a commercial product or paid service
- Using eXamc in a for-profit context

A separate commercial license may be granted upon request.

👉 See the full license text in [`LICENSE`](./LICENSE).

## 🙋 Support

For questions or assistance regarding eXamc, please contact[cepro-exams@epfl.ch](mailto:cepro-exams@epfl.ch).