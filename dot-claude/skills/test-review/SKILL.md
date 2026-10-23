---
name: test-review
description: Use when the user wants the tests of recent work reviewed -- says "test-review", "/test-review", "review the tests", or "check for tests that cannot fail / untested changes / flaky tests / redundant tests". Proves whether tests can fail, finds changed code no test exercises, and reports ranked findings for triage; makes NO edits to the checkout. Do NOT use for line-level bug review (use /code-review), docs and comments (use /docs-review), or simplifying live code (use /simplify).
---

# Test review: find tests that do not pull their weight

A passing suite says nothing about whether it would catch a regression. Tests pile up that cannot
fail, cover the same behavior twice, break on every refactor, flake, or leave the code that just
changed unexercised. This skill reviews the tests of the current branch's work and **reports
findings for your triage -- it never edits your checkout.** Whatever it runs (mutations, coverage)
runs in a scratch copy.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) sets
the testing rules -- read it, and find the repo's test command there or in its README. The review
checklist lives in [references/rubric.md](references/rubric.md).

## Phase 1 -- Ground and scope

Read `README.md`, the repo's `CLAUDE.md`, and `git log --oneline -10`. Then list the branch's work:

- `git diff --name-only --merge-base main` -- committed since the branch left `main`;
- `git diff --name-only HEAD` -- uncommitted changes;
- `git ls-files --others --exclude-standard` -- new untracked files.

Split the union into **changed tests** and **changed production code**, and pair each with the
tests that exercise it (grep the test tree for the changed modules and symbols). When the user asks
for a full review, take every tracked file instead. If neither list has anything, say so and stop.

## Phase 2 -- Parallel review

Dispatch one subagent per concern below, in parallel. Hand each the two lists, the test command,
and the [rubric](references/rubric.md), and require it to return **only** a structured finding list
-- one `[SEVERITY] one-line finding -- file:line` per line, no prose, no preamble. Severity is
HIGH / MEDIUM / LOW.

A subagent that runs anything first copies the working tree -- tracked and untracked files, not
ignored ones (`git ls-files -co --exclude-standard`) -- into its own temporary directory and works
only there, so mutations, coverage data, and caches never touch the user's checkout.

1. **Can the tests fail** (`general-purpose`, runs code) -- for each changed test, and each test
   covering changed production code, prove it would catch a regression: if the repo configures a
   mutation tool (mutmut, Stryker, cargo-mutants, ...), run it scoped to the changed files;
   otherwise apply one minimal fault at a time to the code under test (invert a condition, return a
   constant, drop a call) and run the covering tests. A mutation every test survives is a finding.
2. **Gaps** (`general-purpose`, runs code) -- changed production code no test exercises, measured
   with the repo's coverage tool when one is configured and by tracing callers from the tests when
   not, and missing edge cases for logic that clearly has them.
3. **Test design** (`Explore`) -- redundant tests and duplicated setup, coupling to implementation
   detail, flakiness risks, and tests that assert on prompt prose.

## Phase 3 -- Aggregate and report

Merge the subagents' findings. Where two concerns flagged the same line, keep one finding at the
higher severity. Rank HIGH before MEDIUM before LOW, group by concern, and print one markdown
report -- each finding as `[SEVERITY] finding -- file:line`, naming for concern 1 the mutation the
tests survived. Delete the scratch copies. **Make no edits.**

Close by offering the follow-up the user chooses: open a fix session for the items they pick, or
file issues for them. Triage stays with the user.
