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

# Compose files per env (dev = base + dev.yml ; test/prod add other overrides)
COMPOSE_FILES := -f compose/base.yml -f compose/$(ENV).yml
export COMPOSE_PROJECT_NAME := $(PROJECT)

# Enable mysql-dockerized profile **only** for dev
ifeq ($(ENV),dev)
  export COMPOSE_PROFILES := mysql-dockerized
endif

# Optionnal Seed file (DB) ('make seed')
SEED_FILE ?= deploy/db/dev-seed.sql.gz

# Export project name for stable names (networks/volumes/containers)
export COMPOSE_PROJECT_NAME := $(PROJECT)

# Helper Compose
DC := docker compose $(COMPOSE_FILES)

# =========[ Help ]=========
.PHONY: help
help:
	@echo "Targets principaux :"
	@echo "  make up              - build & démarre tout (selon ENV=$(ENV))"
	@echo "  make build           - (re)build & up des services"
	@echo "  make down            - stoppe le stack"
	@echo "  make reset           - down -v (supprime volumes) + orphelins"
	@echo "  make ps              - affiche l'état des services"
	@echo "  make logs            - logs de tous les services (suivi)"
	@echo "  make web-shell       - shell dans le conteneur web"
	@echo "  make migrate         - django migrate"
	@echo "  make makemigrations  - django makemigrations"
	@echo "  make collectstatic   - django collectstatic"
	@echo "  make createsuperuser - django createsuperuser (interactif)"
	@echo "  make health          - vérifie /healthz via Nginx"
	@echo "  make seed            - importe le seed si DB vide (profil 'seed')"
	@echo "  make dbshell         - ouvre un shell MySQL dans le conteneur"
	@echo "  make dbdump          - export DB -> ./deploy/db/dump-YYYYmmdd.sql.gz"
	@echo "  make prune           - nettoie images non utilisées"
	@echo "  make rebuild-web     - rebuild uniquement le service web"
	@echo
	@echo "Variables : ENV=dev|test|prod  PROJECT=$(PROJECT)  ENV_FILE=$(ENV_FILE)"
	@echo "Exemples : make up ENV=test    |    make seed SEED_FILE=deploy/db/foo.sql.gz"

# =========[ Life cycle ]=========
.PHONY: up build down reset ps logs
up: ensure-env
	$(DC) up -d --build

build: ensure-env
	$(DC) up -d --build

down:
	$(DC) down

reset:
	$(DC) down -v --remove-orphans

ps:
	$(DC) ps

logs:
	$(DC) logs -f --tail=200

# =========[ Django utilities ]=========
.PHONY: web-shell migrate makemigrations collectstatic createsuperuser
web-shell:
	$(DC) exec web bash -lc 'exec bash'

migrate:
	$(DC) exec -T web bash -lc 'python manage.py migrate --noinput'

makemigrations:
	$(DC) exec -T web bash -lc 'python manage.py makemigrations'

collectstatic:
	$(DC) exec -T web bash -lc 'python manage.py collectstatic --noinput'

createsuperuser:
	$(DC) exec web bash -lc 'python manage.py createsuperuser'

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
.PHONY: prune rebuild-web rebuild-all
prune:
	docker image prune -f

rebuild-web:
	$(DC) up -d --build web

rebuild-all:
	$(DC) up -d --build

# =========[ usefule shortcuts ]=========
.PHONY: open web-logs celery-logs beat-logs
open:
	@python -c 'import webbrowser; webbrowser.open("http://127.0.0.1:8000")'

web-logs:
	$(DC) logs -f --tail=200 web

celery-logs:
	$(DC) logs -f --tail=200 celery

beat-logs:
	$(DC) logs -f --tail=200 celery_beat
