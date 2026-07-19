# claude-skills

Personal [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) shared
across repos. Each skill under `skills/` is generic -- zero repo-specific content; the
consuming repo's `CLAUDE.md` and docs supply the specifics.

## Skills

- **[resolve-issue](skills/resolve-issue/SKILL.md)** -- implement a GitHub issue end-to-end:
  ground in the repo, read the issue, branch, TDD, verify, PR with Copilot review, auto-merge,
  clean up. Ships stdlib-only helper scripts (`python3`, `git`, `gh` are the only runtime
  requirements) and the canonical
  [git-workflow doc](skills/resolve-issue/references/git-workflow.md).

## Install

Clone, then symlink the skills you want into a repo's `.claude/skills/` (or your user-level
`~/.claude/skills/`):

```sh
git clone git@github.com:idanyani/claude-skills.git ~/repos/claude-skills
mkdir -p ~/.claude/skills
ln -s ~/repos/claude-skills/skills/resolve-issue ~/.claude/skills/resolve-issue
```

A `git pull` in the clone updates every symlinked copy at once -- that is the point: one
canonical source instead of divergence-by-duplication.

## Development

The skill scripts are stdlib-only; this project's dev-dependencies exist to test and lint
them.

```sh
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Tests live in `tests/` at the repo root -- outside the symlinked skill directories, so
consuming repos never see them.
