from pr_agent.algo.utils import clip_tokens
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

class GithubPRInteraction:
    def __init__(self, provider):
        self.provider = provider

    def publish_description(self, pr_title: str, pr_body: str):
        self.provider.pr.edit(title=pr_title, body=pr_body)

    def get_title(self):
        return self.provider.pr.title

    def get_languages(self):
        languages = self.provider._get_repo().get_languages()
        return languages

    def get_pr_branch(self):
        return self.provider.pr.head.ref

    def get_pr_description_full(self):
        return self.provider.pr.body

    def get_commit_messages(self):
        """
        Retrieves the commit messages of a pull request.

        Returns:
            str: A string containing the commit messages of the pull request.
        """
        max_tokens = get_settings().get("CONFIG.MAX_COMMITS_TOKENS", None)
        try:
            commit_list = self.provider.pr.get_commits()
            commit_messages = [commit.commit.message for commit in commit_list]
            commit_messages_str = "\n".join([f"{i + 1}. {message}" for i, message in enumerate(commit_messages)])
        except Exception:
            commit_messages_str = ""
        if max_tokens:
            commit_messages_str = clip_tokens(commit_messages_str, max_tokens)
        return commit_messages_str

    def auto_approve(self) -> bool:
        try:
            res = self.provider.pr.create_review(event="APPROVE")
            if res.state == "APPROVED":
                return True
            return False
        except Exception as e:
            get_logger().exception(f"Failed to auto-approve, error: {e}")
            return False
