---
name: maintain
description: Use when the user wants a maintenance sweep of recent work for the debris fast development leaves behind -- says "maintain", "/maintain", "audit the repo", or "check for stale docs / unbacked claims / docs shape / duplication / dead code / test quality / convention drift". Reports ranked findings for triage and makes NO edits. Do NOT use for line-level bug review (use /code-review), security review (use /security-review), or simplifying live code (use /simplify).
---

# Maintain: sweep recent work for drift and debris

Fast, AI-accelerated cycles leave debris the main task misses: docs go stale or claim what nothing
backs, facts get duplicated across docs and code until the docs outgrow the code, utilities get
reinvented instead of reused, tests pile up without pulling their weight, dead code and data
accrete, and prose drifts from house conventions. This skill sweeps for that debris and **reports
findings for your triage -- it makes no edits.** Auto-rewriting "stale" docs is how you get
confidently wrong docs; the fix decision stays with you.

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

Dispatch one subagent per concern below, in parallel -- `Explore` for concerns 1-5, which locate
line-level findings, and `general-purpose` for concern 6, which must read whole files to judge
spread, proportion, and reading order. Hand each the file set and the
[conventions rubric](references/conventions-rubric.md), and require it to return **only** a
structured finding list -- one `[SEVERITY] one-line finding -- file:line` per line (concern 6 may
anchor to a file or directory), no prose, no preamble. Severity is HIGH / MEDIUM / LOW. Concerns:

1. **Doc accuracy: freshness and backing** -- doc claims, commands, and API signatures that no
   longer match the code, including CI stages that no longer match the documented pipeline, and
   claims nothing in the code makes true: an unreflected priority, a bypassed guarantee, a fake
   "real" example, an incomplete rule list, a recipe that cannot run. Seed this agent with the
   deterministic broken-link findings from `python3 <skill-dir>/scripts/check_links.py` (feed it
   the markdown paths from Phase 1) so it spends judgment on stale prose, not path resolution.
2. **Duplication and reinvention** -- the same fact, logic, or comment stated in more than one
   place (CI steps and config values included), and new code that reimplements an existing utility
   or pattern instead of reusing it.
3. **Test quality** -- overlapping coverage and duplicated setup, plus no-op or superficial tests,
   tests coupled to implementation detail, and missing edge cases. A test must fail if the code
   broke.
4. **Dead / orphaned code** -- unused functions and imports, commented-out blocks, abandoned
   scaffolding, entry points (scripts, configs, CI jobs, hooks) that nothing invokes or that cannot
   work if invoked, data files nothing reads, and modes whose input the repo can no longer produce.
   Ask reachability outward -- who invokes or reads this? -- never whether the file it points to
   exists. Git remembers; it should be deleted.
5. **Convention adherence (judgment)** -- journal comments, docs prose defined against a design the
   reader never saw, comments restating code, bare "see also" noise links, rotting hardcoded
   counts, AI-tic filler, and gendered Hebrew copy. The mechanical subset (non-ASCII glyphs, emojis
   in code/docs) is caught deterministically by the `check_prose` PostToolUse hook, so do not
   re-scan for it here.
6. **Docs shape (whole set)** -- dispatched only when the file set includes a markdown doc, but
   then hand it every authored markdown doc in the repo (plus the module docstrings they
   describe), not just the changed files: facts stated in many places, pages restating module
   mechanism, a README that does not say what the project is, a broken reading order, docs out of
   proportion to the code, and link density as a coupling signal for the owner.

## Phase 3 -- Aggregate and report

Merge the subagents' findings. Where two concerns flagged the same line, keep one finding at the
higher severity. When concern 6 ran, fold concern 2's per-line duplicates of a fact into the
concern 6 finding that reports that fact's spread. Rank HIGH before MEDIUM before LOW, group by
concern, and print one markdown report -- each finding as `[SEVERITY] finding -- file:line` (or a
file or directory for whole-set findings). **Make no edits.**

Close by offering the follow-up the user chooses: open a fix session for the items they pick, or
file issues for them. Triage stays with the user.
