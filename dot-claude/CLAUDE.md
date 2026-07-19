# Global preferences

## Interaction preferences

- When `AskUserQuestion` returns an empty or "no response" result (its ~60s timeout fired),
  do **not** proceed on assumptions. A timeout means the answer was not received yet, not
  consent to guess. Re-ask the question (or stop and wait) so the decision stays with the user.
