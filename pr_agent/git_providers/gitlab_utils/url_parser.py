from urllib.parse import urlparse
from typing import Tuple
from pr_agent.log import get_logger

class GitLabURLParser:
    def __init__(self, provider):
        self.provider = provider

    def _parse_merge_request_url(self, merge_request_url: str) -> Tuple[str, int]:
        parsed_url = urlparse(merge_request_url)

        path_parts = parsed_url.path.strip('/').split('/')
        if 'merge_requests' not in path_parts:
            raise ValueError("The provided URL does not appear to be a GitLab merge request URL")

        mr_index = path_parts.index('merge_requests')
        # Ensure there is an ID after 'merge_requests'
        if len(path_parts) <= mr_index + 1:
            raise ValueError("The provided URL does not contain a merge request ID")

        try:
            mr_id = int(path_parts[mr_index + 1])
        except ValueError as e:
            raise ValueError("Unable to convert merge request ID to integer") from e

        # Handle special delimiter (-)
        project_path = "/".join(path_parts[:mr_index])
        if project_path.endswith('/-'):
            project_path = project_path[:-2]

        # Return the path before 'merge_requests' and the ID
        return project_path, mr_id

    def get_git_repo_url(self, issues_or_pr_url: str) -> str:
        provider_url = issues_or_pr_url
        repo_path = self.provider._get_project_path_from_pr_or_issue_url(provider_url)
        if not repo_path or repo_path not in issues_or_pr_url:
            get_logger().error(f"Unable to retrieve project path from url: {issues_or_pr_url}")
            return ""
        return f"{issues_or_pr_url.split(repo_path)[0]}{repo_path}.git"

    def get_canonical_url_parts(self, repo_git_url:str=None, desired_branch:str=None) -> Tuple[str, str]:
        repo_path = ""
        if not repo_git_url and not self.provider.pr_url:
            get_logger().error("Cannot get canonical URL parts: missing either context PR URL or a repo GIT URL")
            return ("", "")
        if not repo_git_url: #Use PR url as context
            repo_path = self.provider._get_project_path_from_pr_or_issue_url(self.provider.pr_url)
            try:
                desired_branch = self.provider.gl.projects.get(self.provider.id_project).default_branch
            except Exception as e:
                get_logger().exception(f"Cannot get PR: {self.provider.pr_url} default branch. Tried project ID: {self.provider.id_project}")
                return ("", "")
        else: #Use repo git url
            repo_path = repo_git_url.split('.git')[0].split('.com/')[-1]
        prefix = f"{self.provider.gitlab_url}/{repo_path}/-/blob/{desired_branch}"
        suffix = "?ref_type=heads"  # gitlab cloud adds this suffix. gitlab server does not, but it is harmless.
        return (prefix, suffix)

    def _get_project_path_from_pr_or_issue_url(self, pr_or_issue_url: str) -> str:
        repo_project_path = None
        if 'issues' in pr_or_issue_url:
            #replace 'issues' with 'merge_requests', since gitlab provider does not support issue urls, just to get the git repo url:
            pr_or_issue_url = pr_or_issue_url.replace('issues', 'merge_requests')
        if 'merge_requests' in pr_or_issue_url:
            repo_project_path, _ = self._parse_merge_request_url(pr_or_issue_url)
        if not repo_project_path:
            get_logger().error(f"url is not a valid merge requests url: {pr_or_issue_url}")
            return ""
        return repo_project_path
