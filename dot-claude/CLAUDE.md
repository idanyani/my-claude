# Working conventions

## Git commit messages

- Start with a specific imperative verb conveying intent ("Implement", "Refactor",
  "Document", "Harden") -- not generic "Add"/"Update"/"Change".
- Describe what the commit does to the repository's persistent state, never the session:
  no "as discussed", no naming uncommitted scratch files.
- No conventional-commit prefixes ("feat:", "fix:"); no Co-Authored-By lines.
- Reference issues with `Resolves #N`.
- Rename/move with `git mv` and delete with `git rm`, never plain `rm`, so history
  follows the file.

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

## TDD and testing

- Write the failing test first: skeletonize the API with `raise NotImplementedError`
  equivalents, confirm Red, implement to Green.
- Reproduce every bug with a failing test before fixing it.
- Before calling a test done, verify it would fail if the code broke.
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
- Don't follow conventions that no longer serve a purpose (e.g. the `X-` header prefix,
  deprecated by RFC 6648).

## Readability

- Self-documenting code over comments: expressive names and structure say what and how.
- Comment only why: trade-offs, workarounds with references, non-obvious constraints.
  Never restate code.
- No journal comments -- write for a clean-slate reader who never saw the change; change
  history belongs in commit messages.

## Prose and docs

- ASCII in code and text files: `-->` not Unicode arrows, `--`/`---` not em/en-dashes.
- US English spelling (`normalize`, `catalog`).
- Emojis only in user-facing scripts, never in code or docs.
- No AI-tic filler ("delve", "load-bearing", "testament"): state plainly what is critical
  or what breaks.
- No hardcoded counts that rot: prefer structural descriptions unless the number is cited
  or definitional.
- Cross-reference discipline: a relative link is Required (points to the single place a
  fact or definition lives, or is an index/README entry) or Noise (bare "see also").
  Test: if removing the link loses no fact, it should not be there.

## Memory discipline

- An assistant's auto-memory is machine-local and invisible to teammates. Use it only for
  transient or machine-local facts; any durable convention, decision, or preference
  belongs in a committed file.

## Hebrew

- User-facing Hebrew copy is gender-neutral: prefer nouns, infinitives, and passive
  constructions over gendered conjugations; the slash form (מסכים/ה) is a last resort.
