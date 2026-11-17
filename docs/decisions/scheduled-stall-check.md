# Stuck auto-merge PRs are fixed when a branch starts, not on a schedule

An armed PR that GitHub never merges, or whose push fired no CI, is re-armed or reopened only when
its author next runs `start_branch.py` in its repo, so in a repo no one works in, it stays open
until a session next starts a branch there. A scheduled job running the same fix across all repos
would bound that wait. It is not built, because no PR has waited that way. Of about 350 PRs that
auto-merge merged across 7 repos from 2026-10-16 to 2026-11-17, each merged, or was re-armed or
reopened, within 22 minutes of its checks passing, and on 2026-11-17 no armed PR was open in any of
them. Those repos are all worked in often, so this does not show how long an idle repo would wait;
it shows only that none has held a stuck PR yet. A scheduled job would be one more thing to keep
running and to keep listing the repos for, against a wait not yet seen. Reopen this once an armed
PR stays open for more than a day.
