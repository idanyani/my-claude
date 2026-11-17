# resolve-issue may hand issues to subagents, once the user settled their design

A session that hands an issue to a subagent can decide its design without the user, by writing a
design into the subagent's prompt or leaving it to the subagent. Two remedies are rejected.
Never resolving issues with subagents gives up parallel work on issues whose design the user
already settled, where nothing is left to decide. Letting the subagent brief the user itself does
not work, because a subagent cannot wait for the user's answer. Instead, the spawning session
briefs each issue and waits for the user, and the subagent returns any design choice the user's
answers leave open. Reopen this if subagents can ask the user directly and wait for the answer.
