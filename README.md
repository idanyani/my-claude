# my-claude

Personal global [Claude Code](https://docs.claude.com/en/docs/claude-code) configuration --
settings and [skills](https://docs.claude.com/en/docs/claude-code/skills) -- with one
organizing principle: **`dot-claude/` is an exact image of `~/.claude`**. Whatever should
exist under `~/.claude` lives at the same relative path under `dot-claude/`, and
`install.sh` mirrors the tree generically, so adding a new file or directory (`agents/`,
`commands/`, ...) never requires touching the script.

```
dot-claude/
  CLAUDE.md            symlinked into ~/.claude (edits flow straight back to the repo)
  settings.json        merged (Claude Code rewrites it at runtime, which would sever a link)
  skills/
    resolve-issue/     symlinked; one `git pull` here updates every machine's live skill
```

## Working conventions

[`dot-claude/CLAUDE.md`](dot-claude/CLAUDE.md) holds the working conventions: rules true for
any project, loaded into every Claude Code session on a machine that installs my-claude.

## Skills

- **[resolve-issue](dot-claude/skills/resolve-issue/SKILL.md)** -- implement a GitHub issue
  end-to-end: ground in the repo, read the issue, brief the user, branch, TDD, verify,
  `/simplify`, PR with in-session review, auto-merge, clean up, brief the user on the result. Ships stdlib-only helper scripts (`python3`, `git`,
  `gh` are the only runtime requirements) and the canonical
  [git-workflow doc](dot-claude/skills/resolve-issue/references/git-workflow.md).
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

- **[brief](dot-claude/skills/brief/SKILL.md)** -- fill the user in on a session's work so they
  can review and steer it: one screen, top-down from the epic, issue and PR, with each finding
  tagged by how well it is backed, the choices made without the user, and the decisions waiting
  on them. Also the format for every report and question to the user.

## Install

```sh
git clone git@github.com:idanyani/my-claude.git   # any location works
cd my-claude && ./install.sh                      # idempotent; heals moved links, retires dropped ones
```

Skills and `CLAUDE.md` are symlinked, so a `git pull` in the clone updates every machine's
live config at once -- one canonical source instead of divergence-by-duplication.
`settings.json` is the deliberate exception: `install.sh` merges it into the live file
instead of linking it, so settings added on the machine survive; the merge rules live in
[`scripts/merge_settings.py`](scripts/merge_settings.py).

## Development

The skill scripts are stdlib-only; this project's dev-dependencies exist to test and lint
them.

```sh
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Tests live in `tests/` at the repo root, outside the mirrored `dot-claude/` tree, so they are
not installed into `~/.claude`.
