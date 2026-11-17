---
name: purpose-review
description: Use when the user wants to settle what a repo is for now -- says "purpose-review", "/purpose-review", "what is this project for", "have our goals changed", "check the README states the goals", or "surface implicit assumptions / non-goals". Infers goals and non-goals from the docs, code, and history, has the user confirm them, then checks the docs, code, and tests against them -- goals unstated, unmet, or unguarded, and parts that serve no goal; makes NO edits. Do NOT use for code nothing reaches (use /dead-code-review), stale doc claims (use /docs-review), or what a change's tests miss (use /test-review).
---

# Purpose review: settle what the project is for, now

A project's goals change over its lifetime; that is normal. What hurts is when the docs still state
the original goals, or never stated any: every design call is then made against a goal no one can
check, and a part built for a goal since dropped keeps running and costing upkeep. This skill
infers the goals **and non-goals** from what the repo shows, **has the user settle them**, and
reports where the repo disagrees -- **it makes no edits.** Code and history record what was built,
not what was meant, so an inferred goal is a hypothesis until the user confirms it.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) sets
the rules -- read it.

## Phase 1 -- Gather

Read, citing each source by path, commit, issue, or PR:

- **Stated purpose now:** `README.md`, the repo's `CLAUDE.md`, and the docs they link.
- **Stated purpose then:** the first README and the early commits
  (the first lines of `git log --reverse --format='%h %ad %s' --date=short`, then
  `git show <sha>:README.md`), and how the README's opening changed
  (`git log --format='%h %ad %s' --date=short -- README.md`).
- **What the work went into:** issue and PR titles over time, the earliest as well as the latest
  (`gh issue list --state all --limit 100 --json number,title,createdAt`, once more with
  `--search sort:created-asc`, likewise `gh pr list`), and where commits landed
  (`git log --since=<a recent window> --name-only --format=` counted by top-level directory).
- **What the project serves:** its entry points, outputs, and consumers as the code shows them;
  run results and consumer repos when the user points to them.
- **What guards it:** the behaviors the repo's checks pin -- its tests, and also eval cases, CI
  jobs, hooks, and type checks -- grouped by the part of the project they exercise. Dispatch one
  `general-purpose` subagent to map them from the checks' names and what they assert, and to
  return only that map, so the main session keeps its context for the user's questions.

## Phase 2 -- Infer

From that evidence, state as hypotheses, each with its citations:

- **Goals:** what the project must achieve, and for whom.
- **Non-goals:** what it deliberately does not do. They are rarely written down, so infer them
  from what was declined or removed, and from scope the code stops short of. Without them no part
  can be judged unneeded.
- **Implicit assumptions:** conditions the design relies on but nothing states -- the scale, the
  users, the environment, a consumer's needs.
- **Contradictions:** where the stated purpose and the work disagree -- a goal the docs state that
  no recent work serves, work no stated goal explains, a non-goal the code now does.
- **Drift:** where the purpose then and the purpose now differ, and whether the docs say so.

History shows where effort went, not whether its result still stands: check each inference against
the current code before stating it.

## Phase 3 -- Settle with the user

Present the hypotheses and ask the user to confirm, correct, or complete them (AskUserQuestion:
one question per goal or assumption in doubt, the inferred answer first). The user's answers are
the purpose -- a free-text answer as written, not the nearest option; where they contradict the
evidence, they win, and the contradiction becomes a finding. **Do not report before the user has
settled the goals.**

## Phase 4 -- Report

Report only what changes how the project is understood or what it keeps -- **a finding that
changes the goals, removes a part, or adds the code or check a goal lacks**. Stale claims, broken
links, unreachable code, and a change's untested lines belong to `/docs-review`,
`/dead-code-review`, and `/test-review`: name them in one line, not as findings. Print:

1. **Purpose:** the settled goals and non-goals, a few lines each, ready to go into the README.
2. **Docs gap:** whether `README.md` states that purpose -- missing, stated vaguely, or stating an
   old one -- citing the lines.
3. **Goals unmet or unguarded:** a goal no code serves -- the contradictions Phase 2 found among
   them -- and a goal the code serves but no check guards, so a change could break it unnoticed,
   each citing what was searched. Name the kind of check that fits the goal; one the repo's
   conventions forbid, such as matching a prompt's prose, does not fit.
4. **Parts that serve no goal:** features, modes, options, or components that still run but serve
   no settled goal, or serve a non-goal -- each with what it costs to keep (code, tests, CI time,
   dependencies) and what removing it would break. These are not dead code: something still
   reaches them. Tests that pin a non-goal belong here too: they hold in place what the project
   no longer wants.

If the docs state the settled purpose, every goal is served and guarded, and every part serves
a goal, say so plainly: **the purpose is clear and current** is a full answer.

Close by offering the follow-up the user chooses: file issues for the picked findings with
`/file-issue`. Triage stays with the user.
