"""Tests for the consumer re-sync script's pure decisions.

The clone/commit/push/PR side runs only in the workflow against the app installation; what is
tested here is every choice that side acts on.
"""

from typing import Any

from sync_consumers import arm_auto_merge, bot_identity, consumer_repos, pr_body
from sync_copilot_instructions import INSTRUCTIONS_PATH, SOURCE_URL


def repo(full_name: str, archived: bool = False) -> dict[str, Any]:
    return {"full_name": full_name, "archived": archived}


class TestConsumerRepos:
    def test_lists_every_repo_the_installation_reaches(self):
        payload = {"repositories": [repo("org/a"), repo("org/b")]}
        assert consumer_repos(payload) == ["org/a", "org/b"]

    def test_skips_archived_repos_which_reject_pushes(self):
        payload = {"repositories": [repo("org/a"), repo("org/old", archived=True)]}
        assert consumer_repos(payload) == ["org/a"]

    def test_empty_installation_has_no_consumers(self):
        assert consumer_repos({"repositories": []}) == []


class TestArmAutoMerge:
    def test_arms_when_the_repo_allows_auto_merge(self):
        assert arm_auto_merge({"allow_auto_merge": True}) is True

    def test_leaves_the_pr_open_when_the_repo_disallows_it(self):
        assert arm_auto_merge({"allow_auto_merge": False}) is False

    def test_treats_an_absent_setting_as_disallowed(self):
        assert arm_auto_merge({}) is False


class TestBotIdentity:
    def test_commits_as_the_apps_bot_account(self):
        name, email = bot_identity("conventions-sync", 123)
        assert name == "conventions-sync[bot]"
        # GitHub attributes a commit to the bot only through this noreply form.
        assert email == "123+conventions-sync[bot]@users.noreply.github.com"


class TestPrBody:
    def test_links_the_source_commit(self):
        assert f"{SOURCE_URL}/commit/abc123" in pr_body("abc123")

    def test_names_the_regenerated_file(self):
        assert str(INSTRUCTIONS_PATH) in pr_body("abc123")

    def test_is_ascii_per_the_prose_conventions(self):
        assert pr_body("abc123").isascii()
