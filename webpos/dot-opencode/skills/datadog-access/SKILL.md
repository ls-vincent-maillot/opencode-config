---
name: datadog-access
description: How to query Datadog (logs, events, metrics, traces, monitors) from this workspace via the MCP server. Use when verifying whether a cron/job/service runs in dev/staging/prod, inspecting production logs, checking a Datadog event or metric, or confirming a deploy. Documents the working server name, the tool set, the required telemetry arg, and R-Series service/env conventions.
---

# Datadog Access (R-Series / webPOS)

## Which MCP server to use — the main gotcha

There are two Datadog MCP servers that can appear in this workspace:

- `plugin-datadog-datadog` — the bundled Datadog plugin. It is frequently **not set up / errored** (its `STATUS.md` says "The MCP server errored"). Do **not** assume Datadog is unavailable just because this one fails.
- **`user-datadog`** — the user-configured server (server name `datadog`, site **us5**). **This is the one that works here.** Prefer it.

If an agent only tries `plugin-datadog-datadog` (or trusts a stale `STATUS.md`), it wrongly concludes "no Datadog access." Always probe `user-datadog` with a real call before giving up.

## How to call it

Use `CallMcpTool` with `server: "user-datadog"`. **Read the tool's JSON schema first** — descriptors live in the project's `mcps/user-datadog/tools/*.json` (per the MCP file system). Key rules:

- Every tool requires a `telemetry: { intent: "<why you're calling>" }` argument. Omitting it fails the call.
- `STATUS.md` showing "errored" can be stale/per-session. If a call returns *"MCP server does not exist: datadog"*, the server isn't loaded in **this** session → reload the Cursor window (and re-auth under Settings → Tools & MCP). If it returns *"Tool X was not found"*, the server **is** connected — you just used the wrong tool name.

## Skill discovery (do this first for a domain)

The server ships its own skill guides. Before a domain investigation, run in parallel:

- `load_datadog_skill` with `skill_name: "datadog/logs"` (or `datadog/metrics`, `datadog/traces`, `datadog/events`, `datadog/visualizations`).
- `list_datadog_skills` with a fuzzy `query` of topic keywords.

Skip only if you've already loaded that domain's skill this session.

## Core tools

| Need | Tool |
|---|---|
| Raw logs / log patterns | `search_datadog_logs` (set `use_log_patterns:true` to cluster) |
| Log counts / SQL aggregation | `analyze_datadog_logs` (DDSQL over a virtual `logs` table) |
| Datadog **events** (deploys, alerts, custom `metrics->event()`) | `search_datadog_events` / `aggregate_events` |
| Metrics | `get_datadog_metric`, `search_datadog_metrics`, `get_datadog_metric_context` |
| Traces / spans | `get_datadog_trace`, `search_datadog_spans`, `aggregate_spans` |
| Monitors / dashboards | `search_datadog_monitors`, `search_datadog_dashboards`, `get_datadog_dashboard` |
| Hosts / services | `search_datadog_hosts`, `search_datadog_services`, `search_datadog_service_dependencies` |

Log query syntax: tags are bare `key:value` (`env:production service:retail-...`); attributes use `@` (`@http.status_code:500`). Time accepts `now-7d`, ISO 8601, or unix ms. For aggregations prefer `analyze_datadog_logs` over paging raw logs.

## R-Series conventions (so queries actually match)

- **Environments** (`env:` tag): `development`, `staging`, `production`.
- **Service names** seen for background work:
  - `retail-monolith-cronjob` — the Laravel scheduler that *dispatches* scheduled jobs.
  - `retail-workers-retail-system` — the SQS **system-queue** worker that *executes* system jobs (`->onQueue(...sqs...system)`). This is where a job's own log lines (and its in-job feature-flag guard) appear.
- Job/class log lines carry the FQCN in `message`, e.g. `LS\Retail\Domain\Jobs\<JobName>` — search by the bare class name (`"CheckStorecoveReadinessJob"`).
- A config-gated cron (e.g. `*_SCHEDULED_TASK_ENABLED`) that is **dispatched but disabled** logs a `"... is disabled in this environment, exiting."` line on `retail-workers-retail-system` every tick — useful to confirm the schedule wiring without the feature being live.
- Custom Datadog **events** emitted via `StatsdMetricsCollector::event()` (e.g. `storecove.readiness.stuck`) are found with `search_datadog_events`, **not** `search_datadog_logs`.

## Example: is a scheduled job running, and how far?

```
search_datadog_logs
  query:  "CheckStorecoveReadinessJob"
  from:   now-3d
  extra_fields: ["env"]
  telemetry: { intent: "Verify a scheduled job is dispatched and whether it runs past its feature-flag guard across envs" }
```

Read the `message` + `env` of each hit: `"...is disabled in this environment, exiting."` ⇒ dispatched but flag off; `"...activated (X) of (Y) pending merchant(s)."` ⇒ running its body. Absence of any past-the-guard line across all envs ⇒ still disabled everywhere.

## Don'ts

- Don't query the staging Datadog org for real-customer diagnostics — this server is the prod org (us5).
- Don't put API keys/tokens in files — auth is handled by the MCP server config.
- Don't conclude "Datadog isn't available" from a `plugin-datadog-datadog` failure or a stale `STATUS.md` alone; probe `user-datadog` first.
