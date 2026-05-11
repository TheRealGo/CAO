# CAO

CAO is a Chief Agent Officer cockpit for supervising other Codex sessions through tmux.

You should not need to run CAO commands yourself. The intended workflow is:

```sh
cd /Users/therealgo/Codex/CAO
codex
```

Then ask the CAO Codex things like:

- `XXX で YYY を実装して`
- `XXX で動いている Codex セッションを監視して`
- `追加で AAA で動いている Codex セッションも監視して`
- `今監視している Agent たちの状況を見て、必要なら返事して`

The CAO Codex uses `./bin/cao` internally to create, inspect, and type into tmux windows.

## Mental Model

```text
User
 |
CAO Codex in this directory
 |
tmux session: cao
 |
+-- window: pm
+-- window: project-a-agent
+-- window: project-b-agent
```

The tmux screen is the source of truth. CAO should inspect visible agent output directly with `capture-pane`, then answer, redirect, or ask the user.

## What CAO Does Internally

When you say `XXX で YYY を実装して`, CAO should:

1. create or reuse the `cao` tmux session,
2. create a window for `XXX`,
3. start `codex` in that directory,
4. send the implementation request to that Codex session,
5. periodically inspect the screen and keep the work moving.

When you say `XXX で動いている Codex セッションを監視して`, CAO should:

1. find the relevant tmux session/window if it already exists,
2. capture the visible screen,
3. infer whether it is working, waiting, blocked, or asking a question,
4. respond only when the decision is safe,
5. ask you when the decision affects product intent, architecture, permissions, schema, public APIs, destructive Git operations, or cross-agent ownership.

## Internal Tool

`./bin/cao` is an internal helper for the CAO Codex, not a user-facing workflow.

Useful internal commands:

```sh
./bin/cao init
./bin/cao add /path/to/project --name project-a --resume
./bin/cao list
./bin/cao capture
./bin/cao capture project-a --lines 180
./bin/cao send project-a "Yes、その方針で進めてください。"
./bin/cao attach
```

CAO may also call raw `tmux` commands when attaching to an already-running session that was not created by `./bin/cao`.

## Policy

Prefer direct screen inspection over extra status files. Do not require worker agents to create report files unless the user explicitly asks for that.

Keep CAO as the central user-intent holder:

- answer obvious local choices,
- correct agents that drift from the user's request,
- prevent conflicting ownership,
- escalate high-impact choices to the user,
- summarize only the decisions and outcomes that matter.
