# Docs review rubric

The checklist a `docs-review` applies, derived from the global conventions in `~/.claude/CLAUDE.md`
plus whatever the target repo's own `CLAUDE.md` adds. This file names what to look for; the
conventions themselves live in those `CLAUDE.md` files -- read them for the authoritative wording,
and defer to the repo's `CLAUDE.md` where it is stricter.

Each concern below maps to one Phase 2 subagent (concern 3 runs only when the file set touches a
doc). Report every hit as `[SEVERITY] one-line finding -- file:line`, nothing else; a finding that
exists only across files (concern 3) anchors to the file or directory it spans instead. Reserve HIGH
for prose that misleads a reader (a wrong doc, a claim nothing backs, a broken link); MEDIUM for real
debt (a fact restated across pages, a journal comment, docs shaped wrong); LOW for style and polish,
and for signals that only the owner can judge.

Auxiliary machinery -- package-manager scripts, build and test configs, CI workflows and composite
actions, shell scripts, Dockerfiles, git hooks -- is subject matter too: docs describe it, and its
comments drift like any other.

## 1. Doc accuracy: freshness and backing

A claim can be wrong two ways: it went stale, or nothing ever made it true. Ask both -- "is this
still true?" and "what in the code makes this true?". A claim with no answer to the second is a
finding even if no commit ever contradicted it.

- A doc states a command, flag, path, signature, or count that the current code no longer matches.
- A doc describes behavior that was changed or removed.
- A stated priority or ordering (between goals, rules, or sources) that no design decision, code
  path, or config reflects.
- A guarantee ("nothing ships until it passes", "every X goes through Y") that a side entry point,
  flag, or script bypasses.
- An example presented as real that matches no real file, record, or output.
- A list that reads as complete but misses a case the code or its tests enforce.
- A recipe that cannot run: trace each command, path, and precondition it assumes. Do not execute
  it -- a recipe may have side effects, and this review makes no changes.
- A CI workflow whose stages no longer match the pipeline the docs describe.
- A broken intra-repo link (the `check_links.py` findings are pre-computed -- fold them in as HIGH).
- A hardcoded number in prose that is already wrong (one that is right today but will rot is
  concern 2).

## 2. Prose conventions (judgment)

Applies to docs, docstrings, and code comments alike. The mechanical prose checks (non-ASCII
glyphs, emojis in code/docs) are handled deterministically by the `check_prose` PostToolUse hook --
do NOT re-scan for them. This concern covers only what needs judgment:

- Journal comments that narrate change history (that belongs in commit messages), and citations of
  the project's own issues or PRs (an upstream bug a workaround depends on is a reference, not
  history).
- Docs prose defined against a design the reader never saw: a contrast or denial whose other half
  exists only in history or imagination ("X is a label, not a folder", "there is no state file").
  The doc counterpart of a journal comment -- state what the design is, not what it is not.
- Docs or comments that name a thing by a term nothing else in the repo defines or uses (grep
  before reporting): an invented distinction that cannot be checked against anything.
- Comments that restate what the code plainly says, rather than explaining a non-obvious *why*.
- A copied comment -- the information belongs in a doc or a named constant, not repeated.
- A reference to another file that carries no fact the text needs, or that points to something
  written later.
- A hardcoded count that will rot, where a structural description would not.
- AI-tic filler ("delve", "load-bearing", "testament") in prose.

## 3. Docs shape (whole set)

Read the docs set as one body -- every authored markdown doc in the repo (`README.md`, `docs/`,
skill and reference files, wherever the repo keeps them), plus the module docstrings those docs
describe -- whenever the file set touches any markdown doc. Each problem here is invisible per
line: every duplicate, every page reads fine alone.

- A fact stated in several places. Report how many and where, and name the one place that should
  own it.
- A page that is mostly mechanism a module already documents. A sentence that would have to change
  under a refactor of that module belongs in its docstring, not in the docs.
- A `README.md` that does not open by saying what the project is, or a reading order a newcomer
  cannot follow (a page that depends on terms only a later page defines).
- Docs out of proportion to the code: the set reads as far more complex than what it describes.
- Link density: docs that need many cross-links to make sense, which can mean the docs -- or the
  design under them -- are too tightly coupled. Report as LOW; whether to restructure the docs or
  the design is the owner's call.
