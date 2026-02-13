import hashlib
from typing import Optional
from urllib.parse import urlparse
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings
from pr_agent.algo.utils import clip_tokens, find_line_number_of_relevant_line_in_file

class GitLabPRInteraction:
    def __init__(self, provider):
        self.provider = provider

    def publish_description(self, pr_title: str, pr_body: str):
        try:
            self.provider.mr.title = pr_title
            self.provider.mr.description = pr_body
            self.provider.mr.save()
        except Exception as e:
            get_logger().exception(f"Could not update merge request {self.provider.id_mr} description: {e}")

    def get_title(self):
        return self.provider.mr.title

    def get_languages(self):
        languages = self.provider.gl.projects.get(self.provider.id_project).languages()
        return languages

    def get_pr_branch(self):
        return self.provider.mr.source_branch

    def get_pr_owner_id(self) -> str | None:
        if not self.provider.gitlab_url or 'gitlab.com' in self.provider.gitlab_url:
            if not self.provider.id_project:
                return None
            return self.provider.id_project.split('/')[0]
        # extract host name
        host = urlparse(self.provider.gitlab_url).hostname
        return host

    def get_pr_description_full(self):
        return self.provider.mr.description

    def get_issue_comments(self):
        return self.provider.mr.notes.list(get_all=True)[::-1]

    def get_repo_settings(self):
        try:
            main_branch = self.provider.gl.projects.get(self.provider.id_project).default_branch
            contents = self.provider.gl.projects.get(self.provider.id_project).files.get(file_path='.pr_agent.toml', ref=main_branch).decode()
            return contents
        except Exception:
            return ""

    def get_workspace_name(self):
        return self.provider.id_project.split('/')[0]

    def add_eyes_reaction(self, issue_comment_id: int, disable_eyes: bool = False) -> Optional[int]:
        if disable_eyes:
            return None
        try:
            if not self.provider.id_mr:
                get_logger().warning("Cannot add eyes reaction: merge request ID is not set.")
                return None

            mr = self.provider.gl.projects.get(self.provider.id_project).mergerequests.get(self.provider.id_mr)
            comment = mr.notes.get(issue_comment_id)

            if not comment:
                get_logger().warning(f"Comment with ID {issue_comment_id} not found in merge request {self.provider.id_mr}.")
                return None

            award_emoji = comment.awardemojis.create({
                'name': 'eyes'
            })
            return award_emoji.id
        except Exception as e:
            get_logger().warning(f"Failed to add eyes reaction, error: {e}")
            return None

    def remove_reaction(self, issue_comment_id: int, reaction_id: str) -> bool:
        try:
            if not self.provider.id_mr:
                get_logger().warning("Cannot remove reaction: merge request ID is not set.")
                return False

            mr = self.provider.gl.projects.get(self.provider.id_project).mergerequests.get(self.provider.id_mr)
            comment = mr.notes.get(issue_comment_id)

            if not comment:
                get_logger().warning(f"Comment with ID {issue_comment_id} not found in merge request {self.provider.id_mr}.")
                return False

            reactions = comment.awardemojis.list()
            for reaction in reactions:
                if reaction.name == reaction_id:
                    reaction.delete()
                    return True

            get_logger().warning(f"Reaction '{reaction_id}' not found in comment {issue_comment_id}.")
            return False
        except Exception as e:
            get_logger().warning(f"Failed to remove reaction, error: {e}")
            return False

    def publish_labels(self, pr_types):
        try:
            self.provider.mr.labels = list(set(pr_types))
            self.provider.mr.save()
        except Exception as e:
            get_logger().warning(f"Failed to publish labels, error: {e}")

    def get_pr_labels(self, update=False):
        return self.provider.mr.labels

    def get_repo_labels(self):
        return self.provider.gl.projects.get(self.provider.id_project).labels.list()

    def get_commit_messages(self):
        max_tokens = get_settings().get("CONFIG.MAX_COMMITS_TOKENS", None)
        try:
            commit_messages_list = [commit['message'] for commit in self.provider.mr.commits()._list]
            commit_messages_str = "\n".join([f"{i + 1}. {message}" for i, message in enumerate(commit_messages_list)])
        except Exception:
            commit_messages_str = ""
        if max_tokens:
            commit_messages_str = clip_tokens(commit_messages_str, max_tokens)
        return commit_messages_str

    def get_pr_id(self):
        try:
            pr_id = self.provider.mr.web_url
            return pr_id
        except:
            return ""

    def get_line_link(self, relevant_file: str, relevant_line_start: int, relevant_line_end: int = None) -> str:
        if relevant_line_start == -1:
            link = f"{self.provider.gl.url}/{self.provider.id_project}/-/blob/{self.provider.mr.source_branch}/{relevant_file}?ref_type=heads"
        elif relevant_line_end:
            link = f"{self.provider.gl.url}/{self.provider.id_project}/-/blob/{self.provider.mr.source_branch}/{relevant_file}?ref_type=heads#L{relevant_line_start}-{relevant_line_end}"
        else:
            link = f"{self.provider.gl.url}/{self.provider.id_project}/-/blob/{self.provider.mr.source_branch}/{relevant_file}?ref_type=heads#L{relevant_line_start}"
        return link

    def generate_link_to_relevant_line_number(self, suggestion) -> str:
        try:
            relevant_file = suggestion['relevant_file'].strip('`').strip("'").rstrip()
            relevant_line_str = suggestion['relevant_line'].rstrip()
            if not relevant_line_str:
                return ""

            position, absolute_position = find_line_number_of_relevant_line_in_file \
                (self.provider.diff_files, relevant_file, relevant_line_str)

            if absolute_position != -1:
                # link to right file only
                link = f"{self.provider.gl.url}/{self.provider.id_project}/-/blob/{self.provider.mr.source_branch}/{relevant_file}?ref_type=heads#L{absolute_position}"
                return link
        except Exception as e:
            if get_settings().config.verbosity_level >= 2:
                get_logger().info(f"Failed adding line link, error: {e}")
        return ""

    def _prepare_clone_url_with_token(self, repo_url_to_clone: str) -> str | None:
        if "gitlab." not in repo_url_to_clone:
            get_logger().error(f"Repo URL: {repo_url_to_clone} is not a valid gitlab URL.")
            return None
        (scheme, base_url) = repo_url_to_clone.split("gitlab.")
        access_token = getattr(self.provider.gl, 'oauth_token', None) or getattr(self.provider.gl, 'private_token', None)
        if not all([scheme, access_token, base_url]):
            get_logger().error(f"Either no access token found, or repo URL: {repo_url_to_clone} "
                               f"is missing prefix: {scheme} and/or base URL: {base_url}.")
            return None

        clone_url = f"{scheme}oauth2:{access_token}@gitlab.{base_url}"
        return clone_url
