---
name: schema-ddl
description: >-
  DDL conventions for creating or altering tables in R-Series. Use when adding
  new columns, new tables, new indexes, or modifying schema files
  (account.sql, customer.sql). Must be read before any DDL change.
---

# Schema DDL Conventions

## Files

| DB | Schema file | Test dump |
|----|-------------|-----------|
| Per-account | `db/schema/ddl/account/account.sql` | `tests/Codeception/dumps/test_account.sql` |
| System | `db/schema/ddl/system/customer.sql` | `tests/Codeception/dumps/customer.sql` |

Every DDL change goes in **both** the schema file and its test dump. The DDLizer picks up schema diffs on merge and generates ALTER statements for deployment. No migration triplet files.

**One schema file per PR** — CI enforces this. If a feature touches both `system/customer.sql` and `account/account.sql`, split into separate PRs.

## New table

Add the `CREATE TABLE` block in **alphabetical order** in both files. The test dump additionally needs the section header:

```sql
# Dump of table my_new_table
# ------------------------------------------------------------

DROP TABLE IF EXISTS `my_new_table`;

CREATE TABLE `my_new_table` (
  ...
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
```

## New column on existing table

Add the column to the existing `CREATE TABLE` block in both files. Place columns logically (after related columns), indexes at the end of the key list.

## Hard rules

### No foreign keys

Zero FK constraints in the entire codebase. Referential integrity is enforced at the application layer (transactional writes). Never add `CONSTRAINT ... FOREIGN KEY ... REFERENCES`.

### No `account_id` on per-account tables

Every row implicitly belongs to the account that owns the database. There are zero `account_id` columns across all tables in `account.sql`.

### Index naming

| Type | Prefix | Example |
|------|--------|---------|
| Regular index | `idx_` | `KEY idx_status (status)` |
| Unique index | `udx_` | `UNIQUE KEY udx_sale_id (sale_id)` |

No other prefixes. Reuse the column name(s) in the index name.

### Don't include the PK in secondary indexes

InnoDB silently appends the clustered primary key to **every** secondary index leaf. Listing the PK column explicitly at the end of a secondary index definition therefore:

1. Adds nothing — the column is already there implicitly.
2. Wastes catalog metadata.
3. Misleads readers into thinking the PK carries extra ordering value.
4. Can defeat optimizer paths that recognise "covering by PK suffix".

**Bad** (PK is `e_invoice_id`):

```sql
PRIMARY KEY (`e_invoice_id`),
KEY `idx_status_create_time` (`status`, `create_time`, `e_invoice_id`)
```

**Good**:

```sql
PRIMARY KEY (`e_invoice_id`),
KEY `idx_status_create_time` (`status`, `create_time`)
```

InnoDB treats the second form as functionally equivalent to `(status, create_time, e_invoice_id)` for lookups that benefit from the trailing PK — without the redundant declaration. The same applies to `UNIQUE KEY` definitions on InnoDB tables.

### `cust_<feature>` extension tables (system DB)

Merchant-level configuration tables live in the system DB as `cust_<feature>` extension tables, keyed `UNIQUE (cust_customer_id)`. Precedents: `cust_billing`, `cust_ecommerce`, `cust_module`, `cust_integration`, `cust_openid`.

### Engine and charset

Always `ENGINE=InnoDB DEFAULT CHARSET=utf8`.

### Column defaults

- **TEXT, BLOB, JSON, and other large types**: do **not** write `DEFAULT NULL`. They are implicitly nullable in MySQL and the explicit default is redundant. Just write `text` / `json` / `blob` and let the column be nullable by default.
- **VARCHAR, INT, DATETIME, TIMESTAMP, etc.**: explicit `DEFAULT NULL` is fine and improves readability.

### Timestamp column naming

For row-creation and row-update timestamps, follow the legacy R-Series convention:

- **`create_time`** — `timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP`. Immutable creation timestamp.
- **`time_stamp`** — `timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`. Auto-updated on every row mutation.
- **Append-only tables** (logs, audit trails): only `create_time` — no `time_stamp` (rows are never updated).

Prefer `create_time` over `created_at`, `time_stamp` over `updated_at`. Some recent tables use `created_at` / `updated_at` (Doctrine-style), but the legacy convention is the majority; pick `create_time` / `time_stamp` for consistency with neighbouring tables unless they already use the newer convention.

### Low-cardinality indexes

Don't add an index on a column with very few distinct values (boolean flags, status enums with 5–10 values, etc.). The MySQL optimizer typically ignores such indexes because the gain from filtering is too small relative to the cost of using the index. The write overhead is real even when the index is unused.

Rule of thumb:
- ✅ Index high-cardinality columns (FK-ish IDs, UUIDs, timestamps when range-queried)
- ❌ Skip indexes on `is_*` booleans, `status` enums with few values, single-state flags
- ⚠️ Status indexes on tables with skewed distribution (one value = 95% of rows) are usually skipped by the optimizer

Examples from this codebase: `idx_b2b (is_b2b_customer)` and `idx_storecove_status` were both dropped after review for this reason.

## PR description for schema PRs

Schema PRs follow the standard template (`docs/PULL_REQUEST_TEMPLATE.md`) with DDL-specific content:

```markdown
# **JIRA Ticket: [LSR-XXXXX](https://lightspeedhq.atlassian.net/browse/LSR-XXXXX)**

## Description

<What changed: new table / new columns / altered index. Name the table(s).>
<Why: which initiative or feature requires it.>
<If multiple sub-tasks share one schema file, list them in a table:>

| Sub-task | Change |
|---|---|
| [LSR-XXXXX](...) | `table_name` — short description of columns added |

<Parent ticket if applicable.>

## Evidence

N/A — DDL schema additions only, no behavioral changes.

## Usage

- **Feature flag:** `Features::hasXxx()` (link to the flag PR if already merged)
- **DDLizer:** Picks up the schema diff on merge

## Checklist

<Use the standard checklist from the template.>
```

Key points:
- **Evidence is always `N/A`** for pure DDL — there are no behavioral changes to demonstrate.
- **Usage** must mention the feature flag and note the DDLizer handles deployment.
- If the PR covers multiple sub-tasks of a parent migration ticket (because they share one schema file), list each sub-task with its table and change summary.

## Reference PRs

- New table: [LSR-32256 (#25087)](https://github.com/merchantos/webPOS/pull/25087)
- New column: [LSR-37144 (#26874)](https://github.com/merchantos/webPOS/pull/26874)
- Schema + sort: [LSR-36554 (#26648)](https://github.com/merchantos/webPOS/pull/26648)
