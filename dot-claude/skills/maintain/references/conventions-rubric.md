# Maintenance audit rubric

The checklist a `maintain` sweep applies, derived from the global conventions in `~/.claude/CLAUDE.md`
plus whatever the target repo's own `CLAUDE.md` adds. This file names what to look for; the
conventions themselves live in those `CLAUDE.md` files -- read them for the authoritative wording,
and defer to the repo's `CLAUDE.md` where it is stricter.

Each concern below maps to one Phase 2 subagent. Report every hit as
`[SEVERITY] one-line finding -- file:line`, nothing else. Reserve HIGH for things that mislead a
reader or break a contract (a wrong doc, a broken link, a test that cannot fail); MEDIUM for real
debt (duplication, dead code, a superficial test); LOW for style and polish.

Auxiliary machinery -- package-manager scripts, build and test configs, CI workflows and composite
actions, shell scripts, Dockerfiles, git hooks -- is subject matter for every concern, not scenery.
Nothing imports it, so no resolver, type checker, or linter will ever flag it; debris survives
there longest.

## 1. Doc freshness / drift

- A doc states a command, flag, path, signature, or count that the current code no longer matches.
- A doc describes behavior that was changed or removed.
- A CI workflow whose stages no longer match the pipeline the docs describe.
- A broken intra-repo link (the `check_links.py` findings are pre-computed -- fold them in as HIGH).
- A hardcoded number in prose that has since rotted (see also concern 5).

## 2. Duplication and reinvention

- The same fact or constant defined in more than one place instead of defined once and referenced.
- Copy-pasted logic or blocks that should be extracted.
- A copied comment -- the information belongs in a doc or a named constant, not repeated.
- New code that reimplements a helper, pattern, or off-the-shelf solution that already exists in the
  repo. Prefer reuse; a hand-rolled version of something standard is a finding.
- Duplicated CI steps, test tiers or jobs whose scope overlaps, and config values restated across
  config files.

## 3. Test quality

- Two tests covering the same behavior; duplicated setup that should be a fixture.
- A test that cannot fail if the code broke (no meaningful assertion, tautological, over-mocked).
- A test coupled to implementation detail rather than behavior or contract.
- A missing edge case for logic that clearly has one (boundary, empty, error path).

## 4. Dead / orphaned code

- Unused functions, classes, imports, or variables.
- Commented-out code left in place -- git remembers; it should be deleted.
- Abandoned scaffolding: a `TODO`/placeholder never wired up, an unreachable branch, a flag nothing
  reads.
- An entry point nothing invokes: a script, config, CI job, or hook with no caller but its own
  definition. Check reachability outward -- "does anything invoke this?", not "does the file it
  points to exist?". Search `.github/`, sibling scripts, the package manifest, harness and tool
  configs (`settings.json`, `.pre-commit-config.yaml`), and docs, and run `git log -S"<name>"` to
  learn whether it was ever wired up at all. An event or naming convention is an invoker too: a
  workflow's `on:` triggers, a hook file in the hooks path. With no invoker of either kind, it is a
  deletion candidate, not something to maintain.
- An entry point orphaned by the change set: when a changed file drops its reference to a script or
  config, check that target's remaining invokers too, even though the target itself is outside the
  file set.
- An entry point that cannot work if invoked: one that skips setup its siblings perform (starting a
  container, building first, loading credentials) is dead in practice even where it is referenced.

## 5. Convention adherence (judgment)

The mechanical prose checks (non-ASCII glyphs, emojis in code/docs) are handled deterministically by
the `check_prose` PostToolUse hook -- do NOT re-scan for them. This concern covers only what needs
judgment:

- Journal comments that narrate change history (that belongs in commit messages).
- Comments that restate what the code plainly says, rather than explaining a non-obvious *why*.
- A bare "see also" cross-reference that loses no fact if removed (noise, not a required link).
- A hardcoded count that will rot, where a structural description would not.
- AI-tic filler ("delve", "load-bearing", "testament") in prose.
- Gendered Hebrew copy where a gender-neutral phrasing (noun, infinitive, passive) would serve.
