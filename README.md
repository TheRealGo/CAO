# CAO

**English** | [日本語](README.ja.md)

CAO is a **Chief Agent Officer cockpit** for supervising other agent sessions through tmux. It works with both **Claude Code** and **Codex CLI**, on either side of the supervisor/worker split.

## Quick Start

You launch CAO by starting either Claude Code or Codex CLI in this directory. Whichever you pick becomes the supervisor; worker windows default to the same runner, and individual workers can be flipped to the other runner per window.

```sh
cd ~/CAO
claude        # supervisor = Claude Code
# or
codex         # supervisor = Codex CLI
```

Then ask the CAO supervisor things like:

- `XXX で YYY を実装して`
- `XXX で動いている セッションを監視して`
- `追加で AAA で動いている セッションも監視して`
- `今監視している Agent たちの状況を見て、必要なら返事して`

The supervisor uses `./bin/cao` internally to create, inspect, and type into tmux windows. You should not need to run `bin/cao` yourself.

## Mental Model

```text
User
 │
CAO supervisor (Claude Code or Codex CLI, this directory)
 │
tmux session: cao
 ├── window: pm
 ├── window: project-a-agent   (runner=claude)
 ├── window: project-b-agent   (runner=codex)
 └── window: project-c-agent   (runner=claude)
```

The tmux screen is the source of truth. CAO inspects visible agent output directly with `capture-pane`, then answers, redirects, or asks the user.

The `pm` window keeps a narrow left dashboard pane updated automatically, showing the currently monitored workers and registered external targets. It follows worker additions, removals, and missing targets dynamically.

## What CAO Does Internally

When you say `XXX で YYY を実装して`, CAO:

1. creates or reuses the `cao` tmux session,
2. keeps the supervisor dashboard visible in the `pm` window,
3. creates a window for `XXX`,
4. starts the worker runner in that directory,
5. sends the implementation request,
6. periodically inspects the screen and keeps the work moving.

When you say `XXX で動いている セッションを監視して`, CAO:

1. finds the relevant tmux window if it already exists,
2. registers the existing window with an explicit runner when needed,
3. captures the visible screen,
4. infers state (working / waiting / blocked / asking / finished),
5. responds when the decision is safe,
6. asks the user for high-impact or ambiguous decisions.

## Runner Auto-Detection

`bin/cao` picks the worker default from the supervisor's environment:

| Supervisor | Detected via | Worker default |
|---|---|---|
| Claude Code | `CLAUDECODE` env | `claude` |
| Codex CLI | `CODEX_HOME` env | `codex` |
| Unknown | — | `claude` (fallback) |

Override per worker with `--runner`, or globally with `CAO_RUNNER`:

```sh
./bin/cao add /path/to/project --runner codex     # mix one codex worker in
export CAO_RUNNER=codex                            # force all new workers to codex
```

`cao send` picks the correct submit key per window automatically (`C-m` / Enter for `claude`, `C-j` / Ctrl+Enter for `codex`) based on the runner recorded on that window.

Existing tmux windows that were not created by `cao add` must be registered with an explicit runner before `cao send` can submit input to them. Registered external windows are included in `cao list` and no-argument `cao capture`; unregister them when supervision ends.

## Internal Tool

`./bin/cao` is the supervisor's internal helper. Not user-facing.

```sh
./bin/cao init
./bin/cao add /path/to/project --name project-a                   # runner auto-detected
./bin/cao add /path/to/legacy  --name project-b --runner codex    # explicit codex worker
./bin/cao add /path/to/proj    --name project-c --resume --prompt "続きから"
./bin/cao register other-session:window --runner codex            # existing tmux window
./bin/cao unregister other-session:window                         # stop tracking it
./bin/cao list
./bin/cao capture
./bin/cao capture project-a --lines 180
./bin/cao send project-a "Yes、その方針で進めてください。"
./bin/cao attach
./bin/cao kill
```

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `CAO_SESSION` | `cao` | tmux session name |
| `CAO_RUNNER` | auto-detected | default worker runner (`claude` or `codex`) |
| `CLAUDE_BIN` | `claude` | Claude Code command |
| `CODEX_BIN` | `codex` | Codex command |
| `CAO_HISTORY` | `4000` | tmux pane history limit |
| `CAO_STATE_DIR` | `.cao` | local runtime state for registered external targets |
| `CAO_DASHBOARD_WIDTH` | `34` | width of the automatic `pm` dashboard pane |

## Runner Configuration

CAO ships supervisor configurations for both runners side by side. The two are independent — the supervisor reads only its own runner's files.

### Claude Code (`.claude/` + `CLAUDE.md`)

- `CLAUDE.md` — operating manual for the Claude Code supervisor.
- `.claude/settings.json` — permissions, env, model, hooks, statusline.
- `.claude/commands/cao-*.md` — slash commands (`/cao-add`, `/cao-sweep`, `/cao-rescue`, `/cao-broadcast`).
- `.claude/agents/cao-*.md` — subagents (`cao-supervisor`, `cao-rescue`).
- `.claude/hooks/` — supervision aids (auto-capture after `tmux send-keys`).
- `.claude/statusline.sh` — shows the current worker count and runner mix.

Copy `.claude/settings.local.json.example` to `.claude/settings.local.json` for personal overrides (gitignored).

### Codex CLI (`.codex/` + `AGENTS.md`)

- `AGENTS.md` — operating manual for the Codex supervisor.
- `.codex/config.toml` — runtime sandbox / approval policy.
- `.codex/rules/default.rules` — project-local command rules.

`.codex/config.toml` ships with `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`. This is intentional for the Codex-as-supervisor case: CAO has to read each worker's working tree (`git status`, `cat`, `rg`) and talk to the tmux socket — both live **outside** this repo, which the default `workspace-write` sandbox would block. Adjust it for your own threat model before running Codex CLI here.

The same project config also pins the CAO runtime environment (`CAO_SESSION`, `CAO_RUNNER`, `CLAUDE_BIN`, `CODEX_BIN`) so Codex CLI starts with the expected supervisor defaults in this directory.

## Policy

Prefer direct screen inspection over extra status files. Do not require worker agents to create report files unless the user explicitly asks for that.

Keep CAO as the central user-intent holder:

- answer obvious local choices,
- correct agents that drift from the user's request,
- prevent conflicting ownership,
- escalate high-impact choices to the user,
- summarize only the decisions and outcomes that matter.
