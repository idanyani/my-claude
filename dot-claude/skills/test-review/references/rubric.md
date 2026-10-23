# Test review rubric

The checklist a `test-review` applies, derived from the testing conventions in `~/.claude/CLAUDE.md`
plus whatever the target repo's own `CLAUDE.md` adds. This file names what to look for; the
conventions themselves live in those `CLAUDE.md` files -- read them for the authoritative wording,
and defer to the repo's `CLAUDE.md` where it is stricter.

Each concern below maps to one Phase 2 subagent. Report every hit as
`[SEVERITY] one-line finding -- file:line`, nothing else. Reserve HIGH for a test that gives false
confidence or a change with no test at all (a test that survives a mutation of the code it covers,
changed logic nothing exercises); MEDIUM for real debt (a flaky or implementation-coupled test, a
missing edge case, a test that breaks on rewording); LOW for redundancy and polish.

Test support code -- fixtures, factories, helpers, `conftest` files, test configs, and the CI job
that runs the suite -- is subject matter for every concern, not scenery.

## 1. Can the tests fail

- A mutation of the code under test that every covering test survives: the tests run the code but
  assert nothing that pins its behavior.
- A test with no meaningful assertion, a tautological one (asserting what it just set up), or one
  so mocked that it exercises only the mocks.
- An assertion that cannot be reached (inside a branch or loop the test never enters, or after a
  call that raises).

## 2. Gaps

- Changed production code that no test executes. Use the repo's coverage tool when it has one; a
  line coverage reports as run is still a gap if no assertion depends on its result.
- A missing edge case for logic that clearly has one: a boundary, an empty input, an error path, a
  second call, a concurrent caller.
- A bug fix with no test that reproduces the bug.

## 3. Test design

- Two tests covering the same behavior; duplicated setup that should be a fixture.
- A test coupled to implementation detail rather than behavior or contract: it asserts on private
  state, call counts of internals, or exact log text, so a refactor that keeps behavior breaks it.
- Flakiness risks: sleeps and timeouts standing in for synchronization, wall-clock time or the
  current date, real network or external services, random values without a fixed seed, dependence
  on test order, shared global or filesystem state that one test leaves for the next.
- A test that asserts on the prose of a prompt (a skill, `CLAUDE.md`, an agent definition) rather
  than on text a program consumes (script paths, frontmatter keys, tool rules): rewording breaks it
  without changing behavior.
