# Working conventions

## Issues, pull requests, and commits

- Every change meant to land on `main` follows the resolve-issue skill's steps, through the
  merge and local cleanup, even when the session did not start from an issue: first open an
  issue that records the problem the session raised, then resolve it. So every PR links the
  issue it resolves.
- An issue states one problem: symptom, impact, evidence -- never the fix. Two problems are
  two issues, each resolved by its own PR.
- A PR states the chosen solution and the alternatives considered, each with why it was
  rejected. It links the problem with `Resolves #N` instead of restating it.
- A commit message describes what the commit does to the repository's persistent state,
  never the session: no "as discussed", no naming uncommitted scratch files.

## Problem-solving

- Question the framing before solving: a bug in one layer is often a symptom a layer
  down.
- The best solution often eliminates the problem rather than solving it; root cause over
  symptoms.
- Prefer standard, off-the-shelf solutions over clever custom code; if a solution feels
  hacky, it probably is.
- Delete dead code -- git remembers.
- Automate everything: manual inspection sessions are a code smell.
- Never leave loose ends: no speculation -- investigate until known or explicitly mark
  unknown.
- Answer what you can before asking: search the code, the repo's docs and the web first.
  Ask the user only what that leaves open -- a decision that is theirs, a fact no source
  settles, or a search you have no tool for -- and say what you searched. Never put private
  data in a search query (a private person's details, a confidential deal); ask instead.
- An empty result is a reason to try another route, not evidence of absence. Call a fact
  unsettled only after the routes a diligent person in that field would take.
- Apply rules with judgment: their wording does not override what context makes obvious,
  and only a difference that matters for the purpose at hand is worth raising.

## TDD and testing

- Write the failing test first: skeletonize the API with `raise NotImplementedError`
  equivalents, confirm Red, implement to Green.
- Reproduce every bug with a failing test before fixing it.
- Before calling a test done, verify it would fail if the code broke.
- Never test a prompt (a skill, CLAUDE.md, an agent definition) by matching its prose:
  rewording breaks the test without changing behavior. Assert only on text a program
  consumes (script paths, frontmatter keys, tool rules); a prose edit has no test-first
  step and is verified by running the prompt.
- Untestability is a code smell: refactor -- keep I/O at the boundary and logic pure.
- Never relax a linter/compiler to silence a warning; fix the root cause. Treat warnings
  as errors.

## Small and neat code

- DRY: define each constant/fact once and reference it everywhere; extract repeated
  expressions.
- A copied comment means the information belongs in docs or a constant.
- Match naming across layers (DB column = code field).
- Name things for what they represent, not how they are used; units in numeric names
  (`delayMs`, `maxSizeBytes`).
- Dependencies point one way: a shared component (a library, a config repo, a skill) never
  names its consumers -- not in code, docs, tests, or fixtures; it states the contract any
  consumer relies on instead. It also holds only what is true for every consumer: a rule or
  fact one consumer needs lives in that consumer. Test: if adding or retiring a consumer would
  force an edit to the shared component, the coupling is backwards.
- Don't follow conventions that no longer serve a purpose (e.g. the `X-` header prefix,
  deprecated by RFC 6648).

## Readability

- Self-documenting code over comments: expressive names and structure say what and how.
- Comment only why: trade-offs, workarounds with references, non-obvious constraints.
  Never restate code.
- No journal comments -- write for a clean-slate reader who never saw the change; change
  history belongs in commit messages.
- Never cite the project's own issues or PRs in comments, docstrings, or docs: state the
  reason itself. `git blame` reaches the commit, and its `Resolves #N` reaches the issue. An
  upstream bug a workaround depends on is a reference, not history, so cite it.

## Prose and docs

- ASCII in code and text files: `-->` not Unicode arrows; LaTeX dashes (`--` en dash, `---`
  em dash) not Unicode ones.
- US English spelling (`normalize`, `catalog`).
- Emojis only in user-facing scripts, never in code or docs.
- No AI-tic filler ("delve", "load-bearing", "testament"): state plainly what is critical
  or what breaks.
- No hardcoded counts that rot: prefer structural descriptions unless the number is cited
  or definitional.

## Messages to the user

- Report work for review, or ask for a decision that needs background, in the brief skill's
  format: the user supervises the work and steers it from what the message tells them. Ask a
  quick question that stands on its own directly.
- Explain the problem before the mechanism that fixes it.
- The coined-vocabulary rule of Docs content applies to messages too: a label made up
  mid-session means nothing to a user who was away.
- When the user reads back their understanding, confirm or correct it first, directly.

## Docs content

- Docs tell the high-level story; mechanism lives in the code. The refactor test: a
  sentence that would have to change under a refactor belongs in the docstring of the
  module that implements it, not in README or `docs/`.
- One owner per fact: each fact has one page that owns it; other pages link to it
  rather than restate it. A relative link is Required (points to the page that owns a
  fact or definition, or is an index/README entry) or Noise (bare "see also"). Test: if
  removing the link loses no fact, it should not be there.
- The clean-slate reader of Readability applies to docs too: say what the repo is,
  never what it no longer is ("X is a label, not a folder").
- Don't coin vocabulary the repo doesn't use: name a thing the way the code (or the
  page that defines it) names it, or don't name it. An invented distinction reads as
  precision and cannot be checked against anything.
- Before deleting a page, restructure from the code and give every fact on it a home;
  after deleting it, search the whole repo for links to it, code comments and data
  files included.
- For a change that touches only docs and comments, compare build output the build
  does not embed them in (a bundle, a rendered site) and confirm it is byte-identical,
  so "no behavior change" is evidence rather than a claim.

## Background work

- Never poll for work the harness already tracks: a backgrounded command reports its own
  completion, so wrapping it in a wait loop is waste that outlives the wait.
- Bracket-escape every `pgrep -f`/`pkill -f` pattern (`[p]ytest`, not `pytest`): `-f` matches
  whole command lines, so an unescaped pattern always matches the caller's own shell, and a
  wait loop built on one can never exit.
- Give every poll loop a bound, so a wrong condition ends the loop rather than the session.

## Memory discipline

- An assistant's auto-memory is machine-local and invisible to teammates. Use it only for
  transient or machine-local facts; any durable convention, decision, or preference
  belongs in a committed file.
