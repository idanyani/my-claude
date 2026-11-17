# A rejected design is kept in a decision record, not looked up in past PRs

A change can adopt a design an earlier change rejected, because the rejection sat only in that
change's commit and PR body. Searching past PRs for rejected alternatives before each change was
considered instead of writing records. It is not used, because the search finds a rejection only
by guessing the words the earlier PR used, while the records sit in one directory read before a
redesign. Reopen this if PR search can find a rejected design by meaning rather than by its words.
