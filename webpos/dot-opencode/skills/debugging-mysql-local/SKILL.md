---
name: debugging-mysql-local
description: Read-only MySQL queries against the local Docker dev DB for R-Series webPOS. Use when inspecting local data to reproduce a bug, verify schema/column shape, check what got persisted by a test or UI action, or sanity-check before a code change. Companion to bigquery-cdc-investigations (prod CDC), kept strictly read-only — production-style fix scripts go to the DBA per the schema-changes / data-layer conventions.
---

# Debugging the Local MySQL DB

Read-only MySQL access to the dev stack's database container. For prod investigations use `bigquery-cdc-investigations`; for write fixes hand off to the DBA per the schema/data-layer conventions.

## Guardrails — read-only

Only these statements are allowed:

- `SELECT`
- `SHOW`
- `DESCRIBE` / `DESC`
- `EXPLAIN`

**Never** run `INSERT`, `UPDATE`, `DELETE`, `ALTER`, `DROP`, `TRUNCATE`, `CREATE`, or any other mutation. If a write fix is needed, stop and write a script under `~/Documents/AgentFiles/<LSR-ticket>/` per the artifacts rule.

## Connection

| Field | Value |
|---|---|
| Container | `webpos-retail-retail-database-1` (verify with `docker ps --format '{{.Names}}' | grep database` if your compose project prefix differs) |
| User / pass | `root` / `root` |
| Per-account DB | `cust<RAD_ID>` (e.g. `cust105`, `cust44148`) |
| System (shared) DB | `customer` |
| Catalog DB | `item` (shared across accounts; item-catalog data lives here, not in `cust<N>`) |

## Usage

```bash
docker exec webpos-retail-retail-database-1 sh -c \
  "mysql -u root -proot cust<RAD_ID> -e \"<SQL>\""
```

### Examples

```bash
# List tables in an account DB
docker exec webpos-retail-retail-database-1 sh -c \
  "mysql -u root -proot cust105 -e 'SHOW TABLES;'"

# Describe a table
docker exec webpos-retail-retail-database-1 sh -c \
  "mysql -u root -proot cust105 -e 'DESCRIBE transaction_payment;'"

# Filtered SELECT
docker exec webpos-retail-retail-database-1 sh -c \
  "mysql -u root -proot cust105 -e \"SELECT transaction_payment_id, archived, payment_type_id FROM transaction_payment WHERE transaction_id = 12345 LIMIT 50;\""

# Cross to the system DB
docker exec webpos-retail-retail-database-1 sh -c \
  "mysql -u root -proot customer -e 'SELECT cust_customer_id, name, status FROM cust_customer WHERE cust_customer_id = 105;'"

# EXPLAIN a query to check index usage
docker exec webpos-retail-retail-database-1 sh -c \
  "mysql -u root -proot cust105 -e 'EXPLAIN SELECT * FROM transaction WHERE customer_id = 1 ORDER BY time_stamp DESC LIMIT 10;'"
```

## Gotchas

- The `Using a password on the command line interface can be insecure` warning is expected — ignore.
- Quote string values with single quotes **inside** the double-quoted SQL string (`\"...WHERE x = 'val'\"`).
- Always add `LIMIT` to ad-hoc SELECTs; the local DB still has thousands-to-millions of rows in seeded tables.
- The `item` database is shared across accounts; don't look for item catalog data inside `cust<N>`.
- Local DB ≠ prod. For "what's actually in prod?" use BigQuery via `bigquery-cdc-investigations`.

## When to leave MySQL

- "What did the user actually see?" → reproduce in the UI at `https://rad.localdev`.
- "Why did the value end up like this?" → trace via the codebase; the DB shows state, not intent.
- "Is this happening in prod?" → BigQuery, not local.
