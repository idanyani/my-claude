---
name: naming-review
description: Use when the user wants a repo's core concepts checked for fitting names -- says "naming-review", "/naming-review", "are our names right", "find a rename worth making", or "check for vague / misleading / inconsistent terms". Finds the concepts the system is built around, inventories their names across code, docs, tests, and stored formats, and reports the renames worth their cost, each with rejected alternatives; makes NO edits. Do NOT use for prose conventions in docs and comments (use /docs-review) or line-level naming nits in a diff (use /code-review).
---

# Naming review: give each core concept one fitting name

A reader who knows the domain but not the repo should understand any sentence in it without first
learning words the project made up. Names chosen early stop fitting as the concepts sharpen, and
they spread -- into code, docs, tests, stored formats, and every consumer that reads them. Prose
built on a bad name comes out roundabout, and a concept split across modules stays hidden behind
it. This skill finds the few names whose fix is worth its cost and **reports them -- it makes no
edits.**

This skill is repo-agnostic. The repo's `CLAUDE.md` (and the global conventions it inherits) sets
the rules -- read it.

## Phase 1 -- Ground

1. **Goals.** Take the goals and non-goals confirmed with the user in this session. Failing that,
   take `README.md`'s, if it states both clearly. Failing both, ask the user, or stop and suggest
   `/purpose-review`: a name fits a concept only relative to what the project is for.
2. **Decision records.** Read them, as `CLAUDE.md` says; a finding that raises a rejected rename
   again says why its reason no longer holds.

## Phase 2 -- Inventory

Dispatch one `general-purpose` subagent, handing it the goals, to return only:

- **Core concepts:** the few things every part of the system reads, writes, or passes on -- what
  its data is about, and the states those things are in. For each, one sentence in plain domain
  language, written before looking at what the code calls it.
- **Their names, everywhere:** for each concept, every name it goes by -- type and module names,
  stored keys and values, CLI and output fields, docs, docstrings, comments, and test names -- with
  `git grep -c -w -i` counts per name and per layer (code, docs, tests, stored format), and the
  consumers outside the repo that read it, where the docs name them.

## Phase 3 -- Judge

Compare each concept with its names. A name is a candidate when it is:

- **vague or coined:** a word so general, or so private, that the docs must define it before any
  sentence using it reads -- or explaining it takes a paragraph;
- **misleading:** its everyday meaning contradicts the thing (a word implying a duplicate for the
  one thing never duplicated);
- **attached to the wrong object:** a state value that describes a related thing, so a sentence
  reads as if the wrong thing changed;
- **silent on what:** a status like `ok` that does not say what was checked;
- **narrower than its contents:** a key named after one kind of entry that holds others;
- **one word for two concepts,** or **one concept under several names** across layers.

Roundabout sentences, definitions that must precede the text using them, and one concept explained
again on several pages are symptoms: follow them back to the name.

For each candidate, find the replacement: prefer the domain's common word over a coined one, and
test each option in real sentences from the repo -- how people naturally say a thing settles how
concepts relate ("the document was updated" means the same document with new contents, so a
document has versions). Record each option rejected and why.

## Phase 4 -- Weigh

Report only renames worth their cost -- **a finding renames a core concept or its states**, not a
local variable or a one-off field, which `/code-review` and `/docs-review` cover. Weigh:

- **Spread:** the counts, the layers, and above all whether the name reached a stored format or a
  consumer: each consumer inherits the vocabulary, so the cost of the bad name grows with them.
- **Cost to undo:** renaming code and docs is cheap; renaming a stored format or a public
  interface costs a migration or a breaking change -- unless a moment makes it cheap (stored data
  about to be reset, a major version). Name such a moment when one is near.
- **What it exposes:** a concept that resists one good name is often two concepts, or one split
  across modules. Flag it as a likely design mismatch rather than forcing a name.

## Phase 5 -- Report

Rank the findings, most valuable first, and print for each:

- the concept and its one-sentence definition;
- its current names, with counts per layer and the consumers they reach;
- the proposed name, shown in two or three of the repo's own sentences, rewritten;
- the options rejected, each with why;
- the reach: core types, stored keys, and states take the domain names; low-level fields (a URL,
  a checksum) may keep technical ones; one doc owns the definitions and every other layer uses
  them;
- the cost to undo, and the moment that makes it cheap, if any.

If every core concept already has one fitting name, say so plainly: **the names fit** is a full
answer, with the concept list as its evidence.

Close by offering the follow-up the user chooses: file issues for the picked renames with
`/file-issue` (each finding holds what the issue and its PR need). When the user rejects a rename
for a reason that will still hold, offer a decision record for it, through the same issue and PR
flow.
