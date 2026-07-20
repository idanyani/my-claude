"""Parse and resolve intra-repo markdown links, for the doc-freshness audit.

Deterministic link resolution belongs in code, not a subagent's judgment: the audit should spend
model attention on whether prose still matches the code, not on re-deriving whether a relative path
exists. Pure functions; the executable (check_links.py) walks files and calls these.

Cross-file anchors are deliberately not validated -- heading-slug rules vary by renderer and would
produce false "broken" reports. Path existence (unambiguous) and same-file anchors are checked.
"""

import re
from pathlib import Path

# Markdown inline links: [text](target). Reference-style links and autolinks are out of scope.
_INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
_HEADING = re.compile(r"#{1,6}\s+(.*)")
_NON_SLUG = re.compile(r"[^\w\s-]")
_WHITESPACE = re.compile(r"\s+")


def extract_links(markdown: str) -> list[tuple[int, str]]:
    """(line_number, target) for each inline link, lines 1-indexed."""
    links = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        for match in _INLINE_LINK.finditer(line):
            links.append((line_number, match.group(1)))
    return links


def is_intra_repo(target: str) -> bool:
    """Whether a target is a repo-relative path, not a URL, mailto, or protocol-relative link."""
    return not target.startswith(("http://", "https://", "mailto:", "tel:", "ftp:", "//", "#!"))


def slugify(heading: str) -> str:
    """GitHub-style heading slug: lowercased, punctuation dropped, spaces to hyphens."""
    text = _NON_SLUG.sub("", heading.strip().lower())
    return _WHITESPACE.sub("-", text)


def heading_slugs(markdown: str) -> set[str]:
    """Anchor slugs for every ATX heading in a markdown document."""
    return {
        slugify(match.group(1)) for match in map(_HEADING.match, markdown.splitlines()) if match
    }


def _split_anchor(target: str) -> tuple[str, str | None]:
    path_part, sep, anchor = target.partition("#")
    return path_part, (anchor if sep else None)


def link_is_broken(source_file: Path, target: str, repo_root: Path, source_text: str) -> bool:
    """Whether an intra-repo link fails to resolve to an existing file or same-file anchor."""
    if not is_intra_repo(target):
        return False
    path_part, anchor = _split_anchor(target)
    if path_part == "":
        # Pure same-file anchor: verify the heading exists.
        return anchor is not None and slugify(anchor) not in heading_slugs(source_text)
    if path_part.startswith("/"):
        resolved = repo_root / path_part.lstrip("/")
    else:
        resolved = source_file.parent / path_part
    return not resolved.exists()
