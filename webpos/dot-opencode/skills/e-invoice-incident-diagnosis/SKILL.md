---
name: e-invoice-incident-diagnosis
description: Diagnose R-Series e-invoice failures, missing e_invoice rows, failed manual sends, Storecove submission errors, and invoices that were not created after sale completion. Use this skill whenever a user reports an e-invoice problem and provides an account, sale, customer, or approximate timestamp; start with Datadog application logs, then use redacted BigQuery CDC only to locate the persistence/submission phase.
---

# E-Invoice Incident Diagnosis

## Goal

Determine quickly whether an e-invoice request:

1. Never reached the application.
2. Reached the application but failed before an `e_invoice` row was persisted.
3. Persisted a pending attempt but failed while submitting to Storecove.
4. Persisted a submission outcome that needs follow-up.

Do not infer the cause from a missing `e_invoice` row alone. The manual send path validates and maps the sale before it persists that row.

## Required Inputs

Collect, if available:

- Account/RAD ID.
- Sale ID.
- Customer ID.
- Approximate timestamp, converted to UTC.
- Entry point: transaction-page action or Admin e-invoicing page.
- Whether the sale was completed before the customer was attached.

Use the account ID and sale ID as correlation keys. Do not request or print raw VAT numbers, invoice payloads, event `form_vars`, audit payloads, or Storecove request bodies unless a separately authorized workflow requires them. Redact PII from the final report.

## Step 1: Search Datadog First

Use the `user-datadog` server described by `datadog-access`. Load the server's `datadog/logs` guidance before searching. Query a narrow window, normally five minutes before and after the reported timestamp.

For the legacy transaction-page action, start with:

```text
env:production service:retail-app @extra.system_customer_id:<account_id> ("Manual e-invoice send failed" OR "Manual e-invoice send rejected")
```

Request the `context`, `extra`, and `channel` fields. Inspect the returned record for:

- `transaction_id` in the logging context.
- `error` or `reason`.
- `channel`.
- `trace_id`.
- `url`, `http_method`, `db_name`, and `git.commit.sha` in the request context.

If the incident may have used the Admin endpoint, also search the same account and time window for the request path or trace. Do not assume an absent application message means the endpoint was not called; correlate access logs or the trace before concluding that.

If the send log is absent, search the same narrow window for `Storecove request failed` and then for the request/access record. Storecove endpoint failures are represented in `@context.args`; use an attribute query rather than relying on free-text message search for values buried in that JSON.

## Step 2: Classify the Application Result

| Datadog evidence | Interpretation | Expected persistence |
|---|---|---|
| `Manual e-invoice send rejected` | Curated domain validation failed before submission. | Usually no new row if validation failed before `preparePendingAttempt()`. |
| `Manual e-invoice send failed` | An unexpected exception escaped the send path. Inspect the safe exception message and trace. | May be absent when the exception occurs during retrieval or mapping. |
| `Storecove request failed` | The request reached the external Storecove client and failed there. | An `e_invoice` row should normally already exist. |
| No matching application log | Request not proven. Check access logs, authentication/authorization responses, and the trace. | Unknown. Do not call this "no request" yet. |

For the transaction-page action, the messages are emitted by `send_e_invoice_fnc` in `includes/gui_defs/transaction/views/transaction.class.php`. The Admin route is `POST /admin/e-invoicing/invoices/{saleID}/send`.

## Step 3: Map the Failure to a Send Phase

The synchronous manual path in `EInvoiceSendService::send()` runs in this order:

1. Retrieve the active merchant.
2. Retrieve and validate the completed sale, shop, customer, B2B flag, customer details, and country.
3. Map the invoice with `InvoiceMapper`.
4. Persist the `e_invoice` row and `manual:send:<audit-id>` event in `e_invoice_log`.
5. Call Storecove.
6. Persist `submit:<status>:<audit-id>` in `e_invoice_log`.

Use this ordering when interpreting the logs. For example, a Belgian VAT prefix exception is a mapper failure and occurs before persistence; it cannot produce a `manual:send:*` row.

## Step 4: Use Redacted BigQuery CDC Only When Needed

BigQuery execution is user/DBA-proxied. Load `bigquery-cdc-investigations` and the data classification schema before constructing a query. Keep queries scoped to:

- `metadata_database_name = 'cust<RAD_ID>'`.
- The sale/customer IDs.
- A bounded incident window plus a limited history window.

If writing a new SQL artifact, put the required ticket or Slack source-attribution comment on the first line. Never project restricted payload fields merely to diagnose presence or lifecycle state.

Inspect only these lifecycle signals:

- `e_invoice` row existence, sale ID, customer ID, status, routing method, and timestamps.
- `e_invoice_log.event_type`, `old_status`, `new_status`, and timestamps.
- Sale completion/customer assignment history.
- Non-payload event/audit descriptors when needed to establish which UI action occurred.

Interpret the result as follows:

| CDC evidence | Conclusion |
|---|---|
| No `e_invoice` row and Datadog shows a pre-persistence exception | Request reached the app and failed during retrieval/validation/mapping. |
| No `e_invoice` row and no request/error evidence | Request remains unproven; it may not have been sent or may have failed outside the searched log scope. |
| `manual:send:<audit-id>` | Pending attempt was persisted; the request passed validation and mapping. |
| `submit:<status>:<audit-id>` | Storecove submission reached an outcome recorded by the application. |
| `pending` with no `submit:*` event | Attempt was persisted, but submission outcome was not recorded or remains unconfirmed. |

Prefer the existing redacted correlation template in the ticket's `~/Documents/AgentFiles/<ticket>/` directory when one exists. Do not modify production data from this workflow.

## Common Findings

- Sale completed with `customer_id = 0`, then a customer was assigned later: the sale-completion hook already ran, and `saveAdminAdjustment()` does not replay it. A later manual send is required.
- Customer VAT is non-canonical or malformed: the invoice mapper can fail before persistence. Do not expose the VAT value in the report; use a safe cause such as `customer_vat_not_canonical`.
- Customer is not B2B, lacks required details, or has an unsupported country: the send is rejected before Storecove.
- Merchant is not active, sale is incomplete/voided, or customer/shop is missing: the send is rejected before persistence.
- Storecove returns a validation, transient, permanent, or unknown-outcome error: inspect the persisted `e_invoice` status and `submit:*` event, then correlate the Storecove log attributes.

## Report Format

Return a short evidence-led summary:

```text
Incident: account <id>, sale <id>, customer <id>, <UTC window>

Datadog:
- Request reached application: yes/no/unknown
- Entry point: transaction page/Admin/unknown
- Failure message or safe cause: <redacted safe description>
- Trace/version: <values safe to share>

Persistence:
- e_invoice row: present/absent/unknown
- Lifecycle phase: pre-persistence/pending/Storecove submission/outcome unknown
- e_invoice_log evidence: <manual:send or submit event, if present>

Conclusion:
- <single causal statement>

Remaining gap:
- <only if the evidence does not establish the cause>
```

State facts separately from hypotheses. If the logs identify the exception, do not spend time deriving the same cause from broad CDC scans.

## Safety Rules

- Search Datadog before writing a broad BigQuery query.
- Use narrow time bounds and account-scoped filters.
- Do not print secrets, raw VAT values, invoice payloads, restricted event payloads, or raw Storecove bodies.
- Do not treat a missing database row as proof that no request occurred.
- Do not claim Storecove was called unless a Storecove log or `submit:*` lifecycle event supports it.
- Do not change application or production data while diagnosing an incident.
