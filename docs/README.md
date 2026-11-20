# Managing a fleet of agents

These pages hold the principles behind my-claude: what managing a fleet of AI agents in software
development aims at, and how the repo goes about it. Each management function has a page that
says what in the repo carries it out and which gaps are known, so new work can be weighed against
the whole map rather than the last incident.

## The central principle

Optimize for business productivity, not agent productivity. The aim is not agent utilization,
parallelism, or output, but useful, verified outcomes per unit of total investment: time, money,
and the developer's attention, the scarcest of the three. Managing people spends much of its
effort getting them to work; agents work whenever asked. The effort moves to giving work the
right shape and bounds, and to verifying the outcome independently.

## What agents do well

- *On-demand workers*: as many as resources allow, started and stopped at will, including to try
  alternatives side by side.
- *Cheap work*: work and checks too costly to ask of people become affordable, such as mutation
  testing every change.
- *Speed and availability*: short cycles, and work at any hour.
- *One rulebook*: one configuration reaches every agent at once. A fix lands everywhere, and so
  does a mistake.
- *Full record*: every action is in a transcript, so work can be audited and measured afterward.
  No human worker leaves such a record.
- *Model choice*: a different model or tool can be picked for each task.

## Where agents need management

- *Misjudged own state*: an agent takes on what it cannot do, guesses requirements, declares
  completion early, and misses when to stop and ask.
- *Plausible but wrong*: confident output, findings included, that no run or source backs.
- *Thin or stale context*: an agent lacks the project's history and the developer's intent, and
  acts on instructions it loaded long ago or lost to compaction.
- *No learning from correction*: each session starts fresh; only the rulebook learns. A person
  corrected once stays corrected.
- *Work outruns attention*: work is so cheap that it grows -- follow-ups breeding follow-ups --
  until it fills the developer's attention. A human team rarely produces more work than its
  manager can read.
- *Non-determinism*: the same prompt gives different results from run to run.
- *Unaware of peers*: agents collide in a shared checkout, machine, or cloud resource.
- *Follows injected instructions*: an agent may act on instructions found in content it reads.

## Management functions

| Function | Guards against | Uses |
|---|---|---|
| [Set objectives and priorities](objectives.md) | work outruns attention, thin or stale context | |
| [Decompose and allocate work](allocation.md) | misjudged own state, unaware of peers | on-demand workers |
| [Match capabilities to tasks](capabilities.md) | misjudged own state | model choice |
| [Coordinate shared resources](coordination.md) | unaware of peers | on-demand workers, one rulebook |
| [Delegate authority](authority.md) | misjudged own state, thin or stale context, follows injected instructions | speed and availability |
| [Verify outcomes](verification.md) | plausible but wrong, non-determinism | cheap work |
| [Keep the work healthy](health.md) | thin or stale context | one rulebook, cheap work |
| [Report to steer](reporting.md) | work outruns attention, misjudged own state | |
| [Measure outcomes and cost](measurement.md) | work outruns attention, non-determinism | full record |
| [Learn from failures](learning.md) | no learning from correction, thin or stale context | one rulebook, full record |

Each page names the strengths and weaknesses above in *italics*, and tags its gaps *seen*, when a
failure showed the gap, or *unseen*, when none has yet.
