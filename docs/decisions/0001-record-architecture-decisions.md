# ADR 0001 — Record decisions, findings and experiments in the repository

- Date: 2026-09-16
- Status: accepted

## Context

The project runs over many sessions with an AI assistant. Context is lost
between sessions. Without written state, work repeats and facts about the
hardware get re-discovered or, worse, guessed.

## Decision

The repository holds all project memory:

- `state/STATUS.md` — the live state. Phase, next actions, open questions.
  Updated at the end of every session.
- `JOURNAL.md` — a short dated entry for every session.
- `docs/` — stable facts: hardware inventory, sensor catalogue, architecture.
- `docs/decisions/NNNN-<slug>.md` — one file for each decision, in this format.
- `lab/exp-NNNN-<slug>/` — one folder for each experiment, with a README that
  gives Question, Method and Result, plus the code and the raw results.

Every hardware fact in `docs/` gives the command that produced it.

## Consequences

- A new session can continue after it reads three files.
- The repository grows with documents as well as code. That is intended.
- There is a cost: each session must spend time on the update. Accepted.
