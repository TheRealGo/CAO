---
name: cao-browser-routing
description: "Route browser choice, local UI control, and CAO/Worker triage. Use when a task mentions Playwright, Playwrite, Browser MCP, Chrome, Atlas, Colab MCP, Colab notebook connection, dynamic Colab tools, CAO, Worker, sub-agent questions, Computer Use, browser permission/connect dialogs, or deciding whether to escalate work to the human user. Encodes the local rule: Playwright automation uses Chrome; Colab MCP browser connection uses Atlas; CAO should do feasible judgment, review, coordination, and local chores before involving the user."
---

# CAO Browser Routing

## Routing Rules

- Use Chrome for Playwright and browser automation tasks. Playwright MCP is built around Playwright-managed browsers or CDP-compatible Chromium/Chrome; do not try Atlas for Playwright unless the user explicitly asks to test Atlas remote debugging.
- Use Atlas for Colab MCP browser-side connection flows. When `open_colab_browser_connection` must open a notebook for local MCP, set `BROWSER` to an Atlas opener instead of Chrome.
- Use the existing `colab-mcp-standalone` skill for Colab MCP daemon/session rules. This skill only decides browser routing and UI-control fallbacks.
- Do not reuse a Chrome-opened Colab MCP URL in Atlas for fair browser testing. Start a fresh daemon/session per browser when comparing them.
- Never print or store full Colab MCP URLs, proxy tokens, or token-bearing command lines in reports, repo files, or skill files.

## Colab MCP With Atlas

Do not let a Worker discover Colab MCP helper locations by searching the project or home directory. In this environment the persistent daemon is:

```text
$HOME/.codex/skills/colab-mcp-standalone/scripts/colab_mcp_daemon.py
```

Use this pattern for standalone daemon work:

```bash
BASE="/private/tmp/colab-mcp-$(date +%Y%m%d%H%M%S)-$$"
mkdir -p "$BASE/cache" "$BASE/tools" "$BASE/state"
cat >/private/tmp/open_atlas_colab <<'SH'
#!/bin/sh
exec /usr/bin/open -a "/Applications/ChatGPT Atlas.app" "$@"
SH
chmod 700 /private/tmp/open_atlas_colab

UV_CACHE_DIR="$BASE/cache" \
UV_TOOL_DIR="$BASE/tools" \
BROWSER="/private/tmp/open_atlas_colab %s" \
uv run --with mcp python "$HOME/.codex/skills/colab-mcp-standalone/scripts/colab_mcp_daemon.py" \
  --state "$BASE/state/daemon.json" start \
  --wait-seconds 180 \
  --cache-dir "$BASE/cache" \
  --uv-tool-dir "$BASE/tools"
```

After the Atlas Colab window appears, accept `Connect to a local Colab MCP server` immediately. The `open_colab_browser_connection` call has its own 60 second UI wait; if CAO misses that window and the daemon records `open_result: false`, stop that attempt and start a fresh daemon/session instead of spending time debugging the stale tab.

Verify through the same daemon:

```bash
uv run --with mcp python "$HOME/.codex/skills/colab-mcp-standalone/scripts/colab_mcp_daemon.py" --state "$BASE/state/daemon.json" client --status
uv run --with mcp python "$HOME/.codex/skills/colab-mcp-standalone/scripts/colab_mcp_daemon.py" --state "$BASE/state/daemon.json" client --tool get_cells --arguments '{}'
```

Expected dynamic tools are `add_code_cell`, `run_code_cell`, `get_cells`, `update_cell`, `delete_cell`, `move_cell`, and `add_text_cell`.

Count the connection as successful only when `connected: true` and `get_cells` succeeds. A visible notebook, a dismissed dialog, or `open_colab_browser_connection` alone is not enough.

## Native Colab Tools

If the user asks whether the standalone workaround is still needed, check native tool visibility first with tool discovery for `colab mcp add_code_cell run_code_cell get_cells`.

- If native `add_code_cell`, `run_code_cell`, and `get_cells` are visible after a native Colab connection, use native tools and record that standalone was unnecessary for that session.
- If only `open_colab_browser_connection` is visible, treat it as a Codex dynamic tool refresh problem and use `colab-mcp-standalone`.
- Browser choice does not by itself prove native dynamic tools will appear. Chrome/Atlas affects the notebook-side connection UI; Codex tool refresh is a separate MCP-client behavior.

## CAO UI Control Fallback

Computer Use may fail to resolve apps by display name, bundle id, or app path in this environment. When that happens:

1. Use `list_apps` only as a hint, not proof that `get_app_state` will work.
2. Use `screencapture -D <display>` and `view_image` to inspect real screens.
3. Use `CGWindowListCopyWindowInfo` via Swift to find the actual owner, title, and bounds of Chrome/Atlas windows.
4. When a browser window's bounds are known, inspect that exact region with `screencapture -R X,Y,W,H`; do not rely on a full-screen screenshot that may capture a different frontmost app or display.
5. Prefer bundled scripts in this skill over raw one-off coordinates.
6. After clicking `Connect`, take a region screenshot. If the dialog is still visible, click the button center again before waiting on daemon status.
7. After clicking `Connect`, verify with daemon `client --status` and `client --tool get_cells`; a dismissed dialog alone is not proof of connection.

Useful commands:

```bash
swift ./.codex/skills/cao-browser-routing/scripts/list-browser-windows.swift
swift ./.codex/skills/cao-browser-routing/scripts/click-colab-connect.swift "ChatGPT Atlas"
swift ./.codex/skills/cao-browser-routing/scripts/click-colab-connect.swift "Google Chrome" 0.64 0.63
```

The optional numeric arguments are `x_fraction y_fraction` relative to the detected Colab window bounds. Use them when banners or sidebars shift the default Connect button location.

## CAO Worker Triage

For general Worker-question handling and escalation discipline, use the project-local `cao-supervisor-operator` skill. This section adds browser/UI-specific reminders.

Treat Worker questions and partial results as addressed to CAO first, not automatically to the human user. CAO is an operator and reviewer, not only a message relay between Worker and user.

- Before forwarding a Worker question to the user, decide whether CAO can answer it by inspecting files, running commands, checking screenshots, reading logs, reviewing artifacts, or applying product/design/engineering judgment.
- Do feasible intermediate work yourself: open and inspect artifacts, review screenshots or `.pptx`/docs, compare outputs to requirements, summarize Worker results, resolve obvious ambiguities, choose a reasonable next action, and ask another tool/agent only when that adds evidence.
- If a Worker asks for routine local action, such as clicking a browser button, checking a visible dialog, opening/closing a tab, confirming whether a UI element exists, or retrying a local tool path, CAO should perform the action or inspect the environment directly.
- Do not ask the human user to do mechanical work, basic judgment calls, or coordination that CAO can reasonably handle with available context, Computer Use, screenshots, AX/CoreGraphics scripts, shell commands, MCP/daemon clients, or artifact review.
- Ask the human user only when CAO lacks required private context, business/product preference, credentials, policy approval, external state, or a genuinely user-owned decision; or when OS/browser security requires a human-only action that cannot be safely automated.
- If CAO escalates to the user, state the concrete blocker, what was already attempted, and the decision only the user can make. Avoid vague relay messages from Worker when CAO can first narrow or resolve the issue.

## Measurement Discipline

For Chrome versus Atlas comparisons:

- Close existing Colab tabs/windows first.
- Stop any old standalone daemon before the run.
- Use separate state/socket/cache directories per browser.
- Let each daemon generate its own fresh Colab MCP URL.
- Count success only when daemon tools include `add_code_cell`, `run_code_cell`, and `get_cells`, or when `get_cells` succeeds.
- Clean up Colab tabs/windows and daemon processes afterward.
