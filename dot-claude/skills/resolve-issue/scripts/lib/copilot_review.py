"""Pure logic for reading Copilot's review off the REST API.

The decision-making here is deliberately pure (no `gh` calls) so it is unit-tested without touching
GitHub; the shell-outs live in `lib/gh.py`. Everything reads the REST payloads (`/pulls/{n}/reviews`
and `/pulls/{n}/reviews/{review_id}/comments`), which is what lets a single Copilot identity suffice.
"""

from typing import Any

# Reading reviews via REST (not GraphQL, which strips the suffix) means the review author, the
# re-review *request* target, and every representation of the bot the scripts touch are this one
# `[bot]` login. The inline comments are then fetched from the review's own
# `/reviews/{review_id}/comments` endpoint, so their own author login never has to be matched.
COPILOT_REVIEWER = "copilot-pull-request-reviewer[bot]"


def find_copilot_review(reviews: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The latest Copilot review among a PR's REST reviews, or None if it has not posted yet.

    REST returns every review in chronological order, so across re-reviews the last Copilot-authored
    entry is the current one. Reviews are a separate event stream from CI checks; this keys on the
    review stream alone so review handling never gets gated on the slower, unrelated `verify` signal.
    """
    mine = [r for r in reviews if r.get("user", {}).get("login") == COPILOT_REVIEWER]
    return mine[-1] if mine else None


def is_unavailable_review(review: dict[str, Any]) -> bool:
    """Whether a Copilot review is an "I could not review this" notice rather than real feedback.

    The signal lives in the body, not the state (Copilot still posts it as a `COMMENTED` review):
    "Copilot was unable to review this pull request because ...". Matching the reason-agnostic
    prefix catches the quota case and any other unavailability, so the caller can fall back to an
    in-session review instead of merging unreviewed. A None body (the REST default for a review
    with no overview text) is a real, if terse, review -- not a refusal.
    """
    return "unable to review this pull request" in (review.get("body") or "").lower()


def poll_decision(reviews: list[dict[str, Any]], elapsed_ms: float, timeout_ms: float) -> str:
    """Decide one tick of the bounded wait.

    A review present ends it immediately -- "unavailable" when it is an unavailability notice (no
    real review will follow), otherwise "found". Absent, the wait continues until `elapsed_ms`
    reaches the cap, at which point it expires (the review is advisory, so the caller proceeds
    rather than blocking forever).

    Returns one of: "found", "unavailable", "timeout", "continue".
    """
    review = find_copilot_review(reviews)
    if review is not None:
        return "unavailable" if is_unavailable_review(review) else "found"
    if elapsed_ms >= timeout_ms:
        return "timeout"
    return "continue"


def format_review_comments(comments: list[dict[str, Any]]) -> str:
    """Render inline findings as `path:start-line` (file-level ones as `path` alone) plus body."""
    if not comments:
        return "No inline comments."
    lines = [f"Inline findings ({len(comments)}):"]
    for c in comments:
        start, end = c.get("start_line"), c.get("line")
        if end is None:
            anchor = c.get("path", "")
        elif start is None or start == end:
            anchor = f"{c.get('path', '')}:{end}"
        else:
            anchor = f"{c.get('path', '')}:{start}-{end}"
        # Indent continuation lines too, so a multi-line body stays nested under its bullet.
        body = (c.get("body") or "").strip().replace("\n", "\n  ")
        lines.append(f"- {anchor}\n  {body}")
    return "\n".join(lines)
