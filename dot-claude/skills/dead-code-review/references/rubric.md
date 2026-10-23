# Dead-code review rubric

The checklist a `dead-code-review` applies, derived from the conventions in `~/.claude/CLAUDE.md`
plus whatever the target repo's own `CLAUDE.md` adds. This file names what to look for; the
conventions themselves live in those `CLAUDE.md` files -- read them for the authoritative wording,
and defer to the repo's `CLAUDE.md` where it is stricter.

Each concern below maps to one Phase 2 subagent. Report every hit as
`[SEVERITY] one-line finding -- file:line`, nothing else, naming in the finding where you searched
for an invoker or reader. Reserve HIGH for something that misleads a reader or a caller (an entry
point that cannot work if invoked, a documented mode whose input nothing produces); MEDIUM for
debris that is plainly dead (no invoker or reader anywhere); LOW for a candidate only the owner can
judge (reached only through reflection, a public API, or a consumer outside the repo).

Ask reachability outward -- "who calls, invokes, or reads this?" -- never whether the file it
points to exists. Search code, tests, `.github/`, sibling scripts, the package manifest, harness and
tool configs (`settings.json`, `.pre-commit-config.yaml`, ...), and docs. Run `git log -S"<name>"`
to learn whether a candidate was ever wired up, and when its last reference was dropped. An event
or naming convention is an invoker too: a workflow's `on:` triggers, a hook file in the hooks path,
a test-discovery pattern, a plugin entry point. A caller that is only the candidate's own test, its
own definition, or a doc that describes it does not keep it alive.

Auxiliary machinery -- package-manager scripts, build and test configs, CI workflows and composite
actions, shell scripts, Dockerfiles, git hooks -- is subject matter for every concern, not scenery.
Nothing imports it, so no resolver, type checker, or linter flags it; debris survives there longest.

## 1. Dead code

- An unused function, class, method, module, or constant: no caller in product code. One whose only
  callers are its own tests is dead, and so are those tests.
- Commented-out code left in place.
- An unreachable branch: a condition no caller can satisfy, code after an unconditional return or
  raise.
- Abandoned scaffolding: a placeholder, stub, or `TODO` never wired up; a parameter or flag nothing
  reads.
- Code orphaned by the change: an orphan target whose last reference the change removed.

## 2. Dead entry points

- A script, config, CI job, or hook with no invoker but its own definition.
- An entry point orphaned by the change: an orphan target the change stopped invoking. Check its
  remaining invokers, though it sits outside the diff.
- An entry point that cannot work if invoked: one that skips setup its siblings perform (starting a
  container, building first, loading credentials), or names a command, path, or flag that no longer
  exists. It is dead in practice even where it is referenced.

## 3. Dead data and modes

- A data or config file nothing reads. Being written, validated against a schema, or hand-maintained
  is not being read: ask "who reads this?" and search for a consumer.
- A config key or field nothing reads, though the file itself is read.
- A dead mode: a CLI mode, flag, or branch whose input -- a state, file layout, or format -- the repo
  can no longer produce. Check that something still creates its input, not only that something
  calls it.
