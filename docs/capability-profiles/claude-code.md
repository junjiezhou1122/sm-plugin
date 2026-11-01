# Claude Code capability profiles

Claude Code 2.1.193 and 2.1.306 expose per-session flags for settings, plugins, MCP, and built-in tools. The current `sm-plugin` integration uses `--mode capability`.

The session command combines these inputs:

```text
--settings FILE
--plugin-dir PATH
--mcp-config PATH_OR_JSON
--strict-mcp-config
--tools VALUE
```

The generated temporary settings contain:

```json
{
  "disableBundledSkills": true,
  "enabledPlugins": {
    "plugin@market": false
  },
  "skillOverrides": {
    "ordinary-skill": "off"
  }
}
```

The adapter gets installed plugin IDs from `claude plugin list --json`. It sets known plugins to `false`, sets explicitly selected `--plugin PLUGIN_ID` entries to `true`, and loads local plugin directories with repeated `--plugin-dir` flags. The selected `sm` bundle is also loaded with `--plugin-dir`.

MCP is strict in capability mode. If the user passes no `--mcp-config`, the adapter passes an empty server set. If the user passes one or more MCP files or JSON values, the adapter passes them with `--strict-mcp-config`. A selected plugin that declares MCP servers needs an explicit compatible MCP configuration. The adapter reports this case instead of silently treating the plugin's MCP tools as available.

The built-in tool allowlist is optional. Pass it with `--tools Read,Edit` or a comma-separated value. If no allowlist is supplied, Claude keeps its native built-in tools.

Use the current integration with:

```sh
sm-plugin launch claude Research --mode capability
sm-plugin launch claude Research --mode capability \
  --plugin pstack@pstack-claude \
  --tools Read,Edit
sm-plugin verify claude Research --mode capability
```

Capability mode does not claim complete Claude environment isolation. These sources remain inherited:

- Authentication and account state.
- Model defaults.
- `CLAUDE.md` and project instruction files.
- Global hooks.
- Custom agents.
- Managed plugins and organization policy.

Claude settings merge rules prevent a normal `--settings` file from clearing every hook or managed source. `--bare` and `CLAUDE_CONFIG_DIR` provide stronger isolation, but they also change authentication, history, or other native behavior. They are separate modes and should not be used implicitly by the capability adapter.

The adapter must remove the temporary settings file after the Claude process exits. It must not edit `~/.claude/settings.json`, installed plugin records, global skill directories, or credential files.
