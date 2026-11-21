"""file-issue's filing script, with gh replaced by a fake that records its calls and plays answers."""

import subprocess

import pytest
from file_issue import file_issue, main


class FakeGh:
    """Answers each gh call by its subcommand; records every call."""

    def __init__(self, **answers: tuple[int, str]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        code, out = self.answers.get(f"{args[0]}_{args[1]}", (0, ""))
        return subprocess.CompletedProcess(args, code, stdout=out, stderr="boom" if code else "")

    def call(self, subcommand: str) -> list[str]:
        [found] = [c for c in self.calls if c[:2] == subcommand.split()]
        return found


URL = "https://github.com/o/r/issues/7\n"


def test_files_the_issue_with_its_origin_label_created_first():
    gh = FakeGh(issue_create=(0, URL))
    assert file_issue("developer", "T", "/b", None, gh) == "https://github.com/o/r/issues/7"
    assert gh.calls[0] == ["label", "create", "origin:developer", "--force", "--color", "c5def5"]
    assert gh.calls[1] == [
        "issue",
        "create",
        "--title",
        "T",
        "--body-file",
        "/b",
        "--label",
        "origin:developer",
    ]


def test_targets_the_given_repo_in_every_call():
    gh = FakeGh(issue_create=(0, URL))
    file_issue("agent", "T", "/b", "o/r", gh)
    assert all(call[call.index("--repo") + 1] == "o/r" for call in gh.calls)


def test_files_without_a_label_in_a_repo_the_session_cannot_write_to():
    gh = FakeGh(label_create=(1, ""), repo_view=(0, "READ\n"), issue_create=(0, URL))
    file_issue("proposed", "T", "/b", "up/stream", gh)
    assert gh.call("repo view")[2] == "up/stream"
    assert "--label" not in gh.call("issue create")


@pytest.mark.parametrize("permission", ["WRITE", "MAINTAIN", "ADMIN"])
def test_stops_when_a_writable_repo_refuses_the_label(permission):
    gh = FakeGh(label_create=(1, ""), repo_view=(0, permission + "\n"))
    with pytest.raises(RuntimeError, match="boom"):
        file_issue("agent", "T", "/b", None, gh)
    assert not [c for c in gh.calls if c[:2] == ["issue", "create"]]


def test_stops_when_the_permission_cannot_be_read():
    gh = FakeGh(label_create=(1, ""), repo_view=(1, ""))
    with pytest.raises(RuntimeError, match="boom"):
        file_issue("agent", "T", "/b", None, gh)
    assert not [c for c in gh.calls if c[:2] == ["issue", "create"]]


def test_reports_a_failed_filing():
    gh = FakeGh(issue_create=(1, ""))
    with pytest.raises(RuntimeError, match="boom"):
        file_issue("agent", "T", "/b", None, gh)


def test_refuses_an_unknown_origin():
    with pytest.raises(SystemExit):
        main(["--origin", "someone", "--title", "T", "--body-file", "/b"])
