## What and why

<!-- One or two sentences. Link the issue or phase (e.g. "v2 Phase 2: placement hub"). -->

## Changes

- Modules touched:
- Models/fields added or changed:
- Views/menus:

## Data safety

- [ ] No existing model, field or selection key was renamed or deleted (relabel + migrate instead)
- [ ] Every schema change that affects existing rows has an idempotent migration in `migrations/<version>/`
- [ ] Manifest `version` bumped where migrations were added
- [ ] Upgrade tested on a cloned DB: `make upgrade` (paste the summary below)
- [ ] Not applicable: no schema change

```
<!-- make upgrade output: module versions + test result -->
```

## Checks

- [ ] `make lint` passes
- [ ] `make test` passes (fresh DB with demo data)
- [ ] New user-facing strings are translatable (`_()` / `self.env._()`)
- [ ] Access rights (`ir.model.access.csv`) and record rules added for new models
- [ ] No secrets, tokens or personal data committed

## Screenshots / notes for reviewers
