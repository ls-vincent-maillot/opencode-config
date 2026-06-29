# Cursor → OpenCode migration record

Record of the migration from Cursor (Claude Opus) to OpenCode (GPT-5.3 Codex),
performed June 2026. Cursor and OpenCode are kept running **in parallel** during the
trial period; nothing in the Cursor setup was removed.

## Guiding decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Project config scope | Local, non-committed | Don't impose OpenCode config on the webPOS team via git |
| Skills/rules home | `.opencode/` (real files) | OpenCode-native, decoupled from the `.cursor/` folder that disappears when Cursor is uninstalled |
| Global rules / MCP | `~/.config/opencode/` | User-wide, apply across all projects |
| Memories home | `.opencode/memories.md` | Project-specific (R-Series), wired via `instructions` |
| Durability | Separate personal repo (this one) | `.opencode/` is git-ignored locally, so it needs an external backup |

## What was migrated

| Item | From (Cursor) | To (OpenCode) | Notes |
| --- | --- | --- | --- |
| Skills | `.cursor/skills/` (12) | `.opencode/skills/` (11) | Same `SKILL.md` format; 1 dropped as a duplicate (see below) |
| Project rules | `.cursor/rules/*.mdc` (16) | `.opencode/rules/*.mdc` | Wired via `instructions` in `opencode.json` |
| Global rules | `~/.cursor/rules/*.mdc` (2) | `~/.config/opencode/AGENTS.md` | `cursor-artifacts`, `sean-reviews` |
| Memories | Cursor app DB (3) | `.opencode/memories.md` | Not file-based in Cursor; recreated as markdown |
| MCP servers | `~/.cursor/mcp.json` | `~/.config/opencode/opencode.json` (`mcp`) | Figma (remote) + datadog (local) |
| Root routing | `AGENTS.md` | `AGENTS.md` | Read natively by OpenCode — no change needed |
| Chat history | 162 `.jsonl` transcripts | `~/Documents/AgentFiles/cursor-chat-archive/*.md` | Exported as readable markdown (see below) |

### Skill deduplication

The enterprise OpenCode install ships its own skills under `~/.config/opencode/skill/`.
After comparing contents, only **one** genuine duplicate was found and dropped:

- `pr-thread-audit` — its stale/unreplied thread-triage logic is already covered by the
  enterprise `pull-request` skill.

Kept (verified **not** duplicates): `pre-merge-do-not-merge-check` (unique guard),
`datadog-access` (queries Datadog, vs. enterprise `datadog-service-catalog` which
generates YAML), `review-webpos-pr` / `review-data-layer-pr` (R-Series-specific
checklists), and the 7 R-Series domain skills.

### Chat export

All 162 Cursor transcripts were rendered to markdown (title header + metadata + full
turn-by-turn conversation, with `tool_use` calls shown as JSON blocks). Two inherent
limitations of the Cursor transcript format:

1. **Tool results are not stored** — only the calls are. The export shows what the agent
   requested, not the raw output it received.
2. **Internal reasoning and visible text are stored together** and cannot be separated.

The export script is reproducible — see the original `/tmp/export_cursor_chats.py`
(re-run before uninstalling Cursor to capture the latest chats).

## What was NOT migrated (and why)

| Item | Reason |
| --- | --- |
| MCP Atlassian | Plugin-provided in Cursor (config not file-extractable); Jira already covered by the enterprise `atlassian-cli-jira` skill + the `jira-integration` rule |
| Notification hook | Cursor `hooks.json` was empty; enterprise `opencode-ghostty-notifier` plugin covers it |
| Custom modes / commands / prompts | Stored in the Cursor app DB, not extractable as files; none found |
| `settings.json`, `keybindings.json`, `argv.json` | IDE/editor-level, not agent behavior |
| `extensions/`, `plugins/`, `skills-cursor/`, `ai-tracking/` | Internal to the Cursor app / telemetry |
| Chat transcripts (native format) | Proprietary `.jsonl`; archived as markdown instead |

## Folder rename

`~/Documents/CursorFiles/` → **`~/Documents/AgentFiles/`** (tool-agnostic). The artifact
paths were updated in **both** tools to keep them aligned:

- OpenCode: `~/.config/opencode/AGENTS.md`
- Cursor: `~/.cursor/rules/cursor-artifacts.mdc`
- Skills referencing the path: `debugging-mysql-local`, `bigquery-cdc-investigations`
  (both the `.cursor/` originals and the `.opencode/` copies)

## Parallel-run notes

- Both tools coexist: Cursor uses `.cursor/`, OpenCode uses `.opencode/` + global config.
- Re-run the chat export before uninstalling Cursor.
- If OpenCode is adopted for good, the skills/rules can be moved to `.agents/` (which is
  git-tracked by webPOS) for team sharing — a separate decision.
