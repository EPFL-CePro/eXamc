# =======[ Ansible ]=======
ANSIBLE_PLAYBOOK ?= ansible-playbook
ANS_DIR          ?= ansible

# Generate local .env via Ansible (Ask for Vault if needed)
.PHONY: env
env:
	$(ANSIBLE_PLAYBOOK) $(ANS_DIR)/playbooks/render_env_local.yml \
	  -e env=$(ENV) -e dest=$$(pwd)/$(ENV_FILE) --vault-id @prompt

# Check .env exists. Otherwise suggest make env
.PHONY: ensure-env
ensure-env:
	@if [ ! -f "$(ENV_FILE)" ]; then \
	  echo "❌ $(ENV_FILE) not found. Generate with : make env ENV=$(ENV)"; \
	  exit 1; \
	fi


SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
# =========[ Config ]=========
# Usage : make <target> [ENV=dev] [PROJECT=examc]
ENV ?= dev
PROJECT ?= examc
export ENV_FILE := .env.${ENV}

# Compose files per env (dev = dev.yml ; test/prod add other overrides)
COMPOSE_FILES := -f compose/$(ENV).yml
export COMPOSE_PROJECT_NAME := $(PROJECT)

# Enable mysql-dockerized profile **only** for dev
ifeq ($(ENV),dev)
  export COMPOSE_PROFILES := mysql-dockerized
endif

# Optional Seed file (DB) ('make seed')
SEED_FILE ?= deploy/db/dev-seed.sql.gz

# Export project name for stable names (networks/volumes/containers)
export COMPOSE_PROJECT_NAME := $(PROJECT)

# Helper Compose
DC := docker compose --env-file .env.${ENV} $(COMPOSE_FILES)

# =========[ Help ]=========
.PHONY: help
help:
	@echo "Targets principaux :"
	@echo "  make up              - build & starts everything (using ENV=$(ENV))"
	@echo "  make build           - (re)builds & starts services"
	@echo "  make tests           - starts tests (using compose/dev.yaml) config"
	@echo "  make down            - stop everything"
	@echo "  make reset           - stop + remove volumes (DB data!)"
	@echo "  make ps              - status"
	@echo "  make logs            - tail logs for all services"
	@echo ""
	@echo "  make django-shell    - shell inside django container"
	@echo "  make makemigrations  - django makemigrations"
	@echo "  make migrate         - django migrate"
	@echo "  make collectstatic   - django collectstatic"
	@echo "  make createsuperuser - django createsuperuser (interactif)"
	@echo ""
	@echo "  make health          - check /healthz via Nginx"
	@echo "  make nginx-reload 	  - test & reload Nginx"
	@echo ""
	@echo "  make seed            - importe le seed si DB vide (profil 'seed')"
	@echo "  make dbshell         - mysql client (root) inside container"
	@echo "  make dbdump          - export DB -> deploy/db/dump-YYYYmmdd_HHMMSS.sql.gz"
	@echo "  make dbimport FILE=deploy/db/foo.sql.gz  - import .sql(.gz)"
	@echo ""
	@echo "  make rebuild-django  - rebuild django service only"
	@echo "  make prune           - prune dangling images"
	@echo
	@echo "Variables : ENV=dev|test|prod  PROJECT=$(PROJECT)  ENV_FILE=$(ENV_FILE)"
	@echo "Exemples : make up ENV=test    |    make seed SEED_FILE=deploy/db/foo.sql.gz"

# =========[ Life cycle ]=========
.PHONY: up build down reset ps logs
up: ensure-env
	$(DC) up -d --build

build: ensure-env
	$(DC) up -d --build

tests:
	$(DC) run --rm django pytest

down:
	$(DC) down

reset:
	$(DC) down -v --remove-orphans

ps:
	$(DC) ps

logs:
	$(DC) logs -f --tail=200

# =========[ Django utilities ]=========
.PHONY: django-shell migrate makemigrations collectstatic createsuperuser
django-shell:
	$(DC) exec django bash -lc 'exec bash'

migrate:
	$(DC) exec -T django bash -lc 'python manage.py migrate --noinput'

makemigrations:
	$(DC) exec -T django bash -lc 'python manage.py makemigrations'

collectstatic:
	$(DC) exec -T django bash -lc 'python manage.py collectstatic --noinput'

createsuperuser:
	$(DC) exec django bash -lc 'python manage.py createsuperuser'

# =========[ Quick healthchecks ]=========
.PHONY: health nginx-reload
health:
	@echo "Ping /healthz via Nginx (http://localhost:8000/healthz/)"
	@curl -sfI http://localhost:8000/healthz/ || true

nginx-reload:
	$(DC) exec nginx nginx -t
	$(DC) exec nginx nginx -s reload

# =========[ Seed & DB ]=========
.PHONY: seed dbshell dbdump dbimport
seed:
	@if [ ! -f "$(SEED_FILE)" ]; then echo "Seed file not found: $(SEED_FILE)"; exit 1; fi
	$(DC) --profile seed run --rm db_seed

dbshell:
	# Opem mysql client inside the MySQL container (use vars from $(ENV_FILE))
	$(DC) exec mysql sh -lc 'mysql -uroot -p"$$MYSQL_ROOT_PASSWORD"'

dbdump:
	@mkdir -p deploy/db
	@ts=$$(date +%Y%m%d_%H%M%S); \
	echo "Dump -> deploy/db/dump-$$ts.sql.gz"; \
	$(DC) exec mysql sh -lc 'mysqldump --default-character-set=utf8mb4 -u"$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE"' | gzip -9 > deploy/db/dump-$$ts.sql.gz; \
	echo "OK: deploy/db/dump-$$ts.sql.gz"

# Import .sql.gz in DB (usage: make dbimport FILE=deploy/db/foo.sql.gz)
FILE ?=
dbimport:
	@if [ -z "$(FILE)" ]; then echo "Usage: make dbimport FILE=deploy/db/foo.sql.gz"; exit 1; fi
	@if ! echo "$(FILE)" | grep -qE '\.sql(\.gz)?$$'; then echo "Le FILE doit être .sql ou .sql.gz"; exit 1; fi
	@if ! [ -f "$(FILE)" ]; then echo "Fichier introuvable: $(FILE)"; exit 1; fi
	@if echo "$(FILE)" | grep -q '\.gz$$'; then \
	  echo "Import .sql.gz -> $$MYSQL_DATABASE"; \
	  $(DC) exec -T mysql sh -lc 'gunzip -c - < /dev/stdin | mysql --default-character-set=utf8mb4 -u"$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE"' < "$(FILE)"; \
	else \
	  echo "Import .sql -> $$MYSQL_DATABASE"; \
	  $(DC) exec -T mysql sh -lc 'mysql --default-character-set=utf8mb4 -u"$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE"' < "$(FILE)"; \
	fi
	@echo "Import terminé."

# =========[ Maintenance ]=========
.PHONY: prune rebuild-django rebuild-all
prune:
	docker image prune -f

rebuild-django:
	$(DC) up -d --build django

rebuild-all:
	$(DC) up -d --build

# =========[ usefule shortcuts ]=========
.PHONY: open django-logs celery-logs beat-logs
open:
	@python -c 'import webbrowser; webbrowser.open("http://127.0.0.1:8000")'

django-logs:
	$(DC) logs -f --tail=200 django

celery-logs:
	$(DC) logs -f --tail=200 celery

beat-logs:
	$(DC) logs -f --tail=200 celery_beat
