# Internship CRM: developer shortcuts. Run `make help` for the list.
SHELL := /bin/bash
.DEFAULT_GOAL := help

DB ?= internship_dev
MODULE ?= all
ODOO := internship_odoo
PG := internship_postgres

.PHONY: help config up down restart logs shell odoo-shell psql init upgrade upgrade-apply \
        upgrade-legacy test test-db demo-data backup restore clone lint format

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

config: ## Create .env and config/odoo.conf from the examples (never overwrites)
	@test -f .env || { cp .env.example .env && echo "Created .env"; }
	@test -f config/odoo.conf || { cp config/odoo.conf.example config/odoo.conf && echo "Created config/odoo.conf"; }

up: config ## Start the stack
	docker compose up -d

down: ## Stop the stack (volumes are kept)
	docker compose down

restart: ## Restart Odoo (reload Python code)
	docker restart $(ODOO)

logs: ## Follow Odoo logs
	docker logs -f --tail=200 $(ODOO)

shell: ## Bash shell in the Odoo container
	docker exec -it $(ODOO) bash

odoo-shell: ## Odoo Python shell on DB (make odoo-shell DB=...)
	docker exec -it $(ODOO) bash -c 'odoo shell -c /etc/odoo/odoo.conf --db_host "$$HOST" --db_user "$$USER" --db_password "$$PASSWORD" -d $(DB) --http-port=8070'

psql: ## psql on DB (make psql DB=...)
	docker exec -it $(PG) psql -U $${POSTGRES_USER:-odoo} -d $(DB)

init: ## Create DB and install all modules (make init DB=... DEMO=1)
	scripts/init_db.sh $(DB) $(if $(DEMO),--demo)

upgrade: ## Backup, clone, upgrade + test the clone (real DB untouched)
	scripts/upgrade.sh $(DB)

upgrade-legacy: ## Like upgrade, but seeds pre-v2 sample rows into the clone first (tests migrations)
	scripts/upgrade.sh $(DB) --legacy-fixture

upgrade-apply: ## Same as upgrade, then upgrade the real DB
	scripts/upgrade.sh $(DB) --apply

test: ## Run tests on a fresh throwaway DB (make test MODULE=internship_base)
	scripts/test.sh $(MODULE)

test-db: ## Upgrade + test an existing clone (make test-db DB=internship_dev_upgrade_test)
	scripts/test.sh $(MODULE) --db $(DB)

demo-data: ## Load workflow demo data into a DEMO database (make demo-data DB=internship_v2_demo)
	scripts/demo_data.sh $(DB)

backup: ## Back up DB + filestore into backups/
	scripts/backup_db.sh $(DB)

restore: ## Restore a backup (make restore BACKUP=backups/<dir> [DB=...] [FORCE=1])
	@test -n "$(BACKUP)" || { echo "Usage: make restore BACKUP=backups/<dir> [DB=name] [FORCE=1]"; exit 1; }
	scripts/restore_db.sh $(BACKUP) $(if $(filter-out internship_dev,$(DB)),$(DB)) $(if $(FORCE),--force)

clone: ## Clone DB to TARGET (make clone DB=internship_dev TARGET=internship_copy)
	@test -n "$(TARGET)" || { echo "Usage: make clone [DB=src] TARGET=dst"; exit 1; }
	scripts/clone_db.sh $(DB) $(TARGET)

lint: ## Run all pre-commit checks (ruff, pylint-odoo, XML, whitespace)
	pre-commit run --all-files

format: ## Auto-format Python with ruff
	ruff format custom_addons && ruff check --fix custom_addons
