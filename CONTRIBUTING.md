# Contributing

## Setup

```sh
make up            # creates .env and config/odoo.conf from the examples, starts Docker
make init DEMO=1   # new database internship_dev with all modules + demo data
pip install pre-commit && pre-commit install
```

Optional debugger: `cp docker-compose.override.yml.example docker-compose.override.yml`,
then `docker compose up -d --build` and use the **Attach to Odoo (debugpy)** launch
configuration in VS Code.

## Branches

- `main` is always deployable.
- Feature work: `v2/<topic>` (for example `v2/workflow-redesign`) or `feat/<topic>`,
  `fix/<topic>`. Open a pull request into `main`; CI must be green.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat(internship_placement): add university review wizard
fix(internship_vapi): reject webhook calls without a token
chore: add backup and clone scripts
```

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci`, `build`.
The scope is the module name when the change is inside one module.

## Rules that protect existing data

These rules are not optional. Production databases hold real student data.

1. **Never modify Odoo core.** Only `custom_addons/`, `config/`, `scripts/`, `.github/`,
   `.vscode/` and `docs/`.
2. **Never rename or delete** an existing model, field or selection key directly.
   - Add the new field, relabel the old one (`string=`), and move data with a migration.
   - Deprecate the old field with `deprecated="Replaced by X in 19.0.2"`, remove it from
     views, keep the column. Drop it only in a later major version (19.0.3+) via a migration.
   - Selections are extended with `selection_add=[...]` plus an `ondelete={...}` policy.
3. **Every schema change that affects existing rows ships with a migration** in
   `custom_addons/<module>/migrations/<new_version>/pre-migrate.py` or `post-migrate.py`,
   and the manifest `version` is bumped to `<new_version>`.
4. **Migrations are idempotent.** Check that a table/column exists
   (`information_schema`) before touching it, skip rows already migrated, log counts with
   `_logger.info`, and never `DROP` a column.
5. **Test every upgrade on a clone first**: `make upgrade` backs up the database, clones
   it to `<db>_upgrade_test`, upgrades and tests the clone, and leaves the real database
   untouched. Only then `make upgrade-apply`.

### Versions and when migrations run

Module versions follow the Odoo series: `19.0.<major>.<minor>.<patch>`. Odoo runs a
migration folder `migrations/X/` only when upgrading from an installed version **below**
`X` to a code version **at or above** `X`.

v2 is developed across several phases, all at `19.0.2.0.0`. Keep your real development
database on the pre-v2 version (don't `make upgrade-apply`) until the v2 migrations are
complete. Otherwise the database gets marked `19.0.2.0.0` and later-phase migrations in
`migrations/19.0.2.0.0/` never run on it. `make upgrade` always re-clones from the
untouched database, so every phase is tested against real pre-v2 data.

## Code style

- PEP 8 with ruff (line length 120); `make lint` runs ruff, pylint-odoo and the XML checks.
- Model names `internship.*`, Python classes `PascalCase`, XML ids `snake_case`,
  one model per file.
- Business logic lives in model methods or `services/`, not in controllers.
- Every user-facing string is translatable: `_("...")` or `self.env._("...")`.
- Odoo 19 conventions: `models.Constraint`, `res.groups.privilege`, `group_ids`,
  `<list>` views, inline `invisible=`/`readonly=` (no `attrs`).
- Check an API in the Odoo 19 source before using it:
  `docker exec internship_odoo grep -rn "<name>" /usr/lib/python3/dist-packages/odoo`.

## Secrets

API keys and tokens live in `.env` (gitignored) or in Odoo system parameters, entered
through Settings. `config/odoo.conf` is gitignored; edit `config/odoo.conf.example`
for shared defaults.
