---
name: project-review
description: Use when the user wants a repo reviewed from a bird's eye view and its next major steps planned -- says "project-review", "/project-review", "zoom out", "review the whole project", "what should we change if we started over", or "plan the next big refactor". Settles the project's purpose with the user, then reviews its names and its design in hindsight, and returns one ordered plan of the changes it needs -- or says the project is good as it stands; makes NO edits. Do NOT use for one aspect alone (use /purpose-review, /naming-review, or /hindsight-review) or for reviewing a diff (use /code-review).
---

# Project review: settle the purpose, then plan the large changes

A repo's largest gains sit where its goals, its names, and its design no longer fit what the project
has become. Each question depends on the one before: a name fits a concept, and a design fits a
goal, only once the goals are settled; and a rename is wasted on a part a redesign removes. This
skill answers them in order and turns the findings into one ordered plan -- **the review makes no
edits.** Each of the three reviews it runs holds its report for the plan, skipping its own closing
follow-up offer: the plan makes one offer for all of them.

It reports changes to the goals, the core names, and the structure -- however costly, since they
are the technical debt it exists to clear -- never the minor issues the other reviews cover, and
**"the project is good as it stands" is a full answer.** Knowing when to leave a repo alone is part
of the review.

## Phase 1 -- Purpose

Run `/purpose-review` with the Skill tool, in this session: its questions need the user. **Stop
until the user has settled the goals and non-goals**; every later phase judges against them.

## Phase 2 -- Names, then design

Run `/naming-review`, then `/hindsight-review`, with the Skill tool, in this session -- each
against the goals Phase 1 settled, and each dispatching its own subagents. In that order, the
concepts naming found resisting one name reach the design review as leads.

## Phase 3 -- Plan

Merge the three reports into one plan:

1. **Drop and merge.** Remove a rename of a part a redesign removes or rebuilds; fold it into that
   redesign. Merge findings that are one change seen from two reviews -- a part serving no goal
   that the design review would also remove, a name that resists fitting and the design mismatch
   behind it.
2. **Order** by what each change makes easier or wasted:
   - stating the purpose in the docs comes first: every later change is argued from it;
   - removals next: they shrink what the rest must touch;
   - renames before the redesigns that keep the renamed concepts, so new code is written in the
     right words;
   - a change whose cost drops at a coming moment (a data reset, a major version) is placed at it.
3. For each step: what changes, the finding it comes from, its cost and how to pay it, and what it
   unblocks.

## Phase 4 -- Report

Print the purpose settled in Phase 1, then the plan, then one line each for the smaller issues the
reviews routed to other skills. Report in chat; when it is long or needs diagrams, publish it as a
private artifact and give the link.

If no review found a change, say so plainly, with each review's evidence that its
part holds.

Close by asking which steps to take. File each picked step with `/file-issue`; once the user asks
for them to be resolved, resolve them with `/resolve-issue` in the plan's order. Collect the
candidates the user rejects for a reason that will still hold, and offer their decision records as
one issue and PR.
