from typing import Optional, Tuple
import gitlab
from pr_agent.algo.types import FilePatchInfo
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger
from pr_agent.git_providers.git_provider import GitProvider

from pr_agent.git_providers.gitlab_utils.url_parser import GitLabURLParser
from pr_agent.git_providers.gitlab_utils.comment_handler import GitLabCommentHandler
from pr_agent.git_providers.gitlab_utils.diff_handler import GitLabDiffHandler
from pr_agent.git_providers.gitlab_utils.file_handler import GitLabFileHandler
from pr_agent.git_providers.gitlab_utils.submodule_handler import GitLabSubmoduleHandler
from pr_agent.git_providers.gitlab_utils.pr_interaction import GitLabPRInteraction

class DiffNotFoundError(Exception): pass

class GitLabProvider(GitProvider):
    def __init__(self, merge_request_url: Optional[str] = None, incremental: Optional[bool] = False):
        gitlab_url = get_settings().get("GITLAB.URL", None)
        if not gitlab_url: raise ValueError("GitLab URL is not set in the config file")
        self.gitlab_url = gitlab_url
        ssl_verify = get_settings().get("GITLAB.SSL_VERIFY", True)
        gitlab_access_token = get_settings().get("GITLAB.PERSONAL_ACCESS_TOKEN", None)
        if not gitlab_access_token: raise ValueError("GitLab personal access token is not set in the config file")
        auth_method = get_settings().get("GITLAB.AUTH_TYPE", "oauth_token")
        if auth_method not in ["oauth_token", "private_token"]:
            raise ValueError(f"Unsupported GITLAB.AUTH_TYPE: '{auth_method}'. Must be 'oauth_token' or 'private_token'.")
        try:
            if auth_method == "oauth_token": self.gl = gitlab.Gitlab(url=gitlab_url, oauth_token=gitlab_access_token, ssl_verify=ssl_verify)
            else: self.gl = gitlab.Gitlab(url=gitlab_url, private_token=gitlab_access_token, ssl_verify=ssl_verify)
        except Exception as e:
            get_logger().error(f"Failed to create GitLab instance: {e}")
            raise ValueError(f"Unable to authenticate with GitLab: {e}")
        self.max_comment_chars = 65000
        self.id_project = None; self.id_mr = None; self.mr = None; self.diff_files = None; self.git_files = None
        self.pr_url = merge_request_url
        self.incremental = incremental

        # Initialize Handlers
        self.url_parser = GitLabURLParser(self)
        self.comment_handler = GitLabCommentHandler(self)
        self.diff_handler = GitLabDiffHandler(self)
        self.file_handler = GitLabFileHandler(self)
        self.submodule_handler = GitLabSubmoduleHandler(self)
        self.pr_interaction = GitLabPRInteraction(self)

        self._set_merge_request(merge_request_url)
        if get_settings().config.get("token_economy_mode", False):
            get_settings().set("config.patch_extra_lines_before", 0)
            get_settings().set("config.patch_extra_lines_after", 0)
            get_logger().info("Token economy mode enabled: reduced patch extra lines to 0")

    @property
    def pr(self): return self.mr

    def _set_merge_request(self, merge_request_url: str):
        self.id_project, self.id_mr = self._parse_merge_request_url(merge_request_url)
        self.mr = self._get_merge_request()
        try: self.last_diff = self.mr.diffs.list(get_all=True)[-1]
        except IndexError as e: raise DiffNotFoundError(f"Could not get diff for merge request {self.id_mr}") from e

    def _get_merge_request(self): return self.gl.projects.get(self.id_project).mergerequests.get(self.id_mr)

    # Delegates
    def _parse_merge_request_url(self, merge_request_url: str) -> Tuple[str, int]: return self.url_parser._parse_merge_request_url(merge_request_url)
    def get_git_repo_url(self, issues_or_pr_url: str) -> str: return self.url_parser.get_git_repo_url(issues_or_pr_url)
    def get_canonical_url_parts(self, repo_git_url:str=None, desired_branch:str=None) -> Tuple[str, str]: return self.url_parser.get_canonical_url_parts(repo_git_url, desired_branch)
    def _get_project_path_from_pr_or_issue_url(self, pr_or_issue_url: str) -> str: return self.url_parser._get_project_path_from_pr_or_issue_url(pr_or_issue_url)

    def publish_comment(self, mr_comment: str, is_temporary: bool = False): return self.comment_handler.publish_comment(mr_comment, is_temporary)
    def edit_comment(self, comment, body: str): self.comment_handler.edit_comment(comment, body)
    def edit_comment_from_comment_id(self, comment_id: int, body: str): self.comment_handler.edit_comment_from_comment_id(comment_id, body)
    def reply_to_comment_from_comment_id(self, comment_id: int, body: str): self.comment_handler.reply_to_comment_from_comment_id(comment_id, body)
    def publish_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, original_suggestion=None): self.comment_handler.publish_inline_comment(body, relevant_file, relevant_line_in_file, original_suggestion)
    def create_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, absolute_position: int = None): return self.comment_handler.create_inline_comment(body, relevant_file, relevant_line_in_file, absolute_position)
    def create_inline_comments(self, comments: list[dict]): return self.comment_handler.create_inline_comments(comments)
    def get_comment_body_from_comment_id(self, comment_id: int): return self.comment_handler.get_comment_body_from_comment_id(comment_id)
    def send_inline_comment(self, body: str, edit_type: str, found: bool, relevant_file: str, relevant_line_in_file: str, source_line_no: int, target_file: str, target_line_no: int, original_suggestion=None) -> None: self.comment_handler.send_inline_comment(body, edit_type, found, relevant_file, relevant_line_in_file, source_line_no, target_file, target_line_no, original_suggestion)
    def publish_code_suggestions(self, code_suggestions: list) -> bool: return self.comment_handler.publish_code_suggestions(code_suggestions)
    def publish_file_comments(self, file_comments: list) -> bool: return self.comment_handler.publish_file_comments(file_comments)
    def remove_initial_comment(self): self.comment_handler.remove_initial_comment()
    def remove_comment(self, comment): self.comment_handler.remove_comment(comment)
    def publish_inline_comments(self, comments: list[dict]): pass

    def get_diff_files(self) -> list[FilePatchInfo]: return self.diff_handler.get_diff_files()
    def get_files(self) -> list: return self.diff_handler.get_files()
    def get_relevant_diff(self, relevant_file: str, relevant_line_in_file: str) -> Optional[dict]: return self.diff_handler.get_relevant_diff(relevant_file, relevant_line_in_file)
    def search_line(self, relevant_file, relevant_line_in_file): return self.diff_handler.search_line(relevant_file, relevant_line_in_file)
    def find_in_file(self, file, relevant_line_in_file): return self.diff_handler.find_in_file(file, relevant_line_in_file)
    def get_edit_type(self, relevant_line_in_file): return self.diff_handler.get_edit_type(relevant_line_in_file)

    def get_pr_file_content(self, file_path: str, branch: str) -> str: return self.file_handler.get_pr_file_content(file_path, branch)
    def create_or_update_pr_file(self, file_path: str, branch: str, contents="", message="") -> None: self.file_handler.create_or_update_pr_file(file_path, branch, contents, message)
    def delete_file(self, file_path: str, branch: str, message: str = "Delete file") -> None: self.file_handler.delete_file(file_path, branch, message)

    def _get_gitmodules_map(self) -> dict[str, str]: return self.submodule_handler._get_gitmodules_map()
    def _url_to_project_path(self, url: str) -> str | None: return self.submodule_handler._url_to_project_path(url)
    def _project_by_path(self, proj_path: str): return self.submodule_handler._project_by_path(proj_path)
    def _compare_submodule(self, proj_path: str, old_sha: str, new_sha: str) -> list[dict]: return self.submodule_handler._compare_submodule(proj_path, old_sha, new_sha)
    def expand_submodule_changes(self, changes: list[dict]) -> list[dict]: return self.submodule_handler.expand_submodule_changes(changes)

    def publish_description(self, pr_title: str, pr_body: str): self.pr_interaction.publish_description(pr_title, pr_body)
    def get_title(self): return self.pr_interaction.get_title()
    def get_languages(self): return self.pr_interaction.get_languages()
    def get_pr_branch(self): return self.pr_interaction.get_pr_branch()
    def get_pr_owner_id(self) -> str | None: return self.pr_interaction.get_pr_owner_id()
    def get_pr_description_full(self): return self.pr_interaction.get_pr_description_full()
    def get_issue_comments(self): return self.pr_interaction.get_issue_comments()
    def get_repo_settings(self): return self.pr_interaction.get_repo_settings()
    def get_workspace_name(self): return self.pr_interaction.get_workspace_name()
    def add_eyes_reaction(self, issue_comment_id: int, disable_eyes: bool = False) -> Optional[int]: return self.pr_interaction.add_eyes_reaction(issue_comment_id, disable_eyes)
    def remove_reaction(self, issue_comment_id: int, reaction_id: str) -> bool: return self.pr_interaction.remove_reaction(issue_comment_id, reaction_id)
    def publish_labels(self, pr_types): self.pr_interaction.publish_labels(pr_types)
    def get_pr_labels(self, update=False): return self.pr_interaction.get_pr_labels(update)
    def get_repo_labels(self): return self.pr_interaction.get_repo_labels()
    def get_commit_messages(self): return self.pr_interaction.get_commit_messages()
    def get_pr_id(self): return self.pr_interaction.get_pr_id()
    def get_line_link(self, relevant_file: str, relevant_line_start: int, relevant_line_end: int = None) -> str: return self.pr_interaction.get_line_link(relevant_file, relevant_line_start, relevant_line_end)
    def generate_link_to_relevant_line_number(self, suggestion) -> str: return self.pr_interaction.generate_link_to_relevant_line_number(suggestion)
    def _prepare_clone_url_with_token(self, repo_url_to_clone: str) -> str | None: return self.pr_interaction._prepare_clone_url_with_token(repo_url_to_clone)

    def is_supported(self, capability: str) -> bool:
        if capability in ['get_issue_comments', 'create_inline_comment', 'publish_inline_comments', 'publish_file_comments']: return False
        return True

    def get_latest_commit_url(self):
        try: return self.mr.commits().next().web_url
        except StopIteration: return ""
        except Exception as e: get_logger().exception(f"Could not get latest commit URL: {e}"); return ""

    def get_comment_url(self, comment): return f"{self.mr.web_url}#note_{comment.id}"
    def publish_persistent_comment(self, pr_comment: str, initial_header: str, update_header: bool = True, name='review', final_update_message=True): self.publish_persistent_comment_full(pr_comment, initial_header, update_header, name, final_update_message)
    def get_user_id(self): return None
