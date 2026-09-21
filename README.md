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
  settings.json        copied (Claude Code rewrites it at runtime, which would sever a link)
  skills/
    resolve-issue/     symlinked; one `git pull` here updates every machine's live skill
```

## Shared conventions

[`dot-claude/CLAUDE.md`](dot-claude/CLAUDE.md) is the canonical core of working
conventions shared across the maintained repos; each repo's own `CLAUDE.md` keeps only its
genuinely unique rules. The core reaches every consumer through three layers:

1. **Claude Code on the maintainer's machines** -- `install.sh` symlinks the file to
   `~/.claude/CLAUDE.md`, so it loads into every session.
2. **Tiki's bot container** -- the image bakes my-claude in.
3. **GitHub Copilot code review** -- [`scripts/sync_copilot_instructions.py`](scripts/sync_copilot_instructions.py)
   renders the file into `.github/copilot-instructions.md` in each consuming repo, which is
   where Copilot reads it. Pass repo paths to verify (exit 1 on drift) and `--write` to
   refresh. Organization-level instructions would keep one central copy instead, but they
   require paid Copilot Business seats and expose no API, so nothing could check that copy
   was current; a generated file is committed, so drift is a diff.

## Skills

- **[resolve-issue](dot-claude/skills/resolve-issue/SKILL.md)** -- implement a GitHub issue
  end-to-end: ground in the repo, read the issue, branch, TDD, verify, PR with Copilot
  review, auto-merge, clean up. Ships stdlib-only helper scripts (`python3`, `git`, `gh` are
  the only runtime requirements) and the canonical
  [git-workflow doc](dot-claude/skills/resolve-issue/references/git-workflow.md).
- **[maintain](dot-claude/skills/maintain/SKILL.md)** -- sweep recent work for the debris fast
  cycles leave behind (stale docs, duplication and reinvention, weak tests, dead code,
  convention drift) and report ranked findings for triage, making no edits. Pairs with the
  `check_prose` PostToolUse hook, which deterministically flags the mechanical prose-convention
  violations (non-ASCII typography, emojis in code) that linters miss.

## Install

Normally driven by [my-config](https://github.com/idanyani/my-config)'s `copyConfig.sh`,
which clones this repo if missing and runs `install.sh`. Directly:

```sh
git clone git@github.com:idanyani/my-claude.git   # any location works
cd my-claude && ./install.sh                      # idempotent; re-running heals moved links
```

Skills and `CLAUDE.md` are symlinked, so a `git pull` in the clone updates every machine's
live config at once -- one canonical source instead of divergence-by-duplication.
`settings.json` is the deliberate exception: it is copied as a snapshot, and re-running
`install.sh` overwrites local drift.

## Development

The skill scripts are stdlib-only; this project's dev-dependencies exist to test and lint
them.

```sh
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Tests live in `tests/` at the repo root, and maintainer tooling in `scripts/` -- both
outside the mirrored `dot-claude/` tree, so neither is installed into `~/.claude`.
