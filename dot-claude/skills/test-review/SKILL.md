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

Read `README.md`, the repo's `CLAUDE.md`, and `git log --oneline -10`. Then `git fetch` and run
`git remote set-head origin --auto`, which records the remote default branch as `origin/HEAD` (a
clone may lack it). List the branch's work against it, not a local `main` that may be stale or
absent:

- `git diff --name-only --merge-base origin/HEAD` -- committed since the branch left it;
- `git diff --name-only HEAD` -- uncommitted changes;
- `git ls-files --others --exclude-standard` -- new untracked files.

Sort the union into **changed tests** (test files and their support code), **changed production
code** (source the tests exercise), and everything else -- docs, prompts, configs, lockfiles,
generated or vendored files -- which is out of scope. Pair each changed production file with the
tests that exercise it (grep the test tree for the changed modules and symbols). When the user asks
for a full review, take every tracked file instead. If the first two lists are empty, say so and
stop.

## Phase 2 -- Parallel review

Dispatch one `general-purpose` subagent per concern below, in parallel -- each must read whole test
files, and the first two run code. Hand each the two lists, the test command, and the
[rubric](references/rubric.md), and require it to return **only** a finding list in the rubric's
format, no prose, no preamble.

A subagent that runs anything first copies the whole repo directory -- ignored files and `.git`
included (`cp -a`), so installed dependencies and git-aware tools work -- into its own temporary
directory and works only there, so mutations, coverage data, and caches never touch the user's
checkout. If the test tools fail to start in the copy, it runs the repo's dependency-install step
there first. Each runner keeps its own copy: a mutation in a shared one would corrupt the other's
coverage run.

1. **Can the tests fail** (runs code) -- for each changed test, and each test
   covering changed production code, prove it would catch a regression: if the repo configures a
   mutation tool (mutmut, Stryker, cargo-mutants, ...), run it scoped to the changed files;
   otherwise apply one minimal fault at a time to the code under test (invert a condition, return a
   constant, drop a call) and run the covering tests. A mutation every test survives is a finding.
2. **Gaps** (runs code) -- changed production code no test exercises, measured
   with the repo's coverage tool when one is configured and by tracing callers from the tests when
   not, and missing edge cases for logic that clearly has them.
3. **Test design** -- redundant tests and duplicated setup, coupling to implementation
   detail, flakiness risks, and tests that assert on prompt prose.

## Phase 3 -- Aggregate and report

Merge the subagents' findings. Where two concerns flagged the same line, keep one finding at the
higher severity. Rank by severity, group by concern, and print one markdown report in the rubric's
finding format, naming for concern 1 the mutation the tests survived. Delete the scratch copies. **Make no edits.**

Close by offering the follow-up the user chooses: open a fix session for the items they pick, or
file issues for them. Triage stays with the user.
