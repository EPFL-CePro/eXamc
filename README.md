# eXamc — Django + MySQL + Redis + Celery (Docker)

---

### ✨ New: Automated with Ansible + Vault

This project now uses **Ansible** to manage all environment configuration and deployment securely.

- 🔐 **Secrets** are stored encrypted with **Ansible Vault** (`ansible/group_vars/<env>/vault.yml`).
- 🧩 **Environment files** (`.env.dev`, `.env.test`, `.env.prod`) are **generated automatically** from a Jinja2 template (`.env.j2`).
- 🚀 **Local dev**: run `make env ENV=dev` to create `.env.dev`, then `make up ENV=dev`.
- 🌍 **TEST / PROD**: deploy using:
  ```bash
  ansible-playbook -i ansible/inventory/prod/hosts.ini ansible/playbooks/deploy.yml -e env=prod --vault-id @prompt
  ```

> This replaces manual `.env.*` editing while keeping `.env.example` as a public reference.

---


Dockerized environment for **eXamc** featuring:
- **Django** (web), **Gunicorn** (prod) / **runserver** (dev)
- **MySQL 8.4**
- **Redis 7** (Celery broker/results)
- **Celery** (worker) + **Celery Beat**
- **Nginx** (reverse proxy + static/media)
- **Private media** via **Nginx X-Accel-Redirect**

> ⚠️ Internal repo note: the app relies on **Entra ID** (Azure AD) configuration.  
> Do **not** commit any real `.env.*` files or DB dumps.

---

## Table of Contents

- [Prerequisites](#prerequisites)  
- [Layout](#layout)  
- [Environment files](#environment-files)  
- [Entra ID (OIDC) parameters](#entra-id-oidc-parameters)  
- [Run in DEV](#run-in-dev)  
- [Makefile commands](#makefile-commands)  
- [DB seed / import / export (optional)](#db-seed--import--export-optional)  
- [MySQL Workbench access](#mysql-workbench-access)  
- [Private media](#private-media)  
- [Migrations & updates](#migrations--updates)  
- [TEST / PROD overview](#test--prod-overview)  
- [Troubleshooting](#troubleshooting)

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
├─ compose/
│  ├─ base.yml
│  ├─ dev.yml
│  ├─ test.yml
│  └─ prod.yml
├─ deploy/
│  ├─ entrypoint.sh
│  ├─ gunicorn.conf.py
│  └─ nginx/
│     ├─ nginx.dev.conf
│     └─ nginx.ssl.conf            # used in test/prod
├─ examc/                          # settings/urls/wsgi/asgi
├─ examc_app/                      # Django app(s)
├─ Dockerfile
├─ Makefile
├─ requirements.txt
├─ .env.example                    # sample env (no secrets)
└─ README.md
```


---

## 🧰 Ansible-managed environments (preferred)

> This section **adds** an automated workflow without removing the manual approach below.

- Secrets and env values are generated from **Ansible templates** and **Vault-encrypted** variables.
- Template: `ansible/templates/.env.j2`
- Per-environment vars:
  - Non-sensitive: `ansible/group_vars/<env>/app.yml`
  - **Secrets (encrypted):** `ansible/group_vars/<env>/vault.yml`

Generate your local `.env.dev`:
```bash
make env ENV=dev
```

Then start the stack:
```bash
make up ENV=dev
```

> If `.env.dev` is missing, `make up` will prompt you to run `make env` first.
> Real `.env.*` files remain **untracked** (ignored by Git). Keep `.env.example` for reference.

---


`.gitignore` excludes: `.env.*` (keep `.env.example`), SQL dumps, `media/`, `export_tmp/`, `__pycache__`, etc.  
`.dockerignore` excludes: `.git`, `.env.*`, dumps, `media/`, caches, etc.

---

## Environment files

Create one per environment **locally** (not versioned), from `.env.example`:

```bash
cp .env.example .env.dev
cp .env.example .env.test
cp .env.example .env.prod
```

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
MEDIA_ROOT=/media
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

---

## Makefile commands

```bash
make up             # build + start
make down           # stop
make reset          # stop + remove volumes (DB data!)
make ps             # status
make logs           # tail logs for all services

make web-shell      # shell inside web container
make makemigrations # django makemigrations
make migrate        # django migrate
make collectstatic  # django collectstatic
make createsuperuser

make health         # HEAD /healthz via Nginx
make nginx-reload   # test & reload Nginx

make dbshell        # mysql client (root) inside container
make dbdump         # export DB -> deploy/db/dump-YYYYmmdd_HHMMSS.sql.gz
make dbimport FILE=deploy/db/foo.sql.gz  # import .sql(.gz)

make rebuild-web    # rebuild web service only
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

- Mounted under **`/private_media`** (web/nginx).  
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
  docker compose ... exec web python manage.py migrate --noinput
  docker compose ... exec web python manage.py collectstatic --noinput
  # reload Gunicorn/Nginx
  ```

---

## TEST / PROD overview

- Overrides: `compose/test.yml`, `compose/prod.yml`
- **HTTPS** via `nginx.ssl.conf` + certs (ACME/Let’s Encrypt or internal)
- Security: `SECURE_SSL_REDIRECT=1`, cookie `*_SECURE=1`, **HSTS** enabled
- **Gunicorn** in front (never `runserver`)
- Controlled migrations, centralized logging, backups, monitoring

---


**Ansible deployment (TEST/PROD):**
```bash
ansible-playbook -i ansible/inventory/<env>/hosts.ini   ansible/playbooks/deploy.yml   -e env=<env>   --vault-id @prompt
```
This playbook renders `/opt/examc/.env` from `.env.j2`, decrypts Vault values, and runs `docker compose up -d --build` on the target host.

## Troubleshooting

- **MIME `text/plain` for JS/CSS**: ensure `mime.types` is included; `alias /static/` / `alias /media/` paths correct.
- **`the input device is not a TTY`**: use `docker compose exec -T` for non-interactive commands (done in Makefile).
- **`DB not reachable`**: check `.env.*` (`DB_HOST=mysql`, `DB_PORT=3306`), startup order, healthchecks.
- **OIDC issues**:
  - Redirect URI must exactly match (including **port**),
  - `ALLOWED_HOSTS` & `CSRF_TRUSTED_ORIGINS` align with the URL,
  - Box clock is correct (JWTs are time-sensitive).
