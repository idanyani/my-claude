---
name: maintain
description: Use when the user wants a maintenance sweep of recent work for the debris fast development leaves behind -- says "maintain", "/maintain", "audit the repo", or "check for stale docs / duplication / dead code / test quality / convention drift". Reports ranked findings for triage and makes NO edits. Do NOT use for line-level bug review (use /code-review), security review (use /security-review), or simplifying live code (use /simplify).
---

# Maintain: sweep recent work for drift and debris

Fast, AI-accelerated cycles leave debris the main task misses: docs go stale, facts get duplicated
across docs and code, utilities get reinvented instead of reused, tests pile up without pulling
their weight, dead code accretes, and prose drifts from house conventions. This skill sweeps for
that debris and **reports findings for your triage -- it makes no edits.** Auto-rewriting "stale"
docs is how you get confidently wrong docs; the fix decision stays with you.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) is the
rubric -- read it. The audit checklist derived from those conventions lives in
[references/conventions-rubric.md](references/conventions-rubric.md). Helper scripts live in this
skill's `scripts/` directory, invoked as plain files: `python3 <skill-dir>/scripts/<name>.py`
(stdlib-only; they need `python3` and `git` on PATH and run against the current repo).

Scope stays deliberately narrow. Security, line-level correctness bugs, and over-engineering of live
code are owned by `/security-review`, `/code-review`, and `/simplify` -- do not re-audit them here;
duplicating a mature tool is the exact anti-pattern this skill exists to catch.

## Phase 1 -- Ground and scope

Read `README.md`, the repo's `CLAUDE.md`, and `git log --oneline -10` so findings account for fresh
changes. Then compute the file set:

- Default: `python3 <skill-dir>/scripts/changed_files.py` -- the current branch's work (changes
  since the merge-base with `main`, plus uncommitted and untracked files). This matches the pain:
  debris left *during* a cycle.
- Whole repo: pass `--all` when the user asks for a full sweep.

If the set is empty, say so and stop.

## Phase 2 -- Parallel audit

Dispatch one `Explore` subagent per concern below, in parallel. Hand each the file set and the
[conventions rubric](references/conventions-rubric.md), and require it to return **only** a
structured finding list -- one `[SEVERITY] one-line finding -- file:line` per line, no prose, no
preamble. Severity is HIGH / MEDIUM / LOW. Concerns:

1. **Doc freshness / drift** -- doc claims, commands, and API signatures that no longer match the
   code. Seed this agent with the deterministic broken-link findings from
   `python3 <skill-dir>/scripts/check_links.py` (feed it the markdown paths from Phase 1) so it
   spends judgment on stale prose, not path resolution.
2. **Duplication and reinvention** -- the same fact, logic, or comment stated in more than one
   place, and new code that reimplements an existing utility or pattern instead of reusing it.
3. **Test quality** -- overlapping coverage and duplicated setup, plus no-op or superficial tests,
   tests coupled to implementation detail, and missing edge cases. A test must fail if the code
   broke.
4. **Dead / orphaned code** -- unused functions and imports, commented-out blocks, and abandoned
   scaffolding. Git remembers; it should be deleted.
5. **Convention adherence (judgment)** -- journal comments, comments restating code, bare "see also"
   noise links, rotting hardcoded counts, AI-tic filler, and gendered Hebrew copy. The mechanical
   subset (non-ASCII glyphs, emojis in code/docs) is caught deterministically by the `check_prose`
   PostToolUse hook, so do not re-scan for it here.

## Phase 3 -- Aggregate and report

Merge the subagents' findings, dropping duplicates where two concerns flagged the same line. Rank
HIGH before MEDIUM before LOW, group by concern, and print one markdown report -- each finding as
`[SEVERITY] finding -- file:line`. **Make no edits.**

Close by offering the follow-up the user chooses: open a fix session for the items they pick, or
file issues for them. Triage stays with the user.
