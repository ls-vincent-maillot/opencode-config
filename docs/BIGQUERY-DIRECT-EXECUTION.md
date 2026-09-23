# Direct BigQuery Execution

This recipe configures OpenCode to run approved R-Series/webPOS BigQuery queries
locally through the authenticated `bq` CLI.

## One-Time Setup

Install the Google Cloud SDK if it is not already installed:

```sh
cd "$HOME"
brew install --cask google-cloud-sdk
```

Authenticate with Google:

```sh
gcloud auth login
gcloud auth application-default login
```

`gcloud auth login` is normally sufficient for the `bq` CLI. The Application
Default Credentials login is useful for client libraries and scripts.

Verify that both tools are available:

```sh
command -v bq
command -v gcloud
```

Restart OpenCode after installing or changing skills and rules so it reloads
the configuration.

## R-Series Projects

Use these projects for R-Series/webPOS queries:

| Purpose | Project or dataset |
| --- | --- |
| Query job and billing project | `ls-infra-retail-001-data-prd` |
| R-Series data project | `ls-data-platform-prd` |
| Per-account CDC dataset | `retail_binlog_row_unified` |
| Shared/system CDC dataset | `retail_ss_binlog_row_unified` |

The query job runs in `ls-infra-retail-001-data-prd`, while source tables are
referenced fully qualified in `ls-data-platform-prd`. Do not use the X-Series
project for R-Series queries.

## Ask OpenCode

Ask the question in plain language. For example:

```text
For R-Series account cust12345, inspect the current state of sale 67890,
including its transaction, calculation, and payment rows.
```

The agent should construct a bounded Standard SQL query using the R-Series CDC
schema and account-scoping conventions.

## Approval Gate

Before running any `bq query`, including a dry run, OpenCode must show:

- The complete SQL.
- The query job or billing project.
- Every source table.
- Account and other data filters.
- The time range.
- The `--maximum_bytes_billed` limit.

Verify the SQL and parameters. Approve only the exact version you reviewed:

```text
I approve this exact query and parameters. Run it.
```

If the SQL, source tables, filters, project, time range, or byte limit changes,
the agent must ask for approval again.

## Execution Flow

After explicit approval, OpenCode should:

1. Confirm that `bq` is available with `command -v bq`.
2. Run a dry run using the exact approved SQL and execution project.
3. Report the estimated bytes processed.
4. Stop and request new approval if the estimate exceeds the approved byte
   limit.
5. Run the same approved SQL with the approved byte limit.
6. Return the result, bytes processed when available, and any warnings or
   errors.

The dry run is a cost check, not a replacement for the approval gate.

The execution shape is:

```sh
bq query \
  --use_legacy_sql=false \
  --dry_run \
  --project_id=ls-infra-retail-001-data-prd \
  --maximum_bytes_billed=APPROVED_LIMIT \
  --format=pretty \
  'APPROVED SQL'
```

Then execute the same SQL without `--dry_run`:

```sh
bq query \
  --use_legacy_sql=false \
  --project_id=ls-infra-retail-001-data-prd \
  --maximum_bytes_billed=APPROVED_LIMIT \
  --format=pretty \
  'APPROVED SQL'
```

## Query Requirements

- Use Standard SQL with `--use_legacy_sql=false`.
- Run jobs in `ls-infra-retail-001-data-prd`.
- Read R-Series data from fully qualified `ls-data-platform-prd` tables.
- Bound CDC queries by `metadata_event_timestamp`.
- Scope per-account queries with `metadata_database_name = 'cust<RAD_ID>'`.
- Use `curr_<column>` for post-change values and `prev_<column>` for prior
  values.
- Use `SAFE_CAST` when comparing numeric CDC fields stored as strings.
- Select only the fields needed for the question.
- Avoid restricted payload fields, especially event-log free-form data, unless
  access and necessity are established.
- Keep the workflow read-only. Never issue DDL, DML, or other mutation
  statements.

Every query must begin with a first-line provenance comment. Use the full Jira
URL for Jira work, a Slack discussion identifier or link for Slack work, or a
brief user-request provenance statement when the query comes directly from the
user. Do not place `DECLARE` or `WITH` before this header.

## Troubleshooting

### `bq` or `gcloud` is missing

Install the Google Cloud SDK from a valid working directory, then restart the
terminal if needed:

```sh
cd "$HOME"
brew install --cask google-cloud-sdk
```

### Authentication fails

Run the Google login commands again in a terminal and complete the browser
flow:

```sh
gcloud auth login
gcloud auth application-default login
```

Do not print credential files or tokens.

### `bigquery.jobs.create` is denied

Confirm that the query job uses:

```text
ls-infra-retail-001-data-prd
```

Do not move the job to `ls-data-platform-prd` just because that is the data
source project.

### Dataset or table access is denied

Confirm that the fully qualified source table is in the R-Series project:

```text
ls-data-platform-prd
```

Report the exact denied resource and permission. Do not silently switch to an
X-Series dataset or another billing project.
