---
name: hindsight-review
description: Use when the user wants a repo's design judged in hindsight -- says "hindsight-review", "/hindsight-review", "would we build it this way today", "is there a simpler approach now", or "has a tool replaced our custom code". Reads the repo's history for lessons, searches for tools released since, designs the project afresh from its goals, and reports the few redesigns worth their cost -- or that the design holds; makes NO edits. Do NOT use for unreached code (use /dead-code-review), line-level bugs (use /code-review), or simplifying a diff (use /simplify).
---

# Hindsight review: would we choose this design today?

A design is chosen with what is known when it is chosen. Later, a simpler approach becomes visible
once the problem is understood, a tool or platform feature released since does what custom code
does, or a constraint a decision rested on stops holding. Most repos carry such legacy; few
designs are worth replacing. This skill finds the redesigns whose gain outweighs their cost, or
says the design holds, and **reports them -- it makes no edits.** The current code is the spec of
what a redesign must keep: it handles needs a fresh design forgets.

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) sets
the rules -- read it.

## Phase 1 -- Ground

1. **Goals.** Unless this session already settled the goals and non-goals with `/purpose-review`,
   run it first: a design is right only relative to what the project is for.
2. **Decision records.** Read them, as `CLAUDE.md` says; a finding that raises a rejected design
   again says why its reason no longer holds.
3. **Map the design:** the parts, what each is for, how data moves between them, and what the
   project builds itself versus takes off the shelf -- enough to brief the subagents.
4. **Design mismatches already flagged,** such as a concept a naming review found resisting one
   name: take them as leads for Phase 3.

## Phase 2 -- Parallel evidence

Dispatch three `general-purpose` subagents in parallel, handing each the goals -- and the design
map to the first two only -- and require each to return only its list, plus one
`NOT RUN: <what> -- <why>` line for anything it could not check. Every item of the first two cites
a file, commit, issue, PR, or URL; the fresh design cites the goal each choice serves:

1. **History.** Where the repo's own record shows the design straining: areas changed far more than
   their size explains (`git log --name-only`), the same kind of fix landing again in one area,
   reverts and retired features, alternatives PRs rejected and why, and decisions whose stated
   reason -- in a decision record, PR, or comment -- no longer holds.
2. **Landscape.** For each part the project builds itself, whether a library, tool, service, or
   platform feature now does it -- found by web search and the platform's current docs, citing
   when it appeared and how mature it is. Ask of each part whether it has become a product or a
   commodity since it was built: build what is new and particular to the project, take what has
   become standard.
3. **Fresh design.** From the goals and non-goals alone, without reading the implementation, how
   the project would be built today: its parts, data flow, and what it would take off the shelf.
   Not reading the code keeps the sketch free of the current design's assumptions.

## Phase 3 -- Compare

Set the fresh design beside the current one, and add what the history and landscape lists found.
Each real difference is a candidate, stating:

- **the change**, in a sentence, and the evidence that points to it;
- **what it must keep:** the behavior the current code handles that the fresh design missed --
  edge cases, fixes the history shows were needed, needs a consumer relies on. A candidate whose
  kept behavior swallows its gain is dropped;
- **the gain:** what gets simpler, what code and upkeep go away, what stops recurring;
- **the cost to undo:** code and docs are cheap; stored formats, public interfaces, and what other
  projects consume cost a migration -- unless a moment makes it cheap (stored data about to be
  reset, a major version). Name such a moment when one is near;
- **the path:** how to get there in steps that each leave the project working, rather than a
  rewrite.

## Phase 4 -- Report

Report only redesigns worth their cost -- **a finding changes the structure or the main tools**:
a part replaced, merged, split, or removed, or a data flow rebuilt. Local cleanups belong to
`/simplify`, `/code-review`, and `/dead-code-review`: name them in one line, not as findings.

Rank the candidates as **Strong** (the evidence is clear and the gain outweighs the cost now) or
**Worth exploring** (the payoff depends on where the project goes next); drop the rest. Then name
the **top recommendation** and why.

If no candidate clears the bar, say so plainly: **the design holds** is a full answer, with the
evidence that it holds -- the history shows no strain, nothing off the shelf does its custom parts
better, and the fresh design matches it.

Close by offering the follow-up the user chooses: file issues for the picked candidates with
`/file-issue`. When the user rejects a candidate for a reason that will still hold, offer a
decision record for it, through the same issue and PR flow.
