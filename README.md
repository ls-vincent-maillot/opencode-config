# opencode-config

Personal backup of my [OpenCode](https://opencode.ai) configuration, migrated from
Cursor. The live config files stay where OpenCode expects them
(`~/.config/opencode/` and `/Volumes/dev/webPOS/.opencode/`); this repo holds **copies**
synced by `sync-opencode-config.sh`. Nothing in the live setup is moved or symlinked,
so the working structure is never altered.

## Why this repo exists

The OpenCode project config lives under `.opencode/` inside the webPOS working tree,
which is **git-ignored locally** (not versioned by the webPOS repo). It is therefore
local-only: a fresh clone or a `git clean -dfx` would wipe it. This repo is the durable,
remote-backed source of truth for that config.

## What's tracked

| Repo path | Live location | Contents |
| --- | --- | --- |
| `global/opencode.json` | `~/.config/opencode/opencode.json` | model, providers, permissions, plugins, MCP servers, and agent configuration |
| `global/AGENTS.md` | `~/.config/opencode/AGENTS.md` | global rules (apply to every project) |
| `global/opencode-ghostty-notifier.json` | `~/.config/opencode/opencode-ghostty-notifier.json` | Ghostty notifier plugin (sound off, notifications on) |
| `global/mechanical-commands.md` | `~/.config/opencode/mechanical-commands.md` | global delegation guidance for mechanical commands |
| `global/agents/luna-runner.md` | `~/.config/opencode/agents/luna-runner.md` | fixed-model subagent for formatters, tests, linters, type checks, and builds |
| `webpos/opencode.json` | `/Volumes/dev/webPOS/opencode.json` | `instructions` wiring (rules + memories) |
| `webpos/dot-opencode/skills/` | `.../.opencode/skills/` | 11 R-Series skills |
| `webpos/dot-opencode/rules/` | `.../.opencode/rules/` | 16 project rules (`.mdc`) |
| `webpos/dot-opencode/memories.md` | `.../.opencode/memories.md` | personal project memories |

What is **not** tracked here: the enterprise-managed skills under
`~/.config/opencode/skill/` (provisioned by the company install), `node_modules`,
plugins, and the Cursor chat archive (that lives under `~/Documents/AgentFiles/`).

## Prerequisites

- `bash`, `git`, `rsync` (all default on macOS)
- An SSH remote already configured (`origin`)

## Usage

### Back up live config → repo

```bash
sync-opencode-config              # alias: copies live files in, makes a local commit
git -C ~/opencode-config push     # push when ready (the script never pushes)
```

The alias lives in `~/.zshrc`. The script only commits locally — pushing is always a
deliberate, separate step.

### Restore repo → live config

On a new machine, or after a re-clone / accidental wipe of `.opencode/`:

```bash
git clone git@github.com:ls-vincent-maillot/opencode-config.git ~/opencode-config
~/opencode-config/sync-opencode-config.sh --restore
```

`--restore` overwrites the live config files from the repo and recreates the
`.opencode/skill` backwards-compat symlink.

### Other flags

```bash
sync-opencode-config.sh --no-commit   # backup only, skip the commit
```

## Session Export Utility

The shared exporter in [`tools/export_session.py`](tools/export_session.py) exports an
OpenCode session as JSON by default. It requires Python 3.10+ and the `opencode` CLI.

```bash
python3 tools/export_session.py ses_xxx --sanitize --cleanup -o session.json
```

Options:

- `--sanitize` asks OpenCode to redact sensitive transcript and file data.
- `--cleanup` removes internal fields, reasoning blocks, tool executions, lifecycle
  parts, timestamps, IDs, and empty objects locally.
- `--format rtf` exports an RTF document instead of JSON; macOS `textutil` is required.

If no session ID is supplied, the utility lists the 10 latest sessions:

```bash
python3 tools/export_session.py
```

If a supplied session ID cannot be found, it reports the error and prints the same list
so the correct ID can be selected. Generated `ses_*.json` and `ses_*.rtf` files are ignored
by Git.

## Documentation

- [`docs/MIGRATION.md`](docs/MIGRATION.md) — full record of the Cursor → OpenCode
  migration: what moved where, what wasn't portable, and the decisions taken.
- [`docs/OPENCODE-CONFIG-REFERENCE.md`](docs/OPENCODE-CONFIG-REFERENCE.md) — how
  OpenCode discovers and loads each piece of config (precedence, skills, instructions,
  MCP).
