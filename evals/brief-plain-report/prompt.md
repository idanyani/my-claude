---
max_turns: 5
allowed_tools: [Skill, Read, Glob, Grep]
---

I've been away for a week and lost track. Here are my raw session notes -- bring me up to speed on where we are:

- repo recipe-site, branch 17-stale-search, PR #19 open, CI green
- issue #17: IndexBuilder only runs on deploy, so a recipe edited between deploys keeps its old text in SearchIdx until the next release
- added on_save hook -> IndexBuilder.reindex(recipe_id); debounced 30s via SaveQueue to coalesce rapid edits
- test_reindex_on_save.py: 5 cases, all pass
- picked per-recipe reindex over full rebuild on save: full rebuild takes ~4 min at 12k recipes
- open q: should a deleted recipe drop from SearchIdx right away (needs tombstone in SaveQueue) or wait for the next deploy rebuild? currently waits
- build/ has 2 stale idx-*.tmp files from an aborted rebuild; the nightly cleanup cron removes them
