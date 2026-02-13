from __future__ import annotations
import traceback
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from starlette_context import context

from pr_agent.algo.file_filter import filter_ignored
from pr_agent.algo.language_handler import is_valid_file
from pr_agent.algo.types import EDIT_TYPE
from pr_agent.algo.utils import load_large_diff
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.git_provider import MAX_FILES_ALLOWED_FULL, FilePatchInfo
from pr_agent.log import get_logger
from pr_agent.servers.utils import RateLimitExceeded


@retry(retry=retry_if_exception_type(RateLimitExceeded),
       stop=stop_after_attempt(get_settings().github.ratelimit_retries),
       wait=wait_exponential(multiplier=2, min=2, max=60))
def get_github_diff_files(provider) -> list[FilePatchInfo]:
    """
    Retrieves the list of files that have been modified, added, deleted, or renamed in a pull request in GitHub,
    along with their content and patch information.
    """
    try:
        try:
            diff_files = context.get("diff_files", None)
            if diff_files:
                return diff_files
        except Exception:
            pass

        if provider.diff_files:
            return provider.diff_files

        # filter files using [ignore] patterns
        files_original = provider.get_files()
        files = filter_ignored(files_original)
        if files_original != files:
            try:
                names_original = [file.filename for file in files_original]
                names_new = [file.filename for file in files]
                get_logger().info(f"Filtered out [ignore] files for pull request:", extra=
                {"files": names_original,
                 "filtered_files": names_new})
            except Exception:
                pass

        diff_files = []
        invalid_files_names = []
        is_close_to_rate_limit = False

        # The base.sha will point to the current state of the base branch (including parallel merges), not the original base commit when the PR was created
        # We can fix this by finding the merge base commit between the PR head and base branches
        # Note that The pr.head.sha is actually correct as is - it points to the latest commit in your PR branch.
        # This SHA isn't affected by parallel merges to the base branch since it's specific to your PR's branch.
        repo = provider.repo_obj
        pr = provider.pr
        try:
            compare = repo.compare(pr.base.sha, pr.head.sha) # communication with GitHub
            merge_base_commit = compare.merge_base_commit
        except Exception as e:
            get_logger().error(f"Failed to get merge base commit: {e}")
            merge_base_commit = pr.base
        if merge_base_commit.sha != pr.base.sha:
            get_logger().info(
                f"Using merge base commit {merge_base_commit.sha} instead of base commit ")

        counter_valid = 0
        for file in files:
            if not is_valid_file(file.filename):
                invalid_files_names.append(file.filename)
                continue

            patch = file.patch
            if is_close_to_rate_limit:
                new_file_content_str = ""
                original_file_content_str = ""
            else:
                # allow only a limited number of files to be fully loaded. We can manage the rest with diffs only
                counter_valid += 1
                avoid_load = False
                if counter_valid >= MAX_FILES_ALLOWED_FULL and patch and not provider.incremental.is_incremental:
                    avoid_load = True
                    if counter_valid == MAX_FILES_ALLOWED_FULL:
                        get_logger().info(f"Too many files in PR, will avoid loading full content for rest of files")

                if avoid_load:
                    new_file_content_str = ""
                else:
                    new_file_content_str = provider._get_pr_file_content(file, provider.pr.head.sha)  # communication with GitHub

                if provider.incremental.is_incremental and provider.unreviewed_files_set:
                    original_file_content_str = provider._get_pr_file_content(file, provider.incremental.last_seen_commit_sha)
                    patch = load_large_diff(file.filename, new_file_content_str, original_file_content_str)
                    provider.unreviewed_files_set[file.filename] = patch
                else:
                    if avoid_load:
                        original_file_content_str = ""
                    else:
                        original_file_content_str = provider._get_pr_file_content(file, merge_base_commit.sha)
                        # original_file_content_str = self._get_pr_file_content(file, self.pr.base.sha)
                    if not patch:
                        patch = load_large_diff(file.filename, new_file_content_str, original_file_content_str)


            if file.status == 'added':
                edit_type = EDIT_TYPE.ADDED
            elif file.status == 'removed':
                edit_type = EDIT_TYPE.DELETED
            elif file.status == 'renamed':
                edit_type = EDIT_TYPE.RENAMED
            elif file.status == 'modified':
                edit_type = EDIT_TYPE.MODIFIED
            else:
                get_logger().error(f"Unknown edit type: {file.status}")
                edit_type = EDIT_TYPE.UNKNOWN

            # count number of lines added and removed
            if hasattr(file, 'additions') and hasattr(file, 'deletions'):
                num_plus_lines = file.additions
                num_minus_lines = file.deletions
            else:
                patch_lines = patch.splitlines(keepends=True)
                num_plus_lines = len([line for line in patch_lines if line.startswith('+')])
                num_minus_lines = len([line for line in patch_lines if line.startswith('-')])

            file_patch_canonical_structure = FilePatchInfo(original_file_content_str, new_file_content_str, patch,
                                                           file.filename, edit_type=edit_type,
                                                           num_plus_lines=num_plus_lines,
                                                           num_minus_lines=num_minus_lines,)
            diff_files.append(file_patch_canonical_structure)
        if invalid_files_names:
            get_logger().info(f"Filtered out files with invalid extensions: {invalid_files_names}")

        provider.diff_files = diff_files
        try:
            context["diff_files"] = diff_files
        except Exception:
            pass

        return diff_files

    except Exception as e:
        get_logger().error(f"Failing to get diff files: {e}",
                           artifact={"traceback": traceback.format_exc()})
        raise RateLimitExceeded("Rate limit exceeded for GitHub API.") from e
