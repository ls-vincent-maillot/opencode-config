# opencode-config

Personal backup of my OpenCode configuration. The live files stay where they are
(`~/.config/opencode/` and `/Volumes/dev/webPOS/.opencode/`); this repo holds copies
synced by `sync-opencode-config.sh`. Nothing in the live setup is moved or symlinked.

## Layout

```
global/
  opencode.json     # ~/.config/opencode/opencode.json (providers, permissions, plugins, MCP)
  AGENTS.md         # ~/.config/opencode/AGENTS.md (global rules)
webpos/
  opencode.json     # /Volumes/dev/webPOS/opencode.json (instructions wiring)
  dot-opencode/
    skills/         # /Volumes/dev/webPOS/.opencode/skills/ (R-Series skills)
    rules/          # /Volumes/dev/webPOS/.opencode/rules/  (project rules)
    memories.md     # /Volumes/dev/webPOS/.opencode/memories.md
```

## Sync (backup live → repo)

```
sync-opencode-config        # alias; runs the script and makes a local commit
git -C ~/opencode-config push   # push when ready (script never pushes)
```

## Restore (repo → live, e.g. new machine or after a re-clone)

```
~/opencode-config/sync-opencode-config.sh --restore
```

This overwrites the live config files from the repo and recreates the `.opencode/skill`
compat symlink.
