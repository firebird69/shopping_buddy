# Git Strategy

## Purpose

This document is the repo-owned source of truth for git routine and closeout policy. It defines how agents should inspect, stage, commit, and report repo changes for The Hardcore Bot.

Git itself remains the source of truth for commit history. Do not turn this file into a manual commit ledger. Task-specific commit evidence belongs in `STATUS.md` only when useful for pickup, or in a task report when one exists.

## Branch Model

- `master` is the current primary development branch for this MVP repo.
- Keep work on the current branch unless the user explicitly asks for a feature branch or remote workflow.
- This repo currently has no deployment/runtime branch split. If a runtime/deploy lane is added later, update this section before using it.

## Runtime Boundaries

- Primary workspace: `/workspace/projects/the-hardcore-bot`.
- Live Telegram mode requires `TELEGRAM_BOT_TOKEN` from the operator environment; never commit tokens or `.env` files.
- SQLite demo/runtime database files under `data/*.sqlite*` are ignored local artifacts.
- Real-source collection must stay low-volume and public-source only; no login flows, private API interception, WAF bypass, proxies, or high-frequency scraping.

## Commit Policy

- Use explicit staging only. Do not use broad `git add .` in this repo.
- Review `git status --short --branch` before staging.
- Stage only reviewed repo-owned paths needed for the current task.
- Keep unrelated local artifacts, caches, `.env`, databases, and credentials unstaged.
- Prefer coherent task commits over mixed checkpoint dumps.
- Commit messages should use concise conventional prefixes when useful:
  - `feat(scope): ...` for user-visible or product capability slices;
  - `fix(scope): ...` for bug fixes;
  - `docs(scope): ...` for documentation-only changes;
  - `test(scope): ...` for test-only changes;
  - `chore(scope): ...` for repo/tooling hygiene.
- For the initial baseline commit, `feat: scaffold grocery price alert MVP` is acceptable because it introduces the MVP scaffold.

## Push Policy

- Do not push unless the user explicitly approves pushing.
- If a remote is added later, inspect `git remote -v` and `git status --short --branch` before any push.
- Report the pushed ref and final status after any approved push.

## Validation Policy

Before committing code or behavior changes, run the narrowest relevant validation. Current baseline:

- `python3 -m pytest -q`
- JSON syntax checks for seed/mapping files when touched
- source mapping validation when mapping files are touched
- `git diff --check`
- `git diff --cached --check` after staging

If `python3 -m venv .venv` is unavailable on this host because `ensurepip` / `python3.10-venv` is missing, use the existing environment and record the blocker in `STATUS.md` rather than inventing a clean virtualenv.

## Task Closing Routine

At the end of every meaningful task:

1. Read/update `STATUS.md` so it reflects the current pickup state.
2. Run relevant validation after the final source/doc edit.
3. Inspect `git status --short --branch`.
4. Review the changed paths and stage explicitly by name.
5. Run `git diff --cached --stat` and `git diff --cached --check`.
6. Commit only after validation passes and commit approval is in scope.
7. Push only if the user explicitly approved pushing.
8. Final report should include:
   - files changed;
   - validation commands/results;
   - commit SHA/message if a commit was made;
   - whether push occurred;
   - final `git status --short --branch`.

## Report / Artifact Policy

- `STATUS.md` is the living pickup state, not a transcript or full changelog.
- Detailed plans belong under `docs/` and should be linked from `STATUS.md` when useful.
- Evidence archives should live under `reports/<topic>/INDEX.md` only when explicitly useful; do not create chronological reports by default.
- Do not duplicate git history into docs. Use `git log --oneline --decorate --graph` for history.

## Recovery / Rollback

Useful read-only recovery commands:

- `git status --short --branch`
- `git log --oneline --decorate --graph --all -20`
- `git diff --stat`
- `git diff -- <path>`
- `git show --stat <commit>`

Rollback or destructive commands such as `git reset --hard`, `git clean`, branch deletion, or history rewrites require explicit user approval and a clear statement of what will be lost.
