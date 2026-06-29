# OpenCode config reference

How OpenCode discovers and loads each piece of config in this setup. For the full
upstream docs see <https://opencode.ai/docs/config/>.

## Config file precedence

OpenCode merges config from several sources (later overrides earlier):

1. Remote org config (`.well-known/opencode`)
2. Global config — `~/.config/opencode/opencode.json`
3. `OPENCODE_CONFIG` env var (custom path)
4. **Project config — `opencode.json` in the project root** (highest of the standard files)
5. `.opencode/` directory (agents, commands, plugins, skills, …)
6. Inline / managed configs

In this setup that means: `/Volumes/dev/webPOS/opencode.json` overrides
`~/.config/opencode/opencode.json` for the webPOS project.

## Rules (`AGENTS.md` + `instructions`)

OpenCode reads rules from, in order:

1. Local `AGENTS.md`, walking up from the cwd to the git root
2. Global `~/.config/opencode/AGENTS.md`
3. `~/.claude/CLAUDE.md` (unless disabled)

Extra instruction files are pulled in via the `instructions` field (supports globs),
resolved relative to the project root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    ".opencode/rules/*.mdc",
    ".agents/*.md",
    ".opencode/memories.md"
  ]
}
```

- `webpos/opencode.json` in this repo carries that wiring.
- The `.mdc` frontmatter (`description:`, `alwaysApply:`) is included as plain text —
  harmless, just slightly noisy.
- The root `AGENTS.md` of webPOS is read **natively**, so it is not listed in
  `instructions`.

## Skills

Skills are folders containing a `SKILL.md` with YAML frontmatter. OpenCode searches
(project paths walk up to the git root):

- `.opencode/skills/<name>/SKILL.md` ← **this setup**
- `~/.config/opencode/skills/<name>/SKILL.md` (global; enterprise skills live here, under
  the singular `skill/` which is supported for backwards compatibility)
- `.claude/skills/…`, `.agents/skills/…` (and their `~` equivalents)

Recognized frontmatter fields: `name` (required), `description` (required), `license`,
`compatibility`, `metadata`. Cursor's `SKILL.md` format uses only `name` + `description`,
so the files are compatible as-is.

A `.opencode/skill` (singular) → `skills` symlink is kept for naming compatibility; the
`--restore` step recreates it.

Skill access is gated by `permission.skill` in `opencode.json` (`allow` / `ask` / `deny`,
with glob patterns). This setup uses `"skill": "allow"`.

## MCP servers

Configured under `mcp` in `opencode.json`. Two shapes:

```json
{
  "mcp": {
    "figma":   { "type": "remote", "url": "https://mcp.figma.com/mcp", "enabled": true },
    "datadog": { "type": "local",  "command": ["/path/to/datadog_mcp_cli"], "enabled": true }
  }
}
```

- `remote` — hosted MCP, addressed by `url` (auth handled by OpenCode on first use).
- `local` — spawned process, `command` is an argv array.

These live in `global/opencode.json` here, so they are available in every project.

## Permissions

`permission` in the global config controls what the agent may do (`allow` / `ask` /
`deny`), with per-tool and glob-pattern granularity — e.g. `read` denies `*.env`,
`bash` allows `git *` / `curl *` but asks otherwise. See the upstream
[agents docs](https://opencode.ai/docs/agents/) for the full key list.

## Provisioned by the enterprise install (not in this repo)

`enabled_providers`, the `@lightspeedhq/*` plugins, and the enterprise skills under
`~/.config/opencode/skill/` come from the company OpenCode install. They are intentionally
left out of this backup — only personal config is tracked here.
