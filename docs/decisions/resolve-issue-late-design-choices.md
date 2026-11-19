# resolve-issue stops before merging only for a design choice no source settles

A session that resolves an issue can make a design choice after the user approved the design:
a mechanism or a value a failing test or a review fix calls for. Two remedies are rejected.
Reporting every such choice in the PR and merging anyway does not work for a choice neither the
approved design nor a stated intent settles, because the user cannot reject it before it lands
on `main`; reopen this if a merged change can be held back from taking effect until the user
accepts it. Briefing the user and waiting before every merge gives up merging with no one
watching, a goal the README states; reopen this if that goal is dropped. Instead, before arming
auto-merge, the session checks each test expectation the branch adds or changes: a choice the
approved design or a stated intent settles is made and cited in the PR, and only one no source
settles waits for the user.
