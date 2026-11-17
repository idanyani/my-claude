# my-claude

My global [Claude Code](https://docs.claude.com/en/docs/claude-code) configuration -- settings,
hooks, [skills](https://docs.claude.com/en/docs/claude-code/skills), and working conventions --
for the agents I run across all my repos. It aims to:

- keep one source for that configuration, installed on every machine I use;
- have agents in every repo work the same way: issue first, test first, a PR the agent reviews
  before it merges, and less is more;
- keep repos healthy, with reviews that find the debris and drift fast agent-driven work leaves
  behind;
- drive projects forward, with reviews that settle a project's purpose, names, and design and
  plan its next large changes;
- let agents carry a development task end to end and merge it to `main` on their own -- safe
  because tests written first and CI checks gate every merge.

It does not aim to:

- support installs by other people -- the repo is public, but it serves my machines;
- hold rules for one project's code -- those live in that project's own `CLAUDE.md`;
- tie the conventions to Claude Code -- they are plain prose any agent tool can read, while the
  skills, hooks, and settings target Claude Code.

One organizing principle shapes the repo: **`dot-claude/` is an exact image of `~/.claude`**.
Whatever should exist under `~/.claude` lives at the same relative path under `dot-claude/`, and
`install.sh` mirrors the tree generically, so adding a new file or directory (`agents/`,
`commands/`, ...) never requires touching the script.

```
dot-claude/
  CLAUDE.md            symlinked into ~/.claude (edits flow straight back to the repo)
  settings.json        merged (Claude Code rewrites it at runtime, which would sever a link)
  hooks/               symlinked; settings.json registers them
  skills/
    resolve-issue/     symlinked; a `git pull` in the main checkout updates the live skill
```

## Working conventions

[`dot-claude/CLAUDE.md`](dot-claude/CLAUDE.md) holds the working conventions: rules true for
any project, loaded into every Claude Code session on a machine that installs my-claude.

## Skills

- **[resolve-issue](dot-claude/skills/resolve-issue/SKILL.md)** -- implement a GitHub issue
  end-to-end: ground in the repo, read the issue, brief the user, branch, TDD, verify,
  `/simplify`, PR with in-session review, auto-merge, clean up, brief the user on the result.
  Ships stdlib-only helper scripts (`python3`, `git`, `gh` are the only runtime requirements)
  and the canonical
  [git-workflow doc](dot-claude/skills/resolve-issue/references/git-workflow.md).
- **[file-issue](dot-claude/skills/file-issue/SKILL.md)** -- record a problem as a GitHub
  issue, after searching open and closed issues for one that already covers it.
- **[docs-review](dot-claude/skills/docs-review/SKILL.md)** -- review docs, docstrings, and
  comments for stale or unbacked claims, broken links, prose-convention drift, and docs shaped
  wrong as a whole, and report ranked findings for triage, making no edits. Pairs with the
  `check_prose` PostToolUse hook, which deterministically flags the mechanical prose-convention
  violations (non-ASCII typography, emojis in code) that linters miss.
- **[test-review](dot-claude/skills/test-review/SKILL.md)** -- review the tests of recent work:
  prove they can fail by mutating the code under test in a scratch copy, find changed code no test
  exercises, and flag flaky, redundant, or implementation-coupled tests; report ranked findings,
  making no edits.
- **[dead-code-review](dot-claude/skills/dead-code-review/SKILL.md)** -- find code, scripts, CI
  jobs, hooks, data files, and modes that nothing calls, invokes, or reads, searching the whole
  repo rather than only the diff, including targets a change orphaned by dropping their last
  reference; report ranked findings, making no edits.
- **[project-review](dot-claude/skills/project-review/SKILL.md)** -- review a repo from a bird's
  eye view: settle its purpose with the user, review its names and its design in hindsight, and
  return one ordered plan of the changes it needs, or say it is good as it stands.
  Runs these three, each also usable alone, making no edits:
  - **[purpose-review](dot-claude/skills/purpose-review/SKILL.md)** -- infer the goals and
    non-goals from the docs, code, and history, have the user settle them, and report docs that
    do not state them and parts that serve none.
  - **[naming-review](dot-claude/skills/naming-review/SKILL.md)** -- find the core concepts,
    inventory their names across code, docs, tests, and stored formats, and report the renames
    the core concepts need.
  - **[hindsight-review](dot-claude/skills/hindsight-review/SKILL.md)** -- read the history for
    lessons, search for tools released since, design the project afresh from its goals, and
    report the redesigns it would make today.
- **[lessons-review](dot-claude/skills/lessons-review/SKILL.md)** -- find the kinds of mistake
  agents keep repeating, in session transcripts, PR reviews, issues, and fix commits, and propose
  for each the check a program runs, or else the rule, that would stop it; report findings,
  making no edits.
- **[brief](dot-claude/skills/brief/SKILL.md)** -- fill the user in on a session's work so they
  can review and steer it: one screen of short, plain bullets saying where the work stands,
  what to check (each claim tagged by how well it is backed, and the choices made without the
  user), and, last, the decisions waiting on them with a recommendation.

## Install

```sh
git clone git@github.com:idanyani/my-claude.git   # any location works
cd my-claude && ./install.sh                      # idempotent; heals moved links, retires dropped ones
```

Run `install.sh` in the main checkout -- the directory `git clone` created -- not in a linked
worktree: everything it installs links into the checkout that runs it.

Skills, hooks, and `CLAUDE.md` are symlinked, so a `git pull` in a machine's main checkout updates
its live config at once -- one canonical source instead of divergence-by-duplication.
`settings.json` is the deliberate exception: `install.sh` merges it into the live file
instead of linking it, so settings added on the machine survive; the merge rules live in
[`scripts/merge_settings.py`](scripts/merge_settings.py). `install.sh` also installs git
hooks that rerun it after a pull, checkout, or rebase updates the main checkout, so the merged
settings keep up with the linked files. A commit, a `git reset`, or resolving a merge conflict fires none
of them: run `./install.sh` after those.

## Development

The skill scripts are stdlib-only; this project's dev-dependencies exist to test and lint
them.

```sh
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Tests live in `tests/` at the repo root, outside the mirrored `dot-claude/` tree, so they are
not installed into `~/.claude`.

Designs weighed and rejected, with what would reopen them, are recorded in
[`docs/decisions/`](docs/decisions/).
