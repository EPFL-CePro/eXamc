![Version](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2FEPFL-CePro%2FeXamc%2Frefs%2Fheads%2Fmain%2Fdjango%2Fapp%2Fpyproject.toml&query=%24.project.version&label=version&color=blue)
![License](https://img.shields.io/badge/license-NCL%20v1.0-red)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/EPFL-CePro/eXamc/refs/heads/main/django/app/pyproject.toml)
![CI](https://img.shields.io/github/actions/workflow/status/EPFL-CePro/eXamc/docker-build-test-and-push.yml?branch=main&label=CI)
![GitHub Issues](https://img.shields.io/github/issues/EPFL-CePro/eXamc)

<div style="text-align: center;">
    <img width="400" src="https://raw.githubusercontent.com/EPFL-CePro/eXamc/refs/heads/main/django/app/examc_app/static/img/eXamc.svg" alt="eXamc logo">
</div>

---

**eXamc** is a web application for written exams, from preparation to grades. Teachers write the exam and its scoring in the browser, generate the printable copies with [Auto Multiple Choice (AMC)](https://www.auto-multiple-choice.net/), upload the scans, and correct the open questions online with their reviewers. eXamc then computes the marks and grades, and gives the results and statistics by exam, section and question.

It also handles common exams shared by several courses, importing the students list, room plans and seat assignment, and exporting the grades.

### Stack

- **Django** on **Gunicorn** (prod), Python managed by **uv**
- **Vite** frontend (TypeScript/Sass, pnpm)
- **MySQL** and **Redis** (Celery broker/results)
- **Celery** (worker) + **Celery Beat**
- **Caddy** (reverse proxy, HTTPS, static files, private media, maintenance page)
- Images built on **Docker Hardened Images** (`dhi.io`), running as a non-root user
- **Ansible** for deployment: see [EPFL-CePro/eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops)

> [!IMPORTANT]
> This app relies on **Entra ID** (Azure AD) configuration. Do **not** commit any real `.env.*` files, secrets (`compose/secrets/`) or DB dumps.

---

## Table of Contents

<!-- TOC -->
  * [Prerequisites](#prerequisites)
  * [Layout](#layout)
  * [Configuration: `.env` and secrets](#configuration-env-and-secrets)
  * [Entra ID (OIDC) parameters](#entra-id-oidc-parameters)
  * [Run in DEV](#run-in-dev)
  * [Updating dependencies](#updating-dependencies)
  * [Makefile commands](#makefile-commands)
  * [DB seed / import / export (optional)](#db-seed--import--export-optional)
  * [Private media](#private-media)
  * [Users and file ownership](#users-and-file-ownership)
  * [Migrations & updates](#migrations--updates)
  * [STAGING / PROD overview](#staging--prod-overview)
  * [Troubleshooting](#troubleshooting)
  * [📄 License](#-license)
  * [🙋 Support](#-support)
<!-- TOC -->

---

## Prerequisites

- Docker & Docker Compose
- `make` (Linux/macOS; on Windows use WSL)
- A Docker Hub account with access to **Docker Hardened Images** (`docker login dhi.io`)
- [Ansible](https://docs.ansible.com/) and a checkout of [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops), which writes the `.env` and the secrets
- Free ports:
  - **Caddy:** `8443` in dev (`CADDY_PORT`, can be changed); `80` and `443` on staging / prod, not configurable.
  - **MySQL**, bound to `127.0.0.1` only: `3307` in dev and `3306` on staging / prod by default (`MYSQL_HOST_PORT`, can be changed).
- Access to your **Entra ID app registration** (to configure OIDC)

---

## Layout

```
.
├─ .github/
│  ├─ workflows/                    # CI workflows
│  └─ dependabot.yml                # Dependabot config (uv, pnpm, Docker, Compose, Actions; dhi.io registry)
├─ compose/                         # Docker Compose configurations
│  ├─ compose.base.yml              # Shared service definitions, defaults and image pins (not used directly)
│  ├─ compose.dev.yml               # Development environment
│  ├─ compose.test.yml              # Test/CI environment (no .env, no secrets)
│  ├─ compose.prod.yml              # Production environment (also used for the staging server)
│  ├─ secrets/                      # Dev secrets, one file per secret (not versioned)
│  ├─ data/                         # Local persistent data (not versioned)
│  │  └─ private_media/             # AMC projects, scans, exports, room plans (dev)
│  └─ deploy/                       # Deployment-related configuration
│     ├─ db/                        # Database init scripts and dev seed
│     └─ caddy/                     # Caddy configuration and maintenance page
├─ django/                          # Backend container
│  ├─ app/                          # Django application and Python project
│  │  ├─ docs/                      # Sphinx documentation
│  │  ├─ examc/                     # Django project: settings/urls/wsgi/asgi/celery
│  │  ├─ examc_app/                 # Main Django application
│  │  ├─ templates/                 # Django templates
│  │  ├─ gunicorn.conf.py
│  │  ├─ manage.py
│  │  ├─ pyproject.toml             # Main project configuration (version, dependencies)
│  │  └─ uv.lock
│  ├─ security/                     # Static security checks
│  │  ├─ check_forbidden_calls.py
│  │  ├─ check_require_post.py
│  │  └─ security_check.sh
│  ├─ Dockerfile                    # Backend image (dev, tooling, prod targets)
│  ├─ entrypoint.sh
│  ├─ install-build-deps.sh
│  └─ sphinx-autobuild.py           # Live-reload docs server (docs service in dev)
├─ frontend/                        # Frontend container
│  ├─ app/                          # Frontend source (Vite + TypeScript)
│  ├─ Dockerfile                    # Frontend image (dev, artifact targets)
│  └─ deploy-static.sh
├─ Security/                        # Security-related documentation
│  └─ local_security_checks.md
├─ Makefile
├─ CHANGELOG.md
├─ CODE_OF_CONDUCT.md
├─ LICENSE
├─ README.md
├─ README-deploy.md
└─ SECURITY.md
```

---

## Configuration: `.env` and secrets

Defaults live in `compose/compose.base.yml` (production values). Each environment's `.env` only overrides what differs (UID/GID, paths, site address, image tags, dev flags).

**Secrets are never in a `.env`.** Each one is a file in `SECRETS_DIR`, mounted by Compose at `/run/secrets/<name>`: `secret_key`, `mysql_root_password`, `mysql_password`, `redis_password`, `redis_acl`, `oidc_rp_client_id`, `oidc_rp_client_secret`, `tenant_id`, `oasis_base_url`, `oasis_bearer`, `tls_crt`, `tls_key`.

> [!WARNING]
> Every secret the Compose files mount must exist. A missing file makes `docker compose up` fail with `bind source path does not exist`, after the old containers have already been stopped.

The `.env` and the secrets of every environment are written by the [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops) playbook, from an Ansible Vault per environment. Nothing is created by hand.

| Environment | `.env`                      | Secrets                                   | Written by                                                      |
|-------------|-----------------------------|-------------------------------------------|-----------------------------------------------------------------|
| dev         | `.env.dev` in your checkout | `compose/secrets/`                        | [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops), locally   |
| staging     | `/opt/examc/.env.staging`   | `/srv/examc/secrets`                      | [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops), over SSH  |
| prod        | `/opt/examc/.env.prod`      | `/srv/examc/secrets`                      | [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops), over SSH  |
| tests       | none                        | none (fixed values in `compose.test.yml`) | n/a                                                             |

`.gitignore` excludes `.env.*` (except `.env.example`) and `compose/secrets/`.

---

## Entra ID (OIDC) parameters

1. **Create/Configure** an application in Azure Entra ID (your tenant).
2. **Allow** the redirect URI of each environment, including the port:
   - dev: `https://localhost:8443/oidc/callback/`
   - staging / prod: `https://<host>/oidc/callback/`
3. **Store** the client ID, the client secret and the tenant ID in the environment's vault in eXamc.ops (`oidc_rp_client_id`, `oidc_rp_client_secret`, `tenant_id`).

`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are derived from the site hosts of the environment by eXamc.ops.

---

## Run in DEV

```bash
# 1) From the eXamc.ops checkout: writes .env.dev and compose/secrets/, then starts the stack
ansible-playbook playbook.yml -i inventory/dev --vault-id @prompt -e branch=staging -e checkout=~/Documents/Projets/eXamc

# 2) Afterwards, from this repository
make up
make ps                 # all services "healthy"
make health             # HEAD /healthz → 200

# 3) Open
xdg-open https://localhost:8443   # (use open/start on macOS/Windows)
```

The playbook clones the repository into `checkout` if needed, or switches your checkout to `branch` (without discarding local changes). Rerun it when secrets or settings change. Caddy serves dev with its internal certificate: accept it once in the browser, or trust Caddy's local CA.

---

## Updating dependencies

This project uses [`uv`](https://docs.astral.sh/uv/) to manage Python dependencies. `uv` is installed in the `tooling` target of the Dockerfile (used by the test and dev environments):

```bash
docker compose -f compose/compose.test.yml run --rm django uv add dependency_name
docker compose -f compose/compose.test.yml run --rm django uv lock --upgrade    # every dependency, within pyproject.toml
docker compose -f compose/compose.test.yml run --rm django uv lock --upgrade-package django
```

This updates `django/app/pyproject.toml` and `django/app/uv.lock`. Frontend dependencies are managed with `pnpm` in `frontend/app/`.

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
docker compose -f compose/compose.test.yml build --target tooling django
```

**Dependabot** opens pull requests for security updates (Python, pnpm) and for the Docker images, Compose images, and GitHub Actions. It reads the hardened images from `dhi.io` with the `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` **Dependabot** secrets of the organization. Major Node.js versions are ignored: bump them by hand once they are LTS.

---

## Makefile commands

```bash
make up             # build & starts everything
make build          # (re)builds & starts services
make tests          # runs the tests (compose/compose.test.yml)
make down           # stop everything
make reset          # stop + remove volumes (DB data!)
make ps             # status
make logs           # tail logs for all services

make django-shell   # shell inside django container
make makemigrations # django makemigrations
make migrate        # django migrate
make collectstatic  # django collectstatic
make createsuperuser

make health         # HEAD /healthz through Caddy

make dbshell        # mysql client (root) inside container
make dbdump         # export DB -> deploy/db/dump-YYYYmmdd_HHMMSS.sql.gz
make dbimport FILE=deploy/db/foo.sql.gz  # import .sql(.gz)

make rebuild-django # rebuild django service only
make prune          # prune dangling images
```

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
- **Dev seed**: provide `deploy/db/dev-seed.sql.gz` (not versioned). In dev, the `mysql-init` service loads it **only if the DB is empty**: the hardened MySQL image ignores `docker-entrypoint-initdb.d`.

---

## Private media

- Stored on the host in `PRIVATE_MEDIA_DIR` (dev: `compose/data/private_media/`; servers: `/srv/examc/private_media`), mounted at **`/private_media`** in the containers.
- Never served directly: Django checks the user's access, then hands the file over to Caddy.
- Each exam's files are under `projects/<exam id>/`. Exams with a legacy `<year>/<semester>/<code>_<date>` folder are moved there the next time their settings are saved.
- Settings:
  ```python
  PRIVATE_MEDIA_ROOT = os.environ.get("PRIVATE_MEDIA_ROOT", "/private_media")
  ```

---

## Users and file ownership

The images run as non-root users, so the files they write must belong to them:

| Container          | User (UID:GID)                       | Needs to write                                  |
|--------------------|--------------------------------------|-------------------------------------------------|
| django, celery(-beat) | `examc` (1500:1500 on servers; your UID in dev) | private media, the media and static volumes |
| mysql, redis       | 65532                                | their data volumes                              |

On servers, [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops) creates the `examc` user and gives it the private media. When moving data from an older setup, change the owner of the volumes too, e.g.:

```bash
docker run --rm -v examc-prod_static_volume:/data alpine chown -R 1500:1500 /data
```

The secrets folder is root only (`0700`) with files readable by all (`0444`): Docker mounts each file into its container as root, so every container can read its own secret, but no other user of the server can.

---

## Migrations & updates

- **DEV**: entrypoint auto-runs `migrate` (and `collectstatic` if `COLLECTSTATIC=1`).
- **STAGING/PROD**: **no auto-migrate** at boot. Apply migrations after a deploy:
  ```bash
  cd /opt/examc
  alias dc='docker compose -p examc-prod --env-file .env.prod -f compose/compose.prod.yml'
  dc exec django python manage.py migrate --noinput
  ```

> [!IMPORTANT]
> Always use the project name, env file and Compose file of the deploy (the `dc` alias above). Without them, Compose creates a second set of containers.

---

## STAGING / PROD overview

- Compose file: `compose/compose.prod.yml` (staging and prod), images `ghcr.io/epfl-cepro/examc-*` tagged `staging` / `stable`
- **HTTPS** is handled by the Caddy container (certificates from the vault in prod, internal certificate in staging); no web server runs on the host
- Security: `SECURE_SSL_REDIRECT=1`, cookie `*_SECURE=1`, **HSTS** enabled
- **Gunicorn** in front (never `runserver`)
- Deployed with [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops): secrets, `.env`, checkout, `docker compose up --wait`

Tests run without MySQL and Redis (SQLite and in-memory Celery):

```bash
make tests
# or
docker compose -f compose/compose.test.yml run --rm --remove-orphans django
```

---

## Troubleshooting

- **`bind source path does not exist: …/secrets/<name>`**: a secret the Compose files mount is missing from the vault. Add it in eXamc.ops and rerun the playbook.
- **`Permission denied` in the logs** (Django, `collectstatic`, Redis `dump.rdb`, MySQL `binlog.index`): a folder or volume still belongs to the previous user. See [Users and file ownership](#users-and-file-ownership).
- **`/healthz/` answers `301`**: the request reached Django over HTTP without Caddy's `X-Forwarded-Proto`, and `SECURE_SSL_REDIRECT` redirects it.
- **`the input device is not a TTY`**: use `docker compose exec -T` for non-interactive commands (done in Makefile).
- **`DB not reachable`**: check the startup order and the health checks (`make ps`), and the MySQL logs.
- **OIDC issues**:
  - The redirect URI must match exactly, including the **port** (`8443` in dev),
  - `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` must match the URL (set from the site hosts in [eXamc.ops](https://github.com/EPFL-CePro/eXamc.ops)),
  - The clock of the machine must be correct (JWTs are time-sensitive).

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

For questions or assistance regarding eXamc, please contact [cepro-exams@epfl.ch](mailto:cepro-exams@epfl.ch).