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

## Known gaps

- *Seen:* nothing measures outcomes per unit of the developer's attention.
- *Seen:* the developer's answers to agents' questions exist only in session transcripts, which
  stay on one machine and expire; this repo is public, so the measures need a private, durable
  place of their own.
