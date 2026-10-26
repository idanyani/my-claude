---
name: docs-review
description: Use when the user wants the repo's docs and comments reviewed -- says "docs-review", "/docs-review", "review the docs", or "check for stale docs / unbacked claims / broken links / docs shape / journal comments / prose drift". Reports ranked findings for triage and makes NO edits. Do NOT use for line-level bug review (use /code-review), test quality (use /test-review), or simplifying live code (use /simplify).
allowed-tools:
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/changed_files.py *)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/check_links.py *)
---

# Docs review: find docs and comments that mislead or drift

Docs rot faster than code: nothing fails when a claim goes stale, a fact gets restated on a second
page, or a comment narrates a change instead of explaining the code. This skill reviews the repo's
prose -- markdown docs, docstrings, and code comments -- and **reports findings for your triage --
it makes no edits.** Auto-rewriting "stale" docs is how you get confidently wrong docs; the fix
decision stays with you.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) is the
rubric -- read it. The review checklist derived from those conventions lives in
[references/rubric.md](references/rubric.md). Helper scripts live in this skill's `scripts/`
directory, invoked as plain files: `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py` (stdlib-only; they
need `python3` and `git` on PATH and run against the current repo).

## Phase 1 -- Ground and scope

Read `README.md`, the repo's `CLAUDE.md`, and `git log --oneline -10` so findings account for fresh
changes. Then compute the file set:

- Default: `python3 ${CLAUDE_SKILL_DIR}/scripts/changed_files.py` -- the current branch's work (changes
  since the merge-base with the remote default branch, plus uncommitted and untracked files).
- Whole repo: pass `--all` when the user asks for a full review.

If the set is empty, say so and stop.

## Phase 2 -- Parallel review

Dispatch one subagent per concern below, in parallel -- `Explore` for concerns 1 and 2, which locate
line-level findings, and `general-purpose` for concern 3, which must read whole files to judge
spread, proportion, and reading order. Hand each the file set and the
[rubric](references/rubric.md), and require it to return **only** a finding list in the rubric's
format, no prose, no preamble. Concerns:

1. **Doc accuracy: freshness and backing** -- doc claims, commands, and API signatures that no
   longer match the code, and claims nothing in the code makes true. Seed this agent with the
   deterministic broken-link findings from `python3 ${CLAUDE_SKILL_DIR}/scripts/check_links.py` (feed it
   the markdown paths from Phase 1) so it spends judgment on stale prose, not path resolution.
   Also hand it any file the script names on stderr as skipped unreadable: its links went unchecked.
2. **Prose conventions (judgment)** -- in docs, docstrings, and comments: journal comments, prose
   defined against a design the reader never saw, coined vocabulary, comments restating code or
   copied between places, references the text does not need, rotting counts, and AI-tic filler. The mechanical
   subset (non-ASCII glyphs, emojis in code/docs) is caught deterministically by the `check_prose`
   PostToolUse hook, so do not re-scan for it here.
3. **Docs shape (whole set)** -- dispatched only when the file set includes a markdown doc, but
   then hand it every authored markdown doc in the repo (plus the module docstrings they
   describe), not just the changed files: facts stated in many places, pages restating module
   mechanism, a README that does not say what the project is, a broken reading order, docs out of
   proportion to the code, and link density as a coupling signal for the owner.

## Phase 3 -- Aggregate and report

Merge the subagents' findings. Where two concerns flagged the same line, keep one finding at the
higher severity. When concern 3 ran, fold concern 2's copied-comment findings about a fact into the
concern 3 finding that reports that fact's spread. Rank by severity, group by concern, and print one
markdown report in the rubric's finding format. **Make no edits.**

Close by offering the follow-up the user chooses: open a fix session for the items they pick, or
file issues for them. Triage stays with the user.
