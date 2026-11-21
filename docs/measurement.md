# Measure outcomes and cost

Terms in *italics* are defined in [the index](README.md).

A rule tuned only to the last failure cannot tell whether it helped. The central principle names
what to measure: outcomes the developer wanted, landed and still standing, per unit of what they
cost -- the developer's attention above all. Fewer questions is not progress if the agents now
decide what the developer should have, so a measure of progress is paired with measures of what it
could hide: decisions the developer later reversed, and work reverted or reopened. Agents leave a
*full record*, so the measures can be computed from it rather than recalled.

## In my-claude

- [file-issue](../dot-claude/skills/file-issue/SKILL.md) labels each issue with where its work
  came from, and the [require_issue_origin](../dot-claude/hooks/require_issue_origin.py) hook
  refuses an issue filed any other way.
- [fleet_metrics.py](../dot-claude/bin/fleet_metrics.py) saves the developer's turns from each
  machine's transcripts into a private repo before they expire, and reports, per week, the issues
  the developer brought that landed and stood, per turn, beside reopenings and reverts. Each
  machine's environment runs its collection daily.

## Known gaps

- *Unseen:* the measures count turns, not their kind: a correction weighs the same as an answer
  to a question, and decisions the developer later reversed are not counted.
