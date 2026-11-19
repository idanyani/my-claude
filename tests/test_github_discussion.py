"""Tests for dot-claude/bin/github-discussion, run as a plain file against a fake `gh` on PATH.

The fake answers as GitHub and `gh api` would, from pages each test sets: every page only under
`--paginate`, each through the `--jq` filter with the real jq. The REST issues listing holds only
open items unless asked for `state=all`; GraphQL returns only the fields a query names, at most the
`reviews(first: N)` it asks for, and more than one page only to a query asking for `pageInfo`.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "dot-claude" / "bin" / "github-discussion"

FAKE_GH = r"""#!/usr/bin/env python3
import json, os, re, subprocess, sys

args = sys.argv[1:]
served = json.load(open(os.environ["FAKE_GH_PAGES"]))
if "graphql" in args:
    if not {"owner={owner}", "name={repo}"} <= set(args):
        sys.exit("graphql: no repo given")
    query = next(a.removeprefix("query=") for a in args if a.startswith("query="))
    first = int(re.search(r"reviews\(first: (\d+)\)", query)[1])

    def answer(value, key=""):
        if isinstance(value, list):
            return [answer(v) for v in value][: first if key == "reviews" else None]
        if isinstance(value, dict):
            return {k: answer(v, key if k == "nodes" else k) for k, v in value.items()
                    if k == "data" or re.search(rf"\b{k}\b", query)}
        return value

    pages = [answer(page) for page in served.get("graphql", [])]
    if "pageInfo { hasNextPage endCursor }" not in query:
        pages = pages[:1]
else:
    endpoint = next(a for a in args if a.startswith("repos/{owner}/{repo}/"))
    path, _, params = endpoint.removeprefix("repos/{owner}/{repo}/").partition("?")
    pages = served.get(path, [])
    if pages == "FAIL":
        sys.exit(f"{path}: HTTP 502")
    if path == "issues" and "state=all" not in params.split("&"):
        pages = [[item for item in page if item["state"] == "open"] for page in pages]
jq_filter = args[args.index("--jq") + 1]
for page in pages if "--paginate" in args else pages[:1]:
    subprocess.run(["jq", "-c", jq_filter], input=json.dumps(page), text=True, check=True)
"""


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Put the fake on PATH; return a function that serves its pages and runs the script."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    pages_file = tmp_path / "pages.json"
    monkeypatch.setenv("FAKE_GH_PAGES", str(pages_file))

    def run(pages: dict) -> subprocess.CompletedProcess:
        pages_file.write_text(json.dumps(pages))
        return subprocess.run([SCRIPT], capture_output=True, text=True)

    return run


def output(run, pages: dict) -> Path:
    """Run the script and return the directory it prints."""
    result = run(pages)
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.strip())


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def prs_page(*prs: tuple[int, int, list[dict]]) -> dict:
    """One GraphQL page of PRs, each given as (number, total review count, reviews returned)."""
    nodes = [
        {"number": n, "reviews": {"totalCount": total, "nodes": reviews}}
        for n, total, reviews in prs
    ]
    return {"data": {"repository": {"pullRequests": {"nodes": nodes}}}}


def test_reads_every_issue_and_pr_open_or_closed_into_its_files(run):
    issue = {
        "number": 1,
        "title": "t",
        "user": {"login": "u"},
        "body": "b",
        "state": "closed",
        "state_reason": "not_planned",
        "created_at": "c",
        "closed_at": "d",
    }
    pr = {
        "number": 2,
        "title": "p",
        "user": {"login": "v"},
        "body": "pb",
        "state": "closed",
        "state_reason": None,
        "created_at": "c2",
        "closed_at": "d2",
        "pull_request": {"merged_at": "m"},
    }
    out = output(run, {"issues": [[issue], [pr]]})
    assert records(out / "issues.jsonl") == [
        {
            "number": 1,
            "is_pr": False,
            "title": "t",
            "author": "u",
            "body": "b",
            "state": "closed",
            "state_reason": "not_planned",
            "created_at": "c",
            "closed_at": "d",
            "merged_at": None,
        },
        {
            "number": 2,
            "is_pr": True,
            "title": "p",
            "author": "v",
            "body": "pb",
            "state": "closed",
            "state_reason": None,
            "created_at": "c2",
            "closed_at": "d2",
            "merged_at": "m",
        },
    ]
    assert sorted(os.listdir(out)) == [
        "comments.jsonl",
        "issues.jsonl",
        "review-comments.jsonl",
        "reviews.jsonl",
    ]


def test_reads_comments_past_the_first_page(run):
    def comment(issue: int, body: str) -> dict:
        return {
            "issue_url": f"https://api.github.com/repos/o/r/issues/{issue}",
            "user": {"login": "u"},
            "created_at": "c",
            "body": body,
        }

    out = output(run, {"issues/comments": [[comment(1, "first")], [comment(3, "second")]]})
    assert records(out / "comments.jsonl") == [
        {"number": 1, "author": "u", "created_at": "c", "body": "first"},
        {"number": 3, "author": "u", "created_at": "c", "body": "second"},
    ]


def test_keeps_where_inline_comments_point_and_what_they_reply_to(run):
    url = "https://api.github.com/repos/o/r/pulls/2"
    current = {
        "pull_request_url": url,
        "id": 10,
        "in_reply_to_id": None,
        "user": {"login": "u"},
        "path": "a.py",
        "line": 5,
        "original_line": 3,
        "created_at": "c",
        "body": "fix",
    }
    # GitHub sets `line` to null once a later push outdates the comment.
    outdated_reply = {
        **current,
        "id": 11,
        "in_reply_to_id": 10,
        "line": None,
        "original_line": 7,
        "body": "done",
    }
    out = output(run, {"pulls/comments": [[current, outdated_reply]]})
    assert records(out / "review-comments.jsonl") == [
        {
            "number": 2,
            "id": 10,
            "in_reply_to_id": None,
            "author": "u",
            "path": "a.py",
            "line": 5,
            "created_at": "c",
            "body": "fix",
        },
        {
            "number": 2,
            "id": 11,
            "in_reply_to_id": 10,
            "author": "u",
            "path": "a.py",
            "line": 7,
            "created_at": "c",
            "body": "done",
        },
    ]


def test_reads_reviews_of_prs_past_the_first_page_up_to_a_full_page_of_them(run):
    review = {"author": {"login": "u"}, "state": "APPROVED", "submittedAt": "s", "body": "b"}
    hundred = [{**review, "body": str(i)} for i in range(100)]
    out = output(
        run,
        {
            "graphql": [prs_page((2, 1, [review])), prs_page((4, 100, hundred))],
            "pulls/4/reviews": [[{"user": {"login": "u"}, "body": "fetched again"}]],
        },
    )
    reviews = records(out / "reviews.jsonl")
    assert reviews[0] == {
        "number": 2,
        "author": "u",
        "state": "APPROVED",
        "submitted_at": "s",
        "body": "b",
    }
    assert [(r["number"], r["body"]) for r in reviews[1:]] == [(4, str(i)) for i in range(100)]


def test_reads_every_review_of_a_pr_with_more_than_a_page_of_them(run):
    many = [{"author": {"login": "u"}, "body": str(i)} for i in range(101)]
    rest_review = {"user": {"login": "u"}, "state": "COMMENTED", "submitted_at": "s"}
    out = output(
        run,
        {
            "graphql": [prs_page((2, 101, many), (3, 1, [{"body": "one"}]))],
            "pulls/2/reviews": [
                [{**rest_review, "body": str(i)} for i in range(100)],
                [{**rest_review, "body": "100"}],
            ],
        },
    )
    reviews = records(out / "reviews.jsonl")
    assert [(r["number"], r["body"]) for r in reviews] == [(3, "one")] + [
        (2, str(i)) for i in range(101)
    ]
    assert reviews[1] == {
        "number": 2,
        "author": "u",
        "state": "COMMENTED",
        "submitted_at": "s",
        "body": "0",
    }


def test_fails_and_leaves_nothing_behind_when_a_request_fails(run, tmp_path):
    result = run({"issues/comments": "FAIL"})
    assert result.returncode != 0
    assert list((tmp_path / "tmp").iterdir()) == []
