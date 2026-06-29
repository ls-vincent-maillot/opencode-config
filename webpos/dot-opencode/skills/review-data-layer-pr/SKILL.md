---
name: review-data-layer-pr
description: Review checklist for merchantos/webPOS PRs that add a new entity (table), new column, or repository to the data layer. Use when reviewing PRs touching includes/data/model/, includes/data/io/sql/, includes/database/bs_*.class.php, src/Domain/<feature>/<entity>Repository.php, or DIC.config.php with new repository bindings.
---

# Review a webPOS Data Layer PR

A focused review skill for data-layer PRs. Defers the actual conventions to:

- **`r-series-data-layer-conventions/SKILL.md`** — the full data-layer authoring rules (nullable fields, type conventions, append-only patterns, FK annotations, naming, etc.). When checking a PR, walk that skill's items against the diff.
- **`schema-ddl/SKILL.md`** — DDL conventions (file placement, FK ban, index naming, timestamp columns, low-cardinality index rule).
- **`r-series-repository-tests/SKILL.md`** — expected test shape (transactional vs unit, append-only test pattern, dataProvider for forbidden-method tests).

Use `review-webpos-pr/SKILL.md` for the overall review workflow; this skill drops in for the data-layer-specific phase.

## When this skill applies

The PR touches any of:

- `includes/data/model/*.class.php` — model classes
- `includes/data/io/sql/*.class.php` — IO mappers
- `includes/database/bs_*.class.php` — bs_table classes
- `src/Domain/<feature>/<entity>Repository*.php` — repositories
- `includes/config/DIC.config.php` — DI bindings for new repos
- `phpstan-baseline.neon` — entries for new repo interfaces
- `db/schema/ddl/*` or any of `db/data_set/*.sql`, `db/schema/initial_data/*.sql`, `tests/Codeception/dumps/*.sql`

## Review-specific checks (not in the conventions skills)

These are the things the reviewer needs to verify against the **PR diff** that the authoring skills don't talk about.

### 1. The 3+ file pattern is complete

For a new entity, the PR should include all of:

- [ ] `includes/data/model/<Name>.class.php`
- [ ] `includes/data/io/sql/<Name>.class.php`
- [ ] `includes/database/bs_<name>.class.php`
- [ ] `src/Domain/<feature>/<Name>RepositoryInterface.php`
- [ ] `src/Domain/<feature>/<Name>DatabaseRepository.php`
- [ ] DIC binding (`DIC.config.php`)
- [ ] PHPStan baseline entry (`phpstan-baseline.neon`)
- [ ] Parent model gains a `'collection'` field for the new relation

If a `<Name>CachingRepository` is also introduced, verify:

- [ ] IO mapper declares `protected $repository = <Name>RepositoryInterface::class;` — without this, writes that bypass the repo (legacy GUI, generic controllers, migrations) won't invalidate cache. Most-missed check; lesson from PR #26973 / #26974.

### 2. Cross-file consistency

- **System DB vs per-account DB** must agree across model / IO mapper / bs_table / repository:
  - System: bs_table sets `$this->database = 'customer'`, IO mapper uses `customer.<table>` prefix, repo overrides `getConnectionType()` → `DBType::SYSTEM()`.
  - Per-account: none of the above.
  - A mismatch routes writes to the wrong connection.
- **`abstract class stub_<name>` pattern**: dominant (~222 of ~231 bs_* files). Flag any non-stub deviation.

### 3. Out-of-scope changes (red flag)

Per the workspace `jira-integration.mdc`, controller changes don't belong in a pure data-layer ticket. If the PR adds:

- New entries to `$_load_relations` on a controller, OR
- A controller method querying the new table

…flag as scope creep. These actively query the new schema on every API call and should be a separate, feature-flag-gated PR — production breakage risk if the schema isn't deployed yet.

### 4. Test data drift

When a new column or new seeded row is added, the four parallel SQL fixtures must all be updated together:

- [ ] `db/data_set/test_account.account.sql`
- [ ] `db/data_set/test_transactional.account.sql`
- [ ] `db/schema/initial_data/blank_account.sql`
- [ ] `tests/Codeception/dumps/test_account.sql`

Missing one causes silent fixture drift.

### 5. DIC + PHPStan placement

- `DIC.config.php` entries are alphabetically sorted. Run `make sort-dic-config` if visibly out of order.
- `generics.noParent` entries in `phpstan-baseline.neon` belong alphabetically near sibling interfaces.

### 6. Repository test coverage

The test files must follow `r-series-repository-tests/SKILL.md` patterns:

- Transactional repository test under `tests/Transactional/Domain/<Area>/`
- Unit caching repo test under `tests/Unit/Domain/<Area>/` if a CachingRepository was introduced
- Transactional bs_* test under `includes/tests/transactional/database/` for any custom behaviour (append-only, save overrides)
- Append-only enforcement covered via `dataProvider` over forbidden methods (not just `store` / `delete` — also `bulkStore`, `saveFields`, `bulkStoreUsingUniqueKey`, …)

### 7. Pre-merge reminder

For schema additions, remind the author to run **System → More Utilities → Generate DB Scheme** locally before deploying — it regenerates `includes/justlogic/merchantos/data_scheme/relations__*.inc.php`. Cannot be done from CLI.

## Verdict-time questions

Before signing off, ask in the verdict:

1. **Is any production code path** (controller / form / gui_defs / API endpoint) **already querying the new table?** If yes, must be feature-flag-gated.
2. **Is the schema dependency PR merged?** If the data layer is stacked on a not-yet-merged schema PR, the merge order matters — see `pre-merge-do-not-merge-check/SKILL.md`.
3. **Is there a follow-up ticket** for the business logic that will consume this data layer? If not, this PR ships dead code.

Answers belong in the verdict so the user can chase down the missing pieces.
