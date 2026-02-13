import copy
import re
import time
import difflib
from github import GithubException
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings
from pr_agent.algo.utils import find_line_number_of_relevant_line_in_file
from pr_agent.algo.git_patch_processing import extract_hunk_headers
from pr_agent.algo.language_handler import set_file_languages

def create_inline_comment(body: str, relevant_file: str, relevant_line_in_file: str, diff_files, absolute_position: int = None, max_comment_chars=65000):
    body = body[:max_comment_chars]
    position, absolute_position = find_line_number_of_relevant_line_in_file(diff_files,
                                                                            relevant_file.strip('`'),
                                                                            relevant_line_in_file,
                                                                            absolute_position)
    if position == -1:
        get_logger().info(f"Could not find position for {relevant_file} {relevant_line_in_file}")
        subject_type = "FILE"
    else:
        subject_type = "LINE"
    path = relevant_file.strip()
    return dict(body=body, path=path, position=position) if subject_type == "LINE" else {}

def try_fix_invalid_inline_comments(invalid_comments: list[dict]) -> list[dict]:
    fixed_comments = []
    for comment in invalid_comments:
        try:
            fixed_comment = copy.deepcopy(comment)
            if "```suggestion" in comment["body"]:
                fixed_comment["body"] = comment["body"].split("```suggestion")[0]
            if "start_line" in comment:
                fixed_comment["line"] = comment["start_line"]
                del fixed_comment["start_line"]
            if "start_side" in comment:
                fixed_comment["side"] = comment["start_side"]
                del fixed_comment["start_side"]
            if fixed_comment != comment:
                fixed_comments.append(fixed_comment)
        except Exception as e:
            get_logger().error(f"Failed to fix inline comment, error: {e}")
    return fixed_comments

def validate_comments_inside_hunks(code_suggestions, diff_files):
    code_suggestions_copy = copy.deepcopy(code_suggestions)
    RE_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[ ]?(.*)")
    diff_files = set_file_languages(diff_files)
    for suggestion in code_suggestions_copy:
        try:
            relevant_file_path = suggestion['relevant_file']
            for file in diff_files:
                if file.filename == relevant_file_path:
                    patch_str = file.patch
                    if not hasattr(file, 'patches_range'):
                        file.patches_range = []
                        patch_lines = patch_str.splitlines()
                        for i, line in enumerate(patch_lines):
                            if line.startswith('@@'):
                                match = RE_HUNK_HEADER.match(line)
                                if match:
                                    section_header, size1, size2, start1, start2 = extract_hunk_headers(match)
                                    file.patches_range.append({'start': start2, 'end': start2 + size2 - 1})
                    patches_range = file.patches_range
                    comment_start_line = suggestion.get('relevant_lines_start', None)
                    comment_end_line = suggestion.get('relevant_lines_end', None)
                    original_suggestion = suggestion.get('original_suggestion', None)
                    if not comment_start_line or not comment_end_line or not original_suggestion: continue
                    is_valid_hunk = False
                    min_distance = float('inf')
                    patch_range_min = None
                    for i, patch_range in enumerate(patches_range):
                        d1 = comment_start_line - patch_range['start']
                        d2 = patch_range['end'] - comment_end_line
                        if d1 >= 0 and d2 >= 0:
                            is_valid_hunk = True
                            min_distance = 0
                            patch_range_min = patch_range
                            break
                        elif d1 * d2 <= 0:
                            d1_clip = abs(min(0, d1))
                            d2_clip = abs(min(0, d2))
                            d = max(d1_clip, d2_clip)
                            if d < min_distance:
                                patch_range_min = patch_range
                                min_distance = min(min_distance, d)
                    if not is_valid_hunk:
                        if min_distance < 10:
                            suggestion['relevant_lines_start'] = max(suggestion['relevant_lines_start'], patch_range_min['start'])
                            suggestion['relevant_lines_end'] = min(suggestion['relevant_lines_end'], patch_range_min['end'])
                            body = suggestion['body'].strip()
                            existing_code = original_suggestion['existing_code'].rstrip() + "\n"
                            improved_code = original_suggestion['improved_code'].rstrip() + "\n"
                            diff = difflib.unified_diff(existing_code.split('\n'), improved_code.split('\n'), n=999)
                            patch_orig = "\n".join(diff)
                            patch = "\n".join(patch_orig.splitlines()[5:]).strip('\n')
                            diff_code = f"\n\n<details><summary>New proposed code:</summary>\n\n```diff\n{patch.rstrip()}\n```"
                            body = re.sub(r'```suggestion.*?```', diff_code, body, flags=re.DOTALL)
                            body += "\n\n</details>"
                            suggestion['body'] = body
                            get_logger().info(f"Comment was moved to a valid hunk, start_line={suggestion['relevant_lines_start']}, end_line={suggestion['relevant_lines_end']}, file={file.filename}")
                        else:
                            get_logger().error(f"Comment is not inside a valid hunk, start_line={suggestion['relevant_lines_start']}, end_line={suggestion['relevant_lines_end']}, file={file.filename}")
        except Exception as e:
            get_logger().error(f"Failed to process patch for committable comment, error: {e}")
    return code_suggestions_copy

def publish_code_suggestions(provider, code_suggestions: list) -> bool:
    post_parameters_list = []
    diff_files = provider.get_diff_files()
    code_suggestions_validated = validate_comments_inside_hunks(code_suggestions, diff_files)
    for suggestion in code_suggestions_validated:
        body = suggestion['body']
        relevant_file = suggestion['relevant_file']
        relevant_lines_start = suggestion['relevant_lines_start']
        relevant_lines_end = suggestion['relevant_lines_end']
        if not relevant_lines_start or relevant_lines_start == -1:
            get_logger().exception(f"Failed to publish code suggestion, relevant_lines_start is {relevant_lines_start}")
            continue
        if relevant_lines_end < relevant_lines_start:
            get_logger().exception(f"Failed to publish code suggestion, relevant_lines_end is {relevant_lines_end} and relevant_lines_start is {relevant_lines_start}")
            continue
        if relevant_lines_end > relevant_lines_start:
            post_parameters = {"body": body, "path": relevant_file, "line": relevant_lines_end, "start_line": relevant_lines_start, "start_side": "RIGHT"}
        else:
            post_parameters = {"body": body, "path": relevant_file, "line": relevant_lines_start, "side": "RIGHT"}
        post_parameters_list.append(post_parameters)
    try:
        provider.publish_inline_comments(post_parameters_list)
        return True
    except Exception as e:
        get_logger().error(f"Failed to publish code suggestion, error: {e}")
        return False

class GithubCommentHandler:
    def __init__(self, provider):
        self.provider = provider

    def publish_persistent_comment(self, pr_comment: str, initial_header: str, update_header: bool = True, name='review', final_update_message=True):
        self.provider.publish_persistent_comment_full(pr_comment, initial_header, update_header, name, final_update_message)

    def publish_comment(self, pr_comment: str, is_temporary: bool = False):
        if not self.provider.pr and not self.provider.issue_main: return None
        if is_temporary and not get_settings().config.publish_output_progress: return None
        pr_comment = self.provider.limit_output_characters(pr_comment, self.provider.max_comment_chars)
        if self.provider.issue_main: return self.provider.issue_main.create_comment(pr_comment)
        response = self.provider.pr.create_issue_comment(pr_comment)
        if hasattr(response, "user") and hasattr(response.user, "login"): self.provider.github_user_id = response.user.login
        response.is_temporary = is_temporary
        if not hasattr(self.provider.pr, 'comments_list'): self.provider.pr.comments_list = []
        self.provider.pr.comments_list.append(response)
        return response

    def publish_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, original_suggestion=None):
        self.publish_inline_comments([create_inline_comment(self.provider.limit_output_characters(body, self.provider.max_comment_chars), relevant_file, relevant_line_in_file, self.provider.diff_files, None, self.provider.max_comment_chars)])

    def create_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, absolute_position: int = None):
        return create_inline_comment(body, relevant_file, relevant_line_in_file, self.provider.diff_files, absolute_position, self.provider.max_comment_chars)

    def publish_inline_comments(self, comments: list[dict], disable_fallback: bool = False):
        try: self.provider.pr.create_review(commit=self.provider.last_commit_id, comments=comments)
        except Exception as e:
            if getattr(e, "status", None) != 422 or disable_fallback: raise e
            self._publish_inline_comments_fallback_with_verification(comments)

    def _publish_inline_comments_fallback_with_verification(self, comments: list[dict]):
        verified, invalid = self._verify_code_comments(comments)
        if verified:
            try: self.provider.pr.create_review(commit=self.provider.last_commit_id, comments=verified)
            except: pass
        if invalid and get_settings().github.try_fix_invalid_inline_comments:
            for comment in try_fix_invalid_inline_comments([c for c, _ in invalid]):
                try: self.publish_inline_comments([comment], disable_fallback=True)
                except: pass

    def _verify_code_comment(self, comment: dict):
        try:
            data = self.provider.pr._requester.requestJsonAndCheck("POST", f"{self.provider.pr.url}/reviews", input=dict(commit_id=self.provider.last_commit_id.sha, comments=[comment]))[1]
            try: self.provider.pr._requester.requestJsonAndCheck("DELETE", f"{self.provider.pr.url}/reviews/{data['id']}")
            except: pass
            return True, None
        except Exception as e: return False, e

    def _verify_code_comments(self, comments: list[dict]) -> tuple[list[dict], list[tuple[dict, Exception]]]:
        verified, invalid = [], []
        for comment in comments:
            time.sleep(1)
            is_verified, e = self._verify_code_comment(comment)
            verified.append(comment) if is_verified else invalid.append((comment, e))
        return verified, invalid

    def publish_code_suggestions(self, code_suggestions: list) -> bool: return publish_code_suggestions(self.provider, code_suggestions)

    def edit_comment(self, comment, body: str):
        try: comment.edit(body=self.provider.limit_output_characters(body, self.provider.max_comment_chars))
        except GithubException as e: get_logger().warning("Failed to edit github comment", artifact={"error": e}) if e.status == 403 else get_logger().exception("Failed to edit github comment")

    def edit_comment_from_comment_id(self, comment_id: int, body: str):
        try: self.provider.pr._requester.requestJsonAndCheck("PATCH", f"{self.provider.base_url}/repos/{self.provider.repo}/issues/comments/{comment_id}", input={"body": self.provider.limit_output_characters(body, self.provider.max_comment_chars)})
        except Exception as e: get_logger().exception(f"Failed to edit comment, error: {e}")

    def reply_to_comment_from_comment_id(self, comment_id: int, body: str):
        try: self.provider.pr._requester.requestJsonAndCheck("POST", f"{self.provider.base_url}/repos/{self.provider.repo}/pulls/{self.provider.pr_num}/comments/{comment_id}/replies", input={"body": self.provider.limit_output_characters(body, self.provider.max_comment_chars)})
        except Exception as e: get_logger().exception(f"Failed to reply comment, error: {e}")

    def get_comment_body_from_comment_id(self, comment_id: int):
        try: return self.provider.pr._requester.requestJsonAndCheck("GET", f"{self.provider.base_url}/repos/{self.provider.repo}/issues/comments/{comment_id}")[1].get("body", "")
        except Exception: return None

    def publish_file_comments(self, file_comments: list) -> bool:
        try:
            existing_comments = self.provider.pr._requester.requestJsonAndCheck("GET", f"{self.provider.pr.url}/comments")[1]
            for comment in file_comments:
                comment.update({'commit_id': self.provider.last_commit_id.sha, 'body': self.provider.limit_output_characters(comment['body'], self.provider.max_comment_chars)})
                same_creator = lambda c: (get_settings().get("GITHUB.APP_NAME", "").lower() in c['user']['login'].lower()) if self.provider.deployment_type == 'app' else (self.provider.github_user_id == c['user']['login'])
                found = next((c for c in existing_comments if c['subject_type'] == 'file' and comment['path'] == c['path'] and same_creator(c)), None)
                if found: self.provider.pr._requester.requestJsonAndCheck("PATCH", f"{self.provider.base_url}/repos/{self.provider.repo}/pulls/comments/{found['id']}", input={"body": comment['body']})
                else: self.provider.pr._requester.requestJsonAndCheck("POST", f"{self.provider.pr.url}/comments", input=comment)
            return True
        except Exception: return False

    def remove_initial_comment(self):
        try: [self.remove_comment(c) for c in getattr(self.provider.pr, 'comments_list', []) if c.is_temporary]
        except Exception: pass

    def remove_comment(self, comment):
        try: comment.delete()
        except Exception: pass

    def get_review_thread_comments(self, comment_id: int) -> list[dict]:
        try:
            all_comments = list(self.provider.pr.get_comments())
            target = next((c for c in all_comments if c.id == comment_id), None)
            if not target: return []
            root_id = target.raw_data.get("in_reply_to_id", target.id)
            return [c for c in all_comments if c.id == root_id or c.raw_data.get("in_reply_to_id") == root_id]
        except Exception: return []
