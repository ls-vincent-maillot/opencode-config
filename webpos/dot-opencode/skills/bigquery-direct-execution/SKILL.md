---
name: bigquery-direct-execution
description: Run approved R-Series BigQuery queries locally with the bq CLI. Use after the agent has constructed a query and the user has explicitly approved the exact SQL and execution parameters.
---

# Direct BigQuery Execution

Use this skill together with `bigquery-cdc-investigations` for R-Series/webPOS
BigQuery work. The investigation skill owns dataset conventions, schema
discovery, account scoping, PII handling, and query construction. This skill
owns local execution through the authenticated `bq` CLI.

## Mandatory approval gate

1. Construct the query and show the user the exact SQL before running anything.
2. Show the execution project, source tables, time range, account filters, and
   any `--maximum_bytes_billed` limit.
3. Ask the user to verify the query and explicitly approve execution.
4. Do not run `bq query`, including a dry run, until the user approves the
   exact query and execution parameters.
5. If the user changes the query, repeat the approval step for the complete
   updated query. Approval of an earlier version does not carry forward.

An approval such as "run it" applies only to the exact query and parameters
shown immediately before it. Do not broaden the query, change the project,
remove a cost limit, or add fields after approval without asking again.

## Query provenance

Every query must begin with a first-line comment identifying its source. For a
Jira request, use the full Jira URL; for a Slack request, use the discussion
identifier or link. If the query comes directly from the current user, state
that in the first-line comment. Do not put `DECLARE` or `WITH` before this
header.

## Local prerequisites

Check the local tools before proposing execution:

```sh
command -v bq
command -v gcloud
```

If the Google Cloud SDK is missing, the user can install it on macOS with:

```sh
brew install --cask google-cloud-sdk
```

Do not install software or start a browser authentication flow solely because
a query was approved. Ask for separate setup authorization if either action is
needed.

For a new or expired local login, the user can authenticate with:

```sh
gcloud auth login
gcloud auth application-default login
```

The first command is sufficient for the `bq` CLI in the normal case. The ADC
login is useful for client libraries and scripts that use Application Default
Credentials. Do not print credential files or tokens. Pass the billing project
explicitly to every query instead of relying on the active gcloud project.

## R-Series execution defaults

- Run query jobs in `ls-infra-retail-001-data-prd`.
- Read R-Series CDC data from fully qualified tables in
  `ls-data-platform-prd`, normally `retail_binlog_row_unified` or
  `retail_ss_binlog_row_unified`.
- Use Google user credentials already configured for the local `bq` CLI.
- Never use the X-Series project for R-Series/webPOS queries.
- Use Standard SQL explicitly with `--use_legacy_sql=false`.
- Set `--maximum_bytes_billed` for every query unless the user explicitly
  approves an unbounded limit.

## Execution procedure

After approval:

1. Verify the executable with `command -v bq`.
2. Run a dry run using the exact approved SQL and execution project:

   ```sh
   bq query \
     --use_legacy_sql=false \
     --dry_run \
     --project_id=ls-infra-retail-001-data-prd \
     --maximum_bytes_billed=APPROVED_LIMIT \
     --format=pretty \
     'APPROVED SQL'
   ```

3. Report the dry-run estimate. If the estimate exceeds the approved
   `--maximum_bytes_billed` limit, stop and ask for a new approval.
4. Execute the same SQL with the approved byte limit:

   ```sh
   bq query \
     --use_legacy_sql=false \
     --project_id=ls-infra-retail-001-data-prd \
     --maximum_bytes_billed=APPROVED_LIMIT \
     --format=pretty \
     'APPROVED SQL'
   ```

5. Return the query result, bytes processed when available, and any BigQuery
   warnings or errors. Do not expose credentials.

The dry run is a cost check, not a substitute for approval. Both commands
must use the same SQL, billing project, and relevant execution options.

## Safety and data handling

- BigQuery access is read-only for this workflow. Never issue DDL, DML,
  scripting statements with writes, or other mutation statements.
- Keep queries bounded by `metadata_event_timestamp` and account/database
  filters whenever the question permits.
- Select only fields needed to answer the question; avoid restricted payload
  fields such as event-log free-form data unless access and necessity are
  established.
- Prefer aggregate results or narrowly scoped rows over broad extracts.
- Do not print environment files, credential files, access tokens, or query
  history containing secrets.
- Treat query results as potentially sensitive. Return only the fields needed
  for the answer and redact or summarize PII where possible.
- A successful dry run proves syntax and authorization to plan the query; it
  does not prove that the result is complete or that CDC has caught up.

## Authentication failures

If `bq` is missing, report that it is unavailable and stop; do not install
software without explicit user instruction.

If authentication fails, ask the user to run the required Google login in their
own terminal. Do not inspect or print credential files. If job creation fails,
verify that the query uses `ls-infra-retail-001-data-prd` as the execution
project. If dataset or table access fails, report the fully qualified resource
and permission error without switching projects or datasets silently.
