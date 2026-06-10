# CAO

CAO is a **Chief Agent Officer cockpit** for supervising other agent sessions through tmux.

On the `ClaudeCode` branch the supervisor is **Claude Code**, and worker windows default to Claude Code as well. Codex CLI is still supported as a secondary runner.

You should not need to run CAO commands yourself. The intended workflow is:

```sh
cd ~/CAO
claude
```

Then ask the CAO Claude Code things like:

- `XXX で YYY を実装して`
- `XXX で動いている Claude セッションを監視して`
- `追加で AAA で動いている Codex セッションも監視して`
- `今監視している Agent たちの状況を見て、必要なら返事して`

The CAO supervisor uses `./bin/cao` internally to create, inspect, and type into tmux windows.

## Mental Model

```text
User
 │
CAO Claude Code (this directory)
 │
tmux session: cao
 ├── window: pm
 ├── window: project-a-agent   (runner=claude)
 ├── window: project-b-agent   (runner=codex)
 └── window: project-c-agent   (runner=claude)
```

The tmux screen is the source of truth. CAO inspects visible agent output directly with `capture-pane`, then answers, redirects, or asks the user.

## What CAO Does Internally

When you say `XXX で YYY を実装して`, CAO:

1. creates or reuses the `cao` tmux session,
2. creates a window for `XXX`,
3. starts the runner (default: `claude --dangerously-skip-permissions`) in that directory,
4. sends the implementation request,
5. periodically inspects the screen and keeps the work moving.

When you say `XXX で動いている セッションを監視して`, CAO:

1. finds the relevant tmux window if it already exists,
2. captures the visible screen,
3. infers state (working / waiting / blocked / asking / finished),
4. responds when the decision is safe,
5. asks the user for high-impact or ambiguous decisions.

## Internal Tool

`./bin/cao` is the supervisor's internal helper. Not user-facing.

```sh
./bin/cao init
./bin/cao add /path/to/project --name project-a                   # default runner: claude
./bin/cao add /path/to/legacy  --name project-b --runner codex    # codex worker
./bin/cao add /path/to/proj    --name project-c --resume --prompt "続きから"
./bin/cao list
./bin/cao capture
./bin/cao capture project-a --lines 180
./bin/cao send project-a "Yes、その方針で進めてください。"
./bin/cao attach
./bin/cao kill
```

`cao send` automatically picks the correct submit key (`C-m` for `claude`, `C-j` for `codex`) based on the window's recorded runner.

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `CAO_SESSION` | `cao` | tmux session name |
| `CAO_RUNNER` | `claude` | default worker runner (`claude` or `codex`) |
| `CLAUDE_BIN` | `claude` | Claude Code command |
| `CODEX_BIN` | `codex` | Codex command |
| `CAO_HISTORY` | `4000` | tmux pane history limit |

## Claude Code Configuration

This branch includes a `.claude/` directory and `CLAUDE.md` that wire the supervisor into Claude Code:

- `CLAUDE.md` — the supervisor's operating manual (replaces `AGENTS.md` for the Claude Code runner).
- `.claude/settings.json` — permissions, env, model, hooks, statusline.
- `.claude/commands/cao-*.md` — slash commands (`/cao-add`, `/cao-sweep`, `/cao-rescue`, `/cao-broadcast`).
- `.claude/agents/cao-*.md` — subagents (`cao-supervisor`, `cao-rescue`).
- `.claude/hooks/` — supervision aids (auto-capture after `tmux send-keys`).
- `.claude/statusline.sh` — shows the current worker count and runner mix.

Copy `.claude/settings.local.json.example` to `.claude/settings.local.json` for personal overrides (gitignored).

## Codex Runner (Secondary)

The Codex runner is preserved end-to-end on this branch:

- `.codex/config.toml` remains.
- `AGENTS.md` is retained as the Codex supervisor manual and as the Codex runner spec.
- `cao add --runner codex ...` spawns a Codex worker. `cao send` switches its submit key to `C-j` automatically.

If you want to run the supervisor itself in Codex CLI, switch to `main` or set `CODEX_BIN` in your environment and start `codex` in this directory.

`.codex/config.toml` ships with `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`. This is intentional for the Codex-as-supervisor case: CAO has to read each worker's working tree (`git status`, `cat`, `rg`) and talk to the tmux socket — both live **outside** this repo, which the default `workspace-write` sandbox would block. The setting is unused on the `ClaudeCode` branch (Claude Code's permissions come from `.claude/settings.json`). Adjust it for your own threat model before running Codex CLI here.

## Policy

Prefer direct screen inspection over extra status files. Do not require worker agents to create report files unless the user explicitly asks for that.

Keep CAO as the central user-intent holder:

- answer obvious local choices,
- correct agents that drift from the user's request,
- prevent conflicting ownership,
- escalate high-impact choices to the user,
- summarize only the decisions and outcomes that matter.
