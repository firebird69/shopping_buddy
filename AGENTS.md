# The Hardcore Bot — Agent Instructions

> **MANDATORY:** Read `STATUS.md` at the start of every session. Update `STATUS.md` after every meaningful step.

## Project Overview

The Hardcore Bot is a Telegram-native Kyiv grocery price alert MVP. It tracks a curated set of grocery SKUs, stores price observations in SQLite, and alerts users when a meaningful drop, threshold hit, or best observed price appears.

## Critical Policies

### 1. Keep `STATUS.md` Current

`STATUS.md` is the living pickup point for this repo. Update it whenever project state, validation evidence, blockers, or the next unblocked action changes.

### 2. Validate Source Work Before Product Promises

The risky part is grocery source reliability. Do not promise broad real-time scraping until low-volume public-source spikes prove stable, legal, and maintainable. Avoid login flows, private API interception, WAF bypass, proxies, and high-frequency scraping.

### 3. No Secrets in Repo

Do not read, print, or commit `.env`, Telegram tokens, cookies, session files, or credentials. Live Telegram mode requires `TELEGRAM_BOT_TOKEN` from the operator environment.

### 4. Low-Volume Collection Only

Initial real-source collectors should run at low cadence, around 2–4 fetches/day, against a small curated SKU set. Persist source URL, retailer/store/filial context, fetch time, availability, and promo validity whenever available.

### 5. Git and Deployment Discipline

Do not commit, push, deploy, or schedule live collection unless explicitly asked. This repo currently has no commits; inspect `git status --short --branch` before closeout.

## Environment

- Primary workspace: `/workspace/projects/the-hardcore-bot`
- Python package: `the-hardcore-bot`, Python `>=3.10`
- Main validation: create/use `.venv`, install `.[dev]`, then run `python -m pytest -q`
- SQLite demo DB path: `data/hardcore.sqlite3` (ignored)

## Key Files

| File | Purpose |
|---|---|
| `STATUS.md` | Living project state — read first, update often |
| `README.md` | Product overview, quick start, commands |
| `docs/next-week-work-plan.md` | Current one-week execution plan |
| `docs/source-feasibility.md` | Source feasibility conclusions and spike evidence |
| `scripts/source_spike.py` | Low-volume public source spike runner |
| `hardcore_bot/` | Bot package: storage, alert rules, formatting, CLI, Telegram entrypoint |
| `tests/` | Unit tests for storage, formatting, and alerts |
