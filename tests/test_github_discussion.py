"""Tests for dot-claude/bin/github-discussion, run as a plain file against a fake `gh` on PATH.

The fake serves each endpoint's pages from a JSON file, all of them only under `--paginate`, and
applies the `--jq` filter with the real jq, as `gh api` does to each page.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "dot-claude" / "bin" / "github-discussion"

FAKE_GH = """#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[1:]
endpoint = next(a for a in args if a == "graphql" or a.startswith("repos/"))
path = endpoint.removeprefix("repos/{owner}/{repo}/").split("?")[0]
pages = json.load(open(os.environ["FAKE_GH_PAGES"])).get(path, [])
jq_filter = args[args.index("--jq") + 1]
for page in pages if "--paginate" in args else pages[:1]:
    subprocess.run(["jq", "-c", jq_filter], input=json.dumps(page), text=True, check=True)
"""


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Put the fake on PATH; return a function that sets its pages and runs the script."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    pages_file = tmp_path / "pages.json"
    monkeypatch.setenv("FAKE_GH_PAGES", str(pages_file))

    def run(pages: dict[str, list[list[dict]]]) -> Path:
        pages_file.write_text(json.dumps(pages))
        result = subprocess.run([SCRIPT], check=True, capture_output=True, text=True)
        return Path(result.stdout.strip())

    return run


def records(path: Path) -> list[tuple]:
    """Each JSON line of `path` as (number, body)."""
    return [(r["number"], r["body"]) for r in map(json.loads, path.read_text().splitlines())]


ISSUE = {"number": 1, "state_reason": "not_planned"}
PR = {"number": 2, "pull_request": {"merged_at": "m"}}


def test_reads_comments_past_the_first_page(fake_gh):
    out = fake_gh(
        {
            "issues/comments": [
                [{"issue_url": "https://api.github.com/repos/o/r/issues/1", "body": "first"}],
                [{"issue_url": "https://api.github.com/repos/o/r/issues/3", "body": "second"}],
            ]
        }
    )
    assert records(out / "comments.jsonl") == [(1, "first"), (3, "second")]


def test_keeps_why_an_issue_closed_and_whether_a_pr_merged(fake_gh):
    out = fake_gh({"issues": [[ISSUE, PR]]})
    assert [
        (i["number"], i["is_pr"], i["state_reason"], i["merged_at"])
        for i in map(json.loads, (out / "issues.jsonl").read_text().splitlines())
    ] == [(1, False, "not_planned", None), (2, True, None, "m")]


def test_keeps_who_wrote_an_issue_what_and_when(fake_gh):
    issue = {
        "number": 1,
        "title": "t",
        "user": {"login": "u"},
        "body": "b",
        "state": "closed",
        "created_at": "c",
        "closed_at": "d",
    }
    out = fake_gh({"issues": [[issue]]})
    [record] = map(json.loads, (out / "issues.jsonl").read_text().splitlines())
    assert {
        k: record[k] for k in ("title", "author", "body", "state", "created_at", "closed_at")
    } == {
        "title": "t",
        "author": "u",
        "body": "b",
        "state": "closed",
        "created_at": "c",
        "closed_at": "d",
    }


def test_keeps_who_reviewed_a_pr_with_what_verdict_and_when(fake_gh):
    page = pr_reviews_page(2, 1, ["b"])
    page["data"]["repository"]["pullRequests"]["nodes"][0]["reviews"]["nodes"][0].update(
        {"user": {"login": "u"}, "state": "APPROVED", "submitted_at": "s"}
    )
    out = fake_gh({"graphql": [page]})
    [record] = map(json.loads, (out / "reviews.jsonl").read_text().splitlines())
    assert record == {
        "number": 2,
        "author": "u",
        "state": "APPROVED",
        "submitted_at": "s",
        "body": "b",
    }


def pr_reviews_page(number: int, total: int, bodies: list[str]) -> dict:
    """One page of the GraphQL listing of PRs with their reviews, holding one PR."""
    reviews = {"totalCount": total, "nodes": [{"body": b} for b in bodies]}
    return {
        "data": {
            "repository": {"pullRequests": {"nodes": [{"number": number, "reviews": reviews}]}}
        }
    }


def test_reads_reviews_of_prs_past_the_first_page(fake_gh):
    out = fake_gh(
        {"graphql": [pr_reviews_page(2, 1, ["first"]), pr_reviews_page(4, 1, ["second"])]}
    )
    assert records(out / "reviews.jsonl") == [(2, "first"), (4, "second")]


def test_reads_every_review_of_a_pr_with_more_than_one_page_of_them(fake_gh):
    out = fake_gh(
        {
            "graphql": [pr_reviews_page(2, 101, ["capped"])],
            "pulls/2/reviews": [[{"body": "all"}], [{"body": "of them"}]],
        }
    )
    assert records(out / "reviews.jsonl") == [(2, "all"), (2, "of them")]


def test_keeps_where_an_outdated_inline_comment_pointed(fake_gh):
    out = fake_gh(
        {
            "pulls/comments": [
                [
                    {
                        "pull_request_url": "https://api.github.com/repos/o/r/pulls/2",
                        "line": None,
                        "original_line": 7,
                        "body": "inline",
                    }
                ]
            ],
        }
    )
    [comment] = map(json.loads, (out / "review-comments.jsonl").read_text().splitlines())
    assert (comment["number"], comment["line"], comment["body"]) == (2, 7, "inline")
