# Every PR goes into main, ready, and resolves its issue

Common git workflows also open a PR against a long-lived branch, stack small PRs each based on the
one below, open a draft, or land part of an issue in a PR that does not close it. resolve-issue
allows none of these: every PR targets `main`, opens ready for review, and resolves its issue, and
a hook refuses opening or merging one with `gh` directly instead of through its scripts. A
long-lived branch drifts from `main` until its merge is too big to review; unfinished work instead
lands in `main`, unreachable until it is wired in, as trunk-based development does
(https://dora.dev/capabilities/trunk-based-development/). A draft adds nothing here: a PR cannot
merge until its session arms auto-merge, and CI runs on it from its first push. An issue too big
for one PR is split into issues that one PR each resolves. Stacking pays off when review takes
hours or days, so the author keeps working meanwhile; here the review runs in the authoring
session and auto-merge lands a PR minutes after its checks pass, so a dependent change waits
little for the one below. Reopen this once review waits on people, or once a repo keeps a release
branch that a fix must target.
