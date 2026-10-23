---
name: dead-code-review
description: Use when the user wants the repo swept for dead code and orphaned files -- says "dead-code-review", "/dead-code-review", "find dead code", or "check for unused functions / orphaned scripts / CI jobs or hooks nothing runs / data files nothing reads / dead modes". Asks of each candidate "does anything still call, invoke, or read this?" across the whole repo, not only the diff, and reports ranked findings for triage; makes NO edits. Do NOT use for line-level bug review (use /code-review), test quality (use /test-review), docs and comments (use /docs-review), or simplifying live code (use /simplify).
---

# Dead-code review: find what nothing calls, invokes, or reads

Linters see only what is imported, and coverage sees only what the tests ran, so debris survives
where neither looks: a function whose last caller is its own unit test, a script or CI job nothing
invokes, a data file only ever written, a mode whose input the repo can no longer produce, a target
orphaned when a change dropped its last reference. This skill asks of each candidate "does anything
still call, invoke, or read this?" across the whole repo and **reports findings for your triage --
it makes no edits.** Git remembers, so each finding is a deletion candidate; whether to delete stays
with you.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) sets
the rules -- read it. The review checklist lives in [references/rubric.md](references/rubric.md).

## Phase 1 -- Ground and scope

Read `README.md`, the repo's `CLAUDE.md`, and `git log --oneline -10`. Then `git fetch` and run
`git remote set-head origin --auto`, which records the remote default branch as `origin/HEAD` (a
clone may lack it). The candidates are, by default, the branch's work against it:

- the files in `git diff --name-only --merge-base origin/HEAD`, `git diff --name-only HEAD`, and
  `git ls-files --others --exclude-standard` -- what the branch added or changed;
- the **orphan targets** -- every symbol, script, config, or file a removed line in
  `git diff --merge-base origin/HEAD` and `git diff HEAD` referred to. They sit outside the diff,
  and the change may have dropped their last reference.

When the user asks for a full review, take every tracked file (`git ls-files`) instead: debris
older than the branch is found only this way. Whatever the scope, a candidate's invokers and
readers are searched for across the whole repo. If the candidate set is empty, say so and stop.

## Phase 2 -- Parallel review

Dispatch one `general-purpose` subagent per concern below, in parallel. Hand each the candidate set
and the [rubric](references/rubric.md), and require it to return **only** a finding list in the
rubric's format, no prose, no preamble.

1. **Dead code** -- unused functions, classes, modules, and constants, commented-out code,
   unreachable branches, and abandoned scaffolding. If the repo configures a dead-code tool (vulture,
   knip, deadcode, a compiler's unused-code warnings, ...), run it first and judge its hits, since
   such tools report false positives for code reached by reflection, registration, or a framework.
   A tool that writes caches or needs installing runs in a scratch copy of the repo (`cp -a`, `.git`
   included), never in the checkout.
2. **Dead entry points** -- scripts, configs, CI jobs, hooks, and package-manager scripts with no
   invoker but their own definition, and entry points that cannot work if invoked.
3. **Dead data and modes** -- data and config files nothing reads, and CLI modes, flags, or
   branches whose input the repo can no longer produce.

## Phase 3 -- Aggregate and report

Merge the subagents' findings. Where two concerns flagged the same target, keep one finding at the
higher severity. Rank by severity, group by concern, and print one markdown report in the rubric's
finding format. **Make no edits.**

Close by offering the follow-up the user chooses: open a fix session for the items they pick, or
file issues for them. Triage stays with the user.
