# eXamc — README-deploy (TEST / PROD)

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


This is a **deployment playbook** for **TEST** and **PROD** environments.

Stack:
- Orchestration: Docker Compose (or your orchestrator)
- Reverse proxy: **Nginx** (with **TLS**)
- App server: **Gunicorn** (WSGI)
- Services: **MySQL**, **Redis**, **Celery**, **Celery Beat**
- SSO: **Entra ID** (Azure AD)

> ⚠️ In TEST/PROD: **no `runserver`**, **no auto-migrations on boot**, **HTTPS required**.

---


## 0) Deployment with Ansible

This repository now uses **Ansible + Vault** to render environment files and deploy TEST/PROD.

**Structure**
```
ansible/
├── inventory/
│   ├── test/hosts.ini
│   └── prod/hosts.ini
├── group_vars/
│   ├── test/
│   └── prod/
├── templates/
│   └── .env.j2
└── playbooks/
    └── deploy.yml
```

**Deploy commands**
```bash
# TEST
ansible-playbook -i ansible/inventory/test/hosts.ini ansible/playbooks/deploy.yml -e env=test --vault-id @prompt
# PROD
ansible-playbook -i ansible/inventory/prod/hosts.ini ansible/playbooks/deploy.yml -e env=prod --vault-id @prompt
```

The playbook will:
1. Render `/opt/examc/.env` from `.env.j2`
2. Decrypt secrets from `group_vars/<env>/vault.yml`
3. Run `docker compose up -d --build` remotely

> This **replaces manual `.env.test` / `.env.prod` editing**; keep `.env.example` as a reference.


## 1) Prereqs & secrets

- Prepare non-versioned env files: `.env.test`, `.env.prod`.
- Provide secrets via your secrets store or secured files:
  - `SECRET_KEY`
  - `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`
  - `OIDC_CLIENT_SECRET`
  - TLS certs (`.crt`/`.key`) if not using ACME
- DNS:
  - TEST: `examc-test.epfl.ch`
  - PROD: `examc.epfl.ch`

---

## 2) Nginx TLS (nginx.ssl.conf)

Example **vhost** per environment (adapt cert paths):

```nginx
events {}
http {
  include       mime.types;
  default_type  application/octet-stream;
  sendfile on;
  server_tokens off;

  upstream web_upstream {
    server web:8000;  # Gunicorn in 'web' service
  }

  server {
    listen 443 ssl http2;
    server_name examc-test.epfl.ch;  # prod: examc.epfl.ch

    ssl_certificate     /etc/nginx/ssl/fullchain.crt;
    ssl_certificate_key /etc/nginx/ssl/privkey.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    client_max_body_size 50m;

    # Static & media (public)
    location /static/ { alias /static/; access_log off; expires 7d; }
    location /media/  { alias /media/;  access_log off; expires 7d; }

    # Private media via X-Accel
    location /_protected/ {
      internal;
      alias /private_media/;
    }

    location / {
      proxy_pass         http://web_upstream;
      proxy_set_header   Host $host;
      proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header   X-Forwarded-Proto $scheme;
      proxy_read_timeout 120s;
    }

    location /healthz { return 200 "ok"; }
  }

  # HTTP -> HTTPS redirect
  server {
    listen 80;
    server_name examc-test.epfl.ch;  # prod: examc.epfl.ch
    return 301 https://$host$request_uri;
  }
}
```

Expected Compose mounts:
- `/static:ro`, `/media:ro`, `/private_media:ro`
- `/etc/nginx/ssl:ro` (if mounting cert files)

---

## 3) Gunicorn (web)

- Start Gunicorn from **entrypoint** or Compose `command`, e.g.:
  ```bash
  gunicorn examc.wsgi:application -c /app/deploy/gunicorn.conf.py
  ```
- Suggested tuning (adjust to CPU/RAM):
  - workers = `2*CPU + 1` (or start with `4–8`), class `sync` or `gthread`
  - timeout = `120` for heavier views (otherwise 30)
  - `accesslog`/`errorlog` to stdout

> In prod, disable `DEBUG`, enable `SECURE_SSL_REDIRECT=1`, cookies `*_SECURE=1`, enable **HSTS** (6 months).

---

## 4) Release cycle (TEST/PROD)

1. **Prepare** artifacts  
   - Git tag (`vX.Y.Z`), build images (web/celery/celery_beat), push to registry (if used).

2. **Controlled stop** (if needed)  
   - You can deploy hot, but schedule maintenance if intrusive migrations are planned.

3. **Migrations** (manual/CI)
   ```bash
   docker compose -f compose/base.yml -f compose/prod.yml --env-file .env.prod      exec web python manage.py migrate --noinput
   docker compose ... exec web python manage.py collectstatic --noinput
   ```

4. **Reload Gunicorn/Nginx**
   - **Hot reload Gunicorn** (if supported):
     ```bash
     docker compose ... exec web kill -HUP 1
     ```
     or restart `web` (short hiccup):
     ```bash
     docker compose ... up -d --no-deps --build web
     ```
   - **Nginx**:
     ```bash
     docker compose ... exec nginx nginx -t
     docker compose ... exec nginx nginx -s reload
     ```

5. **Validation**
   - `curl -I https://examc.epfl.ch/healthz` → 200
   - Key user journeys (OIDC login, main views, protected download).

---

## 5) Celery & Beat

- **Celery worker** (needs Redis & Django):
  ```bash
  celery -A examc worker -l INFO --concurrency=8
  ```
- **Celery Beat** (DB scheduler):
  ```bash
  celery -A examc beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
  ```
- Healthchecks: PID/port or `celery inspect ping` via script.

---

## 6) MySQL backups & restore

- **Backup** (cron/CI): `mysqldump` + gzip, offsite storage.
- **Restore**:
  ```bash
  gunzip -c dump.sql.gz | mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"
  ```
- Ensure **utf8mb4** (tables & connection).

---

## 7) Logs & monitoring

- Nginx access/error → stdout
- Gunicorn access/error → stdout
- Django → stdout (or route to syslog/ELK/Sentry)
- Celery/Beat → stdout
- Healthchecks: `/healthz` from LB/monitoring (e.g. every 30s)

---

## 8) Security

- HTTPS required (TLS ≥ 1.2)
- HSTS (6 months), `Secure` cookies, `SECURE_SSL_REDIRECT=1`
- Strict `ALLOWED_HOSTS` for test/prod
- Rotate secrets (DB, OIDC)
- Regularly update base images & Python deps
- Limit upload size via Nginx (`client_max_body_size 50m`)

---

## 9) Pre/Post-release checklist

### Before
- [ ] Git tag and image builds OK
- [ ] `.env.<env>` complete (secrets provided)
- [ ] TLS certs OK (or ACME ready)
- [ ] Maintenance window communicated (if needed)

### Deploy
- [ ] `docker compose up -d --build` (services healthy)
- [ ] `migrate` + `collectstatic`
- [ ] Reload Gunicorn + Nginx

### After
- [ ] `/healthz` → 200 (https)
- [ ] OIDC login OK
- [ ] Critical user journeys OK
- [ ] Monitoring/alerting OK
- [ ] (Optional) Post-release backup

---

## 10) OIDC notes (Entra ID)

- Redirect URIs must match exactly (https + final host)
- Keep clock skew minimal (NTP accurate)
- Scopes: `openid profile email` (extend as needed)
- CSRF/ALLOWED_HOSTS configured for your domains

---

## 11) Quick rollback

- Revert to previous image tag (`vX.Y.(Z-1)`)
- Restore DB if migration can’t be reversed
- Reload Gunicorn/Nginx
