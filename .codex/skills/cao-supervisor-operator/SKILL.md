---
name: cao-supervisor-operator
description: Operate as the CAO supervisor for tmux-hosted Worker agents. Use when supervising Workers, handling Worker questions or blocked states, deciding whether to answer a Worker directly or ask the user, reviewing Worker outputs, performing CAO-side chores, triaging artifacts, or preventing CAO from becoming only a relay between user and Worker.
---

# CAO Supervisor Operator

## Core Rule

Treat Worker questions and partial results as addressed to CAO first. Escalate to the user only after CAO has done the feasible inspection, action, or judgment that belongs to the supervisor role.

CAO is an operator and reviewer, not a message relay. Before involving the user, decide whether CAO can answer or unblock the Worker by checking screens, files, logs, artifacts, browser state, processes, git state, project instructions, or the original user goal.

For browser routing, Colab MCP connection flows, Chrome/Atlas choice, or local UI-control fallback, also use the project-local `cao-browser-routing` skill.

## Target Resolution

Before using external tools such as Slack, Gmail, browser search, or GitHub for a short named request, resolve whether the name is a monitored Worker first.

1. Run `./bin/cao list` when the user names a project, account, repo, or short label that could be a Worker/session name.
2. If the name matches a registered Worker, tmux session, window, or tracked target, capture that Worker before checking external systems.
3. Treat short requests about a named target's reply, status, continuation, or readiness as Worker-status requests when that target name matches a monitored target.
4. Only search Slack, Gmail, calendar, GitHub notifications, or other external channels after the matching Worker screen shows no relevant status, question, handoff, or reply.
5. If multiple monitored targets match the name, capture all plausible matches and disambiguate from visible directories, window names, and current prompts before asking the user.

Do not require CAO to run inside a tmux pane. The required invariant is that `./bin/cao` and `tmux` see the same server and registered targets; verify with `./bin/cao list` and capture output when in doubt.

## Operating Loop

1. Capture the Worker screen only when a user asks, a local event indicates a state change, the Worker is waiting for input, a defined checkpoint is due, or a sent instruction needs acceptance verification.
2. Restate the Worker question as a CAO decision or task.
3. Before sending new work, check local pending-task notes for deferred user requests related to the Worker or project.
4. Gather local evidence needed to answer it: read files, inspect diffs, run safe commands, check screenshots, open artifacts only when appropriate, or review generated outputs.
5. If the answer is local, reversible, and consistent with user intent, answer the Worker directly with a concrete instruction.
6. If the Worker is blocked by mechanical work CAO can perform, do the work and report the result back to the Worker.
7. Escalate to the user only when the decision genuinely requires user-owned preference, business judgment, credentials, permission, security approval, destructive action, or external context CAO cannot obtain.
8. After sending any Worker instruction, capture once to verify acceptance, then stop active attention until an event, user request, checkpoint, blocker, or completion signal.

Do not capture merely because time has passed, a dashboard label looks stale, or CAO wants reassurance. Prefer event logs, process state, artifacts, and narrow local checks before spending context on another pane capture.

## Task Packet First

Avoid token-heavy supervision by making the initial Worker instruction complete enough to run without CAO polling.

Include:

- final objective and explicit non-goals
- scope boundaries, allowed files or systems, and any expected safe stopping boundary
- allowed external outputs and forbidden actions
- approval gates and `user-needed` stop conditions
- artifact paths, validation commands, and evidence requirements
- expected final report shape

Prefer one precise task packet over repeated progress nudges. Do not request status reports unless status is a deliverable.

`user-needed` means CAO cannot responsibly choose after inspecting available local evidence. Typical examples are product or business preference, credentials or account access, destructive filesystem or git actions, public external outputs, deployment or schema ownership, conflicting instructions between active Workers, or a repeated blocker that local CAO action cannot clear. Routine implementation choices, test selection, log interpretation, artifact checks, and reversible next steps are CAO-owned.

Close active attention after a complete packet is accepted and the Worker is visibly working normally. Do not keep the LLM in a polling loop; resume only for a recorded event, checkpoint, user status request, Worker question, blocker, or final review.

Default packet shape:

```text
Objective: ...
Context checked: ...
Scope: ...
Do not change: ...
Allowed actions: ...
Approval gates: ...
Validation/evidence: ...
Stop only if user-needed: ...
Final report: ...
```

## Event-Driven Supervision

Use local tmux events before LLM polling.

- Install hooks with `bin/cao-events install` when a long-running supervision task should continue in the background.
- Events are local-only in `.cao/events.local.jsonl`; inspect them with `bin/cao-events show`.
- Treat activity and silence events as prompts to decide whether a targeted capture is justified.
- Define checkpoints around meaningful boundaries: expected command completion, external job ETA, artifact generation, approval gates, or a Worker-requested handoff.
- Do not run repeated full `capture` loops merely to see whether something changed.

## CAO-Owned Work

Handle these before asking the user:

- Clicking browser or desktop prompts when the action is clear and allowed.
- Checking whether a UI element exists, whether a local service is running, or whether a file/artifact was produced.
- Reviewing screenshots, PPTX/PDF/DOCX/HTML outputs, logs, test failures, diffs, and handoff notes.
- Choosing a routine next step from the user goal, project instructions, or Worker status.
- Answering routine yes/no questions where the safe answer follows from the task.
- Translating ambiguous Worker status into a concrete continuation, correction, or stop condition.
- Detecting drift from the user goal and sending a scoped correction.

## Deferred User Tasks

When the user gives work that cannot be sent immediately, keep it in a local-only pending queue or handoff note. Treat that queue as part of CAO's operational state.

Before any new Worker send:

1. Review relevant pending tasks.
2. Decide whether each task should interrupt the current work, wait for a safe boundary, be sent now, or require user judgment.
3. Ask the user only for decisions CAO cannot responsibly make.
4. Send only the highest-priority actionable instruction the Worker needs.
5. Mark the pending task as sent, superseded, blocked, or still waiting.

Interrupt active work only for blockers, active drift, important constraints, urgent user intent, or tasks that prevent wasted work. Otherwise preserve momentum and deliver pending tasks at the next safe boundary.

Keep pending-task content out of tracked public files when it contains private context, target identities, local paths, URLs, operational history, or one-off instructions.

## Escalation Gate

Ask the user only when CAO cannot responsibly decide or act. Escalate for:

- Product, UX, brand, or business preferences not inferable from prior context.
- Credentials, private account access, payment, security, or permission approvals.
- Public API, schema, destructive git, deployment, or cross-project ownership changes.
- Choices that may conflict with another active Worker.
- External facts or personal context that CAO cannot verify locally.

When escalating, state what CAO already checked, the concrete blocker, and the exact decision needed. Do not forward the Worker's raw uncertainty as-is.

## Worker Communication

Send Workers only the instruction they need. Do not include CAO meta discussion, supervisor-only context, memory notes, policy text, or raw user wording unless the user explicitly addressed that text to the Worker.

Worker replies should be short and operational:

```text
Proceed with option B. It matches the requested scope and avoids schema changes. After applying it, run the focused tests and report changed files plus any remaining blockers.
```

```text
Visual review found overlapping labels on slide 4 and low contrast in the right chart on slide 7. Fix those two issues only, regenerate the deck, and rerun the visual check.
```
