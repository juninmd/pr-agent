import copy
import difflib
import hashlib
import itertools
import json
import re
import time
import traceback
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse

from github import AppAuthentication, Auth, Github, GithubException
from github.Issue import Issue
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from starlette_context import context

from ..algo.file_filter import filter_ignored
from ..algo.git_patch_processing import extract_hunk_headers
from ..algo.language_handler import is_valid_file
from ..algo.types import EDIT_TYPE
from ..algo.utils import (PRReviewHeader, Range, clip_tokens,
                          find_line_number_of_relevant_line_in_file,
                          load_large_diff, set_file_languages)
from ..config_loader import get_settings
from ..log import get_logger
from ..servers.utils import RateLimitExceeded
from .git_provider import (MAX_FILES_ALLOWED_FULL, FilePatchInfo, GitProvider,
                           IncrementalPR)
from pr_agent.git_providers.github_utils.url_parser import GithubURLParser
from pr_agent.git_providers.github_utils.diff_handler import get_github_diff_files

from pr_agent.git_providers.github_utils.label_handler import GithubLabelHandler
from pr_agent.git_providers.github_utils.reaction_handler import GithubReactionHandler
from pr_agent.git_providers.github_utils.file_handler import GithubFileHandler
from pr_agent.git_providers.github_utils.pr_interaction import GithubPRInteraction
from pr_agent.git_providers.github_utils.graphql_handler import GithubGraphQLHandler
from pr_agent.git_providers.github_utils.comment_handler import GithubCommentHandler

class GithubProvider(GitProvider):
    def __init__(self, pr_url: Optional[str] = None):
        self.repo_obj = None
        try: self.installation_id = context.get("installation_id", None)
        except Exception: self.installation_id = None
        self.max_comment_chars = 65000
        self.base_url = get_settings().get("GITHUB.BASE_URL", "https://api.github.com").rstrip("/")
        self.base_url_html = self.base_url.split("api/")[0].rstrip("/") if "api/" in self.base_url else "https://github.com"
        self.github_client = self._get_github_client()
        self.repo = None; self.pr_num = None; self.pr = None; self.issue_main = None; self.github_user_id = None
        self.diff_files = None; self.git_files = None; self.incremental = IncrementalPR(False)

        # Initialize Handlers
        self.label_handler = GithubLabelHandler(self)
        self.reaction_handler = GithubReactionHandler(self)
        self.file_handler = GithubFileHandler(self)
        self.pr_interaction = GithubPRInteraction(self)
        self.graphql_handler = GithubGraphQLHandler(self)
        self.comment_handler = GithubCommentHandler(self)

        if pr_url and 'pull' in pr_url:
            self.set_pr(pr_url)
            self.pr_commits = list(self.pr.get_commits())
            self.last_commit_id = self.pr_commits[-1]
            self.pr_url = self.get_pr_url()
        elif pr_url and 'issue' in pr_url: self.issue_main = self._get_issue_handle(pr_url)
        else: self.pr_commits = None

    # Delegates
    def publish_labels(self, pr_types): self.label_handler.publish_labels(pr_types)
    def get_pr_labels(self, update=False): return self.label_handler.get_pr_labels(update)
    def get_repo_labels(self): return self.label_handler.get_repo_labels()
    def add_eyes_reaction(self, issue_comment_id: int, disable_eyes: bool = False) -> Optional[int]: return self.reaction_handler.add_eyes_reaction(issue_comment_id, disable_eyes)
    def remove_reaction(self, issue_comment_id: int, reaction_id: str) -> bool: return self.reaction_handler.remove_reaction(issue_comment_id, reaction_id)
    def get_pr_file_content(self, file_path: str, branch: str) -> str: return self.file_handler.get_pr_file_content(file_path, branch)
    def create_or_update_pr_file(self, file_path: str, branch: str, contents="", message="") -> None: self.file_handler.create_or_update_pr_file(file_path, branch, contents, message)
    def delete_file(self, file_path: str, branch: str, message: str = "Delete file") -> None: self.file_handler.delete_file(file_path, branch, message)
    def _get_pr_file_content(self, file: FilePatchInfo, sha: str) -> str: return self.file_handler.get_file_content_from_obj(file, sha)
    def publish_description(self, pr_title: str, pr_body: str): self.pr_interaction.publish_description(pr_title, pr_body)
    def get_title(self): return self.pr_interaction.get_title()
    def get_languages(self): return self.pr_interaction.get_languages()
    def get_pr_branch(self): return self.pr_interaction.get_pr_branch()
    def get_pr_description_full(self): return self.pr_interaction.get_pr_description_full()
    def get_commit_messages(self): return self.pr_interaction.get_commit_messages()
    def auto_approve(self) -> bool: return self.pr_interaction.auto_approve()
    def fetch_sub_issues(self, issue_url): return self.graphql_handler.fetch_sub_issues(issue_url)

    # Comment Delegates
    def publish_persistent_comment(self, pr_comment: str, initial_header: str, update_header: bool = True, name='review', final_update_message=True): self.comment_handler.publish_persistent_comment(pr_comment, initial_header, update_header, name, final_update_message)
    def publish_comment(self, pr_comment: str, is_temporary: bool = False): return self.comment_handler.publish_comment(pr_comment, is_temporary)
    def publish_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, original_suggestion=None): self.comment_handler.publish_inline_comment(body, relevant_file, relevant_line_in_file, original_suggestion)
    def create_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, absolute_position: int = None): return self.comment_handler.create_inline_comment(body, relevant_file, relevant_line_in_file, absolute_position)
    def publish_inline_comments(self, comments: list[dict], disable_fallback: bool = False): self.comment_handler.publish_inline_comments(comments, disable_fallback)
    def _publish_inline_comments_fallback_with_verification(self, comments: list[dict]): self.comment_handler._publish_inline_comments_fallback_with_verification(comments)
    def _verify_code_comment(self, comment: dict): return self.comment_handler._verify_code_comment(comment)
    def _verify_code_comments(self, comments: list[dict]): return self.comment_handler._verify_code_comments(comments)
    def publish_code_suggestions(self, code_suggestions: list) -> bool: return self.comment_handler.publish_code_suggestions(code_suggestions)
    def edit_comment(self, comment, body: str): self.comment_handler.edit_comment(comment, body)
    def edit_comment_from_comment_id(self, comment_id: int, body: str): self.comment_handler.edit_comment_from_comment_id(comment_id, body)
    def reply_to_comment_from_comment_id(self, comment_id: int, body: str): self.comment_handler.reply_to_comment_from_comment_id(comment_id, body)
    def get_comment_body_from_comment_id(self, comment_id: int): return self.comment_handler.get_comment_body_from_comment_id(comment_id)
    def publish_file_comments(self, file_comments: list) -> bool: return self.comment_handler.publish_file_comments(file_comments)
    def remove_initial_comment(self): self.comment_handler.remove_initial_comment()
    def remove_comment(self, comment): self.comment_handler.remove_comment(comment)
    def get_review_thread_comments(self, comment_id: int) -> list[dict]: return self.comment_handler.get_review_thread_comments(comment_id)

    # Remaining methods
    def _get_issue_handle(self, issue_url) -> Optional[Issue]:
        repo_name, issue_number = GithubURLParser.parse_issue_url(issue_url)
        if not repo_name or not issue_number: return None
        try:
            repo_obj = self.github_client.get_repo(repo_name)
            return repo_obj.get_issue(issue_number) if repo_obj else None
        except Exception: return None

    def get_incremental_commits(self, incremental=IncrementalPR(False)):
        self.incremental = incremental
        if self.incremental.is_incremental:
            self.unreviewed_files_set = dict()
            self._get_incremental_commits()

    def is_supported(self, capability: str) -> bool: return True

    def _get_owner_and_repo_path(self, given_url: str) -> str:
        try:
            repo_path = None
            if 'issues' in given_url: repo_path, _ = GithubURLParser.parse_issue_url(given_url)
            elif 'pull' in given_url: repo_path, _ = GithubURLParser.parse_pr_url(given_url)
            elif given_url.endswith('.git'):
                parsed_url = urlparse(given_url)
                repo_path = (parsed_url.path.split('.git')[0])[1:]
            return repo_path if repo_path else ""
        except Exception: return ""

    def get_git_repo_url(self, issues_or_pr_url: str) -> str:
        repo_path = self._get_owner_and_repo_path(issues_or_pr_url)
        return f"{self.base_url_html}/{repo_path}.git" if repo_path and repo_path in issues_or_pr_url else ""

    def get_canonical_url_parts(self, repo_git_url:str, desired_branch:str) -> Tuple[str, str]:
        owner = repo = scheme_and_netloc = None
        if repo_git_url or self.issue_main:
            desired_branch = desired_branch if repo_git_url else self.issue_main.repository.default_branch
            html_url = repo_git_url if repo_git_url else self.issue_main.html_url
            parsed_git_url = urlparse(html_url)
            scheme_and_netloc = parsed_git_url.scheme + "://" + parsed_git_url.netloc
            repo_path = self._get_owner_and_repo_path(html_url)
            if repo_path.count('/') == 1: owner, repo = repo_path.split('/')
            else: return ("", "")
        if (not owner or not repo) and self.repo:
            owner, repo = self.repo.split('/')
            scheme_and_netloc = self.base_url_html
            desired_branch = self.repo_obj.default_branch
        return (f"{scheme_and_netloc}/{owner}/{repo}/blob/{desired_branch}", "") if all([scheme_and_netloc, owner, repo]) else ("", "")

    def get_pr_url(self) -> str: return self.pr.html_url
    def set_pr(self, pr_url: str):
        self.repo, self.pr_num = GithubURLParser.parse_pr_url(pr_url)
        self.pr = self._get_pr()

    def _get_incremental_commits(self):
        if not self.pr_commits: self.pr_commits = list(self.pr.get_commits())
        self.previous_review = self.get_previous_review(full=True, incremental=True)
        if self.previous_review:
            self.incremental.commits_range = self.get_commit_range()
            for commit in self.incremental.commits_range:
                if not commit.commit.message.startswith(f"Merge branch '{self._get_repo().default_branch}'"):
                    self.unreviewed_files_set.update({file.filename: file for file in commit.files})
        else: self.incremental.is_incremental = False

    def get_commit_range(self):
        last_review_time = self.previous_review.created_at
        first_new_commit_index = None
        for index in range(len(self.pr_commits) - 1, -1, -1):
            if self.pr_commits[index].commit.author.date > last_review_time:
                self.incremental.first_new_commit = self.pr_commits[index]
                first_new_commit_index = index
            else:
                self.incremental.last_seen_commit = self.pr_commits[index]
                break
        return self.pr_commits[first_new_commit_index:] if first_new_commit_index is not None else []

    def get_previous_review(self, *, full: bool, incremental: bool):
        if not (full or incremental): raise ValueError("At least one of full or incremental must be True")
        if not getattr(self, "comments", None): self.comments = list(self.pr.get_issue_comments())
        prefixes = []
        if full: prefixes.append(PRReviewHeader.REGULAR.value)
        if incremental: prefixes.append(PRReviewHeader.INCREMENTAL.value)
        for index in range(len(self.comments) - 1, -1, -1):
            if any(self.comments[index].body.startswith(prefix) for prefix in prefixes): return self.comments[index]

    def get_files(self):
        if self.incremental.is_incremental and self.unreviewed_files_set: return self.unreviewed_files_set.values()
        try:
            if not context.get("git_files", None): context["git_files"] = list(self.pr.get_files())
            return context["git_files"]
        except Exception: return list(self.pr.get_files())

    def get_num_of_files(self):
        try: return self.git_files.totalCount if hasattr(self.git_files, "totalCount") else len(self.git_files)
        except Exception: return -1

    @retry(retry=retry_if_exception_type(RateLimitExceeded), stop=stop_after_attempt(get_settings().github.ratelimit_retries), wait=wait_exponential(multiplier=2, min=2, max=60))
    def get_diff_files(self) -> list[FilePatchInfo]: return get_github_diff_files(self)

    def get_latest_commit_url(self) -> str: return self.last_commit_id.html_url
    def get_comment_url(self, comment) -> str: return comment.html_url

    def get_pr_owner_id(self) -> str | None: return self.repo.split('/')[0] if self.repo else None
    def get_user_id(self):
        if not self.github_user_id:
            try: self.github_user_id = self.github_client.get_user().raw_data['login']
            except Exception: self.github_user_id = ""
        return self.github_user_id

    def get_notifications(self, since: datetime):
        if get_settings().get("GITHUB.DEPLOYMENT_TYPE", "user") != 'user': raise ValueError("Deployment mode must be set to 'user'")
        return self.github_client.get_user().get_notifications(since=since)

    def get_issue_comments(self): return self.pr.get_issue_comments()
    def get_repo_settings(self):
        try: return self.repo_obj.get_contents(".pr_agent.toml").decoded_content
        except Exception: return ""

    def get_workspace_name(self): return self.repo.split('/')[0]

    def _get_github_client(self):
        self.deployment_type = get_settings().get("GITHUB.DEPLOYMENT_TYPE", "user")
        if self.deployment_type == 'app':
            auth = AppAuthentication(app_id=get_settings().github.app_id, private_key=get_settings().github.private_key, installation_id=self.installation_id)
        else: auth = Auth.Token(get_settings().github.user_token)
        return Github(auth=auth, base_url=self.base_url)

    def _get_repo(self):
        if not (hasattr(self, 'repo_obj') and hasattr(self.repo_obj, 'full_name') and self.repo_obj.full_name == self.repo):
            self.repo_obj = self.github_client.get_repo(self.repo)
        return self.repo_obj

    def _get_pr(self): return self._get_repo().get_pull(self.pr_num)

    def generate_link_to_relevant_line_number(self, suggestion) -> str:
        try:
            relevant_file = suggestion['relevant_file'].strip('`').strip("'").strip('\n')
            relevant_line_str = suggestion['relevant_line'].strip('\n')
            if not relevant_line_str: return ""
            position, absolute_position = find_line_number_of_relevant_line_in_file(self.diff_files, relevant_file, relevant_line_str)
            if absolute_position != -1:
                sha_file = hashlib.sha256(relevant_file.encode('utf-8')).hexdigest()
                return f"{self.base_url_html}/{self.repo}/pull/{self.pr_num}/files#diff-{sha_file}R{absolute_position}"
        except Exception: pass
        return ""

    def get_line_link(self, relevant_file: str, relevant_line_start: int, relevant_line_end: int = None) -> str:
        sha_file = hashlib.sha256(relevant_file.encode('utf-8')).hexdigest()
        link = f"{self.base_url_html}/{self.repo}/pull/{self.pr_num}/files#diff-{sha_file}"
        if relevant_line_start != -1: link += f"R{relevant_line_start}" + (f"-R{relevant_line_end}" if relevant_line_end else "")
        return link

    def get_lines_link_original_file(self, filepath: str, component_range: Range) -> str:
        return f"{self.base_url_html}/{self.repo}/blob/{self.last_commit_id.sha}/{filepath}/#L{component_range.line_start + 1}-L{component_range.line_end + 1}"

    def get_pr_id(self): return f"{self.repo}/{self.pr_num}" if self.repo else ""
    def calc_pr_statistics(self, pull_request_data: dict): return {}

    def _prepare_clone_url_with_token(self, repo_url_to_clone: str) -> str | None:
        github_token = self.auth.token
        scheme = "https://"
        if not github_token or scheme not in self.base_url_html: return None
        github_com = self.base_url_html.split(scheme)[1]
        if github_com not in repo_url_to_clone: return None
        clone_url = scheme + ("git:" if self.deployment_type == 'app' else "") + f"{github_token}@{github_com}{repo_url_to_clone.split(github_com)[-1]}"
        return clone_url
