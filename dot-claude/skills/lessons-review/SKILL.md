---
name: lessons-review
description: Use when the user wants the agents' recurring mistakes turned into lessons -- says "lessons-review", "/lessons-review", "what keeps going wrong", "turn repeated mistakes into checks", or "why do agents keep doing X". Reads session transcripts, PR reviews, issues, and fix commits for kinds of mistake that recur, and proposes for each the check or rule that would stop it, preferring a check a program runs; makes NO edits. Do NOT use for a project's goals, names, or design (use /project-review) or for reviewing one change (use /code-review).
---

# Lessons review: stop the mistakes that keep coming back

A session fixes the mistake in front of it and the lesson ends there: the same kind of mistake
returns in a later session, costing another review round or another correction from the user.
This skill looks across sessions for kinds of mistake that recur, and for each proposes what would
stop it -- **reporting them, it makes no edits.** A check a program runs (a linter rule, a hook, a
test, a CI job) stops a mistake every time; a written rule only asks an agent to remember, so a
rule is the answer only where no program can judge.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) sets
the rules -- read it, since a recurring mistake that breaks a stated rule shows that rule failing.

## Phase 1 -- Scope

The default scope is the current repo, over the window the user names, else its last month of
work. Find the repo's session transcripts: Claude Code keeps one `.jsonl` per session under
`~/.claude/projects/`, in a directory named after the directory the session started in, with every
`/` and `.` turned into `-` -- so sessions started in the repo's worktrees have directories of their
own beginning with the same prefix -- and its subagents' transcripts in a `subagents/` directory
beside it. They exist only on the machine that ran the sessions; say when none are found.

## Phase 2 -- Parallel evidence

Dispatch two `general-purpose` subagents in parallel, handing each the scope and the repo's
`CLAUDE.md` files, and require each to return only its list of mistakes -- each with what went
wrong, where (transcript and timestamp, PR, commit, or issue), and what corrected it -- plus a
`NOT RUN: <what> -- <why>` line for anything it could not read:

1. **Sessions.** In the transcripts: the user's messages that correct the agent (a "no", a
   reverted change, a repeated instruction, a rule quoted back), tool calls a hook or the user
   denied, and work the agent redid after a failure it caused. Read the user's own text, not the
   tool output or system reminders around it. Quote only what the finding needs: transcripts are
   private.
2. **History.** On GitHub and in git: review findings a PR applied (the commits after its first,
   `gh pr view <n> --json commits,reviews,comments`), issues whose problem is how an agent behaved
   rather than a defect in the code, and fix commits that undo an agent's earlier change.

## Phase 3 -- Group and weigh

Group the mistakes into kinds -- the same wrong move, whatever file or session it hit. A kind is a
finding only when it **recurs**: in more than one session or PR. Weigh each by how often it
recurred, what each recurrence cost (a review round, a broken merge, the user's time), and whether
a stated rule already forbids it.

## Phase 4 -- Pick the remedy

For each kind, the first of these that fits:

1. **A check a program runs** -- for a mechanical mistake: a fixed pattern, a forbidden command
   or API, a file in the wrong place, a format. Name the cheapest place: a linter rule the repo
   already runs, a hook that blocks the tool call, a test, a CI job. A check that exists but did
   not run is the finding, not a new one.
2. **A script that makes the right way the only way** -- when the mistake is a step done by hand
   that a skill's script could do.
3. **A rule** -- only for a judgment no program can make. Say where it belongs: the global
   conventions when it holds in every repo, the repo's `CLAUDE.md` when only there, a skill when
   only in its workflow.
4. **A rule fixed or removed** -- when a stated rule already forbids the mistake and it recurs:
   say why the rule failed (buried, ambiguous, contradicted by another, or asking for what only a
   check can enforce) and whether rule 1 replaces it.

## Phase 5 -- Report

Rank the findings by cost, and print for each: the kind of mistake in a sentence, its recurrences
with their evidence, the remedy and where it goes, and the rule it replaces or fixes, if any.

If no kind of mistake recurs, say so plainly: **nothing recurs** is a full answer, with the window
and the sources read as its evidence.

Close by offering the follow-up the user chooses: file issues for the picked findings with
`/file-issue`. Triage stays with the user.
