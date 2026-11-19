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
`~/.claude/projects/`, in a directory named after the directory the session started in, its
separators and punctuation turned into `-`. List `~/.claude/projects/` and take the directory of
the repo's main checkout and those of its worktrees (the same name, then `--claude-worktrees-`),
not a sibling repo whose name merely starts the same. A session's subagents' transcripts are in
`<session-id>/subagents/` beside its `.jsonl`. Transcripts exist only on the machine that ran the
sessions, and Claude Code deletes them after `cleanupPeriodDays` (30 by default): state the date
of the oldest one read, and say when the window reaches past it.

## Phase 2 -- Parallel evidence

Dispatch two `general-purpose` subagents in parallel, handing each the scope and the repo's
`CLAUDE.md` files, and require each to return only its list of mistakes -- each with what went
wrong, where (transcript and timestamp, PR, commit, or issue), and what corrected it -- plus a
`NOT RUN: <what> -- <why>` line for anything it could not read:

1. **Sessions.** Transcripts run to megabytes, mostly tool output, so filter them rather than read
   them whole. The user's own messages are the `"type":"user"` entries whose `message.content` is
   a string and that are not `isMeta`, minus the system reminders and command output inside them:
   find there the corrections (a "no", a reverted change, a repeated instruction, a rule quoted
   back). In the `tool_result` entries, find only the tool calls a hook or the user denied. And
   find work the agent redid after a failure it caused. Describe what was said; quote only the
   words a finding cannot do without, since transcripts are private.
2. **History.** On GitHub and in git: review findings a PR applied -- its review bodies and
   comments (`gh pr view <n> --json commits,reviews,comments`), its inline review comments
   (`gh api repos/<owner>/<repo>/pulls/<n>/comments`), and the later commits whose message or
   review says they fix one, not every later commit -- issues whose problem is how an agent
   behaved rather than a defect in the code, read with their bodies and comments
   (`gh issue list --state all --limit 1000 --json number,title,body,stateReason,comments`), and
   fix commits that undo an agent's earlier change.

## Phase 3 -- Group and weigh

First merge the two lists' reports of one incident -- a session and the PR it pushed to -- into
one. Then group the incidents into kinds: the same wrong move, whatever file or session it hit. A
kind is a finding only when it **recurs**: in more than one incident. Weigh each by how often it
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
3. **A stated rule fixed or removed** -- when a rule already forbids the mistake and it recurs:
   say why the rule failed -- buried, ambiguous, contradicted by another, or placed where it is
   not read when the mistake is made -- and what fixes it.
4. **A new rule** -- for a judgment no program can make and no rule covers. Say where it belongs:
   the global conventions when it holds in every repo, the repo's `CLAUDE.md` when only there, a
   skill when only in its workflow.

## Phase 5 -- Report

Rank the findings by cost, and print for each: the kind of mistake in a sentence, its recurrences
with their evidence, the remedy and where it goes, and the rule it replaces or fixes, if any.

If no kind of mistake recurs, say so plainly: **nothing recurs** is a full answer, with the window
and the sources read as its evidence.

Close by offering the follow-up the user chooses: file issues for the picked findings with
`/file-issue`, describing each recurrence without quoting the transcripts. Triage stays with the
user.
