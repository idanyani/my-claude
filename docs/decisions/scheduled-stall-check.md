# Stuck auto-merge PRs are fixed when a branch starts, not on a schedule

An armed PR that GitHub never merges, or whose push fired no CI, is re-armed or reopened only when
`start_branch.py` next runs in its repo, so in a repo no one works in, it could stay open that
long. A scheduled job -- a GitHub Action in every repo, or a daily job on the machine that runs the
same fix across all repos -- would bound that wait. It is not built, because the wait has not
happened: of about 350 PRs that auto-merge merged across 7 repos from 2026-10-16 to 2026-11-17,
each merged or was re-armed within 22 minutes of its checks passing, and none sat open waiting. A
scheduled job would add a second place that runs the fix, and would need a workflow in every repo
or a job on every machine, to guard against a wait no repo has shown. Reopen this once an armed PR
with passing checks stays open for more than a day.
