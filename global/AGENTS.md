# Global Rules (migrated from Cursor user rules)

User-global guidelines that apply across all projects.

## Resuming After Compaction

After resuming from a compacted summary, reload every specialized skill named for the active task before performing an external mutation. A summary that says the skill was previously loaded is not a substitute for its current instructions; if the skill is not advertised, read the recorded skill path directly.

## Shell and Tool Availability

- Before reporting an executable as unavailable, run `command -v` in the exact shell that will execute the command. If a non-login shell differs from the user's login shell, check the known package-manager path and `zsh -l -c 'command -v <tool>'` before concluding the tool is missing.
- For GitHub operations, preflight `gh` and `jq`, then verify `gh auth status`, before invoking a workflow script. On macOS, Homebrew's standard CLI path is `/opt/homebrew/bin`.

## Sensitive File Inspection

- Before inspecting any configuration, environment, or runtime-metadata source that may contain credentials, identify the exact setting needed and emit only a narrowly bounded, redacted excerpt or key names.
- Never print a complete sensitive file or unredacted assignment values. Redact by position, removing everything after the first `=`, rather than relying on variable-name suffixes; never read `.env` values into tool output.

## Agent-Produced Artifacts — Storage Convention

Any document, report, audit, plan, summary, diagram (`.mmd`/`.png`/`.svg`), ad-hoc SQL, scratch script, or throw-away markdown generated that is **not** part of the application's source code or its committed in-repo documentation.

### Where to write

Always write under `~/Documents/AgentFiles/`, never inside the project working tree.

- **Tied to a JIRA ticket** → `~/Documents/AgentFiles/<TICKET-ID>/<descriptive-filename>`
  - `<TICKET-ID>` is canonical: uppercase project key, dash, number (e.g. `LSR-36941`).
  - Do not repeat the ticket id in the filename — the folder already encodes it.
  - Example: `~/Documents/AgentFiles/LSR-36941/customer-creation-audit.sql`.
- **No JIRA ticket** → `~/Documents/AgentFiles/<YYYY-MM-DD-HHMM>-<keyword>/<filename>`
  - `<YYYY-MM-DD-HHMM>` is the local date/time the work began.
  - `<keyword>` is one short lower-case word capturing the topic.
  - Example: `~/Documents/AgentFiles/2026-05-14-1508-bananas/at-large-vendor-num-audit.sql`.

### Hard rules

1. Never create these artifacts inside any project repo. No `.ai/` folder, no top-level `LSR-*-*.sql`, no scratch markdown next to source files.
2. Never modify project-owned files (e.g. a project's `AGENTS.md`, `.cursor/rules/`, `.opencode/`, `README.md`) to add or reference this convention. This rule is user-global; it does not belong in any project.
3. When asked for an audit, report, diagram, plan, summary, or scratch query without a path, default to the appropriate `~/Documents/AgentFiles/` folder and report the absolute path written to.
4. When resuming work on a ticket that already has a folder, append to it instead of creating a new dated folder.
5. Rendered/derived outputs (e.g. `.png` from a `.mmd`) live next to their source.
6. Real project assets (source code, Dockerfiles for committed services, schema DDL, committed READMEs, tests, CI config) are **not** artifacts and stay in the repo. If unsure, ask.

## Sean's Reviews

Sean is principal, he is 99.999% always right. If he suggests something about my code, challenge my code first, instead of challenging Sean's suggestion.
