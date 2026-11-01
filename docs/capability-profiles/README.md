# Capability profiles

A capability profile selects the tools and instructions that an agent can use for one session. It does not need to create a new account, copy credentials, or replace the agent's entire home directory.

The normalized profile contains these fields when the target runtime supports them:

```text
skills
plugins or extensions
MCP servers
built-in tools
hooks
context files
agents or subagents
model and thinking level
```

`sm` remains the source of truth for skill membership, tags, and presets. Each runtime keeps its own native package format. Claude Code uses plugin directories and session settings. Codex uses an app-server and skill roots. Pi uses per-run flags with explicit skill and extension paths. dsh uses a named profile plus a patch layer.

The default mode remains additive. A capability mode creates a session profile and leaves authentication and other native state in place. A runtime may inherit sources that its API cannot remove. The adapter must report those sources instead of claiming complete isolation.

| Runtime | Per-session control | Native profile model | Current sm-plugin status |
| --- | --- | --- | --- |
| Claude Code | `--settings`, `--plugin-dir`, `--mcp-config`, `--strict-mcp-config`, `--tools` | User, project, local, and managed settings | `--mode capability` is implemented |
| Codex | app-server config, `skills/extraRoots/set`, `skills.config` | User, project, session, and app-server roots | `--mode exclusive` is implemented for skills |
| Pi | `--no-*`, `--skill`, `--extension`, `--tools`, `--exclude-tools` | `$PI_CODING_AGENT_DIR` plus per-run flags | Adapter design only |
| dsh | `--profile`, `--patch`, `--dump-config` | Profile bundle tree plus ordered patch layers | Adapter design only |

A profile renderer must keep these boundaries visible:

- A skill is an instruction workflow.
- A plugin or extension is a runtime package that may add skills, tools, hooks, MCP servers, or agents.
- An MCP server is a tool source with its own process or transport.
- A hook is lifecycle automation and may remain inherited when the target runtime has no session-level removal API.
- A context file is persistent instruction text. It is separate from the capability package.

Do not copy credentials or edit global runtime directories when creating a session profile. Write temporary settings, patch, or bundle files under a session-owned directory and remove them after the process exits.

## Adapter documents

- [Pi](pi.md) records per-run flags, package discovery, and the Pi adapter boundary.
- [Codex](codex.md) records app-server roots, session config, and skill verification.
- [Claude Code](claude-code.md) records session settings, plugin selection, MCP, and inherited sources.
- [dsh](dsh.md) records profile bundles, Cordis patch layers, and per-run overlays.
