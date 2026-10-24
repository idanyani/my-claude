"""`lib.gh.arm_auto_merge`, with gh replaced by a fake that records its arguments."""

import pytest
from lib import gh


@pytest.fixture
def gh_args(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def run_gh_text(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(gh, "run_gh_text", run_gh_text)
    return calls


def test_pins_the_merge_to_a_given_head(gh_args):
    gh.arm_auto_merge("7", "c0ffee")
    [args] = gh_args
    assert args[args.index("--match-head-commit") + 1] == "c0ffee"


def test_leaves_the_head_unpinned_when_none_is_given(gh_args):
    gh.arm_auto_merge("7")
    [args] = gh_args
    assert "--match-head-commit" not in args
