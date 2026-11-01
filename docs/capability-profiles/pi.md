# Pi capability profiles

Pi 1.3.0 exposes most capability controls as command-line flags. The default agent directory is controlled by `PI_CODING_AGENT_DIR` and is `~/.pi/agent` when the variable is unset. The current user settings file is [~/.pi/agent/settings.json](/Users/junjie/.pi/agent/settings.json).

Pi discovers packages and extensions from its settings, then applies per-run flags. The relevant flags are:

```text
--no-extensions       disable extension discovery and built-in extensions
--extension PATH      load an explicit extension; repeat the flag
--no-skills           disable skill discovery and loading
--skill PATH          load an explicit skill file or directory; repeat the flag
--no-mcp              disable MCP servers and MCP tools
--tools VALUE         set the built-in tool allowlist
--exclude-tools VALUE disable tools after the allowlist is applied
--no-context-files    skip AGENTS.md and CLAUDE.md discovery
--no-prompt-templates disable prompt template discovery
--no-themes           disable theme discovery
--no-session          avoid saving the session
--session-dir PATH    choose session storage
```

A research session can therefore start with a small explicit capability set:

```sh
pi \
  --no-extensions \
  --no-skills \
  --no-mcp \
  --no-context-files \
  --skill /tmp/sm-bundle/skills/paper-reading \
  --skill /tmp/sm-bundle/skills/literature \
  --tools read,grep,find,ls,bash
```

`--no-extensions` still permits explicitly supplied `--extension` paths. `--tools` controls the built-in set, while MCP tools remain available unless the profile also uses `--no-mcp` or explicitly filters MCP names. Use `--exclude-tools` for a denylist that includes MCP tools.

The Pi adapter should map an `sm` preset to explicit `--skill` paths. A Pi extension is a separate artifact and must be selected with `--extension`. A Claude plugin directory is not automatically a Pi extension. If a profile needs an extension, the profile must name its Pi extension source.

The adapter should keep the user's model and authentication settings by default. It can change the model or thinking level with `--model`, `--provider`, and `--thinking`. It can use `--no-session` when the profile must not persist conversation history. These are separate choices from skill and tool selection.

Pi can suppress context files for a session. This gives it a stronger capability boundary than runtimes that always load a global `CLAUDE.md`. If a profile needs a short instruction set, pass it with `--system-prompt` or `--append-system-prompt` instead of re-enabling the whole context-file search.

The adapter must not mutate `~/.pi/agent/settings.json` to switch profiles. It should construct the command line for one process and report the selected skills, extensions, MCP state, tool allowlist, context-file state, model, and session persistence state.
