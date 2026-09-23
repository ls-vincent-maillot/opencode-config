---
name: bigquery-cdc-investigations
description: Investigate production sale, payment, customer, or event-log state for R-Series webPOS via the BigQuery CDC mirror. Use when diagnosing a prod sale (especially OOB), inspecting a payment lifecycle, tracing what a cashier did, verifying prod vs. codebase, or writing a one-off "state of X on account Y" query. Covers dataset/table conventions, the schema source of truth (lsp-data-classification-policy), PII-aware querying, and BigQuery's read-only relationship to prod MariaDB.
---

# BigQuery CDC Investigations (R-Series / webPOS)

## What this is

CDC mirror of prod MariaDB. Every change to a `bs_*` table lands in `<table>_unified` and every prior version is kept. **Read-only** — fixes are MariaDB `UPDATE`s run by the DBA (stage scripts under `~/Documents/AgentFiles/<LSR-ticket>/`). Active tables lag by minutes; re-query before concluding an event didn't happen.

## Schema source of truth

`lsp-data-classification-policy` (sibling of webPOS, e.g. `/Volumes/dev/lsp-data-classification-policy/`) is authoritative for field names, types, and PII tags. Check it before writing a query to avoid runtime "Access Denied".

- `datasets/retail_binlog_row/<table>.csv` — quick column + PII-tag scan.
- `datasets/retail_binlog_row/<table>.json` — full schema:
  - `table_info_references` — fully-qualified BQ refs (we query the `_unified` view in `ls-data-platform-prd.retail_binlog_row_unified`).
  - `unified_schema[].name` — fields exposed as `curr_<f>`, `prev_<f>`, plus `metadata_*`.
  - `unified_schema[].desired_policy_tag_flat_name` — anything beyond `General - Internal[ - DP Metadata]` likely needs fine-grained access.

## Dataset and table conventions

- **Project**: `ls-data-platform-prd` always (`-stg` is staging — never for real-customer diagnostics).
- **Datasets**: `retail_binlog_row_unified` (per-account, ~all investigations) and `retail_ss_binlog_row_unified` (system/shared, e.g. `cust_customer_unified`).
- **Tables**: `<source_table>_unified`, views over versioned shards.
- **Account scoping**: filter `metadata_database_name = 'cust<RAD_ID>'` (e.g. `'cust44148'`). Empty result on a known-good account usually means the filter is wrong.
- **Columns**: `curr_<col>` (post-change), `prev_<col>` (pre-change — great for CDC diffs, e.g. `WHERE prev_archived = 0 AND curr_archived = 1` finds the archive event).
- **Metadata** (on every table): `metadata_database_name`, `metadata_event_timestamp`, `metadata_row_operation` (`INSERT`/`UPDATE`/`DELETE`), `metadata_shard_name`, `metadata_table_name`.
- **Type coercion**: numeric IDs are STRING — `SAFE_CAST(... AS INT64)` (or `AS NUMERIC` for money).

## Current-state pattern

```sql
WITH tx_payment AS (
  SELECT * FROM (
    SELECT
      metadata_database_name, metadata_row_operation,
      curr_transaction_payment_id, curr_transaction_id, ...,
      ROW_NUMBER() OVER (
        PARTITION BY metadata_database_name, curr_transaction_payment_id
        ORDER BY metadata_event_timestamp DESC
      ) AS seqnum
    FROM `ls-data-platform-prd.retail_binlog_row_unified.transaction_payment_unified`
    WHERE metadata_database_name = TARGET_DB
      AND SAFE_CAST(curr_transaction_id AS INT64) = TARGET_SALE_ID
      AND DATE(metadata_event_timestamp) BETWEEN START_DATE AND END_DATE
  ) WHERE seqnum = 1
    AND metadata_row_operation != 'DELETE'  -- drop if a tombstone is the answer
)
```

Drop `!= 'DELETE'` when investigating "did this row ever exist?" or "was this archived correctly?".

## CDC history pattern

Drop `WHERE seqnum = 1` and order ASC to see every INSERT/UPDATE/DELETE. Pair `curr_<col>` with `prev_<col>` to read each UPDATE as a diff. Useful for status/archive flips and "when did this row stop being right?".

## Parameterized template

```sql
DECLARE START_DATE      DATE   DEFAULT DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY);
DECLARE END_DATE        DATE   DEFAULT CURRENT_DATE();
DECLARE TARGET_DB       STRING DEFAULT 'cust<RAD_ID>';
DECLARE TARGET_SALE_ID  INT64  DEFAULT <sale_id>;
```

180 days is the usual lookback; widen to 365+ for old sales. A NULL field often just means the row's last CDC event is outside the window.

## Cost discipline

- Always bound `metadata_event_timestamp`. Unbounded scans across years get expensive fast.
- Check estimated bytes in the UI; >1 GB for a single-account/single-sale query means a filter isn't pushing down (usually timestamp).
- Avoid `SELECT *` on tables with big text/JSON (`event_log_v3.curr_form_vars`, `bs_log_*.curr_details`).
- Prefer `COUNT(*)` when checking "does any row match?".

## PII / policy-tag restrictions

Restricted fields fail with *"Access Denied: ... policy tag …"*. Known example: `event_log_v3.curr_form_vars` (`OMNI Merchant : Merchant Employee - Freeform`) — the full event payload; ask UI-access support to share rows rather than querying. Full restricted list lives in `lsp-data-classification-policy`.

## Workflow

1. **Reuse ticket queries** when present (`query_S1_current_state.sql` / `query_S2_cdc_history.sql`); edit the DECLAREs.
2. **Verify, don't guess.** Run an approved query through `bigquery-direct-execution` and quote the rows — don't infer prod state from local DB or codebase reading.
3. **Cross-check unfamiliar columns** against `includes/database/bs_<table>.class.php` (1:1 with `curr_<col>`). If working from PHP ORM names, translate via `$_map` in `includes/data/io/sql/<Model>.class.php` — BQ uses MySQL column names, not ORM names.
4. **Distinguish "the DB shows X" from "the code path appears to do X".** Name which one you're reporting.
5. **No writes against BigQuery.** Fixes are MariaDB UPDATEs for the DBA; stage scripts under `~/Documents/AgentFiles/`.

## Useful joins (sale-shaped)

- **Sale snapshot**: `transaction_unified` ↔ `transaction_calc_unified` (1:1 by `curr_transaction_id`) ↔ `transaction_payment_unified` (1:N).
- **Payment lifecycle**: `transaction_payment_unified` filtered by `curr_transaction_payment_id`, ORDER ASC.
- **Event timeline**: `event_log_v3_unified` filtered by `curr_transaction_id`. Payload in `curr_form_vars` is PII-tagged — fall back to UI.
- **Cross-sale refunds**: `transaction_payment.ref_payment_uid` → another `transaction_payment.transaction_payment_id`, possibly on a different sale. Look it up before calling it wrong-sale; refund-by-reference against a deposit charge is by design.

## Widening to multiple accounts

Source-table IDs (`transaction_id`, `employee_id`, etc.) are per-database — two accounts can both have `transaction_id = 12345`. Build a global key:

```sql
CONCAT(metadata_database_name, ':', CAST(curr_transaction_id AS STRING)) AS sale_key
```

Use it (not the raw ID) in `GROUP BY` / `COUNT(DISTINCT)` / joins.

Filter to real customers via `cust_customer_unified`:

```sql
WITH accounts AS (
  SELECT curr_database_name FROM (
    SELECT
      curr_database_name, curr_status, metadata_row_operation,
      ROW_NUMBER() OVER (
        PARTITION BY metadata_database_name, curr_cust_customer_id
        ORDER BY metadata_event_timestamp DESC
      ) AS seqnum
    FROM `ls-data-platform-prd.retail_ss_binlog_row_unified.cust_customer_unified`
    WHERE metadata_event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  )
  WHERE seqnum = 1
    AND metadata_row_operation != 'DELETE'
    AND curr_status IN ('customer', 'suspended')
)
```

Statuses to keep: `customer`, `suspended`. Drop: `sandbox`, `demo`, `test`, `cancelled`, `delete`, `blank` (source: `AccountStatus.class.php`). 90 days is enough to capture every active account's latest status.

## Gotchas I've consistently caught

- **Misleading action names.** `register.account_actions.withdraw` is "refund deposit" (return CA balance via another payment method), not "use CA balance to pay this sale". When in doubt, read `includes/forms/ajax_forms/register/account_actions/<action>.php`.
- **Row existence ≠ gateway settled.** A `transaction_payment` with a `payment_charge_reference` UUID and `archived = 0` is strong evidence but not proof — declined/errored payments get archived by `setArchiveFromPayment` from the Payment Service callback; a missed callback leaves the row looking live. For refunds >24h old, assume settled; for fresh ones, confirm with payments.
- **Mirror lag at the edges.** Within minutes of an event, a missing row may just be lag — re-query before concluding it didn't happen.
- **Counting rows ≠ summing money.** `calc_num_payments` is the count of non-archived payment rows, not their sum. A sale can be OOB while it looks fine. Cross-check `calc_total` vs `calc_payments` (or sum `transaction_payment` yourself).

## When the investigation outgrows BigQuery

- **"Did the gateway settle this refund?"** → payments team / Payment Service tooling.
- **"What did the cashier intend?"** → event-log payloads (PII-tagged, via UI) + what the merchant can tell you.
- **"Why is the DB column empty when the event payload had a value?"** → likely server-side mutation between request and persistence; trace via the codebase.

Name the unanswerable parts explicitly rather than speculating.
