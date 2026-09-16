---
name: circleci-builds
description: Read and diagnose CircleCI build/job results for merchantos/webPOS via the CircleCI API over curl. Use when a user shares a CircleCI pipeline/job URL, asks why a build or test suite failed, wants the failing step's log output, or needs to interpret a non-zero exit code from a CI job. Documents the token location, project slug, the v2-vs-v1.1 API split, how to pull step logs, and how to read PHPUnit crash signatures.
---

# CircleCI Builds (R-Series / webPOS)

Read failed CircleCI jobs directly from the API with `curl`. No CLI install needed.

## Credentials & project

- **Token**: `PERSONAL_CIRCLECI_API_KEY` in the project `.env`. Source it, never print it.
  ```bash
  set -a; source /Volumes/dev/webPOS/.env; set +a
  ```
- **Project slug**: `gh/merchantos/webPOS` (VCS `gh` + org + repo).
- Auth header on every call: `-H "Circle-Token: $PERSONAL_CIRCLECI_API_KEY"`.

## Parsing a CircleCI URL

`app.circleci.com/pipelines/gh/merchantos/webPOS/<pipeline_num>/workflows/<workflow_id>/jobs/<JOB_NUMBER>`
— the trailing `jobs/<JOB_NUMBER>` is the **job number** you need (e.g. `2478802`).

## The API split — the main gotcha

- **v2** (`/api/v2/...`) gives clean job metadata (name, status, workflow) but **no step logs**.
- **v1.1** (`/api/v1.1/...`) gives **steps + per-step `output_url`** (the actual logs) and a `/tests` endpoint for JUnit metadata.

Use v2 to identify the job, then v1.1 to read logs.

## Workflow

```bash
set -a; source /Volumes/dev/webPOS/.env; set +a
JOB=<job_number>
BASE="https://circleci.com/api"
AUTH=(-H "Circle-Token: $PERSONAL_CIRCLECI_API_KEY")

# 1. Job meta (name, status, branch, workflow)
curl -s "${AUTH[@]}" "$BASE/v2/project/gh/merchantos/webPOS/job/$JOB" | python3 -m json.tool

# 2. Steps — find the failed action (a.failed == true) and its output_url
curl -s "${AUTH[@]}" "$BASE/v1.1/project/gh/merchantos/webPOS/$JOB" > /tmp/cci_job.json
```

Then extract the failing step's `output_url` and fetch it. The `output_url` returns a JSON **array of messages**, each with `type` (`out` / `error`) and `message`; concatenate `message` fields for the full log:

```python
import json, urllib.request
d = json.load(open('/tmp/cci_job.json'))
for s in d["steps"]:
    for a in s["actions"]:
        if a.get("failed"):
            data = json.load(urllib.request.urlopen(a["output_url"]))
            print("".join(m["message"] for m in data))
```

- JUnit metadata (per-test pass/fail): `GET /v1.1/project/gh/merchantos/webPOS/$JOB/tests`. **Often empty** — if the process crashed before writing the JUnit file, this returns 0 tests. Empty ≠ "no tests ran".
- Artifacts: `GET /v1.1/project/gh/merchantos/webPOS/$JOB/artifacts`.

## Reading exit codes & PHPUnit crash signatures

The webPOS test jobs (`check-app-8.4-src-*`) run PHPUnit inside Docker via `make ... php-test`. Read the **shape** of the output, not just "it failed":

- **Assertion failure** → progress line shows `F`/`E`, and PHPUnit prints a summary (`FAILURES!` / `Tests: N, Assertions: M, Failures: K`) + exit **1** or **2**. The failing test name is in the summary.
- **Abnormal crash** → all passing dots, reaches `NNNN / NNNN (100%)`, but **no PHPUnit summary line** (`OK (...)` / `Tests: ...`) before the run ends, and exit **255**. This means the process died *after* the last test but *before* emitting its result — a PHP fatal, segfault, or OOM at teardown/shutdown. Tests passed; the process crashed.
  - The version footer (`PHP: / PHPUnit: / Xdebug: / Blackfire:`) always prints last — it's a `register_shutdown_function` (tests/bootstrap.php:17), **not** proof the run completed cleanly. Don't mistake it for a summary.
  - Missing JUnit metadata (`/tests` returns 0) corroborates a pre-report crash.
  - CircleCI may only capture stdout; a PHP `Fatal error:` on stderr can be absent from `output_url`. Absence of a fatal message + exit 255 leans toward a **segfault/killed process** rather than a caught error.
- `make: *** [Makefile:61: php-test] Error 255` is `make` reporting the dockerized runner's exit code — 255 is the container/PHP exit, not a make-specific error.

## Diagnosing a crash you can't see in the log

1. **Re-run the job.** Pass on retry ⇒ flaky (segfault/OOM/resource), not deterministic code.
2. Reproduce locally on the **exact CI branch** (CI branch may differ from your local checkout) and read stderr:
   `make -C cli/tester php-test SUITE=src-transactional` — the fatal CircleCI swallowed shows on the terminal.
3. Correlate with the commit under test (`v1.1` job JSON `subject`/`branch`) — a change touching shutdown handlers, destructors, queue fakes, or global state is the prime suspect for a shutdown-time crash.

## Don'ts

- Don't paste the token into chat, commits, or files — source it from `.env`.
- Don't conclude "a test failed" from a non-zero exit alone — check for the PHPUnit summary and the exit code (255 = crash, not assertion failure).
- Don't trust an empty `/tests` result as "no tests ran" — it usually means the report was never written.
