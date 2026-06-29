---
name: public-repo-hygiene
description: Prevent private, identifying, or narrative context from entering public or potentially public git repositories. Use before editing, adding, committing, or documenting tracked files in a public repo; when the user says a repo is public; when changes mention company, client, project, worker/session, account, workspace, incident, local path, URL, or operational history; or when durable rules should live in a user-global skill or local exclude instead of the repository.
---

# Public Repo Hygiene

## Core Rule

Treat public or potentially public repositories as productized code artifacts, not private operating logs. Do not add content that reveals private identities, target names, internal companies, customer context, worker/session names, local environment details, or the story of why a rule was created.

## Pre-Edit Check

Before writing to a git-tracked file:

1. Check whether the file is tracked or intended to be tracked:

   ```bash
   git ls-files -- <path>
   git status --short -- <path>
   ```

2. If the repository is public, or visibility is unknown, assume public.

3. Keep tracked content generic. Prefer reusable behavior rules over task-specific explanations.

4. Put user-specific or target-specific durable rules in a user-global skill, local untracked notes, or `.git/info/exclude`, not in the public repo.

## Disallowed In Tracked Public Files

Do not add:

- Company, customer, client, workspace, organization, repository, project, worker, session, account, device, host, or person names that are not already part of the public product.
- Narrative history that records request history, prior runs, monitored target identity, incident context, or task-specific origin.
- Local absolute paths, private URLs, workspace URLs, tokens, OAuth codes, cookies, invite links, screenshots, logs, terminal transcripts, or generated status reports.
- One-off operational helpers whose names reveal private targets.
- Rules that only make sense for one private task, client, company, worker, or environment.

## Safe Patterns

Use neutral wording:

- "When a monitored worker reaches a clear next phase..."
- "When a saved direction artifact exists..."
- "Use a local watcher for scheduled supervision..."
- "Escalate for credentials, permissions, destructive actions, or conflicting direction..."

Avoid even anonymized prose if it still reveals the workflow context. If the rule is not broadly reusable, do not put it in the public repo.

## Local-Only Handling

For target-specific files:

- Prefer `.git/info/exclude` for local ignore patterns that should not affect the public repo.
- Prefer `$CODEX_HOME/skills` or `~/.codex/skills` for user-global operating rules.
- Prefer untracked local notes for private runbooks or status handoffs.

Do not edit user-level Codex config unless the user explicitly requests that exact change.

## Verification

Before finalizing:

1. Scan tracked diffs and staged files:

   ```bash
   git diff --stat
   git diff --check
   git diff
   git status --short
   ```

2. Search for likely private identifiers in tracked diffs and file lists. Use task-specific terms from the conversation, but do not write those terms into repo files.

3. If a public tracked file needs a rule, rewrite it as a generic principle. If it cannot be made generic without losing meaning, keep it out of the repository.
