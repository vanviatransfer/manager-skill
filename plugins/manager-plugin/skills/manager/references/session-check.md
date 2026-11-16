# Overhead and session checks

Read by the manager skill at step 0 item 3, once per run, and again after a compaction until their
recommendations are given.

Overhead check (read-only): list what the repo itself enables — `enabledPlugins` in
`.claude/settings.json` / `settings.local.json`, servers in `.mcp.json`, skills under
`.claude/skills` — other than this plugin. Never change them. They load into the main session
and into a `general-purpose` fallback (`manager-plugin:fallback` drops skills and the MCP
servers it denies); user-level settings aren't covered.

Session check (read-only; never edit settings yourself): (a) the auto-compact window, from
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` and the `autoCompactWindow` keys (top level, or under
`modelSettings` for this session's model) in `~/.claude/settings.json` and the project's settings;
a value is in tokens, as an integer or in `300k` style. If none is set, or one above 300k is (often
a larger window an older plugin version recommended), recommend an orchestrator window of 300k:
the owner runs `/autocompact 300k` if they haven't already (you can't run a built-in command, and
a `--autocompact` flag isn't visible to you), and for a value above 300k you name it (`şu an
<değer>`); if only the environment variable is above 300k, recommend lowering it instead. A value
of 300k or less is the owner's choice: leave it. It sets the main session's window only; never say
it covers subagents. (b) Whether `cc-plugin-you-should-know@builtin` is enabled
(`true`) in an `enabledPlugins` of those files: its side checks are extra requests to the same
model and its notes wait for a human at the prompt, so recommend disabling it for the run. (c)
The MCP servers and connectors this session shows (names from its deferred-tool list and MCP
server instruction blocks): each loads into the main session every turn, while the restricted
plugin agents don't get them. From the plan's remaining phases and the project rules, name the
ones this project's work won't use and recommend `/mcp disable <name>` for each: it turns the
server off for this project only, from the next session on, and `/mcp enable <name>` turns it
back on. Never recommend the GitHub backend's server or any server the plan or project rules use;
when unsure, leave it out. You can't run these commands; the owner types them. Put these
recommendations in the model-strategy question when you ask it, otherwise in the final report,
once per run.
